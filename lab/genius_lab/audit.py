"""Research & Audit — decision journal and after-cost evaluation.

IMPLEMENTED. Every cycle writes a journal entry (JSONL) whether or not a trade
happened; agreement between agents is recorded but never treated as proof of
correctness — outcomes are evaluated after costs, against the logged thesis.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict


class Journal:
    def __init__(self, path: str | None = None):
        self.path = path
        self.entries: list[dict] = []
        self.equity_curve: list[dict] = []
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()

    def log(self, entry: dict):
        self.entries.append(entry)
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def mark_equity(self, ts: int, equity: float, price: float):
        self.equity_curve.append({"ts": ts, "equity": round(equity, 2),
                                  "price": round(price, 2)})

    # -- metrics ---------------------------------------------------------------

    def metrics(self, broker=None) -> dict:
        closed = broker.closed if broker else self._closed_from_entries()
        trades = len(closed)
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in closed)
        total_costs = sum(t.costs for t in closed)
        expectancy = total_pnl / trades if trades else 0.0

        max_dd = 0.0
        peak = -float("inf")
        for pt in self.equity_curve:
            peak = max(peak, pt["equity"])
            if peak > 0:
                max_dd = min(max_dd, (pt["equity"] - peak) / peak)

        decisions = [e for e in self.entries if e.get("type") == "cycle"]
        return {
            "trades": trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / trades if trades else 0.0,
            "total_pnl": round(total_pnl, 2),
            "total_costs": round(total_costs, 2),
            "expectancy": round(expectancy, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "no_trade": sum(1 for e in decisions if e["decision"] == "NO_TRADE"),
            "vetoes": sum(1 for e in decisions if e["decision"] == "VETOED"),
            "entries": sum(1 for e in decisions if e["decision"] == "ENTERED"),
            "cycles": len(decisions),
        }

    def _closed_from_entries(self):
        class _T:
            def __init__(self, pnl, costs):
                self.pnl, self.costs = pnl, costs
        out = []
        for e in self.entries:
            if e.get("type") == "trade_closed":
                out.append(_T(e["trade"]["pnl"], e["trade"]["costs"]))
        return out


def trade_to_dict(trade) -> dict:
    return asdict(trade)
