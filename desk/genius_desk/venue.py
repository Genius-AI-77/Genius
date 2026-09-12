"""Venues. One interface, two implementations.

    ShadowVenue  fills on paper against the live mark price with Drift's fee
                 schedule. Sends nothing anywhere. Used until the desk is
                 switched to live, and always available for dry runs.
    DriftVenue   Drift Protocol perpetuals on Solana. One sub-account per book
                 so the books never net against each other on-chain. Every
                 entry also places a reduce-only trigger order at the stop,
                 so a dead runner never leaves a position unprotected.

HERMES is the only caller of `open` / `close` / `flatten`. Nothing else in the
desk holds the wallet.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

# Drift taker fee, base tier. Rebates for makers exist but the desk takes.
DRIFT_TAKER_BPS = 10.0


@dataclass
class Position:
    side: str            # long | short
    qty: float           # base units (BTC)
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
    """Paper fills against the live mark, Drift fee model, per-book equity."""

    mode = "shadow"

    def __init__(self, books: list[str], starting_cash: float, mark: float,
                 fee_bps: float = DRIFT_TAKER_BPS, slippage_k: float = 0.05):
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


# ------------------------------------------------------------------ drift

class DriftVenue(Venue):
    """Drift Protocol adapter. Requires `driftpy` and a funded wallet.

    Imported lazily so the shadow desk has no dependency on it. Every public
    method is synchronous; driftpy is async, so calls run through one event
    loop owned by this object.

    Sub-accounts: book i trades on sub-account `sub_account[i]`. Each holds its
    own USDC collateral and positions, so books never net against each other.
    """

    mode = "live"

    def __init__(self, books: dict[str, int], market: str, rpc_url: str, wallet_key: str,
                 fee_bps: float = DRIFT_TAKER_BPS):
        import asyncio
        from driftpy.constants.perp_markets import mainnet_perp_market_configs
        from driftpy.drift_client import DriftClient
        from driftpy.keypair import load_keypair
        from solana.rpc.async_api import AsyncClient

        self.books = books
        self.fee_bps = fee_bps
        self.loop = asyncio.new_event_loop()
        cfg = next((m for m in mainnet_perp_market_configs if m.symbol == market), None)
        if cfg is None:
            raise ValueError(f"unknown Drift market {market!r}")
        self.market_index = cfg.market_index
        self.kp = load_keypair(wallet_key)           # base58 or JSON array
        self.client = DriftClient(AsyncClient(rpc_url), self.kp, "mainnet")
        self.loop.run_until_complete(self.client.subscribe())
        for sub in books.values():
            self.loop.run_until_complete(self.client.add_user(sub))
        self.fills: list[Fill] = []
        self.closed: list[Closed] = []
        self._open_meta: dict[str, dict] = {}         # book -> {entry, fee, since_ts, side, qty}

    # -- helpers -------------------------------------------------------------
    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    def mark_price(self) -> float:
        from driftpy.constants.numeric_constants import PRICE_PRECISION
        od = self.client.get_oracle_price_data_for_perp_market(self.market_index)
        return od.price / PRICE_PRECISION

    def equity(self, book: str) -> float:
        from driftpy.constants.numeric_constants import QUOTE_PRECISION
        user = self.client.get_user(self.books[book])
        return user.get_total_collateral() / QUOTE_PRECISION

    def position(self, book: str) -> Position | None:
        from driftpy.constants.numeric_constants import BASE_PRECISION, QUOTE_PRECISION
        pp = self.client.get_perp_position(self.market_index, self.books[book])
        if pp is None or pp.base_asset_amount == 0:
            return None
        qty = abs(pp.base_asset_amount) / BASE_PRECISION
        side = "long" if pp.base_asset_amount > 0 else "short"
        entry = abs(pp.quote_entry_amount) / QUOTE_PRECISION / qty if qty else 0.0
        mark = self.mark_price()
        unreal = (mark - entry) * qty * (1 if side == "long" else -1)
        meta = self._open_meta.get(book, {})
        return Position(side=side, qty=qty, entry=round(entry, 2), mark=mark,
                        unrealized=round(unreal, 4), stop=meta.get("stop"),
                        since_ts=meta.get("since_ts", 0))

    def _order(self, sub: int, direction: str, qty: float, reduce_only: bool,
               trigger: float | None = None, trigger_cond: str | None = None) -> str:
        from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
        from driftpy.types import (MarketType, OrderParams, OrderTriggerCondition,
                                   OrderType, PositionDirection)
        params = OrderParams(
            order_type=OrderType.TriggerMarket() if trigger else OrderType.Market(),
            base_asset_amount=int(round(qty * BASE_PRECISION)),
            market_index=self.market_index,
            direction=PositionDirection.Long() if direction == "long" else PositionDirection.Short(),
            market_type=MarketType.Perp(),
            reduce_only=reduce_only,
            trigger_price=int(round(trigger * PRICE_PRECISION)) if trigger else None,
            trigger_condition=(OrderTriggerCondition.Below() if trigger_cond == "below"
                               else OrderTriggerCondition.Above()),
        )
        sig = self._run(self.client.place_perp_order(params, sub))
        return str(sig)

    def _cancel_all(self, sub: int):
        from driftpy.types import MarketType
        try:
            self._run(self.client.cancel_orders(MarketType.Perp(), self.market_index, None, sub))
        except Exception:
            pass   # nothing open is fine

    # -- HERMES' three verbs ---------------------------------------------------
    def open(self, book, side, qty, mark, stop, atr) -> Fill:
        sub = self.books[book]
        tx = self._order(sub, side, qty, reduce_only=False)
        # exchange-side stop: reduce-only trigger market in the opposite direction
        self._order(sub, "short" if side == "long" else "long", qty, reduce_only=True,
                    trigger=stop, trigger_cond="below" if side == "long" else "above")
        fee = qty * mark * self.fee_bps / 10_000
        self._open_meta[book] = {"entry": mark, "fee": fee, "since_ts": int(time.time()),
                                 "side": side, "qty": qty, "stop": stop}
        f = Fill(ts=int(time.time()), book=book, side="buy" if side == "long" else "sell",
                 qty=qty, price=mark, fee=round(fee, 4), tx=tx, note="drift")
        self.fills.append(f)
        return f

    def close(self, book, mark, atr, reason) -> Closed:
        sub = self.books[book]
        p = self.position(book)
        assert p is not None, f"{book}: nothing to close"
        self._cancel_all(sub)
        tx = str(self._run(self.client.close_position(self.market_index, 0, sub)))
        fee = p.qty * mark * self.fee_bps / 10_000
        meta = self._open_meta.pop(book, {"fee": 0.0, "since_ts": p.since_ts})
        gross = (mark - p.entry) * p.qty * (1 if p.side == "long" else -1)
        costs = meta.get("fee", 0.0) + fee
        c = Closed(book=book, open_ts=meta.get("since_ts", 0), close_ts=int(time.time()),
                   side=p.side, qty=p.qty, entry=p.entry, exit=mark,
                   pnl=round(gross - costs, 4), costs=round(costs, 4), reason=reason, tx=tx)
        self.fills.append(Fill(ts=c.close_ts, book=book, side="sell" if p.side == "long" else "buy",
                               qty=p.qty, price=mark, fee=round(fee, 4), tx=tx, note="drift"))
        self.closed.append(c)
        return c

    def flatten_all(self, mark, atr, reason) -> list[Closed]:
        out = []
        for b in self.books:
            self._cancel_all(self.books[b])
            if self.position(b):
                out.append(self.close(b, mark, atr, reason))
        return out

    def snapshot(self) -> dict:
        return {"open_meta": self._open_meta,
                "closed": [c.to_dict() for c in self.closed][-500:],
                "fills": [f.to_dict() for f in self.fills][-500:]}

    def restore(self, snap: dict) -> None:
        self._open_meta = snap.get("open_meta", {})
        self.closed = [Closed(**c) for c in snap.get("closed", [])]
        self.fills = [Fill(**f) for f in snap.get("fills", [])]
