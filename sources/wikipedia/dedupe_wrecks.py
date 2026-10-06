#!/usr/bin/env python3
"""
Dédoublonnage et filtrage de data/wrecks.csv (produit par wikipedia_wrecks.py).

Pourquoi tant de lignes ? Les listes Wikipedia « List of shipwrecks in <mois> <année> »
recensent tous les *sinistres* : échouements, collisions, chavirages... dont beaucoup
de navires renfloués (« refloated », « salvaged », « repaired »). Ce ne sont pas des
épaves. S'y ajoutent de vrais doublons :
  * le même navire dans une liste chronologique ET une liste géographique, avec un
    pavillon écrit différemment (« Royal Navy » / « United Kingdom ») ;
  * des préfixes variables (« HMS Basilisk » / « Basilisk ») ;
  * un même navire sinistré plusieurs fois (échoué en 1850, coulé en 1853).

Étapes :
  1. normalisation des noms (préfixes HMS/USS/SS…, accents, ponctuation) ;
  2. fusion des lignes qui pointent vers le même article Wikipedia ;
  3. fusion des lignes de même nom normalisé et même date (jour ou mois) ;
  4. fusion des lignes de même nom et même année situées à moins de --max-km ;
  5. classement de chaque ligne : wreck / refloated / unknown, d'après la note.

Sorties (à côté du CSV d'entrée) :
  wrecks_dedup.csv      toutes les lignes fusionnées, avec les colonnes status, merged_ids, n_merged
  wrecks_only.csv       uniquement les épaves probables (status = wreck ou unknown)
  dedupe_report.txt     statistiques

Usage :
  python dedupe_wrecks.py                       # data/wrecks.csv
  python dedupe_wrecks.py chemin/wrecks.csv --max-km 5
"""
from __future__ import annotations

import argparse
import collections
import csv
import math
import re
import sys
import unicodedata
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
HERE = Path(__file__).resolve().parent

# Préfixes de navires (marines militaires, civils, langues diverses)
PREFIXES = r"""
HMS|HMAS|HMCS|HMNZS|HMIS|HMSAS|HMT|HMY|HMHS|HMRT|HM|RMS|RMMV|SS|S\.S|MV|M/V|MS|M/S|MT|M/T|
TS|SV|S/V|PS|SY|FV|F/V|USS|USNS|USAT|USCGC|USC&GS|USRC|USLHT|USFC|USAHS|USSB|
SMS|SM|KMS|HNLMS|HNoMS|HDMS|HSwMS|HMNZS|FS|ORP|ARA|BNS|INS|ITS|RN|KRI|TCG|NRP|
RV|R/V|CS|LV|USCG|HSK|UC|UB|HMSub|SMU|MFV|TSS|SMY|CSS|USMS|IJN|NMS|HNMS|TB|ST|SB|SL
"""
PREFIX_RE = re.compile(r"^(?:(?:" + PREFIXES.replace("\n", "") + r")\.?\s+)+", re.I)

# Indices d'un navire récupéré (=> pas une épave)
REFLOAT_RE = re.compile(
    r"\b(refloated|re-floated|was salvaged|were salvaged|later salvaged|subsequently salvaged|"
    r"salvaged and|raised and|was raised|later raised|repaired|returned to service|"
    r"put back into service|towed (?:in|into|to)|taken in tow|got off|gotten off|was got off|"
    r"brought into|assisted into|put into|was rescued and|righted|"
    r"refitted|rebuilt|recommissioned|was beached and repaired)\b", re.I)
# Indices d'une perte totale (=> épave)
WRECK_RE = re.compile(
    r"\b(sank|sunk|foundered|wrecked|was lost|were lost|total loss|lost with all hands|"
    r"scuttled|broke up|broken up by|destroyed|went down|capsized and sank|torpedoed|"
    r"exploded and sank|burnt to the waterline|burned to the waterline|wreck lies|"
    r"the wreck|scrapped in situ)\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)", " ", s)  # « Foo (1890) », « Foo ( United Kingdom) »
    s = PREFIX_RE.sub("", s.strip())
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).lower().strip()
    s = re.sub(r"^the ", "", s)
    return s


def classify(note: str) -> str:
    if not note:
        return "unknown"
    w = WRECK_RE.search(note)
    r = REFLOAT_RE.search(note)
    if r and not w:
        return "refloated"
    if w and not r:
        return "wreck"
    if w and r:
        # « was sunk ... later raised and repaired » -> la dernière mention l'emporte
        return "refloated" if r.start() > w.start() else "wreck"
    return "unknown"


def km(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def coords(r):
    try:
        return float(r["latitude"]), float(r["longitude"])
    except (KeyError, ValueError, TypeError):
        return None


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)
            return True
        return False


def score(r) -> tuple:
    """Ligne « maîtresse » d'un groupe : article > coordonnées > date précise > note longue."""
    return (bool(r.get("wikipedia_url")), bool(r.get("latitude")), bool(r.get("depth_m")),
            len(r.get("date") or ""), len(r.get("note") or ""))


