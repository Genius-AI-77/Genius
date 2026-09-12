# GENIUS — Product & Architecture

## 1. What the product actually is

Strip away the token and the hardware and GENIUS is one thing: **a machine that produces
auditable research about markets, in public, on a schedule.**

Everything else is a layer around that core.

| Layer | Purpose | Depends on |
|---|---|---|
| **Research engine** | Forms hypotheses, tests them, records the outcome after costs | Data, compute |
| **Risk envelope** | Makes failure survivable and bounded | Nothing — it's arithmetic |
| **Public record** | Turns the engine's output into something people can read and check | The engine |
| **Community / token** | Distributes attention and coordination around the public record | The public record being real |

The order matters. The token is downstream of the public record, which is downstream of the
engine. A token launched before there is anything to report is a different product with a
different risk profile — and it is the failure mode this architecture is designed to avoid.

### What is validated today

- A six-role agent pipeline produces different, non-redundant analyses of the same bar.
- Hard risk limits, enforced in code, hold across 792 consecutive cycles with zero breaches
  (proven by the test suite, not asserted).
- "No trade" as a first-class outcome is achievable — 287 of 792 cycles, or 36%.
- After-cost accounting materially changes the picture: costs were $640 against a $2,742
  loss, i.e. 23% of the damage was friction, not being wrong.

### What is not validated

| Claim | Status | What would validate it |
|---|---|---|
| The strategy has positive edge | **Unproven — currently negative** | Walk-forward on real data across regimes |
| 33 DGX Sparks are the right architecture | **Unproven** | Benchmark 1–2 units against the actual workload |
| 33 units act as one supercomputer | **Probably false as stated** | See §4 |
| Six roles need six models | **Probably false** | Ablation: one model, six prompts vs. six models |
| Order flow gives edge on our chosen market | **Unproven** | See `DATA-AND-ORDERFLOW.md` |
| A token improves the project's outcome | **Untested, and a real risk** | See `DECISIONS.md` D6 |

---

## 2. Architecture, in plain terms

The system is a loop. Each turn of the loop is a **cycle**, and a cycle is one bar of market
data.

```
   market data
        │
        ▼
 ┌─────────────┐
 │  CONTEXT    │  the same immutable snapshot for every agent
 └──────┬──────┘
        │
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
   ┌────────┐    ┌──────────┐   ┌──────────┐
   │ ATLAS  │    │  EUCLID  │   │   FLUX   │     independent, parallel,
   │ (fund) │    │  (tech)  │   │  (flow)  │     no shared scratchpad
   └───┬────┘    └────┬─────┘   └────┬─────┘
       └──────────────┼──────────────┘
                      ▼
              ┌───────────────┐
              │  COMMITTEE    │  a pure function: three reports → proposal | None
              └───────┬───────┘
                      ▼
              ╔═══════════════╗
              ║  RISK ENGINE  ║  ◄── no model. arithmetic only. terminal authority.
              ╚═══════┬═══════╝
              approve │ reject
                      ▼
              ┌───────────────┐
              │    HERMES     │  fills, with fees and slippage charged
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │    LEDGER     │  journals the cycle — trade or not — and scores it
              └───────────────┘
```

Three design decisions carry most of the weight.

### 2.1 Agents are isolated, not collaborative

ATLAS, EUCLID and FLUX never see each other's output. They cannot converge, defer, or
anchor on one another. This is deliberate: the value of six perspectives comes entirely
from their independence, and a shared scratchpad destroys it. Three correlated opinions
presented as a consensus is *worse* than one opinion, because it carries false confidence.

The committee that combines them is a **pure function**, not an agent. It is readable in
twenty lines, it is deterministic, and it can be argued about.

### 2.2 The risk engine contains no model

This is the architectural claim the whole project rests on, so it is worth stating precisely:

> **A language model can propose a direction and a level. It can never propose a size, relax
> a limit, or overrule a rejection — because no code path exists that would accept such an
> instruction.**

Position size is *derived*: `qty = (equity × max_risk) / distance_to_invalidation`. No agent
submits a quantity, so no agent can inflate one. The engine's public API has no `override`,
`force`, or `bypass` — and a test asserts that it never grows one.

This is not a prompt-engineering pattern. There is nothing to jailbreak, because there is
nothing listening.

