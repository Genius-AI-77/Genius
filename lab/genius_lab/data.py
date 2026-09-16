"""Market data layer.

IMPLEMENTED: synthetic regime-switching market generator (deterministic, seeded).
IMPLEMENTED: live ETH-USD data from Coinbase Exchange's public API, no key needed:
               • hourly candles, paged back far enough for a full 33-session run
               • the recent trade tape with aggressor side → real buy/sell delta
               • a level-2 order-book snapshot → real depth for the Order Flow agent
IMPLEMENTED: a recorder that persists every live fetch to lab/data/ so the
             archive of tape + depth grows with each run (depth is free live and
             expensive historically, every unrecorded day must later be bought).

All live fetches fail soft: they return None and the caller falls back to
synthetic data, and the run's metadata records exactly which inputs were real.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Candle:
    ts: int          # unix seconds, bar open
    open: float
    high: float
    low: float
    close: float
    volume: float    # total traded volume (base units)
    buy_volume: float
    sell_volume: float
    tape: bool = False   # True when buy/sell split comes from real trades

    @property
    def delta(self) -> float:
        """Order-flow delta: aggressive buy volume minus aggressive sell volume."""
        return self.buy_volume - self.sell_volume

    def to_dict(self) -> dict:
        d = asdict(self)
        d["delta"] = round(self.delta, 4)
        return d


@dataclass
class Trade:
    ts: float
    price: float
    size: float
    aggressor: str   # "buy" | "sell", the side that crossed the spread


@dataclass
class Book:
    """Aggregated level-2 snapshot, trimmed to a band around mid."""
    ts: int
    bids: list[tuple[float, float]]   # (price, size) best first
    asks: list[tuple[float, float]]
    band_pct: float

    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2 if self.bids and self.asks else 0.0

    @property
    def spread_bps(self) -> float:
        m = self.mid
        return (self.best_ask - self.best_bid) / m * 10_000 if m else 0.0

    def depth(self, pct: float) -> tuple[float, float]:
        """Total resting size within ±pct of mid: (bid_size, ask_size)."""
        m = self.mid
        lo, hi = m * (1 - pct), m * (1 + pct)
        b = sum(s for p, s in self.bids if p >= lo)
        a = sum(s for p, s in self.asks if p <= hi)
        return b, a

    def walls(self, n: int = 3) -> dict:
        """Largest single resting levels on each side, candidate absorption points."""
        return {
            "bids": sorted(self.bids, key=lambda x: -x[1])[:n],
            "asks": sorted(self.asks, key=lambda x: -x[1])[:n],
        }

    def to_dict(self) -> dict:
        return {"ts": self.ts, "bids": self.bids, "asks": self.asks,
                "band_pct": self.band_pct}


# --- Synthetic market -------------------------------------------------------

_REGIMES = [
    # (name, drift per bar, volatility per bar, mean bars in regime)
    ("uptrend", 0.0012, 0.006, 60),
    ("downtrend", -0.0011, 0.008, 45),
    ("chop", 0.0000, 0.004, 80),
    ("shakeout", -0.0004, 0.014, 18),
]


def synthetic_candles(n: int, seed: int = 33, start_price: float = 65_000.0,
                      start_ts: int = 1_756_684_800, bar_seconds: int = 3600) -> list[Candle]:
    """Deterministic regime-switching random walk with order-flow structure.

    Buy/sell split is correlated with the bar's return plus noise, and
    'absorption' bars (high volume, small range) are injected near regime turns
    so the Order Flow Analyst has something real to detect.
    """
    rng = random.Random(seed)
    candles: list[Candle] = []
    price = start_price
    regime_idx = 0
    bars_left = _REGIMES[regime_idx][3]

    for i in range(n):
        name, drift, vol, _ = _REGIMES[regime_idx]
        bars_left -= 1
        turning = bars_left <= 3

        r = rng.gauss(drift, vol)
        o = price
        c = price * (1 + r)
        wick = abs(rng.gauss(0, vol * 0.7)) * price
        h = max(o, c) + wick
        low = min(o, c) - abs(rng.gauss(0, vol * 0.7)) * price

        base_volume = rng.uniform(80, 160)
        if turning:
            base_volume *= rng.uniform(2.2, 3.5)
            mid = (o + c) / 2
            o, c = mid * (1 - vol * 0.15), mid * (1 + vol * 0.15)
            h = max(o, c) + wick * 0.3
            low = min(o, c) - wick * 0.3

        pressure = max(-0.9, min(0.9, (r / max(vol, 1e-9)) * 0.35 + rng.gauss(0, 0.15)))
        buy_share = 0.5 + pressure / 2
        buy_v = base_volume * buy_share
        sell_v = base_volume - buy_v

        candles.append(Candle(
            ts=start_ts + i * bar_seconds,
            open=round(o, 2), high=round(h, 2), low=round(low, 2), close=round(c, 2),
            volume=round(base_volume, 4),
            buy_volume=round(buy_v, 4), sell_volume=round(sell_v, 4),
        ))
        price = c

        if bars_left <= 0:
            regime_idx = rng.choice([j for j in range(len(_REGIMES)) if j != regime_idx])
            bars_left = max(8, int(rng.gauss(_REGIMES[regime_idx][3], 12)))

    return candles


# --- Live data: Coinbase Exchange public API --------------------------------

API = "https://api.exchange.coinbase.com"
_UA = {"User-Agent": "genius-lab/0.1"}
_MAX_CANDLES_PER_REQUEST = 300   # documented API cap
_RATE_SLEEP = 0.15               # public limit is ~10 req/s; stay well under


def _get(path: str, params: dict | None = None, timeout: float = 10.0):
    """GET → (headers, parsed JSON). Raises on any failure; callers catch."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.headers, json.loads(resp.read().decode())


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> float:
    """ISO-8601 → unix seconds. Coinbase emits up to nanosecond precision;
    fromisoformat (esp. on 3.9) accepts at most microseconds, so truncate."""
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, tail = s.split(".", 1)
        n = 0
        while n < len(tail) and tail[n].isdigit():
            n += 1
        frac, tz = tail[:n], tail[n:]
        s = f"{head}.{frac[:6].ljust(6, '0')}{tz}"
    return datetime.fromisoformat(s).timestamp()


