# GENIUS

**Everyone is a Scientist.**

A trading desk run by six AI agent roles, built in public. This repository holds the whole
thing: the research pipeline, the risk engine that can say no, the desk that trades on
Robinhood Chain from one wallet, and the site that reports every decision, losses included.

Live site: **https://geniusai77.xyz**

---

## How it works

Six roles, one cycle per hourly bar:

| Agent | Role | Authority |
|---|---|---|
| **ATLAS** | Fundamentals: headlines, regime, macro | advisory |
| **EUCLID** | Technicals: structure, levels, the invalidation price | advisory |
| **FLUX** | Order flow: tape, book, aggressor delta | advisory |
| **VETO** | Risk: hard limits in code | **binding**, no override path |
| **HERMES** | Execution: the only role that touches the wallet | executes approved orders only |
| **LEDGER** | Audit: journal, after-cost metrics, degradation flag | reports |

Three rules sit above all six:

1. **"Do not trade" is a valid, recorded outcome.** Most cycles end that way. That is the system
   working, not failing.
2. **Agreement between agents is not evidence.** It is logged as context. Only the after-cost
   result counts.
3. **Every number and every limit is computed in code.** A model may read, interpret and
   narrate. A model may never set a position size, relax a limit, or overrule the risk engine.
   There is no code path that would let it.

---

## The desk

`desk/` runs the six agents against a real venue. Details in [desk/README.md](desk/README.md).

- **Venue:** Uniswap v3 on Robinhood Chain (chain id 4663), called directly through the chain's
  public RPC. No trading API, no API key. Cash is USDG, the chain's dollar. The asset is set in
  config: ETH today, the NVDA stock token once its price feed is built.
- **One wallet.** The token's trade fees arrive in it, and HERMES trades from it. Every swap is
  a transaction anyone can open on [Blockscout](https://robinhoodchain.blockscout.com).
- **Three books**, one per analyst, isolated from each other, reconciled against the chain
  before every cycle. A mismatch halts the desk.
- **Pilot limits**, enforced by `lab/genius_lab/risk.py`: $1 at risk per trade, $3 daily loss
  per book then that book halts, no leverage, one position per book, long only.
- **Kill switch**: `run_desk.py --kill` flattens everything and blocks trading until a human
  resumes.
- **Modes:** `shadow` (paper fills at the live mark, nothing sent) and `live`.

---

## Run it locally

Python 3.9+ for the lab (no packages). The desk venue needs Python 3.10+ and `desk/requirements.txt`.

```bash
python3 lab/run_demo.py --live          # real ETH-USD candles, tape, book and headlines; paper run
python3 serve.py                        # preview the site at http://localhost:4173/
python3 desk/run_desk.py --once --offline --no-publish   # one desk cycle on a synthetic market
```

`--live` pulls, with no API key: hourly candles, the recent trade tape (real aggressor-side
delta), a level-2 order-book snapshot, and headlines from public RSS feeds. Each input fails
soft to its synthetic fallback and the run records exactly which inputs were real.

Tests (62, all offline):

```bash
python3 -m unittest discover -s lab/tests -t lab -v
python3 -m unittest discover -s desk/tests -t desk -v
```

They cover the risk limits in dollars, book isolation, the kill switch, state surviving a
restart, reconciliation halting on mismatch, secrets never reaching the published payload,
and the wallet-connect guard below.

---

## What's in here

```
lab/                      the research pipeline
├── genius_lab/
│   ├── data.py           market data: live candles, tape, book (Coinbase public) plus synthetic
│   ├── news.py           live RSS headlines, lexicon-scored, time-gated
│   ├── agents.py         the six agent roles
│   ├── risk.py           the risk engine: hard limits, binding veto, PILOT_100 and PRODUCTION
│   ├── execution.py      paper broker with fees and slippage
│   ├── audit.py          decision journal and after-cost metrics
│   └── pipeline.py       orchestrator, one research cycle per bar
├── tests/
└── run_demo.py

desk/                     the live runner (see desk/README.md)
├── run_desk.py           CLI: --once --loop --status --kill --resume --probe --init-cash --new-evm-wallet
├── set_ca.py             publishes the token contract address to the site after checking it on chain
├── config.json           mode, venue, asset, books, limits, publish targets (no secrets)
└── genius_desk/
    ├── evm_venue.py      Uniswap v3 on Robinhood Chain: quotes, swaps, stops, reconcile
    ├── venue.py          ShadowVenue (paper at the live mark) and optional venues
    ├── runner.py         the cycle, books, persistence, reconciliation, kill switch
    ├── publish.py        site payload plus git push (the host redeploys)
    └── config.py         config and secrets loading (secrets are never logged)

site/                     the public site: static HTML, no build step
├── index.html            landing page, token section, wallet connect
├── ca.js                 the contract address slot (blank until the token exists)
├── wallet.js             read-only wallet connect for Robinhood Chain
└── console/              the lab console and the published data.js

genius-web/               the same site as a React + Vite + Tailwind project

docs/                     design record: architecture, roadmap, costs, data, wallet security, decisions
```

---

## The site never touches your funds

The wallet connect on the site is read-only by construction. It can show your address, your
ETH balance on Robinhood Chain, your GENIUS balance, and ask your wallet to sign a message you
can read in full. It cannot request a transaction or a typed-data signature, so it has no way
to move funds or grant an allowance. `lab/tests/test_wallet_guard.py` enumerates the exact
wallet calls allowed and fails the build if any other appears anywhere in the front end. The
security headers only let the page talk to itself and the chain's RPC. Full model in
[docs/WALLET.md](docs/WALLET.md).

---

## Status legend

| | Meaning |
|---|---|
| **IMPLEMENTED** | Working code in this repository, runnable today |
| **SIMULATED** | Working code driven by synthetic or fixture data |
| **PLANNED** | Designed, not built |
| **BLOCKED** | Needs an external dependency: a licence, funds, or a decision |

- **IMPLEMENTED**: six-agent pipeline, risk engine and veto, paper broker with costs, decision
  journal, audit metrics, live market data (candles, tape, L2 depth), live news, data
  recorder, daily GitHub Actions run, the desk with the Uniswap venue on Robinhood Chain
  (verified against the chain: quotes, marks, signed swaps), read-only wallet connect,
  strict CSP, site, console, 62 tests
- **SIMULATED**: the offline fallback for every live input, used automatically when a feed is
  unreachable; shadow mode on the desk
- **PLANNED**: an on-chain candle feed for the NVDA stock token, continuous depth recording,
  walk-forward validation, multi-machine job distribution, the 33-unit cluster
- **BLOCKED**: the LLM interpretation layer (needs an API key)

**Honesty note on "AI agents":** today every agent is deterministic rules. Good, testable
rules, but no language model runs anywhere in the pipeline yet. When the LLM layer is added it
will interpret (read headlines, narrate decisions); every number and limit stays in code.

---

## Deployment

`site/` is the entire public site. See [DEPLOY.md](DEPLOY.md). The desk publishes
`site/console/data.js` and pushes; the host redeploys in about a minute.

---

## Disclaimer

GENIUS is a research and community project. Nothing here is investment, financial, legal or
tax advice, an offer to sell, or a solicitation to buy any asset. Results published by the desk
are small, early and can be negative on any given day; past results do not predict future
ones. Hardware described is a build target, not owned. NVIDIA, DGX and DGX Spark are trademarks
of NVIDIA Corporation; GENIUS is not affiliated with, endorsed by, or partnered with NVIDIA or
with Robinhood. Digital assets are volatile and you can lose everything you put in.
