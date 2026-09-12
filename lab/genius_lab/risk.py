"""Risk engine — hard limits enforced in code, never by model output.

IMPLEMENTED. Every proposed trade passes through RiskEngine.review(); the
engine's veto is final and logged. "No trade" is a valid, tracked outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


# Binding limits (per project spec: enforced by code, not by AI judgement)
MAX_RISK_PER_TRADE = 0.005     # 0.5% of equity at the invalidation level
MAX_DAILY_LOSS = 0.02          # 2% — halt for the session when breached
MAX_EXPOSURE = 0.25            # notional exposure ≤ 25% of equity
MAX_CONSECUTIVE_LOSSES = 3     # cooldown after 3 straight losers
COOLDOWN_BARS = 12
MIN_CONFIDENCE = 0.55          # committee confidence floor
MIN_STOP_DISTANCE_PCT = 0.002  # refuse stops tighter than 0.2% (noise)


@dataclass
class TradeProposal:
    side: str                  # long | short
    price: float
    invalidation: float        # stop level
    confidence: float
    thesis: str


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str]
    qty: float = 0.0
    stop: float | None = None


class RiskEngine:
    def __init__(self, broker):
        self.broker = broker
        self.day_start_equity = broker.equity
        self.consecutive_losses = 0
        self.cooldown_until_bar = -1
        self.halted = False
        self.halt_reason = ""

    # -- state transitions ----------------------------------------------------

    def new_session(self):
        self.day_start_equity = self.broker.equity
        self.halted = False
        self.halt_reason = ""

    def record_trade_result(self, pnl: float, bar_index: int):
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                self.cooldown_until_bar = bar_index + COOLDOWN_BARS
        else:
            self.consecutive_losses = 0
        self._check_daily_loss()

    def _check_daily_loss(self):
        dd = (self.broker.equity - self.day_start_equity) / self.day_start_equity
        if dd <= -MAX_DAILY_LOSS:
            self.halted = True
            self.halt_reason = (f"daily loss {dd:.2%} breached limit "
                                f"{-MAX_DAILY_LOSS:.0%}")

    # -- the gate --------------------------------------------------------------

    def review(self, p: TradeProposal, bar_index: int) -> RiskDecision:
        reasons: list[str] = []
        self._check_daily_loss()

        if self.halted:
            return RiskDecision(False, [f"VETO: {self.halt_reason}"])
        if bar_index < self.cooldown_until_bar:
            return RiskDecision(False, [
                f"VETO: cooldown after {MAX_CONSECUTIVE_LOSSES} consecutive "
                f"losses (until bar {self.cooldown_until_bar})"])
        if self.broker.position_qty != 0:
            return RiskDecision(False, ["VETO: position already open — one at a time"])
        if p.confidence < MIN_CONFIDENCE:
            return RiskDecision(False, [
                f"VETO: committee confidence {p.confidence:.2f} below floor "
                f"{MIN_CONFIDENCE:.2f}"])

        stop_dist = abs(p.price - p.invalidation)
        if stop_dist < p.price * MIN_STOP_DISTANCE_PCT:
            return RiskDecision(False, [
                f"VETO: stop distance {stop_dist:,.0f} inside noise band"])

        equity = self.broker.equity
        risk_capital = equity * MAX_RISK_PER_TRADE
        qty = risk_capital / stop_dist
        notional = qty * p.price
        max_notional = equity * MAX_EXPOSURE
        if notional > max_notional:
            qty = max_notional / p.price
            reasons.append(f"size capped by exposure limit ({MAX_EXPOSURE:.0%} of equity)")

        reasons.insert(0, (f"approved: risk ${risk_capital:,.0f} "
                           f"({MAX_RISK_PER_TRADE:.1%} of equity), "
                           f"qty {qty:.5f}, stop {p.invalidation:,.0f}"))
        return RiskDecision(True, reasons, qty=qty, stop=p.invalidation)

    # -- reporting -------------------------------------------------------------

    def state_summary(self) -> dict:
        day_pnl = (self.broker.equity - self.day_start_equity) / self.day_start_equity
        return {
            "equity": round(self.broker.equity, 2),
            "day_pnl_pct": round(day_pnl * 100, 3),
            "consecutive_losses": self.consecutive_losses,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "limits_text": (f"≤{MAX_RISK_PER_TRADE:.1%}/trade, "
                            f"≤{MAX_DAILY_LOSS:.0%}/day, "
                            f"≤{MAX_EXPOSURE:.0%} exposure, veto is final"),
            "limits": {
                "max_risk_per_trade": MAX_RISK_PER_TRADE,
                "max_daily_loss": MAX_DAILY_LOSS,
                "max_exposure": MAX_EXPOSURE,
                "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,
            },
        }
