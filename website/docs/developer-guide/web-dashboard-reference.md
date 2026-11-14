---
title: Agent Scientist Web App Reference
description: Complete dashboard feature guide, architecture, technology stack, source ownership, and development workflow.
---

# Agent Scientist Web App Reference

Agent Scientist's web app, launched with `sci dashboard`, provides browser chat and administration of an SCI installation. It combines a React frontend with the Python agent backend: conversations use the same agent runtime, provider authentication, tools, skills, and profile state as the other SCI interfaces.

This guide covers the built-in pages, controls, scientific viewers, storage, authentication, extension points, and source files. It describes the implementation at **10 November 2026**, checkout **`dabe6cc39c`**. Installed plugins can add pages and controls beyond this inventory. Availability also depends on the selected profile, connected services, and server configuration.

All source paths below are **relative to the repository root**. On this development machine that root is `/home/boltzmann20/storage2/Perception_agent`; `/home/boltzmann20/Perception_agent` is a symlink to it. For example, `web/src/App.tsx` means `/home/boltzmann20/storage2/Perception_agent/web/src/App.tsx`. Runtime data belongs to the selected SCI home, not the source directory.

## Contents

1. [Starting and operating the app](#starting-and-operating-the-app)
2. [Architecture and technology stack](#architecture-and-technology-stack)
3. [Application shell and shared controls](#application-shell-and-shared-controls)
4. [Page and feature inventory](#page-and-feature-inventory)
5. [Scientific workflows and structure viewers](#scientific-workflows-and-structure-viewers)
6. [Backend interfaces and source ownership](#backend-interfaces-and-source-ownership)
7. [Profiles, persistence, and authentication](#profiles-persistence-and-authentication)
8. [Appearance and branding](#appearance-and-branding)
9. [Development, builds, and verification](#development-builds-and-verification)
10. [Troubleshooting and implementation boundaries](#troubleshooting-and-implementation-boundaries)

## Starting and operating the app

```bash
sci dashboard
```

The launcher normally opens the browser at `http://127.0.0.1:9119`. Without an explicit port it can try subsequent ports if necessary; use the actual URL printed by the launcher. A compatible running machine dashboard can be reused. The root route redirects to **Sessions**; open `/chat` for the scientific conversation interface.

| Command or option | Function |
| --- | --- |
| `sci dashboard` | Launch the web UI and normally open a browser. |
| `sci dashboard --no-open` | Launch without opening a browser. Useful for an SSH session or supervised service. |
| `sci dashboard --port 9125` | Request that specific port. Explicit ports do not silently switch to another port. |
| `sci dashboard --port 0` | Let the operating system allocate a free port. |
| `sci dashboard --host 127.0.0.1` | Bind to loopback, the default. |
| `sci dashboard --host 0.0.0.0` | Listen beyond loopback; requires a configured dashboard authentication provider. |
| `sci dashboard --status` | List running SCI dashboard/server processes. |
| `sci dashboard --stop` | Stop running SCI web server processes. This is broader than closing a browser tab. |
| `sci -p research dashboard` | Open the machine dashboard with `research` selected, subject to launcher routing. |
| `sci -p research dashboard --isolated` | Request a dedicated server for that profile. |
| `sci dashboard --skip-build` | Serve an existing frontend build without building it at startup. It does not compile new frontend edits. |
| `sci dashboard register` | Register the optional Nous Portal dashboard OAuth integration. Supports `--name`, `--redirect-uri`, and `--portal-url`. |
| `--insecure` | Deprecated, accepted as a no-op; it does not disable the authentication requirement. |
| `sci serve` | Run the shared backend headlessly for clients such as Desktop. It is not the command for the browser dashboard. |

Launcher ownership is split across `sci_cli/subcommands/dashboard.py` (arguments), `sci_cli/main.py::cmd_dashboard` (dispatch), `sci_cli/main_dashboard.py` (routing and process lifecycle), `sci_cli/main_web_build.py` and `sci_cli/source_build.py` (frontend preparation), and `sci_cli/web_server.py::start_server` (server startup).

For remote access, a loopback server can be reached through an SSH tunnel. Substitute the actual server and dashboard port:

```bash
# On the server
sci dashboard --no-open

# On the client
ssh -L 9119:127.0.0.1:9119 user@server
```

Open `http://127.0.0.1:9119` on the client. Server file paths still refer to the server. Direct public access requires dashboard authentication and an appropriate HTTPS/reverse-proxy deployment; model-provider login and dashboard login are separate concerns.

## Architecture and technology stack

### How a browser action reaches the agent

```text
Browser
  web/index.html -> web/src/main.tsx -> web/src/App.tsx
    |
    +-- Administration pages -> web/src/lib/api.ts -> HTTP /api/...
    |                                              |
    |                                 sci_cli/web_routers/*.py
    |                                              |
    |                                 SCI config/state/services
    |
    +-- Native Chat -> useWebChat.ts -> GatewayClient
                                           |
                                      WebSocket /api/ws
                                           |
                         sci_cli/web_routers/chat_ws.py
                                           |
                         tui_gateway/ws.py + server.py
                                           |
                               shared agent runtime
                                           |
                             providers / tools / plugins
```

The frontend is a **single-page application**. React Router changes pages without a full document reload. Pages load lazily, and the server serves the SPA entry point for supported browser navigation. The Python server also supports transports used by Desktop and terminal clients; an available backend endpoint does not automatically mean the browser has a corresponding screen.

The current `/chat` page is **native React chat**, not an xterm rendering of `sci --tui`. xterm and PTY infrastructure remain in the repository for console and other client paths. Older descriptions and some comments still refer to the earlier terminal-based chat implementation.

### Stack and responsibilities

Versions are the direct declarations in `web/package.json` at the revision above, not a claim about arbitrary installed copies.

| Layer | Technology | Responsibility and source |
| --- | --- | --- |
| Frontend language | TypeScript 6.0.3 | Typed React components, API models, shared transport types; `web/tsconfig*.json`. |
| UI runtime | React / React DOM 19.2.7 | Components, hooks, rendering; `web/src/main.tsx`. |
| Routing | React Router 8.3.0 | Built-in pages, deep links, profile query parameters; `web/src/App.tsx`. |
| Development and bundling | Vite 8.2.0, React plugin, React Compiler | HMR, code splitting, compilation; `web/vite.config.ts`. |
| Styling | Tailwind CSS 4.3.3, CSS variables, component CSS | Layout, themes, chat, animations; `web/src/index.css`, `web/src/themes/`, `web/src/components/chat/chat.css`. |
| UI components | `@sci/ui` 1.0.0 and local components | Buttons, cards, dialogs, selectors, tables, toasts, typography. Imports use `@sci/ui/ui/components/...`. |
| Shared client code | Local `@sci/shared` workspace | JSON-RPC client/types, theme palettes, command parsing; `apps/shared/src/`. |
| Icons | Lucide React | Navigation and action icons. |
| Scientific 3D | Mol* 5.13.1 and WebGL | Browser PDB/mmCIF visualization; `web/src/components/structure/`. |
| Animation and visualization dependencies | Motion, GSAP, Three.js, React Three Fiber, Observable Plot | Available to UI/design-system features; not every page or animation uses each library. The dotted logo has its own canvas implementation. |
| Terminal support | xterm.js 6.0.0 and fit, Unicode, links, WebGL addons | Console/terminal surfaces; not the current native chat transcript. |
| HTTP backend | Python, FastAPI, Starlette, Uvicorn | Routes, validation, auth, static assets, background operations; `sci_cli/web_server.py`. Python dependencies are declared in `pyproject.toml`. |
| Bidirectional transport | WebSocket and JSON-RPC | Streaming chat, interactive requests, lifecycle events; `tui_gateway/`. |
| Persistent state | SCI configuration files and session database | Profile settings, secrets, conversations, plugin state. The browser does not replace the server's state store. |
| Testing and linting | Vitest, TypeScript, ESLint; Python test suite | Frontend behavior, type checks, API and profile-scope tests. |

### Frontend build and delivery

`web/src/` is source. `sci_cli/web_dist/` is the normal compiled output served by the dashboard. Editing source alone does not change an already served production bundle.

`web/package.json` delegates builds to `scripts/build/web.mjs`. That script type-checks the TypeScript project graph, invokes Vite, incorporates public assets/prepared icons, and records build inputs. `scripts/build/frontend-common.mjs` and `scripts/build/freshness.mjs` support the build. `sci_cli/web_server_dashboard.py::mount_spa` serves assets and injects runtime bootstrap values, including base-path/profile/auth information. HTML uses no-store caching; content-hashed assets can be cached immutably.

## Application shell and shared controls

| Component | User-facing behavior | Responsible files |
| --- | --- | --- |
| Main navigation | Built-in pages, plugin pages, active-route highlighting, collapsible desktop sidebar, mobile navigation. | `web/src/App.tsx` |
| Page heading and actions | Pages supply their title, badges, filters, refresh controls, and action buttons to a shared header. | `web/src/contexts/PageHeaderProvider.tsx`, `web/src/contexts/usePageHeader.ts` |
| Profile selection | Selects the management target; preserves selection across navigation and expresses it as `?profile=...`. | `web/src/components/ProfileSwitcher.tsx`, `web/src/contexts/ProfileProvider.tsx`, `web/src/lib/profile-bootstrap.ts` |
| Scope banner | Identifies when the managed profile differs from the server's own scope. | `web/src/components/ProfileScopeBanner.tsx` |
| Gateway status | Reports gateway/platform status; shared restart/update actions show confirmation and progress. | `web/src/components/SidebarStatusStrip.tsx`, `web/src/hooks/useSidebarStatus.ts`, `web/src/contexts/SystemActions.tsx`, `web/src/App.tsx` |
| Resource warnings | Shows memory/disk pressure and relevant unexpected-restart warnings from backend status. | `web/src/components/MemoryPressureBanner.tsx` |
| Shared-runtime warning | Explains multiplex/standalone runtime conditions. | `web/src/components/MultiplexStandaloneBanner.tsx`, `web/src/lib/shared-gateway.ts` |
| Authentication widget | Displays dashboard authentication state and login/logout-related actions. | `web/src/components/AuthWidget.tsx` |
| Appearance | Theme and font selection, including responsive picker presentation. | `web/src/components/ThemeSwitcher.tsx`, `web/src/themes/` |
| Language | Translated navigation and administration copy with locale persistence. | `web/src/components/LanguageSwitcher.tsx`, `web/src/i18n/` |
| Confirmations and notifications | Confirm destructive operations; display load errors, success/failure toasts, and modal state. | `web/src/components/ConfirmDialog.tsx`, `web/src/components/DeleteConfirmDialog.tsx`, `web/src/components/LoadErrorNotice.tsx`, shared UI components |
| Branded entrance | Muted intro video with Skip and Escape; skipped for reduced-motion preference. | `web/src/components/BrandEntrance.tsx`, `web/src/components/brand-entrance.css`, `web/src/assets/agent-scientist-intro.mp4` |

## Page and feature inventory

### Chat — `/chat`

Chat provides a conversation interface with a history rail, active model/profile display, model-settings link, new-chat button, transcript, and composer.

- **Send messages:** Enter sends; Shift+Enter inserts a newline. The composer grows with the text. Send is disabled while disconnected or already busy.
- **Stream responses:** Assistant text arrives incrementally, alongside working/status indicators. Completed assistant responses have Copy controls.
- **Inspect tool activity:** Tool start/completion events appear as expandable cards containing the returned text or summary. These are not a dedicated scientific job dashboard.
- **Attach images:** File selection or clipboard paste accepts PNG, JPEG, GIF, WebP, and BMP, up to 25 MiB per image in the composer. Remove attachments before sending if needed. A text prompt is required; images are not sent with slash commands.
- **Stop a response:** Sends `session.interrupt` and reports whether stopping was confirmed. Interrupting the agent does not inherently cancel a remote scientific service job.
- **New or resumed conversations:** New chat creates a new conversation; history selection resumes a stored session. `/new` and `/reset` are handled by the browser as new-chat actions.
- **Workspace selection:** Choose a known project/repository or another server path through the history rail. The stored choice applies to a new conversation; a resumed conversation uses its saved context.
- **Reconnect:** A disconnected chat shows a Reconnect action. Recovery resumes the saved conversation and restores available transcript/in-flight state rather than automatically resending the last prompt. The connection requests `close_on_disconnect: false`; a browser disconnect alone is not a confirmed cancellation.
- **Clarifications:** Choice buttons and free-text answers are supported, including multi-selection when requested by the backend.
- **Approvals:** The browser renders the backend's offered choices, such as Allow once, Allow for this session, Always allow, and Deny.
- **Secure input:** Password-type inputs handle secret, sudo, and supported vault requests. Unsupported interactive request types fail explicitly rather than being silently approved.
- **Service connections:** A connection card shows the service, requested action, requirements/tools, scan information, credential fields, authorization link, and Approve/Skip/Continue controls.
- **Slash commands:** Commands go through the shared slash/command dispatcher. Some return text or prefill a prompt; not every CLI dialog has a browser equivalent.
- **Empty state:** Animated dotted Boltzmann logo and suggestions for literature, data understanding, and research planning. Suggestions prefill the composer; they do not immediately send a request.

The chat host remains mounted after its first visit when navigating between dashboard pages. Switching profiles creates a new profile-owned chat view and clears a conflicting resume URL. Browser session storage remembers the last durable chat identifier per profile; the actual conversation remains server-owned.

| Responsibility | File |
| --- | --- |
| Chat page composition and conversation switching | `web/src/pages/ChatPage.tsx` |
| Connection, create/resume, send, interrupt, event handling | `web/src/components/chat/useWebChat.ts` |
| Transcript and streaming state reducer | `web/src/lib/web-chat-state.ts` |
| Message display, tool cards, copy, empty state | `web/src/components/chat/ChatTranscript.tsx` |
| Text input, keyboard handling, image selection | `web/src/components/chat/ChatComposer.tsx` |
| Clarification, approval, secret forms | `web/src/components/chat/ChatRequest.tsx` |
| Service-access review | `web/src/components/chat/ChatConnection.tsx` |
| History and workspace selector | `web/src/components/ChatSessionList.tsx`, `web/src/components/ChatWorkspacePicker.tsx` |
| Message Markdown and structure links | `web/src/components/Markdown.tsx` |
| Native chat layout | `web/src/components/chat/chat.css` |
| WebSocket client and server adapter | `web/src/lib/gatewayClient.ts`, `sci_cli/web_routers/chat_ws.py`, `tui_gateway/ws.py` |

### Sessions — `/sessions`

The default landing page manages stored conversations. It provides searchable/filterable session lists, pagination, source/profile context, transcript inspection, message/tool details, and resume-in-chat actions. Search results can navigate to matching conversation content.

Actions include renaming a session, exporting session JSON, importing exported JSON/JSONL, deleting an individual session, selecting sessions for bulk deletion, removing empty sessions, and pruning older sessions. Destructive actions are confirmed. Session JSON export is a structured data export; it should not be confused with the CLI's user-facing Markdown `/export-chat` output.

**Files:** `web/src/pages/SessionsPage.tsx`; supporting `web/src/lib/session-import.ts`, `session-prune.ts`, `session-refresh.ts`; backend `sci_cli/web_routers/sessions.py` and `sci_cli/web_server_sessions.py`. Profile-aggregated listings are in `sci_cli/web_routers/profiles.py`.

### Files — `/files`

Browse server files and folders with path navigation, refresh, file metadata, directory creation, uploads, drag-and-drop uploads, downloads, structure previews, and deletion confirmation. Structure files have a **3D** action. **Open local structure** selects a browser-local structure for viewing without uploading it to SCI.

The server returns whether the path can be changed and whether a managed root is enforced. A normal local install starts at the server user's home and may allow navigation elsewhere. A configured/hosted managed root restricts navigation to that root. The Files page is therefore **not universally restricted to the selected profile's workspace**. Sensitive file and path policies still apply. Browser uploads to Files are distinct from uploading a scientific input to Boltzmann.

**Files:** `web/src/pages/FilesPage.tsx`, `sci_cli/web_routers/files.py`, `sci_cli/web_server_files.py`; structure components are described below.

### Analytics — `/analytics`

When enabled, this page offers 7-, 30-, and 90-day views, refresh, daily input/output token charts, model breakdowns, skill usage, and sortable tables.

The page is gated by `dashboard.show_token_analytics`; absent/false shows an explanation instead of the analytics view. Treat these as **local recorded usage/debug statistics**, not a complete provider bill or a guaranteed count of every auxiliary call/retry. Displayed cost estimates are not billing receipts. The browser should not be described as providing provider-independent exact per-response accounting.

**Files:** `web/src/pages/AnalyticsPage.tsx`, `sci_cli/web_routers/analytics.py` (`/api/analytics/usage`), `web/src/lib/api.ts` (response types).

### Models — `/models`

Shows configured/used models and controls model assignment. The page includes the default model, auxiliary-task assignments, reasoning-related controls where supported, model information, and mixture-of-agents configuration. The selector is populated by backend model options and provider availability.

Auxiliary slots represented in the UI include vision, compression, Skills Hub, smart approval, MCP routing, title generation, review, triage specification, Kanban decomposition, profile description, and curator. Mixture-of-agents settings provide presets and reference-model selection. Usage views support 7-, 30-, and 90-day periods; token/cost fields have the same optional analytics gate.

Saving a default and changing an existing conversation are distinct operations. Use the page's returned reload/continuation guidance; changing saved settings is not a promise that an active session's cached prompt has been rebuilt.

**Files:** `web/src/pages/ModelsPage.tsx`, `web/src/components/ModelPickerDialog.tsx`, `ModelInfoCard.tsx`, `ReasoningPicker.tsx`, `ModelReloadConfirm.tsx`; `sci_cli/web_routers/models.py`; usage aggregation in `sci_cli/web_routers/analytics.py`.

### Logs — `/logs`

Read `agent`, `errors`, or `gateway` logs; filter by ALL/DEBUG/INFO/WARNING/ERROR and by component (all, gateway, agent, tools, CLI, cron). Choose 50, 100, 200, or 500 lines, refresh manually, or enable five-second auto-refresh. Severity styling uses log-level classification rather than treating any occurrence of “error” in a payload as an error record.

**Files:** `web/src/pages/LogsPage.tsx`, `web/src/lib/log-classify.ts`, `sci_cli/web_routers/status.py` (`/api/logs`), `sci_logging.py`.

### Cron — `/cron`

Create and manage scheduled work, inspect job details and run history, pause/resume a schedule, trigger it now, edit it, or delete it. The page supports profile filtering/ownership and automation blueprints.

The create/edit forms cover name and prompt, schedule builder, delivery destination, skill/toolset selection, provider/model overrides, working directory, and advanced execution fields. Script-only `no_agent` mode is available for delivering script output without an agent pass. The schedule builder translates user choices to the backend's supported schedule representation. Available delivery destinations depend on configured channels.

**Files:** `web/src/pages/CronPage.tsx`, `web/src/components/ScheduleBuilder.tsx`, `AutomationBlueprints.tsx`, `web/src/lib/schedule.ts`, `cron-job.ts`; backend `sci_cli/web_routers/cron.py`, `sci_cli/web_server_cron.py`, and `cron/jobs.py`.

### Skills and toolsets — `/skills`

Browse and search skills and toolsets, filter the catalog, toggle availability, inspect setup state, and edit supported skill content. The hub section searches external skill listings, shows inspection/scan information, installs selected entries, and updates hub-managed skills with action progress.

Toolset configuration opens a drawer rather than requiring users to edit raw configuration. Depending on the toolset, it exposes required environment values, provider/model choice, setup steps, and terminal-backend controls. Enabling a skill supplies instructions; it does not itself create credentials or grant every tool permission.

**Files:** `web/src/pages/SkillsPage.tsx`, `web/src/components/SkillEditorDialog.tsx`, `ToolsetConfigDrawer.tsx`; `sci_cli/web_routers/skills.py` and `tools.py`.

### Plugins — `/plugins`

Lists installed and catalog plugins, searches the catalog, installs a plugin from supported source inputs, rescans discoveries, enables/disables plugins, updates them, removes them, and controls sidebar visibility for dashboard integrations.

The provider area selects/configures memory providers and the context engine. Memory setup can expose dependency actions, configuration fields, secret fields, and provider authorization/setup status. Dashboard plugins can add UI pages; a tool-only plugin does not automatically have a dashboard page.

**Files:** `web/src/pages/PluginsPage.tsx`, `web/src/plugins/`, `web/src/lib/memory-provider-setup.ts`; `sci_cli/web_routers/dashboard_ui.py`, `memory_providers.py`, `sci_cli/web_server_dashboard.py`, and `web_server_memory.py`.

### MCP — `/mcp`

Manage Model Context Protocol server connections. Add a server using supported command/stdio or remote transport details, configure environment/authentication inputs, enable/disable a server, test a connection, remove it, and install catalog entries. Supported OAuth servers have an authentication action and flow-status handling.

The page manages connectivity; the active conversation's allowed tool set and permissions remain governed by runtime policy. A successful configuration save is distinct from a successful connection test.

**Files:** `web/src/pages/McpPage.tsx`, `web/src/lib/mcp-dashboard-oauth.ts`, `mcp-server-create.ts`; `sci_cli/web_routers/mcp.py`, `sci_cli/web_server_mcp.py`.

### Channels — `/channels`

Configure messaging-platform integrations, edit their settings/credentials, enable or disable them, test supported connections, and restart the messaging gateway when required. Telegram and WhatsApp have guided onboarding flows with progress/status, cancellation, and apply steps; WhatsApp includes QR-based setup where supported.

This is messaging integration management. Starting `sci dashboard` is not by itself proof that every messaging gateway or channel is running.

**Files:** `web/src/pages/ChannelsPage.tsx`, `web/src/components/PlatformsCard.tsx`; `sci_cli/web_routers/messaging.py`, `sci_cli/web_server_messaging.py`, with platform implementations under `gateway/platforms/`.

### Webhooks — `/webhooks`

Enable webhook handling, create named webhook subscriptions, configure the supported request/prompt fields, inspect/copy generated integration values, toggle subscriptions, and delete them. The page can restart the gateway after relevant configuration changes. Webhooks trigger server work; they are separate from the browser's chat WebSocket.

**Files:** `web/src/pages/WebhooksPage.tsx`, `sci_cli/web_routers/ops.py` (`/api/webhooks` family).

### Pairing — `/pairing`

Review pending messaging-user pairing requests, approve a request, inspect approved users, revoke access, and clear pending requests. Pairing controls channel-user access; it is distinct from dashboard login and model-provider authentication.

**Files:** `web/src/pages/PairingPage.tsx`, `sci_cli/web_routers/ops.py` (`/api/pairing` family).

### Profiles — `/profiles` and `/profiles/new`

Profiles group related configuration and working state. The management page lists profiles and supports creation/cloning, rename, delete, active-profile selection, model assignment, description editing/generation, and SOUL/personality editing. Setup links/commands guide users to profile-specific configuration.

The dedicated builder follows **Identity → Model → Skills → MCPs → Review**. It collects selections before creating the profile. Hub-skill installations may continue after profile creation and are reported separately; “profile created” does not imply every background install has already completed.

The sidebar management selection, stored active profile, and already-running conversation are related but distinct states. Backend export/import endpoints also exist, but the built-in Profiles page should not be documented as having buttons that it does not render.

**Files:** `web/src/pages/ProfilesPage.tsx`, `ProfileBuilderPage.tsx`, `web/src/contexts/ProfileProvider.tsx`; `sci_cli/web_routers/profiles.py`, `sci_cli/web_server_profiles.py`, `sci_cli/profiles.py`.

### Config — `/config`

Edit configuration with schema-generated fields or raw YAML. Search/filter settings, inspect category sections, save changes, import/export configuration, and reset the selected scope to defaults with confirmation.

Categories come from the backend schema; examples include general agent settings, terminal, display, delegation, memory, compression, security, browser, voice/TTS/STT, logging, auxiliary models, sessions, and tool-loop guardrails. A setting's presence in this editor does not mean the web app has a dedicated UI for that feature. Saved changes can require a new session or runtime restart depending on the setting.

**Files:** `web/src/pages/ConfigPage.tsx`, `web/src/components/AutoField.tsx`, `web/src/lib/nested.ts`; `sci_cli/web_routers/config_env.py`, raw-YAML endpoints in `analytics.py`, `sci_cli/web_server_config.py`.

### Keys — `/env`

Manage provider and tool credentials by category. Save, replace, clear, or explicitly reveal supported stored values; add custom environment keys; inspect configured/unconfigured state; and use supported provider OAuth login controls. OAuth setup can require a browser/device flow and polling before success is confirmed.

The management target follows the selected profile. Keys in this page authenticate services and model providers; they do not substitute for dashboard access control.

**Files:** `web/src/pages/EnvPage.tsx`, `web/src/components/OAuthProvidersCard.tsx`, `OAuthLoginModal.tsx`, `web/src/lib/env-state.ts`; `sci_cli/web_routers/config_env.py`, `oauth.py`, `sci_cli/web_server_oauth.py`.

### System — `/system`

This page consolidates operations and diagnostics:

| Area | Available operations |
| --- | --- |
| Runtime health | Gateway and host status, resource statistics, links to logs, platform/runtime information. |
| Gateway lifecycle | Start, stop, restart; inspect shared-gateway migration plan and perform supported migration. Shared restart explains affected profiles. |
| Updates | Check for updates, inspect availability, run supported update operations, and monitor action output. Externally managed installations may disable in-app updating. |
| Memory | Inspect available memory information/provider state and reset selected memory state after confirmation. |
| Curator | Inspect state, pause/resume, and run a review. |
| Credential pool | Inspect entries, add an entry, remove a selected entry. |
| SCI Console | Open an xterm-based command console with command history, supported command execution, and required confirmations. |
| Diagnostics | Doctor, security audit, prompt-size inspection, support dump, config migration, skill updates. |
| Backup and restore | Create/download a backup, select a server archive or upload a backup, and confirm restore. |
| Debug sharing | Generate supported debug-share output with the UI's redaction option. |
| Checkpoints | Inspect stored checkpoints and prune them with confirmation. |
| Shell hooks | Inspect, add, and remove configured hooks. |
| Portal | Inspect portal-related state and available links. |

The console uses `web/src/components/SciConsoleModal.tsx`, `/api/console` in `sci_cli/web_routers/chat_ws.py`, and `sci_cli/console_engine.py`. It is a separate component from native Chat.

Long operations expose progress/log output using the shared action-status mechanism. A started operation is not a completed one; the final action state is the result to report.

**Files:** `web/src/pages/SystemPage.tsx`, `web/src/contexts/SystemActions.tsx`; `sci_cli/web_routers/ops.py`, `actions.py`, `status.py`, `sci_cli/web_server_gateway.py`.

### Documentation — `/docs`

Renders the repository's root `README.md` through the app's Markdown component, with plugin slots above and below. It is **not** an embedded copy of every page in the Docusaurus documentation website. README content is imported at frontend build time.

**Files:** `web/src/pages/DocsPage.tsx`, `README.md`, `web/src/components/Markdown.tsx`.

## Scientific workflows and structure viewers

### Boltzmann integration

Scientific work is requested in Chat and executed by the shared agent with the selected profile's enabled capabilities and authorization. The browser does not independently implement antibody generation, molecular screening, enzyme tools, or remote job execution.

The integration includes tool discovery/contracts, input validation, upload, submission, status monitoring, downloading, and result handling. Which scientific operations are available depends on the installed Boltzmann plugin and current service contracts. Scientific outputs can be inspected through the transcript's links and the Files page when allowed by the server's file policy.

| Responsibility | Repository location |
| --- | --- |
| Plugin registration and manifest | `plugins/boltzmann/__init__.py`, `plugins/boltzmann/plugin.yaml` |
| Tool execution and schemas | `plugins/boltzmann/tools.py`, `schemas.py` |
| Authorization and preflight | `plugins/boltzmann/auth.py`, `preflight.py` |
| Validation and upload receipts | `plugins/boltzmann/file_validation.py`, `receipt_store.py` |
| Durable job state and monitoring | `plugins/boltzmann/job_store.py`, `job_monitor.py`, `job_continuation.py`, `job_notifications.py` |
| Output location and result handling | `plugins/boltzmann/output_paths.py`, `results.py` |
| Scientific instructions and contracts | `plugins/boltzmann/skills/boltzmann-tools/SKILL.md` and its `references/` directory |

There is no built-in `/experiments` page or dedicated saved-specialist editor in the current route table. Plugin routes can extend the UI. A conversational tool capability should not be presented as a standalone browser form unless that form actually exists.

### Interactive browser structure viewer

Use **3D** in Files or a supported structure link in rendered Markdown. Alternatively, select **Open local structure** to view a browser-local file. Supported formats are `.pdb`, `.cif`, and `.mmcif`, with a 20 MiB structure limit.

Mol* supports rotation, zoom, residue selection, measurement, representation controls, and image export. Controls adapt to viewport width. Browser-local files are read locally; server files use authenticated SCI file access. The viewer disables remote-state/volume-streaming features in this integration and reports unsupported, empty, oversized, unreadable, or WebGL-unavailable inputs.

Opening a structure visualizes its contents; it does not establish experimental validity or scientific correctness.

**Files:** `web/src/components/structure/StructurePreview.tsx` (entry controls/dialog), `StructureViewport.tsx` (Mol* lifecycle), `structure-preview.css` (layout), `web/src/lib/structure-source.ts` (formats/links/size checks), and `web/public/molstar-LICENSE.txt`.

### PyMOL Desktop

A server-backed structure dialog also offers **PyMOL Desktop**. It checks the profile-managed runtime, offers installation if missing, lists accessible server desktops, and launches a separate PyMOL window on the selected desktop. It opens a temporary structure copy and reports the process, version, and loaded atom count. The original input is preserved.

This window appears on the **SCI server's graphical desktop**, not inside the browser or automatically on a remote user's computer. A graphical session/remote desktop is needed. An SSH tunnel only exposes the web app. Once launched, close the window in PyMOL; closing the browser dialog does not close PyMOL. Installation can continue after the panel closes.

**Files:** `web/src/components/structure/PyMOLDesktop.tsx`, `sci_cli/web_routers/structures.py`, `sci_cli/web_pymol.py`. Endpoints are `GET /api/structures/pymol`, `POST /api/structures/pymol/install`, and `POST /api/structures/pymol/launch`.

## Backend interfaces and source ownership

### HTTP API groups

`web/src/lib/api.ts` centralizes typed requests, errors, auth, base paths, and profile propagation. `sci_cli/web_server.py` assembles the FastAPI application and mounts the routers. The following table identifies the implementation owner; route families include multiple operations rather than a single generic handler.

| API area | Representative paths | Owning file under `sci_cli/web_routers/` |
| --- | --- | --- |
| Status, logs, host metrics | `/api/status`, `/api/health`, `/api/system/stats`, `/api/logs` | `status.py` |
| Sessions | `/api/sessions`, `/api/sessions/search`, `/api/sessions/{session_id}/messages`, `/export` under a session | `sessions.py` |
| Profiles and aggregated sessions | `/api/profiles`, `/api/profiles/active`, `/api/profiles/sessions` | `profiles.py` |
| Config and secrets | `/api/config`, `/api/config/schema`, `/api/env`, `/api/env/reveal` | `config_env.py` |
| Raw config and analytics | `/api/config/raw`, `/api/analytics/usage`, `/api/analytics/models` | `analytics.py` |
| Models | `/api/model/options`, `/api/model/set`, `/api/model/auxiliary`, `/api/model/moa` | `models.py` |
| Provider OAuth | `/api/providers/oauth` and provider start/poll/submit paths | `oauth.py` |
| Skills and hub | `/api/skills`, `/api/skills/hub/...` | `skills.py` |
| Toolset setup | `/api/tools/toolsets`, `/api/tools/terminal/backend` | `tools.py` |
| MCP | `/api/mcp/servers`, `/api/mcp/catalog`, `/api/mcp/oauth/...` | `mcp.py` |
| Cron | `/api/cron/jobs`, `/api/cron/delivery-targets`, `/api/cron/blueprints` | `cron.py` |
| Messaging setup | `/api/messaging/platforms`, Telegram/WhatsApp onboarding paths | `messaging.py` |
| Pairing, webhooks, memory, backups, hooks | `/api/pairing`, `/api/webhooks`, `/api/memory`, `/api/ops/...` | `ops.py` |
| Gateway/update actions | `/api/gateway/restart`, `/api/sci/update`, `/api/actions/{name}/status` | `actions.py` |
| Files and media | `/api/files`, `/api/files/read`, `/api/files/upload`, `/api/media` | `files.py` |
| Structures | `/api/structures/pymol` and its install/launch actions | `structures.py` |
| Themes, fonts, plugins | `/api/dashboard/themes`, `/api/dashboard/font`, `/api/dashboard/plugins`, `/dashboard-plugins/...` | `dashboard_ui.py` |
| Memory-provider setup | `/api/memory/providers/{name}/config`, `/setup` | `memory_providers.py` |
| Chat workspace discovery | `/api/chat/workspaces` | `chat_workspaces.py` |

Additional backend families—`audio.py`, `git.py`, `local_models.py`, and `display.py`—serve shared client capabilities. They do not imply that this dashboard currently exposes a voice-call composer, full Git review page, local-model manager, or streamed-computer-desktop page. Keep frontend route/component evidence separate from backend availability.

### Chat protocol

| RPC/event | Purpose |
| --- | --- |
| `session.create` / `session.resume` | Create or restore a profile-owned runtime conversation. |
| `prompt.submit` | Send a prompt to the shared agent. |
| `image.attach_bytes` | Attach encoded image data before the prompt. |
| `session.interrupt` | Request interruption of the active response. |
| `slash.exec` / `command.dispatch` | Execute supported commands or resolve a command action. |
| `connection.respond` | Return a user's service-connection decision. |
| `message.delta`, `message.interim`, `message.complete` | Stream text and settle the turn. |
| `tool.start`, `tool.complete`, `tool.generating` | Report tool activity. |
| `status.update`, `session.info`, `notice`, `error` | Progress, session metadata, and failure information. |
| Server requests such as `approval`, `clarify`, `secret`, `sudo` | Request explicit user input through a browser form. |

The browser adapter is `web/src/lib/gatewayClient.ts`; shared protocol/client code lives in `apps/shared/src/`. The HTTP WebSocket route hands the connection to `tui_gateway/ws.py`, then the shared dispatcher in `tui_gateway/server.py` and its topical modules. Agent execution remains in `run_agent.py` and `agent/`.

### Plugin UI extension

Dashboard-capable plugins provide manifests and JavaScript that register pages or slot content. `web/src/plugins/usePlugins.ts` loads discovered plugins; `registry.ts` exposes the SDK and registration; `PluginPage.tsx` hosts a plugin page; `slots.ts` defines insertion points; `types.ts` and `sdk.d.ts` define the contract. `App.tsx` merges plugin tabs with the built-in navigation, including ordering/override/hidden information.

The Python side discovers manifests and serves assets in `sci_cli/web_server_dashboard.py` and `sci_cli/web_routers/dashboard_ui.py`. Plugin API mounting uses the plugin runtime and profile secret scope. Hiding a tab and disabling a plugin are different actions.

## Profiles, persistence, and authentication

### Where information lives

Let `SCI_HOME` mean the home resolved for the selected profile. The common default is `~/.sci`; named profiles commonly live below `~/.sci/profiles/<name>`. Resolve actual paths through SCI's profile system rather than assuming every page reads the default home.

| Data | Storage/owner |
| --- | --- |
| Settings and selected providers/models | Profile configuration, generally `SCI_HOME/config.yaml`. |
| Secret environment values | Profile secret storage, including `SCI_HOME/.env`; OAuth/pool storage follows the authentication subsystem. |
| Conversation messages and session metadata | Server session database via `sci_state.py` and related modules. |
| Logs | Profile-aware `SCI_HOME/logs/`, including agent/errors/gateway logs. |
| Memory, skills, plugins, cron, checkpoints | Their existing profile-owned SCI subsystems; the web app calls those services. |
| Scientific job/receipt/output state | Boltzmann plugin stores and configured output paths; not browser local storage. |
| Last browser chat | Per-profile stored session ID in browser `sessionStorage` (`sci-web-chat:<profile>`); messages remain on the server. |
| Workspace preference | Per-profile browser preference managed by `web/src/lib/chat-workspaces.ts`. |
| Theme/font/language | Browser preference storage plus supported theme/font server configuration. |
| Custom themes | `dashboard-themes/*.yaml` under the relevant SCI home, loaded by the dashboard theme backend. |

Profile-aware requests are added by `web/src/lib/api.ts`, while explicit profile parameters take precedence. Server scope helpers in `sci_cli/web_routers/_common.py` bind the target configuration and secret scope. Chat passes profile ownership through create/resume and later RPCs. Some surfaces are machine-wide or aggregate multiple profiles; file access is separately controlled by the managed-files policy.

### Access control

- **Loopback mode:** The backend injects an ephemeral session token into served HTML for protected requests. A stale page after a backend restart may need to reload its bootstrap token.
- **Gated mode:** Non-loopback/public deployments require configured dashboard authentication. The backend can use password or OAuth/OIDC provider integrations. Missing required authentication fails closed.
- **WebSocket access:** The client obtains the appropriate authentication material; gated browser connections use a single-use ticket rather than treating a legacy query token as sufficient.
- **Host and origin handling:** Server middleware validates request hosts and applies transport/auth rules. Configured reverse-proxy/base-path deployment must match those expectations.
- **File operations:** Authenticated access is still subject to managed-root, sensitive-path, size, and operation-specific checks.
- **User decisions:** Agent approvals and secure inputs are interactive protocol requests, separate from signing into the web app.

**Files:** `sci_cli/dashboard_auth/` (providers, routes, middleware, cookies, tickets, audit), `plugins/dashboard_auth/` (provider implementations), `sci_cli/web_server.py` (HTTP host/auth middleware), `web/src/lib/api.ts`, `web/src/lib/dashboard-auth-reload.ts`.

See the [dashboard deployment guide](../user-guide/features/web-dashboard.md#authentication-gated-mode) for authentication configuration examples.

## Appearance and branding

The native CLI skin and dashboard theme are different rendering systems. A change to `sci_cli/skin_defaults.py` does not automatically change React page colors.

| Visual element | Edit location |
| --- | --- |
| HTML document and favicon links | `web/index.html` |
| Global styles and design-system integration | `web/src/index.css` |
| Theme colors, density, typography presets | `web/src/themes/presets.ts`, `types.ts` |
| Theme application and persistence | `web/src/themes/context.tsx` |
| Font catalog | `web/src/themes/fonts.ts` |
| Theme/font selector | `web/src/components/ThemeSwitcher.tsx` |
| Chat-specific colors/layout/bubbles/composer | `web/src/components/chat/chat.css` |
| Intro video and skip behavior | `web/src/components/BrandEntrance.tsx`, `brand-entrance.css`, `web/src/assets/agent-scientist-intro.mp4` |
| Dotted Boltzmann logo renderer | `web/src/components/BoltzmannParticleLogo.tsx` |
| Dot formation and motion | `web/src/components/boltzmann-particles.ts`, `boltzmann-particle-motion.ts` |
| Logo glow/sizing/fallback styles | `web/src/components/boltzmann-particle-logo.css` |
| Browser icon assets | `web/public/boltzmann-favicon.svg`, `web/public/favicon.ico` |
| Structure viewer layout | `web/src/components/structure/structure-preview.css` |
| Sidebar and responsive shell | `web/src/App.tsx`, `web/src/components/SidebarFooter.tsx` |

The default dashboard preset is **Scientist Black**. Other registered presets are Sci Teal (Large), SCI Blue, Midnight, Ember, Mono, Cyberpunk, and Rosé. Theme definitions and custom themes can affect more than accent color, including typography and spacing. The current dashboard exposes a theme/font picker; do not infer that a previous CLI-only color policy removed all web appearance controls.

The particle logo is rendered locally, reacts to pointer interaction, and reforms its dotted shape. Visibility/reduced-motion handling avoids unnecessary continuous animation; no LLM or scientific job is needed to animate it.

The language catalog currently includes English, Simplified and Traditional Chinese, Japanese, German, Spanish, French, Turkish, Ukrainian, Afrikaans, Korean, Italian, Irish, Portuguese, Russian, Hungarian, and Arabic. Some newer native chat strings are authored directly in English, so the presence of a locale does not imply every new component has been translated.

## Development, builds, and verification

### Work on frontend source

Use an appropriately configured development installation and a disposable SCI home/profile when exercising mutating features. Start the backend, then Vite in another terminal:

```bash
# Repository root: serve APIs without opening the production UI
sci dashboard --no-open

# Second terminal, repository root
npm run dev --workspace web
```

Open the URL printed by Vite, usually `http://localhost:5173`. `web/vite.config.ts` proxies `/api` (including WebSockets) and `/dashboard-plugins` to `http://127.0.0.1:9119` by default. If the backend selected another port, use the existing `SCI_DASHBOARD_URL` development override:

```bash
SCI_DASHBOARD_URL=http://127.0.0.1:9120 npm run dev --workspace web
```

The Vite development bootstrap plugin forwards backend token/profile/chat bootstrap values. Missing backend access can therefore produce authentication errors even when the frontend itself loads.

### Build the dashboard

```bash
# From the repository root, with workspace dependencies prepared
npm run build --workspace web
```

This normally produces `sci_cli/web_dist/`. Open the dashboard's printed URL and reload after rebuilding. Restart the backend when its Python code/configuration requires it. Vite HMR updates the development page; it does not rewrite the production bundle merely because both servers are running.

### Existing checks and useful test files

```bash
npm run typecheck --workspace web
npm run test --workspace web
npm run lint --workspace web
# Equivalent combined frontend check:
npm run check --workspace web
```

For Python tests, use the repository's configured test interpreter and `scripts/run_tests.sh`.

| Behavior | Existing checks to start with |
| --- | --- |
| Native chat and conversation state | `web/src/pages/ChatPage.test.tsx`, `web/src/lib/web-chat-state.test.ts` |
| WebSocket/API client | `web/src/lib/gatewayClient.test.ts`, `api.test.ts`, `dashboard-auth-reload.test.ts` |
| Profile UI scope | `web/src/contexts/ProfileProvider.test.tsx`, `tests/sci_cli/test_web_multi_profile_scope.py` |
| Session display | `web/src/pages/SessionsPage.test.tsx`, `web/src/lib/session-import.test.ts` |
| Molecular viewer | `web/src/components/structure/StructurePreview.test.tsx`, `PyMOLDesktop.test.tsx`, `web/src/lib/structure-source.test.ts`, `tests/sci_cli/test_web_pymol.py` |
| Branding | `web/src/components/BoltzmannParticleLogo.test.tsx`, `boltzmann-particle-motion.test.ts` |
| Theme catalog | `web/src/themes/presets.test.ts` |
| Managed file access | `tests/sci_cli/test_web_server_fs.py` |
| Authentication | `tests/sci_cli/test_dashboard_auth_middleware.py`, `test_dashboard_auth_ws_tickets.py`, `test_dashboard_token_auth.py` |
| Build preparation | `tests/sci_cli/test_web_ui_build.py` |

These identify existing verification coverage, not a claim that every test has been run for this documentation update. This guide was checked against source routes, component behavior, manifests, and referenced paths; live provider calls, scientific submissions, installations, and destructive UI operations are outside this documentation review.

## Troubleshooting and implementation boundaries

| Symptom | Interpretation and next check |
| --- | --- |
| Frontend edit is not visible | Check whether you opened Vite or the built dashboard. Rebuild `web_dist` for production; verify the dashboard uses the intended checkout. |
| Dashboard starts on another port | The default port was occupied or an existing server was reused. Use the printed URL; explicit `--port` behaves differently. |
| UI loads but APIs return 401 | Check dashboard login/bootstrap token and development proxy target; reload after a backend restart. |
| Remote backend reports healthy but chat fails | HTTP health is not proof of an authenticated WebSocket. Check auth, proxy WebSocket support, origin/host settings, and `/api/ws`. |
| Chat disconnects during work | Reconnect to retrieve current state. Avoid manually resubmitting an uncertain scientific job just to restore the UI. |
| A service or tool is unavailable | Check the selected profile, plugin enablement, MCP state, credentials, and tool permission scope. |
| Files are outside the allowed root | The server's managed-file policy applies. A profile selector is not permission to bypass it. |
| PyMOL does not appear on the client | It opens on the server desktop. Use server display/remote desktop, or browser Mol* for in-page viewing. |
| 3D preview fails | Check supported extension, nonempty content, 20 MiB limit, file access, and browser WebGL/hardware acceleration. |
| Analytics are hidden | `dashboard.show_token_analytics` is not enabled. Their optional totals should not be used as exact billing. |
| Documentation tab misses a website article | `/docs` renders the root README; the Docusaurus website is a separate documentation surface. |
| A backend feature has no menu item | Backend APIs are shared with other clients. Check `App.tsx` and plugin manifests for actual browser UI registration. |

For a UI change, start at the relevant `web/src/pages/` component, follow its calls into `web/src/lib/api.ts` or `useWebChat.ts`, and then inspect the matching Python route/shared RPC implementation. For styling, start with the theme or component stylesheet rather than the CLI skin. For scientific execution, trace the shared agent/plugin rather than adding a second implementation to the browser.
