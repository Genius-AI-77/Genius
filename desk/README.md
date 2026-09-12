# GENIUS Desk: the live runner

Takes the lab's six agents to a real venue. Three analyst books (ATLAS, EUCLID, FLUX),
one gate (VETO), one signer (HERMES), one auditor (LEDGER). One cycle per hourly bar.

```
desk/
├── run_desk.py         CLI: --once --loop --status --kill --resume
├── config.json         mode, books, limits, publish targets (no secrets)
├── install.sh          one-shot Ubuntu server install (systemd service + CLI)
├── requirements.txt    solders (solana venue) and hyperliquid-python-sdk (optional)
├── genius_desk/
│   ├── config.py       config + secrets loading (secrets never logged)
│   ├── venue.py        ShadowVenue (paper at the live mark) + HyperliquidVenue
│   ├── solana_venue.py SolanaVenue: Jupiter spot swaps signed by the desk wallet
│   ├── runner.py       the cycle, books, persistence, reconciliation, kill switch
│   └── publish.py      site payload + optional git push (Netlify redeploys)
├── tests/              13 offline tests: limits, isolation, kill, restart, secrets
├── state/              runtime state + journal (gitignored)
└── data/               recorded tape, book, headlines (gitignored)
```

## Modes

| Mode | What HERMES does | How to enter |
|---|---|---|
| **shadow** | Computes every order and fills it on paper at the live mark with Hyperliquid's fee model. Sends nothing. | default |
| **live** | Real orders on Hyperliquid perps. One sub-account per book. Every entry also places a reduce-only stop order on the exchange. The desk holds an agent key that can trade but never withdraw. | `"mode": "live"` in config.json, agent key + account in secrets |
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
| Lot size | 0.00001 BTC; Hyperliquid's $10 minimum order value is enforced (0.00014 BTC); smaller sizes are vetoed, not rounded up |

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
   DESK_AGENT_KEY=             # leave empty for shadow mode
   DESK_ACCOUNT=
   DESK_GIT_REMOTE=https://x-access-token:<TOKEN>@github.com/<user>/<repo>.git
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

   Watch a day of shadow fills. Compare the fill prices in the journal to what Hyperliquid
   showed at those minutes. If they're within a few basis points, the model is honest.

## Going live on Solana (default venue: `"venue": "solana"`)

The simplest real venue: one dedicated Phantom wallet, SOL and USDC, every swap on Solscan.
Long only (a short read means the book stands aside); the desk watches stops itself every
minute because spot has no exchange-side stops. **Use a wallet that holds only the pilot
money; its key signs swaps and could move funds.**

1. **Fund the wallet:** send about $105 of SOL to it (the desk keeps 0.03 SOL for fees and
   converts the rest to USDC as cash).
2. **Secrets file** (Mac: `~/.genius-desk/secrets.env`, server: `/etc/genius-desk/secrets.env`):

   ```
   DESK_WALLET_KEY=<base58 private key exported from Phantom>
   DESK_RPC_URL=              # optional; a free Helius endpoint is steadier than the public RPC
   ```
3. `desk/config.json`: `"mode": "live"` (venue is already `solana`).
4. **Convert to cash and split across the three books** (once):

   ```bash
   python3 desk/run_desk.py --init-cash
   ```
5. **Probe** (a $5 round trip on the ATLAS book, two Solscan links), then **loop**:

   ```bash
   python3 desk/run_desk.py --probe
   python3 desk/run_desk.py --loop
   ```

## Going live on Hyperliquid (`"venue": "hyperliquid"`)

Only after shadow looks right, or with a pilot amount you can lose.

**Identity model, once:** the *master* wallet holds the money and is yours, in Phantom or
any EVM wallet. The desk never has its key. In the Hyperliquid app you approve an *agent*
(API) wallet: a second key that can place orders for the master and its sub-accounts but
**cannot withdraw**. Only that agent key goes on the server. You can revoke it from the
master at any time, and you can always withdraw everything yourself.

1. **Fund Hyperliquid.** From Phantom, the native route: on app.hyperliquid.xyz click
   Deposit → SOL → copy the Solana deposit address (this is Unit, Hyperliquid's bridge) →
   send at least **0.2 SOL** (about $105 worth for the pilot) from Phantom. It arrives in
   2 to 10 minutes as spot SOL. Then Trade → Spot → sell SOL for USDC → Transfer to Perps.
2. **Three sub-accounts.** Top right → Sub-Accounts → Create, three times. Transfer about
   one third of the USDC into each. Note each sub-account's 0x address.
3. **Agent key.** Top right → API → Generate. Name it `genius-desk`. Copy the private key
   once; the UI never shows it again. Approve it.
4. **Config:** in `desk/config.json` fill `hl_books` with the three sub-account addresses:

   ```json
   "hl_books": { "ATLAS": "0x…", "EUCLID": "0x…", "FLUX": "0x…" }
   ```

   and set `"mode": "live"`.
5. **Secrets** (server: `/etc/genius-desk/secrets.env`; Mac: `~/.genius-desk/secrets.env`):

   ```
   DESK_AGENT_KEY=<agent private key, hex>
   DESK_ACCOUNT=<master wallet 0x address>
   DESK_TESTNET=0
   ```
6. **Probe, then loop.**

   ```bash
   genius-desk once                     # server
   python3 desk/run_desk.py --probe     # Mac: tiny round trip, prints explorer links
   ```

   The first fill appears in the journal with a `tx` hash; open it at
   `https://app.hyperliquid.xyz/explorer/tx/<hash>`.

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
| Fill prices look wrong | shadow: compare journal fills vs the Hyperliquid UI; live: open the `tx` in the explorer |
| Runner died | `systemctl status genius-desk`; it restarts itself in 30s; positions keep their exchange-side stops |

## Honest notes

- The Hyperliquid adapter has been exercised against Hyperliquid's **testnet** from this
  repo (connect, read market and account, sign and submit an order; the exchange answered
  correctly for an unfunded account). The first *filled* order is the first live cycle.
  Do that with $100, not $10,000.
- Exchange-side stops are trigger-market orders. In a violent move they fill with
  slippage, the same as anywhere.
- Coinbase is the data source and Hyperliquid is the venue. Their BTC prices track within
  a few basis points; the shadow fill model uses Coinbase's close and Hyperliquid's fee.
  Live mode uses Hyperliquid's own mid price for marks.
- Hyperliquid's terms exclude US residents.
