"""Desk safety tests. All offline: synthetic market, shadow venue, temp state.

These prove the claims the runbook makes: pilot limits bind in dollars, books
are isolated, the kill switch flattens and blocks, state survives a restart,
a reconciliation mismatch halts, and secrets never reach the published file.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
sys.path.insert(0, DESK)
sys.path.insert(0, os.path.join(os.path.dirname(DESK), "lab"))

from genius_desk import publish                              # noqa: E402
from genius_desk.config import DeskConfig, Secrets           # noqa: E402
from genius_desk.runner import Desk                          # noqa: E402
from genius_desk.venue import ShadowVenue                    # noqa: E402
from genius_lab.risk import PILOT_100, RiskEngine, TradeProposal  # noqa: E402


def make_desk(tmp, **over):
    cfg = DeskConfig(state_dir=os.path.join(tmp, "state"), data_dir=os.path.join(tmp, "data"), **over)
    return Desk(cfg, Secrets(), offline=True)


class PilotLimits(unittest.TestCase):
    class _B:  # minimal broker
        equity = 33.33
        position_qty = 0.0

    def test_dollar_cap_binds_not_percentage(self):
        eng = RiskEngine(self._B(), PILOT_100)
        d = eng.review(TradeProposal("long", 70_000, 66_000, 0.8, "t"), 10)
        self.assertTrue(d.approved)
        self.assertAlmostEqual(d.qty * 4_000, 1.0, places=6, msg="exactly $1 at risk")

    def test_no_leverage_caps_risk_below_a_dollar_when_stop_is_close(self):
        """A 2.9% stop would need $35 of notional on a $33 book; without
        leverage the cap wins and the real risk is under $1. That is correct."""
        eng = RiskEngine(self._B(), PILOT_100)
        d = eng.review(TradeProposal("long", 70_000, 68_000, 0.8, "t"), 10)
        self.assertTrue(d.approved)
        self.assertLessEqual(d.qty * 70_000, 33.33 + 1e-6)
        self.assertLess(d.qty * 2_000, 1.0)
        self.assertTrue(any("exposure limit" in r for r in d.reasons))

    def test_no_leverage(self):
        eng = RiskEngine(self._B(), PILOT_100)
        d = eng.review(TradeProposal("long", 70_000, 69_990, 0.8, "t"), 10)  # stop inside noise band
        self.assertFalse(d.approved)
        d = eng.review(TradeProposal("long", 70_000, 69_800, 0.8, "t"), 10)  # 0.29% stop
        self.assertTrue(d.approved)
        self.assertLessEqual(d.qty * 70_000, 33.33 + 1e-6, "notional capped at equity")

    def test_daily_dollar_halt(self):
        b = self._B(); eng = RiskEngine(b, PILOT_100)
        b.equity = 33.33 - 3.01
        self.assertFalse(eng.review(TradeProposal("long", 70_000, 68_000, 0.8, "t"), 1).approved)
        self.assertTrue(eng.halted)


class DeskBehaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_three_isolated_books_sum_to_the_account(self):
        d = make_desk(self.tmp)
        d.run_cycle()
        eq = [d.venue.equity(n) for n in d.books]
        self.assertEqual(len(eq), 3)
        self.assertAlmostEqual(sum(eq), 3 * 33.33, delta=0.5)   # only fees can move it in one cycle

    def test_state_survives_restart(self):
        d = make_desk(self.tmp)
        d.run_cycle(); d.run_cycle()
        before = {n: d.venue.equity(n) for n in d.books}
        pos_before = {n: (d.venue.position(n).to_dict() if d.venue.position(n) else None) for n in d.books}
        d2 = make_desk(self.tmp)                              # fresh process, same state dir
        self.assertEqual(d2.state["cycles"], 2)
        for n in d.books:
            self.assertAlmostEqual(d2.venue.equity(n), before[n], places=6)
            p = d2.venue.position(n)
            self.assertEqual(p.to_dict() if p else None, pos_before[n])

    def test_kill_switch_flattens_and_blocks(self):
        d = make_desk(self.tmp)
        for _ in range(6):
            d.run_cycle()
            if any(d.venue.position(n) for n in d.books):
                break
        d.venue.pos["FLUX"] = d.venue.pos["FLUX"] or None
        if not any(d.venue.position(n) for n in d.books):     # force one so the flatten path is exercised
            d.venue.open("FLUX", "long", 0.0003, d.venue.mark_price(), d.venue.mark_price() * 0.98, 0.0)
        closed = d.halt("test")
        self.assertGreaterEqual(len(closed), 1)
        self.assertTrue(all(d.venue.position(n) is None for n in d.books))
        e = d.run_cycle()
        self.assertNotEqual(e["decision"], "ENTERED")
        self.assertTrue(all(v["decision"] != "ENTERED" for v in e["books"].values()))
        d2 = make_desk(self.tmp)                              # halt survives restart
        self.assertTrue(d2.state["halted"])
        d2.resume()
        self.assertFalse(d2.state["halted"])

    def test_lot_rounding_rejects_dust(self):
        d = make_desk(self.tmp, order_step=1.0, min_order=1.0)     # 1 SOL lots: more than a $33 book can buy
        e = d.run_cycle()
        for v in e["books"].values():
            self.assertNotEqual(v["decision"], "ENTERED")
            if v["decision"] == "VETOED":
                self.assertIn("venue minimum", v["detail"])

    def test_reconcile_mismatch_halts_live_desk(self):
        d = make_desk(self.tmp)
        d.venue.mode = "live"                                  # pretend; still shadow fills
        d.books["EUCLID"].entry_bar_ts = 12345                 # journal says open, venue says flat
        d.run_cycle()
        self.assertTrue(d.state["halted"])
        self.assertIn("reconciliation", d.state["halt_reason"])

    def test_published_payload_has_site_shape_and_no_secrets(self):
        d = make_desk(self.tmp)
        d.run_cycle()
        p = publish.build_payload(d)
        for k in ("meta", "metrics", "desk", "equity_curve", "reports", "journal_tail", "closed_trades"):
            self.assertIn(k, p)
        self.assertEqual(p["meta"]["execution"], "shadow")
        self.assertEqual(len(p["desk"]["books"]), 3)
        self.assertEqual([r["agent"] for r in p["reports"]], ["ATLAS", "EUCLID", "FLUX", "VETO", "HERMES", "LEDGER"])
        blob = json.dumps(p)
        for word in ("DESK_AGENT_KEY", "x-access-token", "secret"):
            self.assertNotIn(word, blob)

    def test_secrets_repr_redacts(self):
        s = Secrets(agent_key="0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318",
                    account="0x1111111111111111111111111111111111111111",
                    git_remote="https://x-access-token:ghp_abc@github.com/x/y.git")
        self.assertNotIn("4c0883", repr(s)); self.assertNotIn("ghp_", str(s))
        self.assertIn("agent_key=set", repr(s))


class ShadowVenueMaths(unittest.TestCase):
    def test_round_trip_costs_two_fees(self):
        v = ShadowVenue(["A"], 33.33, mark=100.0, fee_bps=10.0, slippage_k=0.0)
        v.open("A", "long", 0.1, 100.0, 98.0, 0.0)
        c = v.close("A", 100.0, 0.0, "flat exit")
        self.assertAlmostEqual(c.costs, 2 * 0.1 * 100 * 0.001, places=6)
        self.assertAlmostEqual(c.pnl, -c.costs, places=6)
        self.assertAlmostEqual(v.equity("A"), 33.33 - c.costs, places=6)

    def test_short_profits_when_price_falls(self):
        v = ShadowVenue(["A"], 33.33, mark=100.0, fee_bps=0.0, slippage_k=0.0)
        v.open("A", "short", 0.1, 100.0, 102.0, 0.0)
        v.set_mark(90.0)
        self.assertAlmostEqual(v.position("A").unrealized, 1.0, places=6)
        self.assertAlmostEqual(v.close("A", 90.0, 0.0, "x").pnl, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
