#!/usr/bin/env python3
"""
Récupération des épaves (shipwrecks) depuis Wikipedia (en).

Étape 1 – `lists`
    Parcourt https://en.wikipedia.org/wiki/Lists_of_shipwrecks et, récursivement,
    toutes les pages « List(s) of shipwrecks ... » (par année, par mois, par
    région). Chaque tableau est analysé et le résultat est écrit dans un CSV
    synthétique : id, nom, pavillon, date, latitude, longitude, profondeur, note.

Étape 2 – `articles`
    Pour chaque épave qui possède un article Wikipedia, récupère le texte
    (brut + HTML), les métadonnées et les images, puis les envoie dans un bucket
    Cloudflare R2 sous la clé  wrecks/<id>/...
    Les coordonnées et la profondeur manquantes dans le CSV sont complétées à
    partir de l'article.

Usage :
    python wikipedia_wrecks.py lists
    python wikipedia_wrecks.py articles              # vers R2 (variables d'env.)
    python wikipedia_wrecks.py articles --storage local --local-dir ./export
    python wikipedia_wrecks.py all

Variables d'environnement pour R2 (fichier .env accepté) :
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
    R2_PREFIX (optionnel, défaut « wrecks »)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import mimetypes
import os
import re
import sys
import threading
import time
import unicodedata
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup, Tag

API = "https://en.wikipedia.org/w/api.php"
WIKI = "https://en.wikipedia.org/wiki/"
ROOT_PAGE = "Lists of shipwrecks"
USER_AGENT = os.environ.get(
    "WIKI_USER_AGENT",
    "ShipWrecksBot/1.0 (https://github.com/; contact: flemmens@gmail.com) python-requests",
)
HERE = Path(__file__).resolve().parent
CSV_FIELDS = [
    "id", "name", "flag", "date", "latitude", "longitude", "depth_m", "note",
    "wikipedia_url", "date_raw", "depth_source", "coord_source", "source_lists",
]

log = logging.getLogger("wrecks")

try:  # lxml est plus rapide ; repli sur le parseur standard s'il n'est pas installé
    import lxml  # noqa: F401
    HTML_PARSER = "lxml"
except ImportError:
    HTML_PARSER = "html.parser"


# --------------------------------------------------------------------------- #
# HTTP / API
# --------------------------------------------------------------------------- #
_tls = threading.local()


def session() -> requests.Session:
    s = getattr(_tls, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        _tls.s = s
    return s


class Throttle:
    """Délai minimal global entre deux requêtes (tous threads confondus)."""

    def __init__(self, delay: float):
        self.delay = delay
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            sleep = self.last + self.delay - now
            if sleep > 0:
                time.sleep(sleep)
            self.last = time.monotonic()


THROTTLE = Throttle(0.2)


def http_get(url: str, params: dict | None = None, stream=False, tries=6) -> requests.Response:
    backoff = 2.0
    for attempt in range(tries):
        THROTTLE.wait()
        try:
            r = session().get(url, params=params, timeout=60, stream=stream)
        except requests.RequestException as e:
            log.warning("Erreur réseau %s (%s) – tentative %d", url, e, attempt + 1)
            time.sleep(backoff)
            backoff *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("Retry-After") or backoff)
            log.warning("HTTP %s sur %s – attente %.0fs", r.status_code, url, wait)
            time.sleep(wait)
            backoff *= 2
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"Échec après {tries} tentatives : {url}")


def api(params: dict) -> dict:
    p = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    for _ in range(5):
        data = http_get(API, p).json()
        err = data.get("error")
        if err and err.get("code") == "maxlag":
            time.sleep(5)
            continue
        if err:
            raise RuntimeError(f"API error {err}")
        return data
    raise RuntimeError("maxlag persistant")


def cached_parse(title: str, cache_dir: Path, refresh=False) -> dict | None:
    """action=parse avec cache disque. Retourne {title, pageid, revid, html} ou None."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / (hashlib.sha1(title.encode()).hexdigest() + ".json")
    if f.exists() and not refresh:
        return json.loads(f.read_text("utf-8"))
    try:
        d = api({"action": "parse", "page": title, "prop": "text|revid",
                 "redirects": "1", "disableeditsection": "1", "disabletoc": "1"})
    except RuntimeError as e:
        if "missingtitle" in str(e):
            log.warning("Page absente : %s", title)
            return None
        raise
    p = d["parse"]
    out = {"title": p["title"], "pageid": p.get("pageid"), "revid": p.get("revid"),
           "html": p["text"]}
    f.write_text(json.dumps(out, ensure_ascii=False), "utf-8")
    return out


