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

STATUS: the network egress policy for this session denies CONNECT to all
three hosts (403), so the HTTP layer below has never executed against the
live sites. Everything that does not need the network -- FX conversion,
outlier trimming, confidence rules, judgement, checkpointing, output
schema -- is exercised by test_wine_price_check.py and is verified.

The site-specific parsing is written to the formats documented in the
brief (`162,630 ~ 216,840원`, `183,300원 / 2021-06-18`) and is deliberately
pattern-based rather than class-based, but it is UNVERIFIED against live
markup. Run `--calibrate <wineNumber>` first once the hosts are allowed:
it dumps a decoded page so the region trimming can be checked before a
full 165-row run.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
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
# "183,300원 / 2021-06-18"  (also tolerates 2021.06.18 and 2021/06/18)
_SELLER_RE = re.compile(
    r"([\d,]{4,})\s*원[^\d\n]{0,12}((?:19|20)\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})")
_BARE_PRICE_RE = re.compile(r"([\d,]{4,})\s*원")

# Everything from one of these markers onward is the recommendation /
# review / ad furniture the brief warns about, not the wine's own prices.
_TAIL_MARKERS = (
    "이 와인과 비슷한", "관련 와인", "추천 와인", "함께 본", "이런 와인은 어때",
    "최근 본 와인", "리뷰", "댓글", "인기 와인", "베스트", "광고",
)


def strip_markup(html_text: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_text)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|td|h[1-6]|table)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def main_region(text: str) -> str:
    """Cut the page at the first recommendation/review heading.

    UNVERIFIED against live markup -- see module docstring. If a run comes
    back with prices that do not match the wine, this is the function to
    recalibrate against a `--calibrate` dump.
    """
    cut = len(text)
    for marker in _TAIL_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return text[:cut]


def parse_price_range(text: str) -> tuple[int, int] | None:
    m = _RANGE_RE.search(text)
    if not m:
        return None
    lo = int(m.group(1).replace(",", ""))
    hi = int(m.group(2).replace(",", ""))
    return (lo, hi) if lo <= hi else (hi, lo)


def parse_seller_prices(text: str) -> list[tuple[int, date]]:
    """Extract (price, registration date) pairs from the seller list."""
    out: list[tuple[int, date]] = []
    for m in _SELLER_RE.finditer(text):
        price = int(m.group(1).replace(",", ""))
        try:
            when = date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            continue
        out.append((price, when))
    return out


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
            d.thin_sample, d.excluded, self.비고,
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


def search_wine(keyword: str) -> list[str]:
    """Return candidate wineNumbers for a keyword, best-effort."""
    for encoder in (euc_kr_query, urllib.parse.quote):
        html_text = http_get(SEARCH_URL.format(q=encoder(keyword)))
        numbers = list(dict.fromkeys(_WINENUMBER_RE.findall(html_text)))
        if numbers:
            return numbers
    return []


def fetch_domestic(wine_number: str, today: date) -> tuple[Domestic, str]:
    """Prices for one wineNumber. Prefers the dedicated seller-price page."""
    text = main_region(strip_markup(http_get(PRICELIST_URL.format(n=wine_number))))
    pairs = parse_seller_prices(text)
    note = ""
    if not pairs:
        detail = main_region(strip_markup(http_get(DETAIL_URL.format(n=wine_number))))
        pairs = parse_seller_prices(detail)
        if not pairs:
            rng = parse_price_range(detail)
            if rng:
                # A range with no dated seller rows: keep it, flag the date gap.
                note = "판매처별 날짜 없음 · 가격범위만 확보"
                d = Domestic(low=rng[0], high=rng[1],
                             median=int(round((rng[0] + rng[1]) / 2)),
                             sellers=0, confidence="미상", status="조회성공",
                             thin_sample=True)
                return d, note
    return aggregate_domestic(pairs, today), note


