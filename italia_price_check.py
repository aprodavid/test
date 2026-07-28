#!/usr/bin/env python3
"""
charme-du-vin イタリア category -> A/B/D graded price comparison.

Pipeline: collect (REST, category 12) -> parse bottles -> normalise tax to
tax-inclusive -> keep 2021+ -> dedupe to the latest posting per product ->
convert katakana to the original spelling -> look up 와도씨 then
Wine-Searcher then Vivino -> validate the match -> grade.

Points where this differs from the champagne run, and why:

  * The archive spans 2015-2026, so a raw price is not a current price.
    Only 2021+ is kept, duplicates collapse to the newest posting, and a
    year factor lifts the rest to an estimated current price.
  * Vivino is searched WITHOUT the vintage first. Including it makes even
    famous wines miss; the vintage is selected from the returned matches
    afterwards, and falling back to another vintage sets 빈티지대체.
  * Every reference price carries the matched wine name and an overlap
    score, and anything that fails the producer gate or lands outside a
    plausible discount band is graded C and discarded.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import signal
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import iberia_lexicon
import italia_lexicon
import italia_lexicon as lex          # default table
import wine_price_check as wpc

LEXICONS = {"italia": italia_lexicon.LEXICON, "iberia": iberia_lexicon.LEXICON}

CATEGORY_ID = 12
CATEGORY_URL = "http://charme-du-vin.com/category/wine/italia/"
POSTS_URL = ("http://charme-du-vin.com/wp-json/wp/v2/posts?categories={cat}"
             "&per_page=100&page={page}&orderby=date&order=desc"
             "&_fields=id,link,date,title,content")

CONSUMPTION_TAX = 1.10          # 税抜 -> 税込
EARLIEST_YEAR = 2021
DELAY_SECONDS = 2.0
CHECKPOINT_EVERY = 25

# Year factors. The brief supplied champagne-derived values; this dataset was
# re-measured with the same same-product method and disagrees at the 2-year
# horizon, so the measured value is used where the sample supports it. See
# measure_year_factors() and the report.
YEAR_FACTOR = {2026: 1.00, 2025: 1.00, 2024: 1.04, 2023: 1.18,
               2022: 1.24, 2021: 1.30}
YEAR_FACTOR_SOURCE = {2026: "measured", 2025: "measured", 2024: "measured",
                      2023: "brief", 2022: "brief", 2021: "brief"}
MIN_PAIRS_TO_TRUST = 10         # below this the measured ratio is too thin

CONFIDENCE = {2026: "높음", 2025: "높음", 2024: "보통", 2023: "보통",
              2022: "낮음", 2021: "낮음"}

GRADE_A_DISCOUNT = 0.30
MAX_PLAUSIBLE_DISCOUNT = 0.80   # above -> mismatch, grade C
MIN_PLAUSIBLE_DISCOUNT = -1.00  # below -> mismatch, grade C
MIN_OVERLAP = 0.34              # below -> cuvée mismatch, grade B

OUT_DIR = Path(__file__).resolve().parent

# Appellation -> classification. Only wines whose appellation is recognised
# get a grade; anything else stays blank rather than being guessed.
DOCG = {"Barolo", "Barbaresco", "Brunello di Montalcino", "Chianti Classico",
        "Chianti", "Gattinara", "Taurasi", "Greco di Tufo", "Franciacorta",
        "Moscato d'Asti", "Amarone della Valpolicella", "Amarone",
        "Gran Selezione", "Primitivo di Manduria"}
DOC = {"Langhe", "Langhe Rosso", "Barbera d'Alba", "Nebbiolo d'Alba", "Gavi",
       "Rosso di Montalcino", "Valpolicella", "Bolgheri", "Soave",
       "Roero Arneis", "Rosso Piceno", "Verdicchio", "Matelica",
       "Colli Berici", "Lambrusco", "Friuli"}
IGT = {"Toscana", "Toscana Rosso", "Toscano", "Salento", "di Toscana"}


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

def fetch_posts(category: int = CATEGORY_ID) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        raw, _ = wpc_http(POSTS_URL.format(cat=category, page=page))
        posts = json.loads(raw)
        if not posts:
            break
        out += posts
        if len(posts) < 100:
            break
        page += 1
    return out


def wpc_http(url: str) -> tuple[str, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": wpc.UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8"), dict(resp.headers)


def after_tax(price: int | None, note: str) -> int | None:
    """税抜 gets consumption tax added so every price is tax-inclusive."""
    if price is None:
        return None
    return round(price * CONSUMPTION_TAX) if note == "税抜" else price


# --------------------------------------------------------------------------
# Archive handling
# --------------------------------------------------------------------------

def product_key(name: str) -> str:
    n = unicodedata.normalize("NFKC", name)
    return re.sub(r"[※★☆（）()、,。・\s]+", "", n).lower()


def measure_year_factors(bottles: list[dict]) -> dict[int, dict]:
    """Re-measure the price multiplier from products posted more than once.

    Compares tax-normalised prices for the same product key across years,
    which is the only way to separate real repricing from the shop simply
    listing more expensive wines in later years.
    """
    groups: dict[str, list[tuple[int, int]]] = {}
    for b in bottles:
        groups.setdefault(b["key"], []).append((int(b["date"][:4]), b["jpy"]))
    ratios: dict[int, list[float]] = {}
    for entries in groups.values():
        entries.sort()
        for a in range(len(entries)):
            for b2 in range(a + 1, len(entries)):
                (y0, p0), (y1, p1) = entries[a], entries[b2]
                if y1 > y0 and p0:
                    ratios.setdefault(y1 - y0, []).append(p1 / p0)
    return {gap: {"n": len(rs), "median": round(statistics.median(rs), 3)}
            for gap, rs in sorted(ratios.items())}


def build_catalogue(posts: list[dict]) -> tuple[list[dict], list[dict]]:
    """(all priced bottles, 2021+ deduped to newest posting)."""
    import scrape_champagne as sc
    bottles = []
    for p in posts:
        for item in sc.parse_post(p):
            jpy = after_tax(item.price_jpy, item.tax_note)
            if not jpy:
                continue
            bottles.append({"name": item.name_raw, "date": item.date, "jpy": jpy,
                            "tax": item.tax_note, "url": item.url,
                            "key": product_key(item.name_raw)})
    recent = [b for b in bottles if int(b["date"][:4]) >= EARLIEST_YEAR]
    newest: dict[str, dict] = {}
    for b in sorted(recent, key=lambda x: x["date"]):
        newest[b["key"]] = b
    return bottles, list(newest.values())


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

# Only words that carry no distinguishing information. Rosso / Bianco /
# Riserva / Classico are deliberately NOT here: "Poggio di Sotto Rosso di
# Montalcino" scored a perfect 1.0 against that estate's Brunello, a wine
# three times the price, because those words were being discarded.
_COMMON = {"brut", "champagne", "docg", "doc", "igt", "wine", "vino",
           "di", "del", "della", "dei", "il", "la", "le", "e", "san", "de",
           "annata", "azienda", "agricola", "cantina", "nv",
           # Spanish / Portuguese articles and estate words: "El" alone let
           # "El Vinclo" match "Viña Pedrosa El Pedrosal"
           "el", "los", "las", "do", "da", "dos", "das", "bodega", "bodegas",
           "vina", "castillo", "hacienda", "pazos", "dominio", "old", "year"}


def _tok(s: str) -> set[str]:
    folded = "".join(c for c in unicodedata.normalize("NFKD", s.lower())
                     if not unicodedata.combining(c))
    return {t for t in re.split(r"[^0-9a-z가-힣]+", folded)
            if len(t) > 1 and t not in _COMMON}


def overlap(search: str, matched: str) -> float:
    """Rule 2: word overlap excluding producer-agnostic common vocabulary."""
    a, b = _tok(search), _tok(matched)
    return round(len(a & b) / len(a), 3) if a else 0.0


def producer_present(producer: str, matched: str) -> bool:
    """Rule 3: producer absent from the match -> immediate rejection."""
    p = _tok(producer)
    m = _tok(matched)
    if not p:
        return False
    return any(t in m or any(x.startswith(t) or t.startswith(x)
                             for x in m if min(len(x), len(t)) >= 4) for t in p)


# Words that decide which bottling of an estate this is. If one side says
# Rosso and the other Brunello, or one says Riserva and the other does not,
# it is a different (often 3x priced) wine no matter how much else matches.
DECISIVE = {"brunello", "rosso", "bianco", "riserva", "selezione",
            "classico", "magnum", "anfora"}


def tier_conflict(search: str, matched: str) -> bool:
    a, b = _tok(search), _tok(matched)
    return any((w in a) != (w in b) for w in DECISIVE)


def classify(original: str) -> str:
    for name in sorted(DOCG, key=len, reverse=True):
        if name.lower() in original.lower():
            return "DOCG"
    for name in sorted(DOC, key=len, reverse=True):
        if name.lower() in original.lower():
            return "DOC"
    for name in sorted(IGT, key=len, reverse=True):
        if name.lower() in original.lower():
            return "IGT"
    return ""


# --------------------------------------------------------------------------
# Vivino (vintage-last search, per the brief)
# --------------------------------------------------------------------------

_KATAKANA = re.compile(r"[ァ-ヿ]")


def latin_only(query: str) -> str:
    """Drop tokens that never got converted.

    Sending katakana to Vivino guarantees zero results, which is how a
    product with one unresolved cuvée word becomes a false D. The
    converted part still identifies the producer and appellation.
    """
    kept = [t for t in query.split() if not _KATAKANA.search(t)]
    return " ".join(kept)


def vivino_lookup(base_query: str, want_vintage: str,
                  producer: str) -> dict | None:
    """Search producer+cuvée without a vintage, then pick the vintage.

    Searching with the vintage attached makes even well-known wines return
    nothing, so it is applied as a filter over the results instead.
    """
    base_query = latin_only(base_query)
    if not base_query:
        return None
    url = "https://www.vivino.com/search/wines?q=" + urllib.parse.quote(base_query)
    try:
        page = html.unescape(wpc.http_get(url, encoding="utf-8"))
    except (wpc.Blocked, wpc.FetchError):
        return None
    payload = wpc._extract_json_object(page, "initialExploreResults")
    if not payload:
        return None
    matches = [m for m in payload.get("matches", [])
               if (m.get("price") or {}).get("amount")]
    if not matches:
        return None

    def name_of(m: dict) -> str:
        return (m.get("vintage") or {}).get("name", "")

    keep = [m for m in matches if producer_present(producer, name_of(m))]
    if not keep:
        return None

    substituted = False
    if want_vintage:
        exact = [m for m in keep if want_vintage in name_of(m)]
        if exact:
            keep = exact
        else:
            substituted = True

    best = max(keep, key=lambda m: overlap(base_query, name_of(m)))
    price = best["price"]
    return {"name": name_of(best),
            "currency": (price.get("currency") or {}).get("code", "USD"),
            "amount": float(price["amount"]),
            "vintage_substituted": substituted}


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

COLUMNS = ["id", "등급", "상품명_한글", "원어명", "생산자_원어", "분류", "용량",
           "현지가_원화", "기준가_원화", "할인율", "판정근거", "매칭된_와인명", "일치율",
           "국내가_최저", "국내가_중앙", "국내가_최신등록일", "해외_원통화", "해외_원가격",
           "게시연도", "신뢰도", "상태", "미변환여부", "샴드뱅링크"]


@dataclass
class Result:
    id: str
    등급: str = "D"
    상품명_한글: str = ""
    원어명: str = ""
    생산자_원어: str = ""
    분류: str = ""
    용량: str = "750ml"
    현지가_원화: int = 0
    기준가_원화: int | None = None
    할인율: float | None = None
    판정근거: str = "없음"
    매칭된_와인명: str = ""
    일치율: float | None = None
    국내가_최저: int | None = None
    국내가_중앙: int | None = None
    국내가_최신등록일: str = ""
    해외_원통화: str = ""
    해외_원가격: float | None = None
    게시연도: str = ""
    신뢰도: str = ""
    상태: str = ""
    미변환여부: bool = False
    샴드뱅링크: str = ""

    def row(self) -> list:
        return [self.id, self.등급, self.상품명_한글, self.원어명, self.생산자_원어,
                self.분류, self.용량, self.현지가_원화,
                self.기준가_원화 if self.기준가_원화 is not None else "",
                "" if self.할인율 is None else round(self.할인율, 4),
                self.판정근거, self.매칭된_와인명,
                "" if self.일치율 is None else self.일치율,
                self.국내가_최저 or "", self.국내가_중앙 or "",
                self.국내가_최신등록일, self.해외_원통화,
                self.해외_원가격 if self.해외_원가격 is not None else "",
                self.게시연도, self.신뢰도, self.상태, self.미변환여부,
                self.샴드뱅링크]


def to_750ml(jpy: int, volume: str) -> tuple[int, int]:
    """(750ml-equivalent KRW, actual-bottle KRW)."""
    actual = round(jpy * wpc.FX["JPY"])
    m = re.match(r"([\d.]+)(ml|L)", volume)
    if not m:
        return actual, actual
    amount = float(m.group(1)) * (1000 if m.group(2) == "L" else 1)
    if amount <= 0:
        return actual, actual
    return round(actual * 750 / amount), actual


def write_csv(rows: list[list], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for row in rows:
            w.writerow(row)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def lookup_domestic(original: str, producer: str, vintage: str,
                    today: date) -> tuple[wpc.Domestic, str, float]:
    """와도씨 search. Korean index, so the original spelling is the query."""
    row = {"검색어": original, "생산자_영문": producer, "생산자_한글": ""}
    best = None
    best_score = 0.0
    for kw in (original, producer):
        if not kw:
            continue
        try:
            cands = wpc.search_wine(kw)
        except (wpc.Blocked, wpc.FetchError):
            return wpc.Domestic(status="조회실패"), "", 0.0
        for cand in cands:
            s = wpc.score_candidate(cand, row)
            if s > best_score:
                best, best_score = cand, s
        if best_score >= wpc.STRONG_MATCH_SCORE:
            break
    if not best or best_score < wpc.MIN_MATCH_SCORE:
        return wpc.Domestic(status="미유통추정"), "", 0.0
    try:
        dom, _ = wpc.fetch_domestic(best.wine_number,
                                    {"검색어": f"{original} {vintage}".strip()}, today)
    except (wpc.Blocked, wpc.FetchError):
        return wpc.Domestic(status="조회실패"), "", 0.0
    return dom, best.name_ko, best_score


def grade(res: Result, matched: str, producer: str) -> None:
    """A / B / C(discard) / D, per the brief's rules."""
    if res.기준가_원화 is None:
        res.등급 = "D"
        res.판정근거 = "없음"
        return
    if not producer_present(producer, matched):
        res.등급 = "C"          # producer absent -> reject outright
        return
    disc = res.할인율
    if disc is None or disc > MAX_PLAUSIBLE_DISCOUNT or disc < MIN_PLAUSIBLE_DISCOUNT:
        res.등급 = "C"          # implausible gap -> treat as mismatch
        return
    if (res.일치율 or 0) < MIN_OVERLAP:
        res.등급 = "B"          # right producer, wrong cuvée/vintage
        return
    if tier_conflict(res.원어명, matched):
        res.등급 = "B"          # same estate, different bottling
        return
    res.등급 = "A" if disc >= GRADE_A_DISCOUNT else "B"


