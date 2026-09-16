/**
 * All site copy lives here, separated from markup.
 *
 * Edit this file (or ask Lovable to edit it) to change wording, add a ledger
 * row, or adjust a stat, without touching layout components.
 *
 * IMPORTANT, the status labels below are load-bearing, not decoration.
 * GENIUS commits publicly to labelling every component as implemented,
 * simulated, planned or blocked. Do not upgrade a status here unless the
 * underlying thing actually changed.
 */

export type Status = "impl" | "sim" | "plan" | "block";

export const STATUS_LABEL: Record<Status, string> = {
  impl: "Live",
  sim: "Building",
  plan: "Next",
  block: "Later",
};

export const tickerItems = [
  "The desk is open",
  "Six agents trading ETH, around the clock",
  "Real market, real decisions, every one public",
  "Everyone is a Scientist",
  "Build phase 01, building in public",
];

export const navLinks = [
  { href: "#machine", label: "Machine" },
  { href: "#agents", label: "Agents" },
  { href: "#method", label: "Method" },
  { href: "#veto", label: "Veto" },
  { href: "#desk", label: "Desk" },
  { href: "#connect", label: "Connect" },
  { href: "#ledger", label: "Build log" },
];

export const hero = {
  kicker: { num: "01", label: "The Vision" },
  headline: ["Everyone is", "a Scientist"],
  sub: "Curiosity is the starting point.",
  lede: "Six AI agents run a trading desk the way scientists run a lab. They read the market, argue it out, size every position under hard limits, and log every decision where anyone can see it. The desk is open right now. Watch it work.",
};

export const machine = {
  kicker: { num: "02", label: "The Machine" },
  specs: [
    { k: "Unit", v: "NVIDIA DGX Spark (GB10)" },
    { k: "Unified memory / unit", v: "128 GB LPDDR5X" },
    { k: "Units × agent roles", v: "33 × 6 = 198" },
    { k: "Street price observed", v: "$3,999 to $4,699" },
  ],
  total: { k: "Hardware estimate (33 units)", v: "$132k to $155k" },
  departments: ["Discovery", "Validation", "Operations"],
};

export type Agent = {
  name: string;
  role: string;
  body: string;
  io: { label: string; value: string }[];
  accent: "volt" | "cyan" | "danger";
  binding?: boolean;
  note?: { text: string; status: Status };
};

export const agents: Agent[] = [
  {
    name: "ATLAS",
    role: "Fundamental Analyst",
    accent: "volt",
    body: "Reads news, macro releases and asset-level events. Every claim carries a source and a date, or it does not count.",
    io: [
      { label: "In", value: "news feeds, econ calendar, filings" },
      { label: "Out", value: "directional bias + cited events" },
      { label: "Scored on", value: "bias vs. forward return, source quality" },
    ],
  },
  {
    name: "EUCLID",
    role: "Technical Analyst",
    accent: "cyan",
    body: "Market structure, trend and levels, and above all the exact price at which the thesis is simply wrong.",
    io: [
      { label: "In", value: "OHLCV history" },
      { label: "Out", value: "structure, levels, invalidation price" },
      { label: "Scored on", value: "level hit rate, invalidation accuracy" },
    ],
  },
  {
    name: "FLUX",
    role: "Order Flow Analyst",
    accent: "cyan",
    body: "The trade tape and the book: delta, volume by price, depth, liquidity, and candidate absorption where aggressive orders meet a wall.",
    note: { text: "Depth live", status: "impl" },
    io: [
      { label: "In", value: "trades, volume-by-price, L2 depth" },
      { label: "Out", value: "delta trend, point of control, absorption flags" },
      { label: "Scored on", value: "flow signal vs. next-bar continuation" },
    ],
  },
  {
    name: "HERMES",
    role: "Execution Specialist",
    accent: "volt",
    body: "Takes approved orders and gets them filled: entries, exits, spread, fees, slippage. It reports the cost of being right.",
    io: [
      { label: "In", value: "approved order, book conditions" },
      { label: "Out", value: "fills, realised costs" },
      { label: "Scored on", value: "slippage vs. decision price" },
    ],
  },
  {
    name: "LEDGER",
    role: "Research & Audit Analyst",
    accent: "volt",
    body: "Journals every decision, including the decision to do nothing, and grades them after costs. Flags strategy decay before the equity curve does.",
    io: [
      { label: "In", value: "full decision journal, fills, outcomes" },
      { label: "Out", value: "after-cost expectancy, decay flags" },
      { label: "Scored on", value: "did it catch degradation early?" },
    ],
  },
  {
    name: "VETO",
    role: "Risk Manager · binding authority",
    accent: "danger",
    binding: true,
    body: "Exposure, position size, loss limits. VETO does not offer an opinion. It returns approve or reject, and reject is final. Its limits are arithmetic in code, not instructions in a prompt, so no model can talk its way past them. An agent that wants a bigger position can want it indefinitely.",
    io: [
      { label: "In", value: "proposal, equity, open risk, session P&L" },
      { label: "Out", value: "APPROVE(size, stop) or REJECT(reason)" },
      { label: "Scored on", value: "limit breaches, target zero" },
      { label: "Override path", value: "none exists" },
    ],
  },
];

