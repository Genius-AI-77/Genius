# GENIUS, web

The GENIUS public site as a **Vite + React + TypeScript + Tailwind** app, structured so
Lovable's GitHub importer will accept it.

> This folder is self-contained and must be pushed as **its own repository**. Lovable
> expects a single `package.json` at the repo root and rejects monorepos, so do not push
> the parent GENIUS folder.

## Run locally

```bash
npm install
npm run dev
```

Opens on <http://localhost:8080>. Build with `npm run build`, preview with `npm run preview`.

## Structure

```
index.html                 Vite entry, <head>, fonts, meta tags
tailwind.config.js         brand tokens: volt, cyan, ink, panel, line…
src/
├── main.tsx
├── App.tsx                section order, reorder the page here
├── index.css              base layer + .mod / .btn / .dek component classes
├── data/content.ts        ALL COPY LIVES HERE  ← edit this to change wording
└── components/
    ├── ui.tsx             GMark, Pill, Kicker, H2, Hi, Section, Wrap, Mod
    ├── Chrome.tsx         Stage backdrop, Nav, Ticker
    ├── AgentIcon.tsx      per-agent line icons
    ├── Sections.tsx       Hero, Machine, Agents, Method, Veto, Experiment,
    │                      Token, Challenge
    └── Ledger.tsx         status table + Footer
public/
├── favicon.svg
├── robots.txt
└── console/               the lab console, served verbatim at /console/
    ├── index.html
    └── data.js            regenerate with: python3 lab/run_demo.py
```

### Where to edit what

| To change | Edit |
|---|---|
| Any wording, stat, ledger row, agent description | `src/data/content.ts` |
| Colours, fonts, shadows | `tailwind.config.js` |
| Card / button / heading styling | `src/index.css` |
| Section order, adding or removing a section | `src/App.tsx` |
| Layout of one section | that section in `src/components/Sections.tsx` |

Copy is deliberately separated from markup so it can be edited by prompting without
touching layout.

## The console

`public/console/` is plain static HTML that Vite copies to the build output untouched.
It reads `data.js`, produced by the Python lab in the parent project:

```bash
python3 lab/run_demo.py
```

`run_demo.py` writes this file *and* the mirror in `public/console/` automatically. The
landing page's Experiment section also reads it at runtime, so stats stay current. It is a
build artifact the site needs, so commit it; the daily GitHub Action keeps it fresh.

## Status labels are load-bearing

The `Status` type in `src/data/content.ts` (`impl` / `sim` / `plan` / `block`) drives the
badges across the site. GENIUS publicly commits to labelling every component honestly.
**Do not upgrade a status unless the underlying thing actually changed**, the status
ledger is the product, not a legal footnote.
