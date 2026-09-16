#!/usr/bin/env python3
"""GENIUS Desk CLI.

    python3 desk/run_desk.py --once            run one cycle now, publish, exit
    python3 desk/run_desk.py --loop            run every bar, forever (the service)
    python3 desk/run_desk.py --status          print equity, positions, mode, halted
    python3 desk/run_desk.py --kill            flatten every book and halt the desk
    python3 desk/run_desk.py --resume          clear the halt (human decision)
    python3 desk/run_desk.py --probe           tiny round-trip test trade (proves the wiring)
    python3 desk/run_desk.py --once --offline  synthetic market, no network (tests/dev)

Mode (shadow | live) comes from desk/config.json. Live needs DESK_EVM_KEY in the
secrets file (made by --new-evm-wallet); the CLI never prints it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from genius_desk import publish                       # noqa: E402
from genius_desk.config import DeskConfig, Secrets    # noqa: E402
from genius_desk.runner import Desk                   # noqa: E402


def status(desk: Desk) -> str:
    lines = [f"mode: {desk.venue.mode}   halted: {desk.state.get('halted')}"
             + (f" ({desk.state.get('halt_reason')})" if desk.state.get("halted") else ""),
             f"cycles: {desk.state.get('cycles', 0)}   last bar: "
             + (time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(desk.state.get("last_bar_ts", 0)))
                if desk.state.get("last_bar_ts") else "never"),
             f"limits: {next(iter(desk.books.values())).risk.limits_text()}"]
    for b in desk.books.values():
        p = desk.venue.position(b.name)
        lines.append(f"  {b.name:<7} equity ${desk.venue.equity(b.name):8.2f}   "
                     + (f"{p.side} {p.qty:.6f} @ {p.entry:,.0f}  unreal {p.unrealized:+.2f}  stop {p.stop or 0:,.0f}"
                        if p else "flat") + f"   last: {b.last_decision}")
    lines.append(f"  {'TOTAL':<7} equity ${sum(desk.venue.equity(n) for n in desk.books):8.2f}")
    return "\n".join(lines)


def new_evm_wallet() -> int:
    """Generate the desk wallet for Robinhood Chain (0x) ON THIS MACHINE and store
    its key in the secrets file as DESK_EVM_KEY. It receives the token fees and
    HERMES trades from it. Only the public address is printed. Refuses to
    overwrite an existing key."""
    from eth_account import Account
    path = os.environ.get("DESK_SECRETS_FILE", os.path.expanduser("~/.genius-desk/secrets.env"))
    existing = open(path).read() if os.path.exists(path) else ""
    if "DESK_EVM_KEY=" in existing and existing.split("DESK_EVM_KEY=", 1)[1].split("\n", 1)[0].strip():
        print(f"a fee wallet key already exists in {path}; not overwriting.")
        return 1
    acct = Account.create()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [l for l in existing.splitlines() if not l.startswith("DESK_EVM_KEY=")]
    lines.append(f"DESK_EVM_KEY={acct.key.hex()}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    print("desk wallet created (Robinhood Chain).")
    print(f"  key file : {path}  (mode 600, owner only; never printed)")
    print(f"  address  : {acct.address}")
    print()
    print("set that address as the token's fee receiver. the desk trades from it. back the file up somewhere safe.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--kill", action="store_true")
    g.add_argument("--resume", action="store_true")
    g.add_argument("--probe", action="store_true", help="tiny round-trip test trade to prove the wiring")
    g.add_argument("--init-cash", action="store_true", help="adopt fees that landed in the wallet: wrap spare ETH, sell to USDG, split across books")
    g.add_argument("--new-evm-wallet", action="store_true", help="robinhood chain: create the 0x desk wallet (fees + trading) inside the secrets file; prints only the public address")
    ap.add_argument("--offline", action="store_true", help="synthetic market, no network")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = DeskConfig.load(args.config)
    if args.new_evm_wallet:
        return new_evm_wallet()
    secrets = Secrets.load()
    desk = Desk(cfg, secrets, offline=args.offline)

    def after(d: Desk, entry: dict):
        if args.no_publish:
            return
        files = publish.write(d)
        publish.push(d, secrets, files, f"desk: {d.venue.mode} cycle {entry.get('bar', '?')} {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}")

    if args.status:
        print(status(desk)); return 0
    if args.kill:
        closed = desk.halt("manual kill switch")
        print(f"HALTED. flattened {len(closed)} position(s)."); print(status(desk))
        after(desk, {"bar": "kill"}); return 0
    if args.resume:
        desk.resume(); print("resumed."); print(status(desk)); return 0
    if args.init_cash:
        if not hasattr(desk.venue, "init_cash"):
            print("init-cash only applies in live mode"); return 1
        r = desk.venue.init_cash(); desk.save()
        print(json.dumps(r, indent=1)); print(status(desk)); after(desk, {"bar": "init"}); return 0
    if args.probe:
        r = desk.probe()
        print(json.dumps(r, indent=1))
        if r.get("tx_open"):
            base = "https://robinhoodchain.blockscout.com/tx/"
            print(f"\nopen : {base}{r['tx_open']}\nclose: {base}{r['tx_close']}")
        after(desk, {"bar": "probe"}); return 0 if r.get("ok") else 1
    if args.once:
        entry = desk.run_cycle()
        print(json.dumps({k: entry[k] for k in ("ts", "decision", "detail", "equity", "mode") if k in entry}, indent=1))
        print(status(desk)); after(desk, entry); return 0
    if args.loop:
        print(f"desk loop: {desk.venue.mode} mode, bar {cfg.bar_seconds}s. Ctrl-C to stop (positions stay open; use --kill to flatten).")
        desk.loop(on_cycle=after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
