#!/usr/bin/env python3
"""GENIUS Lab — runs the 33-session challenge end to end.

Usage:
    python3 lab/run_demo.py            # synthetic market (deterministic, offline)
    python3 lab/run_demo.py --live     # real BTC-USD: candles + trade tape + L2 book
                                       # + RSS headlines. Falls back per-input on
                                       # failure and records what was real.

Outputs:
    lab/output/journal.jsonl           # full decision journal
    lab/data/*.jsonl                   # recorded tape / book / candles (live only)
    site/console/data.js               # data consumed by the lab console page
    genius-web/public/console/data.js  # same, for the React/Lovable copy (if present)

`site/` is the deployable folder — see DEPLOY.md.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from genius_lab.data import fetch_live, synthetic_candles
from genius_lab.news import live_news
from genius_lab.pipeline import Lab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS = 33
BARS_PER_SESSION = 24
WARMUP = 60
BARS_NEEDED = WARMUP + SESSIONS * BARS_PER_SESSION   # 852 hourly bars ≈ 35.5 days


def main() -> None:
    use_live = "--live" in sys.argv
    t0 = time.time()
    inputs = {"candles": "synthetic", "tape": "none", "book": "none", "news": "fixtures"}
    provenance: dict = {}
    candles = news = book = None

    if use_live:
        print("fetching live data (Coinbase public API + RSS)…")
        bundle = fetch_live("BTC-USD", bars=BARS_NEEDED,
                            record_dir=os.path.join(ROOT, "lab", "data"))
        if bundle and len(bundle.candles) >= WARMUP + 2 * BARS_PER_SESSION:
            candles, book = bundle.candles, bundle.book
            inputs["candles"] = "live:coinbase"
            inputs["tape"] = f"live:{bundle.tape_bars} bars" if bundle.tape_bars else "none"
            inputs["book"] = "live" if book else "none"
            provenance = bundle.provenance()
        else:
            print("  candles unavailable — falling back to synthetic market")
        news = live_news(cache_dir=os.path.join(ROOT, "lab", "data"))
        if news and news.items:
            inputs["news"] = f"live:rss ({len(news.items)} items)"
            provenance["news"] = news.summary()
        else:
            news = None
            print("  news feeds unavailable — falling back to fixtures")

    if candles is None:
        candles = synthetic_candles(BARS_NEEDED, seed=33)

    lab = Lab(journal_path=os.path.join(ROOT, "lab", "output", "journal.jsonl"))
    metrics = lab.run_backtest(candles, warmup=WARMUP,
                               bars_per_session=BARS_PER_SESSION, news=news, book=book)

    sessions_run = (len(candles) - WARMUP) // BARS_PER_SESSION
    real = [k for k, v in inputs.items() if v.startswith("live")]

    # open position + session state, for the live desk view
    b = lab.broker
    last = candles[-1]
    position = None
    if b.position_qty != 0:
        side = "long" if b.position_qty > 0 else "short"
        unreal = b.position_qty * (last.close - b.entry_price)
        position = {"side": side, "qty": round(abs(b.position_qty), 6),
                    "entry": round(b.entry_price, 2), "mark": round(last.close, 2),
                    "unrealized": round(unreal, 2), "stop": lab._stop,
                    "since_ts": b.entry_ts,
                    "bars_held": len(candles) - 1 - lab._entry_bar}
    cycles = [e for e in lab.journal.entries if e["type"] == "cycle"]
    session = cycles[-(len(cycles) % BARS_PER_SESSION or BARS_PER_SESSION):]
    session_start_eq = next((pt["equity"] for pt in lab.journal.equity_curve
                             if pt["ts"] == session[0]["ts"]), b.equity)
    last_decision = cycles[-1] if cycles else None
    fills_last_cycle = [e for e in lab.journal.entries
                        if e["type"] == "trade_closed" and e["ts"] == last.ts]
    entered_last_cycle = bool(last_decision and last_decision["decision"] == "ENTERED")

    payload = {
        "meta": {
            "source": inputs["candles"],
            "inputs": inputs,
            "provenance": provenance,
            "instrument": "BTC-USD",
            "mode": "PAPER / SIMULATED — no real capital, no live execution",
            "sessions": sessions_run,
            "bars_per_session": BARS_PER_SESSION,
            "generated_at": int(t0),
            "execution": "paper",           # paper | shadow | live
            "venue": "BTC-USD",
            "bar_seconds": 3600,
            "last_bar_ts": last.ts,
            "next_cycle_ts": last.ts + 2 * 3600,
            "generated_note": ("All performance is after simulated fees and slippage. "
                               + (f"Real inputs: {', '.join(real)}." if real
                                  else "All inputs synthetic.")),
        },
        "metrics": metrics,
        "desk": {
            "equity": round(b.equity, 2),
            "session_pnl": round(b.equity - session_start_eq, 2),
            "position": position,
            "last_decision": ({"decision": last_decision["decision"],
                               "detail": last_decision["detail"],
                               "ts": last_decision["ts"]} if last_decision else None),
            "fill_last_cycle": bool(fills_last_cycle) or entered_last_cycle,
            "stances": {r["agent"]: r["stance"] for r in lab.last_reports},
            "lines": {r["agent"]: (r["findings"][0] if r["findings"] else "")
                      for r in lab.last_reports},
        },
        "equity_curve": lab.journal.equity_curve,
        "reports": lab.last_reports,
        "journal_tail": [e for e in lab.journal.entries if e["type"] == "cycle"][-60:],
        "closed_trades": [e["trade"] for e in lab.journal.entries
                          if e["type"] == "trade_closed"][-25:],
    }

    out = os.path.join(ROOT, "site", "console", "data.js")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("window.GENIUS_DATA = ")
        json.dump(payload, f)
        f.write(";\n")
    mirror = os.path.join(ROOT, "genius-web", "public", "console", "data.js")
    if os.path.isdir(os.path.dirname(mirror)):
        shutil.copyfile(out, mirror)

    print(f"inputs: {inputs}")
    if provenance:
        print(f"provenance: {json.dumps(provenance)}")
    print(f"sessions: {sessions_run} × {BARS_PER_SESSION} bars (+{WARMUP} warmup)")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"journal: lab/output/journal.jsonl ({len(lab.journal.entries)} entries)")
    print("console data: site/console/data.js"
          + (" (+ genius-web mirror)" if os.path.exists(mirror) else ""))
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
