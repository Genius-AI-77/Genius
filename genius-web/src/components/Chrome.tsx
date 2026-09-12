import { navLinks, tickerItems } from "../data/content";
import { GMark, Wrap } from "./ui";
import { WalletButton } from "./Wallet";

/** Fixed studio backdrop: volt haze, floor grid, cyan light bars. */
export function Stage() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute left-1/2 top-[-14%] h-[640px] w-[min(1000px,120vw)] -translate-x-1/2
                   rounded-[50%] blur-[30px]"
        style={{
          background:
            "radial-gradient(closest-side, rgba(166,226,46,.13), transparent 70%)",
        }}
      />
      <div
        className="absolute inset-x-[-10%] bottom-0 top-[-10%]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(166,226,46,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(166,226,46,.05) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage:
            "radial-gradient(ellipse 90% 60% at 50% 0%, #000 0%, transparent 72%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 90% 60% at 50% 0%, #000 0%, transparent 72%)",
        }}
      />
      {(["left-[5%]", "right-[5%]"] as const).map((pos) => (
        <div
          key={pos}
          className={`absolute top-[6%] hidden h-[56%] w-[3px] rounded-[3px] opacity-50 blur-[1.5px] md:block ${pos}`}
          style={{
            background:
              "linear-gradient(180deg, transparent, #35d6e8 18%, #35d6e8 82%, transparent)",
            boxShadow: "0 0 34px 8px rgba(53,214,232,.28)",
          }}
        />
      ))}
    </div>
  );
}

export function Nav() {
  return (
    <div className="sticky top-0 z-[60] border-b border-line bg-bg/80 backdrop-blur-[14px]">
      <Wrap className="flex h-[62px] items-center gap-3.5">
        <a href="#top" className="flex items-center gap-[11px] no-underline">
          <GMark className="h-[29px] w-[26px] drop-shadow-[0_0_9px_rgba(166,226,46,.34)]" />
          <span className="font-display text-[20px] font-extrabold leading-none tracking-[0.16em] text-ink">
            GENIUS
          </span>
        </a>
        <nav className="ml-auto flex gap-[26px] font-mono text-[11px] font-medium uppercase tracking-[0.13em]">
          {navLinks.map((l, i) => (
            <a
              key={l.href}
              href={l.href}
              className={`group relative text-ink-3 no-underline transition-colors hover:text-volt
                ${i >= 3 ? "hidden lg:inline" : ""} ${i >= 2 ? "max-[520px]:hidden" : ""}`}
            >
              {l.label}
              <span className="absolute -bottom-1.5 left-0 h-px w-0 bg-volt transition-all duration-200 group-hover:w-full" />
            </a>
          ))}
        </nav>
        <WalletButton />
      </Wrap>
    </div>
  );
}

export function Ticker() {
  const doubled = [...tickerItems, ...tickerItems];
  return (
    <div className="overflow-hidden whitespace-nowrap border-b border-line bg-black font-mono text-[10.5px] font-medium uppercase tracking-[0.16em]">
      <div className="inline-block animate-slide py-2 motion-reduce:animate-none">
        {doubled.map((t, i) => (
          <span key={i} className="px-[22px] text-ink-3">
            <i className="mr-[9px] not-italic text-volt">◆</i>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