# --------------------------------------------------------------------------- #
# Utilitaires de parsing
# --------------------------------------------------------------------------- #
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9
MONTH_RE = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?"
YEAR_RE = r"(\d{1,4})(?:\s*(BC|BCE|AD|CE))?"


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\[(?:\d+|[a-z]|note \d+|citation needed|nb \d+)\]", "", text)
    text = text.replace("﻿", "").replace("​", "")
    return re.sub(r"\s+", " ", text).strip()


def cell_text(td: Tag) -> str:
    td = BeautifulSoup(str(td), HTML_PARSER)
    for bad in td.select("sup.reference, sup.noprint, .reference, style, .geo-nondefault, "
                         ".geo-multi-punct, .mw-empty-elt, .sortkey, .noprint"):
        bad.decompose()
    return clean(td.get_text(" "))


def flag_text(td: Tag) -> str:
    txt = cell_text(td)
    if txt:
        return txt.strip("() ")
    # Pas de texte : on prend le titre/alt de l'icône de drapeau
    for a in td.find_all("a", title=True):
        return clean(a["title"]).replace("Flag of ", "")
    img = td.find("img", alt=True)
    if img:
        return clean(img["alt"]).replace("Flag of ", "")
    return ""


def year_int(y: str, era: str | None) -> int:
    v = int(y)
    return -v if era and era.upper() in ("BC", "BCE") else v


def fmt_date(y: int | None, m: int | None = None, d: int | None = None) -> str:
    if y is None:
        return ""
    ys = f"{y:04d}" if y >= 0 else f"-{abs(y):04d}"
    if m and d:
        return f"{ys}-{m:02d}-{d:02d}"
    if m:
        return f"{ys}-{m:02d}"
    return ys


def parse_date(text: str, default_year: int | None = None, default_month: int | None = None):
    """Retourne (iso_partielle, (y, m, d)) à partir d'un texte libre."""
    t = clean(text)
    # 14 May 1918 / 14 May
    m = re.search(rf"\b(\d{{1,2}})\s+{MONTH_RE}(?:,?\s+{YEAR_RE})?\b", t, re.I)
    if m:
        d, mo = int(m.group(1)), MONTHS[m.group(2).lower().rstrip(".")]
        y = year_int(m.group(3), m.group(4)) if m.group(3) else default_year
        if 1 <= d <= 31:
            return fmt_date(y, mo, d), (y, mo, d)
    # May 14, 1918 / May 14
    m = re.search(rf"\b{MONTH_RE}\s+(\d{{1,2}})(?:,\s*{YEAR_RE})?\b", t, re.I)
    if m:
        mo, d = MONTHS[m.group(1).lower().rstrip(".")], int(m.group(2))
        y = year_int(m.group(3), m.group(4)) if m.group(3) else default_year
        if 1 <= d <= 31:
            return fmt_date(y, mo, d), (y, mo, d)
    # May 1918
    m = re.search(rf"\b{MONTH_RE}\s+{YEAR_RE}\b", t, re.I)
    if m:
        mo, y = MONTHS[m.group(1).lower().rstrip(".")], year_int(m.group(2), m.group(3))
        return fmt_date(y, mo), (y, mo, None)
    # Mois seul (titre de section)
    m = re.fullmatch(rf"{MONTH_RE}", t, re.I)
    if m:
        mo = MONTHS[m.group(1).lower().rstrip(".")]
        return fmt_date(default_year, mo), (default_year, mo, None)
    # Année seule
    m = re.search(r"\b(\d{3,4})(?:\s*(BC|BCE|AD|CE))?\b", t)
    if m and (m.group(2) or 100 <= int(m.group(1)) <= 2100):
        y = year_int(m.group(1), m.group(2))
        return fmt_date(y), (y, None, None)
    m = re.search(r"\b(\d{1,4})\s*(BC|BCE)\b", t)
    if m:
        y = year_int(m.group(1), m.group(2))
        return fmt_date(y), (y, None, None)
    if default_year is not None:
        return fmt_date(default_year, default_month), (default_year, default_month, None)
    return "", (None, None, None)


