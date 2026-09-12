"""Risk engine: hard limits enforced in code, never by model output.

IMPLEMENTED. Every proposed trade passes through RiskEngine.review(); the
engine's veto is final and logged. "No trade" is a valid, tracked outcome.

Limits come in two shapes and the engine takes whichever is tighter:
  * percentages of equity (the production defaults below), and
  * absolute dollar caps (`risk_usd`, `daily_loss_usd`) for a small pilot
    account, where 0.5% of $100 would be fifty cents and fees would swamp it.
"""

from __future__ import annotations

from dataclasses import dataclass


# Binding production limits (per project spec: enforced by code, not by AI judgement)
MAX_RISK_PER_TRADE = 0.005     # 0.5% of equity at the invalidation level
MAX_DAILY_LOSS = 0.02          # 2%, halt for the session when breached
MAX_EXPOSURE = 0.25            # notional exposure <= 25% of equity
MAX_CONSECUTIVE_LOSSES = 3     # cooldown after 3 straight losers
COOLDOWN_BARS = 12
MIN_CONFIDENCE = 0.55          # committee confidence floor
MIN_STOP_DISTANCE_PCT = 0.002  # refuse stops tighter than 0.2% (noise)


@dataclass(frozen=True)
class RiskLimits:
    max_risk_per_trade: float = MAX_RISK_PER_TRADE
    max_daily_loss: float = MAX_DAILY_LOSS
    max_exposure: float = MAX_EXPOSURE
    max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES
    cooldown_bars: int = COOLDOWN_BARS
    min_confidence: float = MIN_CONFIDENCE
    min_stop_distance_pct: float = MIN_STOP_DISTANCE_PCT
    risk_usd: float | None = None        # absolute cap on $ at risk per trade
    daily_loss_usd: float | None = None  # absolute cap on $ lost per session

    def risk_capital(self, equity: float) -> float:
        cap = equity * self.max_risk_per_trade
        return min(cap, self.risk_usd) if self.risk_usd is not None else cap

    def daily_loss_limit(self, day_start_equity: float) -> float:
        """Dollars of session loss that trigger a halt (positive number)."""
        cap = day_start_equity * self.max_daily_loss
        return min(cap, self.daily_loss_usd) if self.daily_loss_usd is not None else cap


PRODUCTION = RiskLimits()

# A $100 desk: $1 at risk per trade, $3 per session, no leverage, one position.
PILOT_100 = RiskLimits(max_risk_per_trade=1.0, max_daily_loss=1.0, max_exposure=1.0,
                       min_confidence=0.50, risk_usd=1.0, daily_loss_usd=3.0)


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
    def __init__(self, broker, limits: RiskLimits = PRODUCTION):
        self.broker = broker
        self.limits = limits
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
            if self.consecutive_losses >= self.limits.max_consecutive_losses:
                self.cooldown_until_bar = bar_index + self.limits.cooldown_bars
        else:
            self.consecutive_losses = 0
        self._check_daily_loss()

    def _check_daily_loss(self):
        loss = self.day_start_equity - self.broker.equity
        limit = self.limits.daily_loss_limit(self.day_start_equity)
        if loss >= limit > 0:
            self.halted = True
            self.halt_reason = (f"daily loss ${loss:,.2f} breached limit "
                                f"${limit:,.2f}")

    # -- the gate --------------------------------------------------------------

    def review(self, p: TradeProposal, bar_index: int) -> RiskDecision:
        reasons: list[str] = []
        self._check_daily_loss()

        if self.halted:
            return RiskDecision(False, [f"VETO: {self.halt_reason}"])
        if bar_index < self.cooldown_until_bar:
            return RiskDecision(False, [
                f"VETO: cooldown after {self.limits.max_consecutive_losses} consecutive "
                f"losses (until bar {self.cooldown_until_bar})"])
        if self.broker.position_qty != 0:
            return RiskDecision(False, ["VETO: position already open, one at a time"])
        if p.confidence < self.limits.min_confidence:
            return RiskDecision(False, [
                f"VETO: committee confidence {p.confidence:.2f} below floor "
                f"{self.limits.min_confidence:.2f}"])

        stop_dist = abs(p.price - p.invalidation)
        if stop_dist < p.price * self.limits.min_stop_distance_pct:
            return RiskDecision(False, [
                f"VETO: stop distance {stop_dist:,.0f} inside noise band"])

        equity = self.broker.equity
        risk_capital = self.limits.risk_capital(equity)
        qty = risk_capital / stop_dist
        notional = qty * p.price
        max_notional = equity * self.limits.max_exposure
        if notional > max_notional:
            qty = max_notional / p.price
            reasons.append(f"size capped by exposure limit ({self.limits.max_exposure:.0%} of equity)")

        reasons.insert(0, (f"approved: risk ${risk_capital:,.2f} "
                           f"({risk_capital / equity:.2%} of equity), "
                           f"qty {qty:.6f}, stop {p.invalidation:,.0f}"))
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
            "limits_text": self.limits_text(),
            "limits": {
                "max_risk_per_trade": self.limits.max_risk_per_trade,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_exposure": self.limits.max_exposure,
                "max_consecutive_losses": self.limits.max_consecutive_losses,
                "risk_usd": self.limits.risk_usd,
                "daily_loss_usd": self.limits.daily_loss_usd,
            },
        }

    def limits_text(self) -> str:
        L = self.limits
        if L.risk_usd is not None:
            return (f"${L.risk_usd:,.0f}/trade, ${L.daily_loss_usd:,.0f}/day, "
                    f"no leverage, veto is final")
        return (f"≤{L.max_risk_per_trade:.1%}/trade, ≤{L.max_daily_loss:.0%}/day, "
                f"≤{L.max_exposure:.0%} exposure, veto is final")
