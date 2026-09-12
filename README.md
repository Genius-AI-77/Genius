# GENIUS

**Everyone is a Scientist.**

A market research lab built on AI agents, and the public site that reports what it finds.
This repository contains a working six-agent research pipeline, a paper broker with realistic
costs, a decision journal, and a static site + console — all runnable locally with no
dependencies beyond Python 3.

> **Status: pre-launch.** No token exists. No hardware has been bought. No real capital is
> deployed. Everything labelled *simulated* below is exactly that.

---

## Run it

Requires Python 3.9+. No packages to install.

```bash
python3 lab/run_demo.py --live   # real BTC-USD data + headlines, 33 sessions (~40s)
python3 serve.py                 # preview at http://localhost:4173/
```

`--live` pulls, with no API key: ~850 hourly candles, the recent trade tape (real
aggressor-side delta), a level-2 order-book snapshot, and headlines from public RSS
feeds. Each input fails soft to its synthetic/fixture fallback and the run records
exactly which inputs were real. Omit `--live` for a deterministic offline run.

Outputs:

| Path | What it is |
|---|---|
| `lab/output/journal.jsonl` | Every cycle, one JSON object per line — including no-trade cycles |
| `lab/data/*.jsonl` | Recorded tape, book and headlines (live only, gitignored, grows per run) |
| `site/console/data.js` | Metrics, equity curve, agent reports and input provenance for the site + console |

Run the tests:

```bash
python3 -m unittest discover -s lab/tests -t lab -v
python3 -m unittest discover -s desk/tests -t desk -v
```

---

## What's in here

```
lab/                      the research pipeline
├── genius_lab/
│   ├── data.py           market data — live candles/tape/book (Coinbase public) + synthetic
│   ├── news.py           live RSS headlines, lexicon-scored, time-gated
│   ├── agents.py         the six agent roles
│   ├── risk.py           the risk engine — hard limits, binding veto
│   ├── execution.py      paper broker with fees and slippage
│   ├── audit.py          decision journal and after-cost metrics
│   └── pipeline.py       orchestrator — one research cycle per bar
├── tests/                unit tests, including risk-limit enforcement
└── run_demo.py           entry point

site/                     the deployable folder (see DEPLOY.md)
├── index.html            landing page
└── console/index.html    lab console

desk/                     the live runner: three books, shadow or Drift, kill switch (see desk/README.md)

docs/
├── ARCHITECTURE.md       product synthesis, system design, agent contracts, stack
├── MVP-AND-ROADMAP.md    exact MVP scope, phases, completion criteria, content plan
├── COSTS.md              software, data, models, hardware, trading capital
├── DATA-AND-ORDERFLOW.md data sources, order-flow reference study, market-type limits
├── WALLET.md             wallet-connect security model — read-only, enforced by a build test
└── DECISIONS.md          what needs a decision from you before the next phase
```

---

## The six agents

| Agent | Role | Authority |
|---|---|---|
| **ATLAS** | Fundamental Analyst | advisory |
| **EUCLID** | Technical Analyst | advisory — owns the invalidation level |
| **FLUX** | Order Flow Analyst | advisory |
| **VETO** | Risk Manager | **binding** — approve or reject, no override path |
| **HERMES** | Execution Specialist | executes approved orders only |
| **LEDGER** | Research & Audit | reports; can raise a degradation flag |

Two rules sit above all six:

1. **"Do not trade" is a valid, recorded outcome.** In the reference run, 287 of 792 cycles
   ended in no trade. That is the system working, not failing.
2. **Agreement between agents is not evidence.** It is logged as context. Only the after-cost
   result counts.

And one architectural rule: **every number and every limit is computed in code.** A model may
interpret, summarise and investigate. A model may never set a position size, relax a limit, or
overrule the risk engine — there is no code path that would let it.

---

## Status legend

Used consistently across the code, the docs and the site.

| | Meaning |
|---|---|
| **IMPLEMENTED** | Working code in this repository, runnable today |
| **SIMULATED** | Working code driven by synthetic or fixture data |
| **PLANNED** | Designed, not built |
| **BLOCKED** | Needs an external dependency: a licence, funds, or a decision |

Current state:

- **IMPLEMENTED** — six-agent pipeline, risk engine and veto, paper broker with costs,
  decision journal, audit metrics, live market data (candles, trade tape, L2 depth),
  live news (RSS, lexicon-scored, time-gated), data recorder, daily GitHub Actions run,
  Solana wallet connect (read-only; transaction signing forbidden by a build test), strict
  CSP, site, console, 48 tests
- **SIMULATED** — the offline fallback for every live input (synthetic market, fixture
  headlines), used automatically when a feed is unreachable
- **PLANNED** — continuous (websocket) depth recording, footprint/replay tooling,
  walk-forward validation, multi-machine job distribution
- **BLOCKED** — LLM reasoning layer (needs an API key), licensed futures MBO data, the
  33-unit cluster, live execution with real capital, the $GENIUS token, the NVDA pair

**Honesty note on "AI agents":** today every agent is deterministic rules — good,
testable rules, but no language model runs anywhere in the pipeline. The LLM layer is
blocked on an API key and, when added, will *interpret* (read headlines, narrate
decisions); every number and limit stays in code.

---

## Deployment

`site/` is the entire public site: static HTML, no build step. See **[DEPLOY.md](DEPLOY.md)**
— drag-and-drop to Netlify Drop or Cloudflare Pages, plus an honest note on what Lovable can
and cannot do with it.

---

## Disclaimer

GENIUS is a research and community project. Nothing here is investment, financial, legal or
tax advice, an offer to sell, or a solicitation to buy any asset. All performance shown is
simulated on paper with no capital at risk; simulated results carry well-known biases and do
not predict real outcomes. Hardware described is proposed, not owned. NVIDIA, DGX and DGX
Spark are trademarks of NVIDIA Corporation; GENIUS is not affiliated with, endorsed by, or
partnered with NVIDIA. Digital assets are volatile and you can lose everything you put in.
