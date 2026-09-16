"""Paper broker, execution mechanics with realistic costs.

IMPLEMENTED (paper only). Live execution is BLOCKED pending: venue decision,
API keys, trading capital, and jurisdiction/compliance review.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Fill:
    ts: int
    side: str            # buy | sell
    qty: float
    ask_price: float     # decision price
    fill_price: float    # after slippage
    fee: float


@dataclass
class ClosedTrade:
    open_ts: int
    close_ts: int
    side: str            # long | short
    qty: float
    entry: float
    exit: float
    pnl: float           # after fees + slippage
    costs: float
    reason: str


class PaperBroker:
    """Single-instrument paper broker. Fees and slippage are charged on every
    fill so all reported performance is after costs."""

    def __init__(self, starting_cash: float = 100_000.0, fee_bps: float = 8.0,
                 slippage_k: float = 0.05):
        self.cash = starting_cash
        self.fee_bps = fee_bps
        self.slippage_k = slippage_k   # fraction of ATR paid as slippage
        self.position_qty = 0.0        # signed: + long, - short
        self.entry_price = 0.0
        self.entry_ts = 0
        self.entry_costs = 0.0
        self.last_price = 0.0
        self.fills: list[Fill] = []
        self.closed: list[ClosedTrade] = []

    # -- valuation -------------------------------------------------------------

    @property
    def equity(self) -> float:
        unrealized = self.position_qty * (self.last_price - self.entry_price)
        return self.cash + unrealized

    def mark(self, price: float):
        self.last_price = price

    # -- cost model ------------------------------------------------------------

    def estimate_slippage(self, price: float, atr_value: float) -> float:
        """Slippage paid on every fill, as a price offset against the taker.

        Scales with volatility. When ATR is unavailable (early bars) it falls
        back to a flat 2 bps of price. `slippage_k = 0` disables the model
        entirely, used by tests to isolate fee accounting.
        """
        if self.slippage_k <= 0:
            return 0.0
        if atr_value > 0:
            return self.slippage_k * atr_value
        return price * 0.0002

    def _fill(self, ts: int, side: str, qty: float, price: float,
              atr_value: float) -> Fill:
        slip = self.estimate_slippage(price, atr_value)
        fill_price = price + slip if side == "buy" else price - slip
        fee = abs(qty) * fill_price * self.fee_bps / 10_000
        f = Fill(ts=ts, side=side, qty=qty, ask_price=price,
                 fill_price=round(fill_price, 2), fee=round(fee, 2))
        self.fills.append(f)
        return f

    # -- orders ----------------------------------------------------------------

    def open_position(self, ts: int, side: str, qty: float, price: float,
                      atr_value: float):
        assert self.position_qty == 0, "one position at a time"
        f = self._fill(ts, "buy" if side == "long" else "sell", qty, price, atr_value)
        self.position_qty = qty if side == "long" else -qty
        self.entry_price = f.fill_price
        self.entry_ts = ts
        self.entry_costs = f.fee
        self.cash -= f.fee

    def close_position(self, ts: int, price: float, atr_value: float,
                       reason: str) -> ClosedTrade:
        assert self.position_qty != 0, "no position to close"
        side = "long" if self.position_qty > 0 else "short"
        qty = abs(self.position_qty)
        f = self._fill(ts, "sell" if side == "long" else "buy", qty, price, atr_value)
        direction = 1 if side == "long" else -1
        gross = direction * qty * (f.fill_price - self.entry_price)
        costs = self.entry_costs + f.fee
        pnl = gross - f.fee  # entry fee already deducted from cash at open
        self.cash += pnl
        trade = ClosedTrade(open_ts=self.entry_ts, close_ts=ts, side=side,
                            qty=round(qty, 6), entry=self.entry_price,
                            exit=f.fill_price, pnl=round(gross - costs, 2),
                            costs=round(costs, 2), reason=reason)
        self.closed.append(trade)
        self.position_qty = 0.0
        self.entry_price = 0.0
        self.entry_costs = 0.0
        return trade
