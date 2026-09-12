"""Pipeline orchestrator — one research cycle per bar.

Flow per cycle:
  1. Fundamental / Technical / Order Flow analysts produce reports.
  2. A committee rule forms a proposal ONLY when Technical and Order Flow
     stances agree (and Fundamental does not strongly oppose). Agreement is
     logged, not trusted — the audit loop judges outcomes after costs.
  3. The Risk Engine (pure code) reviews the proposal. Its veto is final.
  4. The Execution Specialist manages approved orders (fees + slippage).
  5. Research & Audit journals everything, including NO_TRADE cycles.
"""

from __future__ import annotations

from .agents import (AgentReport, ExecutionSpecialistAgent, FundamentalAnalyst,
                     MarketContext, OrderFlowAnalyst, ResearchAuditAgent,
                     RiskManagerAgent, TechnicalAnalyst, atr)
from .audit import Journal, trade_to_dict
from .data import Candle
from .execution import PaperBroker
from .risk import RiskEngine, TradeProposal

MAX_HOLDING_BARS = 24


class Lab:
    def __init__(self, journal_path: str | None = None,
                 starting_cash: float = 100_000.0):
        self.broker = PaperBroker(starting_cash=starting_cash)
        self.risk = RiskEngine(self.broker)
        self.journal = Journal(journal_path)
        self.fundamental = FundamentalAnalyst()
        self.technical = TechnicalAnalyst()
        self.orderflow = OrderFlowAnalyst()
        self.risk_agent = RiskManagerAgent(self.risk)
        self.execution_agent = ExecutionSpecialistAgent(self.broker)
        self.audit_agent = ResearchAuditAgent(self.journal)
        self._entry_bar = -1
        self._stop: float | None = None
        self.last_reports: list[dict] = []

    # -- committee -------------------------------------------------------------

    def _form_proposal(self, reports: dict[str, AgentReport],
                       price: float) -> tuple[TradeProposal | None, str]:
        tech, flow, fund = reports["technical"], reports["orderflow"], reports["fundamental"]
        if tech.stance == "flat" or tech.stance != flow.stance:
            return None, "no technical/order-flow alignment"
        if fund.stance != "flat" and fund.stance != tech.stance and fund.confidence > 0.3:
            return None, f"fundamental bias opposes {tech.stance} thesis"
        if tech.invalidation is None:
            return None, "no invalidation level available"
        confidence = (tech.confidence + flow.confidence) / 2
        if fund.stance == tech.stance:
            confidence = min(1.0, confidence + 0.1)
        thesis = (f"{tech.stance.upper()}: trend and order flow aligned; "
                  f"invalidation {tech.invalidation:,.0f}")
        return TradeProposal(side=tech.stance, price=price,
                             invalidation=tech.invalidation,
                             confidence=confidence, thesis=thesis), ""

    # -- position management ---------------------------------------------------

    def _manage_open_position(self, ctx: MarketContext, reports) -> dict | None:
        if self.broker.position_qty == 0:
            return None
        c = ctx.now
        a = atr(ctx.candles) or 0.0
        side = "long" if self.broker.position_qty > 0 else "short"
        reason = None
        if self._stop is not None:
            if side == "long" and c.low <= self._stop:
                reason = "stop (invalidation) hit"
            elif side == "short" and c.high >= self._stop:
                reason = "stop (invalidation) hit"
        if reason is None and reports["technical"].stance not in ("flat", side):
            reason = "opposite technical signal"
        if reason is None and ctx.bar_index - self._entry_bar >= MAX_HOLDING_BARS:
            reason = f"time stop ({MAX_HOLDING_BARS} bars)"
        if reason is None:
            return None
        exit_price = self._stop if reason.startswith("stop") and self._stop else c.close
        trade = self.broker.close_position(c.ts, exit_price, a, reason)
        self.risk.record_trade_result(trade.pnl, ctx.bar_index)
        self._stop = None
        entry = {"type": "trade_closed", "ts": c.ts, "trade": trade_to_dict(trade)}
        self.journal.log(entry)
        return entry

    # -- one cycle -------------------------------------------------------------

    def run_cycle(self, candles: list[Candle], bar_index: int,
                  news=None, book=None) -> dict:
        ctx = MarketContext(candles=candles, bar_index=bar_index, news=news, book=book)
        c = ctx.now
        self.broker.mark(c.close)

        reports = {
            "fundamental": self.fundamental.analyze(ctx),
            "technical": self.technical.analyze(ctx),
            "orderflow": self.orderflow.analyze(ctx),
        }
        closed = self._manage_open_position(ctx, reports)

        decision, detail, risk_reasons = "NO_TRADE", "", []
        if self.broker.position_qty != 0:
            decision, detail = "HOLDING", "managing open position"
        else:
            proposal, why_not = self._form_proposal(reports, c.close)
            if proposal is None:
                detail = why_not
            else:
                verdict = self.risk.review(proposal, bar_index)
                risk_reasons = verdict.reasons
                if not verdict.approved:
                    decision, detail = "VETOED", "; ".join(verdict.reasons)
                else:
                    a = atr(ctx.candles) or 0.0
                    self.broker.open_position(c.ts, proposal.side, verdict.qty,
                                              c.close, a)
                    self._stop = verdict.stop
                    self._entry_bar = bar_index
                    decision, detail = "ENTERED", proposal.thesis

        reports["risk"] = self.risk_agent.analyze(ctx)
        reports["execution"] = self.execution_agent.analyze(ctx)
        reports["audit"] = self.audit_agent.analyze(ctx)

        self.journal.mark_equity(c.ts, self.broker.equity, c.close)
        entry = {
            "type": "cycle", "ts": c.ts, "bar": bar_index,
            "price": c.close, "decision": decision, "detail": detail,
            "risk_reasons": risk_reasons,
            "stances": {k: r.stance for k, r in reports.items()},
            "confidence": {k: round(r.confidence, 2) for k, r in reports.items()},
        }
        if closed:
            entry["closed_trade"] = closed["trade"]
        self.journal.log(entry)
        self.last_reports = [r.to_dict() for r in reports.values()]
        return entry

    # -- backtest --------------------------------------------------------------

    def run_backtest(self, candles: list[Candle], warmup: int = 60,
                     bars_per_session: int = 24, news=None, book=None) -> dict:
        """Replay bar by bar. `news` is time-gated internally so no cycle sees
        a headline from its future; `book` is a *now* snapshot and is only
        handed to the final cycle — giving it to earlier bars would be look-ahead."""
        last = len(candles) - 1
        for i in range(warmup, len(candles)):
            if (i - warmup) % bars_per_session == 0:
                self.risk.new_session()
            self.run_cycle(candles[:i + 1], i, news=news,
                           book=book if i == last else None)
        return self.journal.metrics(self.broker)
