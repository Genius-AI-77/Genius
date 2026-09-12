"""Live-data layer, tested offline: parsing, aggressor mapping, tape overlay,
book maths, news scoring, and the no-look-ahead guarantee. No network."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genius_lab.data import (Book, Candle, Trade, _parse_iso, apply_tape,
                             synthetic_candles, trade_from_row)
from genius_lab.news import NewsBias, NewsItem, parse_feed, score
from genius_lab.pipeline import Lab


class IsoParsing(unittest.TestCase):
    def test_handles_micro_nano_and_whole_seconds(self):
        base = _parse_iso("2026-09-12T02:24:42Z")
        self.assertAlmostEqual(_parse_iso("2026-09-12T02:24:42.534964Z"), base + 0.534964, places=6)
        self.assertAlmostEqual(_parse_iso("2026-09-12T02:24:42.115587213Z"), base + 0.115587, places=6)
        self.assertEqual(_parse_iso("2026-09-12T02:24:42+00:00"), base)


class AggressorMapping(unittest.TestCase):
    """Coinbase's `side` is the maker's side. Getting this backwards inverts delta."""

    def test_maker_buy_means_aggressor_sold(self):
        t = trade_from_row({"time": "2026-09-12T00:00:00Z", "price": "100", "size": "1", "side": "buy"})
        self.assertEqual(t.aggressor, "sell")

    def test_maker_sell_means_aggressor_bought(self):
        t = trade_from_row({"time": "2026-09-12T00:00:00Z", "price": "100", "size": "1", "side": "sell"})
        self.assertEqual(t.aggressor, "buy")


class TapeOverlay(unittest.TestCase):
    def _candles(self):
        return [Candle(ts=3600 * i, open=1, high=1, low=1, close=1, volume=10.0,
                       buy_volume=5.0, sell_volume=5.0) for i in range(4)]

    def test_fully_covered_bars_get_real_split_and_flag(self):
        c = self._candles()
        trades = [Trade(ts=3600 * 2 - 1, price=1, size=1, aggressor="buy"),   # tail of bar 1
                  Trade(ts=3600 * 2 + 10, price=1, size=3, aggressor="buy"),
                  Trade(ts=3600 * 2 + 20, price=1, size=1, aggressor="sell"),
                  Trade(ts=3600 * 3 + 5, price=1, size=2, aggressor="sell")]
        n = apply_tape(c, trades)
        self.assertEqual(n, 2, "bars 2 and 3 are fully covered; bar 1 only partially")
        self.assertTrue(c[2].tape and c[3].tape)
        self.assertFalse(c[0].tape or c[1].tape)
        # candle volume stays authoritative; tape supplies the share (3:1 → 7.5/2.5)
        self.assertAlmostEqual(c[2].buy_volume, 7.5)
        self.assertAlmostEqual(c[2].sell_volume, 2.5)
        self.assertAlmostEqual(c[3].delta, -10.0)

    def test_partially_covered_bar_is_not_marked_real(self):
        """If the oldest trade is mid-bar, that bar's delta would be a lie."""
        c = self._candles()
        trades = [Trade(ts=3600 * 1 + 1800, price=1, size=1, aggressor="buy"),
                  Trade(ts=3600 * 2 + 10, price=1, size=1, aggressor="buy")]
        apply_tape(c, trades)
        self.assertFalse(c[1].tape, "bar 1 is only half covered")
        self.assertTrue(c[2].tape)

    def test_empty_tape_changes_nothing(self):
        c = self._candles()
        self.assertEqual(apply_tape(c, []), 0)
        self.assertFalse(any(x.tape for x in c))


