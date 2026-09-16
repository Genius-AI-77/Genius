"""The six agent roles.

IMPLEMENTED as deterministic rule-based analysts so the pipeline is testable,
reproducible and free to run. Each agent exposes the same contract:

    report = agent.analyze(context) -> AgentReport

An optional LLM hook (`narrator`) can later wrap each report with a natural-
language rationale (PLANNED, the numbers and limits never come from the LLM;
the LLM only interprets, per the project's "math is enforced by code" rule).

Stances: "long" | "short" | "flat". "flat" (no trade) is a first-class output.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .data import Candle, fundamental_bias


@dataclass
class AgentReport:
    agent: str
    role: str
    stance: str                 # long | short | flat
    confidence: float           # 0..1
    findings: list[str]
    invalidation: float | None = None   # price level that voids the thesis
    data: dict = field(default_factory=dict)
    status: str = "IMPLEMENTED"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = round(self.confidence, 3)
        return d


@dataclass
class MarketContext:
    candles: list[Candle]       # history up to and including "now"
    bar_index: int              # index of the current bar in the full series
    news: object | None = None  # NewsBias, real headlines, time-gated (or None → fixtures)
    book: object | None = None  # Book, live depth snapshot; only valid for the latest bar

    @property
    def now(self) -> Candle:
        return self.candles[-1]


# --- helpers ----------------------------------------------------------------

def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for prev, cur in zip(closes[-period - 1:-1], closes[-period:]):
        change = cur - prev
        if change >= 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - 100 / (1 + rs)


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs = []
    for prev, cur in zip(candles[-period - 1:-1], candles[-period:]):
        trs.append(max(cur.high - cur.low,
                       abs(cur.high - prev.close),
                       abs(cur.low - prev.close)))
    return sum(trs) / period


# --- 1. Fundamental Analyst --------------------------------------------------

class FundamentalAnalyst:
    """Inputs: headlines with source + timestamp, live RSS when the context
    carries a NewsBias (IMPLEMENTED, lexicon-scored, time-gated), fixtures
    otherwise (SIMULATED). Output: directional bias with the events behind it.
    Evaluation: was the bias directionally consistent with forward returns?
    """

    name = "ATLAS"
    role = "Fundamental Analyst"

    def analyze(self, ctx: MarketContext) -> AgentReport:
        if ctx.news is not None:
            bias, events = ctx.news.bias_at(ctx.now.ts)
            status = "IMPLEMENTED"
        else:
            bias, events = fundamental_bias(ctx.bar_index)
            status = "SIMULATED"
        stance = "long" if bias > 0.15 else "short" if bias < -0.15 else "flat"
        findings = []
        for e in events:
            line = f"[{e['date']}] {e['headline']} (source: {e['source']}, bias {e['bias']:+.1f})"
            if e.get("matched"):
                line += f" (terms: {', '.join(e['matched'])})"
            findings.append(line)
        if not findings:
            findings = ["No directional headlines in the lookback window."]
        if status == "IMPLEMENTED":
            findings.append("Scoring: keyword lexicon, time-gated to headlines "
                            "published before this bar. LLM reading is PLANNED.")
        return AgentReport(
            agent=self.name, role=self.role, stance=stance,
            confidence=min(1.0, abs(bias)) * 0.8,
            findings=findings, data={"bias": round(bias, 3), "events": events},
            status=status,
        )


# --- 2. Technical Analyst ----------------------------------------------------

class TechnicalAnalyst:
    """Inputs: OHLCV history. Output: trend structure, levels, invalidation."""

    name = "EUCLID"
    role = "Technical Analyst"

    def analyze(self, ctx: MarketContext) -> AgentReport:
        closes = [c.close for c in ctx.candles]
        price = closes[-1]
        s20, s50 = sma(closes, 20), sma(closes, 50)
        r = rsi(closes)
        lookback = ctx.candles[-20:]
        swing_high = max(c.high for c in lookback)
        swing_low = min(c.low for c in lookback)

        findings, stance, confidence, invalidation = [], "flat", 0.2, None
        if s20 is None or s50 is None or r is None:
            findings.append("Insufficient history for trend classification.")
        elif price > s20 > s50 and r < 72:
            stance, confidence, invalidation = "long", 0.65, swing_low
            findings += [f"Uptrend: price {price:,.0f} > SMA20 {s20:,.0f} > SMA50 {s50:,.0f}.",
                         f"RSI {r:.0f} not overbought.",
                         f"Invalidation: close below swing low {swing_low:,.0f}."]
        elif price < s20 < s50 and r > 28:
            stance, confidence, invalidation = "short", 0.65, swing_high
            findings += [f"Downtrend: price {price:,.0f} < SMA20 {s20:,.0f} < SMA50 {s50:,.0f}.",
                         f"RSI {r:.0f} not oversold.",
                         f"Invalidation: close above swing high {swing_high:,.0f}."]
        else:
            findings.append("No aligned trend structure, range conditions. Stand aside.")
            if r is not None:
                findings.append(f"RSI {r:.0f}; SMA20/50 mixed.")

        return AgentReport(
            agent=self.name, role=self.role, stance=stance, confidence=confidence,
            findings=findings, invalidation=invalidation,
            data={"sma20": s20, "sma50": s50, "rsi": r,
                  "swing_high": swing_high, "swing_low": swing_low},
        )


# --- 3. Order Flow Analyst ---------------------------------------------------

class OrderFlowAnalyst:
    """Inputs: per-bar buy/sell volume (real tape where `Candle.tape` is True,
    direction-estimated otherwise) and, on the latest bar, a live level-2 book.
    Output: delta trend, volume point of control, absorption candidates, and
    resting-depth imbalance / walls when depth is available.
    """

    name = "FLUX"
    role = "Order Flow Analyst"

    def analyze(self, ctx: MarketContext) -> AgentReport:
        window = ctx.candles[-20:]
        cum_delta = sum(c.delta for c in window)
        recent_delta = sum(c.delta for c in window[-5:])
        avg_vol = sum(c.volume for c in ctx.candles[-60:]) / min(60, len(ctx.candles))

        # volume-by-price over the last 60 bars → point of control
        profile: dict[float, float] = {}
        step = max(0.01, ctx.now.close * 0.0035)      # ~0.35% price buckets, any instrument
        for c in ctx.candles[-60:]:
            bucket = round(int(c.close / step) * step, 2)
            profile[bucket] = profile.get(bucket, 0.0) + c.volume
        poc = max(profile, key=profile.get) if profile else None

        # absorption: volume >2x average with a compressed range
        absorption = []
        for c in window[-5:]:
            rng_pct = (c.high - c.low) / c.close
            if c.volume > 2 * avg_vol and rng_pct < 0.004:
                side = "buy" if c.delta > 0 else "sell"
                absorption.append({"ts": c.ts, "side": side,
                                   "volume": round(c.volume, 1)})

        price = ctx.now.close
        tape_bars = sum(1 for c in window if c.tape)
        findings = [f"Cumulative delta (20 bars): {cum_delta:+,.0f}; "
                    f"last 5 bars: {recent_delta:+,.0f} "
                    f"[{tape_bars}/{len(window)} bars from real tape]."]
        if poc is not None:
            findings.append(f"Volume point of control near {poc:,.0f} "
                            f"({'above' if poc > price else 'below'} price).")
        if absorption:
            findings.append(f"Possible absorption on {absorption[-1]['side']} side "
                            f"(volume spike, compressed range). Caution on breakouts.")

        if cum_delta > 0 and recent_delta > 0:
            stance, confidence = "long", 0.55
        elif cum_delta < 0 and recent_delta < 0:
            stance, confidence = "short", 0.55
        else:
            stance, confidence = "flat", 0.3
            findings.append("Delta conflicted across horizons, no flow edge.")
        if absorption:
            confidence *= 0.7  # absorption against the move weakens conviction

        # --- live depth (only meaningful on the bar the snapshot was taken) ---
        depth = None
        if ctx.book is not None and ctx.book.mid > 0:
            b = ctx.book
            bid_d, ask_d = b.depth(0.005)
            imb = (bid_d - ask_d) / (bid_d + ask_d) if (bid_d + ask_d) else 0.0
            w = b.walls(2)
            depth = {"mid": round(b.mid, 2), "spread_bps": round(b.spread_bps, 2),
                     "bid_depth_50bps": round(bid_d, 3), "ask_depth_50bps": round(ask_d, 3),
                     "imbalance": round(imb, 3),
                     "bid_walls": [[round(p, 2), round(s, 3)] for p, s in w["bids"]],
                     "ask_walls": [[round(p, 2), round(s, 3)] for p, s in w["asks"]]}
            findings.append(f"Book: spread {b.spread_bps:.2f} bps; depth within 50 bps "
                            f"bid {bid_d:,.1f} / ask {ask_d:,.1f} (imbalance {imb:+.2f}).")
            if w["bids"]:
                findings.append(f"Largest resting bid {w['bids'][0][1]:,.1f} @ {w['bids'][0][0]:,.0f}; "
                                f"largest ask {w['asks'][0][1]:,.1f} @ {w['asks'][0][0]:,.0f}.")
            # depth agreeing with delta strengthens, disagreeing weakens
            if stance == "long" and imb < -0.2 or stance == "short" and imb > 0.2:
                confidence *= 0.8
                findings.append("Resting depth leans against the flow read, so conviction is reduced.")
            elif stance != "flat" and abs(imb) > 0.2:
                confidence = min(0.7, confidence + 0.1)

        return AgentReport(
            agent=self.name, role=self.role, stance=stance, confidence=confidence,
            findings=findings,
            data={"cum_delta_20": round(cum_delta, 1),
                  "recent_delta_5": round(recent_delta, 1),
                  "poc": poc, "absorption": absorption,
                  "tape_bars": tape_bars, "depth": depth},
            status="IMPLEMENTED" if (tape_bars or depth) else "SIMULATED",
        )


# --- 4. Risk Manager (interface, hard limits live in risk.py) ---------------

class RiskManagerAgent:
    """The reporting face of the risk engine. The binding checks are pure code
    in risk.py (RiskEngine); this agent only explains the current risk state.
    It is the one agent whose veto is final.
    """

    name = "VETO"
    role = "Risk Manager"

    def __init__(self, engine):
        self.engine = engine

    def analyze(self, ctx: MarketContext) -> AgentReport:
        state = self.engine.state_summary()
        findings = [f"Equity ${state['equity']:,.0f}; "
                    f"day P&L {state['day_pnl_pct']:+.2f}%.",
                    f"Limits: {state['limits_text']}"]
        if state["halted"]:
            findings.append(f"TRADING HALTED: {state['halt_reason']}")
        return AgentReport(
            agent=self.name, role=self.role,
            stance="flat" if state["halted"] else "long",  # stance unused; veto is in engine
            confidence=1.0, findings=findings, data=state,
        )


# --- 5. Execution Specialist (interface, mechanics live in execution.py) -----

class ExecutionSpecialistAgent:
    """Reports on execution conditions (spread/fees/slippage model)."""

    name = "HERMES"
    role = "Execution Specialist"

    def __init__(self, broker):
        self.broker = broker

    def analyze(self, ctx: MarketContext) -> AgentReport:
        a = atr(ctx.candles) or 0.0
        price = ctx.now.close
        est_slip = self.broker.estimate_slippage(price, a)
        findings = [f"Paper venue. Fee {self.broker.fee_bps:.0f} bps per side; "
                    f"est. slippage ~${est_slip:,.0f} at current volatility.",
                    f"ATR(14): ${a:,.0f} ({a / price:.2%} of price)."]
        return AgentReport(
            agent=self.name, role=self.role, stance="flat", confidence=0.5,
            findings=findings,
            data={"fee_bps": self.broker.fee_bps, "est_slippage": round(est_slip, 2),
                  "atr": round(a, 2)},
        )


# --- 6. Research & Audit Analyst (interface, metrics live in audit.py) -------

class ResearchAuditAgent:
    """Reports current after-cost performance and strategy-health flags."""

    name = "LEDGER"
    role = "Research & Audit Analyst"

    def __init__(self, journal):
        self.journal = journal

    def analyze(self, ctx: MarketContext) -> AgentReport:
        m = self.journal.metrics()
        findings = [f"Closed trades: {m['trades']}; win rate {m['win_rate']:.0%}; "
                    f"expectancy after costs ${m['expectancy']:,.0f}.",
                    f"No-trade cycles: {m['no_trade']}; risk vetoes: {m['vetoes']}."]
        if m["trades"] >= 5 and m["expectancy"] < 0:
            findings.append("FLAG: negative after-cost expectancy, strategy "
                            "degradation. Recommend halting new entries for review.")
        return AgentReport(
            agent=self.name, role=self.role, stance="flat", confidence=0.6,
            findings=findings, data=m,
        )
