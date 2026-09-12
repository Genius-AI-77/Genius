# Data Sources, Order Flow, and Market Structure

## 1. The order-flow reference study

The brief names **DeepCharts** as a functional reference for footprint, delta, volume
profile, DOM, replay and liquidity analysis. This section separates what that reference
tells us from what we can actually build.

### What DeepCharts is, from public sources

DeepCharts is an order-flow platform built by Volumetrica Trading, aimed at professional
futures traders. Publicly documented capability includes footprint charts ("Deep Prints"),
volume and delta profiles, a DOM ladder with historical order tracking, 80+ indicators, and
proprietary studies. It connects to **Rithmic, dxFeed and CQG** for data, and covers CME and
EUREX instruments. It ingests **Market-By-Order (MBO)** data — the raw per-order exchange
feed, as opposed to aggregated price-level data.

### What that means for us — three separate buckets

**A. Functionality we can build ourselves with data we can license or obtain freely.**

These are not proprietary techniques. Footprint charts, delta, volume profile, VWAP and
cumulative delta are published, decades-old methods described openly in trading literature.
The work is engineering, not access.

| Capability | Data needed | Availability to us |
|---|---|---|
| Volume-by-price / profile / POC | Trades with price + size | **Free** on crypto venues |
| Delta & cumulative delta | Trades with aggressor side | **Free** on crypto venues |
| Footprint (bid/ask per price level) | Aggressor-tagged trades bucketed by price | **Free** on crypto venues |
| DOM ladder (current depth) | L2 order book snapshots/diffs | **Free** via crypto websockets |
| Depth heatmap over time | L2 stream, persisted | Free feed, **our storage cost** |
| Replay | Any of the above, recorded | Our storage cost |
| Absorption detection | Trades + depth, jointly | Free feed, our modelling |

**B. Functionality that requires a vendor or a licence.**

| Capability | Why it's gated |
|---|---|
| CME / EUREX futures order flow | Exchange market-data licensing + a vendor (Rithmic, dxFeed, CQG, Databento). Non-display and redistribution fees apply, and **publishing derived charts publicly can change which licence tier you need.** |
| True MBO (per-order queue position) | Only some venues publish it; it is the premium tier where it exists |
| US equities consolidated depth | Fragmented across 16+ venues; full depth means many feeds |
| Historical tick/L2 archives | Vendors (Tardis, Databento, Kaiko) — meaningful monthly cost |

**C. Integrations that actually exist.**

To be explicit, because this is the kind of claim that quietly becomes a lie:

> **We have no API access to, partnership with, integration with, or relationship of any kind
> with DeepCharts or Volumetrica Trading.** Public sources do not document a public DeepCharts
> API. We use it the way you use any published product: as evidence of *which capabilities
> matter to serious practitioners*. No proprietary technology is copied, and no integration
> is implied anywhere in our materials.

What *is* available to us are the same **underlying data vendors** — Rithmic, dxFeed, CQG,
Databento — which we can license directly if and when futures become the target market.
That is the real dependency, and it is a commercial one, not a technical one.

---

## 2. Order-flow analysis does not transfer equally across markets

This is the most important technical section in the document, because getting it wrong means
building sophisticated tooling that measures nothing.

Order-flow analysis assumes a specific market structure: **a central limit order book, where
passive resting orders wait and aggressive orders consume them.** Every concept —
absorption, exhaustion, trapped traders, delta divergence — is a statement about the
interaction between those two populations. Where that structure is absent or fragmented, the
concepts do not simply get harder to measure. Some of them stop existing.

### Centralised futures (CME, EUREX) — the ideal case

One venue, one book, all the volume. MBO data reveals individual order placement, pulling
and filling. Delta is unambiguous because every trade has a definite aggressor. Absorption is
directly observable: a large resting order that does not move while volume hits it.

*Cost:* licensing, and it is the highest of any option here.

### Centralised crypto (Binance, Coinbase, Bybit, OKX) — very good, with caveats

Free websocket access to L2 depth and trades, and trades carry the aggressor side. Structurally
this is a real CLOB and the concepts transfer directly.

