# GENIUS Desk: the live runner

Takes the lab's six agents to a real venue. Three analyst books (ATLAS, EUCLID, FLUX),
one gate (VETO), one signer (HERMES), one auditor (LEDGER). One cycle per hourly bar.

```
desk/
├── run_desk.py         CLI: --once --loop --status --kill --resume --probe --init-cash --new-evm-wallet
├── set_ca.py           publish the token contract address to the site after checking it on chain
├── config.json         mode, venue, asset, books, limits, publish targets (no secrets)
├── install.sh          one-shot Ubuntu server install (systemd service + CLI)
├── requirements.txt    eth-account (Robinhood Chain venue); solders and hyperliquid-python-sdk optional
├── genius_desk/
│   ├── config.py       config + secrets loading (secrets never logged)
│   ├── evm_venue.py    UniswapVenue: Uniswap v3 on Robinhood Chain, raw JSON-RPC, signed locally
│   ├── venue.py        ShadowVenue (paper at the live mark) + HyperliquidVenue (optional)
│   ├── solana_venue.py SolanaVenue (optional, Jupiter spot)
│   ├── runner.py       the cycle, books, persistence, reconciliation, kill switch
│   └── publish.py      site payload + git push (the host redeploys)
├── tests/              13 offline tests: limits, isolation, kill, restart, reconcile, secrets
├── state/              runtime state + journal (gitignored)
└── data/               recorded tape, book, headlines (gitignored)
```

## The venue: Uniswap v3 on Robinhood Chain (`"venue": "uniswap"`)

One 0x wallet does two jobs: it receives the GENIUS token's trade fees, and HERMES trades
from it. Nothing bridges anywhere.

| | |
|---|---|
| Chain | Robinhood Chain, chain id 4663, public RPC `rpc.mainnet.chain.robinhood.com` |
| Explorer | https://robinhoodchain.blockscout.com |
| Cash | USDG (Global Dollar), the chain's dollar |
| Asset | `"asset"` in config: `WETH` (default) or `NVDA` (the Robinhood stock token) |
| Pool | Uniswap v3, fee tier `"pool_fee"` (500 = 0.05 %) |
| Contracts | v3 Factory, QuoterV2 and SwapRouter02 from developers.uniswap.org/deployments, verified on chain |
| Signing | `eth_account`, on the machine running the desk; the key never leaves the secrets file |
| Gas | ETH. The desk keeps 0.002 ETH back and never swaps it |

Every entry is `USDG -> asset`, every exit `asset -> USDG`, through `exactInputSingle` with a
quote from QuoterV2 and a slippage floor. P&L is exact: the USDG actually spent and actually
received, read from balances before and after each swap. Spot has no exchange-side stops, so
the loop checks stops every minute and swaps out. Long only; a short read stands aside.

## Modes

| Mode | What HERMES does | How to enter |
|---|---|---|
| **shadow** | Computes every order and fills it on paper at the live mark with the venue's fee model. Sends nothing. | `"mode": "shadow"` |
| **live** | Real swaps on Uniswap from the desk wallet. | `"mode": "live"` in config.json, `DESK_EVM_KEY` in secrets |
| **halted** | Kill switch pulled. Everything flattened, nothing trades until a human resumes. | `run_desk.py --kill` |

## Pilot limits

Set by `"limits": "PILOT_100"` in config.json, defined in `lab/genius_lab/risk.py`:

| Limit | Value |
|---|---|
| Risk per trade | $1 (at the stop) |
| Daily loss per book | $3, then that book halts for the day |
| Leverage | none: notional never exceeds the book's equity |
| Positions per book | 1 |
| Confidence floor | 0.50 |
| Lot size | `order_step` / `min_order` in config; smaller sizes are vetoed, not rounded up |

When the wallet grows, switch `"limits"` to `"PRODUCTION"` (percentages).

## Setting up, in order

1. **Create the wallet on the machine that will run the desk.** Nothing is pasted, nothing is
   printed but the public address:

   ```bash
   python3 desk/run_desk.py --new-evm-wallet
   ```

   The key goes into `~/.genius-desk/secrets.env` (mode 600) as `DESK_EVM_KEY`. Back that file
   up; it is the only copy. Set the printed address as the token's fee receiver.