### 2.3 Everything is journaled, especially the nothing

Every cycle writes a JSONL entry: the price, all six stances, the decision, the reason, and
the risk verdict. A no-trade cycle is as fully recorded as a trade. This means:

- The strategy's *selectivity* is measurable, not anecdotal.
- Post-hoc analysis can ask "what did we decline, and would it have worked?"
- The public reports are generated from the journal, so they cannot drift from what happened.

---

## 3. The six agents — contracts

Each agent implements one method, `analyze(context) → AgentReport`, and is scored on one
question. The uniform contract is what lets roles be swapped, ablated, or run on different
hardware without touching the orchestrator.

| Field | Meaning |
|---|---|
| `stance` | `long` \| `short` \| `flat` — `flat` is a real answer |
| `confidence` | 0–1, advisory only; the engine has a floor, not a multiplier |
| `findings` | Human-readable, source-attributed where applicable |
| `invalidation` | Price that voids the thesis. **Only EUCLID sets this.** |
| `data` | Structured numbers backing the findings |
| `status` | `IMPLEMENTED` \| `SIMULATED` — surfaced in the UI |

### ATLAS — Fundamental Analyst
- **In:** news, macro calendar, filings, asset-level events
- **Out:** directional bias with cited events, each carrying a source and a date
- **Scored on:** bias vs. forward return; unsourced claims are counted as errors
- **Today:** `SIMULATED` — fixture events. A licensed feed is the first real dependency.

### EUCLID — Technical Analyst
- **In:** OHLCV history
- **Out:** trend classification, swing levels, RSI/SMA context, and **the invalidation price**
- **Scored on:** level hit rate; how often price actually respected the stated invalidation
- **Note:** EUCLID owns invalidation because position size is derived from it. This makes
  EUCLID's accuracy directly load-bearing on risk, which is why it is scored separately.

### FLUX — Order Flow Analyst
- **In:** trades with aggressor side, volume-by-price, L2 depth *(depth is `PLANNED`)*
- **Out:** cumulative delta across two horizons, volume point of control, absorption candidates
- **Scored on:** flow signal vs. next-bar continuation
- **Honest limitation:** without true L2 depth, "absorption" is inferred from volume-with-
  compressed-range, which is a proxy, not the real thing. See `DATA-AND-ORDERFLOW.md`.

### VETO — Risk Manager *(binding)*
- **In:** proposal, equity, open risk, session P&L, loss streak
- **Out:** `APPROVE(qty, stop)` or `REJECT(reason)`
- **Scored on:** limit breaches. Target is zero. Any non-zero value is an incident, not a metric.

### HERMES — Execution Specialist
- **In:** approved order, book conditions
- **Out:** fills with fees and slippage charged against the decision price
- **Scored on:** realised slippage vs. decision price — the cost of being right

### LEDGER — Research & Audit Analyst
- **In:** the full journal, fills, outcomes
- **Out:** after-cost expectancy, win rate, drawdown, and degradation flags
- **Scored on:** did it flag decay before the equity curve made it obvious?
- **Authority:** LEDGER cannot block a trade, but its flag is published. Social pressure is
  the enforcement mechanism, and that is intentional — an audit function that can act is no
  longer an audit function.

---

## 4. The 33-machine question, honestly

The proposal is 33 NVIDIA DGX Spark units in three columns of eleven, six agent roles each,
198 roles total. Three things about that need separating.

**The number 33 is a brand decision, not an engineering one.** That is fine — it is memorable,
it maps to the 33-Day Challenge, and 3×11 is a good visual. But it should be recognised as a
constraint chosen for narrative reasons, and the engineering should be sized independently.
If the workload needs 4 machines, buying 33 is a marketing expense, and should be budgeted
as one.

**"33 machines as one supercomputer" is not how these work.** NVIDIA documents pairing *two*
DGX Sparks over ConnectX-7 to share 256 GB and run larger models. That is a documented
two-node configuration, not evidence of an N-node fabric. Scaling to 33 nodes would need a
high-speed switch, a distributed runtime, and a workload that actually benefits from
model-parallelism across nodes.

Our workload does **not** obviously benefit from that. Six agents analysing a bar is an
*embarrassingly parallel* problem: many independent small jobs, not one huge model. The
right mental model is:

