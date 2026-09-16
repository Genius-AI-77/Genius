# Cost Estimates

> **Planning record.** Written in September 2026 before the venue was chosen. Kept as the history of how the decisions were made. The current setup (Robinhood Chain, Uniswap, one wallet) is in `README.md` and `desk/README.md`.

**All figures are estimates for planning, not quotes.** Prices in this market move fast and
my information has a cutoff. Every number marked ⚠️ must be re-checked against a live quote
before anyone commits money. Ranges are given rather than single figures because the honest
answer to most of these is "it depends on volume."

Costs are separated into five buckets deliberately: **software, data, models, hardware, and
trading capital** are funded differently, fail differently, and should never be pooled into
one "budget" number.

---

## Bucket 1, Software & infrastructure

### Today (Phase 0)

| Item | Cost |
|---|---|
| Everything | **$0** |

The engine is Python stdlib. The site is static and deploys to a free tier. This is not
frugality theatre, it means the demonstrable product has no failure mode that involves an
unpaid invoice.

### Phase 1 to 2 (real data, scheduled runs)

| Item | Monthly | Notes |
|---|---|---|
| Site hosting | **$0** | Netlify / Cloudflare Pages free tier is genuinely sufficient |
| Domain | **~$1 to 4** | $15 to 50/year ⚠️ premium `.com` can be far more |
| VPS (data recorder + cron) | **$6 to 25** | Hetzner CX22 ≈ $5 to 7; DigitalOcean/Linode ≈ $12 to 24 |
| Block storage for L2 archive | **$5 to 25** | See sizing below |
| Off-site backup | **$1 to 6** | Object storage, ~$0.005 to 0.02/GB/mo |
| Uptime + error monitoring | **$0 to 30** | Free tiers cover this scale |
| **Subtotal** | **$13 to 90/mo** | |

**Storage sizing.** A single instrument's L2 diff stream plus trades runs roughly
0.5 to 3 GB/day uncompressed, depending on venue and depth levels captured. Compressed
(zstd) that is ~10 to 20% of raw. Call it **5 to 20 GB/month compressed** per instrument. A year
of one instrument fits comfortably in 100 to 250 GB.

The relevant point is not the cost, it is that **this data cannot be bought retroactively at
that price.** Historical L2 from a vendor costs $99 to 500/month. Recording it yourself costs
~$10/month. Every month of delay converts a $10 cost into a several-hundred-dollar one.
Start the recorder early; it is the cheapest option that expires.

---

## Bucket 2, Market data

| Source | Cost | Phase |
|---|---|---|
| Crypto exchange websockets (trades + L2) | **$0** | Phase 1 |
| Coinbase / exchange REST candles | **$0** | Now |
| News: RSS aggregation, self-built | **$0** | Phase 1 |
| News: commercial aggregator | ⚠️ **$50 to 450/mo** | Phase 2, wide range; entry tiers exist well under $100 |
| Historical crypto tick/L2 archive | ⚠️ **$99 to 500/mo** | Phase 3, avoidable if we record from Phase 1 |
| Futures MBO (Databento / Rithmic / dxFeed) | ⚠️ **$100 to 1,000/mo** vendor | Phase 5+ |
| **CME exchange fees on top of the vendor** | ⚠️ **$500 to 3,000+/mo** | The part that surprises people |

Two warnings that materially affect budgeting:

**Exchange fees are separate from vendor fees, and larger.** A futures data vendor's headline
price is the access layer. The exchange charges its own non-display and per-user fees on top,
and these dominate. Budget the exchange fee first and the vendor fee second.

**Publishing changes your licence tier.** Redistributing or publicly displaying derived data
from a licensed exchange feed is a different licence from using it internally. Since public
publication is the entire point of GENIUS, this must be checked *before* subscribing, not
after. It is a common and expensive surprise.

**Recommendation:** stay on free crypto feeds through Phase 4. The licensing cost is only
justified once there is a demonstrated edge that specifically requires futures microstructure.

---

## Bucket 3, Models

Two paths, with very different shapes.

### Path A, Hosted API

Cost scales linearly with cycles, so the arithmetic matters more than any single price:

```
monthly cost ≈ cycles/day × 30 × agents/cycle
               × (input_tokens × input_price + output_tokens × output_price)
```

Worked example, 3 LLM agents (ATLAS, EUCLID, FLUX; the other three stay rule-based),
~4k input and ~1k output tokens each:

| Cadence | LLM calls/month | Rough monthly cost ⚠️ |
|---|---|---|
| Hourly bars (24 cycles/day) | ~2,160 | **$10 to 80** |
| 15-min bars (96/day) | ~8,640 | **$40 to 320** |
| 1-min bars / scalping (1,440/day) | ~130,000 | **$600 to 4,800** |

⚠️ Model pricing changes frequently, recompute with current published rates before
committing. The ranges span the gap between a small fast model and a large frontier one.

**The structural insight:** cost is driven by *cadence*, not by sophistication. Moving from
hourly to 1-minute bars multiplies the model bill ~60×. This is the strongest practical
argument for the architecture we already have, **rules compute, models interpret.** Six
rule-based agents cost nothing per cycle, so a high-frequency loop stays affordable, and the
model is invoked only where language actually matters: reading news, and explaining a
decision to a human.

Three cost controls worth building in from the start: cache news analysis across cycles
(the same headline does not need re-reading 24 times), invoke the LLM only when the
rule-based layer produces a proposal, and batch overnight narration rather than doing it
per cycle.