2. **Secrets.** The same file also takes the push token so each cycle can publish:

   ```
   DESK_EVM_KEY=<written by --new-evm-wallet>
   DESK_GIT_REMOTE=https://x-access-token:<token>@github.com/<user>/<repo>.git
   ```

3. **Wait for fees.** Fees arrive as ETH. The desk cannot trade an empty wallet; `--probe`
   and `--once` refuse cleanly until there is a balance.

4. **Adopt the money.** Wraps spare ETH above the gas reserve, sells it for USDG, splits it
   equally across the three books. Run it again whenever new fees have landed.

   ```bash
   python3 desk/run_desk.py --init-cash
   ```

5. **Prove the wiring.** One tiny round trip on the first book, journaled as a system probe,
   never as an agent trade. Prints two explorer links.

   ```bash
   python3 desk/run_desk.py --probe
   ```

6. **Run.**

   ```bash
   python3 desk/run_desk.py --loop
   ```

   On a server: `bash desk/install.sh` installs a systemd service and the `genius-desk`
   CLI (`once`, `start`, `logs`, `status`, `kill`, `resume`).

## Local dry run (no wallet, no network)

```bash
python3 desk/run_desk.py --once --offline --no-publish
python3 desk/run_desk.py --status
python3 -m unittest discover -s desk/tests -t desk
```

## Publishing the contract address

```bash
python3 desk/set_ca.py 0x<contract>          # checks it is a deployed ERC-20 on Robinhood Chain, writes, commits, pushes
python3 desk/set_ca.py --fee-wallet 0x<wallet>   # publishes the agents' wallet row
python3 desk/set_ca.py --clear
```

The site hides every token element while `site/ca.js` is blank, so the address appears
everywhere at once, about a minute after the push.

## The kill switch

```bash
python3 desk/run_desk.py --kill
```

Flattens every book at market and sets a halt flag that survives restarts. The loop keeps
running but trades nothing. `--resume` clears it. Both are human actions; nothing automated
can resume the desk.

The desk also halts itself when:
- a book's daily loss limit is hit (that book only, until the next UTC day),
- **reconciliation fails**: the chain holds less than the books say they own, or the wallet
  has no ETH left for gas. This is the "something is wrong" signal and it always wins.
- the asset token reports itself paused by its issuer (stock tokens can be); the desk stands
  aside rather than send a swap that would revert.

New fee income makes the chain richer than the books; that is reported, not treated as a
mismatch, because `--init-cash` is the deliberate step that adopts it.

## What to check if something looks off

| Symptom | Look at |
|---|---|
| Site shows stale desk | logs for `publish_error`; is `git_push` true; is the token valid |
| A book stopped trading | `--status`: halted? cooldown after 3 losses? daily loss hit? |
| Everything halted | journal `halt` entry with the reason; fix the cause, then `--resume` |
| A swap reverted | open the `tx` on Blockscout; usual causes are slippage past the floor or a paused token |
| Runner died | `systemctl status genius-desk`; it restarts itself in 30 s and re-checks stops first |

## Honest notes

- The Uniswap venue has been exercised against Robinhood Chain mainnet from this repo with a
  throwaway key: pool discovery, marks from `slot0`, quotes both ways, allowance check, a
  fully built and signed swap that the chain refused for lack of gas. The first *filled* swap
  is `--probe` on the funded wallet.
- Coinbase is the data source (ETH-USD) and Uniswap on Robinhood Chain is the venue. Marks
  come from the pool itself; the shadow fill model uses Coinbase's close and the pool fee.
- The NVDA stock token is tradable by any wallet (blocklist model, not allowlist) and its
  USDG pool is deep, but Coinbase has no candles for it. Switching `"asset"` to `NVDA` works
  today for execution; the analysts need an on-chain candle feed first, which is planned.
- Public RPC endpoints are rate-limited. For a server, set `DESK_RPC_URL` to a dedicated one.
- Optional venues: `solana_venue.py` (Jupiter spot) and `HyperliquidVenue` remain in the tree
  and are selectable with `"venue": "solana"` or `"hyperliquid"`; they are not the default
  and are not what the site describes.