Caveats that matter:
- **Fragmentation.** Delta on one exchange is not global delta. BTC trades meaningfully on
  a dozen venues plus perpetual futures. A single-venue read is a sample, not a census.
- **No true MBO on most venues.** Depth is aggregated per price level, so queue position is
  invisible. Spoofing and layering are hard to distinguish from genuine interest.
- **Data quality.** Wash trading and self-matching distort volume on some venues; incentive
  structures around maker rebates can manufacture flow that means nothing.
- **Perpetual futures** carry funding-rate dynamics that create flow unrelated to directional
  conviction.

### US equities — possible, expensive, structurally incomplete

Fragmented across 16+ lit exchanges plus dark pools and internalisers. The consolidated tape
(SIP) gives trades but not full depth. A substantial share of volume executes off-exchange
and is reported with less granularity. Building a complete order-flow picture means
subscribing to many feeds and reconstructing the book yourself.

### AMM liquidity pools (Uniswap, Raydium, Orca) — the concepts do not transfer

**There is no order book.** This is not a data-availability problem; it is a market-structure
difference, and it invalidates most of the toolkit:

| Concept | In a CLOB | In an AMM |
|---|---|---|
| Bid/ask depth ladder | Resting limit orders | **Does not exist.** Liquidity is a curve (`x·y=k`, or concentrated ranges) |
| Absorption | A passive order refusing to move | **Does not exist.** The curve always fills; nobody chooses to absorb |
| Delta / aggressor side | Buyer-initiated vs seller-initiated | *Computable* from swap direction, but there is no passive counterparty with a view |
| Order pulling / spoofing | Visible in MBO | Liquidity is added/removed via LP transactions — visible, but on a different timescale |
| Slippage | Uncertain, depends on hidden depth | **Deterministic** from pool math — genuinely better |
| Point of control | Volume-weighted price magnet | Weakly meaningful; price is arbitrage-anchored to CEXs |

What replaces order flow on an AMM is a different discipline: **pool reserve tracking,
concentrated-liquidity tick distribution** (Uniswap v3 tick maps *are* a liquidity map, with
different semantics), LP add/remove events, and mempool observation. It is legitimate
analysis — it is just not footprint analysis.

Two further consequences, both material:

1. **MEV.** On a public mempool your intended trade is visible before it executes and can be
   sandwiched. Order-flow analysis cuts both ways: you are also order flow, and on-chain you
   are order flow that adversaries can read and act on first.
2. **Most on-chain "flow" is arbitrage.** AMM prices are kept in line with centralised venues
   by arbitrage bots. A large swap frequently carries no directional information at all — it
   is a bot closing a two-cent gap. Treating it as conviction is a category error.

> **The implication for GENIUS is worth stating plainly, because it is slightly awkward:**
> $GENIUS will itself trade on an AMM. So the lab's order-flow research and the lab's own
> token market are **structurally different domains**. Skill in one does not transfer to the
> other, and we should never imply that it does.

---

## 3. Recommended initial market

**BTC perpetual futures on one major centralised venue** (or BTC-USD spot on Coinbase for
the very first phase).

Why this and not the alternatives:

| Criterion | Why it wins |
|---|---|
| **Data cost** | L2 depth and aggressor-tagged trades are free over websocket. Zero licensing. |
| **Structure** | A genuine CLOB — the order-flow toolkit is valid, unlike on an AMM |
| **Hours** | 24/7, which a 33-consecutive-day public challenge needs. Futures and equities have gaps, holidays and session breaks that would make "33 days" mean something awkward. |
| **Depth** | Deep enough that our size never affects price — so simulated fills stay honest |
| **Verifiability** | Anyone can independently pull the same public data and check our reports |
| **Migration path** | The concepts port directly to CME futures later, once licensing is justified |

**Why not start with CME futures**, despite it being the better market for order flow:
licensing cost before any edge is demonstrated, plus redistribution terms that complicate
publishing charts publicly — which is the entire point of the project. Earn the licence with
results first.

**Why not equities:** fragmentation makes the flow picture structurally incomplete, and market
hours break the daily-cadence commitment.

