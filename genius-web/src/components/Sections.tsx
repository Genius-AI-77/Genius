import {
  agents,
  experimentStats,
  hero,
  machine,
  methodSteps,
  pairCaveats,
  riskLimits,
  tokenIs,
  tokenIsNot,
} from "../data/content";
import { GMark, H2, Hi, Kicker, Mod, Section, Wrap } from "./ui";
import { Pill } from "./ui";
import { AgentIcon } from "./AgentIcon";
import { WalletCard } from "./Wallet";

/* ------------------------------------------------------------------ 01 */

export function Hero() {
  return (
    <header id="top" className="relative z-[2] py-[clamp(64px,11vw,140px)] text-center">
      <Wrap>
        <Kicker num={hero.kicker.num} label={hero.kicker.label} centered />
        <div className="mx-auto mb-[clamp(26px,4vw,42px)] w-[clamp(78px,12vw,116px)]">
          <GMark
            className="h-auto w-full animate-float motion-reduce:animate-none
              drop-shadow-[0_0_26px_rgba(166,226,46,.34)]"
          />
        </div>
        <h1
          className="font-display font-extrabold tracking-[-0.045em] text-white"
          style={{ fontSize: "clamp(46px,10.4vw,116px)", lineHeight: 0.9, textWrap: "balance" }}
        >
          {hero.headline[0]}
          <br />
          {hero.headline[1]}
          <span className="text-volt">.</span>
        </h1>
        <p
          className="mt-[clamp(18px,2.6vw,28px)] font-mono tracking-[0.09em] text-ink-2"
          style={{ fontSize: "clamp(13px,2.1vw,19px)" }}
        >
          {hero.sub}
        </p>
        <p
          className="mx-auto mt-[clamp(30px,4vw,44px)] max-w-[60ch] leading-[1.68] text-ink-2"
          style={{ fontSize: "clamp(16px,1.9vw,18.5px)" }}
        >
          Markets are treated as a place to be right. We treat them as a place to{" "}
          <strong className="font-semibold text-ink">run experiments</strong>. GENIUS is a
          research lab where AI agents form hypotheses, test them against data, size them
          under hard limits, execute them — and then audit themselves, with the losses
          published next to the wins.
        </p>
        <div className="mt-[clamp(32px,4vw,44px)] flex flex-wrap justify-center gap-3">
          <a className="btn btn-solid" href="#experiment">
            See the first experiment
          </a>
          <a className="btn btn-ghost" href="#ledger">
            What's real today
          </a>
        </div>
        <div
          className="mx-auto mt-[clamp(38px,5vw,56px)] max-w-[74ch] rounded border border-line
            border-l-2 border-l-amber p-[18px_22px] text-left font-mono text-[13.5px]
            leading-[1.72] text-ink-2"
          style={{ background: "linear-gradient(180deg, rgba(240,165,60,.05), transparent)" }}
        >
          <b className="mb-[7px] block text-[11px] uppercase tracking-[0.1em] text-amber">
            Read this first
          </b>
          {hero.notice}
        </div>
      </Wrap>
    </header>
  );
}

/* ------------------------------------------------------------------ 02 */

