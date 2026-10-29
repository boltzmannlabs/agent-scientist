# web/ + sci_cli/web_routers/ — the dashboard (`sci dashboard` → `/chat`)

Applies on top of the root `AGENTS.md`. Backend routers: `sci_cli/web_routers/*.py`, one file per
dashboard surface, mounted by `sci_cli/web_server.py` (+ `web_server_*.py` siblings). Frontend:
`web/src/`. Shared JSON-RPC/WS client: `apps/shared` (`@sci/shared`), also used by the desktop.

## Native browser chat

The dashboard `/chat` uses a native React conversation interface, as requested by the
product owner. `web/src/pages/ChatPage.tsx` composes the conversation history,
transcript, composer, and interactive requests in `web/src/components/chat/`.

- Reuse `GatewayClient` and authenticated `/api/ws` JSON-RPC. The existing
  `tui_gateway` owns agent behavior, sessions, models, tools, and slash commands.
- `session.create` / `session.resume` bind the owning profile; `prompt.submit`
  streams structured events. Never turn terminal output into browser messages.
- Keep the conversation mounted across dashboard navigation. Reconnect resumes
  authoritative session state and never resends a prompt automatically.
- Approval, clarification, and secret requests use the existing server-request
  protocol. Secrets stay out of transcript and browser persistence.
- Keep prompt and tool state owned by the backend; cosmetic changes never rebuild
  an active agent. Image uploads use the existing scoped gateway attachment RPC.
- `/api/pty` and the standalone Ink TUI remain available to their existing consumers;
  the browser chat no longer spawns a PTY or requires Node on the execution host.

## `dashboard` vs `serve`

`dashboard` and `serve` share `cmd_dashboard` / `start_server` but are independent surfaces — neither
launches the other. `serve` is the headless backend the desktop app spawns (`headless_backend=True`:
`cmd_dashboard` skips `_build_web_ui` and exports `SCI_SERVE_HEADLESS=1` so `mount_spa()`
disables the SPA even if a stray `web_dist/` exists — only JSON-RPC/WS/API is reachable). The
desktop has no build/runtime dependency on this frontend. Details: `apps/desktop/src/AGENTS.md`.

## Rules

- Auth: every new REST route and WS endpoint uses the same session token; never a second scheme.
- Routers are one-file-per-surface; a new surface is a new `web_routers/<surface>.py`, not a growing
  `web_server.py`.
- Tests: Python in `tests/sci_cli/` (routers, pty bridge); JS in the `web/` vitest suite. Python
  tests must not assert about `package.json` / `.tsx` sources (root testing rules). Root TypeScript
  style rules apply.
