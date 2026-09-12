# GENIUS Desk: the live runner

Takes the lab's six agents to a real venue. Three analyst books (ATLAS, EUCLID, FLUX),
one gate (VETO), one signer (HERMES), one auditor (LEDGER). One cycle per hourly bar.

```
desk/
├── run_desk.py         CLI: --once --loop --status --kill --resume
├── config.json         mode, books, limits, publish targets (no secrets)
├── install.sh          one-shot Ubuntu server install (systemd service + CLI)
├── requirements.txt    driftpy, live mode only
├── genius_desk/
│   ├── config.py       config + secrets loading (secrets never logged)
│   ├── venue.py        ShadowVenue (paper at the live mark) + DriftVenue (real)
│   ├── runner.py       the cycle, books, persistence, reconciliation, kill switch
│   └── publish.py      site payload + optional git push (Netlify redeploys)
├── tests/              13 offline tests: limits, isolation, kill, restart, secrets
├── state/              runtime state + journal (gitignored)
└── data/               recorded tape, book, headlines (gitignored)
```

## Modes

| Mode | What HERMES does | How to enter |
|---|---|---|
| **shadow** | Computes every order and fills it on paper at the live mark with Drift's fee model. Sends nothing. | default |
| **live** | Real orders on Drift Protocol (Solana perps). One sub-account per book. Every entry also places a reduce-only stop order on the exchange. | `"mode": "live"` in config.json, wallet key in secrets |
| **halted** | Kill switch pulled. Everything flattened, nothing trades until a human resumes. | `genius-desk kill` |

## Pilot limits ($100 desk)

Set by `"limits": "PILOT_100"` in config.json, defined in `lab/genius_lab/risk.py`:

| Limit | Value |
|---|---|
| Risk per trade | $1 (at the stop) |
| Daily loss per book | $3, then that book halts for the day |
| Leverage | none: notional never exceeds the book's equity |
| Positions per book | 1 |
| Confidence floor | 0.50 |
| Lot size | 0.0001 BTC (Drift BTC-PERP); smaller sizes are vetoed, not rounded up |

When the account grows, switch `"limits"` to `"PRODUCTION"` (percentages).

## Local dry run (no server, no network)

```bash
python3 desk/run_desk.py --once --offline --no-publish
python3 desk/run_desk.py --status
python3 -m unittest discover -s desk/tests -t desk
```

`--once` without `--offline` runs one real shadow cycle on live market data and writes
`site/console/data.js`, so the site shows the desk.

## Server setup

1. **Get a server.** Hetzner CX22 or DigitalOcean basic, Ubuntu 24.04, about $6 a month.
2. **Make a GitHub token** so the server can pull the private repo and push data:
   GitHub → Settings → Developer settings → Fine-grained tokens → repository access:
   only this repo → permissions: Contents read and write. Copy it once.
3. **Install.** On the server, as root:

   ```bash
   GENIUS_REPO_URL=https://x-access-token:<TOKEN>@github.com/<user>/<repo>.git \
     bash <(curl -fsSL https://raw.githubusercontent.com/<user>/<repo>/main/desk/install.sh)
   ```

   (Or clone the repo first and run `bash desk/install.sh`.)
4. **Secrets.** `nano /etc/genius-desk/secrets.env`:

   ```
   DESK_WALLET_KEY=            # leave empty for shadow mode
   DESK_GIT_REMOTE=https://x-access-token:<TOKEN>@github.com/<user>/<repo>.git
   DESK_RPC_URL=               # optional: a private Solana RPC for reliability
   ```

   And in `desk/config.json` set `"git_push": true` so each cycle pushes `data.js`
   and Netlify redeploys the site with the desk's state.
5. **Shadow for a day.**

   ```bash
   genius-desk once      # one cycle, prints the three books
   genius-desk start     # hourly loop
   genius-desk logs      # watch
   genius-desk status    # any time
   ```

   Watch a day of shadow fills. Compare the fill prices in the journal to what Drift
   showed at those minutes. If they're within a few basis points, the model is honest.

## Going live

Only after shadow looks right.

1. **Fund the wallet:** $100 USDC on Solana plus about $2 SOL for transaction fees.
2. **Deposit into Drift** from the wallet's own UI (app.drift.trade), splitting across
   three sub-accounts (roughly $33.33 each): sub-account 0 = ATLAS, 1 = EUCLID, 2 = FLUX.
   Create the sub-accounts in the Drift UI first; the runner expects them to exist.
3. **Wallet key into the secrets file**, on the server only:
   `DESK_WALLET_KEY=<base58 private key>`. Export it from Phantom (Settings → Security →
   Export private key). It never goes anywhere else. You keep the same key in Phantom, so
   you can always withdraw everything yourself, regardless of the server.
4. **Flip the mode:** `desk/config.json` → `"mode": "live"`, then `genius-desk restart`.
5. **Watch the first cycle:** `genius-desk logs`. The first live fill appears in the
   journal with a `tx` field; open it on solscan.io to see it on-chain.

## The kill switch

```bash
genius-desk kill
```

Flattens every book at market, cancels every stop order, and sets a halt flag that
survives restarts. The loop keeps running but trades nothing. `genius-desk resume` clears
it. Both are human actions; nothing automated can resume the desk.

The desk also halts itself when:
- a book's daily loss limit is hit (that book only, until the next UTC day),
- **reconciliation fails**: the venue's position for a book disagrees with the journal.
  This is the "something is wrong" signal and it always wins.

## What is where, and what to check if something looks off

| Symptom | Look at |
|---|---|
| Site shows stale desk | `genius-desk logs` for `publish_error`; is `git_push` true; is the token valid |
| A book stopped trading | `genius-desk status`: halted? cooldown after 3 losses? daily loss hit? |
| Everything halted | journal `halt` entry with the reason; fix the cause, then `genius-desk resume` |
| Fill prices look wrong | shadow: compare journal fills vs Drift UI; live: open the `tx` on solscan |
| Runner died | `systemctl status genius-desk`; it restarts itself in 30s; positions keep their exchange-side stops |

## Honest notes

- The Drift adapter is written against the current `driftpy` API and the shadow path is
  fully tested, but the live path has not been exercised against mainnet in this repo
  until the first real cycle. Do that with $100, not $10,000.
- Exchange-side stops are trigger-market orders. In a violent move they fill with
  slippage, the same as anywhere.
- Coinbase is the data source and Drift is the venue. Their BTC prices track within a
  few basis points; the shadow fill model uses Coinbase's close and Drift's fee. Live
  mode uses Drift's own oracle price for marks.
