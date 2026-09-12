"""Venues. One interface, two implementations.

    ShadowVenue  fills on paper against the live mark price with Hyperliquid's fee
                 schedule. Sends nothing anywhere. Used until the desk is
                 switched to live, and always available for dry runs.
    HyperliquidVenue  Hyperliquid perpetuals. One sub-account per book so the
                 books never net against each other. Every entry also places a
                 reduce-only stop order on the exchange, so a dead runner never
                 leaves a position unprotected. The desk holds only an agent
                 key, which can trade but cannot withdraw.

HERMES is the only caller of `open` / `close` / `flatten`. Nothing else in the
desk holds the wallet.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

# Hyperliquid taker fee, base tier (0.045%). Makers get rebates; the desk takes.
TAKER_BPS = 4.5


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
    """Paper fills against the live mark, Hyperliquid fee model, per-book equity."""

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


# ------------------------------------------------------------ hyperliquid

def _px5(px: float) -> float:
    """Hyperliquid prices: at most 5 significant figures, at most 6 decimals."""
    return round(float(f"{px:.5g}"), 6)


class HyperliquidVenue(Venue):
    """Hyperliquid perpetuals adapter (official `hyperliquid-python-sdk`).

    Identity model (this is the security design, read it once):
      * `account_address`  the master wallet's PUBLIC address. Holds the funds.
      * `agent_key`        the private key of an API/agent wallet the master
                           approved in the Hyperliquid UI. It can TRADE for the
                           master and its sub-accounts. It CANNOT withdraw.
                           This is the only key the desk ever holds.
      * one sub-account per book, addressed through `vault_address`, so the
        books never net against each other.

    Every entry also places a reduce-only stop-loss trigger on the exchange.
    """

    mode = "live"

    def __init__(self, books: dict[str, str], account_address: str, agent_key: str,
                 coin: str = "BTC", testnet: bool = False, fee_bps: float = 4.5):
        from eth_account import Account
        from hyperliquid.exchange import Exchange
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        self.books = books                      # book name -> sub-account address
        self.coin = coin
        self.fee_bps = fee_bps                  # taker, base tier
        self.account = account_address
        self.base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        self.info = Info(self.base_url, skip_ws=True)
        wallet = Account.from_key(agent_key)
        self.agent_address = wallet.address
        # one Exchange per book, each acting on its sub-account (vault_address)
        self.ex = {b: Exchange(wallet, self.base_url,
                               vault_address=(None if addr.lower() == account_address.lower() else addr),
                               account_address=account_address)
                   for b, addr in books.items()}
        meta = self.info.meta()
        asset = next(a for a in meta["universe"] if a["name"] == coin)
        self.sz_decimals = int(asset["szDecimals"])
        self.fills: list[Fill] = []
        self.closed: list[Closed] = []
        self._open_meta: dict[str, dict] = {}

    # -- reads -----------------------------------------------------------------
    def mark_price(self) -> float:
        return float(self.info.all_mids()[self.coin])

    def _state(self, book: str) -> dict:
        return self.info.user_state(self.books[book])

    def equity(self, book: str) -> float:
        return float(self._state(book)["marginSummary"]["accountValue"])

    def position(self, book: str) -> Position | None:
        for ap in self._state(book).get("assetPositions", []):
            p = ap["position"]
            if p["coin"] != self.coin:
                continue
            szi = float(p["szi"])
            if szi == 0:
                continue
            side = "long" if szi > 0 else "short"
            entry = float(p.get("entryPx") or 0)
            meta = self._open_meta.get(book, {})
            return Position(side=side, qty=abs(szi), entry=entry, mark=self.mark_price(),
                            unrealized=float(p.get("unrealizedPnl") or 0),
                            stop=meta.get("stop"), since_ts=meta.get("since_ts", 0))
        return None

    def _sz(self, qty: float) -> float:
        return round(qty, self.sz_decimals)

    @staticmethod
    def _fill_of(resp: dict) -> tuple[float, float, str]:
        """(filled size, avg price, oid) from an order response, or raise."""
        if resp.get("status") != "ok":
            raise RuntimeError(f"venue rejected: {resp}")
        st = resp["response"]["data"]["statuses"][0]
        if "error" in st:
            raise RuntimeError(f"venue error: {st['error']}")
        if "filled" in st:
            f = st["filled"]
            return float(f["totalSz"]), float(f["avgPx"]), str(f["oid"])
        return 0.0, 0.0, str(st.get("resting", {}).get("oid", ""))

    def _last_fill_hash(self, book: str) -> str | None:
        try:
            fills = self.info.user_fills(self.books[book])
            return fills[0].get("hash") if fills else None
        except Exception:
            return None

    # -- HERMES' three verbs ---------------------------------------------------
    def open(self, book, side, qty, mark, stop, atr) -> Fill:
        ex = self.ex[book]
        sz = self._sz(qty)
        filled, px, oid = self._fill_of(ex.market_open(self.coin, side == "long", sz, None, 0.01))
        if filled <= 0:
            raise RuntimeError("market order did not fill")
        # exchange-side stop: reduce-only trigger, opposite direction
        trig = _px5(stop)
        ex.order(self.coin, side != "long", filled, trig,
                 {"trigger": {"triggerPx": trig, "isMarket": True, "tpsl": "sl"}}, reduce_only=True)
        fee = filled * px * self.fee_bps / 10_000
        self._open_meta[book] = {"entry": px, "fee": fee, "since_ts": int(time.time()),
                                 "side": side, "qty": filled, "stop": stop}
        f = Fill(ts=int(time.time()), book=book, side="buy" if side == "long" else "sell",
                 qty=filled, price=px, fee=round(fee, 4), tx=self._last_fill_hash(book), note="hyperliquid")
        self.fills.append(f)
        return f

    def _cancel_all(self, book: str):
        try:
            for o in self.info.open_orders(self.books[book]):
                if o.get("coin") == self.coin:
                    self.ex[book].cancel(self.coin, o["oid"])
        except Exception:
            pass

    def close(self, book, mark, atr, reason) -> Closed:
        p = self.position(book)
        assert p is not None, f"{book}: nothing to close"
        self._cancel_all(book)
        filled, px, oid = self._fill_of(self.ex[book].market_close(self.coin, None, None, 0.01))
        px = px or mark
        fee = p.qty * px * self.fee_bps / 10_000
        meta = self._open_meta.pop(book, {"fee": 0.0, "since_ts": p.since_ts})
        gross = (px - p.entry) * p.qty * (1 if p.side == "long" else -1)
        costs = meta.get("fee", 0.0) + fee
        tx = self._last_fill_hash(book)
        c = Closed(book=book, open_ts=meta.get("since_ts", 0), close_ts=int(time.time()),
                   side=p.side, qty=p.qty, entry=p.entry, exit=px,
                   pnl=round(gross - costs, 4), costs=round(costs, 4), reason=reason, tx=tx)
        self.fills.append(Fill(ts=c.close_ts, book=book, side="sell" if p.side == "long" else "buy",
                               qty=p.qty, price=px, fee=round(fee, 4), tx=tx, note="hyperliquid"))
        self.closed.append(c)
        return c

    def flatten_all(self, mark, atr, reason) -> list[Closed]:
        out = []
        for b in self.books:
            self._cancel_all(b)
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