def candidate_keywords(row: dict) -> list[str]:
    """Search-term ladder: English name, then Korean producer + cuvée, then
    producer alone. 큐베 is often Japanese katakana in this dataset and is
    useless as a Korean-site query, so it is only appended when it is not."""
    kws = [row["검색어"].strip()]
    producer_ko = row.get("생산자_한글", "").strip()
    cuvee = row.get("큐베", "").strip()
    if producer_ko:
        if cuvee and not re.search(r"[぀-ヿ]", cuvee):
            kws.append(f"{producer_ko} {cuvee}")
        kws.append(producer_ko)
    producer_en = row.get("생산자_영문", "").strip()
    if producer_en and producer_en not in kws:
        kws.append(producer_en)
    return [k for k in dict.fromkeys(kws) if k]


# --------------------------------------------------------------------------
# Overseas fallbacks (only reached when wadossi has nothing)
# --------------------------------------------------------------------------

def fetch_overseas(keyword: str, state: dict) -> tuple[str, float, str] | None:
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
        return _vivino(keyword)
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


def _vivino(keyword: str) -> tuple[str, float, str] | None:
    url = "https://www.vivino.com/search/wines?q=" + urllib.parse.quote(keyword)
    text = strip_markup(http_get(url, encoding="utf-8"))
    m = re.search(r"([$€£])\s*([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    return _CURRENCY_BY_SYMBOL[m.group(1)], float(m.group(2).replace(",", "")), "Vivino"


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

    try:
        numbers: list[str] = []
        for kw in candidate_keywords(row):
            numbers = search_wine(kw)
            if numbers:
                if kw != row["검색어"]:
                    out.비고 = (out.비고 + " · " if out.비고 else "") + f"대체검색어:{kw}"
                break
        if numbers:
            out.dom, note = fetch_domestic(numbers[0], today)
            if note:
                out.비고 = (out.비고 + " · " if out.비고 else "") + note
        else:
            out.dom.status = "미유통추정"
    except Blocked as exc:
        raise
    except FetchError as exc:
        out.dom.status = "조회실패"
        out.비고 = (out.비고 + " · " if out.비고 else "") + f"국내조회실패:{exc}"

    if out.dom.median is None:
        hit = fetch_overseas(row["검색어"], state)
        if hit:
            cur, amount, source = hit
            out.해외_원통화, out.해외_원가격 = cur, amount
            out.해외가_원화 = int(to_krw(amount, cur))
            out.해외_출처 = source
        if out.dom.status != "조회실패":
            out.dom.status = "미유통추정"
    return out


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
    elif any(r.해외_출처 == "Wine-Searcher" for r in rows):
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

    today = date.today()
    targets = load_targets(args.targets, args.priority)
    if args.limit:
        targets = targets[:args.limit]

    ckpt = args.out_dir / "checkpoint.json"
    done_ids: set[str] = set()
    rows: list[Row] = []
    if ckpt.exists():
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        print(f"resuming: {len(saved['ids'])} already done", file=sys.stderr)
        done_ids = set(saved["ids"])

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
                save(rows, args.out_dir)
                ckpt.write_text(json.dumps(
                    {"ids": sorted(done_ids | {r.id for r in rows})},
                    ensure_ascii=False), encoding="utf-8")
                print(f"  checkpoint at {processed}", file=sys.stderr)
    except Blocked as exc:
        save(rows, args.out_dir)
        print(f"\nBLOCKED: {exc}\n"
              f"egress policy denies this host; not attempting a workaround.\n"
              f"collected {len(rows)} rows before stopping.", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        save(rows, args.out_dir)
        print(f"\ninterrupted after {len(rows)} rows (checkpoint kept)", file=sys.stderr)
        return 130

    save(rows, args.out_dir)
    write_report(rows, state, args.out_dir, today)
    if ckpt.exists():
        ckpt.unlink()
    print(f"done: {len(rows)} rows -> result.csv, report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