def page_period(title: str):
    """« List of shipwrecks in June 1942 » -> (1942, 6)."""
    m = re.search(rf"in {MONTH_RE}\s+(\d{{4}})", title, re.I)
    if m:
        return int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")]
    m = re.search(r"in (\d{3,4})$", title)
    if m:
        return int(m.group(1)), None
    return None, None


# --- coordonnées ------------------------------------------------------------ #
def extract_coords(node: Tag):
    geo = node.select_one("span.geo")
    if geo:
        m = re.match(r"\s*(-?[\d.]+)\s*[;,]\s*(-?[\d.]+)", geo.get_text())
        if m:
            return float(m.group(1)), float(m.group(2))
    lat, lon = node.select_one(".latitude"), node.select_one(".longitude")
    if lat and lon:
        a, b = dms_to_dec(lat.get_text()), dms_to_dec(lon.get_text())
        if a is not None and b is not None:
            return a, b
    return None


def dms_to_dec(s: str):
    s = clean(s)
    m = re.match(r"(-?[\d.]+)°?\s*(?:([\d.]+)′)?\s*(?:([\d.]+)″)?\s*([NSEW])?", s)
    if not m:
        return None
    v = float(m.group(1)) + float(m.group(2) or 0) / 60 + float(m.group(3) or 0) / 3600
    if m.group(4) in ("S", "W"):
        v = -v
    return round(v, 6)


# --- profondeur ------------------------------------------------------------- #
UNIT = r"(metres|meters|metre|meter|m|feet|foot|ft|fathoms|fathom|fms?)"
NUM = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?:\s*(?:-|–|to)\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?)?"
PAREN = r"(?:\s*\([^)]{0,30}\))?"
DEPTH_PATTERNS = [
    # « in 85 feet (26 m) of water »
    re.compile(rf"{NUM}\s*-?\s*{UNIT}\b{PAREN}\s+of\s+(?:\w+\s+)?water", re.I),
    # « at a depth of 60 metres », « depth of about 30 m »
    re.compile(rf"(?<!hold )(?<!moulded )depth\s+of\s+(?:about|approximately|around|some|roughly|over|nearly|~|c\.)?\s*{NUM}\s*-?\s*{UNIT}\b", re.I),
    # « lies 40 m deep », « 60 metres deep »
    re.compile(rf"{NUM}\s*-?\s*{UNIT}\b{PAREN}\s+(?:deep|down|below the surface|beneath the surface)", re.I),
    # « at 40 m depth »
    re.compile(rf"\bat\s+{NUM}\s*-?\s*{UNIT}\b{PAREN}\s+depth", re.I),
]
TO_M = {"m": 1, "metre": 1, "metres": 1, "meter": 1, "meters": 1,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "fathom": 1.8288, "fathoms": 1.8288, "fm": 1.8288, "fms": 1.8288}


