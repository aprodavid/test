#!/usr/bin/env python3
"""
Compare Japanese shop prices (현지가_원화) against Korean domestic and
overseas market prices for the priority-1 rows of 조회대상_750ml.csv.

Sources, in the order the spec requires:
  1. 와도씨 (www.wadossi.com)  -- domestic, EUC-KR encoded
  2. Wine-Searcher             -- overseas average, if wadossi has nothing
  3. Vivino                    -- immediate fallback if Wine-Searcher blocks us
                                  (no bypass attempts; the switch is reported)
  4. none of the above         -> 국내가_상태 = 미유통추정

What the live site actually looks like (checked, not assumed):

  * EUC-KR is required for the *query string* too. Searching with a
    UTF-8 percent-encoded keyword returns zero results; EUC-KR returns
    the real hits.
  * mWinePriceList.php?wineNumber=N is the page to use. It is ~12KB,
    covers exactly one wine, has no recommendation/review tail, and
    carries a `> 주류가격 3 (평균가 : 180,700원)` header giving the listing
    count and the site's own average.
  * mSubDetail.php is NOT used: it is ~327KB, mostly SEO keyword spam,
    and carries the related-wine furniture the brief warns about. The
    price list page makes it unnecessary.
  * Listings are line-separated, not slash-separated. The brief's
    `183,300원 / 2021-06-18` is really two lines, `183,300원` then
    `2021-06-18`, preceded by 지역 / `NV 빈티지` / `판매처 로그인 후 조회가능`.
  * Seller *names* need a login; prices and dates do not. 국내_판매처수 is
    therefore a count of listings, not of named shops.
  * There is no pagination -- a 44-listing wine returns all 44 on one page.
  * One wineNumber mixes vintages, and prices differ enormously across
    them (Dom Pérignon 628: 249,000원 for 2008 next to 650,000원 for
    another year). Where the target row names a vintage, listings are
    filtered to it; see match_vintage.
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
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Fixed configuration (spec: do not call an FX API, record the values used)
# --------------------------------------------------------------------------

FX = {"JPY": 9.0, "USD": 1490.0, "EUR": 1700.0, "GBP": 1950.0, "KRW": 1.0}

DELAY_SECONDS = 2.0
CHECKPOINT_EVERY = 25
TIMEOUT = 30
MAX_RETRIES = 2
STALE_YEARS = 2  # domestic data older than this -> 국내가_신뢰도 = 낮음

OUTLIER_HIGH = 1.5  # drop > 1.5x median
OUTLIER_LOW = 0.6   # drop < 0.6x median
MIN_SELLERS_FOR_MEDIAN = 3
MIN_MATCH_SCORE = 0.6     # below this the search hit is a different wine
STRONG_MATCH_SCORE = 1.0  # at or above this, stop trying further keywords
EXTREME_DISCOUNT = 0.85   # above this a "bargain" is almost certainly a mismatch
EXTREME_MARKUP = 1.50     # below -this the reference is almost certainly wrong

WADOSSI = "https://www.wadossi.com"
DETAIL_URL = WADOSSI + "/mobile/subWine/mSubDetail.php?wineNumber={n}"
PRICELIST_URL = WADOSSI + "/mobile/subWine/mWinePriceList.php?wineNumber={n}"
SEARCH_URL = WADOSSI + "/mobile/subSearch/mSubSearchPrice.php?sKeywords={q}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

OUT_DIR = Path(__file__).resolve().parent


class Blocked(RuntimeError):
    """Egress policy denied the host. Never worked around -- only reported."""


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------

def to_krw(amount: float, currency: str) -> float:
    """JPY is quoted per-yen (9.0 == 100엔:900원)."""
    try:
        return round(amount * FX[currency.upper()])
    except KeyError as exc:
        raise ValueError(f"no FX rate for {currency}") from exc


# --------------------------------------------------------------------------
# Text parsing -- formats taken verbatim from the brief
# --------------------------------------------------------------------------

_RANGE_RE = re.compile(r"([\d,]{4,})\s*원?\s*~\s*([\d,]{4,})\s*원")
# A listing is a price line followed by a date line, optionally with the
# 지역 / 빈티지 / 판매처 lines in between on the price side.
_SELLER_RE = re.compile(
    r"([\d,]{4,})\s*원\s*[\r\n]+\s*((?:19|20)\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# Header: "> 주류가격 3 (평균가 : 180,700원)"
_HEADER_RE = re.compile(r"주류가격\s*(\d+)\s*\(\s*평균가\s*:\s*([\d,]+)\s*원\s*\)")
_VINTAGE_RE = re.compile(r"^(NV|(?:19|20)\d{2})\s*빈티지")
_PRICE_LINE_RE = re.compile(r"^([\d,]{4,})\s*원$")
_DATE_LINE_RE = re.compile(r"^((?:19|20)\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})$")


def strip_markup(html_text: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_text)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|td|h[1-6]|table)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def parse_price_range(text: str) -> tuple[int, int] | None:
    m = _RANGE_RE.search(text)
    if not m:
        return None
    lo = int(m.group(1).replace(",", ""))
    hi = int(m.group(2).replace(",", ""))
    return (lo, hi) if lo <= hi else (hi, lo)


@dataclass
class Listing:
    price: int
    when: date
    vintage: str = ""  # "NV", "2008", or "" when the row omits it


@dataclass
class PriceList:
    declared_count: int = 0
    site_average: int | None = None
    listings: list[Listing] = field(default_factory=list)


def parse_pricelist(text: str) -> PriceList:
    """Parse mWinePriceList.php.

    The page repeats: 지역 / "<vintage> 빈티지" / 판매처 로그인 후 조회가능 /
    "<price>원" / "<date>". Vintage is carried forward from the most recent
    빈티지 line, and the header average is skipped so it cannot be counted
    as a listing.
    """
    out = PriceList()
    lines = text.split("\n")

    start = 0
    for i, line in enumerate(lines):
        m = _HEADER_RE.search(line)
        if m:
            out.declared_count = int(m.group(1))
            out.site_average = int(m.group(2).replace(",", ""))
            start = i + 1
            break

    vintage = ""
    pending: int | None = None
    for line in lines[start:]:
        vm = _VINTAGE_RE.match(line)
        if vm:
            vintage = vm.group(1)
            continue
        pm = _PRICE_LINE_RE.match(line)
        if pm:
            pending = int(pm.group(1).replace(",", ""))
            continue
        dm = _DATE_LINE_RE.match(line)
        if dm and pending is not None:
            try:
                when = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except ValueError:
                pending = None
                continue
            out.listings.append(Listing(pending, when, vintage))
            pending, vintage = None, ""
    return out


def parse_seller_prices(text: str) -> list[tuple[int, date]]:
    """(price, date) pairs -- kept as the format-level primitive."""
    out: list[tuple[int, date]] = []
    for m in _SELLER_RE.finditer(text):
        try:
            when = date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            continue
        out.append((int(m.group(1).replace(",", "")), when))
    return out


_TARGET_VINTAGE_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def target_vintage(keyword: str) -> str:
    m = _TARGET_VINTAGE_RE.search(keyword)
    return m.group(1) if m else ""


def match_vintage(listings: list[Listing], want: str) -> tuple[list[Listing], str]:
    """Narrow to the requested vintage when the page actually distinguishes it.

    A wineNumber pools every vintage, and the spread between them is far
    wider than the outlier band, so comparing a 2008 shelf price against a
    pool containing other years would be meaningless. Falls back to the
    whole set (with a note) when nothing matches.
    """
    if not want:
        return listings, ""
    hit = [l for l in listings if l.vintage == want]
    if hit:
        return hit, f"빈티지 {want} 일치 {len(hit)}건"
    return listings, f"빈티지 {want} 미발견 · 전체 빈티지로 비교"


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

@dataclass
class Domestic:
    low: int | None = None
    median: int | None = None
    high: int | None = None
    sellers: int = 0
    latest: date | None = None
    confidence: str = ""       # 최신 / 낮음
    status: str = ""           # 조회성공 / 미유통추정
    excluded: int = 0
    thin_sample: bool = False


def aggregate_domestic(pairs: list[tuple[int, date]], today: date) -> Domestic:
    """Median representative + outlier trim, per the spec's thresholds.

    The band is anchored on the median of the *raw* set, then min/median/max
    are recomputed from the survivors, so one absurd listing cannot drag the
    reported figures.
    """
    d = Domestic()
    if not pairs:
        d.status = "미유통추정"
        return d

    d.status = "조회성공"
    prices = [p for p, _ in pairs]
    d.latest = max(when for _, when in pairs)
    age_days = (today - d.latest).days
    d.confidence = "낮음" if age_days >= STALE_YEARS * 365 else "최신"

    if len(prices) >= MIN_SELLERS_FOR_MEDIAN:
        anchor = statistics.median(prices)
        kept = [p for p in prices if OUTLIER_LOW * anchor <= p <= OUTLIER_HIGH * anchor]
        d.excluded = len(prices) - len(kept)
        if not kept:  # degenerate; keep the raw set rather than emit nothing
            kept, d.excluded = prices, 0
    else:
        kept = prices
        d.thin_sample = True

    d.sellers = len(kept)
    d.low = min(kept)
    d.high = max(kept)
    d.median = int(round(statistics.median(kept)))
    return d


# --------------------------------------------------------------------------
# Result rows
# --------------------------------------------------------------------------

RESULT_COLUMNS = [
    "id", "검색어", "분류", "현지가_원화",
    "국내가_최저", "국내가_중앙", "국내가_최고", "국내_판매처수",
    "국내가_최신등록일", "국내가_신뢰도", "국내가_상태",
    "해외_원통화", "해외_원가격", "해외가_원화", "해외_출처",
    "판정근거", "기준가_원화", "할인율", "표본부족", "제외건수", "비고",
]


@dataclass
class Row:
    id: str
    검색어: str
    분류: str
    현지가_원화: float
    dom: Domestic = field(default_factory=Domestic)
    해외_원통화: str = ""
    해외_원가격: float | None = None
    해외가_원화: int | None = None
    해외_출처: str = ""
    비고: str = ""

    def judge(self) -> tuple[str, int | None, float | None]:
        """(판정근거, 기준가_원화, 할인율).

        할인율 is positive when the Japanese shelf price is below the
        reference: (기준가 - 현지가) / 기준가.
        """
        if self.dom.median is not None:
            basis, ref = "국내가", self.dom.median
        elif self.해외가_원화 is not None:
            basis, ref = "해외평균가", self.해외가_원화
        else:
            return "판정불가", None, None
        if not ref:
            return basis, ref, None
        return basis, ref, round((ref - self.현지가_원화) / ref, 4)

    def implausible(self) -> str:
        """Flag discounts too extreme to be a real price gap.

        Name matching cannot resolve every case -- abbreviations (Bollinger
        "VZ") and shared surnames (Selosse-Pajon vs Jacques Selosse) can
        land on a far pricier bottle from a plausible-looking producer. The
        arithmetic is still correct; the reference is not. These rows are
        marked rather than dropped so they can be checked by hand.
        """
        _, _, disc = self.judge()
        if disc is None:
            return ""
        if disc > EXTREME_DISCOUNT:
            return "⚠비교대상 확인필요(할인율 과대)"
        if disc < -EXTREME_MARKUP:
            return "⚠비교대상 확인필요(현지가 과대)"
        return ""

    def to_csv(self) -> list:
        basis, ref, disc = self.judge()
        d = self.dom
        return [
            self.id, self.검색어, self.분류, int(self.현지가_원화),
            d.low or "", d.median or "", d.high or "", d.sellers or "",
            d.latest.isoformat() if d.latest else "", d.confidence, d.status,
            self.해외_원통화, self.해외_원가격 if self.해외_원가격 is not None else "",
            self.해외가_원화 or "", self.해외_출처,
            basis, ref or "", "" if disc is None else disc,
            d.thin_sample, d.excluded,
            " · ".join(x for x in (self.implausible(), self.비고) if x),
        ]


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

_last_request = 0.0


def http_get(url: str, encoding: str = "euc-kr") -> str:
    """GET with the mandated 2s spacing. EUC-KR by default -- wadossi is
    EUC-KR and decoding it as UTF-8 mojibakes every Korean string."""
    global _last_request
    gap = time.monotonic() - _last_request
    if gap < DELAY_SECONDS:
        time.sleep(DELAY_SECONDS - gap)

    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept-Language": "ko-KR,ko;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
            _last_request = time.monotonic()
            return raw.decode(encoding, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 407):
                raise Blocked(f"{urllib.parse.urlsplit(url).netloc}: HTTP {exc.code}") from exc
            last = exc
        except urllib.error.URLError as exc:
            if "CONNECT tunnel failed" in str(exc) or "403" in str(exc):
                raise Blocked(f"{urllib.parse.urlsplit(url).netloc}: {exc}") from exc
            last = exc
        except Exception as exc:
            last = exc
        if attempt < MAX_RETRIES:
            time.sleep(DELAY_SECONDS * (attempt + 1))
    _last_request = time.monotonic()
    raise FetchError(f"{url}: {last}")


def euc_kr_query(keyword: str) -> str:
    """EUC-KR percent-encoding for the search term.

    The brief flags this as needing confirmation; search_wine() tries this
    form first and retries with UTF-8 if it yields nothing.
    """
    return urllib.parse.quote(keyword.encode("euc-kr", errors="replace"))


# --------------------------------------------------------------------------
# 와도씨
# --------------------------------------------------------------------------

_WINENUMBER_RE = re.compile(r"wineNumber=(\d+)")
_KO_NAME_RE = re.compile(r'Fsize16"[^>]*>(.*?)</span>', re.S)
_EN_NAME_RE = re.compile(r'Fsize13"[^>]*>(.*?)</span>', re.S)


@dataclass
class Candidate:
    wine_number: str
    name_ko: str
    name_en: str
    is_sparkling: bool = True  # Vivino rows are pre-filtered; wadossi sets it


def parse_search(html_text: str) -> list[Candidate]:
    """One Candidate per result card in mSubSearchPrice.php.

    Each card links to mWinePriceList.php?wineNumber=N and carries the
    Korean name in .Fsize16 and the (truncated) English name in .Fsize13.
    """
    out: list[Candidate] = []
    seen: set[str] = set()
    for block in html_text.split('id="myContentsSmall"')[1:]:
        m = _WINENUMBER_RE.search(block)
        if not m or m.group(1) in seen:
            continue
        ko = _KO_NAME_RE.search(block)
        en = _EN_NAME_RE.search(block)
        seen.add(m.group(1))
        out.append(Candidate(
            m.group(1),
            re.sub(r"<[^>]+>", "", ko.group(1)).strip() if ko else "",
            re.sub(r"<[^>]+>", "", en.group(1)).strip() if en else "",
            # cards mark the wine type with an icon and the region in a
            # breadcrumb; either is enough to tell sparkling from still
            "iconSparkling" in block or "상파뉴" in block))
    return out


# Two different jobs, so two different lists.
#
# _NOISE carries no information anywhere and is dropped from every
# comparison: articles, the word champagne itself, bottle sizes.
_NOISE = {
    "champagne", "nv", "ml", "750ml", "magnum", "de", "du", "la", "le", "les",
    "and", "the", "of", "샴페인", "샹파뉴", "빈티지",
}

# _PRODUCER_STOP is style vocabulary. It cannot satisfy the producer gate --
# that is what let "Justin Extra Brut 2009" score against "Schramsberg Extra
# Brut 2009" -- but it is deliberately still scored for coverage, because
# blanc / rosé / millésime are exactly what separate one cuvée from another
# within a producer. Stripping them from scoring made Billecart-Salmon Blanc
# de Blancs match Billecart-Salmon Demi-Sec.
_PRODUCER_STOP = {
    "brut", "extra", "nature", "cuvee", "grand", "cru", "premier",
    "blanc", "blancs", "noir", "noirs", "rose", "millesime",
    "vieilles", "vignes", "reserve", "tradition", "vintage",
    "dosage", "zero", "sec", "demi",
    "브뤼", "브륏", "엑스트라", "뀌베", "퀴베", "그랑", "크뤼", "프리미어", "블랑",
    "누아", "로제", "밀레짐", "레제르브", "트라디씨옹", "트라디시옹", "나뛰르", "나튀르",
    "드미", "섹",
}

MIN_PREFIX_MATCH = 4  # shorter than this, a prefix relation means nothing


def _fold(s: str) -> str:
    """Drop accents so French names tokenize as words.

    Without this the token split breaks on the accent itself: Réserve ->
    "r" + "serve" and Cuvée -> "cuv" + "e", which slips both past the
    generic-word list and matches them against unrelated wines.
    """
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower())
                   if not unicodedata.combining(c))


def _tokens(s: str, drop_style: bool = False) -> set[str]:
    out = {t for t in re.split(r"[^0-9A-Za-z가-힣]+", _fold(s)) if len(t) > 1}
    out -= _NOISE
    return out - _PRODUCER_STOP if drop_style else out


def _matches_any(token: str, have: set[str]) -> bool:
    """Exact match, or a prefix relation between two reasonably long tokens.

    Search cards truncate the English name ("Egly Ouriet, Brut Ro"), so a
    prefix has to count -- but only above MIN_PREFIX_MATCH. Without that
    floor "delong" matched "de" in "Jolie-Laide Melon de Bourgogne" and
    scored a perfect 1.0 against an unrelated wine.
    """
    for h in have:
        if h == token:
            return True
        if min(len(h), len(token)) >= MIN_PREFIX_MATCH and (
                h.startswith(token) or token.startswith(h)):
            return True
    return False


def score_candidate(cand: Candidate, row: dict) -> float:
    """Producer gate, then coverage of the target's remaining tokens.

    The gate decides whether this is even the right winery; the coverage
    term decides whether it is the right bottle from that winery.
    """
    have = _tokens(cand.name_ko + " " + cand.name_en)
    if not have:
        return 0.0

    # Every target here is champagne, so a still wine from a same-named
    # producer is never the right answer (Justin the Champagne grower vs
    # Justin the Paso Robles cabernet house).
    if not cand.is_sparkling:
        return 0.0

    producer = _tokens(" ".join((row.get("생산자_영문", ""), row.get("생산자_한글", ""))),
                       drop_style=True)
    if not producer:
        # Nothing identifying to match on -- style words alone would match
        # any wine in the index. Every row in this dataset has a producer,
        # so this only guards degenerate input.
        return 0.0
    if not any(_matches_any(p, have) for p in producer):
        return 0.0  # different producer -- not this wine, whatever else lines up

    want = _tokens(" ".join((row.get("검색어", ""), row.get("생산자_영문", ""),
                             row.get("생산자_한글", ""))))
    if not want:
        return 0.0
    score = sum(1 for w in want if _matches_any(w, have)) / len(want)
    vint = target_vintage(row.get("검색어", ""))
    if vint:
        score += 0.5 if vint in cand.name_ko + cand.name_en else -0.25
    return max(score, 0.0)


def search_wine(keyword: str) -> list[Candidate]:
    """Candidates for a keyword. EUC-KR query encoding is mandatory here --
    a UTF-8 encoded keyword returns zero rows on this site."""
    for encoder in (euc_kr_query, urllib.parse.quote):
        cands = parse_search(http_get(SEARCH_URL.format(q=encoder(keyword))))
        if cands:
            return cands
    return []


def fetch_domestic(wine_number: str, row: dict, today: date) -> tuple[Domestic, str]:
    """Domestic prices for one wineNumber, narrowed to the target vintage."""
    text = strip_markup(http_get(PRICELIST_URL.format(n=wine_number)))
    pl = parse_pricelist(text)
    if not pl.listings:
        return Domestic(status="미유통추정"), ""
    listings, note = match_vintage(pl.listings, target_vintage(row.get("검색어", "")))
    return aggregate_domestic([(l.price, l.when) for l in listings], today), note


def candidate_keywords(row: dict) -> list[str]:
    """Search-term ladder, Korean first.

    wadossi's index is Korean: "Piper-Heidsieck" and "Egly-Ouriet" both
    return zero rows while 파이퍼 하이직 and 에글리 우리에 return five and four.
    The English 검색어 is kept as a later fallback because it does work for
    some producers (Bollinger, Salon). 큐베 is Japanese katakana on 70 of
    the 165 rows, which is useless as a Korean-site query, so it is only
    combined in when it is not.
    """
    kws: list[str] = []
    producer_ko = row.get("생산자_한글", "").strip()
    cuvee = row.get("큐베", "").strip()
    if producer_ko:
        if cuvee and not re.search(r"[぀-ヿ]", cuvee):
            kws.append(f"{producer_ko} {cuvee}")
        kws.append(producer_ko)
    kws.append(row["검색어"].strip())
    producer_en = row.get("생산자_영문", "").strip()
    if producer_en:
        kws.append(producer_en)
    return [k for k in dict.fromkeys(kws) if k]


# --------------------------------------------------------------------------
# Overseas fallbacks (only reached when wadossi has nothing)
# --------------------------------------------------------------------------

def fetch_overseas(keyword: str, state: dict, row: dict | None = None) -> tuple[str, float, str] | None:
    """Wine-Searcher first; on any block switch to Vivino permanently.

    No bypass is attempted -- per the brief, a block is recorded and the
    run moves on.
    """
    if not state.get("ws_blocked"):
        try:
            return _wine_searcher(keyword)
        except Blocked as exc:
            state["ws_blocked"] = True
            state["ws_block_detail"] = str(exc)
        except FetchError:
            pass
    try:
        return _vivino(keyword, row)
    except (Blocked, FetchError) as exc:
        state.setdefault("vivino_block_detail", str(exc))
        return None


_WS_PRICE_RE = re.compile(r"(?:average|평균)[^\d]{0,40}([$€£¥])\s*([\d,]+(?:\.\d+)?)", re.I)
_CURRENCY_BY_SYMBOL = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}


def _wine_searcher(keyword: str) -> tuple[str, float, str] | None:
    url = ("https://www.wine-searcher.com/find/"
           + urllib.parse.quote(keyword.lower().replace(" ", "-")))
    text = strip_markup(http_get(url, encoding="utf-8"))
    m = _WS_PRICE_RE.search(text)
    if not m:
        return None
    return _CURRENCY_BY_SYMBOL[m.group(1)], float(m.group(2).replace(",", "")), "Wine-Searcher"


def _extract_json_object(text: str, key: str) -> dict | None:
    """Pull one embedded JSON object out of a page by key, brace-balanced."""
    i = text.find(f'"{key}"')
    if i == -1:
        return None
    start = text.find("{", i)
    if start == -1:
        return None
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _vivino(keyword: str, row: dict | None = None) -> tuple[str, float, str] | None:
    """Read Vivino's embedded search payload.

    Scraping a currency token out of the rendered text does not work: the
    first `$` on the page belongs to the price-range filter widget
    ("Wines, above $10.0"), which produced nonsense reference prices. The
    page ships the real results as JSON under initialExploreResults, with
    a name and a price per match, so the best name match is used instead
    of whichever number appears first.
    """
    url = "https://www.vivino.com/search/wines?q=" + urllib.parse.quote(keyword)
    page = html.unescape(http_get(url, encoding="utf-8"))
    payload = _extract_json_object(page, "initialExploreResults")
    if not payload:
        return None
    matches = [m for m in payload.get("matches", []) if (m.get("price") or {}).get("amount")]
    if not matches:
        return None

    probe = row or {"검색어": keyword}

    def scored(m: dict) -> float:
        return score_candidate(
            Candidate("", "", (m.get("vintage") or {}).get("name", "")), probe)

    best = max(matches, key=scored)
    if scored(best) < MIN_MATCH_SCORE:
        # Vivino answers every query with something; an obscure grower can
        # land on a famous near-namesake (Selosse-Pajon -> Jacques Selosse
        # at $1,140). Rather than emit that as a reference price, report no
        # overseas figure.
        return None
    price = best["price"]
    currency = (price.get("currency") or {}).get("code", "USD")
    return (currency, float(price["amount"]),
            f"Vivino:{(best.get('vintage') or {}).get('name', '')[:60]}")


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def load_targets(path: Path, priority: str) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["우선순위"] == priority]


def process(row: dict, state: dict, today: date) -> Row:
    out = Row(id=row["id"], 검색어=row["검색어"], 분류=row["분류"],
              현지가_원화=float(row["현지가_원화"]))
    if row.get("식별확실") == "False":
        out.비고 = "식별확실=False"

    def note(msg: str) -> None:
        out.비고 = (out.비고 + " · " if out.비고 else "") + msg

    try:
        # Score across every keyword's hits rather than taking the first
        # keyword that returns anything: a broad producer term can return
        # the wrong wine ("살롱" surfaces 샤또 샬롱) while a later, narrower
        # term finds the right one.
        best: Candidate | None = None
        best_score = 0.0
        best_kw = ""
        for kw in candidate_keywords(row):
            for cand in search_wine(kw):
                s = score_candidate(cand, row)
                if s > best_score:
                    best, best_score, best_kw = cand, s, kw
            if best_score >= STRONG_MATCH_SCORE:
                break  # unambiguous; no need to spend more requests
        if best_score < MIN_MATCH_SCORE:
            best = None
        if best:
            if best_kw != row["검색어"]:
                note(f"대체검색어:{best_kw}")
        if best:
            note(f"매칭:{best.name_ko}")
            out.dom, vnote = fetch_domestic(best.wine_number, row, today)
            if vnote:
                note(vnote)
        else:
            out.dom.status = "미유통추정"
    except Blocked as exc:
        raise
    except FetchError as exc:
        out.dom.status = "조회실패"
        note(f"국내조회실패:{exc}")

    if out.dom.median is None:
        hit = fetch_overseas(row["검색어"], state, row)
        if hit:
            cur, amount, source = hit
            out.해외_원통화, out.해외_원가격 = cur, amount
            out.해외가_원화 = int(to_krw(amount, cur))
            out.해외_출처 = source
        if out.dom.status != "조회실패":
            out.dom.status = "미유통추정"
    return out


def _int_or_none(s: str) -> int | None:
    return int(s) if s not in ("", None) else None


def load_completed(out_dir: Path) -> list[Row]:
    """Rebuild rows written by an earlier, interrupted run.

    The checkpoint stores only ids, so without reading the previous
    result.csv back a resumed run would overwrite it with just the rows
    collected after the restart -- and the report would cover only those.
    """
    path = out_dir / "result.csv"
    if not path.exists():
        return []
    out: list[Row] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != RESULT_COLUMNS:
            return []
        for rec in reader:
            # the ⚠ flag is derived at write time; strip it so it is not
            # doubled on the next save
            memo = " · ".join(p for p in rec["비고"].split(" · ")
                              if not p.startswith("⚠"))
            r = Row(id=rec["id"], 검색어=rec["검색어"], 분류=rec["분류"],
                    현지가_원화=float(rec["현지가_원화"] or 0), 비고=memo)
            latest = rec["국내가_최신등록일"]
            r.dom = Domestic(
                low=_int_or_none(rec["국내가_최저"]),
                median=_int_or_none(rec["국내가_중앙"]),
                high=_int_or_none(rec["국내가_최고"]),
                sellers=_int_or_none(rec["국내_판매처수"]) or 0,
                latest=date.fromisoformat(latest) if latest else None,
                confidence=rec["국내가_신뢰도"], status=rec["국내가_상태"],
                excluded=_int_or_none(rec["제외건수"]) or 0,
                thin_sample=rec["표본부족"] == "True")
            r.해외_원통화 = rec["해외_원통화"]
            r.해외_원가격 = float(rec["해외_원가격"]) if rec["해외_원가격"] else None
            r.해외가_원화 = _int_or_none(rec["해외가_원화"])
            r.해외_출처 = rec["해외_출처"]
            out.append(r)
    return out


def flush(rows: list[Row], out_dir: Path, ckpt: Path) -> None:
    """Persist rows and the resume marker together, so they cannot disagree."""
    save(rows, out_dir)
    ckpt.write_text(json.dumps({"ids": sorted({r.id for r in rows})},
                               ensure_ascii=False), encoding="utf-8")


def save(rows: list[Row], out_dir: Path) -> None:
    with (out_dir / "result.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(RESULT_COLUMNS)
        for r in rows:
            w.writerow(r.to_csv())


def write_report(rows: list[Row], state: dict, out_dir: Path, today: date) -> None:
    done = len(rows)
    dom_ok = [r for r in rows if r.dom.median is not None]
    abroad = [r for r in rows if r.dom.median is None and r.해외가_원화 is not None]
    none_ = [r for r in rows if r.dom.median is None and r.해외가_원화 is None]
    stale = [r for r in dom_ok if r.dom.confidence == "낮음"]
    fresh = [r for r in dom_ok if r.dom.confidence == "최신"]

    L = [
        "# 조회 결과 리포트",
        "",
        f"- 대상: 우선순위 1, {done}건",
        f"- 실행일: {today.isoformat()}",
        "- 적용 환율 (하드코딩): "
        f"JPY {FX['JPY']} / USD {FX['USD']:,.0f} / EUR {FX['EUR']:,.0f} / GBP {FX['GBP']:,.0f}",
        f"- 이상치 기준: 중앙값의 {OUTLIER_HIGH}배 초과 또는 {OUTLIER_LOW}배 미만 제외 "
        f"(판매처 {MIN_SELLERS_FOR_MEDIAN}곳 이상일 때만 적용)",
        "- 할인율 = (기준가_원화 − 현지가_원화) / 기준가_원화. 양수면 일본 현지가가 더 쌈",
        "",
        "## 소스별 분포",
        "",
        "| 구분 | 건수 |",
        "|---|---:|",
        f"| 국내가 확보 (와도씨) | {len(dom_ok)} |",
        f"| 해외가로 판정 | {len(abroad)} |",
        f"| 미유통추정·판정불가 | {len(none_)} |",
        "",
        "## Wine-Searcher 접근 가능 여부",
        "",
    ]
    if state.get("ws_blocked"):
        L.append(f"- **차단됨** — {state.get('ws_block_detail', '')}")
        L.append("- 우회 시도 없이 Vivino로 전환함")
    elif any(r.해외_출처.startswith("Wine-Searcher") for r in rows):
        L.append("- 정상 접근")
    else:
        L.append("- 호출 사례 없음 (국내가로 전부 판정됨)")
    if state.get("vivino_block_detail"):
        L.append(f"- Vivino 역시 실패: {state['vivino_block_detail']}")

    L += [
        "",
        "## 국내가 신뢰도 분포",
        "",
        "| 신뢰도 | 건수 |",
        "|---|---:|",
        f"| 최신 ({STALE_YEARS}년 이내) | {len(fresh)} |",
        f"| 낮음 ({STALE_YEARS}년 이상 경과) | {len(stale)} |",
        "",
        "## 비교대상 확인필요",
        "",
        f"자동 매칭이 다른 큐베·다른 생산자를 잡았을 가능성이 높은 건 "
        f"(할인율 {EXTREME_DISCOUNT:.0%} 초과 또는 현지가가 기준가의 "
        f"{1 + EXTREME_MARKUP:.1f}배 초과). 계산은 정상이고 비교대상만 의심됨:",
        "",
        "| id | 검색어 | 기준가 | 할인율 | 근거 |",
        "|---:|---|---:|---:|---|",
    ]
    flagged = [(r, r.judge()) for r in rows if r.implausible()]
    for r, (basis, ref, disc) in flagged:
        L.append(f"| {r.id} | {r.검색어} | {ref:,} | {disc:.1%} | "
                 f"{r.해외_출처 or basis} |")
    if not flagged:
        L.append("| - | 없음 | | | |")
    L += [
        "",
        "## 할인율 상위 30건",
        "",
        "| # | id | 검색어 | 현지가 | 기준가 | 할인율 | 판정근거 | 신뢰도 |",
        "|---:|---:|---|---:|---:|---:|---|---|",
    ]
    ranked = [(r, r.judge()) for r in rows]
    ranked = [(r, j) for r, j in ranked if j[2] is not None]
    ranked.sort(key=lambda t: t[1][2], reverse=True)
    for i, (r, (basis, ref, disc)) in enumerate(ranked[:30], 1):
        L.append(f"| {i} | {r.id} | {r.검색어} | {int(r.현지가_원화):,} | {ref:,} | "
                 f"{disc:.1%} | {basis} | {r.dom.confidence or '-'} |")
    L.append("")
    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("targets", type=Path, nargs="?",
                    default=OUT_DIR / "조회대상_750ml.csv")
    ap.add_argument("--priority", default="1")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--calibrate", metavar="WINENUMBER",
                    help="dump one decoded wadossi page and exit, so the "
                         "region trimming can be checked before a full run")
    args = ap.parse_args()

    if args.calibrate:
        for label, url in (("detail", DETAIL_URL), ("pricelist", PRICELIST_URL)):
            page = http_get(url.format(n=args.calibrate))
            dst = args.out_dir / f"calibrate_{label}_{args.calibrate}.txt"
            dst.write_text(strip_markup(page), encoding="utf-8")
            print(f"wrote {dst}")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    targets = load_targets(args.targets, args.priority)
    if args.limit:
        targets = targets[:args.limit]

    ckpt = args.out_dir / "checkpoint.json"
    done_ids: set[str] = set()
    rows: list[Row] = []
    if ckpt.exists():
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        done_ids = set(saved["ids"])
        rows = load_completed(args.out_dir)
        print(f"resuming: {len(done_ids)} done, {len(rows)} rows recovered",
              file=sys.stderr)

    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    state: dict = {}
    processed = 0
    try:
        for row in targets:
            if row["id"] in done_ids:
                continue
            print(f"[{row['id']}] {row['검색어']}", file=sys.stderr)
            rows.append(process(row, state, today))
            processed += 1
            if processed % CHECKPOINT_EVERY == 0:
                flush(rows, args.out_dir, ckpt)
                print(f"  checkpoint at {processed}", file=sys.stderr)
    except Blocked as exc:
        flush(rows, args.out_dir, ckpt)
        print(f"\nBLOCKED: {exc}\n"
              f"egress policy denies this host; not attempting a workaround.\n"
              f"collected {len(rows)} rows before stopping.", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        flush(rows, args.out_dir, ckpt)
        print(f"\ninterrupted at {len(rows)} rows; rerun to resume", file=sys.stderr)
        return 130

    save(rows, args.out_dir)
    write_report(rows, state, args.out_dir, today)
    if ckpt.exists():
        ckpt.unlink()
    print(f"done: {len(rows)} rows -> result.csv, report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
