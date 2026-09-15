import { useState, type ReactNode } from "react";
import { H2, Hi, Kicker, Mod, Section } from "./ui";

type Tok = { chain?: string; chainName?: string; chainId?: number; explorer?: string; ca?: string };
const tok = (): Tok => ((window as unknown as { GENIUS_TOKEN?: Tok }).GENIUS_TOKEN ?? {});
const short = (a: string) => `${a.slice(0, 6)}\u2026${a.slice(-4)}`;
const explorerUrl = (t: Tok) => `${t.explorer ?? "https://robinhoodchain.blockscout.com"}/token/${t.ca}`;
const chartUrl = (t: Tok) => `https://dexscreener.com/search?q=${t.ca}`;
const X = "https://x.com/geniusproto";

/** True once the address is set; later sections shift one number down the page. */
export const hasToken = () => !!tok().ca;

function useCopy() {
  const [done, setDone] = useState(false);
  return {
    done,
    copy: (t: string) => navigator.clipboard?.writeText(t).then(() => { setDone(true); setTimeout(() => setDone(false), 1200); }),
  };
}

const Link = ({ href, children, ext = true }: { href: string; children: ReactNode; ext?: boolean }) => (
  <a href={href} {...(ext ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    className="border-b border-line-2 text-ink-2 no-underline hover:border-volt hover:text-volt">{children}</a>
);

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
        <span className="font-display text-[18px] font-extrabold tracking-[-0.01em] text-volt">Contract address</span>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3">{t.chainName ?? "Robinhood Chain"} · official</span>
      </div>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-[5px] border border-line-2 bg-[#0b0f11] px-3 py-2.5 font-mono text-[12.5px] font-medium text-ink">{ca}</code>
        <button type="button" onClick={() => copy(ca)}
          className="flex-none rounded-[5px] border border-volt bg-volt px-3.5 py-2.5 font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#07130a] hover:shadow-volt">
          {done ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="mt-3 flex gap-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.12em]">
        <Link href={explorerUrl(t)}>Explorer</Link><Link href={chartUrl(t)}>Chart</Link><Link href="#token" ext={false}>Details</Link>
      </div>
      <p className="mt-3 font-mono text-[11.5px] leading-[1.6] text-ink-3">This is the only official source for the contract address. If you see an address anywhere else before it appears here, it is fake.</p>
    </div>
  );
}

/** Section 08 / Token. Renders nothing until the address is set. */
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
  const mods: [string, string][] = [
    ["How the fees work", "Every trade carries a fee. Fees fund the project: development first, then buybacks, liquidity and marketing. Every claim and every spend gets posted with its transaction link, so anyone can check where the money went."],
    ["Why a token", "The lab runs today and the console is free to watch. Building the rest properly, the compute, the cluster, and the audits the desk needs before it handles more than pilot money, costs money. The token is how we raise it while keeping the research public. Holding it backs the work. It is not a claim on the hardware or the code."],
  ];
  return (
    <Section id="token">
      <Kicker num="08" label="Token" />
      <H2>Contract<Hi>.</Hi></H2>
      <p className="dek">We are funding the development of GENIUS with a token on {t.chainName ?? "Robinhood Chain"}. This page is the only official source for the contract address. If you see an address anywhere else before it appears here, it is fake.</p>
      <div className="mt-9 overflow-hidden rounded-lg border border-volt/35 shadow-[0_0_40px_-18px_rgba(166,226,46,.34)]" style={{ background: "linear-gradient(160deg,rgba(166,226,46,.07),rgba(166,226,46,.015))" }}>
        <Row k="Contract address">
          <div className="min-w-0 flex-1 break-all font-mono text-[14px] font-medium text-ink">{ca}</div>
          <button type="button" onClick={() => copy(ca)} className="flex-none rounded-[5px] border border-volt bg-volt px-3.5 py-2.5 font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#07130a] hover:shadow-volt">{done ? "Copied" : "Copy"}</button>
        </Row>
        <Row k="Chain"><div className="font-mono text-[14px] font-medium text-ink">{t.chainName ?? "Robinhood Chain"}</div></Row>
        <Row k="Verify"><div className="flex flex-wrap gap-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.12em]">
          <Link href={explorerUrl(t)}>Explorer</Link><Link href={chartUrl(t)}>Chart</Link><Link href={X}>@geniusproto on X</Link>
        </div></Row>
      </div>
      <div className="mt-3.5 grid gap-3.5 md:grid-cols-2">
        {mods.map(([h, body]) => (
          <Mod key={h} className="p-[26px]">
            <h5 className="my-2.5 font-display text-[17px] font-bold tracking-[-0.015em] text-ink">{h}</h5>
            <p className="text-[13.5px] leading-[1.6] text-ink-2">{body}</p>
          </Mod>
        ))}
      </div>
      <p className="mt-6 font-mono text-[12.5px] leading-[1.8] text-ink-3">Nothing on this page is financial advice. Questions: <a href={X} target="_blank" rel="noopener noreferrer" className="text-ink-2">@geniusproto</a>.</p>
    </Section>
  );
}