def live_candles(product: str = "ETH-USD", granularity: int = 3600,
                 bars: int = 300) -> list[Candle] | None:
    """Fetch `bars` most-recent candles, paging back in API-cap-sized windows.

    Candles carry no buy/sell split; until apply_tape() overlays real trades,
    the split is estimated from close-vs-open direction and `tape` stays False.
    Returns None on any failure.
    """
    try:
        rows: dict[int, list] = {}
        end = time.time()
        window = granularity * _MAX_CANDLES_PER_REQUEST
        while len(rows) < bars:
            start = end - window
            _, raw = _get(f"/products/{product}/candles",
                          {"granularity": granularity, "start": _iso(start),
                           "end": _iso(end)})
            if not isinstance(raw, list) or not raw:
                break
            for r in raw:
                rows[int(r[0])] = r
            end = start
            time.sleep(_RATE_SLEEP)
    except Exception:
        return None
    if not rows:
        return None

    candles: list[Candle] = []
    for ts in sorted(rows)[-bars:]:
        _, low, high, o, c, v = rows[ts][:6]
        o, c, low, high, v = float(o), float(c), float(low), float(high), float(v)
        direction = 1.0 if c >= o else -1.0
        rng = max(1e-9, high - low)
        strength = 0.5 + 0.25 * direction * min(1.0, abs(c - o) / rng)
        candles.append(Candle(ts=ts, open=o, high=high, low=low, close=c, volume=v,
                              buy_volume=v * strength, sell_volume=v * (1 - strength)))
    return candles


def trade_from_row(r: dict) -> Trade:
    """Coinbase trade row → Trade. `side` is the MAKER's side, so the aggressor
    is the opposite: side="buy" means a resting bid was hit → aggressor sold."""
    return Trade(ts=_parse_iso(r["time"]), price=float(r["price"]),
                 size=float(r["size"]),
                 aggressor="sell" if r["side"] == "buy" else "buy")


