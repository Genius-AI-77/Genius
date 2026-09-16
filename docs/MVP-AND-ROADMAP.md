# MVP Scope & Implementation Roadmap

> **Planning record.** Written in September 2026 before the venue was chosen. Kept as the history of how the decisions were made. The current setup (Robinhood Chain, Uniswap, one wallet) is in `README.md` and `desk/README.md`.

## 1. The MVP, precisely bounded

The MVP is **a lab that publishes verifiable research on a schedule.** Not a trading system,
not a token, not a cluster. Those come after, and only if this one earns them.

### In scope, and the parts already done

| # | Deliverable | Status |
|---|---|---|
| 1 | Six-agent pipeline with isolated roles | ✅ `IMPLEMENTED` |
| 2 | Risk engine with binding veto, enforced in code | ✅ `IMPLEMENTED` |
| 3 | Paper broker charging fees + slippage on every fill | ✅ `IMPLEMENTED` |
| 4 | Append-only decision journal, including no-trade cycles | ✅ `IMPLEMENTED` |
| 5 | After-cost audit metrics + degradation flag | ✅ `IMPLEMENTED` |
| 6 | Public site with an honest status ledger | ✅ `IMPLEMENTED` |
| 7 | Lab console rendering real run output | ✅ `IMPLEMENTED` |
| 8 | Test suite proving the risk limits hold | ✅ `IMPLEMENTED` |
| 9 | Live market data from a real venue | ✅ `IMPLEMENTED`, candles, tape, L2 book |
| 10 | L2 depth recorder (start the archive) | ✅ `IMPLEMENTED`, per-run snapshot; streaming planned |
| 11 | Scheduled daily run + auto-published report | ✅ `IMPLEMENTED`, GitHub Actions, no servers |
| 12 | Walk-forward validation on real out-of-sample data | ⬜ `PLANNED`, Phase 2 |

### Explicitly out of scope for the MVP

Naming these matters as much as naming what's in, because each one is a plausible-sounding
detour that would delay the only thing that proves the project real:

- Live execution with real capital
- Any token: no contract, no launch, no presale, no allocation, no whitelist
- Hardware purchases of any kind
- The LLM reasoning layer *(Phase 2, the rule-based skeleton must be verified first)*
- Multi-machine distribution
- Mobile app, user accounts, notifications
- Any market beyond the single chosen instrument

### The MVP's completion criterion

> **33 consecutive daily public reports, generated from the journal, each stating the
> hypothesis, the agents' positions, the risk decision, and the after-cost result, including
> the days that lost money and the days with no trade at all.**

Note what this criterion does *not* mention: profit. The MVP succeeds if the lab
demonstrably runs and reports honestly. Whether the strategy makes money is the *next*
question, and conflating the two is how research projects turn into promises.

---

## 2. Phased plan

Each phase has an explicit completion test. A phase is not "done" because the work happened;
it is done when the test passes.

---

### Phase 0, Foundation ✅ **COMPLETE**

Working pipeline, risk engine, paper broker, journal, site, console, tests.

**Completion test:** `python3 lab/run_demo.py` produces a full journal and populated console;
`python3 -m unittest discover -s lab/tests -t lab` passes. ✅ *26 tests passing.*

**What it proved:** the architecture holds. Risk limits enforced across 792 cycles with zero
breaches. 287 no-trade cycles recorded. Costs were 23% of the loss, a number invisible
without after-cost accounting.

---

### Phase 1, Real data ✅ **COMPLETE (REST variant)**

Synthetic inputs replaced with a real venue. The agents did not change; only what they read.

1. ✅ Coinbase public REST: ~850 hourly candles paged back for 33 full sessions
2. ✅ Trade tape with correct aggressor mapping (maker-side → taker inverted), overlaid
   onto the bars it fully covers, ~80k trades per run, the last ~5 hourly bars get real delta
3. ✅ Level-2 book snapshot trimmed to ±2% of mid; FLUX reads spread, depth imbalance, walls
4. ✅ Recorder persists tape / book / candles / headlines per run to `lab/data/`
5. ✅ ATLAS reads live RSS headlines (3 to 4 public feeds), lexicon-scored, time-gated
6. ✅ Provenance in run metadata: exactly which inputs were real, surfaced on the site

**Completion test passed:** a full 33-session run on live data with all four inputs real,
no synthetic fallback triggered, recorded data on disk, 42 tests green.

**Deliberately deferred, the websocket variant.** The plan called for a streaming L2
client with book reconstruction and resync. REST snapshots get real depth into the
pipeline today with zero moving parts; streaming adds *continuous* depth history, which
matters for replay and absorption studies, not for the daily run. It stays `PLANNED` and
the resync-path warning still applies when it is built.

---

### Phase 2, Publish on a schedule *(in progress)*

This phase produces the MVP's completion criterion.

1. ✅ Daily run, GitHub Actions (`.github/workflows/daily-run.yml`): tests → live run →
   commit `data.js` → host redeploys. No VPS needed after all; zero cost, zero servers.
