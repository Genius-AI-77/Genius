/** Line icons for each agent role. Stroke colour is per-agent, matching the brand. */
export function AgentIcon({ name }: { name: string }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    strokeWidth: 2,
    className: "h-[17px] w-[17px]",
  } as const;

  switch (name) {
    case "ATLAS": // bar chart, fundamentals
      return (
        <svg {...common} stroke="#a6e22e">
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </svg>
      );
    case "EUCLID": // trend line, technicals
      return (
        <svg {...common} stroke="#35d6e8" strokeLinejoin="round">
          <path d="M3 17l5-6 4 4 3-4 6 5" />
          <path d="M3 21h18" />
        </svg>
      );
    case "FLUX": // waveform, order flow
      return (
        <svg {...common} stroke="#35d6e8" strokeLinecap="round">
          <path d="M4 6v12M8 9v6M12 3v18M16 8v8M20 11v2" />
        </svg>
      );
    case "HERMES": // arrow, execution
      return (
        <svg {...common} stroke="#a6e22e" strokeLinecap="round">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      );
    case "LEDGER": // document, research & audit
      return (
        <svg {...common} stroke="#a6e22e" strokeLinejoin="round">
          <path d="M5 3h11l4 4v14H5z" />
          <path d="M8 11h8M8 15h5" />
        </svg>
      );
    case "VETO": // shield with a minus, risk, binding
      return (
        <svg {...common} stroke="#ff5a5a" strokeLinejoin="round">
          <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z" />
          <path d="M9 12h6" />
        </svg>
      );
    default:
      return null;
  }
}
