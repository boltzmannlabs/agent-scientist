---
sidebar_position: 1
title: "CLI Interface"
description: "Master the Sci Agent terminal interface — commands, keybindings, personalities, and more"
---

# CLI Interface

Sci Agent's CLI is a full terminal user interface (TUI) — not a web UI. It features multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output. Built for people who live in the terminal.

:::tip First-time setup
One command — `sci setup --portal` — and you're ready to `sci chat`. See [Nous Portal](../integrations/nous-portal.md).
:::

:::tip
Sci also ships a modern TUI with modal overlays, mouse selection, and non-blocking input. Launch it with `sci --tui` — see the [TUI](tui.md) guide.
:::

## Running the CLI

```bash
# Start an interactive session (default)
sci

# Single query mode (non-interactive)
sci chat -q "Hello"

# Single query from a file or stdin — nothing is shell-interpreted, so
# arbitrary text (quotes, $(...), backticks) arrives verbatim
sci chat --query-file prompt.txt
sci chat --query-file - < prompt.txt

# With a specific model
sci chat --model "anthropic/claude-sonnet-4"

# With a specific provider
sci chat --provider nous        # Use Nous Portal
sci chat --provider openrouter  # Force OpenRouter

# With specific toolsets
sci chat --toolsets "web,terminal,skills"

# Start with one or more skills preloaded
sci -s sci-agent-dev,github-auth
sci chat -s github-pr-workflow -q "open a draft PR"

# Resume previous sessions
sci --continue             # Resume the most recent CLI session (-c)
sci --resume <session_id>  # Resume a specific session by ID (-r)
sci --resume latest        # Resume the most recent session (same as -c)
sci --resume latest --in ./dir  # Resume ./dir's latest session, staying in ./dir

# Verbose mode (debug output)
sci chat --verbose

# Isolated git worktree (for running multiple agents in parallel)
sci -w                         # Interactive mode in worktree
sci -w -z "Fix issue #123"     # Single query in worktree
```

### Worktree cleanup

`sci -w` sessions create disposable worktrees under `<repo>/.worktrees/`.
A conservative pruner runs automatically at startup (it only removes clean,
fully-merged scratch trees past an age threshold), but preserved trees and
merged local branches still accumulate on busy machines. Reclaim them
explicitly:

```bash
sci worktree list              # audit: age, size, verdict, reason per tree
sci worktree list --json       # machine-readable audit (trees, external trees, branches)
sci worktree prune             # remove safe trees + delete merged branches
sci worktree prune --dry-run   # show the plan without changing anything
sci worktree prune --older-than 7   # only reap trees idle for 7+ days
sci worktree prune --trees-only     # leave local branches alone
sci worktree prune --branches-only  # leave worktrees alone
```

Worktrees registered **outside** `.worktrees/` (created by hand or by another
tool) are reported read-only in `list` output and are never removed. The one
exception is metadata: registrations whose directory no longer exists are
dropped via `git worktree prune` (no files are touched). `--older-than DAYS`
only ever narrows what gets reaped — a tree carrying real work is kept at any
age regardless of the flag.

Inside a session, `/worktree prune [--dry-run]` does the same (and never
touches the tree the session is running in).

Safety guarantees (all modes, any age):

- Uncommitted **tracked** changes are never deleted.
- **Unique unpushed commits** are never deleted — commits that were
  rebase/squash-merged upstream are detected via `git cherry`
  patch-equivalence and count as merged, which is what lets the dominant
  "merged PR, tree preserved forever" leak finally reclaim.
- **Repositories without a remote** are judged against the local trunk
  (`main`/`master`, else the branch checked out in the main worktree): only
  trees and branches whose commits are reachable from — or patch-equivalent
  to — that trunk are reclaimed. With no trunk to compare against, every tree
  and branch is preserved.
- **Pushed open-PR lanes free their disk without losing anything**: when a
  clean tree's branch head exactly matches what `origin` holds (checked with
  one `git ls-remote` per sweep), the checkout is redundant — the tree is
  removed but its **branch ref is kept**, so the lane is one
  `git worktree add .worktrees/<name> <branch>` away from restored. If the
  remote can't be reached, the tree is preserved.
