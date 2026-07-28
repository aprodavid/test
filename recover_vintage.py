#!/usr/bin/env python3
"""
Recover the vintage for every row of all_result.csv and re-verify the match.

The vintage was never lost on the site -- it was parsed out of the katakana
name into a field the result schema had no column for, so it was dropped on
write. This pass reads the original post back, re-extracts the vintage,
appends it to both name columns, and then checks it against the vintage in
매칭된_와인명.

Source of the titles: the posts were captured from
/wp-json/wp/v2/posts?categories=... during the collection runs and are on
disk. A 12-post spot check re-fetched by id came back byte-identical for
both title and content, so the cache is used instead of 310 more requests.
Note that the last path segment of a 샴드뱅링크 is the post ID, not the slug
-- ?slug={n} returns zero rows, /posts/{n} returns the post.

Prices are the key back to the right bottle: one post can list several, and
현지가_원화 in the CSV is the 750ml-equivalent price after the year factor,
so recomputing it per bottle identifies which one a row came from.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

import italia_lexicon as lex
import italia_price_check as ip
import scrape_champagne as sc
import wine_price_check as wpc

OUT_DIR = Path(__file__).resolve().parent
CACHES = {"이탈리아": ("italia_posts.json", "italia"),
          "스페인·포르투갈": ("spain_posts.json", "iberia"),
          "미국": ("america_posts.json", "america")}

DELAY_SECONDS = 1.0
CHECKPOINT_EVERY = 50

NV_RE = re.compile(r"(?:^|[\s　])NV(?:$|[\s　])|ノンヴィンテージ|ノンビンテージ", re.I)
MATCH_VINTAGE_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")

NO_VINTAGE = "표기없음"


def load_posts() -> dict[str, tuple[dict, str]]:
    """link -> (post, lexicon name)."""
    out: dict[str, tuple[dict, str]] = {}
    for _, (fn, table) in CACHES.items():
        path = OUT_DIR / fn
        if not path.exists():
            continue
        for post in json.loads(path.read_text(encoding="utf-8")):
            out[post["link"]] = (post, table)
    return out


def fetch_post(link: str) -> dict:
    """Live fallback, by ID -- the URL tail is the post ID, not a slug."""
    pid = link.rstrip("/").rsplit("/", 1)[-1]
    url = f"http://charme-du-vin.com/wp-json/wp/v2/posts/{pid}?_fields=id,link,date,title,content"
    req = urllib.request.Request(url, headers={"User-Agent": wpc.UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def bottles_of(post: dict) -> list[dict]:
    out = []
    for item in sc.parse_post(post):
        jpy = ip.after_tax(item.price_jpy, item.tax_note)
        if jpy:
            out.append({"name": item.name_raw, "jpy": jpy, "date": item.date})
    return out


def estimated_krw(jpy: int, volume: str, year: int, table: str) -> int:
    factors = ip.YEAR_FACTOR_BY_LEXICON.get(table) or ip.YEAR_FACTOR
    krw750, _ = ip.to_750ml(jpy, volume)
    return round(krw750 * factors.get(year, 1.0))


def pick_bottle(bottles: list[dict], row: dict, table: str) -> dict | None:
    """Identify which bottle of a multi-bottle post this row came from.

    Price first, since 현지가_원화 is derived from it; name similarity only
    breaks ties (two bottles in one post can share a price).
    """
    if not bottles:
        return None
    want_price = int(row["현지가_원화"])
    year = int(row["게시연도"])
    lexicon = ip.LEXICONS[table]

    priced = []
    for b in bottles:
        conv = lex.convert(b["name"], lexicon)
        if estimated_krw(b["jpy"], conv["volume"], year, table) == want_price:
            priced.append((b, conv))
    if len(priced) == 1:
        return {"bottle": priced[0][0], "conv": priced[0][1], "how": "가격일치"}

    pool = priced or [(b, lex.convert(b["name"], lexicon)) for b in bottles]
    want = set(row["원어명"].split())
    best = max(pool, key=lambda bc: len(want & set(bc[1]["original"].split())))
    return {"bottle": best[0], "conv": best[1],
            "how": "가격일치·이름확인" if priced else "이름유사"}


def vintage_of(raw_name: str, conv: dict) -> str:
    if conv["vintage"]:
        return conv["vintage"]
    if NV_RE.search(unicodedata.normalize("NFKC", raw_name)):
        return "NV"
    return NO_VINTAGE


def verify(vintage: str, matched: str) -> str:
    """Compare the recovered vintage with the one in the matched wine name."""
    if not matched:
        return ""
    if vintage in ("", NO_VINTAGE):
        return "원문빈티지없음"
    found = MATCH_VINTAGE_RE.findall(matched)
    if not found:
        return "빈티지미상"
    if vintage == "NV":
        return "빈티지불일치"        # matched name carries a year, ours does not
    return "일치" if vintage in found else "빈티지불일치"


def append_vintage(name: str, vintage: str) -> str:
    if vintage in ("", NO_VINTAGE) or not name:
        return name
    return name if name.endswith(vintage) else f"{name} {vintage}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--infile", type=Path, default=OUT_DIR / "all_result.csv")
    ap.add_argument("--outfile", type=Path, default=OUT_DIR / "all_result_v2.csv")
    ap.add_argument("--live", action="store_true",
                    help="re-fetch every post instead of using the cache")
    args = ap.parse_args()

    posts = load_posts()
    rows = list(csv.DictReader(args.infile.open(encoding="utf-8-sig")))
    cols = list(rows[0].keys()) + ["빈티지", "빈티지검증"]

    katakana = re.compile(r"[ァ-ヿ]")
    stats = {"recovered": 0, "nv": 0, "none": 0, "demoted": 0,
             "missing_post": 0, "match_price": 0, "match_name": 0}
    unconverted: dict[str, int] = {}

    for i, row in enumerate(rows, 1):
        link = row["샴드뱅링크"]
        table = CACHES.get(row["카테고리"], (None, "italia"))[1]
        entry = posts.get(link)
        if entry is None or args.live:
            try:
                post = fetch_post(link)
                time.sleep(DELAY_SECONDS)
            except Exception as exc:            # noqa: BLE001
                print(f"  [{i}] {link} 실패: {exc}", file=sys.stderr)
                row["빈티지"], row["빈티지검증"] = NO_VINTAGE, "원문조회실패"
                stats["missing_post"] += 1
                continue
        else:
            post = entry[0]

        hit = pick_bottle(bottles_of(post), row, table)
        if hit is None:
            row["빈티지"], row["빈티지검증"] = NO_VINTAGE, "원문조회실패"
            stats["missing_post"] += 1
            continue
        stats["match_price" if hit["how"].startswith("가격") else "match_name"] += 1

        conv = hit["conv"]
        vintage = vintage_of(hit["bottle"]["name"], conv)
        row["빈티지"] = vintage
        if vintage == "NV":
            stats["nv"] += 1
        elif vintage == NO_VINTAGE:
            stats["none"] += 1
        else:
            stats["recovered"] += 1

        # names are rebuilt from the freshly converted title, then stamped
        row["원어명"] = append_vintage(conv["original"], vintage)
        row["상품명_한글"] = append_vintage(conv["korean"], vintage)
        for tok in conv["unconverted"]:
            unconverted[tok] = unconverted.get(tok, 0) + 1

        row["빈티지검증"] = verify(vintage, row["매칭된_와인명"])
        if row["빈티지검증"] == "빈티지불일치" and row["등급"] == "A":
            row["등급"] = "B"
            stats["demoted"] += 1

        if i % CHECKPOINT_EVERY == 0:
            with args.outfile.open("w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(r for r in rows if "빈티지" in r)
            print(f"  checkpoint {i}", file=sys.stderr)

    with args.outfile.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            r.setdefault("빈티지", NO_VINTAGE)
            r.setdefault("빈티지검증", "")
        w.writerows(rows)

    left = {t: n for t, n in unconverted.items() if katakana.search(t)}
    (OUT_DIR / "unconverted_tokens.json").write_text(
        json.dumps(dict(sorted(left.items(), key=lambda kv: -kv[1])),
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nrows            : {len(rows)}")
    print(f"vintage 복구    : {stats['recovered']}  NV: {stats['nv']}  "
          f"표기없음: {stats['none']}  조회실패: {stats['missing_post']}")
    print(f"병 특정         : 가격일치 {stats['match_price']} / 이름유사 {stats['match_name']}")
    print(f"A->B 강등       : {stats['demoted']}")
    print(f"남은 미변환 토큰: {len(left)}종 / {sum(left.values())}회")
    return 0


if __name__ == "__main__":
    sys.exit(main())
