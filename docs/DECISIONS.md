# Decisions Needed

> **Planning record.** Written in September 2026 before the venue was chosen. Kept as the history of how the decisions were made. The current setup (Robinhood Chain, Uniswap, one wallet) is in `README.md` and `desk/README.md`.

Everything below changes the implementation materially. Everything *not* below, I decided
myself and documented, those choices are reversible, and §3 lists them so you can overturn
any of them cheaply.

Ordered by how soon they block work.

---

## D1, Initial market and venue 🔴 *blocks Phase 1*

**Recommendation: BTC perpetual futures (or BTC-USD spot) on one major centralised venue.**

Free L2 depth and aggressor-tagged trades, a genuine order book so the order-flow toolkit is
actually valid, 24/7 hours that suit a 33-consecutive-day challenge, and enough depth that
our size never distorts the fills we simulate. Full reasoning in
`DATA-AND-ORDERFLOW.md` §3.

| Option | Consequence |
|---|---|
| **Crypto CEX** (recommended) | $0 data cost, immediate start, valid microstructure |
| CME futures | Best order-flow data available; $1k-5k/mo before any edge is shown, and publishing derived data may need a different licence tier |
| US equities | Fragmented across 16+ venues; market hours break the daily cadence |
| An AMM pair | Most order-flow concepts do not apply, see `DATA-AND-ORDERFLOW.md` §2 |

**What I need:** confirmation of the market, and which specific exchange. If you have an
existing account or jurisdictional constraint, that decides it.

---

## D2, Timeframe and cadence 🔴 *blocks Phase 1, drives cost*

Currently hourly bars. This choice sets the model bill more than any other:

| Cadence | Cycles/day | LLM cost/mo ⚠️ | Character |
|---|---|---|---|
| 1-hour | 24 | $10 to 80 | Swing; current default |
| 15-min | 96 | $40 to 320 | Intraday |
| 1-min | 1,440 | $600 to 4,800 | Scalping, the brief mentions this |

**Recommendation: start hourly, move down after Phase 3.** The brief points at scalping, and
that is where order flow is most informative, but scalping is also where execution costs
dominate, where slippage modelling has to be near-perfect, and where a modelling error is
most expensive. Prove the pipeline at a slow cadence where mistakes are cheap and visible,
then compress.

**What I need:** confirm hourly for now, or tell me you want to go straight to scalping and
accept the higher cost and tighter execution requirements.

---

## D3, Risk limits 🟡 *defaults are working, change is one line*

Current values, all enforced in `lab/genius_lab/risk.py`:

| Limit | Value | Rationale |
|---|---|---|
| Risk per trade | 0.5% of equity | Survives a 20-loss streak with ~10% drawdown |
| Daily loss limit | 2% → session halt | Roughly 4 consecutive full-risk losses |
| Gross exposure | 25% of equity | Caps damage from a gap through the stop |
| Consecutive losses | 3 → cooldown | Interrupts the regime the strategy is losing to |
| Committee confidence floor | 0.55 | |
| Minimum stop distance | 0.2% | Prevents stops inside noise |
| Concurrent positions | 1 | Removes correlation risk entirely at this stage |

These are conventional and conservative. Tighter is defensible; **looser needs a reason
written down**, because the whole credibility of the veto rests on limits not moving quietly
when they become inconvenient. Any change lands as a one-line diff with visible git history, that is deliberate.

**What I need:** approval, or specific values.

---

## D4, When paper becomes live 🟡 *not blocking, but decide the rule now*

**Recommendation: not before Phase 3 completes**, a demonstrated out-of-sample edge across
at least two market regimes.

The failure mode is well known and hard to resist: paper results look encouraging, real
capital goes in early, live costs turn out higher than modelled, and the strategy that
"worked" was inside the cost margin all along. The defence is deciding the criterion *now*,
while nothing is at stake.

**Also needs deciding:** who can authorise going live, and who can press the kill switch. My
recommendation is that both are you, named explicitly and published, because an unnamed
authority is not an authority.

**What I need:** agreement on the gate, and the named authority.

---

## D5, Hardware sequencing 🟡 *material spend*

**Recommendation: buy one or two DGX Sparks, not 33.**

One unit costs ~$4,000 and answers the question the full purchase assumes: what is our actual
cycles-per-second and cost-per-cycle on this workload? Full analysis in `COSTS.md` Bucket 4
and `ARCHITECTURE.md` §4.

Three specific things need saying plainly:

