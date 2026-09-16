"""Publish the desk's state for the site.

Writes the same `window.GENIUS_DATA` payload shape the site, console and
floor already read, with `meta.execution` = shadow | live and a `desk.books`
list for the leaderboard. Optionally commits and pushes, which makes Netlify
redeploy. The daily GitHub Action stops overwriting the file once the
`.desk` marker exists next to it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from .config import DeskConfig, REPO_DIR, Secrets
from .runner import Desk

AGENT_META = {
    "ATLAS":  ("Fundamental Analyst", "fundamental"),
    "EUCLID": ("Technical Analyst", "technical"),
    "FLUX":   ("Order Flow Analyst", "orderflow"),
}


def _metrics(desk: Desk) -> dict:
    closed = list(desk.venue.closed)
    wins = [c for c in closed if c.pnl > 0]
    pnl = sum(c.pnl for c in closed)
    costs = sum(c.costs for c in closed)
    curve = desk.state.get("equity_curve", [])
    peak, dd = -1e18, 0.0
    for p in curve:
        peak = max(peak, p["equity"])
        if peak > 0:
            dd = min(dd, (p["equity"] - peak) / peak)
    counts = {"NO_TRADE": 0, "VETOED": 0, "ENTERED": 0, "HOLDING": 0}
    for b in desk.books.values():
        for k, v in b.counts.items():
            counts[k] = counts.get(k, 0) + v
    return {"trades": len(closed), "wins": len(wins), "losses": len(closed) - len(wins),
            "win_rate": len(wins) / len(closed) if closed else 0.0,
            "total_pnl": round(pnl, 2), "total_costs": round(costs, 2),
            "expectancy": round(pnl / len(closed), 2) if closed else 0.0,
            "max_drawdown_pct": round(dd * 100, 2),
            "no_trade": counts["NO_TRADE"], "vetoes": counts["VETOED"],
            "entries": counts["ENTERED"], "cycles": desk.state.get("cycles", 0)}


def _reports(desk: Desk, metrics: dict) -> list[dict]:
    out = []
    for name, (role, key) in AGENT_META.items():
        r = desk.last_reports.get(key)
        if r:
            out.append({**r, "agent": name, "role": role})
    halted = desk.state.get("halted", False)
    limits = next(iter(desk.books.values())).risk.limits_text() if desk.books else ""
    out.append({"agent": "VETO", "role": "Risk Manager", "stance": "flat" if halted else "long",
                "confidence": 1.0, "status": "IMPLEMENTED",
                "findings": [f"Desk equity ${sum(desk.venue.equity(n) for n in desk.books):,.2f} across {len(desk.books)} books.",
                             f"Limits: {limits}."] + ([f"DESK HALTED: {desk.state.get('halt_reason')}"] if halted else []),
                "data": {"halted": halted}})
    mode = desk.venue.mode
    out.append({"agent": "HERMES", "role": "Execution Specialist", "stance": "flat",
                "confidence": 0.5, "status": "IMPLEMENTED",
                "findings": [("Live venue: Uniswap v3 on Robinhood Chain, one desk wallet that also receives the token fees, every swap on Blockscout. Long only; short reads stand aside."
                              if mode == "live" else
                              "Shadow venue: paper fills at the live mark with the real venue's fee model. Nothing sent."),
                             f"Modelled cost {desk.venue.fee_bps:.0f} bps per side; live P&L uses real amounts."],
                "data": {"mode": mode}})
    flag = metrics["trades"] >= 5 and metrics["expectancy"] < 0
    out.append({"agent": "LEDGER", "role": "Research & Audit Analyst", "stance": "flat",
                "confidence": 0.6, "status": "IMPLEMENTED",
                "findings": [f"Closed trades: {metrics['trades']}; win rate {metrics['win_rate']:.0%}; "
                             f"expectancy after costs ${metrics['expectancy']:,.2f}.",
                             f"No-trade cycles: {metrics['no_trade']}; risk vetoes: {metrics['vetoes']}."]
                            + (["FLAG: negative after-cost expectancy. Recommend review before new entries."] if flag else []),
                "data": metrics})
    return out


_VENUE_NAME = {"uniswap": "Robinhood Chain"}
_VENUE_LONG = {"uniswap": "Robinhood Chain (Uniswap v3 spot)"}
_VENUE_MODE = {"uniswap": "real swaps on Robinhood Chain"}


def build_payload(desk: Desk) -> dict:
    cfg, st = desk.cfg, desk.state
    metrics = _metrics(desk)
    books = []
    first_pos = None
    for b in desk.books.values():
        p = desk.venue.position(b.name)
        eq = desk.venue.equity(b.name)
        closed_b = [c for c in desk.venue.closed if c.book == b.name]
        pos = None
        if p:
            pos = {**p.to_dict(), "bars_held": int((st.get("last_bar_ts", 0) - b.entry_bar_ts) / cfg.bar_seconds) if b.entry_bar_ts else 0}
            first_pos = first_pos or pos
        books.append({"name": b.name, "analyst": b.analyst, "equity": round(eq, 2),
                      "session_pnl": round(eq - (b.session_start_equity or eq), 2),
                      "total_pnl": round(sum(c.pnl for c in closed_b) + (p.unrealized if p else 0.0), 2),
                      "trades": len(closed_b), "position": pos,
                      "last_decision": b.last_decision, "last_detail": b.last_detail,
                      "stance": (desk.last_reports.get(b.analyst) or {}).get("stance", "flat")})
    equity = sum(desk.venue.equity(n) for n in desk.books)
    session_pnl = sum(bk["session_pnl"] for bk in books)
    last_ts = st.get("last_bar_ts", 0)
    lines = {n: ((desk.last_reports.get(k) or {}).get("findings") or [""])[0] for n, (_, k) in AGENT_META.items()}
    stances = {n: (desk.last_reports.get(k) or {}).get("stance", "flat") for n, (_, k) in AGENT_META.items()}
    stances.update({"VETO": "flat" if st.get("halted") else "long", "HERMES": "flat", "LEDGER": "flat"})
    lc = desk.last_cycle or {}
    inputs = st.get("inputs", {})
    real = [k for k, v in inputs.items() if str(v).startswith("live")]
    return {
        "meta": {
            "source": inputs.get("candles", "unknown"), "inputs": inputs, "provenance": {},
            "instrument": cfg.instrument, "execution": desk.venue.mode,
            "venue": (f"{_VENUE_LONG[cfg.venue]} {cfg.coin}" if desk.venue.mode == "live"
                      else f"shadow ({cfg.coin} on {_VENUE_NAME[cfg.venue]} fee model)"),
            "venue_name": _VENUE_NAME[cfg.venue],
            "long_only": bool(getattr(desk.venue, "long_only", False)),
            "mode": (f"LIVE: {_VENUE_MODE[cfg.venue]}" if desk.venue.mode == "live"
                     else "SHADOW: paper fills at the live mark, nothing sent"),
            "sessions": None, "bars_per_session": 24, "bar_seconds": cfg.bar_seconds,
            "generated_at": int(time.time()), "last_bar_ts": last_ts,
            "next_cycle_ts": last_ts + 2 * cfg.bar_seconds,
            "books": len(books), "limits": next(iter(desk.books.values())).risk.limits_text() if desk.books else "",
            "generated_note": ("All P&L after venue fees" + (" and modelled slippage" if desk.venue.mode == "shadow" else "")
                               + ". " + (f"Real inputs: {', '.join(real)}." if real else "")),
        },
        "metrics": metrics,
        "desk": {"coin": cfg.coin, "equity": round(equity, 2), "session_pnl": round(session_pnl, 2),
                 "position": first_pos, "books": books,
                 "last_decision": ({"decision": lc.get("decision"), "detail": lc.get("detail", "")[:200],
                                    "ts": lc.get("ts")} if lc else None),
                 "fill_last_cycle": bool(st.get("fill_last_cycle")),
                 "halted": bool(st.get("halted")), "halt_reason": st.get("halt_reason", ""),
                 "stances": stances, "lines": lines},
        "equity_curve": st.get("equity_curve", [])[-800:],
        "reports": _reports(desk, metrics),
        "journal_tail": _journal_tail(desk, 60),
        "closed_trades": [c.to_dict() for c in desk.venue.closed][-25:],
    }


def _journal_tail(desk: Desk, n: int) -> list[dict]:
    if not os.path.exists(desk.journal_path):
        return []
    rows = []
    with open(desk.journal_path) as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "cycle" and e.get("decision") != "SKIPPED":
                rows.append({"ts": e["ts"], "bar": e.get("bar", 0), "price": e.get("price", 0),
                             "decision": e["decision"], "detail": e.get("detail", "")[:240],
                             "stances": e.get("stances", {}), "risk_reasons": []})
    return rows[-n:]


def write(desk: Desk, payload: dict | None = None) -> list[str]:
    payload = payload or build_payload(desk)
    written = []
    for rel in desk.cfg.publish.targets:
        path = os.path.join(REPO_DIR, rel)
        if not os.path.isdir(os.path.dirname(path)):
            continue
        with open(path, "w") as f:
            f.write("window.GENIUS_DATA = ")
            json.dump(payload, f, separators=(",", ":"))
            f.write(";\n")
        marker = os.path.join(os.path.dirname(path), ".desk")
        open(marker, "w").write(f"owned by the desk runner since {time.strftime('%Y-%m-%d')}\n")
        written += [path, marker]
    return written


def push(desk: Desk, secrets: Secrets, files: list[str], message: str) -> bool:
    """Commit + push the published files. Returns False (and never raises) on failure."""
    if not desk.cfg.publish.git_push or not secrets.git_remote:
        return False
    try:
        rel = [os.path.relpath(f, REPO_DIR) for f in files]
        run = lambda *a: subprocess.run(["git", *a], cwd=REPO_DIR, check=True,   # noqa: E731
                                        capture_output=True, text=True, timeout=120)
        run("config", "user.name", "genius-desk[bot]")
        run("config", "user.email", "genius-desk[bot]@users.noreply.github.com")
        run("add", "-f", *rel)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR).returncode == 0:
            return True
        run("commit", "-m", message)
        run("push", secrets.git_remote, f"HEAD:{desk.cfg.publish.git_branch}")
        return True
    except Exception as e:   # log, never leak the remote (it carries the token)
        desk._journal({"type": "publish_error", "ts": int(time.time()),
                       "error": repr(e).replace(secrets.git_remote or "", "<remote>")[:300]})
        return False
