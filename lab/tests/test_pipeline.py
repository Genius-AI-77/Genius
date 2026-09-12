"""Pipeline behaviour: determinism, journaling, cost accounting, and the rule
that agreement between agents never bypasses the risk gate.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genius_lab.data import synthetic_candles
from genius_lab.execution import PaperBroker
from genius_lab.pipeline import Lab

VALID_DECISIONS = {"ENTERED", "VETOED", "NO_TRADE", "HOLDING"}


class Determinism(unittest.TestCase):
    def test_same_seed_gives_identical_markets(self):
        a = synthetic_candles(200, seed=33)
        b = synthetic_candles(200, seed=33)
        self.assertEqual([c.close for c in a], [c.close for c in b])

    def test_different_seeds_diverge(self):
        a = synthetic_candles(200, seed=33)
        b = synthetic_candles(200, seed=7)
        self.assertNotEqual([c.close for c in a], [c.close for c in b])

    def test_backtest_is_reproducible(self):
        candles = synthetic_candles(400, seed=33)
        m1 = Lab().run_backtest(candles, warmup=60)
        m2 = Lab().run_backtest(candles, warmup=60)
        self.assertEqual(m1, m2)


class JournalIntegrity(unittest.TestCase):
    def setUp(self):
        self.candles = synthetic_candles(500, seed=33)
        self.lab = Lab()
        self.metrics = self.lab.run_backtest(self.candles, warmup=60)

    def test_every_bar_produces_exactly_one_cycle_entry(self):
        cycles = [e for e in self.lab.journal.entries if e["type"] == "cycle"]
        self.assertEqual(len(cycles), len(self.candles) - 60)

    def test_decisions_are_all_recognised(self):
        for e in self.lab.journal.entries:
            if e["type"] == "cycle":
                self.assertIn(e["decision"], VALID_DECISIONS)

    def test_no_trade_is_recorded_not_discarded(self):
        self.assertGreater(self.metrics["no_trade"], 0,
                           "standing aside must be a counted outcome")
        self.assertEqual(
            self.metrics["cycles"],
            self.metrics["no_trade"] + self.metrics["vetoes"]
            + self.metrics["entries"]
            + sum(1 for e in self.lab.journal.entries
                  if e.get("type") == "cycle" and e["decision"] == "HOLDING"))

    def test_every_entry_records_all_six_stances(self):
        for e in self.lab.journal.entries:
            if e["type"] == "cycle":
                self.assertEqual(len(e["stances"]), 6)

    def test_vetoes_carry_a_stated_reason(self):
        vetoed = [e for e in self.lab.journal.entries
                  if e.get("type") == "cycle" and e["decision"] == "VETOED"]
        self.assertTrue(vetoed)
        for e in vetoed:
            self.assertTrue(e["detail"].startswith("VETO:"), e["detail"])


class CostAccounting(unittest.TestCase):
    def test_costs_are_charged_and_reported(self):
        lab = Lab()
        m = lab.run_backtest(synthetic_candles(500, seed=33), warmup=60)
        self.assertGreater(m["total_costs"], 0, "costs must not be free")
        for t in lab.broker.closed:
            self.assertGreater(t.costs, 0)

    def test_pnl_is_net_of_costs(self):
        broker = PaperBroker(starting_cash=10_000.0, fee_bps=10.0, slippage_k=0.0)
        broker.mark(100.0)
        broker.open_position(0, "long", 10.0, 100.0, 0.0)
        trade = broker.close_position(1, 100.0, 0.0, "flat exit")
        # a round trip at an unchanged price must lose exactly the fees
        self.assertLess(trade.pnl, 0)
        self.assertAlmostEqual(trade.pnl, -trade.costs, places=6)

    def test_slippage_moves_against_the_taker(self):
        broker = PaperBroker(starting_cash=10_000.0, fee_bps=0.0, slippage_k=0.1)
        broker.mark(100.0)
        broker.open_position(0, "long", 1.0, 100.0, 10.0)   # ATR 10 → 1.0 slip
        self.assertGreater(broker.entry_price, 100.0, "a buy must fill worse")


class RiskGate(unittest.TestCase):
    def test_agreement_alone_never_bypasses_the_gate(self):
        """Whatever the agents conclude, no cycle may open a position while the
        engine is halted."""
        lab = Lab()
        candles = synthetic_candles(500, seed=33)
        lab.risk.halted = True
        lab.risk.halt_reason = "test halt"
        for i in range(60, len(candles)):
            lab.run_cycle(candles[:i + 1], i)   # note: no new_session() call
        self.assertEqual(lab.broker.position_qty, 0)
        self.assertEqual(len(lab.broker.closed), 0)

    def test_position_size_is_never_agent_proposed(self):
        """No agent report may contain a quantity field the engine would trust."""
        lab = Lab()
        candles = synthetic_candles(200, seed=33)
        lab.run_cycle(candles, 199)
        for report in lab.last_reports:
            self.assertNotIn("qty", report["data"])
            self.assertNotIn("size", report["data"])


if __name__ == "__main__":
    unittest.main()
