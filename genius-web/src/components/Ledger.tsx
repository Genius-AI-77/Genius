import { disclaimer, ledgerRows, navLinks } from "../data/content";
import { GMark, H2, Hi, Kicker, Pill, Section, Wrap } from "./ui";

export function Ledger() {
  return (
    <Section id="ledger">
      <Kicker num="09" label="The Ledger" />
      <H2>
        What's <Hi>real</Hi> today.
      </H2>
      <p className="dek">
        The honest ledger. We would rather lose your attention here than earn it dishonestly
        somewhere else.
      </p>
      <div className="mt-9 overflow-x-auto rounded-lg border border-line bg-panel">
        <table className="w-full min-w-[620px] border-collapse font-mono text-[13.5px]">
          <thead>
            <tr>
              {["Component", "Status", "Notes"].map((h) => (
                <th
                  key={h}
                  className="sticky top-0 border-b border-line bg-[#0b0e10] p-[13px_18px]
                    text-left font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-3"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ledgerRows.map((r) => (
              <tr key={r.component} className="transition-colors hover:bg-volt/[.03]">
                <td className="border-b border-line p-[13px_18px] align-top text-ink">
                  {r.component}
                </td>
                <td className="border-b border-line p-[13px_18px] align-top">
                  <Pill status={r.status} />
                </td>
                <td className="border-b border-line p-[13px_18px] align-top text-ink-2">
                  {r.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

export function Footer() {
  return (
    <footer className="relative z-[2] border-t border-line bg-black py-[clamp(48px,7vw,76px)] pb-14">
      <Wrap>
        <div className="grid gap-[34px] lg:grid-cols-[1.6fr_1fr_1fr]">
          <div>
            <div className="mb-[18px] flex items-center gap-3">
              <GMark className="h-[34px] w-[30px] drop-shadow-[0_0_10px_rgba(166,226,46,.34)]" />
              <span className="font-display text-2xl font-extrabold leading-none tracking-[0.15em] text-ink">
                GENIUS
              </span>
            </div>
            <div className="mb-5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-volt">
              Everyone is a Scientist.
            </div>
            <p className="max-w-[66ch] font-mono text-[12px] leading-[1.8] text-ink-3">
              <strong className="font-medium text-ink-2">
                GENIUS is a research and community project.
              </strong>{" "}
              {disclaimer.replace("GENIUS is a research and community project. ", "")}
            </p>
          </div>
          <div>
            <h6 className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-3">
              The lab
            </h6>
            <ul className="list-none p-0 font-mono text-[13px]">
              {navLinks.slice(0, 5).map((l) => (
                <li key={l.href} className="mb-[11px]">
                  <a href={l.href} className="text-ink-2 no-underline transition-colors hover:text-volt">
                    {l.label}
                  </a>
                </li>
              ))}
              <li className="mb-[11px]">
                <a href="/console/" className="text-ink-2 no-underline transition-colors hover:text-volt">
                  Lab console
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h6 className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-3">
              Status key
            </h6>
            <ul className="list-none p-0 font-mono text-[13px]">
              <li className="mb-[11px]">
                <Pill status="impl" /> shipped &amp; runnable
              </li>
              <li className="mb-[11px]">
                <Pill status="sim" /> real code, synthetic data
              </li>
              <li className="mb-[11px]">
                <Pill status="plan" /> designed, unbuilt
              </li>
              <li className="mb-[11px]">
                <Pill status="block" /> needs a dependency
              </li>
            </ul>
          </div>
        </div>
      </Wrap>
    </footer>
  );
}
