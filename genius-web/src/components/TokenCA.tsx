import { useState } from "react";

type Tok = { ticker?: string; chain?: string; ca?: string };
const tok = (): Tok => ((window as unknown as { GENIUS_TOKEN?: Tok }).GENIUS_TOKEN ?? {});
const short = (a: string) => `${a.slice(0, 4)}\u2026${a.slice(-4)}`;

function useCopy() {
  const [done, setDone] = useState(false);
  return {
    done,
    copy: (t: string) => navigator.clipboard?.writeText(t).then(() => { setDone(true); setTimeout(() => setDone(false), 1200); }),
  };
}

/** Nav chip. Renders nothing until the contract address is set in public/ca.js. */
export function CAChip() {
  const t = tok(); const { done, copy } = useCopy();
  if (!t.ca) return null;
  return (
    <button type="button" onClick={() => copy(t.ca!)} title="Copy contract address"
      className="ml-[18px] inline-flex flex-none items-center gap-2 rounded border border-volt/45 bg-volt/[.08] px-3 py-2
        font-mono text-[10.5px] tracking-[0.06em] text-volt transition-all hover:bg-volt/[.16] hover:shadow-volt-soft">
      <b className="font-bold tracking-[0.14em]">CA</b>
      <span className="max-[640px]:hidden">{done ? "Copied" : short(t.ca)}</span>
    </button>
  );
}

/** Hero card. Renders nothing until the contract address is set. */
export function CACard() {
  const t = tok(); const { done, copy } = useCopy();
  if (!t.ca) return null;
  const ca = t.ca;
  return (
    <div className="mx-auto mt-[clamp(30px,4vw,44px)] max-w-[640px] rounded-lg border border-volt/35 p-[18px_20px] text-left shadow-[0_0_40px_-18px_rgba(166,226,46,.34)]"
      style={{ background: "linear-gradient(160deg,rgba(166,226,46,.08),rgba(166,226,46,.02))" }}>
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-2.5">
        <span className="font-display text-[18px] font-extrabold tracking-[-0.01em] text-volt">{t.ticker ?? "$GENIUS"}</span>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">Solana · contract address</span>
      </div>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-[5px] border border-line-2 bg-[#0b0f11] px-3 py-2.5 font-mono text-[12.5px] font-medium text-ink">{ca}</code>
        <button type="button" onClick={() => copy(ca)}
          className="flex-none rounded-[5px] border border-volt bg-volt px-3.5 py-2.5 font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#07130a] hover:shadow-volt">
          {done ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="mt-3 flex gap-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.12em]">
        {[["Solscan", `https://solscan.io/token/${ca}`], ["Chart", `https://dexscreener.com/solana/${ca}`], ["Swap on Jupiter", `https://jup.ag/swap/SOL-${ca}`]].map(([l, h]) => (
          <a key={l} href={h} target="_blank" rel="noopener noreferrer" className="border-b border-line-2 text-ink-2 no-underline hover:border-volt hover:text-volt">{l}</a>
        ))}
      </div>
      <p className="mt-3 font-mono text-[11.5px] leading-[1.6] text-ink-3">This is the only official contract address. Verify it here before you trust it anywhere else.</p>
    </div>
  );
}
