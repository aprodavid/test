#!/usr/bin/env python3
"""Tests for wine_price_check.

Parsing is checked against pages captured from the live site
(tests/fixtures), so the selectors are pinned to real markup rather than
to the formats the brief described from memory. The strongest check is
TestFixtures: parsed listing counts and the mean recomputed from them must
match the counts and 평균가 the site prints on the same page.
"""

import unittest
from datetime import date
from pathlib import Path

import wine_price_check as w

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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

    def test_seller_rows_are_line_separated(self):
        # the real page puts the price and the date on separate lines
        text = "183,300원\n2021-06-18\n201,000원\n2023.04.02"
        self.assertEqual(w.parse_seller_prices(text), [
            (183300, date(2021, 6, 18)),
            (201000, date(2023, 4, 2)),
        ])

    def test_seller_rows_reject_impossible_date(self):
        self.assertEqual(w.parse_seller_prices("10,000원\n2021-13-45"), [])

    def test_strip_markup_drops_scripts(self):
        html = "<div>183,300원<script>var x='999,999원'</script></div>"
        self.assertNotIn("999,999", w.strip_markup(html))


class TestFixtures(unittest.TestCase):
    """Parsed against pages captured from wadossi."""

    def test_small_pricelist_matches_site_header(self):
        pl = w.parse_pricelist(w.strip_markup(fixture("pricelist_5597.html")))
        self.assertEqual(pl.declared_count, 3)
        self.assertEqual(len(pl.listings), 3)
        self.assertEqual(pl.site_average, 180700)
        mean = sum(l.price for l in pl.listings) / len(pl.listings)
        self.assertEqual(round(mean), pl.site_average)

    def test_large_pricelist_matches_site_header(self):
        pl = w.parse_pricelist(w.strip_markup(fixture("pricelist_628.html")))
        self.assertEqual(pl.declared_count, 44)
        self.assertEqual(len(pl.listings), 44)  # no pagination to follow
        mean = sum(l.price for l in pl.listings) / len(pl.listings)
        self.assertEqual(round(mean), pl.site_average)

    def test_header_average_is_not_counted_as_a_listing(self):
        pl = w.parse_pricelist(w.strip_markup(fixture("pricelist_628.html")))
        self.assertNotIn(pl.site_average, [l.price for l in pl.listings[:1]])
        self.assertEqual(pl.declared_count, len(pl.listings))

    def test_one_winenumber_pools_several_vintages(self):
        pl = w.parse_pricelist(w.strip_markup(fixture("pricelist_628.html")))
        self.assertGreater(len({l.vintage for l in pl.listings}), 1)

    def test_search_cards_carry_names(self):
        cands = w.parse_search(fixture("search_egly.html"))
        self.assertGreaterEqual(len(cands), 4)
        self.assertTrue(all(c.wine_number.isdigit() for c in cands))
        self.assertTrue(any("브뤼 트라디씨옹" in c.name_ko for c in cands))

    def test_scoring_picks_the_named_cuvee(self):
        cands = w.parse_search(fixture("search_egly.html"))
        row = {"검색어": "Egly-Ouriet Brut Rosé Grand Cru",
               "생산자_영문": "Egly-Ouriet", "생산자_한글": "에글리 우리에"}
        best = max(cands, key=lambda c: w.score_candidate(c, row))
        self.assertIn("로제", best.name_ko)


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
        # Korean first: wadossi's index returns nothing for most English names
        self.assertEqual(kws, ["들롱", "Delong"])

    def test_latin_cuvee_is_combined_with_korean_producer(self):
        kws = w.candidate_keywords({
            "검색어": "Salon 2004", "생산자_한글": "살롱",
            "큐베": "Le Mesnil 2004", "생산자_영문": "Salon"})
        # Korean producer+cuvee first, then producer, then the English forms
        self.assertEqual(kws, ["살롱 Le Mesnil 2004", "살롱", "Salon 2004", "Salon"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestVintage(unittest.TestCase):
    def test_target_vintage_extracted(self):
        self.assertEqual(w.target_vintage("Salon 2004"), "2004")
        self.assertEqual(w.target_vintage("Piper-Heidsieck Brut"), "")

    def test_match_narrows_to_requested_vintage(self):
        ls = [w.Listing(249000, date(2026, 1, 1), "2008"),
              w.Listing(650000, date(2026, 1, 1), "2010"),
              w.Listing(255000, date(2026, 1, 1), "2008")]
        kept, note = w.match_vintage(ls, "2008")
        self.assertEqual([l.price for l in kept], [249000, 255000])
        self.assertIn("2008", note)

    def test_falls_back_when_vintage_absent(self):
        ls = [w.Listing(249000, date(2026, 1, 1), "2008")]
        kept, note = w.match_vintage(ls, "1998")
        self.assertEqual(len(kept), 1)
        self.assertIn("미발견", note)

    def test_no_target_vintage_keeps_everything(self):
        ls = [w.Listing(1, date(2026, 1, 1), "2008"), w.Listing(2, date(2026, 1, 1), "NV")]
        kept, note = w.match_vintage(ls, "")
        self.assertEqual(len(kept), 2)
        self.assertEqual(note, "")


class TestProducerGate(unittest.TestCase):
    """Style words must never carry a match on their own."""

    def test_same_style_different_producer_scores_zero(self):
        row = {"검색어": "Justin Extra Brut 2009", "생산자_영문": "Justin",
               "생산자_한글": "쥐스탱"}
        cand = w.Candidate("", "", "Schramsberg Extra Brut 2009")
        self.assertEqual(w.score_candidate(cand, row), 0.0)

    def test_right_producer_still_matches(self):
        row = {"검색어": "Justin Extra Brut 2009", "생산자_영문": "Justin",
               "생산자_한글": "쥐스탱"}
        cand = w.Candidate("", "쥐스탱, 엑스트라 브뤼 2009", "Justin, Extra Brut 2009")
        self.assertGreaterEqual(w.score_candidate(cand, row), w.MIN_MATCH_SCORE)

    def test_generic_only_target_does_not_match_everything(self):
        row = {"검색어": "Brut Réserve", "생산자_영문": "", "생산자_한글": ""}
        self.assertEqual(
            w.score_candidate(w.Candidate("", "", "Anything Brut Réserve"), row), 0.0)

    def test_gate_survives_truncated_search_cards(self):
        row = {"검색어": "Egly-Ouriet Brut Tradition", "생산자_영문": "Egly-Ouriet",
               "생산자_한글": "에글리 우리에"}
        cand = w.Candidate("5597", "에글리 우리에, 브뤼 트라디씨옹 그랑 NV", "Egly Ouriet, Brut Tr")
        self.assertGreaterEqual(w.score_candidate(cand, row), w.MIN_MATCH_SCORE)


class TestCuveeDiscrimination(unittest.TestCase):
    ROW = {"검색어": "Billecart-Salmon Blanc de Blancs",
           "생산자_영문": "Billecart-Salmon", "생산자_한글": "빌까르 살몽"}

    def test_right_cuvee_outscores_wrong_cuvee(self):
        right = w.Candidate("", "빌까르 살몽, 블랑 드 블랑 NV", "Billecart Salmon, Blanc de Bl")
        wrong = w.Candidate("", "빌까르 살몽, 드미 섹 NV", "Billecart Salmon, Demi Se")
        self.assertGreater(w.score_candidate(right, self.ROW),
                           w.score_candidate(wrong, self.ROW))

    def test_wrong_cuvee_alone_is_below_threshold(self):
        wrong = w.Candidate("", "빌까르 살몽, 드미 섹 NV", "Billecart Salmon, Demi Se")
        self.assertLess(w.score_candidate(wrong, self.ROW), w.MIN_MATCH_SCORE)

    def test_short_token_prefix_cannot_match(self):
        # "delong" must not match the "de" in "Jolie-Laide Melon de Bourgogne"
        row = {"검색어": "Delong", "생산자_영문": "Delong", "생산자_한글": "들롱"}
        cand = w.Candidate("", "", "Jolie-Laide Melon de Bourgogne 2025")
        self.assertEqual(w.score_candidate(cand, row), 0.0)

    def test_still_wine_is_rejected(self):
        row = {"검색어": "Justin Extra Brut 2009", "생산자_영문": "Justin",
               "생산자_한글": "쥐스탱"}
        cand = w.Candidate("", "저스틴, 까베르네 소비뇽 2019", "Justin, Cabernet Sauvignon",
                           is_sparkling=False)
        self.assertEqual(w.score_candidate(cand, row), 0.0)

    def test_wrong_vintage_is_penalised(self):
        row = {"검색어": "Pol Roger Brut Vintage 2018", "생산자_영문": "Pol Roger",
               "생산자_한글": "폴 로저"}
        right = w.Candidate("", "폴 로저, 브뤼 밀레짐 2018", "Pol Roger, Brut Vintage 2018")
        wrong = w.Candidate("", "폴 로저, 블랑 드 블랑 NV", "Pol Roger, Blanc de Blancs")
        self.assertGreater(w.score_candidate(right, row), w.score_candidate(wrong, row))