def extract_depth(text: str):
    """Profondeur en mètres (float) trouvée dans un texte, sinon None."""
    if not text:
        return None
    for pat in DEPTH_PATTERNS:
        for m in pat.finditer(text):
            ctx = text[max(0, m.start() - 25):m.start()].lower()
            if "hold" in ctx or "draught" in ctx or "draft" in ctx:
                continue
            val = float(m.group(1).replace(",", ""))
            unit = m.group(2).lower()
            depth = val * TO_M.get(unit, 1)
            if 0 < depth < 11000:
                return round(depth, 1)
    return None


# --------------------------------------------------------------------------- #
# Tableaux
# --------------------------------------------------------------------------- #
HEADER_MAP = [
    ("name", re.compile(r"^(ship|ships|name|vessel|vessel name|ship name|wreck)\b", re.I)),
    ("flag", re.compile(r"(flag|state|country|nation|nationality|navy|owner|operator)", re.I)),
    ("date", re.compile(r"(date|sunk|year|lost|when)", re.I)),
    ("note", re.compile(r"(description|notes?|remarks|fate|details|comments?|cause|summary)", re.I)),
    ("coords", re.compile(r"(coord|location|position|lat)", re.I)),
    ("depth", re.compile(r"depth", re.I)),
]


def map_headers(headers: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, h in enumerate(headers):
        for key, rx in HEADER_MAP:
            if key not in out and rx.search(h):
                out[key] = i
                break
    return out


def table_grid(table: Tag):
    """Développe rowspan/colspan. Retourne (headers, [[cell Tag|None, ...], ...])."""
    rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
    grid: list[list] = []
    pending: dict[int, tuple[Tag, int]] = {}
    for tr in rows:
        cells = [c for c in tr.find_all(["td", "th"], recursive=False)]
        row: list = []
        col = 0
        it = iter(cells)
        while True:
            if col in pending:
                c, left = pending[col]
                row.append(c)
                if left <= 1:
                    del pending[col]
                else:
                    pending[col] = (c, left - 1)
                col += 1
                continue
            c = next(it, None)
            if c is None:
                break
            span = int(re.sub(r"\D", "", c.get("colspan", "1")) or 1)
            rspan = int(re.sub(r"\D", "", c.get("rowspan", "1")) or 1)
            for _ in range(span):
                row.append(c)
                if rspan > 1:
                    pending[col] = (c, rspan - 1)
                col += 1
        while col in pending:  # cellules en fin de ligne issues d'un rowspan
            c, left = pending.pop(col)
            row.append(c)
            if left > 1:
                pending[col] = (c, left - 1)
            col += 1
        grid.append(row)
    # La première ligne composée uniquement de <th> = en-têtes
    headers: list[str] = []
    body_start = 0
    for i, row in enumerate(grid):
        if row and all(c.name == "th" for c in row):
            headers = [cell_text(c) for c in row]
            body_start = i + 1
            break
        if i > 2:
            break
    return headers, grid[body_start:]


def article_link(td: Tag) -> str | None:
    for a in td.find_all("a", href=True):
        href = a["href"]
        if "new" in (a.get("class") or []):
            continue
        if not href.startswith("/wiki/"):
            continue
        title = unquote(href[6:].split("#")[0]).replace("_", " ")
        if not title or re.match(r"^(File|Image|Category|Help|Wikipedia|Template|Special|Portal|Talk|Wiktionary):", title, re.I):
            continue
        if a.find_parent(class_="flagicon") or a.find("img"):
            continue
        return title
    return None


def parse_list_page(title: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html, HTML_PARSER)
    root = soup.select_one(".mw-parser-output") or soup
    p_year, p_month = page_period(title)
    out: list[dict] = []
    heading_ctx = {"h2": "", "h3": "", "h4": ""}

    for el in root.find_all(["h2", "h3", "h4", "table"]):
        if el.name in heading_ctx:
            heading_ctx[el.name] = clean(el.get_text())
            if el.name == "h2":
                heading_ctx["h3"] = heading_ctx["h4"] = ""
            elif el.name == "h3":
                heading_ctx["h4"] = ""
            continue
        if el.find_parent("table") is not None:
            continue
        cls = el.get("class") or []
        if "wikitable" not in cls and "sortable" not in cls:
            continue
        headers, rows = table_grid(el)
        cols = map_headers(headers)
        if "name" not in cols:
            continue
        caption = clean(el.caption.get_text()) if el.caption else ""
        # Date de contexte : légende du tableau > titres de sections > titre de page
        ctx_date = ""
        for src in (caption, heading_ctx["h4"], heading_ctx["h3"], heading_ctx["h2"]):
            if src and not re.search(r"unknown|see also|references|notes", src, re.I):
                iso, ymd = parse_date(src, p_year, p_month)
                if iso and (ymd[1] or p_year is None):
                    ctx_date = iso
                    break
        if not ctx_date and p_year:
            ctx_date = fmt_date(p_year, p_month)
        region = heading_ctx["h3"] or heading_ctx["h2"]

        for row in rows:
            if not row or not any(c is not None and c.name == "td" for c in row):
                continue  # ligne d'en-tête / séparateur

            def cell(key):
                i = cols.get(key)
                return row[i] if i is not None and i < len(row) else None

            name_td = cell("name")
            if name_td is None:
                continue
            name = cell_text(name_td)
            if not name or name.lower() in ("ship", "name", "vessel"):
                continue
            flag = flag_text(cell("flag")) if cell("flag") is not None else ""
            note = cell_text(cell("note")) if cell("note") is not None else ""
            date_raw = cell_text(cell("date")) if cell("date") is not None else ""
            if date_raw:
                date_iso, _ = parse_date(date_raw, p_year, p_month)
            else:
                date_iso, date_raw = ctx_date, ctx_date
            # Coordonnées : colonne dédiée, sinon n'importe où dans la ligne
            coords = None
            for c in ([cell("coords")] if cell("coords") is not None else []) + list(dict.fromkeys(row)):
                if c is not None:
                    coords = extract_coords(c)
                    if coords:
                        break
            depth = None
            if cell("depth") is not None:
                depth = extract_depth(cell_text(cell("depth")) + " deep") or _num_m(cell_text(cell("depth")))
            if depth is None:
                depth = extract_depth(note)
            out.append({
                "name": name,
                "flag": flag,
                "date": date_iso,
                "date_raw": date_raw,
                "latitude": f"{coords[0]:.6f}" if coords else "",
                "longitude": f"{coords[1]:.6f}" if coords else "",
                "depth_m": depth if depth is not None else "",
                "depth_source": "list" if depth is not None else "",
                "coord_source": "list" if coords else "",
                "note": note,
                "article": article_link(name_td),
                "region": region,
                "source_lists": title,
            })
    return out


def _num_m(s: str):
    m = re.search(r"([\d.,]+)", s or "")
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if re.search(r"\b(ft|feet|foot)\b", s, re.I):
        v *= 0.3048
    return round(v, 1)


# --------------------------------------------------------------------------- #
# Étape 1 : découverte des listes + CSV
# --------------------------------------------------------------------------- #
LIST_TITLE_RE = re.compile(r"^Lists? of shipwrecks\b", re.I)


def list_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, HTML_PARSER)
    found = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("/wiki/") or "new" in (a.get("class") or []):
            continue
        t = unquote(h[6:].split("#")[0]).replace("_", " ")
        if LIST_TITLE_RE.match(t):
            found.append(t)
    return list(dict.fromkeys(found))


