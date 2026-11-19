# Agent Scientist Web UI

Browser chat and administration for Agent Scientist, launched with `sci dashboard`.

Read the [complete web app reference](../website/docs/developer-guide/web-dashboard-reference.md)
for every built-in page, functionality, settings, architecture, file ownership,
scientific viewers, authentication, storage, and troubleshooting.

## Stack

- React 19 + TypeScript + React Router
- Vite + Tailwind CSS v4 + `@sci/ui` components
- Shared JSON-RPC/WebSocket client from `apps/shared`
- Python FastAPI/Uvicorn backend in `sci_cli/web_server.py`
- Mol* for browser molecular structures; xterm for the separate SCI Console

The current Chat page is a native React conversation UI over `/api/ws`.
It does not render the terminal TUI. The landing route is `/sessions`.

## Development

Run these from the repository root with development dependencies prepared:

```bash
# Terminal 1: backend
sci dashboard --no-open

# Terminal 2: frontend with live reload
npm run dev --workspace web
```

Open the Vite URL printed in the terminal, usually `http://localhost:5173`.
Vite proxies `/api` (including WebSockets) and `/dashboard-plugins` to
`http://127.0.0.1:9119`. If the dashboard chose another port, set the existing
`SCI_DASHBOARD_URL` development override when starting Vite.

The URL printed by `sci dashboard` serves the **built** bundle. Source edits
appear there only after rebuilding; restart the backend for Python changes.

## Build and check

```bash
# From the repository root
npm run build --workspace web
npm run check --workspace web
```

The build script is `scripts/build/web.mjs`; the normal output is
`sci_cli/web_dist/`, served by FastAPI. `check` runs TypeScript, Vitest, and ESLint.

## Source structure

```text
web/
├── index.html                 # Document and favicon links
├── public/                    # Static icons, fonts, viewer license
├── vite.config.ts             # Build, code splitting, development proxy
└── src/
    ├── main.tsx               # Providers and React entry
    ├── App.tsx                # Routes, sidebar, shared shell
    ├── index.css              # Global styles
    ├── pages/                 # Chat, Sessions, Files, Models, Config, etc.
    ├── components/chat/       # Native chat composer/transcript/approvals
    ├── components/structure/  # Mol* and server-desktop PyMOL controls
    ├── components/            # Shared controls, logo, SCI Console
    ├── contexts/              # Profile, page header, system actions
    ├── lib/                   # API, WebSocket, state and utility helpers
    ├── themes/                # Theme definitions and font selection
    ├── i18n/                  # Translations and locale selection
    └── plugins/               # Dashboard plugin SDK and slots
```

## Typography & contrast rules

Read before adding or editing UI styles. These rules keep the dashboard legible across all built-in themes and stop drift back into the patterns the design system was just refactored out of.

### Text size floor

- **Minimum body size: `text-xs` (12px / 0.75rem).** Do not use arbitrary `text-[0.6rem]`, `text-[0.65rem]`, `text-[9px]`, `text-[10px]`, or `text-[11px]` on copy, hints, labels, counts, or badges. Use the standard scale: `text-xs`, `text-sm`, `text-base`.
- Smaller sizes are only acceptable on **decorative overlays** (chart stripes, empty-state icons) — never on text the user is meant to read.

### Opacity floor on text

- **Never apply opacity below 0.7 to text.** No `opacity-30`, `opacity-50`, `opacity-60` on `<span>`s, `<p>`s, labels, etc.
- **Do not stack opacity tokens.** Patterns like `text-muted-foreground/60`, `text-midground/70`, `text-foreground/50` create unpredictable WCAG failures because the parent token already has alpha.
- Use the **semantic text tokens** from `@sci/ui`'s `globals.css`:
  - `text-text-primary` — default body text.
  - `text-text-secondary` — subtitles, meta, inactive nav.
  - `text-text-tertiary` — small chrome labels, counts, footnotes.
  - `text-text-disabled` — disabled states.
  - `text-text-on-accent` — text on filled accent surfaces.

### Brand uppercase via `text-display`, not raw `uppercase`

- The dashboard preserves the Nous brand uppercase aesthetic, but it is **opt-in per element, not global**.
- Apply uppercase via the DS utility `text-display` on **brand chrome only** — page titles, nav section headings, badges, brand wordmark. DS components (`Button`, `Badge`, `Tabs`, `Segmented`, etc.) already self-apply `text-display`.
- **Do not introduce new `uppercase`** (the literal Tailwind class) in `sci-agent/web/src`. Prefer `text-display` for new brand chrome. Legacy `uppercase` call sites (e.g. `components/ui/label.tsx`, `card.tsx`) remain until migrated.
- The app shell no longer forces uppercase globally, so blanket `normal-case` opt-outs are unnecessary. Use `normal-case` only where a DS component applies `text-display` but the label should stay sentence case — e.g. dynamic user content (model slugs, theme names) **or** fixed UI copy that is not brand chrome (EnvPage “not configured” toggle, sidebar “New chat”).

### Fonts

Typography is **opt-in per surface**, not global on layout shells — the app shell and page header keep their original theme/expanded fonts; Mondwest applies only where explicitly set.

| Tier | Classes | Use for |
|------|---------|---------|
| Brand chrome | `font-mondwest text-display` (or `themedChrome`) | Sidebar nav, card section headers (`CardTitle`), Segmented filter buttons, filter panel headings |
| Themed body | `font-mondwest normal-case` (or `themedBody`) | Card content (`Card`, `CardDescription`), session/platform rows, analytics tables — **scoped to the component** |
| Page chrome | `font-expanded` | Page header h1 (`PageHeaderProvider`) — sentence case, not `text-display` |
| Wordmark | `Typography` + size/tracking only | Sidebar/mobile “Sci Agent” — mixed case, no Mondwest, no `text-display` |
| Technical | `font-mono-ui` / `font-mono` / `font-courier` | Model slugs, env keys, schedules, YAML, repo URLs |

- Do **not** put `themedBody` or `themedFont` on `<main>`, `App`, or other layout wrappers — it overrides component-scoped styles.
- **`Card`** applies `themedBody`; **`CardTitle`** uses `text-display` (uppercase chrome); **`CardDescription`** uses `themedBody`.
- **`NouiTypography`** defaults to `font-sans` unless a font prop is passed.
- Do **not** use raw `font-sans` or `font-display` (theme sans variable) on new dashboard UI — prefer Mondwest tiers above where brand-appropriate.

### Color tokens

- Prefer **semantic tokens** (`text-text-*`, `bg-card`, `border-border`, `text-foreground`, `text-destructive`, `text-success`, `text-warning`) over raw layer references (`text-midground`, `text-foreground`).
- `text-muted-foreground` is now wired to `--color-text-secondary`, so existing call sites stay correct, but new code should prefer the semantic name.
- When you genuinely need a non-token color (icon de-emphasis on a chart, terminal foreground via inline style), keep alpha at `≥ 0.7` for any text.

