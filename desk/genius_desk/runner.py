"""The desk runner: one cycle per bar, three books, one gate, one signer.

Per cycle:
  1. Fetch the live market (candles, tape, order book, headlines) via the lab.
  2. Run ATLAS, EUCLID and FLUX once on the shared context.
  3. For each book: manage the open position (stop, opposite signal, time
     stop), or form a proposal from that book's analyst and send it to VETO.
     Stops always come from EUCLID's structure; the analyst supplies direction.
  4. HERMES executes approved orders on the venue.
  5. Reconcile: our record of each book vs the venue's. A mismatch halts the
     desk. Nothing trades again until a human looks.
  6. Journal everything, persist state, publish for the site.

The kill switch (`halt`) flattens every book and sets a flag that survives
restarts. `resume` clears it. Both are explicit human actions.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(DESK_DIR)
sys.path.insert(0, os.path.join(REPO_DIR, "lab"))

from genius_lab import risk as risk_mod                      # noqa: E402
from genius_lab.agents import (FundamentalAnalyst, MarketContext,   # noqa: E402
                               OrderFlowAnalyst, TechnicalAnalyst, atr)
from genius_lab.data import fetch_live, synthetic_candles  # noqa: E402
from genius_lab.news import live_news                       # noqa: E402
from genius_lab.risk import RiskEngine, TradeProposal       # noqa: E402

from .config import DeskConfig, Secrets                     # noqa: E402
from .venue import DriftVenue, ShadowVenue, Venue           # noqa: E402


class _BookEquity:
    """Adapter so the lab's RiskEngine can read a venue book like a broker."""
    def __init__(self, venue: Venue, book: str):
        self.venue, self.book = venue, book

    @property
    def equity(self) -> float:
        return self.venue.equity(self.book)

    @property
    def position_qty(self) -> float:
        p = self.venue.position(self.book)
        return 0.0 if not p else (p.qty if p.side == "long" else -p.qty)


@dataclass
class Book:
    name: str
    analyst: str
    risk: RiskEngine
    entry_bar_ts: int = 0
    session_start_equity: float = 0.0
    last_decision: str = "NO_TRADE"
    last_detail: str = ""
    cycles: int = 0
    counts: dict = field(default_factory=lambda: {"NO_TRADE": 0, "VETOED": 0, "ENTERED": 0, "HOLDING": 0})