def make_id(rec: dict) -> str:
    year = (rec.get("date") or "")[:5].rstrip("-")
    if rec.get("article"):
        key = f"a|{rec['article'].lower()}|{year}"
    else:
        key = "|".join(["n", norm(rec["name"]), rec.get("date") or "", norm(rec.get("flag", ""))])
    return "WPW-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if k == "source_lists":
            srcs = a[k].split(" | ") + [x for x in v.split(" | ") if x not in a[k].split(" | ")]
            a[k] = " | ".join(srcs)
        elif k == "note":
            if len(v) > len(a.get(k) or ""):
                a[k] = v
        elif k == "date":
            if len(v or "") > len(a.get(k) or ""):  # date plus précise
                a[k], a["date_raw"] = v, b.get("date_raw", v)
        elif k in ("latitude", "longitude"):
            if not a.get("latitude") and b.get("latitude"):
                a["latitude"], a["longitude"], a["coord_source"] = b["latitude"], b["longitude"], b["coord_source"]
        elif k == "depth_m":
            if a.get(k) in ("", None) and v not in ("", None):
                a[k], a["depth_source"] = v, b["depth_source"]
        elif not a.get(k) and v:
            a[k] = v
    return a


def cmd_lists(args) -> None:
    cache = Path(args.cache_dir) / "lists"
    queue, seen, pages = deque([ROOT_PAGE]), {ROOT_PAGE}, 0
    records: dict[str, dict] = {}
    while queue:
        title = queue.popleft()
        page = cached_parse(title, cache, refresh=args.refresh)
        if not page:
            continue
        pages += 1
        for t in list_links(page["html"]):
            if t not in seen:
                seen.add(t)
                queue.append(t)
        recs = parse_list_page(page["title"], page["html"])
        for r in recs:
            rid = make_id(r)
            r["id"] = rid
            records[rid] = merge(records[rid], r) if rid in records else r
        log.info("[%d pages | %d en file | %d épaves] %s : +%d", pages, len(queue),
                 len(records), page["title"], len(recs))
        if args.max_pages and pages >= args.max_pages:
            log.warning("Arrêt après %d pages (--max-pages)", pages)
            break
    write_csv(Path(args.csv), records.values())
    log.info("CSV écrit : %s (%d épaves, dont %d avec article)", args.csv, len(records),
             sum(1 for r in records.values() if r.get("article")))


