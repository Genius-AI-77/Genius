"""The risk engine is the one component whose guarantees must hold unconditionally.

These tests exist to prove the claims made on the public site: the limits are
enforced by arithmetic, the veto has no override path, and "no trade" is a real
recorded outcome rather than a failure mode.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genius_lab.execution import PaperBroker
from genius_lab.risk import (MAX_CONSECUTIVE_LOSSES, MAX_DAILY_LOSS,
                             MAX_EXPOSURE, MAX_RISK_PER_TRADE, MIN_CONFIDENCE,
                             RiskEngine, TradeProposal)


def proposal(price=100.0, invalidation=98.0, confidence=0.8, side="long"):
    return TradeProposal(side=side, price=price, invalidation=invalidation,
                         confidence=confidence, thesis="test")


class RiskLimits(unittest.TestCase):
    def setUp(self):
        self.broker = PaperBroker(starting_cash=100_000.0)
        self.broker.mark(100.0)
        self.risk = RiskEngine(self.broker)

    def test_approves_a_well_formed_proposal(self):
        d = self.risk.review(proposal(), bar_index=100)
        self.assertTrue(d.approved)
        self.assertGreater(d.qty, 0)
        self.assertEqual(d.stop, 98.0)

    def test_risk_per_trade_never_exceeds_the_limit(self):
        """Size is derived so that a stop-out costs exactly the risk budget."""
        d = self.risk.review(proposal(price=100.0, invalidation=98.0), bar_index=100)
        loss_if_stopped = d.qty * (100.0 - 98.0)
        budget = self.broker.equity * MAX_RISK_PER_TRADE
        self.assertAlmostEqual(loss_if_stopped, budget, places=6)

    def test_wide_stop_shrinks_size_rather_than_raising_risk(self):
        tight = self.risk.review(proposal(invalidation=99.0), bar_index=100)
        wide = self.risk.review(proposal(invalidation=90.0), bar_index=100)
        self.assertLess(wide.qty, tight.qty)
        for d, stop in ((tight, 99.0), (wide, 90.0)):
            self.assertLessEqual(d.qty * (100.0 - stop),
                                 self.broker.equity * MAX_RISK_PER_TRADE + 1e-6)

    def test_exposure_cap_binds_when_the_stop_is_very_tight(self):
        """A near stop would otherwise imply an enormous notional."""
        d = self.risk.review(proposal(invalidation=99.8), bar_index=100)
        self.assertTrue(d.approved)
        notional = d.qty * 100.0
        self.assertLessEqual(notional, self.broker.equity * MAX_EXPOSURE + 1e-6)
        self.assertTrue(any("exposure limit" in r for r in d.reasons))

    def test_rejects_stop_inside_the_noise_band(self):
        d = self.risk.review(proposal(invalidation=99.95), bar_index=100)
        self.assertFalse(d.approved)
        self.assertIn("noise band", d.reasons[0])

    def test_rejects_below_confidence_floor(self):
        d = self.risk.review(proposal(confidence=MIN_CONFIDENCE - 0.01), bar_index=100)
        self.assertFalse(d.approved)
        self.assertIn("confidence", d.reasons[0])

    def test_rejects_a_second_concurrent_position(self):
        self.broker.open_position(0, "long", 10.0, 100.0, 1.0)
        d = self.risk.review(proposal(), bar_index=100)
        self.assertFalse(d.approved)
        self.assertIn("already open", d.reasons[0])


class RiskStateTransitions(unittest.TestCase):
    def setUp(self):
        self.broker = PaperBroker(starting_cash=100_000.0)
        self.broker.mark(100.0)
        self.risk = RiskEngine(self.broker)

    def test_daily_loss_limit_halts_the_session(self):
        self.broker.cash = 100_000.0 * (1 - MAX_DAILY_LOSS) - 1
        d = self.risk.review(proposal(), bar_index=100)
        self.assertFalse(d.approved)
        self.assertTrue(self.risk.halted)
        self.assertIn("daily loss", d.reasons[0])

    def test_halt_is_not_cleared_by_a_later_proposal(self):
        self.broker.cash = 100_000.0 * (1 - MAX_DAILY_LOSS) - 1
        self.risk.review(proposal(), bar_index=100)
        self.broker.cash = 100_000.0          # equity recovers within the session
        d = self.risk.review(proposal(), bar_index=101)
        self.assertFalse(d.approved, "a halted session must stay halted")

    def test_new_session_clears_the_halt_and_rebases_the_limit(self):
        self.broker.cash = 100_000.0 * (1 - MAX_DAILY_LOSS) - 1
        self.risk.review(proposal(), bar_index=100)
        self.risk.new_session()
        self.assertFalse(self.risk.halted)
        self.assertTrue(self.risk.review(proposal(), bar_index=101).approved)

    def test_consecutive_losses_trigger_a_cooldown(self):
        for i in range(MAX_CONSECUTIVE_LOSSES):
            self.risk.record_trade_result(-10.0, bar_index=100 + i)
        d = self.risk.review(proposal(), bar_index=103)
        self.assertFalse(d.approved)
        self.assertIn("cooldown", d.reasons[0])

    def test_a_win_resets_the_loss_streak(self):
        self.risk.record_trade_result(-10.0, bar_index=100)
        self.risk.record_trade_result(-10.0, bar_index=101)
        self.risk.record_trade_result(+10.0, bar_index=102)
        self.assertEqual(self.risk.consecutive_losses, 0)
        self.assertTrue(self.risk.review(proposal(), bar_index=103).approved)

    def test_no_override_path_exists_on_the_public_surface(self):
        """The veto must not be bypassable through the engine's own API."""
        self.broker.cash = 100_000.0 * (1 - MAX_DAILY_LOSS) - 1
        self.risk.review(proposal(), bar_index=100)
        public = [a for a in dir(self.risk) if not a.startswith("_")]
        for name in public:
            self.assertNotIn("override", name.lower())
            self.assertNotIn("force", name.lower())
            self.assertNotIn("bypass", name.lower())
        # even maximum confidence does not move it
        d = self.risk.review(proposal(confidence=1.0), bar_index=100)
        self.assertFalse(d.approved)


if __name__ == "__main__":
    unittest.main()
