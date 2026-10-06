#!/usr/bin/env python3
"""
Téléchargement des épaves, obstructions et coques (hulks) à jour depuis
NOAA ENC Direct to GIS (cartes marines électroniques des États-Unis).

Service : https://encdirect.noaa.gov/arcgis/rest/services/encdirect
Chaque « bande d'échelle » (overview, general, coastal, approach, harbour, berthing)
est un MapServer ArcGIS qui contient des couches Wreck_point / Wreck_area,
Obstruction_point / _line / _area, Hulk_point / _area. Les attributs sont ceux de la
norme IHO S‑57 (CATWRK, CATOBS, VALSOU, WATLEV, QUASOU, TECSOU...).

Un même objet apparaît souvent dans plusieurs bandes : le script garde la version
la plus détaillée (berthing > harbour > approach > coastal > general > overview)
et fusionne les doublons situés à moins de --merge-m mètres.

Sorties (dossier data/) :
  raw/<bande>__<couche>.geojson   données brutes par couche (cache, --refresh pour recharger)
  noaa_wrecks.geojson             objets fusionnés, géométrie complète
  noaa_wrecks.csv                 CSV au format du projet (point / centroïde)

Usage :
  python noaa_enc_wrecks.py
  python noaa_enc_wrecks.py --no-obstructions --bands harbour approach coastal
  python noaa_enc_wrecks.py --refresh
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

BASE = "https://encdirect.noaa.gov/arcgis/rest/services/encdirect"
# Du plus détaillé au plus général : la première occurrence d'un objet est conservée
BANDS = ["berthing", "harbour", "approach", "coastal", "general", "overview"]
HERE = Path(__file__).resolve().parent
UA = "ShipWrecksBot/1.0 (https://github.com/flemmens/ShipWrecks)"
log = logging.getLogger("noaa")

# --------------------------------------------------------------------------- #
# Listes de valeurs S‑57
# --------------------------------------------------------------------------- #
CATWRK = {1: "non-dangerous wreck", 2: "dangerous wreck", 3: "distributed remains of wreck",
          4: "wreck showing mast/masts", 5: "wreck showing any portion of hull or superstructure"}
CATOBS = {1: "snag/stump", 2: "wellhead", 3: "diffuser", 4: "crib", 5: "fish haven", 6: "foul area",
          7: "foul ground", 8: "ice boom", 9: "ground tackle", 10: "boom"}
WATLEV = {1: "partly submerged at high water", 2: "always dry", 3: "always under water/submerged",
          4: "covers and uncovers", 5: "awash", 6: "subject to inundation or flooding", 7: "floating"}
QUASOU = {1: "depth known", 2: "depth unknown", 3: "doubtful sounding", 4: "unreliable sounding",
          5: "no bottom found at value shown", 6: "least depth known",
          7: "least depth unknown, safe clearance at value shown", 8: "value reported (not surveyed)",
          9: "value reported (not confirmed)", 10: "maintained depth", 11: "not regularly maintained"}
TECSOU = {1: "found by echo-sounder", 2: "found by side scan sonar", 3: "found by multi-beam",
          4: "found by diver", 5: "found by lead-line", 6: "swept by wire-drag", 7: "found by laser",
          8: "swept by vertical acoustic system", 9: "found by electromagnetic sensor",
          10: "photogrammetry", 11: "satellite imagery", 12: "found by levelling",
          13: "swept by side-scan sonar", 14: "computer generated"}
EXPSOU = {1: "within range of surrounding depth", 2: "shoaler than surrounding depth",
          3: "deeper than surrounding depth"}
VERDAT = {1: "Mean low water springs", 2: "Mean lower low water springs", 3: "Mean sea level",
          4: "Lowest low water", 5: "Mean low water", 6: "Lowest low water springs",
          7: "Approximate mean low water springs", 8: "Indian spring low water", 9: "Low water springs",
          10: "Approximate lowest astronomical tide", 11: "Nearly lowest low water",
          12: "Mean lower low water", 13: "Low water", 14: "Approximate mean low water",
          15: "Approximate mean lower low water", 16: "Mean high water", 17: "Mean high water springs",
          18: "High water", 19: "Approximate mean sea level", 20: "High water springs",
          21: "Mean higher high water", 22: "Equinoctial spring low water", 23: "Lowest astronomical tide",
          24: "Local datum", 25: "International Great Lakes Datum 1985", 26: "Mean water level",
          27: "Lower low water large tide", 28: "Higher high water large tide",
          29: "Nearly highest high water", 30: "Highest astronomical tide"}


def decode(value, table: dict) -> str:
    """Décode un code S‑57 (nombre, « 2 », « 2,6 ») ; laisse le texte tel quel."""
    if value is None or value == "":
        return ""
    out = []
    for part in str(value).split(","):
        part = part.strip()
        try:
            out.append(table.get(int(float(part)), part))
        except ValueError:
            # texte tronqué par le serveur (« wreck showing any portion of h ») -> libellé complet
            full = next((v for v in table.values() if part and v.startswith(part)), part)
            out.append(full)
    return "; ".join(out)


# --------------------------------------------------------------------------- #
# Accès ArcGIS REST
# --------------------------------------------------------------------------- #
S = requests.Session()
S.headers["User-Agent"] = UA


def get(url: str, params: dict, method="GET", tries=6) -> dict:
    wait = 3.0
    for attempt in range(1, tries + 1):
        try:
            if method == "POST":
                r = S.post(url, data=params, timeout=120)
            else:
                r = S.get(url, params=params, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise requests.HTTPError(str(data["error"]))
            return data
        except (requests.RequestException, ValueError) as e:
            if attempt == tries:
                raise
            log.warning("%s – nouvel essai dans %.0fs (%s)", url, wait, e)
            time.sleep(wait)
            wait *= 2
    raise RuntimeError("unreachable")


def find_layers(band: str, kinds: list[str]) -> list[dict]:
    info = get(f"{BASE}/enc_{band}/MapServer", {"f": "json"})
    pat = re.compile(r"\.(%s)_(point|line|area)$" % "|".join(kinds), re.I)
    out = []
    for lyr in info.get("layers", []):
        m = pat.search(lyr["name"])
        if m and not lyr.get("subLayerIds"):
            out.append({"band": band, "id": lyr["id"], "name": lyr["name"],
                        "kind": m.group(1).lower(), "geom": m.group(2).lower()})
    return out


def fetch_layer(layer: dict, raw_dir: Path, refresh: bool, chunk: int, delay: float) -> list[dict]:
    fname = raw_dir / f"{layer['band']}__{layer['name'].split('.')[-1]}.geojson"
    if fname.exists() and not refresh:
        return json.loads(fname.read_text("utf-8"))["features"]
    url = f"{BASE}/enc_{layer['band']}/MapServer/{layer['id']}/query"
    ids = get(url, {"where": "1=1", "returnIdsOnly": "true", "f": "json"}).get("objectIds") or []
    ids.sort()
    feats: list[dict] = []
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        data = get(url, {"objectIds": ",".join(map(str, part)), "outFields": "*", "outSR": "4326",
                         "returnGeometry": "true", "f": "geojson"}, method="POST")
        feats.extend(data.get("features", []))
        log.info("   %s : %d/%d", layer["name"], len(feats), len(ids))
        time.sleep(delay)
    fname.parent.mkdir(parents=True, exist_ok=True)
    fname.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), "utf-8")
    return feats


# --------------------------------------------------------------------------- #
# Géométrie et fusion
# --------------------------------------------------------------------------- #
def representative_point(geom: dict):
    """Point (lon, lat) : le point lui‑même, sinon le centre des coordonnées."""
    if not geom:
        return None
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Point":
        return c[0], c[1]
    pts = []

    def walk(x):
        if isinstance(x, (list, tuple)) and x and isinstance(x[0], (int, float)):
            pts.append(x)
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
    walk(c)
    pts = list({(p[0], p[1]) for p in pts})  # ignore le point de fermeture des anneaux
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def dist_m(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


class Grid:
    """Index spatial simple pour retrouver les objets proches."""

    def __init__(self, cell_deg: float):
        self.cell = cell_deg
        self.g = defaultdict(list)

    def key(self, p):
        return int(math.floor(p[0] / self.cell)), int(math.floor(p[1] / self.cell))

    def near(self, p):
        kx, ky = self.key(p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                yield from self.g.get((kx + dx, ky + dy), [])

    def add(self, p, item):
        self.g[self.key(p)].append(item)


def stable_id(kind: str, pt, name: str) -> str:
    key = f"{kind}|{pt[1]:.4f}|{pt[0]:.4f}|{(name or '').strip().lower()}"
    return "NOAA-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def build_record(feat: dict, layer: dict, pt) -> dict:
    a = {k.upper(): v for k, v in (feat.get("properties") or {}).items()}
    kind = layer["kind"]
    if kind == "wreck":
        category = decode(a.get("CATWRK"), CATWRK)
    elif kind == "obstruction":
        category = decode(a.get("CATOBS"), CATOBS)
    else:
        category = "hulk"
    name = (a.get("OBJNAM") or a.get("NOBJNM") or "").strip()
    note_parts = [p for p in (a.get("INFORM"), a.get("NINFOM")) if p]
    valsou = a.get("VALSOU")
    return {
        "id": stable_id(kind, pt, name),
        "name": name,
        "flag": "",
        "date": "",
        "latitude": f"{pt[1]:.6f}",
        "longitude": f"{pt[0]:.6f}",
        "depth_m": "" if valsou in (None, "") else round(float(valsou), 2),
        "note": " | ".join(note_parts),
        "kind": kind,
        "category": category,
        "geometry_type": layer["geom"],
        "water_level": decode(a.get("WATLEV"), WATLEV),
        "depth_quality": decode(a.get("QUASOU"), QUASOU),
        "depth_technique": decode(a.get("TECSOU"), TECSOU),
        "depth_exposition": decode(a.get("EXPSOU"), EXPSOU),
        "vertical_datum": decode(a.get("VERDAT"), VERDAT),
        "height_m": a.get("HEIGHT") if a.get("HEIGHT") is not None else "",
        "source_date": a.get("SORDAT") or "",
        "source_ind": a.get("SORIND") or "",
        "enc_cell": a.get("DSNM") or "",
        "bands": layer["band"],
        "depth_source": "noaa_enc" if valsou not in (None, "") else "",
        "coord_source": "noaa_enc",
    }


CSV_FIELDS = ["id", "name", "flag", "date", "latitude", "longitude", "depth_m", "note",
              "kind", "category", "geometry_type", "water_level", "depth_quality", "depth_technique",
              "depth_exposition", "vertical_datum", "height_m", "source_date", "source_ind",
              "enc_cell", "bands", "depth_source", "coord_source"]


def merge_into(keep: dict, other: dict):
    """Complète l'enregistrement conservé avec les champs vides de l'autre."""
    for k, v in other.items():
        if k in ("id", "bands", "latitude", "longitude", "geometry_type"):
            continue
        if keep.get(k) in ("", None) and v not in ("", None):
            keep[k] = v
    if other["bands"] not in keep["bands"].split(","):
        keep["bands"] += "," + other["bands"]


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(HERE / "data"))
    ap.add_argument("--bands", nargs="+", default=BANDS, choices=BANDS)
    ap.add_argument("--no-obstructions", action="store_true", help="épaves et coques seulement")
    ap.add_argument("--no-hulks", action="store_true")
    ap.add_argument("--merge-m", type=float, default=100.0,
                    help="distance max (m) pour fusionner un même objet présent dans plusieurs bandes")
    ap.add_argument("--chunk", type=int, default=500, help="objets par requête (max serveur : 1000)")
    ap.add_argument("--delay", type=float, default=0.3, help="pause entre requêtes (s)")
    ap.add_argument("--refresh", action="store_true", help="re-télécharger les couches déjà en cache")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    kinds = ["Wreck"] + ([] if args.no_obstructions else ["Obstruction"]) + ([] if args.no_hulks else ["Hulk"])
    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    bands = [b for b in BANDS if b in args.bands]  # ordre du plus détaillé au plus général

    grid = Grid(cell_deg=max(args.merge_m / 111_000 * 2, 0.0005))
    records: list[dict] = []
    geoms: list[dict] = []
    stats = defaultdict(int)

    for band in bands:
        layers = find_layers(band, kinds)
        log.info("Bande %s : %s", band, ", ".join(l["name"] for l in layers) or "aucune couche")
        for layer in layers:
            feats = fetch_layer(layer, raw_dir, args.refresh, min(args.chunk, 1000), args.delay)
            stats[f"brut {layer['kind']}"] += len(feats)
            for f in feats:
                pt = representative_point(f.get("geometry"))
                if pt is None:
                    continue
                rec = build_record(f, layer, pt)
                dup = None
                for idx in grid.near(pt):
                    o = records[idx]
                    if o["kind"] == rec["kind"] and dist_m(pt, (float(o["longitude"]), float(o["latitude"]))) <= args.merge_m:
                        if not rec["name"] or not o["name"] or rec["name"].lower() == o["name"].lower():
                            dup = idx
                            break
                if dup is not None:
                    merge_into(records[dup], rec)
                    stats["doublons inter-bandes"] += 1
                    continue
                grid.add(pt, len(records))
                records.append(rec)
                geoms.append(f.get("geometry"))

    # Identifiants uniques (collision improbable mais possible)
    seen = defaultdict(int)
    for r in records:
        seen[r["id"]] += 1
        if seen[r["id"]] > 1:
            r["id"] = f"{r['id']}-{seen[r['id']]}"

    out_dir.mkdir(parents=True, exist_ok=True)
    order = sorted(range(len(records)), key=lambda i: (records[i]["kind"], records[i]["id"]))
    with (out_dir / "noaa_wrecks.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for i in order:
            w.writerow(records[i])
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": geoms[i], "properties": records[i]} for i in order]}
    (out_dir / "noaa_wrecks.geojson").write_text(json.dumps(fc), "utf-8")

    by_kind = defaultdict(int)
    for r in records:
        by_kind[r["kind"]] += 1
    log.info("Terminé : %d objets uniques %s", len(records), dict(by_kind))
    for k, v in sorted(stats.items()):
        log.info("   %-28s %d", k, v)
    log.info("   avec nom %d, avec profondeur %d",
             sum(1 for r in records if r["name"]), sum(1 for r in records if r["depth_m"] != ""))
    log.info("Fichiers : %s, %s", out_dir / "noaa_wrecks.csv", out_dir / "noaa_wrecks.geojson")


if __name__ == "__main__":
    sys.exit(main())