- **33 is a brand number, not an engineering one.** That is legitimate, it is memorable and
  it anchors the 33-Day Challenge, but if the workload needs four machines, the other 29 are
  a marketing expense and should be budgeted as one, not as compute.
- **They will not act as one supercomputer.** NVIDIA documents pairing *two* units over
  ConnectX-7. A 33-node fused machine is a different claim, needing a fabric, a distributed
  runtime, and a workload that benefits from it, which ours does not obviously do.
- **The real all-in figure is $153k-231k**, not $148.5k. Power, cooling, networking, racking
  and UPS add $21k-76k, plus $450 to 1,700/month in electricity.

**What I need:** approval for a 1 to 2 unit benchmark purchase, or a decision to defer hardware
entirely and use cloud/colocation until Phase 5.

---

## D6, The token 🔴 *highest-stakes decision here*

This is the one where my recommendation may not be what you want to hear, so here it is
directly.

**Recommendation: run the 33-Day Challenge *before* any token step.**

The reasoning:

1. **The Challenge doesn't need the token.** It costs under $200/month to run. There is no
   technical dependency in either direction.
2. **It is the strongest possible argument for the token.** 33 days of published, checkable
   research, including the losses, is a credential almost nothing else in this category
   has. Launching first spends that credibility before earning it.
3. **The sequencing is asymmetric.** Challenge-then-token loses nothing but time. Token-then-
   challenge means every subsequent honest disclosure, every losing day, every "the hardware
   isn't bought", now costs someone money, and the pressure to soften the reporting becomes
   structural rather than personal. The disclosure standard this whole project rests on is
   hardest to keep exactly when it matters most.
4. **Legal review is required either way**, and is cheaper before launch than after.

**Non-negotiable prerequisites**, whichever sequence you choose:

- Legal review in the relevant jurisdictions, token classification, the NVDA-tracker pair,
  and public claims about simulated results
- No presale, no allocation promises, no whitelist before that review completes
- The $GENIUS / NVDAx pair verified against the issuer's own documentation, not aggregators
  (`DATA-AND-ORDERFLOW.md` §5), and my recommendation there is that a deep stablecoin pair
  should be primary, with the NVDA pair secondary for narrative

**What I need:** your call on sequencing, and confirmation that legal review happens before
any token step.

---

## D7, LLM provider and role 🟢 *low stakes, easily reversed*

**Recommendation: LLMs interpret, code computes.** Models read news, summarise findings, and
explain decisions in language. Models never produce a number that reaches the risk engine.

This is already the architecture, the agents are rule-based, and the LLM layer is Phase 2.
Adding a model does not require changing anything else.

**What I need:** a provider preference, or leave it to me. Provider choice is a
configuration change, not an architectural one.

---

## D8, Publishing standard 🔴 *decide before Day 1, not during*

The site currently commits to publishing losing days at the same size and on the same
schedule as winning days, and to labelling everything implemented / simulated / planned /
blocked.

**This will be tested.** There will be a day when a loss is embarrassing, or when a status
label is inconvenient, and the cost of honesty will feel real.

**Recommendation: commit now, in writing, while it is free.** Specifically: no unpublishing,
no retroactive edits to past reports, corrections appended and dated rather than silently
applied, and the status ledger updated on the same day a status changes.

**What I need:** confirmation you want this standard held, including on the bad days.

---

## Decisions I already made (reversible, overturn any of these freely)

| Decision | Why | How to change it |
|---|---|---|
| Python stdlib only, no dependencies | Anyone can verify the run; nothing rots | Add a dependency any time |
| Rule-based agents first | Reproducible and free; verify the skeleton before adding a model | Phase 2 adds the LLM layer |
| Static HTML site, no framework | Zero build, instant load, drag-and-drop deploy | Rebuild in a framework if editing becomes the bottleneck |
| Hand-drawn SVG charts | A library is 100 KB for two line charts; palette is CVD-validated | Swap in a library any time |
| JSONL journal, no database | Human-readable, greppable, no server | Migrate at ~10M rows |
| Agent names (ATLAS, EUCLID, FLUX, VETO, HERMES, LEDGER) | Memorable, role-descriptive, brandable | Rename freely, they are strings |
| Dark / volt-green brand direction | Matches the reference material you provided | CSS variables in one block at the top of each page |
| One position at a time | Removes correlation risk while the pipeline is unproven | A risk-engine change, once Phase 3 justifies it |
| BTC as the demo instrument | Free data, deep, 24/7 | One function in `data.py` |
| Published run is a *losing* run | A lab that only shows winners is not a lab | Re-seed and cherry-pick, but I'd argue hard against it |