def write_csv(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("date") or "9999", r["name"]))
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            if r.get("article") and not r.get("wikipedia_url"):
                r["wikipedia_url"] = WIKI + r["article"].replace(" ", "_")
            w.writerow(r)
    tmp.replace(path)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- #
# Stockage (R2 ou local)
# --------------------------------------------------------------------------- #
class LocalStore:
    def __init__(self, root: str, prefix: str):
        self.root, self.prefix = Path(root), prefix

    def put(self, key: str, data: bytes, content_type: str):
        p = self.root / self.prefix / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


class R2Store:
    def __init__(self, prefix: str):
        import boto3
        from botocore.config import Config
        acc = env_required("R2_ACCOUNT_ID")
        self.bucket = env_required("R2_BUCKET")
        self.prefix = prefix
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT") or f"https://{acc}.r2.cloudflarestorage.com",
            aws_access_key_id=env_required("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=env_required("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
            config=Config(retries={"max_attempts": 8, "mode": "adaptive"}),
        )

    def put(self, key: str, data: bytes, content_type: str):
        self.s3.put_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}", Body=data,
                           ContentType=content_type)


def env_required(k: str) -> str:
    v = os.environ.get(k)
    if not v:
        sys.exit(f"Variable d'environnement manquante : {k}")
    return v


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------- #
# Étape 2 : articles, textes et images
# --------------------------------------------------------------------------- #
SKIP_IMG = re.compile(
    r"(flag[ _]of|ensign|jack[ _]of|naval[ _]ensign|coat[ _]of[ _]arms|commons-logo|wiki|"
    r"icon|symbol|question[ _]book|edit-clear|portal|disambig|padlock|ambox|crystal|"
    r"nuvola|location[ _]map|locator|blank[ _]map|red[ _]pog|map[ _]marker|ship[ _]icon|"
    r"anchor\.svg|logo)", re.I)


def safe_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s[:150] or "image"