def merge_group(rows: list[dict]) -> dict:
    rows = sorted(rows, key=score, reverse=True)
    m = dict(rows[0])
    for r in rows[1:]:
        for k in ("flag", "wikipedia_url", "date", "date_raw"):
            if not m.get(k) and r.get(k):
                m[k] = r[k]
        if not m.get("latitude") and r.get("latitude"):
            m["latitude"], m["longitude"], m["coord_source"] = r["latitude"], r["longitude"], r.get("coord_source", "")
        if not m.get("depth_m") and r.get("depth_m"):
            m["depth_m"], m["depth_source"] = r["depth_m"], r.get("depth_source", "")
    srcs = []
    for r in rows:
        srcs += [s for s in (r.get("source_lists") or "").split(" | ") if s and s not in srcs]
    m["source_lists"] = " | ".join(srcs)
    m["merged_ids"] = " ".join(r["id"] for r in rows[1:])
    m["n_merged"] = len(rows)
    # Statut du groupe : épave si au moins une ligne indique une perte
    sts = {classify(r.get("note", "")) for r in rows}
    m["status"] = "wreck" if "wreck" in sts else ("refloated" if sts == {"refloated"} else
                                                  ("refloated" if "refloated" in sts else "unknown"))
    # Plusieurs sinistres du même navire : on garde l'événement de perte le plus tardif
    losses = [r for r in rows if classify(r.get("note", "")) == "wreck" and r.get("date")]
    if losses:
        last = max(losses, key=lambda r: r["date"])
        m["date"], m["date_raw"] = last["date"], last.get("date_raw", last["date"])
        if len(last.get("note", "")) > 0:
            m["note"] = last["note"]
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=str(HERE / "data" / "wrecks.csv"))
    ap.add_argument("--max-km", type=float, default=10.0, help="distance max pour fusionner (même nom, même année)")
    ap.add_argument("--keep-refloated", action="store_true", help="garder les navires renfloués dans wrecks_only.csv")
    args = ap.parse_args(argv)

    src = Path(args.csv)
    with src.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    n0 = len(rows)
    print(f"{n0} lignes lues")

    for r in rows:
        r["_n"] = norm(r.get("name", ""))
        r["_y"] = (r.get("date") or "")[:5].rstrip("-") if (r.get("date") or "").startswith("-") else (r.get("date") or "")[:4]

    dsu = DSU(len(rows))
    stats = collections.Counter()

    def union_by(key_fn, label):
        groups = collections.defaultdict(list)
        for i, r in enumerate(rows):
            k = key_fn(r)
            if k:
                groups[k].append(i)
        for idx in groups.values():
            for j in idx[1:]:
                if dsu.union(idx[0], j):
                    stats[label] += 1

    # 0. id identiques (ne devrait pas arriver)
    union_by(lambda r: r["id"], "id identique")
    # 1. même article Wikipedia
    union_by(lambda r: r.get("wikipedia_url", "").lower() or None, "même article")
    # 2. même nom normalisé + même date complète (jour)
    union_by(lambda r: (r["_n"], r["date"]) if r["_n"] and len(r.get("date") or "") >= 10 else None,
             "même nom + même jour")
    # 3. même nom + même mois, si l'une des deux dates n'a pas le jour (liste géo vs mensuelle)
    by_nm = collections.defaultdict(list)
    for i, r in enumerate(rows):
        d = r.get("date") or ""
        if r["_n"] and len(d) >= 7:
            by_nm[(r["_n"], d[:7])].append(i)
    for idx in by_nm.values():
        partial = [i for i in idx if len(rows[i]["date"]) == 7]
        full = [i for i in idx if len(rows[i]["date"]) >= 10]
        if partial and (len(set(rows[i]["date"] for i in full)) <= 1):
            for j in idx[1:]:
                if dsu.union(idx[0], j):
                    stats["même nom + même mois"] += 1
    # 4. même nom + même année + proches géographiquement
    by_ny = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if r["_n"] and r["_y"] and coords(r):
            by_ny[(r["_n"], r["_y"])].append(i)
    for idx in by_ny.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if km(coords(rows[idx[a]]), coords(rows[idx[b]])) <= args.max_km:
                    if dsu.union(idx[a], idx[b]):
                        stats[f"même nom + même année + < {args.max_km:g} km"] += 1

    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        groups[dsu.find(i)].append(r)
    out = [merge_group(g) for g in groups.values()]
    out.sort(key=lambda r: (r.get("date") or "9999", r.get("name", "")))

    out_fields = fields + [c for c in ("status", "n_merged", "merged_ids") if c not in fields]
    status_count = collections.Counter(r["status"] for r in out)

    def write(path, data):
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    d_path = src.with_name("wrecks_dedup.csv")
    o_path = src.with_name("wrecks_only.csv")
    write(d_path, out)
    keep = {"wreck", "unknown"} | ({"refloated"} if args.keep_refloated else set())
    only = [r for r in out if r["status"] in keep]
    write(o_path, only)

    report = [
        f"Lignes en entrée            : {n0}",
        f"Après fusion des doublons   : {len(out)}  (-{n0 - len(out)})",
        "Fusions par règle :",
        *[f"   {k:<40} {v}" for k, v in stats.most_common()],
        "Statut (après fusion) :",
        *[f"   {k:<12} {v}" for k, v in status_count.most_common()],
        f"Épaves probables (wrecks_only.csv) : {len(only)}",
        f"   avec coordonnées : {sum(1 for r in only if r.get('latitude'))}",
        f"   avec profondeur  : {sum(1 for r in only if r.get('depth_m'))}",
        f"   avec article     : {sum(1 for r in only if r.get('wikipedia_url'))}",
        "",
        "Noms les plus fréquents restants (à contrôler) :",
        *[f"   {n!r}: {c}" for n, c in collections.Counter(norm(r['name']) for r in only).most_common(25)],
    ]
    text = "\n".join(report)
    print(text)
    src.with_name("dedupe_report.txt").write_text(text + "\n", encoding="utf-8")
    print(f"\nÉcrit : {d_path.name}, {o_path.name}, dedupe_report.txt")


if __name__ == "__main__":
    main()
