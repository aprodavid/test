#!/usr/bin/env python3
"""
charme-du-vin.com  シャンパーニュ (champagne) category scraper.

Findings that drove the design (verified against the live site, not assumed):

  * The site is NOT WooCommerce. `/wp-json/` exposes only
    oembed/1.0, akismet/v1, contact-form-7/v1, wp/v2 -- there is no
    `wc/store/v1` and no `product` post type. `/wp-json/wp/v2/product`
    and `/wp-json/wc/store/v1/products` both return 404 rest_no_route.
  * Products are ordinary WordPress posts in category id 17
    (`<body class="archive category category-champagne category-17">`),
    so `/wp-json/wp/v2/posts?categories=17` is the accurate source and is
    used here in preference to HTML parsing.
  * The category archive markup is a custom theme (bootstrap4_blank), not
    WooCommerce classes: `div.posts > div.post > a[href]`, title in
    `div.post_title`, image in `div.eyecatch > img`, pager in
    `div.wp-pagenavi` with `span.pages` == "1 / 102".
  * The archive shows NO price and TRUNCATES long titles with an ellipsis.
    Prices live only in the post body (`div.content` on the single page /
    `content.rendered` in the REST response), formatted as full-width
    yen amounts, e.g. `￥１１,５５０（税込）`.
  * One post can list several bottles: the body is a sequence of
    (name line, price line) pairs and the post title joins them with "/".
    Those are emitted as separate rows sharing one URL.
  * The site serves plain HTTP only; its TLS certificate is a shared
    hosting cert (CN=*.gmoserver.jp) that does not match the domain.
  * robots.txt disallows only /wp/wp-admin/ -- the category archive, the
    posts and the REST API are all allowed.

Outputs champagne.md and champagne.csv (UTF-8 with BOM) next to this file.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

BASE = "http://charme-du-vin.com"
CATEGORY_ID = 17
CATEGORY_PATH = "/category/wine/france/champagne/"
PER_PAGE = 100
DELAY_SECONDS = 2.0
MAX_RETRIES = 2  # retries after the first attempt
TIMEOUT = 45
USER_AGENT = "Mozilla/5.0 (compatible; champagne-catalog-export/1.0)"

OUT_DIR = Path(__file__).resolve().parent


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

_first_request = True


def fetch(url: str) -> tuple[bytes, dict[str, str]]:
    """GET with a fixed inter-request delay and MAX_RETRIES retries."""
    global _first_request
    if _first_request:
        _first_request = False
    else:
        time.sleep(DELAY_SECONDS)

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(DELAY_SECONDS * attempt)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read(), {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            # 4xx are deterministic; retrying them is pointless.
            if 400 <= exc.code < 500:
                raise FetchError(f"{url} -> HTTP {exc.code}") from exc
            last_err = exc
        except Exception as exc:  # timeouts, connection resets, DNS
            last_err = exc
        print(f"  ! attempt {attempt + 1}/{MAX_RETRIES + 1} failed: {last_err}",
              file=sys.stderr)
    raise FetchError(f"{url} failed after {MAX_RETRIES + 1} attempts: {last_err}")


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

# Full-width digits / separators -> ASCII, for price parsing only.
_DIGIT_MAP = str.maketrans({
    **{chr(0xFF10 + i): str(i) for i in range(10)},  # ０-９
    "，": ",", "、": ",", "．": ".", "　": " ",
    "（": "(", "）": ")", "￥": "¥",
})

# Yen amount: ¥12,345 / 12,345円 / ¥ 12345.
# The thousands separator is inconsistent on this site -- "，" and "、" are the
# common ones but "．" also occurs (e.g. ￥９．３５０), so both are accepted and
# validated as digit groups afterwards.
_PRICE_RE = re.compile(r"(?:¥\s*([\d.,]{3,})|([\d.,]{3,})\s*円)")
_GROUPED_RE = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")

# Anything that reads as "no price" rather than a number.
_STATUS_PATTERNS: list[tuple[str, str]] = [
    (r"売り?切れ|完売|品切れ|在庫[な無]し|SOLD\s*OUT", "품절"),
    (r"(価格|値段)[^。\n]{0,10}(お問い合わせ|お問合せ|問い合わせ)|応談|要問", "가격문의"),
    (r"お問い?合わ?せ(ください)?", "가격문의"),
    (r"入荷(待ち|予定)|予約", "입하대기"),
]


def to_text(markup: str) -> list[str]:
    """Render post HTML down to a list of visible, non-empty lines."""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", markup)
    s = re.sub(r"(?i)<img[^>]*>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    lines = []
    for raw in s.split("\n"):
        line = raw.replace(" ", " ").strip().strip("　").strip()
        if line:
            lines.append(line)
    return lines


def normalize_name(name: str) -> str:
    """Readable form: full-width latin/digits -> ASCII, U+3000 -> space."""
    n = unicodedata.normalize("NFKC", name)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def find_price(line: str) -> tuple[int, str] | None:
    """Return (value, tax_note) if the line carries a yen amount."""
    ascii_line = line.translate(_DIGIT_MAP)
    m = _PRICE_RE.search(ascii_line)
    if not m:
        return None
    token = (m.group(1) or m.group(2)).strip(".,")
    if token.isdigit():
        digits = token
    elif _GROUPED_RE.match(token):
        digits = re.sub(r"[.,]", "", token)
    else:
        return None
    value = int(digits)
    if value < 100:  # guards against vintages / volumes read as prices
        return None
    tax = ""
    if "税込" in line:
        tax = "税込"
    elif "税抜" in line or "税別" in line:
        tax = "税抜"
    return value, tax


# Lines that sit above a price but are not part of the product name:
# promo banners, section headers, parentheticals and tasting-note prose.
_BANNER_RE = re.compile(r"^[★☆【]|[★☆】]$|[！!]{2}|入荷いたしました|再入荷")
_PAREN_RE = re.compile(r"^[（(].*[）)]$")
_PROSE_RE = re.compile(r"[。、]$")
_NAME_LINE_CAP = 3
_PROSE_LEN = 45


def pick_name_lines(pending: list[str]) -> tuple[list[str], bool]:
    """Reduce the text lines above a price to the product-name lines.

    Returns (lines, filtered) where `filtered` says whether anything was
    dropped -- the caller keeps the untouched block so a heuristic miss is
    always recoverable from the CSV.
    """
    kept = [
        line for line in pending
        if not _BANNER_RE.search(line)
        and not _PAREN_RE.match(line)
        and not _PROSE_RE.search(line)
        and len(line) <= _PROSE_LEN
    ]
    if not kept:
        kept = pending[-1:]
    trimmed = kept[-_NAME_LINE_CAP:]
    return trimmed, trimmed != pending


def find_status(lines: list[str]) -> str:
    blob = " ".join(lines)
    for pattern, label in _STATUS_PATTERNS:
        if re.search(pattern, blob, re.I):
            return label
    return ""


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

@dataclass
class Item:
    name_raw: str
    price_raw: str
    price_jpy: int | None
    tax_note: str
    status: str
    name_context: str
    post_title: str
    url: str
    post_id: int
    date: str
    item_index: int
    items_in_post: int

    @property
    def name(self) -> str:
        return normalize_name(self.name_raw)

    @property
    def price_display(self) -> str:
        if self.price_jpy is None:
            return self.status or "가격 미표기"
        tax = f" ({self.tax_note})" if self.tax_note else ""
        return f"¥{self.price_jpy:,}{tax}"


@dataclass
class Report:
    posts_seen: int = 0
    duplicate_urls: int = 0
    rest_total: int | None = None
    archive_total: int | None = None
    archive_pages: int | None = None
    pages_fetched: int = 0
    aborted: str = ""
    items: list[Item] = field(default_factory=list)


# --------------------------------------------------------------------------
# Parsing a single post
# --------------------------------------------------------------------------

def parse_post(post: dict) -> list[Item]:
    """Split one post into (name, price) rows.

    The body is a flat run of lines; every line holding a yen amount closes
    an item, and the text lines above it are that item's name. Posts with no
    amount at all yield a single row carrying a status string.
    """
    post_id = post["id"]
    url = post["link"]
    title = html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"])).strip()
    date = (post.get("date") or "")[:10]
    lines = to_text(post["content"]["rendered"])

    rows: list[dict] = []
    pending: list[str] = []
    for line in lines:
        hit = find_price(line)
        if hit is None:
            pending.append(line)
            continue
        value, tax = hit
        # When the name shares the price's line ("サロン２００８　１５００ｍｌ　￥…"),
        # that head IS the name -- anything above it is surrounding prose.
        head = re.split(r"[¥￥]", line)[0].strip("　 ").strip()
        if head:
            name, filtered = head, bool(pending)
        elif pending:
            parts, filtered = pick_name_lines(pending)
            name = "　".join(parts)
        else:
            name, filtered = title, False
        rows.append({
            "name": name, "price_raw": line, "jpy": value, "tax": tax, "status": "",
            "context": "　| ".join(pending) if filtered else "",
        })
        pending = []

    if not rows:
        rows.append({
            "name": title, "price_raw": " ".join(lines)[:200], "jpy": None, "tax": "",
            "status": find_status(lines) or "가격 미표기", "context": "",
        })

    total = len(rows)
    return [
        Item(name_raw=r["name"], price_raw=r["price_raw"], price_jpy=r["jpy"],
             tax_note=r["tax"], status=r["status"], name_context=r["context"],
             post_title=title, url=url, post_id=post_id, date=date,
             item_index=i + 1, items_in_post=total)
        for i, r in enumerate(rows)
    ]


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

def collect_via_rest(report: Report) -> None:
    seen: set[str] = set()
    page = 1
    while True:
        url = (f"{BASE}/wp-json/wp/v2/posts?categories={CATEGORY_ID}"
               f"&per_page={PER_PAGE}&page={page}&orderby=date&order=desc"
               f"&_fields=id,link,date,title,content")
        print(f"[REST] page {page} ...", file=sys.stderr)
        try:
            body, headers = fetch(url)
        except FetchError as exc:
            if page > 1 and report.rest_total and len(seen) >= report.rest_total:
                break  # already have everything; the extra page just doesn't exist
            report.aborted = str(exc)
            return
        report.pages_fetched += 1
        if report.rest_total is None and "x-wp-total" in headers:
            report.rest_total = int(headers["x-wp-total"])

        posts = json.loads(body.decode("utf-8"))
        if not posts:
            print(f"  page {page} empty -> last page", file=sys.stderr)
            break

        for post in posts:
            report.posts_seen += 1
            if post["link"] in seen:
                report.duplicate_urls += 1
                continue
            seen.add(post["link"])
            report.items.extend(parse_post(post))

        if len(posts) < PER_PAGE:
            break
        page += 1


def verify_via_archive(report: Report) -> None:
    """Cross-check the REST count against the rendered category archive."""
    try:
        body, _ = fetch(f"{BASE}{CATEGORY_PATH}")
    except FetchError as exc:
        print(f"  ! archive verification skipped: {exc}", file=sys.stderr)
        return
    page1 = body.decode("utf-8", "replace")
    per_page = len(re.findall(r'<div class="post">', page1))
    m = re.search(r"<span class='pages'>\s*1\s*/\s*(\d+)\s*</span>", page1)
    if not m or not per_page:
        return
    pages = int(m.group(1))
    report.archive_pages = pages
    try:
        last, _ = fetch(f"{BASE}{CATEGORY_PATH}page/{pages}/")
        on_last = len(re.findall(r'<div class="post">', last.decode("utf-8", "replace")))
    except FetchError:
        on_last = per_page
    report.archive_total = (pages - 1) * per_page + on_last


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def write_markdown(report: Report, path: Path) -> None:
    items = report.items
    priced = [i for i in items if i.price_jpy is not None]
    unpriced = [i for i in items if i.price_jpy is None]
    urls = len({i.url for i in items})

    out: list[str] = []
    out.append("# CHARME du VIN — シャンパーニュ (Champagne) 전체 상품")
    out.append("")
    out.append(f"- **총 상품 수: {len(items)}건**  "
               f"(게시물 {urls}건 — 한 게시물에 여러 병이 실린 경우 분리 집계)")
    out.append(f"- 가격 확인: {len(priced)}건 / 가격 없음: {len(unpriced)}건")
    if priced:
        lo, hi = min(i.price_jpy for i in priced), max(i.price_jpy for i in priced)
        incl = sum(1 for i in priced if i.tax_note == "税込")
        excl = sum(1 for i in priced if i.tax_note == "税抜")
        out.append(f"- 가격 범위: ¥{lo:,} – ¥{hi:,}")
        out.append(f"- 세금 표기: 税込(포함) {incl}건 / 税抜(별도) {excl}건 / "
                   f"표기 없음 {len(priced) - incl - excl}건 "
                   f"— **두 기준이 섞여 있으므로 단순 비교 시 주의**")
    out.append(f"- 카테고리: `{BASE}{CATEGORY_PATH}` (WordPress category id {CATEGORY_ID})")
    out.append(f"- 수집 시각: {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    out.append("")
    out.append("| # | 상품명 | 가격 | 링크 |")
    out.append("|---:|---|---:|---|")
    for n, item in enumerate(items, 1):
        name = item.name.replace("|", "\\|")
        if item.items_in_post > 1:
            name += f" <sub>({item.item_index}/{item.items_in_post})</sub>"
        out.append(f"| {n} | {name} | {item.price_display} | [링크]({item.url}) |")
    out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


CSV_COLUMNS = [
    "no", "name", "name_raw", "price_jpy", "price_raw", "tax_note", "status",
    "url", "post_id", "post_title", "post_date", "item_index", "items_in_post",
    "name_context",
]


def write_csv(report: Report, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for n, i in enumerate(report.items, 1):
            writer.writerow([
                n, i.name, i.name_raw,
                i.price_jpy if i.price_jpy is not None else "",
                i.price_raw, i.tax_note,
                i.status or ("" if i.price_jpy is not None else "가격 미표기"),
                i.url, i.post_id, i.post_title, i.date,
                i.item_index, i.items_in_post, i.name_context,
            ])


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the HTML archive cross-check")
    args = ap.parse_args()

    report = Report()
    collect_via_rest(report)
    if not args.no_verify:
        verify_via_archive(report)

    if not report.items:
        print(f"FAILED: nothing collected. {report.aborted}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(report, args.out_dir / "champagne.md")
    write_csv(report, args.out_dir / "champagne.csv")

    priced = sum(1 for i in report.items if i.price_jpy is not None)
    print("\n=== summary ===")
    print(f"REST pages fetched : {report.pages_fetched}")
    print(f"posts seen         : {report.posts_seen} "
          f"(duplicate URLs dropped: {report.duplicate_urls})")
    print(f"X-WP-Total         : {report.rest_total}")
    print(f"archive says       : {report.archive_total} items "
          f"over {report.archive_pages} pages")
    print(f"rows written       : {len(report.items)} "
          f"(priced {priced}, unpriced {len(report.items) - priced})")
    print(f"names heuristically trimmed (see name_context): "
          f"{sum(1 for i in report.items if i.name_context)}")
    if report.aborted:
        print(f"ABORTED EARLY      : {report.aborted}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