def fetch_article(title: str) -> dict | None:
    d = api({
        "action": "query", "titles": title, "redirects": "1",
        "prop": "extracts|coordinates|info|pageprops|pageimages",
        "explaintext": "1", "exsectionformat": "wiki", "inprop": "url",
        "coprimary": "primary", "piprop": "name", "ppprop": "disambiguation",
    })
    pages = d.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    p = pages[0]
    if "disambiguation" in (p.get("pageprops") or {}):
        return None
    html = api({"action": "parse", "pageid": p["pageid"], "prop": "text",
                "disableeditsection": "1"})["parse"]["text"]
    return {"page": p, "html": html}


def fetch_images(pageid: int, max_images: int, width: int) -> list[dict]:
    out, cont = [], {}
    while True:
        d = api({"action": "query", "pageids": pageid, "generator": "images", "gimlimit": "max",
                 "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                 "iiurlwidth": str(width), **cont})
        for p in d.get("query", {}).get("pages", []):
            ii = (p.get("imageinfo") or [{}])[0]
            name = p["title"]
            if not ii or SKIP_IMG.search(name):
                continue
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/gif", "image/webp", "image/tiff"):
                continue
            if ii.get("width", 0) < 200 or ii.get("height", 0) < 150:
                continue
            meta = ii.get("extmetadata") or {}
            out.append({
                "file": name,
                "url": ii.get("thumburl") or ii["url"],
                "original_url": ii["url"],
                "description_url": ii.get("descriptionurl"),
                "mime": ii.get("mime"),
                "width": ii.get("width"), "height": ii.get("height"),
                "license": strip_html(meta.get("LicenseShortName", {}).get("value")),
                "license_url": meta.get("LicenseUrl", {}).get("value"),
                "artist": strip_html(meta.get("Artist", {}).get("value")),
                "credit": strip_html(meta.get("Credit", {}).get("value")),
                "description": strip_html(meta.get("ImageDescription", {}).get("value")),
            })
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return out[:max_images]


def strip_html(s):
    return clean(BeautifulSoup(s, HTML_PARSER).get_text(" ")) if s else None


def process_wreck(rec: dict, store, args) -> dict:
    wid, title = rec["id"], rec["wikipedia_url"].split("/wiki/", 1)[1].replace("_", " ")
    art = fetch_article(unquote(title))
    if not art:
        return {"id": wid, "status": "missing"}
    p = art["page"]
    text = p.get("extract") or ""
    store.put(f"{wid}/article.txt", text.encode("utf-8"), "text/plain; charset=utf-8")
    store.put(f"{wid}/article.html", art["html"].encode("utf-8"), "text/html; charset=utf-8")

    images = [] if args.no_images else fetch_images(p["pageid"], args.max_images, args.image_width)
    saved = []
    used = set()
    for i, im in enumerate(images, 1):
        try:
            r = http_get(im["url"])
        except Exception as e:  # noqa: BLE001
            log.warning("%s : image %s non téléchargée (%s)", wid, im["file"], e)
            continue
        base = safe_name(im["file"].split(":", 1)[-1])
        ext = Path(urlpath(im["url"])).suffix or mimetypes.guess_extension(im["mime"] or "") or ""
        stem = Path(base).stem
        fname = f"{i:02d}_{stem}{ext}"
        while fname in used:
            fname = f"{i:02d}_{stem}_{len(used)}{ext}"
        used.add(fname)
        ctype = r.headers.get("Content-Type", im["mime"])
        store.put(f"{wid}/images/{fname}", r.content, ctype)
        saved.append({**im, "key": f"images/{fname}", "bytes": len(r.content)})

    coords = (p.get("coordinates") or [None])[0]
    depth = extract_depth(text)
    meta = {
        "id": wid, "name": rec["name"], "flag": rec["flag"], "date": rec["date"],
        "wikipedia_title": p["title"], "pageid": p["pageid"], "revid": p.get("lastrevid"),
        "url": p.get("fullurl") or rec["wikipedia_url"],
        "coordinates": {"lat": coords["lat"], "lon": coords["lon"]} if coords else None,
        "depth_m_from_article": depth,
        "lead_image": p.get("pageimage"),
        "images": saved,
        "license_text": "Text: CC BY-SA 4.0, Wikipedia contributors. Images: see each entry.",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    store.put(f"{wid}/metadata.json", json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"),
              "application/json")
    return {"id": wid, "status": "ok", "coords": meta["coordinates"], "depth": depth,
            "images": len(saved), "title": p["title"]}


def urlpath(u: str) -> str:
    return unquote(u.split("?", 1)[0].rsplit("/", 1)[-1])


def cmd_articles(args) -> None:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        sys.exit(f"{csv_path} introuvable : lancez d'abord la commande « lists ».")
    rows = read_csv(csv_path)
    by_id = {r["id"]: r for r in rows}
    state_path = Path(args.cache_dir) / "articles_state.jsonl"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, dict] = {}
    if state_path.exists() and not args.force:
        for line in state_path.read_text("utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                done[d["id"]] = d

    todo = [r for r in rows if r.get("wikipedia_url") and (r["id"] not in done or done[r["id"]]["status"] == "error")]
    if args.limit:
        todo = todo[: args.limit]
    log.info("%d articles à traiter (%d déjà faits)", len(todo), len(done))

    prefix = os.environ.get("R2_PREFIX", "wrecks")
    store = LocalStore(args.local_dir, prefix) if args.storage == "local" else R2Store(prefix)
    lock = threading.Lock()
    with state_path.open("a", encoding="utf-8") as st, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process_wreck, r, store, args): r for r in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                log.error("%s (%s) : %s", r["id"], r["name"], e)
                res = {"id": r["id"], "status": "error", "error": str(e)}
            with lock:
                st.write(json.dumps(res, ensure_ascii=False) + "\n")
                st.flush()
                done[res["id"]] = res
            log.info("[%d/%d] %s %s – %s (%s images)", n, len(todo), res["id"], r["name"],
                     res["status"], res.get("images", 0))

    # Enrichissement du CSV avec les données des articles
    enriched = 0
    for wid, res in done.items():
        row = by_id.get(wid)
        if not row or res.get("status") != "ok":
            continue
        if not row.get("latitude") and res.get("coords"):
            row["latitude"] = f"{res['coords']['lat']:.6f}"
            row["longitude"] = f"{res['coords']['lon']:.6f}"
            row["coord_source"] = "article"
            enriched += 1
        if not row.get("depth_m") and res.get("depth") is not None:
            row["depth_m"] = res["depth"]
            row["depth_source"] = "article"
            enriched += 1
    write_csv(csv_path, rows)
    log.info("CSV mis à jour (%d champs complétés depuis les articles)", enriched)


# --------------------------------------------------------------------------- #
def main(argv=None):
    load_dotenv(HERE / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["lists", "articles", "all"])
    ap.add_argument("--csv", default=str(HERE / "data" / "wrecks.csv"))
    ap.add_argument("--cache-dir", default=str(HERE / "cache"))
    ap.add_argument("--delay", type=float, default=0.2, help="délai min. entre requêtes (s)")
    ap.add_argument("--refresh", action="store_true", help="ignorer le cache des listes")
    ap.add_argument("--max-pages", type=int, default=0, help="limiter le nb de listes (test)")
    ap.add_argument("--limit", type=int, default=0, help="limiter le nb d'articles (test)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--storage", choices=["r2", "local"], default="r2")
    ap.add_argument("--local-dir", default=str(HERE / "export"))
    ap.add_argument("--max-images", type=int, default=20)
    ap.add_argument("--image-width", type=int, default=1600, help="largeur max des images téléchargées")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--force", action="store_true", help="retraiter les articles déjà faits")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    THROTTLE.delay = args.delay
    if args.command in ("lists", "all"):
        cmd_lists(args)
    if args.command in ("articles", "all"):
        cmd_articles(args)


if __name__ == "__main__":
    main()