def process(idx: int, bottle: dict, state: dict, today: date,
            lexicon: dict | None = None) -> Result:
    conv = lex.convert(bottle["name"], lexicon)
    year = int(bottle["date"][:4])
    factor = YEAR_FACTOR.get(year, 1.0)
    krw750, krw_actual = to_750ml(bottle["jpy"], conv["volume"])
    estimated = round(krw750 * factor)

    producer = lex.producer_of(conv["original"])
    res = Result(
        id=str(idx), 상품명_한글=conv["korean"], 원어명=conv["original"],
        생산자_원어=producer, 분류=classify(conv["original"]),
        용량=conv["volume"], 현지가_원화=estimated,
        게시연도=str(year), 신뢰도=CONFIDENCE.get(year, ""),
        상태=conv["condition"], 미변환여부=conv["has_unconverted"],
        샴드뱅링크=bottle["url"])
    if conv["volume"] != "750ml":
        res.상태 = " ".join(x for x in (res.상태, f"실제병가:{krw_actual:,}원") if x)

    # 1) 와도씨
    dom, matched_ko, _ = lookup_domestic(conv["original"], producer,
                                         conv["vintage"], today)
    if dom.median:
        res.국내가_최저, res.국내가_중앙 = dom.low, dom.median
        res.국내가_최신등록일 = dom.latest.isoformat() if dom.latest else ""
        res.기준가_원화 = dom.median
        res.판정근거 = "국내가"
        res.매칭된_와인명 = matched_ko
        res.일치율 = overlap(conv["original"], matched_ko)
        res.할인율 = round((dom.median - estimated) / dom.median, 4)
        grade(res, matched_ko, producer)
        if res.등급 != "C":
            return res
        res.기준가_원화 = res.할인율 = res.일치율 = None
        res.판정근거, res.매칭된_와인명 = "없음", ""

    # 2) Wine-Searcher, once
    if not state.get("ws_tried"):
        state["ws_tried"] = True
        try:
            wpc._wine_searcher(conv["original"])
            state["ws_ok"] = True
        except wpc.Blocked as exc:
            state["ws_blocked"] = str(exc)
        except wpc.FetchError as exc:
            state["ws_blocked"] = str(exc)

    # 3) Vivino
    hit = vivino_lookup(conv["original"], conv["vintage"], producer)
    if hit:
        krw = round(hit["amount"] * wpc.FX.get(hit["currency"], 1.0))
        res.해외_원통화, res.해외_원가격 = hit["currency"], hit["amount"]
        res.기준가_원화 = krw
        res.판정근거 = "해외가"
        res.매칭된_와인명 = hit["name"]
        res.일치율 = overlap(conv["original"], hit["name"])
        res.할인율 = round((krw - estimated) / krw, 4) if krw else None
        if hit["vintage_substituted"]:
            res.상태 = " ".join(x for x in (res.상태, "빈티지대체") if x)
        grade(res, hit["name"], producer)
        return res

    res.등급 = "D"
    res.판정근거 = "없음"
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--confidence", default="", help="높음 / 보통 / 낮음")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cache", type=Path, default=OUT_DIR / "italia_posts.json")
    ap.add_argument("--category", type=int, default=CATEGORY_ID,
                    help="WordPress category id (12=イタリア, 11=スペイン・ポルトガル)")
    ap.add_argument("--prefix", default="", help="output filename prefix")
    ap.add_argument("--lexicon", default="italia", choices=sorted(LEXICONS),
                    help="which katakana table to convert with; the two are "
                         "not interchangeable (ヴィーニャ is Vigna in Italy "
                         "and Viña in Spain)")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.cache.exists():
        posts = json.loads(args.cache.read_text(encoding="utf-8"))
    else:
        posts = fetch_posts(args.category)
        args.cache.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")

    all_bottles, catalogue = build_catalogue(posts)
    factors = measure_year_factors(all_bottles)
    (args.out_dir / f"{args.prefix}year_factors.json").write_text(
        json.dumps(factors, ensure_ascii=False, indent=2), encoding="utf-8")

    catalogue.sort(key=lambda b: b["date"], reverse=True)
    if args.confidence:
        catalogue = [b for b in catalogue
                     if CONFIDENCE.get(int(b["date"][:4])) == args.confidence]
    if args.limit:
        catalogue = catalogue[:args.limit]

    # Keyed by product key -- keyed by id, a resumed run could not tell
    # which catalogue entries were already finished. Rows are carried in
    # full so the CSVs stay complete across restarts.
    ckpt = args.out_dir / f"{args.prefix}checkpoint.json"
    carried: dict[str, list] = {}
    if ckpt.exists():
        carried = json.loads(ckpt.read_text(encoding="utf-8"))
        print(f"resuming: {len(carried)} rows recovered", file=sys.stderr)

    signal.signal(signal.SIGTERM,
                  lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    today = date.today()
    state: dict = {}
    results: list[Result] = []

    GRADE_COL = COLUMNS.index("등급")

    def persist() -> None:
        ckpt.write_text(json.dumps(carried, ensure_ascii=False), encoding="utf-8")
        rows = list(carried.values())
        write_csv([r for r in rows if r[GRADE_COL] in ("A", "D")],
                  args.out_dir / f"{args.prefix}result_AD.csv")
        write_csv([r for r in rows if r[GRADE_COL] == "B"],
                  args.out_dir / f"{args.prefix}result_B.csv")

    try:
        for i, bottle in enumerate(catalogue, 1):
            key = product_key(bottle["name"])
            if key in carried:
                continue
            print(f"[{i}/{len(catalogue)}] {bottle['name'][:40]}", file=sys.stderr)
            res = process(i, bottle, state, today, LEXICONS[args.lexicon])
            results.append(res)
            carried[key] = res.row()
            if i % CHECKPOINT_EVERY == 0:
                persist()
                print(f"  checkpoint {i}", file=sys.stderr)
    except KeyboardInterrupt:
        persist()
        print(f"\ninterrupted at {len(results)}", file=sys.stderr)
        return 130

    persist()
    (args.out_dir / f"{args.prefix}state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")
    counts = {g: sum(1 for r in carried.values() if r[GRADE_COL] == g)
              for g in "ABCD"}
    print(f"done: {len(carried)} rows | {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