- Trees **in use by a running sci session** are never touched.
- **Untracked-only scratch** (PR body drafts, notes) is archived to
  `~/.sci/archive/worktree-prune/` before its tree is removed — never
  destroyed.
- Branch deletion is content-gated, not name-gated: any local branch whose
  commits are all on upstream is safe to delete; branches with unique work,
  checked-out branches, and `main`/`master`/`develop` are always kept.

The same conservative pruner also runs from the cron scheduler (at most once
every 6 hours, in the background), so gateway-only machines — where nobody
launches `sci -w` for days — no longer accumulate merged scratch trees
between CLI sessions.

When `.worktrees/` grows past 10 trees or 5 GB, startup prints a one-line
notice pointing at these commands.

### Plugin management

The `sci plugins` commands manage native Sci plugins and portable Agent
Plugins v1 packages through the same opt-in workflow:

```bash
sci plugins install owner/repository --no-enable
sci plugins list
sci plugins enable <plugin-name>
sci plugins disable <plugin-name>
sci plugins update <plugin-name>
sci plugins remove <plugin-name>
```

Portable packages remain disabled until explicitly enabled. Sci currently
loads portable Agent Skills and stdio MCP entries. See the
[plugin developer guide](../developer-guide/plugins/index.md#portable-agent-plugins-v1-packages)
for the exact supported subset and trust boundary.

## Interface Layout

<img className="docs-terminal-figure" src="/docs/img/docs/cli-layout.svg" alt="Stylized preview of the Sci CLI layout showing the banner, conversation area, and fixed input prompt." />
<p className="docs-figure-caption">The Sci CLI banner, conversation stream, and fixed input prompt rendered as a stable docs figure instead of fragile text art.</p>

The welcome banner shows your model, terminal backend, working directory, available tools, and installed skills at a glance.

### Status Bar

A persistent status bar sits above the input area, updating in real time:

```
 ☤ claude-sonnet-4-20250514 │ 12.4K/200K │ [██████░░░░] 6% │ $0.06 │ 15m
```

| Element | Description |
|---------|-------------|
| Model name | Current model (truncated if longer than 26 chars) |
| Token count | Context tokens used / max context window; `~` marks an estimate |
| Context bar | Visual fill indicator with color-coded thresholds |
| Cost | Estimated session cost (or `n/a` for unknown/zero-priced models). Rates come from Sci' bundled official price table, then the provider's `/models` listing; on a direct first-party API (OpenAI, xAI, Anthropic, Google, DeepSeek, Xiaomi) a model missing from both is priced at the vendor's list price from models.dev. Proxies, relays and custom endpoints serving the same model id stay `n/a` rather than inherit that price. |
| 🗜️ N | **Context compression count** — how many times the running session has been auto-compressed. Appears once the first compression fires. |
| ▶ N | **Active background tasks** — how many `/bg` prompts are still running in the current session. Appears whenever at least one task is in flight. |
| Duration | Elapsed session time |
| Session title | Once the session has a title, it appears as a gold badge pinned to the far-right edge. Long titles truncate before displacing the essential model and context fields. |
| ⚠ YOLO | **YOLO mode warning** — shown whenever `SCI_YOLO_MODE` is on (either `sci --yolo` at launch or `/yolo` toggled mid-session). Mirrors the banner-line warning so you can't forget you're in auto-approve mode. |

A `~` before a context count or percentage means it includes a local estimate. This also applies to gateway `/status` and `/context`, the TUI, and the Desktop context gauge. An unchanged provider-usage reading has no `~`; a provider anchor plus unpriced new messages does. `/context` reports the selected source. Category, free-space, skill, and toolset breakdowns are always local estimates, even when the overall occupancy comes from provider usage. These display labels do not change compaction decisions or make extra provider requests.

The bar adapts to terminal width — full layout at ≥ 76 columns, compact at 52–75, minimal (model + duration, plus the YOLO badge when active) below 52.

**Context color coding:**

| Color | Threshold | Meaning |
|-------|-----------|---------|
| Green | < 50% | Plenty of room |
| Yellow | 50–80% | Getting full |
| Orange | 80–95% | Approaching limit |
| Red | ≥ 95% | Near overflow — consider `/compress` |

Use `/usage` for a detailed breakdown including per-category costs (input vs output tokens).

On the `openai-codex` provider, `/usage` also shows any banked usage-limit resets on your ChatGPT account ("You have N resets banked - use /usage reset to activate"). `/usage reset` redeems one banked reset, fully restoring your 5-hour and weekly limits. Sci refuses to redeem while your limits aren't exhausted (a banked reset restores the full allowance, so spending it early wastes it) — pass `/usage reset --force` to redeem anyway.

### Session Resume Display

`/resume` opens a searchable list with only the last-active time and conversation title, newest first. Type to filter, use ↑/↓ or PageUp/PageDown to navigate, and Enter to resume. Escape cancels without switching conversations. Session IDs and message counts are not shown in the list; direct `/resume <session-id>` still works.

Escape also cancels the active CLI wizard, model picker, command palette, or setup menu, including while a search filter is active. It never accepts an approval; Escape on an approval denies the pending action.

Attaching to a persistent CLI chat clears the terminal display and scrollback before
replaying that chat. Opening another chat replaces the displayed conversation;
saved histories remain available through `/resume`. Reattaching to a running agent
does not restart it or load code updates from disk.

When resuming a previous session (`sci -c` or `sci --resume <id>`), retained user and assistant messages appear in chronological order using the normal chat styling. Tool details remain accessible with Ctrl+O / F8 and are never rerun. This display does not expand the model’s compressed context. `/side` can open immediately after resume, using the restored conversation without requiring another main-chat message.

## Keybindings

On macOS, `F6`/`F7` mean the physical function keys, not the media/system controls shown on the top row. Hold **Fn** (the **globe** key on newer keyboards) while pressing the function key, or enable **Use F1, F2, etc. keys as standard function keys** in **System Settings → Keyboard → Keyboard Shortcuts → Function Keys**. The reliable terminal fallbacks are **Ctrl+T** for `F6` and **Ctrl+R** for `F7`.

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Alt+Enter`, `Ctrl+J`, or `Shift+Enter` | New line (multi-line input). `Shift+Enter` requires a terminal that distinguishes it from `Enter` — see below. On Windows Terminal, `Alt+Enter` is captured by the terminal (fullscreen toggle); use `Ctrl+Enter` or `Ctrl+J` instead. |
| `Alt+V` | Paste an image from the clipboard when supported by the terminal |
| `Ctrl+V` | Paste text and opportunistically attach clipboard images |
| `Ctrl+B` | Start/stop voice recording when voice mode is enabled (`voice.record_key`, default: `ctrl+b`) |
| `Ctrl+G` | Open the current input buffer in `$EDITOR` (vim/nvim/nano/VS Code/etc.). Save and quit to send the edited text as the next prompt — ideal for long, multi-paragraph prompts. |
| `Ctrl+X Ctrl+E` | Emacs-style alternate binding for the external editor (same behavior as `Ctrl+G`). |
| `Ctrl+S` | **Stash the prompt.** Parks the current draft and clears the composer so you can send something else first. Press `Ctrl+S` again on an empty composer to bring the draft back (cursor at the end, attached images restored). Repeated presses build a stack rather than overwriting, so an earlier draft is never silently lost — with two or more stashed, `Ctrl+S` opens a browse panel (`↑`/`↓` to navigate, `Enter` to restore, `D` to discard, `Esc` or `Ctrl+S` to close). A `📌 N` badge in the status bar shows how many drafts are parked. Multi-line drafts round-trip exactly, including blank lines. The stash lives in memory for the session only — nothing is written to disk, since drafts often contain secrets. |
| `Ctrl+C` | Interrupt agent (double-press within 2s to force exit) |
| `Ctrl+O` / `F8` | While idle, browse the saved conversation without losing your draft. Tab selects tool entries; Enter expands/collapses details; Ctrl+E toggles all details; `/` searches visible text; Escape returns to chat. |
| `Ctrl+T` / `F6` | Open the full-screen live work monitor (subagents and background processes) without losing the composer draft. The live dock appears automatically above the status bar; arrows select a worker or process, `Enter` shows its recent log, `s` steers a worker, and `x` requests stop with confirmation. See [Monitoring subagents](./features/delegation.md#monitoring-running-subagents-agents). |
| `Ctrl+R` / `F7` | Toggle the live work dock between its multi-row preview and a single summary line without moving composer focus. `Ctrl+R` is the reliable fallback when macOS reserves the function-key row. Besides subagents and background processes, the dock shows a standing `/goal` (active, parked or paused, with turns used) on its top row and the prompts waiting in `/queue` on its bottom rows. |
| `Ctrl+D` | Exit |
| `Ctrl+Z` | Suspend Sci to background (Unix only). Run `fg` in the shell to resume. |
| `Tab` | Accept auto-suggestion (ghost text) or autocomplete slash commands |
| `!<command>` | **Shell mode** — run a shell command yourself without spending a model turn (e.g. `!git status`, `!pytest -x`). See below. |

**Multiline paste preview.** When you paste a multi-line block, the CLI echoes a compact single-line preview (`[pasted: 47 lines, 1,842 chars — press Enter to send]`) instead of dumping the whole payload into the scrollback. The full content is still what gets sent; this is just display polish.

### `!` Shell Mode

Start a line with `!` to run it as a shell command instead of sending it to the agent:

```
> !git status
> !ls -la
> !pytest -x tests/sci_cli
```

- **Zero cost.** The model is never invoked — no API call, no tokens, no latency.
- **Nothing enters the conversation.** The command and its output are not added to history, so your context stays clean and the prompt cache is untouched.
- **Runs on your machine, in the session working directory.** With the default local terminal backend `!pwd` matches what the agent would see. A remote or sandboxed `terminal.backend` (`ssh`, `docker`, …) is **not** used for `!` commands — they always run on the host where Sci itself runs, so `!hostname` names your machine while the agent's `terminal` tool names the backend. Ask the agent (or open a shell on the target) to run something *inside* the backend. Path completion in the composer, by contrast, does follow the configured backend and lists the target's filesystem.
- **Approvals still apply.** A dangerous command (`rm -rf`, writes to `~/.sci/config.yaml`, etc.) goes through the same approval prompt the agent's `terminal` tool uses. `!` is a cost/latency shortcut, not a security bypass.
- **Non-zero exits are shown.** A failing command prints `! exited <code>` after its output.
- `!` on its own prints a one-line usage reminder.

Shell mode is CLI-only. Gateway platforms (Discord, Telegram, Slack) and cron runs ignore it — those users already have their own shells.

**Markdown stripping in final responses.** The CLI strips the most verbose markdown fences and `**bold**` / `*italic*` wrappers from *final* agent replies so they render as readable terminal prose rather than raw source. Code blocks and lists are preserved. This does not affect gateway platforms or tool results — they keep their markdown for native rendering.

## Slash Commands

Type `/` to see the autocomplete dropdown. Sci supports a large set of CLI slash commands, dynamic skill commands, and user-defined quick commands.

Common examples:

| Command | Description |
|---------|-------------|
| `/help` | Show command help |
| `/model` | Show or change the current model |
| `/tools` | List currently available tools |
| `/skills browse` | Browse the skills hub and official optional skills |
| `/bg <prompt>` | Run a prompt in a separate background session |
| `/background [status\|attach ID\|stop ID]` | Opt into or manage persistent classic CLI chats |
| `/detach` | Disconnect the viewer of a persistent chat; keep its worker running |
| `/skin` | Show or switch the active CLI skin |
| `/voice on` | Enable CLI voice mode (press `Ctrl+B` to record) |
| `/voice tts` | Toggle spoken playback for Sci replies |
| `/reasoning high` | Increase reasoning effort |
| `/title My Session` | Name the current session |
| `/rename [name]` | Rename the conversation; omit the name to open a prompt (classic CLI) |
| `/side [question]` | Open a temporary, multi-turn discussion using the parent conversation's context (classic CLI) |
| `/status` | Show session info — model/profile/tokens/duration — followed by a local **Session recap** block (recent turn counts, top tools used, files touched, latest user prompt + assistant reply). Pure local compute; no LLM call. |
| `/context [all]` | Visual context-usage breakdown — glyph block grid + per-category token table (system prompt / tools / skills / memory / conversation / free space). `/context all` adds per-skill and per-toolset costs. |
| `/sessions` | Open an interactive session picker right inside the classic CLI (same surface the TUI uses). Type to filter, arrow keys to navigate, Enter to resume. |

For the full built-in CLI and messaging lists, see [Slash Commands Reference](../reference/slash-commands.md).

For setup, providers, silence tuning, and messaging/Discord voice usage, see [Voice Mode](features/voice-mode.md).

:::tip
Commands are case-insensitive — `/HELP` works the same as `/help`. Installed skills also become slash commands automatically.
:::

## Quick Commands

You can define custom commands that run shell commands instantly without invoking the LLM. These work in both the CLI and messaging platforms (Telegram, Discord, etc.).

```yaml
# ~/.sci/config.yaml
quick_commands:
  status:
    type: exec
    command: systemctl status sci-agent
  gpu:
    type: exec
    command: nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
  restart:
    type: alias
    target: /gateway restart
```

Then type `/status`, `/gpu`, or `/restart` in any chat. See the [Configuration guide](./configuration.md#quick-commands) for more examples.

## Preloading Skills at Launch

If you already know which skills you want active for the session, pass them at launch time:

```bash
sci -s sci-agent-dev,github-auth
sci chat -s github-pr-workflow -s github-auth
```

Sci loads each named skill into the session prompt before the first turn. The same flag works in interactive mode and single-query mode.

### Persistent auto-load via config

To have the same skills active at the start of **every** new session — CLI, TUI, gateway, cron and API sessions alike — set `skills.auto_load` in `config.yaml`:

```yaml
skills:
  auto_load:
    - sci-agent-dev
    - github-pr-workflow
```

Each entry is a skill name. The list is resolved once when a session's system prompt is first built and the rendered bytes are reused for the life of the conversation (model switches, compression), so prompt caching stays intact; config edits take effect in the next session. Missing or disabled skills log a warning and are skipped. `-s` names that overlap the list are loaded once.

`--ignore-rules` (equivalently `SCI_IGNORE_RULES=1`) skips auto-load together with AGENTS.md, SOUL.md, `.cursorrules` and memory injection; explicit `-s` skills still load. The setting is profile-scoped: each profile's `config.yaml` controls its own list.

## Skill Slash Commands

Every installed skill in `~/.sci/skills/` is automatically registered as a slash command. The skill name becomes the command:

```
/gif-search funny cats
/axolotl help me fine-tune Llama 3 on my dataset
/github-pr-workflow create a PR for the auth refactor

# Just the skill name loads it and lets the agent ask what you need:
/excalidraw
```

## Personalities

Set a predefined personality to change the agent's tone:

```
/personality pirate
/personality kawaii
/personality concise
```

Built-in personalities include: `helpful`, `concise`, `technical`, `creative`, `teacher`, `kawaii`, `catgirl`, `pirate`, `shakespeare`, `surfer`, `noir`, `uwu`, `philosopher`, `hype`.

To go back to the default (no overlay), use `/personality none` — `default` and `neutral` work too.

You can also define custom personalities in `~/.sci/config.yaml`:

```yaml
personalities:
  helpful: "You are a helpful, friendly AI assistant."
  kawaii: "You are a kawaii assistant! Use cute expressions..."
  pirate: "Arrr! Ye be talkin' to Captain Sci..."
  # Add your own!
```

## Multi-line Input

There are two ways to enter multi-line messages:

1. **`Alt+Enter`, `Ctrl+J`, or `Shift+Enter`** — inserts a new line
2. **Backslash continuation** — end a line with `\` to continue:

```
❯ Write a function that:\
  1. Takes a list of numbers\
  2. Returns the sum
```

`Ctrl+J` and backslash continuation are enabled by default, matching Claude Code / Codex / OpenCode multiline shortcuts. On supported terminals such as iTerm2, Sci also requests extended key reporting so `Shift+Enter` arrives as a distinct newline key. If your terminal sends LF for plain `Enter` and you need the legacy `Ctrl+J`-as-submit fallback, opt out:

```yaml
# ~/.sci/config.yaml
display:
  cli_multiline_shortcuts: false
```

:::info
Pasting multi-line text is supported — use any of the newline keys above, or simply paste content directly.

In terminals using the Kitty keyboard protocol, `Alt+Enter` on the numeric keypad also inserts a newline, including next to a collapsed paste. Modified keypad navigation keys follow their non-keypad equivalents.
:::

### Shift+Enter compatibility

Most terminals send the same byte sequence for `Enter` and `Shift+Enter` by default, so applications cannot distinguish them. Sci recognises `Shift+Enter` only when the terminal sends a distinct sequence via the [Kitty keyboard protocol](https://sw.kovidgoyal.net/kitty/keyboard-protocol/) or xterm's `modifyOtherKeys` mode.

| Terminal | Status |
|---|---|
| Kitty, foot, WezTerm, Ghostty | Distinct `Shift+Enter` enabled by default |
| iTerm2 (recent), Alacritty, VS Code terminal, Warp | Supported once the Kitty protocol is enabled in settings |
| Windows Terminal Preview 1.25+ | Supported once the Kitty protocol is enabled in settings |
| macOS Terminal.app, stock Windows Terminal (stable) | Not supported — `Shift+Enter` is indistinguishable from `Enter` |

Where the terminal cannot distinguish them, `Alt+Enter` and `Ctrl+J` continue to work by default. **On Windows Terminal specifically, `Alt+Enter` is captured by the terminal (toggles fullscreen) and never reaches Sci — use `Ctrl+Enter` (delivered as `Ctrl+J`) or `Ctrl+J` directly for a newline.**

## Redirecting the Agent Mid-Turn

While the agent is working, you can send a correction without starting a new turn:

- **Type a new message + Enter** — redirects the active turn using your correction
- **`Ctrl+C`** — interrupt the current operation (press twice within 2s to force exit)
- Completed tool work and reasoning already shown stay in context
- A running tool reaches its safe boundary before the correction is applied

### Busy Input Mode

The `display.busy_input_mode` config key controls what happens when you press Enter while the agent is working:

| Mode | Behavior |
|------|----------|
| `"interrupt"` (default) | Your message redirects the active turn. Model generation restarts with displayed reasoning and completed work preserved. A running foreground terminal command is moved to the background (not killed — you get a completion notification) so your message is read immediately; other running tools finish first |
| `"queue"` | Your message is silently queued and sent as the next turn after the agent finishes |
| `"steer"` | Your message is injected into the current run via `/steer`, arriving at the agent after the next tool call — no interrupt, no new turn |

```yaml
# ~/.sci/config.yaml
display:
  busy_input_mode: "steer"   # or "queue" or "interrupt" (default)
```

`"queue"` mode prepares a separate follow-up turn. `"steer"` always waits for the next tool-result boundary. The default `"interrupt"` mode responds sooner during model generation while avoiding cancellation of a running tool; a long foreground `terminal` command (a build, a poller) is handed to the background so the agent sees your message right away instead of after the command exits. Use `/stop` when you want to cancel the turn and its foreground work. Unknown values fall back to `"interrupt"`.

`"steer"` has two automatic fallbacks: if the agent hasn't started yet, or if images are attached, the message falls back to `"queue"` behavior so nothing is lost.

Whatever the mode, `/queue <prompt>` queues a follow-up turn explicitly, and `/queue list`, `/queue rm N`, `/queue edit N …` and `/queue move A B` act on the pending queue immediately, even mid-run. The live work dock lists what is waiting.

You can also change it inside the CLI:

```text
/busy queue
/busy steer
/busy interrupt
/busy status
```

:::tip First-touch hint
The first time you press Enter while Sci is working, Sci prints a one-line reminder explaining the `/busy` knob. It only fires once per install; `onboarding.seen.busy_input_prompt` in `config.yaml` records that it was shown. Delete that key to see the tip again.
:::

### Background tasks and terminal suspension

The classic CLI on Linux/macOS/WSL starts its background service automatically.
Press **Ctrl+C** during a task with an empty composer and choose **Cancel task**,
**Run in background**, or **Exit**. Reconnect with `sci --resume SESSION_ID` or the
normal `/resume` picker. `/background`, `/detach`, `/exit`, and closing the terminal
leave the task running. Use `sci background status` to inspect actual task states.

**Ctrl+Z** suspends the terminal viewer; `fg` returns to it. The worker continues
independently. With explicit `sci --no-daemon`, Ctrl+Z instead suspends the entire
foreground process. See [background execution and reconnecting](./sessions.md#background-execution-and-reconnecting)
for stopping, idle cleanup, profile scope and platform limitations.

## Tool Progress Display

The CLI shows animated feedback as the agent works:

**Thinking animation** (during API calls):
```
  ◜ (｡•́︿•̀｡) pondering... (1.2s)
  ◠ (⊙_⊙) contemplating... (2.4s)
  ✧٩(ˊᗜˋ*)و✧ got it! (3.1s)
```

**Tool execution feed:**
```
  ┊ 💻 terminal `ls -la` (0.3s)
  ┊ 🔍 web_search (1.2s)
  ┊ 📄 web_extract (2.1s)
```

Cycle through display modes with `/verbose`: `off → new → all → verbose`. This command can also be enabled for messaging platforms — see [configuration](./configuration.md#display-settings).

### Tool Preview Length

The `display.tool_preview_length` config key controls the maximum number of characters shown in tool call preview lines (e.g. file paths, terminal commands). The default is `0`, which means no limit — full paths and commands are shown.

```yaml
# ~/.sci/config.yaml
display:
  tool_preview_length: 80   # Truncate tool previews to 80 chars (0 = no limit)
```

This is useful on narrow terminals or when tool arguments contain very long file paths.

## Session Management

### Resuming Sessions

When you exit a CLI session, a resume command is printed:

```
Resume this session with:
  sci --resume 20260225_143052_a1b2c3

Session:        20260225_143052_a1b2c3
Duration:       12m 34s
Messages:       28 (5 user, 18 tool calls)
```

Resume options:

```bash
sci --continue                          # Resume the most recent CLI session
sci -c                                  # Short form
sci -c "my project"                     # Resume a named session (latest in lineage)
sci --resume 20260225_143052_a1b2c3     # Resume a specific session by ID
sci --resume "refactoring auth"         # Resume by title
sci --resume latest                     # Resume the most recent session (same as -c)
sci --resume latest --in ./my-project   # Latest session for ./my-project's workspace
sci -r 20260225_143052_a1b2c3           # Short form
```

Resuming restores the full conversation history from SQLite. The agent sees all previous messages, tool calls, and responses — just as if you never left.

Use `/title My Session Name` inside a chat to name the current session, or `sci sessions rename <id> <title>` from the command line. Use `sci sessions list` to browse past sessions.

### Session Storage

CLI sessions are stored in Sci's SQLite state database under `~/.sci/state.db`. The database keeps:

- session metadata (ID, title, timestamps, token counters)
- message history
- lineage across compressed/resumed sessions
- full-text search indexes used by `session_search`

Some messaging adapters also keep per-platform transcript files alongside the database, but the CLI itself resumes from the SQLite session store.

### Context Compression

Long conversations are automatically summarized when approaching context limits:

```yaml
# In ~/.sci/config.yaml
compression:
  enabled: true
  threshold: 0.50    # Compress at 50% of context limit by default

# Summarization model configured under auxiliary:
auxiliary:
  compression:
    model: ""  # Leave empty to use the main chat model (default). Or pin a cheap fast model, e.g. "google/gemini-3-flash-preview".
```

When compression triggers, middle turns are summarized while the first 3 and last 20 turns are always preserved.

## Temporary side conversations

In the classic CLI, `/side` opens a temporary discussion, including while the parent is
working. `/side Why did we choose this method?` opens it and asks the first question.
Ordinary follow-up messages then go to the side discussion. The status bar labels the
side view and shows whether the parent is running, idle, or waiting for input.
The side transcript uses a separate terminal screen. Main replies arriving while you
are there are shown in main when you return; they do not appear in the side transcript.
Each chat keeps its own draft and input history. Page Up/Page Down scroll the side
transcript without moving the composer; its reading position survives switching.
The mouse wheel or trackpad scrolls the side transcript even over the input area.
Wrapped messages scroll by screen rows. Use the draggable scrollbar at the right,
or Ctrl+Home/Ctrl+End to jump to the beginning/latest output. New output does not
pull you away while reading earlier messages; return to the bottom to follow it again.
Mouse capture is limited to side mode; main retains normal terminal scrollback.
Tool polling, download notices, and Python stdout/stderr stay in the originating side
chat even while main is visible. Closing side discards its later display output;
it does not undo completed external actions.

- Ctrl+/: switch between main and the existing side conversation without cancelling either.
  Terminals sending Ctrl+_ for this key are supported too.
- `/side`: open or reopen the temporary conversation; optional text asks a question.
- Ctrl+C: close side and return to main, even with an unfinished draft. Requests cancellation
  of side work without cancelling main. There are no back, close, or status subcommands.

Side conversations inherit the entire available context through the parent's last completed
assistant message, including earlier turns (and existing compression summaries);
unfinished turns and later parent activity are not included. The same selected model answers
follow-ups without changing the parent's history, tools, or cached prompt. No provider
fallback is made. Replies, tool activity, attachments, and approval prompts use the normal
chat interface. Available tools and skills follow the active profile's permissions. Inherited
requests and approvals are reference material: external actions require a request in side.
Only the conversations are separated; files, credentials, and services are shared, so changes
made with tools have real effects. Closing cannot undo completed actions or remote jobs.
Closing returns immediately; opening another side waits for its cancelled worker to finish.
Side conversations are not saved for `/resume`; provider processing and ordinary diagnostic
logging still follow the application's existing settings. `/btw` has been removed.

`/rename "Literature review"` saves a name for the active parent conversation. `/rename`
opens the naming prompt when idle; use an inline name while work is running. Names are
profile-scoped and survive restart/resume. Renaming does not rename the profile or change
conversation content. `/title` remains available. Return from side mode before renaming.

The side UI is currently available in the classic terminal (`sci chat --cli`), not the
Ink TUI, desktop chat, or messaging integrations. Existing `/bg` and persistent
`/background` chats remain separate features.

## Background Sessions

Run a prompt in a separate background session while continuing to use the CLI for other work:

```
/bg Analyze the logs in /var/log and summarize any errors from today
```

Sci immediately confirms the task and gives you back the prompt:

```
🔄 Background task #1 started: "Analyze the logs in /var/log and summarize..."
   Task ID: bg_143022_a1b2c3
```

### How It Works

Each `/bg` prompt spawns a **completely separate agent session** in a daemon thread:

- **Isolated conversation** — the background agent has no knowledge of your current session's history. It receives only the prompt you provide.
- **Same configuration** — the background agent inherits your model, provider, toolsets, reasoning settings, and fallback model from the current session.
- **Non-blocking** — your foreground session stays fully interactive. You can chat, run commands, or even start more background tasks.
- **Multiple tasks** — you can run several background tasks simultaneously. Each gets a numbered ID.

`/bg` runs inside the conversation's worker process. In the default persistent
classic CLI, disconnecting the terminal leaves that worker and its `/bg` tasks
running; `/agents` shows the tasks. With explicit `--no-daemon` foreground mode,
keep the CLI open until they finish. See [background execution and reconnecting](./sessions.md#background-execution-and-reconnecting).
Remote scientific jobs already submitted to a service may
continue independently: retain their job IDs and check status before submitting
another job.

### Results

When a background task finishes, the result appears as a panel in your terminal:

```
╭─ ☤ Sci (background #1) ──────────────────────────────────╮
│ Found 3 errors in syslog from today:                         │
│ 1. OOM killer invoked at 03:22 — killed process nginx        │
│ 2. Disk I/O error on /dev/sda1 at 07:15                      │
│ 3. Failed SSH login attempts from 192.168.1.50 at 14:30      │
╰──────────────────────────────────────────────────────────────╯
```

If the task fails, you'll see an error notification instead. If `display.bell_on_complete` is enabled in your config, the terminal bell rings when the task finishes.

### Use Cases

- **Long-running research** — "/bg research the latest developments in quantum error correction" while you work on code
- **File processing** — "/bg analyze all Python files in this repo and list any security issues" while you continue a conversation
- **Parallel investigations** — start multiple background tasks to explore different angles simultaneously

:::info
Background sessions do not appear in your main conversation history. They are standalone sessions with their own task ID (e.g., `bg_143022_a1b2c3`).
:::

## Quiet Mode

By default, the CLI runs in quiet mode which:
- Suppresses verbose logging from tools
- Enables kawaii-style animated feedback
- Keeps output clean and user-friendly

For debug output:
```bash
sci chat --verbose
```
