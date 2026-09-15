import { useState, type ReactNode } from "react";
import { H2, Hi, Kicker, Mod, Section } from "./ui";

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

/** Full token section (nav tab "Token" + section 08). Renders nothing until the address is set. */
export function TokenSection() {
  const t = tok(); const { done, copy } = useCopy();
  if (!t.ca) return null;
  const ca = t.ca;
  const Row = ({ k, children }: { k: string; children: ReactNode }) => (
    <div className="flex flex-wrap items-center gap-4 border-t border-volt/20 px-[22px] py-5 first:border-t-0 max-[640px]:[&>div:first-child]:w-full">
      <div className="w-[150px] flex-none font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">{k}</div>
      {children}
    </div>
  );
  const links: [string, string][] = [["Solscan", `https://solscan.io/token/${ca}`], ["Chart", `https://dexscreener.com/solana/${ca}`], ["Swap on Jupiter", `https://jup.ag/swap/SOL-${ca}`], ["@geniusproto on X", "https://x.com/geniusproto"]];
  const mods: [string, ReactNode][] = [
    ["What the token is for", "GENIUS is a lab that trades in public. The token is how the build gets funded: the desk that runs today, the compute that comes next, and the road to the 33 machines. Holding it is a way to back the work and to be early to it. It is not a claim on the hardware, the desk wallet or the code, and we will never say it is."],
    ["How to know it is real", "Copy the address from this page. Open it on Solscan. Compare every character with what is in your wallet or on the chart someone sent you. Nothing else counts. We will never message you an address, never ask you to send funds to one, and never run a claim or a mint."],
    ["What we publish", "Every trade the desk takes is on chain, from a wallet that signs nothing else. The console shows the books, the equity curve and the audit report, and a losing day goes up at the same size as a winning one. That is the whole point of doing this in the open."],
    ["Read before you act", <>Nothing on this page is financial advice. The token is early, the market is volatile, and the desk can lose money on any given day. Only put in what you are fine watching move. Questions go to <a href="https://x.com/geniusproto" target="_blank" rel="noopener noreferrer">@geniusproto</a>.</>],
  ];
  return (
    <Section id="token">
      <Kicker num="08" label="The Token" />
      <H2>One <Hi>address</Hi>. Check it here.</H2>
      <p className="dek">$GENIUS is out on Solana. This section is the only place we publish the contract address. If you see a different one anywhere else, in a reply, in a group chat, on an account that looks like ours, it is not ours. Come back here and compare.</p>
      <div className="mt-9 overflow-hidden rounded-lg border border-volt/35 shadow-[0_0_40px_-18px_rgba(166,226,46,.34)]" style={{ background: "linear-gradient(160deg,rgba(166,226,46,.07),rgba(166,226,46,.015))" }}>
        <Row k="Contract address">
          <div className="min-w-0 flex-1 break-all font-mono text-[14px] font-medium text-ink">{ca}</div>
          <button type="button" onClick={() => copy(ca)} className="flex-none rounded-[5px] border border-volt bg-volt px-3.5 py-2.5 font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#07130a] hover:shadow-volt">{done ? "Copied" : "Copy"}</button>
        </Row>
        <Row k="Ticker"><div className="font-display text-[20px] font-extrabold text-volt">{t.ticker ?? "$GENIUS"}</div></Row>
        <Row k="Chain"><div className="font-mono text-[14px] font-medium text-ink">Solana</div></Row>
        <Row k="Verify"><div className="flex flex-wrap gap-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.12em]">
          {links.map(([l, h]) => <a key={l} href={h} target="_blank" rel="noopener noreferrer" className="border-b border-line-2 text-ink-2 no-underline hover:border-volt hover:text-volt">{l}</a>)}
        </div></Row>
      </div>
      <div className="mt-3.5 grid gap-3.5 md:grid-cols-2">
        {mods.map(([h, body]) => (
          <Mod key={h} className="p-[26px]">
            <h5 className="my-2.5 font-display text-[17px] font-bold tracking-[-0.015em] text-ink">{h}</h5>
            <p className="text-[13.5px] leading-[1.6] text-ink-2 [&_a]:text-ink">{body}</p>
          </Mod>
        ))}
      </div>
    </Section>
  );
}

/** True once the address is set; later sections shift one number down the page. */
export const hasToken = () => !!tok().ca;
