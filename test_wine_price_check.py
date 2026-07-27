#!/usr/bin/env python3
"""Tests for the offline half of wine_price_check.

Covers everything that does not touch the network: FX conversion, the text
formats the brief documented, outlier trimming, the staleness rule, and the
judgement/discount arithmetic. The HTTP layer is untested here because the
egress policy denies all three source hosts.
"""

import unittest
from datetime import date

import wine_price_check as w


class TestFx(unittest.TestCase):
    def test_jpy_is_per_yen(self):
        # 100엔 = 900원
        self.assertEqual(w.to_krw(100, "JPY"), 900)

    def test_other_currencies(self):
        self.assertEqual(w.to_krw(2, "USD"), 2980)
        self.assertEqual(w.to_krw(10, "EUR"), 17000)
        self.assertEqual(w.to_krw(1, "GBP"), 1950)

    def test_unknown_currency(self):
        with self.assertRaises(ValueError):
            w.to_krw(1, "CHF")


class TestParsing(unittest.TestCase):
    def test_price_range(self):
        self.assertEqual(
            w.parse_price_range("판매가 162,630 ~ 216,840원"), (162630, 216840))

    def test_price_range_absent(self):
        self.assertIsNone(w.parse_price_range("가격 정보가 없습니다"))

    def test_seller_rows(self):
        text = "183,300원 / 2021-06-18\n201,000원 / 2023.04.02\n95,000원 / 2024/11/30"
        self.assertEqual(w.parse_seller_prices(text), [
            (183300, date(2021, 6, 18)),
            (201000, date(2023, 4, 2)),
            (95000, date(2024, 11, 30)),
        ])

    def test_seller_rows_reject_impossible_date(self):
        self.assertEqual(w.parse_seller_prices("10,000원 / 2021-13-45"), [])

    def test_strip_markup_drops_scripts(self):
        html = "<div>183,300원 / 2021-06-18<script>var x='999,999원'</script></div>"
        self.assertNotIn("999,999", w.strip_markup(html))

    def test_main_region_cuts_recommendations(self):
        text = "183,300원 / 2021-06-18\n이 와인과 비슷한 와인\n5,000원 / 2024-01-01"
        kept = w.main_region(text)
        self.assertIn("183,300", kept)
        self.assertNotIn("5,000원", kept)


class TestAggregate(unittest.TestCase):
    today = date(2026, 7, 27)

    def test_empty_is_not_distributed(self):
        d = w.aggregate_domestic([], self.today)
        self.assertEqual(d.status, "미유통추정")
        self.assertIsNone(d.median)

    def test_thin_sample_flagged(self):
        d = w.aggregate_domestic(
            [(100000, date(2026, 1, 1)), (120000, date(2026, 2, 1))], self.today)
        self.assertTrue(d.thin_sample)
        self.assertEqual(d.sellers, 2)
        self.assertEqual(d.median, 110000)
        self.assertEqual(d.excluded, 0)

    def test_outliers_trimmed_both_ends(self):
        pairs = [(p, date(2026, 1, 1)) for p in
                 (100000, 105000, 110000, 400000, 30000)]
        d = w.aggregate_domestic(pairs, self.today)
        # median of raw = 105,000 -> band is 63,000 .. 157,500
        self.assertEqual(d.excluded, 2)
        self.assertEqual(d.sellers, 3)
        self.assertEqual(d.low, 100000)
        self.assertEqual(d.high, 110000)
        self.assertEqual(d.median, 105000)

    def test_boundaries_are_inclusive(self):
        pairs = [(p, date(2026, 1, 1)) for p in (60000, 100000, 150000)]
        d = w.aggregate_domestic(pairs, self.today)
        self.assertEqual(d.excluded, 0)  # exactly 0.6x and 1.5x are kept

    def test_stale_when_only_old_data(self):
        d = w.aggregate_domestic(
            [(183300, date(2021, 6, 18))], self.today)
        self.assertEqual(d.confidence, "낮음")
        self.assertEqual(d.latest, date(2021, 6, 18))

    def test_fresh_uses_latest_not_oldest(self):
        d = w.aggregate_domestic(
            [(183300, date(2021, 6, 18)), (190000, date(2026, 5, 1))], self.today)
        self.assertEqual(d.confidence, "최신")
        self.assertEqual(d.latest, date(2026, 5, 1))

    def test_stale_data_is_kept_not_dropped(self):
        d = w.aggregate_domestic([(183300, date(2019, 1, 1))], self.today)
        self.assertEqual(d.status, "조회성공")
        self.assertIsNotNone(d.median)


class TestJudgement(unittest.TestCase):
    def _row(self, **kw):
        return w.Row(id="1", 검색어="x", 분류="RM", 현지가_원화=kw.pop("local"), **kw)

    def test_domestic_wins_over_overseas(self):
        r = self._row(local=100000)
        r.dom = w.Domestic(median=200000, status="조회성공")
        r.해외가_원화 = 500000
        basis, ref, disc = r.judge()
        self.assertEqual(basis, "국내가")
        self.assertEqual(ref, 200000)
        self.assertAlmostEqual(disc, 0.5)

    def test_overseas_used_when_not_distributed(self):
        r = self._row(local=120000)
        r.해외가_원화 = 100000
        basis, ref, disc = r.judge()
        self.assertEqual(basis, "해외평균가")
        self.assertAlmostEqual(disc, -0.2)  # Japan is dearer

    def test_no_reference_at_all(self):
        basis, ref, disc = self._row(local=100000).judge()
        self.assertEqual(basis, "판정불가")
        self.assertIsNone(ref)
        self.assertIsNone(disc)


class TestCsvShape(unittest.TestCase):
    def test_row_matches_column_count(self):
        r = w.Row(id="1", 검색어="Salon 2004", 분류="NM", 현지가_원화=1683000.0)
        r.dom = w.aggregate_domestic(
            [(2000000, date(2026, 1, 1)), (2100000, date(2026, 2, 1))],
            date(2026, 7, 27))
        self.assertEqual(len(r.to_csv()), len(w.RESULT_COLUMNS))

    def test_columns_match_spec(self):
        self.assertEqual(w.RESULT_COLUMNS, [
            "id", "검색어", "분류", "현지가_원화",
            "국내가_최저", "국내가_중앙", "국내가_최고", "국내_판매처수",
            "국내가_최신등록일", "국내가_신뢰도", "국내가_상태",
            "해외_원통화", "해외_원가격", "해외가_원화", "해외_출처",
            "판정근거", "기준가_원화", "할인율", "표본부족", "제외건수", "비고",
        ])


class TestKeywordLadder(unittest.TestCase):
    def test_katakana_cuvee_is_not_used_as_query(self):
        kws = w.candidate_keywords({
            "검색어": "Delong", "생산자_한글": "들롱",
            "큐베": "テル オリジナル", "생산자_영문": "Delong"})
        self.assertEqual(kws, ["Delong", "들롱"])

    def test_latin_cuvee_is_combined_with_korean_producer(self):
        kws = w.candidate_keywords({
            "검색어": "Salon 2004", "생산자_한글": "살롱",
            "큐베": "Le Mesnil 2004", "생산자_영문": "Salon"})
        # the bare English producer is the last, broadest fallback
        self.assertEqual(kws, ["Salon 2004", "살롱 Le Mesnil 2004", "살롱", "Salon"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
