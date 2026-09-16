import type { ReactNode } from "react";
import { STATUS_LABEL, type Status } from "../data/content";

/** The hexagonal GENIUS mark. */
export function GMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 44" className={className} aria-hidden="true">
      <path d="M20 0 40 11v22L20 44 0 33V11Z" fill="#a6e22e" />
      <path
        d="M28.5 14.5H18a4.5 4.5 0 0 0-4.5 4.5v6a4.5 4.5 0 0 0 4.5 4.5h8.5V22h-6.8v3.6h3.1v1.4H18a1.9 1.9 0 0 1-1.9-1.9v-6A1.9 1.9 0 0 1 18 17.2h10.5Z"
        fill="#060809"
      />
    </svg>
  );
}

const STATUS_CLASS: Record<Status, string> = {
  impl: "text-volt border-volt/40 bg-volt/10",
  sim: "text-amber border-amber/40 bg-amber/10",
  plan: "text-cyan border-cyan/35 bg-cyan/10",
  block: "text-ink-2 border-line-2 bg-white/[.03]",
};

/** Status chip, implemented / simulated / planned / blocked. */
export function Pill({ status, children }: { status: Status; children?: ReactNode }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-[3px] border px-2 py-[3px]
        align-[1px] font-mono text-[9.5px] font-semibold uppercase tracking-[0.14em]
        ${STATUS_CLASS[status]}`}
    >
      {children ?? STATUS_LABEL[status]}
    </span>
  );
}

/** Numbered section label: "02 / The Machine" */
export function Kicker({
  num,
  label,
  centered = false,
}: {
  num: string;
  label: string;
  centered?: boolean;
}) {
  return (
    <div
      className={`mb-[clamp(22px,3vw,34px)] flex items-center gap-3.5 font-mono
        text-[11px] uppercase tracking-[0.2em] text-ink-3 ${centered ? "justify-center" : ""}`}
    >
      {centered && <span className="h-px w-[52px] bg-line-2" />}
      <span className="text-volt">{num}</span>
      <span>/ {label}</span>
      {!centered && (
        <span className="h-px flex-1 bg-gradient-to-r from-line-2 to-transparent" />
      )}
    </div>
  );
}

/** Section heading. Wrap words in <em> via the accent prop for volt highlight. */
export function H2({ children }: { children: ReactNode }) {
  return (
    <h2
      className="max-w-[19ch] font-display font-extrabold tracking-[-0.038em] text-ink"
      style={{ fontSize: "clamp(34px,6.4vw,72px)", lineHeight: 0.95, textWrap: "balance" }}
    >
      {children}
    </h2>
  );
}

/** Volt-coloured emphasis inside a heading. */
export function Hi({ children }: { children: ReactNode }) {
  return <span className="text-volt">{children}</span>;
}

export function Section({
  id,
  children,
  first = false,
}: {
  id?: string;
  children: ReactNode;
  first?: boolean;
}) {
  return (
    <section
      id={id}
      className={`relative z-[2] py-[clamp(72px,10vw,132px)] ${first ? "" : "border-t border-line"}`}
    >
      <div className="relative z-[2] mx-auto max-w-[1200px] px-[clamp(20px,5vw,72px)]">
        {children}
      </div>
    </section>
  );
}

export function Wrap({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`relative z-[2] mx-auto max-w-[1200px] px-[clamp(20px,5vw,72px)] ${className}`}>
      {children}
    </div>
  );
}

/** The device-module card. `alert` switches to the red VETO treatment. */
export function Mod({
  children,
  className = "",
  alert = false,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  alert?: boolean;
  as?: "div" | "article";
}) {
  return (
    <Tag className={`mod ${alert ? "mod-alert" : ""} ${className}`}>{children}</Tag>
  );
}