def live_trades(product: str = "ETH-USD", span_hours: float = 6.0,
                max_pages: int = 80, per_page: int = 1000) -> list[Trade] | None:
    """Fetch the recent trade tape, paging back via `cb-after` until it spans
    `span_hours` (or max_pages). ETH-USD prints several hundred trades every 5 to 10 min,
    so covering the last few hourly bars takes tens of pages, fine for a
    daily run, and every page lands in the recorder.

    Aggressor mapping, this is the detail that gets order-flow wrong if
    misread: Coinbase's `side` is the MAKER's side. A trade with side="buy"
    means a resting buy order was hit, i.e. the aggressor SOLD. So:
        side == "buy"  → aggressor = "sell"
        side == "sell" → aggressor = "buy"
    """
    trades: list[Trade] = []
    after: str | None = None
    newest: float | None = None
    try:
        for _ in range(max_pages):
            params = {"limit": per_page}
            if after:
                params["after"] = after
            headers, raw = _get(f"/products/{product}/trades", params)
            if not isinstance(raw, list) or not raw:
                break
            trades.extend(trade_from_row(r) for r in raw)
            newest = newest or trades[0].ts
            if newest - trades[-1].ts >= span_hours * 3600:
                break
            after = headers.get("cb-after")
            if not after:
                break
            time.sleep(_RATE_SLEEP)
    except Exception:
        if not trades:
            return None
    return trades or None


def apply_tape(candles: list[Candle], trades: list[Trade],
               bar_seconds: int = 3600) -> int:
    """Overlay real aggressor volumes onto the bars the tape fully covers.

    The candle's total volume stays authoritative (it is the exchange's own
    figure); the tape supplies the buy/sell *share*. A bar is marked `tape=True`
    only when the oldest trade we hold predates the bar's open, a partially
    covered bar would report a delta that is silently wrong.
    Returns the number of bars upgraded to real tape data.
    """
    if not trades:
        return 0
    oldest = min(t.ts for t in trades)
    by_bar: dict[int, list[float]] = {}
    for t in trades:
        bar = int(t.ts // bar_seconds) * bar_seconds
        acc = by_bar.setdefault(bar, [0.0, 0.0])
        acc[0 if t.aggressor == "buy" else 1] += t.size

    upgraded = 0
    for c in candles:
        if c.ts < oldest or c.ts not in by_bar:
            continue
        buy, sell = by_bar[c.ts]
        total = buy + sell
        if total <= 0:
            continue
        share = buy / total
        c.buy_volume = c.volume * share
        c.sell_volume = c.volume * (1 - share)
        c.tape = True
        upgraded += 1
    return upgraded


def live_book(product: str = "ETH-USD", band_pct: float = 0.02) -> Book | None:
    """Level-2 aggregated book, trimmed to ±band_pct of mid.

    The endpoint returns the whole book (tens of thousands of levels); depth
    that far from price is not actionable, so we keep the band the Order Flow
    agent actually reasons about.
    """
    try:
        _, raw = _get(f"/products/{product}/book", {"level": 2})
        bids = [(float(p), float(s)) for p, s, *_ in raw["bids"]]
        asks = [(float(p), float(s)) for p, s, *_ in raw["asks"]]
        ts = int(_parse_iso(raw["time"])) if raw.get("time") else int(time.time())
    except Exception:
        return None
    if not bids or not asks:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2
    lo, hi = mid * (1 - band_pct), mid * (1 + band_pct)
    return Book(ts=ts, bids=[b for b in bids if b[0] >= lo],
                asks=[a for a in asks if a[0] <= hi], band_pct=band_pct)


# --- Recorder ---------------------------------------------------------------

class Recorder:
    """Appends every live fetch to dated JSONL files under `root`.

    This is the cheapest option that expires: depth is free live and costs
    real money historically. Each run adds to the archive.
    """

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, kind: str, ts: float | None = None) -> str:
        day = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self.root, f"{kind}-{day}.jsonl")

    def _append(self, path: str, rows) -> int:
        n = 0
        with open(path, "a") as f:
            for r in rows:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
                n += 1
        return n

    def trades(self, trades: list[Trade]) -> int:
        """Records the tape, split into per-day files. Dedupes on re-run by ts+price+size."""
        seen = set()
        for p in {self._path("trades", t.ts) for t in trades}:
            if os.path.exists(p):
                with open(p) as f:
                    for line in f:
                        d = json.loads(line)
                        seen.add((d["ts"], d["p"], d["s"]))
        by_day: dict[str, list] = {}
        for t in sorted(trades, key=lambda t: t.ts):
            key = (round(t.ts, 6), t.price, t.size)
            if key in seen:
                continue
            seen.add(key)
            by_day.setdefault(self._path("trades", t.ts), []).append(
                {"ts": round(t.ts, 6), "p": t.price, "s": t.size, "a": t.aggressor})
        return sum(self._append(p, rows) for p, rows in by_day.items())

    def book(self, book: Book) -> int:
        return self._append(self._path("book", book.ts), [book.to_dict()])

    def candles(self, candles: list[Candle]) -> int:
        latest = candles[-1]
        return self._append(self._path("candles", latest.ts), [latest.to_dict()])