class Desk:
    def __init__(self, cfg: DeskConfig, secrets: Secrets | None = None,
                 venue: Venue | None = None, offline: bool = False):
        self.cfg = cfg
        self.secrets = secrets or Secrets()
        self.offline = offline
        self.limits = getattr(risk_mod, cfg.limits)
        os.makedirs(cfg.state_dir, exist_ok=True)
        os.makedirs(cfg.data_dir, exist_ok=True)
        self.state_path = os.path.join(cfg.state_dir, "state.json")
        self.journal_path = os.path.join(cfg.state_dir, "journal.jsonl")
        self.state = self._load_state()

        names = [b.name for b in cfg.books]
        if venue is not None:
            self.venue = venue
        elif cfg.mode == "live":
            if not self.secrets.wallet_key:
                raise RuntimeError("live mode needs DESK_WALLET_KEY in the secrets file")
            self.venue = DriftVenue({b.name: b.sub_account for b in cfg.books},
                                    cfg.drift_market, self.secrets.rpc_url or cfg.rpc_url,
                                    self.secrets.wallet_key)
        else:
            self.venue = ShadowVenue(names, cfg.starting_cash_per_book,
                                     mark=self.state.get("last_mark", 0.0) or 0.0)
        if self.state.get("venue"):
            self.venue.restore(self.state["venue"])

        self.analysts = {"fundamental": FundamentalAnalyst(), "technical": TechnicalAnalyst(),
                         "orderflow": OrderFlowAnalyst()}
        self.books: dict[str, Book] = {}
        for bc in cfg.books:
            eng = RiskEngine(_BookEquity(self.venue, bc.name), self.limits)
            bs = self.state.get("books", {}).get(bc.name, {})
            eng.consecutive_losses = bs.get("consecutive_losses", 0)
            eng.cooldown_until_bar = bs.get("cooldown_until_bar", -1)
            eng.halted = bs.get("halted", False)
            eng.halt_reason = bs.get("halt_reason", "")
            eng.day_start_equity = bs.get("day_start_equity", 0.0) or 0.0
            b = Book(name=bc.name, analyst=bc.analyst, risk=eng,
                     entry_bar_ts=bs.get("entry_bar_ts", 0),
                     session_start_equity=bs.get("session_start_equity", 0.0),
                     last_decision=bs.get("last_decision", "NO_TRADE"),
                     last_detail=bs.get("last_detail", ""), cycles=bs.get("cycles", 0),
                     counts=bs.get("counts", {"NO_TRADE": 0, "VETOED": 0, "ENTERED": 0, "HOLDING": 0}))
            self.books[bc.name] = b
        self.last_reports: dict = {}
        self.last_cycle: dict | None = None

    # ------------------------------------------------------------ state
    def _load_state(self) -> dict:
        if os.path.exists(self.state_path):
            return json.load(open(self.state_path))
        return {"halted": False, "halt_reason": "", "cycles": 0, "equity_curve": [],
                "books": {}, "last_bar_ts": 0, "last_mark": 0.0, "session_day": ""}

    def save(self):
        self.state["books"] = {
            n: {"consecutive_losses": b.risk.consecutive_losses,
                "cooldown_until_bar": b.risk.cooldown_until_bar, "halted": b.risk.halted,
                "halt_reason": b.risk.halt_reason, "day_start_equity": b.risk.day_start_equity,
                "entry_bar_ts": b.entry_bar_ts, "session_start_equity": b.session_start_equity,
                "last_decision": b.last_decision, "last_detail": b.last_detail,
                "cycles": b.cycles, "counts": b.counts}
            for n, b in self.books.items()}
        self.state["venue"] = self.venue.snapshot()
        self.state["last_mark"] = self.venue.mark_price()
        tmp = self.state_path + ".tmp"
        json.dump(self.state, open(tmp, "w"))
        os.replace(tmp, self.state_path)

    def _journal(self, entry: dict):
        with open(self.journal_path, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    # ------------------------------------------------------ kill switch
    def halt(self, reason: str = "manual kill switch") -> list:
        mark = self.venue.mark_price() or 0.0
        closed = self.venue.flatten_all(mark, 0.0, f"halt: {reason}") if mark else []
        self.state["halted"] = True
        self.state["halt_reason"] = reason
        for b in self.books.values():
            b.entry_bar_ts = 0
        self._journal({"type": "halt", "ts": int(time.time()), "reason": reason,
                       "flattened": [c.to_dict() for c in closed]})
        self.save()
        return closed

    def resume(self):
        self.state["halted"] = False
        self.state["halt_reason"] = ""
        for b in self.books.values():
            b.risk.new_session()
        self._journal({"type": "resume", "ts": int(time.time())})
        self.save()

    # ----------------------------------------------------------- market
    def _market(self):
        """Live market bundle, or a synthetic one when offline (tests)."""
        if self.offline:
            candles = synthetic_candles(self.cfg.history_bars, seed=int(time.time()) % 1000)
            return candles, None, None, None
        bundle = fetch_live(self.cfg.instrument, bars=self.cfg.history_bars,
                            record_dir=self.cfg.data_dir)
        if not bundle:
            return None, None, None, None
        news = live_news(cache_dir=self.cfg.data_dir)
        return bundle.candles, bundle.book, (news if news and news.items else None), bundle

    # ------------------------------------------------------------ cycle
    def run_cycle(self) -> dict:
        t0 = int(time.time())
        candles, book, news, bundle = self._market()
        if not candles:
            entry = {"type": "cycle", "ts": t0, "decision": "SKIPPED",
                     "detail": "market data unavailable"}
            self._journal(entry)
            return entry
        last = candles[-1]
        if last.ts == self.state.get("last_bar_ts") and not self.offline:
            entry = {"type": "cycle", "ts": t0, "decision": "SKIPPED",
                     "detail": f"bar {last.ts} already processed"}
            self._journal(entry)
            return entry

        mark = last.close if self.venue.mode == "shadow" else (self.venue.mark_price() or last.close)
        if isinstance(self.venue, ShadowVenue):
            self.venue.set_mark(mark)
        a = atr(candles) or 0.0

        # new session (UTC day) → rebase daily limits
        day = time.strftime("%Y-%m-%d", time.gmtime(last.ts))
        if day != self.state.get("session_day"):
            self.state["session_day"] = day
            for b in self.books.values():
                b.risk.new_session()
                b.session_start_equity = self.venue.equity(b.name)

        ctx = MarketContext(candles=candles, bar_index=len(candles) - 1, news=news, book=book)
        reports = {k: an.analyze(ctx) for k, an in self.analysts.items()}
        tech = reports["technical"]
        self.last_reports = {k: r.to_dict() for k, r in reports.items()}

        # reconcile BEFORE anything trades: a mismatch means our picture of the
        # venue is wrong, and trading on a wrong picture is how accounts die
        mismatch = self._reconcile()
        if mismatch and not self.state.get("halted"):
            self.halt(f"reconciliation mismatch: {mismatch}")
        halted = self.state.get("halted", False)
        per_book = {}
        fill_this_cycle = False
        for b in self.books.values():
            eng, pos = b.risk, self.venue.position(b.name)
            decision, detail, risk_reasons = "NO_TRADE", "", []
            closed = None
            # --- manage an open position
            if pos:
                reason = None
                if pos.stop and ((pos.side == "long" and last.low <= pos.stop) or
                                 (pos.side == "short" and last.high >= pos.stop)):
                    reason = "stop (invalidation) hit"
                elif tech.stance not in ("flat", pos.side):
                    reason = "opposite technical signal"
                elif b.entry_bar_ts and (last.ts - b.entry_bar_ts) >= self.cfg.max_holding_bars * self.cfg.bar_seconds:
                    reason = f"time stop ({self.cfg.max_holding_bars} bars)"
                elif halted:
                    reason = "desk halted"
                if reason:
                    exit_mark = pos.stop if reason.startswith("stop") and pos.stop else mark
                    closed = self.venue.close(b.name, exit_mark, a, reason)
                    eng.record_trade_result(closed.pnl, len(candles) - 1)
                    b.entry_bar_ts = 0
                    fill_this_cycle = True
                    self._journal({"type": "trade_closed", "ts": last.ts, "book": b.name,
                                   "trade": closed.to_dict()})
                    pos = None
                else:
                    decision, detail = "HOLDING", f"{pos.side} {pos.qty:.6f} @ {pos.entry:,.0f}"
            # --- or look for a new one
            if pos is None and not halted and decision != "HOLDING":
                rep = reports[b.analyst]
                inval = (tech.invalidation if b.analyst == "technical" else
                         (tech.data.get("swing_low") if rep.stance == "long" else tech.data.get("swing_high")))
                if rep.stance == "flat":
                    detail = f"{b.name} has no directional read"
                elif inval is None:
                    detail = "no structural stop available"
                else:
                    prop = TradeProposal(side=rep.stance, price=mark, invalidation=inval,
                                         confidence=rep.confidence,
                                         thesis=f"{rep.stance.upper()}: {b.name} view, EUCLID stop {inval:,.0f}")
                    verdict = eng.review(prop, len(candles) - 1)
                    risk_reasons = verdict.reasons
                    qty = self._lot(verdict.qty) if verdict.approved else 0.0
                    if verdict.approved and qty < self.cfg.min_order:
                        decision = "VETOED"
                        detail = (f"VETO: size {verdict.qty:.6f} rounds to {qty:.4f}, "
                                  f"below venue minimum {self.cfg.min_order}")
                        risk_reasons = [detail]
                    elif verdict.approved:
                        fill = self.venue.open(b.name, prop.side, qty, mark, verdict.stop, a)
                        b.entry_bar_ts = last.ts
                        fill_this_cycle = True
                        decision, detail = "ENTERED", prop.thesis
                        self._journal({"type": "fill", "ts": last.ts, "book": b.name, "fill": fill.to_dict()})
                    else:
                        decision, detail = "VETOED", "; ".join(verdict.reasons)
            elif halted and pos is None and decision != "HOLDING":
                detail = f"desk halted: {self.state.get('halt_reason', '')}"

            b.cycles += 1
            b.counts[decision] = b.counts.get(decision, 0) + 1
            b.last_decision, b.last_detail = decision, detail
            per_book[b.name] = {"decision": decision, "detail": detail, "risk": risk_reasons,
                                "stance": reports[b.analyst].stance,
                                "confidence": round(reports[b.analyst].confidence, 2),
                                "equity": round(self.venue.equity(b.name), 4),
                                "closed": closed.to_dict() if closed else None}

        # --- and again after: what we did must match what the venue says we did
        mismatch = self._reconcile()
        if mismatch and not self.state.get("halted"):
            self.halt(f"post-trade reconciliation mismatch: {mismatch}")

        equity = sum(self.venue.equity(n) for n in self.books)
        self.state["equity_curve"].append({"ts": last.ts, "equity": round(equity, 4), "price": mark})
        self.state["equity_curve"] = self.state["equity_curve"][-2000:]
        self.state["cycles"] = self.state.get("cycles", 0) + 1
        self.state["last_bar_ts"] = last.ts
        self.state["fill_last_cycle"] = fill_this_cycle
        self.state["inputs"] = ({"candles": "live:coinbase",
                                 "tape": f"live:{bundle.tape_bars} bars" if bundle.tape_bars else "none",
                                 "book": "live" if book else "none",
                                 "news": f"live:rss ({len(news.items)} items)" if news else "none"}
                                if bundle else {"candles": "synthetic", "tape": "none", "book": "none", "news": "fixtures"})
        order = {"ENTERED": 3, "VETOED": 2, "HOLDING": 1, "NO_TRADE": 0}
        top = max(per_book.values(), key=lambda v: order[v["decision"]])
        entry = {"type": "cycle", "ts": last.ts, "bar": self.state["cycles"], "price": mark,
                 "decision": top["decision"], "detail": "; ".join(f"{n}: {v['detail']}" for n, v in per_book.items() if v["detail"]),
                 "books": per_book, "equity": round(equity, 4), "mode": self.venue.mode,
                 "stances": {"fundamental": reports["fundamental"].stance, "technical": tech.stance,
                             "orderflow": reports["orderflow"].stance}}
        self._journal(entry)
        self.last_cycle = entry
        self.save()
        return entry

    def _lot(self, qty: float) -> float:
        """Round down to the venue's lot size."""
        step = self.cfg.order_step
        return round((int(qty / step + 1e-9)) * step, 8)

    def _reconcile(self) -> str:
        """Live only: every book's venue position must match what we think we hold."""
        if self.venue.mode != "live":
            return ""
        problems = []
        for b in self.books.values():
            p = self.venue.position(b.name)
            think_open = bool(b.entry_bar_ts)
            if bool(p) != think_open:
                problems.append(f"{b.name}: venue={'open' if p else 'flat'} journal={'open' if think_open else 'flat'}")
        return "; ".join(problems)

    # ------------------------------------------------------------- loop
    def next_bar_wall_time(self) -> float:
        now = time.time()
        bs = self.cfg.bar_seconds
        return (int(now // bs) + 1) * bs + 45          # 45s after the bar closes

    def loop(self, on_cycle=None):
        while True:
            wake = self.next_bar_wall_time()
            time.sleep(max(1.0, wake - time.time()))
            try:
                entry = self.run_cycle()
                if on_cycle:
                    on_cycle(self, entry)
            except Exception as e:              # never die silently; log and keep the loop alive
                self._journal({"type": "error", "ts": int(time.time()), "error": repr(e)[:500]})
