/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#060809",
        "bg-2": "#0a0d0f",
        panel: "#0f1315",
        "panel-2": "#141a1c",
        line: "#1e2528",
        "line-2": "#2b3438",
        volt: "#a6e22e",
        "volt-dim": "#6f9a1c",
        cyan: "#35d6e8",
        amber: "#f0a53c",
        danger: "#ff5a5a",
        ink: "#f0f3f2",
        "ink-2": "#9aa5a7",
        "ink-3": "#616c6f",
        /* validated chart pair — see docs/ARCHITECTURE.md */
        "chart-price": "#00a2b8",
        "chart-equity": "#71a10f",
      },
      fontFamily: {
        display: ["Archivo", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        volt: "0 0 30px 2px rgba(166,226,46,.34)",
        "volt-soft": "0 0 22px -6px rgba(166,226,46,.34)",
        mod: "0 18px 44px -22px rgba(0,0,0,.9), 0 0 0 1px rgba(166,226,46,.09)",
      },
      keyframes: {
        slide: { to: { transform: "translateX(-50%)" } },
        float: {
          "0%,100%": { transform: "translateY(-5px)" },
          "50%": { transform: "translateY(5px)" },
        },
      },
      animation: {
        slide: "slide 40s linear infinite",
        float: "float 7s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