### Path B, Local models on owned hardware

Zero marginal cost per call; capex and power instead. This is the case *for* the DGX Spark
purchase, and it is a real one, but it only pays back above a certain call volume. That
crossover point is computable once Phase 3 establishes the actual cadence, and it should be
computed before the purchase, not assumed.

---

## Bucket 4, Hardware

### The compute

| Item | Cost |
|---|---|
| NVIDIA DGX Spark, per unit ⚠️ | **$3,999-$4,699** observed |
| × 33 units | **$132,000-$155,000** |

The brief's $4,500 × 33 = $148,500 sits inside that range and is a reasonable planning figure.

### What the compute estimate leaves out

This is where hardware budgets usually break. Roughly 5 to 8 kW of continuous load in a
domestic or small-office space is a building services problem, not a computer problem.

| Item | Estimate ⚠️ | Note |
|---|---|---|
| High-speed switch (100GbE+) | **$8,000 to 25,000** | Needed only if nodes must interconnect at speed, see below |
| Cables + transceivers (33+) | **$5,000 to 13,000** | $150 to 400 each |
| Racking / shelving | **$1,000 to 3,000** | The stacked layout is a visual concept; operation needs airflow |
| PDUs + electrical work | **$2,500 to 12,000** | 5 to 8 kW needs dedicated circuits |
| Cooling | **$3,000 to 15,000** | 5 to 8 kW of heat needs real extraction, not a fan |
| UPS | **$2,000 to 8,000** | |
| **Non-compute subtotal** | **$21,500 to 76,000** | |
| **All-in, 33 units** | **$153,500 to 231,000** | |
| **Electricity, ongoing** | **$450 to 1,700/mo** | ~4,400 to 5,800 kWh/mo at $0.10 to 0.30/kWh, plus cooling overhead |

**The switch may be avoidable, and that is worth $10k+.** If the workload is genuinely
embarrassingly parallel, many independent agent jobs, which is what we have, then ordinary
gigabit or 10GbE networking is sufficient, and the expensive fabric is unnecessary. This is
a question the Phase 5 benchmark answers directly. Do not buy the fabric before knowing.

### The cheaper paths, in order of preference

| Option | Cost | Trade-off |
|---|---|---|
| **1 to 2 DGX Sparks to benchmark** | **$4,000 to 9,400** | The only defensible first purchase. Answers the sizing question for ~5% of the full spend. |
| Cloud GPU rental | ~$0.50 to 3/hr on demand | No capex, no power, no cooling; poor economics at 24/7 |
| Colocation instead of on-premises | $200 to 800/mo/rack + power | Someone else solves cooling, power and physical security |
| Full 33-unit build | $153k-231k | Only justified by a measured workload |

**Recommendation:** buy one, maybe two. Measure cycles-per-second and cost-per-cycle on the
real workload. Then size the purchase against measured demand. Buying 33 units before this
measurement is spending $150k+ to answer a $5k question, and if the answer is "four would
have done," the remaining spend is a marketing expense and should be accounted for as one.

---

## Bucket 5, Trading capital

**Kept entirely separate from operating budget.** It is not a cost; it is capital at risk,
and it should be money whose total loss changes nothing important.

### Sizing

At the configured 0.5% risk per trade:

| Capital | Risk/trade | Practical reality |
|---|---|---|
| $1,000 | $5 | Fees dominate; results measure the exchange's fee schedule, not the strategy |
| $10,000 | $50 | Minimum where after-cost results mean anything |
| $25,000 | $125 | Comfortable; slippage and fees stay proportionate |
| $100,000 | $500 | Only after a demonstrated live edge |

**Recommended first live allocation: $10,000 to 25,000**, treated as fully at risk.

The reason for a floor rather than starting tiny: below roughly $10k, the fixed components
of trading cost swamp the signal, so a losing result tells you nothing about the strategy, you have merely proven that fees exist. That is an expensive way to learn nothing.

---

## Summary

### Monthly operating cost by phase

| Phase | Monthly ⚠️ | What it buys |
|---|---|---|
| **Phase 0** (now) | **$0** | Everything currently built |
| **Phase 1** (real data) | **$15 to 60** | VPS, storage, domain, the depth archive starts accruing |
| **Phase 2** (publishing) | **$30 to 200** | Adds news feed and modest LLM usage |
| **Phase 3** (validation) | **$50 to 350** | Adds historical data if not self-recorded |
| **Phase 4** (live, small) | **$50 to 350** + capital | Same infra; capital is separate |
| **Phase 5** (owned cluster) | **$500 to 1,800** | Electricity and cooling dominate |

### One-time costs

| Item | Range |
|---|---|
| Benchmark hardware (1 to 2 units) | $4,000 to 9,400 |
| Legal review, token, jurisdiction, the NVDA pair | ⚠️ $5,000 to 25,000+ |
| Full 33-unit build, all-in | $153,500 to 231,000 |
| First live trading capital | $10,000 to 25,000 |

### The honest headline

**The MVP through Phase 3 costs under $400/month and needs no hardware purchase at all.**
The expensive commitments, the cluster, the futures data licence, the trading capital, the
legal work, are all gated behind evidence that does not exist yet. That ordering is the
single most valuable property of this plan, and the easiest one to lose.

The one exception worth spending on early is the **legal review**, before any token step.
It is the only item on this list where acting first and checking later can produce a problem
that money cannot fix afterwards.