export function Machine() {
  return (
    <Section id="machine">
      <Kicker num={machine.kicker.num} label={machine.kicker.label} />
      <H2>
        Meet the <Hi>machine</Hi>.
      </H2>
      <p className="dek">
        The target architecture is 33 NVIDIA DGX Spark units, stacked as three columns of
        eleven. Each unit hosts six specialist agent roles — 198 roles in total. This is a{" "}
        <strong>proposal under validation</strong>, not an inventory.
      </p>

      <div className="mt-10 grid items-start gap-[30px] lg:grid-cols-[1.02fr_.98fr] lg:gap-[46px]">
        <Mod className="p-[26px_22px_22px]">
          <div className="mb-[18px] flex flex-wrap justify-between gap-2.5 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-3">
            <span>FIG. 1 — Proposed layout</span>
            <b className="font-medium text-volt">3 × 11 · 198 roles</b>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {machine.departments.map((dept, di) => (
              <div key={dept}>
                <h4
                  className={`mb-[11px] border-b border-line pb-[9px] text-center font-mono
                    text-[10px] font-semibold uppercase tracking-[0.14em]
                    ${di === 0 ? "text-volt" : di === 1 ? "text-cyan" : "text-ink-2"}`}
                >
                  {dept}
                </h4>
                {Array.from({ length: 11 }, (_, u) => (
                  <div
                    key={u}
                    title={`${dept} · unit ${u + 1} · 6 agent roles`}
                    className={`group mb-[5px] flex justify-center gap-1 rounded-[3px] border
                      border-line bg-[#0b0f11] px-[5px] py-1.5 transition-all
                      ${di === 1 ? "hover:border-cyan" : "hover:border-volt"}`}
                  >
                    {Array.from({ length: 6 }, (_, d) => (
                      <i
                        key={d}
                        className={`block h-[5px] w-[5px] rounded-full bg-[#394346] transition-colors
                          ${di === 1 ? "group-hover:bg-cyan" : "group-hover:bg-volt"}`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="mt-[18px] border-t border-dashed border-line pt-3.5 font-mono text-[11.5px] leading-[1.75] text-ink-3">
            Each row = 1 DGX Spark · each dot = 1 agent role.
            <br />
            <b className="font-medium text-ink-2">Discovery</b> generates hypotheses ·{" "}
            <b className="font-medium text-ink-2">Validation</b> tries to kill them with
            backtests and replay · <b className="font-medium text-ink-2">Operations</b>{" "}
            monitors and, once approved, executes.
          </div>
        </Mod>

        <div>
          <ul className="mb-[26px] list-none p-0">
            {machine.specs.map((s) => (
              <li
                key={s.k}
                className="flex items-baseline justify-between gap-3.5 border-b border-line py-3 font-mono text-[13.5px]"
              >
                <span className="text-ink-3">{s.k}</span>
                <b className="text-right font-medium text-ink">{s.v}</b>
              </li>
            ))}
            <li className="flex items-baseline justify-between gap-3.5 border-b border-line py-3 font-mono text-[13.5px]">
              <span className="text-ink-3">{machine.total.k}</span>
              <b className="text-right text-[16px] font-medium text-volt">{machine.total.v}</b>
            </li>
          </ul>
          <p className="dek !mt-0">
            <Pill status="block" /> &nbsp;Purchase is gated on validation we have not
            finished: sustained thermal behaviour under continuous load, power and cooling
            for a stacked layout, and the interconnect question. NVIDIA documents pairing{" "}
            <strong>two</strong> units over ConnectX-7 to share 256&nbsp;GB — it does not
            follow that 33 units behave as one supercomputer. We treat them as 33
            independent workers on a shared job queue until proven otherwise.
          </p>
          <p className="dek">
            The estimate excludes networking, power, racking, cooling, trading capital and
            anything operational. And six agent roles does not imply six separate models —
            role separation is a matter of prompts, tools and permissions, not silicon.
          </p>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ 03 */

export function Agents() {
  return (
    <Section id="agents">
      <Kicker num="03" label="The Agents" />
      <H2>
        Six minds.
        <br />
        Different <Hi>responsibilities</Hi>.
      </H2>
      <p className="dek">
        One model asked to "trade well" produces confident mush. Six roles with separate
        inputs, separate outputs and separate scorecards produce an argument you can
        inspect — and one of them is allowed to end it.
      </p>

      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {agents.map((a) => (
          <Mod
            as="article"
            key={a.name}
            alert={a.binding}
            className={`p-[24px_22px] ${a.binding ? "sm:col-span-2 sm:grid sm:grid-cols-2 sm:gap-x-8" : ""}`}
          >
            <div className={`mb-3.5 flex items-center gap-3 ${a.binding ? "sm:col-span-2" : ""}`}>
              <div
                className={`grid h-[34px] w-[34px] flex-none place-items-center rounded-[5px]
                  border bg-[#0b0f11] ${a.binding ? "border-danger/40" : "border-line-2"}`}
              >
                <AgentIcon name={a.name} />
              </div>
              <div>
                <div className="font-display text-[17px] font-extrabold leading-none tracking-[-0.01em] text-ink">
                  {a.name}
                </div>
                <div
                  className={`mt-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.13em]
                    ${a.binding ? "text-danger" : "text-volt"}`}
                >
                  {a.role}
                </div>
              </div>
            </div>
            <p className="text-[15px] leading-[1.62] text-ink-2">{a.body}</p>
            <dl
              className={`font-mono text-[12px] leading-[1.75] text-ink-3
                ${a.binding ? "sm:mt-0 sm:border-t-0 sm:pt-0" : "mt-4 border-t border-line pt-3.5"}`}
            >
              {a.io.map((row) => (
                <div key={row.label}>
                  <b className="font-medium text-ink-2">{row.label}:</b> {row.value}
                  {row.label === "In" && a.note && (
                    <>
                      {" "}
                      <Pill status={a.note.status}>{a.note.text}</Pill>
                    </>
                  )}
                </div>
              ))}
            </dl>
          </Mod>
        ))}
      </div>

      <p className="dek !max-w-[64ch] mt-8">
        Two rules sit above all six. <strong>"Do not trade" is a valid, recorded outcome</strong>{" "}
        — most cycles end there, and that is the system working. And{" "}
        <strong>agreement between agents is never treated as evidence</strong>: six models
        trained on overlapping data agreeing is a correlation, not a confirmation. Only the
        after-cost result counts.
      </p>
    </Section>
  );
}

/* ------------------------------------------------------------------ 04 */

export function Method() {
  return (
    <Section id="method">
      <Kicker num="04" label="The Method" />
      <H2>
        How GENIUS <Hi>reads</Hi> a market.
      </H2>
      <p className="dek">
        One cycle per bar. Analysis is free, risk is enforced, everything is written down.
      </p>
      <div className="mt-10 grid gap-2.5 lg:grid-cols-5 lg:gap-2">
        {methodSteps.map((s) => (
          <Mod key={s.title} alert={s.gate} className="p-[20px_18px]">
            <div
              className={`font-mono text-[10px] font-medium tracking-[0.16em] ${
                s.gate ? "text-danger" : "text-volt"
              }`}
            >
              {s.n}
            </div>
            <h5 className="my-2.5 font-display text-[17px] font-bold tracking-[-0.015em] text-ink">
              {s.title}
            </h5>
            <p className="text-[13.5px] leading-[1.6] text-ink-2">{s.body}</p>
          </Mod>
        ))}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ 05 */

const VETO_CODE = `# risk.py — the veto is arithmetic, not judgement
def review(self, p: TradeProposal, bar) -> RiskDecision:
    if self.halted:
        return RiskDecision(False, ["VETO: daily loss limit"])
    if bar < self.cooldown_until_bar:
        return RiskDecision(False, ["VETO: loss-streak cooldown"])
    if p.confidence < MIN_CONFIDENCE:
        return RiskDecision(False, ["VETO: below confidence floor"])

    stop_dist = abs(p.price - p.invalidation)
    if stop_dist < p.price * MIN_STOP_DISTANCE_PCT:
        return RiskDecision(False, ["VETO: stop inside noise"])

    # size is DERIVED, never proposed by an agent
    qty = (equity * MAX_RISK_PER_TRADE) / stop_dist
    return RiskDecision(True, reasons, qty=qty, stop=p.invalidation)`;

export function Veto() {
  return (
    <Section id="veto">
      <Kicker num="05" label="The Veto" />
      <H2>
        The agent that can say <Hi>no</Hi>.
      </H2>
      <p className="dek">
        Most AI trading demos fail in the same place: the model is asked to respect a risk
        limit, and eventually it doesn't. We removed the possibility.
      </p>

      <div className="mt-10 grid gap-[26px] lg:grid-cols-[.92fr_1.08fr] lg:gap-10">
        <div>
          <p className="dek !mt-0">
            The risk engine is ordinary code with no model in it. It receives a proposal and
            returns a decision. There is no prompt to jailbreak, no confidence score to
            inflate, no persuasive argument that changes the arithmetic.
          </p>
          <ul className="mt-[26px] list-none p-0">
            {riskLimits.map((l) => (
              <li
                key={l.k}
                className="flex justify-between gap-4 border-b border-line py-[13px] font-mono text-[13.5px]"
              >
                <span className="text-ink-3">{l.k}</span>
                <b className="whitespace-nowrap font-semibold text-ink">{l.v}</b>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <pre className="overflow-x-auto rounded-lg border border-line bg-black p-[22px] font-mono text-[12.5px] leading-[1.8] text-[#c3ccc7]">
            {VETO_CODE}
          </pre>
          <p className="mt-4 font-mono text-[12.5px] leading-[1.75] text-ink-3">
            Position size is <em>derived</em> from the distance to invalidation. No agent
            proposes a size, so no agent can inflate one.
          </p>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ 06 */

type RunData = {
  meta: { instrument: string; sessions: number; bars_per_session: number; generated_at?: number;
          inputs?: Record<string, string> };
  metrics: { cycles: number; no_trade: number; vetoes: number; trades: number;
             total_pnl: number; total_costs: number; max_drawdown_pct: number };
};

function liveStats() {
  const D = (window as unknown as { GENIUS_DATA?: RunData }).GENIUS_DATA;
  if (!D || !D.metrics) return { stats: experimentStats, meta: null as string | null };
  const m = D.metrics, meta = D.meta;
  const money = (v: number) =>
    (v < 0 ? "−$" : "$") + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
  const inputs = meta.inputs ?? {};
  const real = Object.keys(inputs).filter((k) => String(inputs[k]).startsWith("live"));
  const when = meta.generated_at ? new Date(meta.generated_at * 1000).toISOString().slice(0, 10) : "";
  return {
    stats: [
      { v: m.cycles.toLocaleString("en-US"), k: "Research cycles", n: `${meta.sessions} sessions × ${meta.bars_per_session} bars` },
      { v: m.no_trade.toLocaleString("en-US"), k: "No-trade calls", n: "Standing aside is the default" },
      { v: m.vetoes.toLocaleString("en-US"), k: "Risk vetoes", n: "All enforced, none overridden" },
      { v: m.trades.toLocaleString("en-US"), k: "Trades taken", n: `~${Math.round((100 * m.trades) / Math.max(1, m.cycles))}% of cycles reached execution` },
      { v: money(m.total_pnl), k: "Net P&L after costs", n: m.total_pnl < 0 ? "Negative. Published as-is." : `Positive — after ${money(m.total_costs)} costs`, down: m.total_pnl < 0 },
      { v: `${m.max_drawdown_pct < 0 ? "−" : ""}${Math.abs(m.max_drawdown_pct).toFixed(1)}%`, k: "Max drawdown", n: "Within design tolerance", down: true },
    ],
    meta: `Latest run${when ? " " + when : ""} · ${meta.instrument} · inputs: ${
      real.length ? real.map((k) => `${k} (real)`).join(", ") : "all synthetic"} · all P&L after simulated costs`,
  };
}

export function Experiment() {
  const { stats, meta } = liveStats();
  return (
    <Section id="experiment">
      <Kicker num="06" label="The Experiment" />
      <H2>
        Our first public <Hi>experiment</Hi>.
      </H2>
      <p className="dek">
        A working six-agent pipeline running 33 simulated sessions on BTC-USD, with every
        decision journaled and every result reported after fees and slippage.
      </p>

      <div className="my-[30px] grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(148px,1fr))]">
        {stats.map((s) => (
          <Mod key={s.k} className="p-[18px_16px]">
            <div
              className={`font-display font-extrabold leading-none tracking-[-0.03em]
                ${s.down ? "text-danger" : "text-ink"}`}
              style={{ fontSize: "clamp(24px,3.4vw,34px)" }}
            >
              {s.v}
            </div>
            <div className="mt-[9px] font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-ink-3">
              {s.k}
            </div>
            <div className="mt-[5px] text-[12.5px] leading-[1.45] text-ink-3">{s.n}</div>
          </Mod>
        ))}
      </div>

      {meta && (
        <p className="font-mono text-[12.5px] leading-[1.8] text-ink-3">{meta}</p>
      )}

      <p className="dek">
        The experiment is deliberately unflattering. The first published run ended{" "}
        <strong>down</strong> — a 33% win rate and negative expectancy after costs — and
        LEDGER raised the degradation flag exactly as designed. We publish it anyway,
        because a lab that only shows its winning runs is not a lab. The number that matters
        right now is not the P&amp;L: it is that the risk engine held every limit across 792
        cycles, and that 287 of those cycles correctly ended in <strong>no trade</strong>.
      </p>

      <p className="mt-[22px] font-mono text-[12.5px] leading-[1.8] text-ink-3">
        <Pill status="sim" /> Paper broker, synthetic regime-switching market, seeded for
        reproducibility. Fundamental events are fixtures. Nothing here is a forecast, a
        track record, or a promise. Run it yourself:{" "}
        <code className="text-volt">python3 lab/run_demo.py</code>
      </p>

      <div className="mt-[30px] flex flex-wrap gap-3">
        <a className="btn btn-solid" href="/console/">
          Open the lab console
        </a>
        <a className="btn btn-ghost" href="#ledger">
          See what's blocked
        </a>
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ 07 */

export function Token() {
  return (
    <Section id="token">
      <Kicker num="07" label="The Token" />
      <H2>
        What <Hi>$GENIUS</Hi> represents.
      </H2>
      <p className="dek">Said plainly, because the alternative is how people get hurt.</p>

      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {[
          { title: "What it is", items: tokenIs, good: true },
          { title: "What it is not", items: tokenIsNot, good: false },
        ].map((col) => (
          <Mod key={col.title} className="p-6">
            <h5 className="mb-3.5 flex items-center gap-2.5 font-display text-[16px] font-bold text-ink">
              <span
                className={`h-[7px] w-[7px] rounded-full ${col.good ? "bg-volt" : "bg-danger"}`}
                style={{
                  boxShadow: col.good
                    ? "0 0 9px rgba(166,226,46,.5)"
                    : "0 0 9px rgba(255,90,90,.5)",
                }}
              />
              {col.title}
            </h5>
            <ul className="m-0 list-disc pl-[18px] text-[14.5px] leading-[1.65] text-ink-2 marker:text-ink-3">
              {col.items.map((t) => (
                <li key={t} className="mb-2.5">
                  {t}
                </li>
              ))}
            </ul>
          </Mod>
        ))}
      </div>

      <Mod className="mt-3.5 p-[26px]">
        <h5 className="mb-3.5 font-display text-[19px] font-bold text-ink">
          The proposed NVIDIA-exposure pair <Pill status="plan">Under validation</Pill>
        </h5>
        <p className="max-w-[74ch] text-[15.5px] leading-[1.68] text-ink-2">
          The intent is to pair $GENIUS against a tokenised asset tracking NVIDIA (NVDA). The
          candidate we have identified is <strong className="font-semibold text-ink">NVDAx</strong>,
          an xStock tracker certificate issued by{" "}
          <strong className="font-semibold text-ink">Backed Finance</strong> (Switzerland /
          Backed Assets, Jersey) as an SPL token on Solana, collateralised by shares held with
          a regulated custodian. Observed DEX liquidity is roughly{" "}
          <strong className="font-semibold text-ink">$1M</strong> — thin enough that pairing
          against it is a genuine design constraint, not a formality.
        </p>
        <ul className="mt-[18px] list-disc pl-[18px] text-[14.5px] leading-[1.62] text-ink-2 marker:text-ink-3">
          {pairCaveats.map((c) => (
            <li key={c} className="mb-2.5">
              {c}
            </li>
          ))}
        </ul>
        <p className="mt-5 rounded border border-danger/30 bg-danger/5 p-[14px_16px] font-mono text-[12.5px] leading-[1.7] text-[#e79a9a]">
          A pair with a tokenised NVDA tracker implies no partnership with, endorsement by, or
          affiliation with NVIDIA Corporation, and gives $GENIUS holders no rights over NVIDIA
          shares.
        </p>
      </Mod>
      <WalletCard />
    </Section>
  );
}

/* ------------------------------------------------------------------ 08 */

export function Challenge() {
  return (
    <Section id="challenge">
      <Kicker num="08" label="The Challenge" />
      <H2>
        The <Hi>33-Day</Hi> Challenge.
      </H2>
      <p className="dek">
        Thirty-three consecutive sessions. One public report per day: the hypothesis, what the
        agents said, what the risk engine did, and the result after costs — win, loss, or
        nothing at all.
      </p>
      <div className="my-8 grid grid-cols-6 gap-1.5 sm:grid-cols-11">
        {Array.from({ length: 33 }, (_, i) => (
          <div
            key={i}
            title={`Day ${i + 1} — report pending`}
            className="grid aspect-square place-items-center rounded-[3px] border border-line
              bg-panel font-mono text-[11px] font-medium text-ink-3 transition-all
              hover:border-volt hover:bg-volt/[.07] hover:text-volt"
          >
            {i + 1}
          </div>
        ))}
      </div>
      <p className="dek">
        The challenge is a commitment to publication, not to profit. Losing days are published
        at the same size and on the same schedule as winning ones. If the strategy degrades,
        the audit agent's flag goes in the report. If a day ends with no trade taken, that is
        the report. The only failure condition is silence.
      </p>
      <p className="mt-5 font-mono text-[12.5px] leading-[1.8] text-ink-3">
        <Pill status="sim" /> Day 1 runs on paper. Moving any session to live capital requires
        a documented decision, a funded account, and a published change of status on this page
        — never a quiet switch.
      </p>
    </Section>
  );
}