**Why not an AMM pair:** §2 — the analysis we are building does not apply there.

---

## 4. Data source plan by phase

| Phase | Source | Cost | Status |
|---|---|---|---|
| **Now** | Synthetic generator (`data.py`) | $0 | `IMPLEMENTED` |
| **Now** | Coinbase public candles REST | $0 | `IMPLEMENTED` (opt-in via `--live`) |
| **Next** | Exchange websocket: trades + L2 diffs, persisted | $0 feed + storage | `PLANNED` |
| **Next** | News: RSS + a low-cost aggregator for ATLAS | $0–150/mo | `PLANNED` |
| **Later** | Historical tick/L2 archive for walk-forward validation | $99–500/mo | `PLANNED` |
| **Later** | Futures MBO via Databento / Rithmic / dxFeed + exchange fees | $1k–5k/mo | `BLOCKED` |

The critical near-term item is **persisting the L2 stream ourselves**. Depth data is free
live but expensive historically — every day we do not record is a day we must later buy.
Starting the recorder is cheap, reversible, and the value compounds. This should happen
before anything else in the data track.

---

## 5. The proposed $GENIUS / NVDA-exposure pair

### The candidate

The intent is a trading pair between $GENIUS and a tokenised asset tracking NVIDIA (NVDA).
The candidate identified in research:

| Attribute | Finding | Confidence |
|---|---|---|
| Token | **NVDAx** (NVIDIA tokenized stock, xStock) | High |
| Issuer | **Backed Finance** — Switzerland; issued by Backed Assets, Jersey | High |
| Instrument type | Tracker certificate, collateralised 1:1 by NVDA shares held with a regulated custodian | High |
| Chain | Solana (SPL); an ERC-20 form also referenced | High |
| Liquidity | ~**$1M** across major Solana DEXes | Medium — **volatile, must be re-checked at decision time** |
| Mint address | **Not verified** | — |

### What must be verified before this is more than an intention

1. **The exact mint address**, confirmed from the issuer's own documentation — not from an
   aggregator, a search result, or this document. Token-impersonation is common and cheap.
2. **Current issuer terms** — transfer restrictions, eligibility, whether non-qualified
   holders can hold or trade it, and whether creating a third-party pair against it is
   permitted.
3. **Redemption mechanics** — who can redeem for the underlying, under what conditions, and
   what happens to the peg if they can't.
4. **Jurisdiction** — a tokenised security tracker has different regulatory treatment across
   territories, and pairing a memecoin against one may attract treatment neither asset gets
   alone. **This needs a lawyer, not a developer.**
5. **Live liquidity and spread** at the moment of decision, not the number above.

### The structural risk, stated clearly

At roughly $1M of DEX liquidity, NVDAx is a **thin quote asset**. Consequences:

- Our own pool would likely become a significant share of price discovery on that pair.
- Slippage on meaningful size would be severe in both directions.
- A pair against a thin asset can be manipulated more cheaply than one against a deep
  stablecoin — the attack cost scales with the *shallower* side.
- NVDAx's own peg depends on the issuer's operations. A $GENIUS/NVDAx pair inherits
  **two** sets of risk: ours and theirs.

**Recommendation:** if the NVDA-exposure pair is wanted for narrative reasons — and it is a
genuinely good narrative, tying the lab's identity to the compute it runs on — then make it a
**secondary** pair, with a deep stablecoin pair (SOL or USDC) as the primary venue for price
discovery. That gets the story without making the token's market depend on a thin third-party
instrument. This is reversible: a second pair can be added later; a primary pair on a thin
asset is hard to unwind once liquidity settles there.

### Required disclaimer, wherever the pair is mentioned

> A trading pair with a tokenised NVDA tracker implies **no partnership with, endorsement by,
> or affiliation with NVIDIA Corporation**. It confers **no rights over NVIDIA shares**, no
> dividend, no voting right, and no claim on the issuer's collateral. Exposure is to a
> third-party issuer's tracker certificate and to that issuer's solvency and operations —
> not to NVIDIA.
