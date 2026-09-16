"""Venues. One interface, two implementations.

    ShadowVenue   fills on paper against the live mark price with a taker fee.
                  Sends nothing anywhere. Used until the desk is switched to
                  live, and always available for dry runs.
    UniswapVenue  (evm_venue.py) real swaps on Uniswap v3, Robinhood Chain,
                  from the desk wallet.

HERMES is the only caller of `open` / `close` / `flatten`. Nothing else in the
desk holds the wallet.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

# Default paper taker fee (0.045%), in the range of a DEX pool fee plus slippage.
TAKER_BPS = 4.5


@dataclass
class Position:
    side: str            # long | short
    qty: float           # base units (ETH)
    entry: float
    mark: float
    unrealized: float
    stop: float | None = None
    since_ts: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Fill:
    ts: int
    book: str
    side: str            # buy | sell
    qty: float
    price: float
    fee: float
    tx: str | None = None      # on-chain signature in live mode
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Closed:
    book: str
    open_ts: int
    close_ts: int
    side: str
    qty: float
    entry: float
    exit: float
    pnl: float           # after fees + slippage
    costs: float
    reason: str
    tx: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Venue:
    mode = "shadow"

    def mark_price(self) -> float: ...
    def equity(self, book: str) -> float: ...
    def position(self, book: str) -> Position | None: ...
    def open(self, book: str, side: str, qty: float, mark: float, stop: float, atr: float) -> Fill: ...
    def close(self, book: str, mark: float, atr: float, reason: str) -> Closed: ...
    def flatten_all(self, mark: float, atr: float, reason: str) -> list[Closed]: ...
    def snapshot(self) -> dict: ...
    def restore(self, snap: dict) -> None: ...


# ---------------------------------------------------------------- shadow

class ShadowVenue(Venue):
    """Paper fills against the live mark, flat taker fee, per-book equity."""

    mode = "shadow"

    def __init__(self, books: list[str], starting_cash: float, mark: float,
                 fee_bps: float = TAKER_BPS, slippage_k: float = 0.05):
        self.fee_bps = fee_bps
        self.slippage_k = slippage_k
        self._mark = mark
        self.cash = {b: starting_cash for b in books}
        self.pos: dict[str, Position | None] = {b: None for b in books}
        self.entry_fee: dict[str, float] = {b: 0.0 for b in books}
        self.fills: list[Fill] = []
        self.closed: list[Closed] = []

    def set_mark(self, mark: float):
        self._mark = mark
        for p in self.pos.values():
            if p:
                p.mark = mark
                p.unrealized = (mark - p.entry) * p.qty * (1 if p.side == "long" else -1)

    def mark_price(self) -> float:
        return self._mark

    def equity(self, book: str) -> float:
        p = self.pos[book]
        return self.cash[book] + (p.unrealized if p else 0.0)

    def position(self, book: str) -> Position | None:
        return self.pos[book]

    def _slip(self, mark: float, atr: float) -> float:
        """Slippage against the taker. `slippage_k = 0` disables it entirely."""
        if self.slippage_k <= 0:
            return 0.0
        return self.slippage_k * atr if atr > 0 else mark * 0.0002

    def open(self, book, side, qty, mark, stop, atr) -> Fill:
        assert self.pos[book] is None, f"{book}: one position at a time"
        px = mark + self._slip(mark, atr) if side == "long" else mark - self._slip(mark, atr)
        fee = qty * px * self.fee_bps / 10_000
        self.cash[book] -= fee
        self.entry_fee[book] = fee
        self.pos[book] = Position(side=side, qty=qty, entry=round(px, 2), mark=mark,
                                  unrealized=0.0, stop=stop, since_ts=int(time.time()))
        f = Fill(ts=int(time.time()), book=book, side="buy" if side == "long" else "sell",
                 qty=qty, price=round(px, 2), fee=round(fee, 4), note="shadow")
        self.fills.append(f)
        return f

    def close(self, book, mark, atr, reason) -> Closed:
        p = self.pos[book]
        assert p is not None, f"{book}: nothing to close"
        px = mark - self._slip(mark, atr) if p.side == "long" else mark + self._slip(mark, atr)
        fee = p.qty * px * self.fee_bps / 10_000
        gross = (px - p.entry) * p.qty * (1 if p.side == "long" else -1)
        self.cash[book] += gross - fee
        costs = self.entry_fee[book] + fee
        c = Closed(book=book, open_ts=p.since_ts, close_ts=int(time.time()), side=p.side,
                   qty=p.qty, entry=p.entry, exit=round(px, 2), pnl=round(gross - costs, 4),
                   costs=round(costs, 4), reason=reason)
        self.fills.append(Fill(ts=c.close_ts, book=book, side="sell" if p.side == "long" else "buy",
                               qty=p.qty, price=round(px, 2), fee=round(fee, 4), note="shadow"))
        self.closed.append(c)
        self.pos[book] = None
        self.entry_fee[book] = 0.0
        return c

    def flatten_all(self, mark, atr, reason) -> list[Closed]:
        return [self.close(b, mark, atr, reason) for b, p in list(self.pos.items()) if p]

    def snapshot(self) -> dict:
        return {"cash": self.cash, "entry_fee": self.entry_fee, "mark": self._mark,
                "pos": {b: (p.to_dict() if p else None) for b, p in self.pos.items()},
                "closed": [c.to_dict() for c in self.closed][-500:],
                "fills": [f.to_dict() for f in self.fills][-500:]}

    def restore(self, snap: dict) -> None:
        self.cash.update(snap.get("cash", {}))
        self.entry_fee.update(snap.get("entry_fee", {}))
        self._mark = snap.get("mark", self._mark)
        for b, p in snap.get("pos", {}).items():
            self.pos[b] = Position(**p) if p else None
        self.closed = [Closed(**c) for c in snap.get("closed", [])]
        self.fills = [Fill(**f) for f in snap.get("fills", [])]