export const methodSteps = [
  {
    n: "STEP 01",
    title: "Observe",
    body: "Candles, trade tape and buy/sell split land in a shared context. The same snapshot for every agent.",
  },
  {
    n: "STEP 02",
    title: "Argue",
    body: "ATLAS, EUCLID and FLUX each file an independent report: stance, confidence, findings, invalidation.",
  },
  {
    n: "STEP 03",
    title: "Propose",
    body: "A proposal forms only when structure and flow agree and fundamentals do not strongly object. Otherwise: no trade.",
  },
  {
    n: "STEP 04 · GATE",
    title: "Risk review",
    body: "VETO sizes the position from the distance to invalidation, or rejects it. Code, not judgement.",
    gate: true,
  },
  {
    n: "STEP 05",
    title: "Execute & audit",
    body: "HERMES fills it with fees and slippage charged. LEDGER journals the cycle, trade or not, and scores it after costs.",
  },
];

export const riskLimits = [
  { k: "Risk per trade", v: "≤ 0.5% of equity" },
  { k: "Daily loss limit", v: "2% → session halt" },
  { k: "Gross exposure", v: "≤ 25% of equity" },
  { k: "Consecutive losses", v: "3 → cooldown" },
  { k: "Committee confidence floor", v: "0.55" },
  { k: "Minimum stop distance", v: "0.2% (noise band)" },
  { k: "Concurrent positions", v: "1" },
];

/** Fallback values only, the Experiment section overrides these from /console/data.js at runtime. */
export const experimentStats = [
  { v: "792", k: "Research cycles", n: "33 sessions × 24 bars" },
  { v: "287", k: "No-trade calls", n: "Discipline, on the record" },
  { v: "33", k: "Risk vetoes", n: "Every limit held, zero breaches" },
  { v: "24", k: "Trades taken", n: "~3% of cycles reached execution" },
  { v: "−$2,742", k: "Net P&L after costs", n: "Negative. Published as-is.", down: true },
  { v: "−4.4%", k: "Max drawdown", n: "Inside the limits, by design", down: true },
];

export const ledgerRows: { component: string; status: Status; note: string }[] = [
  { component: "Six-agent research pipeline", status: "impl", note: "Runs locally, deterministic, reproducible" },
  { component: "Risk engine & veto", status: "impl", note: "Pure code, enforced on every cycle" },
  { component: "Paper broker (fees + slippage)", status: "impl", note: "All P&L reported after costs" },
  { component: "Decision journal & audit metrics", status: "impl", note: "JSONL, one entry per cycle" },
  { component: "Lab console & this site", status: "impl", note: "Static, no backend required" },
  { component: "Market data", status: "impl", note: "Live ETH-USD candles, trade tape and level-2 depth from a public exchange API; synthetic fallback if unreachable" },
  { component: "Fundamental news inputs", status: "impl", note: "Live headlines, scored and time-gated so no bar sees its future" },
  { component: "LLM reasoning layer", status: "plan", note: "Next up. Models will read and interpret; every number and limit stays in code" },
  { component: "Order-book depth / DOM", status: "impl", note: "Level-2 snapshot each run, recorded to disk; continuous streaming is planned" },
  { component: "Daily automated run", status: "impl", note: "GitHub Actions: tests, live run, commit, redeploy. No servers, no keys" },
  { component: "Wallet connect (Robinhood Chain)", status: "impl", note: "Read-only: public address, balance, message-signature ownership proof. Never requests a transaction signature, enforced by a build test" },
  { component: "Footprint & replay tooling", status: "plan", note: "Studied against public references; nothing proprietary copied" },
  { component: "Futures order-flow data", status: "block", note: "Phase three, once the edge is demonstrated on the current market" },
  { component: "33× DGX Spark cluster", status: "block", note: "Phase two. Benchmark on one or two units, then scale to 33" },
  { component: "Live execution", status: "block", note: "After validation: out-of-sample edge across two market regimes first" },
];

export const disclaimer =
  "GENIUS is a research project, built in public. Nothing on this page is investment, financial, legal or tax advice. Performance shown is paper research on real market data with no capital at risk; research results do not predict real outcomes. Hardware described is the build target for a later phase. NVIDIA, DGX and DGX Spark are trademarks of NVIDIA Corporation; GENIUS is not affiliated with, endorsed by, or partnered with NVIDIA. Other platforms referenced are studied as public prior art only.";