2. ⬜ Report generator: journal → dated Markdown/HTML, fully automated
3. ⬜ Console shows a run history, not just the latest run
4. ⬜ Walk-forward validation: strict train/test split, out-of-sample only
5. 🔴 LLM layer for *narration and news reading only*, **blocked on an API key**
6. ⬜ Day-1 report published

**Completion test:** 33 consecutive daily reports, published without manual intervention,
each traceable to a journal entry. A reader can pick any claim and check it against the
raw journal.

**The rule that makes this worth anything:** losing days are published on the same schedule
and at the same prominence as winning days. The moment that stops being true, the project is
marketing.

---

### Phase 3, Validate the edge *(≈3 to 6 weeks, gated on Phase 2)*

Only start when there is a public track record to attach results to.

1. Multiple hypotheses in parallel, isolated per strategy
2. Discovery / Validation separation enforced by **data access**, not convention
3. Ablations that actually answer questions:
   - one model, six prompts vs. six specialised models
   - does FLUX add anything over EUCLID alone?
   - does ATLAS's bias correlate with forward returns at all?
4. Parameter-sensitivity and overfitting checks
5. Cost sensitivity: at what fee/slippage level does the edge vanish?

**Completion test:** at least one strategy with positive after-cost expectancy on
out-of-sample data across ≥2 market regimes, with a documented reason it should work that
is not "the backtest says so."

**Gate:** if this fails, the honest outcome is publishing that it failed and iterating, not proceeding to Phase 4. Phase 4 without Phase 4's prerequisite is how people lose money.

---

### Phase 4, Live execution *(gated on Phase 3, and on decisions D1-D4)*

1. Venue selection, API keys, IP allowlisting
2. Exchange-side limits mirroring the internal ones, **defence in depth**
3. Small live capital, treated as fully at risk
4. Reconciliation: our journal vs. exchange fills, every session
5. A documented, published kill switch and who can press it

**Completion test:** 30 sessions live, zero limit breaches, zero reconciliation
discrepancies, and realised slippage within the modelled range.

**Do not skip:** running live with the same size as paper, but for a short period, to
measure the paper-to-live gap before it matters.

---

### Phase 5, Infrastructure *(gated on a workload that needs it)*

1. Benchmark the real workload on **1 to 2** DGX Sparks before buying 33
2. Measure: cycles/second, cost per cycle, thermal behaviour under sustained load
3. Job-queue distribution across nodes (independent workers, not one fused machine)
4. Only then size the purchase, against measured demand, not the brand number

**Completion test:** a measured cost-per-research-cycle that justifies capex over cloud
rental, with the arithmetic published.

---

### Phase 6, Token *(gated on D6, and on a real public record)*

Deliberately last. Everything the token would point at must exist first, or the token points
at nothing.

Prerequisites, all of them: legal review complete; the public record is real and
independently checkable; the honest-disclosure standard has held under pressure; liquidity
plan and pair structure decided (see `DATA-AND-ORDERFLOW.md` §5).

---

## 3. Public content plan

Sequenced to match what actually exists at each point. Each piece can only ship once its
subject is real.

| # | Piece | Ships when | Core message |
|---|---|---|---|
| 1 | **Everyone is a Scientist.** | Now | The thesis: markets as a place to run experiments, not to be right |
| 2 | **Meet the machine.** | Now | The proposed architecture, labelled proposed, with the open questions named |
| 3 | **Six minds. Different responsibilities.** | Now | Why role isolation beats one model asked to "trade well" |
| 4 | **How GENIUS reads a market.** | Now | The cycle, end to end |
| 5 | **The agent that can say no.** | Now | The veto is arithmetic. Show the code. This is the credibility piece. |
| 6 | **Our first public experiment.** | Now | Published including the loss, the piece that sets the standard |
| 7 | **What $GENIUS represents.** | Before any token discussion | What it is and is not, in plain words |
| 8 | **The 33-Day Challenge.** | Phase 2 start | A commitment to publication, not to profit |

All eight are live on the site today, sections 01 to 09.

**The editorial rule:** every piece names what is implemented, simulated, planned or blocked.
The status ledger is not a legal footnote, it is the product. A lab that publishes only its
wins is not a lab, and an audience that discovers the gap later is an audience you have lost
permanently.

---

## 4. Sequencing of the public commitments

The brief lists five milestones. The dependency order matters, and one of them is commonly
run out of order with expensive results:

```
Public experiment & validation
        │
        ▼
Token definition & presentation      ← definition only; no launch
        │
        ▼
Launch under documented conditions   ← gated on legal + a real record
        │
        ├──────────────┐
        ▼              ▼
Infrastructure    The 33-Day Challenge
   expansion       (can run in parallel, it needs no token)
```

**The 33-Day Challenge does not require the token.** It is the strongest possible argument
*for* the token, and it costs almost nothing to run first. Running it before launch is the
single highest-leverage sequencing decision available.