> **33 independent workers pulling from a shared job queue** — not one machine with 33× the memory.

That is far easier to build, far easier to scale incrementally, and degrades gracefully when
a node dies. It also means you can start with one node and add more without re-architecting.

**Six roles does not mean six models.** Role separation is a matter of system prompt, tool
access and permissions. One model serving six roles sequentially is the cheap default; six
*specialised* models is a hypothesis to test, not an assumption to build on. The ablation is
easy and should happen before any hardware is bought.

### Recommended department mapping

Keeping all six roles in each department, but with different objectives, avoids duplicated
analysis:

| Department | Nodes | Runs on | Six roles adapted to |
|---|---|---|---|
| **Discovery** | 11 | Historical + live, no execution | Generating candidate hypotheses; FLUX mines flow patterns, LEDGER catalogues what's been tried |
| **Validation** | 11 | Historical replay only, out-of-sample | Trying to *kill* hypotheses; VETO runs stress scenarios, HERMES models fill realism |
| **Operations** | 11 | Live data, approved strategies only | Monitoring and executing; VETO is the live gate, LEDGER produces the daily public report |

The anti-duplication rule: **Discovery may not see Validation's out-of-sample window.** If it
does, the whole validation step becomes theatre. This is a data-access boundary, and it
should be enforced by which node can read which dataset — not by convention.

---

## 5. Stack, and why

The guiding principle: **the demonstrable product should have as few dependencies as
possible, so it keeps working.** Complexity gets added only where it buys something.

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| **Research engine** | Python 3.9+, stdlib only | Zero install friction; anyone can verify the run. Pandas/NumPy add real value at scale but not yet — and every dependency is a reason the demo breaks a year from now. |
| **Agents (now)** | Deterministic rules | Reproducible, free, testable. You cannot debug an LLM pipeline whose non-LLM parts are also unverified. Get the skeleton right first. |
| **Agents (next)** | LLM as *interpreter*, rules as *computer* | The model reads news and explains findings; the numbers stay in code. This bounds cost and eliminates hallucinated arithmetic. |
| **Risk** | Pure functions, no I/O, no model | Testable in isolation, provably terminal. |
| **Storage** | JSONL append-only | Human-readable, greppable, git-diffable, no server. A database is the right answer at ~10M rows, not now. |
| **Site & console** | Static HTML/CSS/vanilla JS | No build step, no framework churn, deploys by drag-and-drop, loads instantly, and cannot break from a dependency update. |
| **Charts** | Hand-drawn SVG | A charting library is ~100 KB for two line charts. The palette is validated for colour-vision deficiency; a library's defaults are not. |
| **Hosting** | Netlify Drop / Cloudflare Pages | Free tier, global CDN, automatic TLS, drag-and-drop. See `DEPLOY.md`. |
| **Scheduling (next)** | One small VPS + cron | The 33-Day Challenge needs a daily run. This is a $6/month problem, not a Kubernetes problem. |

### What we deliberately did not use

- **A frontend framework** — the site is content, not an application.
- **A charting library** — two line charts.
- **A vector DB / RAG stack** — there is no corpus yet. Adding retrieval before having
  documents worth retrieving is architecture theatre.
- **An agent framework** — the orchestration is ~150 lines and we need exact control over
  who sees what. Frameworks optimise for agents *sharing* context; our core requirement is
  that they *don't*.
- **A database** — see above.

Each of these is a reasonable *later* decision. None of them is a *now* decision, and adding
them now would make the system harder to verify without making it better.

---

## 6. Extension points

Built so the next phases don't require rewrites:

- **`data.py`** — one function returns `list[Candle]`. A new venue is a new function.
- **`agents.py`** — add a role by implementing `analyze(ctx) → AgentReport`.
- **`pipeline.py`** — `_form_proposal` is the committee rule, isolated and replaceable.
- **`risk.py`** — limits are module constants; changing one is a one-line diff with a
  visible git history. That is deliberate: **risk limits should be hard to change quietly.**
- **`Lab`** — instantiating multiple `Lab` objects with different seeds or committee rules is
  how the Discovery/Validation split will be implemented, and how the 33-node job queue will
  distribute work.