class BookMaths(unittest.TestCase):
    def setUp(self):
        self.b = Book(ts=0, band_pct=0.02,
                      bids=[(99.0, 1.0), (98.0, 5.0), (90.0, 50.0)],
                      asks=[(101.0, 2.0), (102.0, 1.0), (110.0, 40.0)])

    def test_mid_and_spread(self):
        self.assertEqual(self.b.mid, 100.0)
        self.assertAlmostEqual(self.b.spread_bps, 200.0)

    def test_depth_respects_band(self):
        bid, ask = self.b.depth(0.03)   # 97..103
        self.assertEqual((bid, ask), (6.0, 3.0))

    def test_walls_are_largest_levels(self):
        w = self.b.walls(1)
        self.assertEqual(w["bids"], [(90.0, 50.0)])
        self.assertEqual(w["asks"], [(110.0, 40.0)])


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Bitcoin ETF outflows accelerate</title><link>http://x/1</link>
<pubDate>Thu, 11 Sep 2026 12:33:00 GMT</pubDate></item>
<item><title>Fed signals rate cut ahead</title><link>http://x/2</link>
<pubDate>Wed, 10 Sep 2026 09:00:00 GMT</pubDate></item>
<item><title>Local bakery wins award</title><link>http://x/3</link>
<pubDate>Wed, 10 Sep 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Exchange hack drains crypto wallets</title>
<link href="http://y/1"/><published>2026-09-09T08:00:00Z</published></entry>
</feed>"""


class NewsScoring(unittest.TestCase):
    def test_lexicon_direction_and_terms(self):
        s, terms = score("Bitcoin ETF outflows accelerate")
        self.assertLess(s, 0)
        self.assertIn("outflows", terms)
        s, terms = score("Fed signals rate cut ahead")
        self.assertGreater(s, 0)

    def test_irrelevant_headlines_are_ignored(self):
        self.assertEqual(score("Local bakery wins award"), (0.0, []))
        self.assertEqual(score("Massive crash at the motor race"), (0.0, []),
                         "no asset term → not a market headline")

    def test_parses_rss_and_atom_and_drops_unscored(self):
        rss = parse_feed(RSS, "T")
        self.assertEqual([i.title for i in rss],
                         ["Bitcoin ETF outflows accelerate", "Fed signals rate cut ahead"])
        atom = parse_feed(ATOM, "A")
        self.assertEqual(len(atom), 1)
        self.assertEqual(atom[0].link, "http://y/1")
        self.assertLess(atom[0].bias, 0)


class NoLookAhead(unittest.TestCase):
    """ATLAS must never see a headline published after the bar it is analysing."""

    def setUp(self):
        self.t0 = 1_000_000.0
        self.news = NewsBias([
            NewsItem(ts=self.t0 - 3600, title="past bearish", source="s", link="", bias=-0.8, matched=["x"]),
            NewsItem(ts=self.t0 + 3600, title="future bullish", source="s", link="", bias=+0.9, matched=["y"]),
        ], lookback_hours=72)

    def test_future_items_are_invisible(self):
        bias, events = self.news.bias_at(self.t0)
        self.assertLess(bias, 0)
        self.assertEqual([e["headline"] for e in events], ["past bearish"])

    def test_future_items_appear_once_time_passes(self):
        bias, events = self.news.bias_at(self.t0 + 7200)
        self.assertEqual({e["headline"] for e in events}, {"past bearish", "future bullish"})

    def test_items_outside_lookback_expire(self):
        # at t0+71h: "past bearish" is 72h old (expired), "future bullish" 70h old (in)
        bias, events = self.news.bias_at(self.t0 + 71 * 3600)
        self.assertEqual([e["headline"] for e in events], ["future bullish"])
        self.assertGreater(bias, 0)


class BookOnlyOnLatestBar(unittest.TestCase):
    """A 'now' snapshot handed to historical bars would be look-ahead."""

    def test_only_final_cycle_sees_depth(self):
        candles = synthetic_candles(120, seed=1)
        book = Book(ts=0, band_pct=0.02, bids=[(1.0, 1.0)], asks=[(1.1, 1.0)])
        seen = []
        lab = Lab()
        orig = lab.orderflow.analyze
        def spy(ctx):
            seen.append(ctx.book is not None)
            return orig(ctx)
        lab.orderflow.analyze = spy
        lab.run_backtest(candles, warmup=60, book=book)
        self.assertEqual(sum(seen), 1)
        self.assertTrue(seen[-1])


if __name__ == "__main__":
    unittest.main()