# --- Fundamental fixtures (SIMULATED fallback) ------------------------------

FUNDAMENTAL_FIXTURES = [
    # (bar_index_from, bias in [-1, 1], headline, source, date)
    (0,   0.2, "Spot ETF net inflows continue for a third week", "fixture:etf-flows", "2025-09-01"),
    (180, -0.5, "Macro: hotter-than-expected CPI print pressures risk assets", "fixture:cpi", "2025-09-08"),
    (320, 0.4, "Large exchange announces institutional custody expansion", "fixture:custody", "2025-09-14"),
    (520, -0.3, "Regulatory hearing scheduled; headline risk elevated", "fixture:hearing", "2025-09-22"),
    (700, 0.5, "Sovereign wealth fund discloses crypto allocation", "fixture:swf", "2025-09-29"),
]


def fundamental_bias(bar_index: int) -> tuple[float, list[dict]]:
    """Return the active simulated fundamental bias and its supporting events."""
    active = [f for f in FUNDAMENTAL_FIXTURES if f[0] <= bar_index]
    if not active:
        return 0.0, []
    recent = active[-2:]
    bias = sum(f[1] for f in recent) / len(recent)
    events = [{"headline": f[2], "source": f[3], "date": f[4], "bias": f[1]}
              for f in recent]
    return bias, events


@dataclass
class LiveBundle:
    """Everything one live fetch produced, plus provenance for the run metadata."""
    candles: list[Candle]
    trades: list[Trade] | None
    book: Book | None
    tape_bars: int = 0
    recorded: dict = field(default_factory=dict)

    def provenance(self) -> dict:
        return {
            "candles": len(self.candles),
            "trades": len(self.trades) if self.trades else 0,
            "tape_bars": self.tape_bars,
            "book_levels": (len(self.book.bids) + len(self.book.asks)) if self.book else 0,
            "book_ts": self.book.ts if self.book else None,
            "recorded": self.recorded,
        }


def fetch_live(product: str = "ETH-USD", bars: int = 300,
               record_dir: str | None = None) -> LiveBundle | None:
    """One-shot live fetch: candles + tape + book, tape overlaid, optionally recorded."""
    candles = live_candles(product, bars=bars)
    if not candles:
        return None
    trades = live_trades(product)
    book = live_book(product)
    bundle = LiveBundle(candles=candles, trades=trades, book=book)
    if trades:
        bundle.tape_bars = apply_tape(candles, trades)
    if record_dir:
        rec = Recorder(record_dir)
        bundle.recorded = {
            "trades": rec.trades(trades) if trades else 0,
            "book": rec.book(book) if book else 0,
            "candles": rec.candles(candles),
        }
    return bundle
