---
sidebar_position: 10
title: "Skins & Themes"
description: "Customize the Sci CLI with built-in and user-defined skins"
---

# Skins & Themes

Skins control the **visual presentation** of the Sci CLI: banner colors, spinner faces and verbs, response-box labels, branding text, and the tool activity prefix.

Conversational style and visual style are separate concepts:

- **Personality** changes the agent's tone and wording.
- **Skin** changes the CLI's appearance.

## Change skins

```bash
/skin                # show the current skin and list available skins
/skin ares           # switch to a built-in skin
/skin mytheme        # switch to a custom skin from ~/.sci/skins/mytheme.yaml
```

Or set the default skin in `~/.sci/config.yaml`:

```yaml
display:
  skin: neon-theme
```

The native CLI and TUI use the dark burgundy palette exclusively. Terminal
appearance hints and legacy light-mode settings are ignored. `/skin` can change
the accent palette while keeping the interface dark.

Both `agent-sci` and `agent-sci --tui` use a black canvas with rose controls,
the Agent Scientist title artwork, and a welcome card with the Boltzmann logo
on the left and profile details on the right. Narrow windows use a compact card.
The welcome heading reads `Agent Scientist` without a leading icon.

The classic CLI defaults to compact spacing, with rounded welcome/status tables
and tighter question pickers. The logo and existing color palette are preserved.
Set `display.compact: false` in `config.yaml` to use roomier spacing; an explicitly
saved preference takes precedence over the default. This setting does not change
the web, desktop, or React TUI layout.

On a fresh interactive welcome screen, the dotted Boltzmann logo slowly rotates
in three dimensions. The profile details stay still. Typing stops the animation
face-on; submitting input leaves one static card in scrollback. Resumed chats,
small classic terminals (under 70 columns or 28 rows), redirected output and
custom artwork remain static. Frames are display-only and never enter chat
history, exports or model context. The classic CLI and React TUI share the same
frames; regenerate them after artwork changes with `python -m sci_cli.logo_animation`.
VS Code receives native terminal progress signals (`OSC 9;4`) while SCI works,
so its tab list can show the built-in animated indicator. Progress clears when
SCI waits for input, becomes idle, or exits. On other terminals, title updates
use moving dots during work, a still dot when idle, and `?` when input is needed.
VS Code needs the progress field in its tab-title template. Its default
`${process}` template hides both application titles and progress, even when SCI
emits the correct signals. Set these in VS Code User Settings (or Remote
Settings for SSH/remote terminals):

```json
{
  "terminal.integrated.tabs.title": "${progress} ${sequence}",
  "terminal.integrated.tabs.enableAnimation": true
}
```

Workspace settings override user/remote settings, so check the active
workspace if the title still shows `python`. A manually renamed terminal also
overrides the template; reset its name or create a new terminal. No SCI restart
is needed for a tab-template change;
SCI must already be running a version that emits native progress. Codex and a
few other CLIs receive special title handling from VS Code; SCI uses the
standard configurable template.
The footer reads `agent-sci`. User messages have a clear label, answers use
horizontal borders, and the status bar sits below the composer. The card
shows the actual selected model, workspace and capability counts; use
`/capabilities` for the inventory. Custom skins with artwork retain their banners.

Pickers, masked-key entry, approvals and login confirmations use the same palette.
Picker options have no visible numeric prefixes. `/activate` uses radio-style
choices with full-row highlighting. Plain-text fallbacks accept option labels. Skill and tool
selection shows checked items alongside the existing Select all, Clear selection
and Done controls. Arrow keys navigate, Enter selects, and Escape cancels;
long lists scroll within the terminal height.
The Boltzmann account card highlights the verified email, credits and frozen
credits. Secret entry stays masked and setup changes still apply at the existing
conversation boundary.

The model picker uses compact, highlighted choice rows instead of padding short
catalogs with empty entries. Login prompts distinguish the platform link, field
label, and masked input. Account confirmation has its own green surface; balances
are service-reported values. Resume lists show conversation title and last activity, hiding the activity
column on narrow terminals. Selected rows,
approval commands, queued messages, and specialist activity share the dark
palette. These are native terminal adaptations of the approved HTML
design; browser fonts, shadows, and pixel spacing depend on the terminal.

On interactive terminals that support OSC 10/11, SCI sets the default foreground
and background so unused screen space is black too, then restores the terminal's
configured defaults on normal exit. Terminals that reject these color controls retain
their own canvas; set that terminal profile's background to black. Redirected
classic-CLI output does not receive these controls.

The React TUI also remains dark-only. `/statusbar top` and `/statusbar bottom`
change status-bar placement. Appearance changes do not alter model context,
permissions, authentication, tools, or saved conversation contents.

Browser shadows, blur, fractional font sizes and window controls are not terminal
features; the terminal application still controls the font. Use a true-color
terminal and a monospace font for the closest match. The HTML design is a
reference, not a separate interface or runtime dependency.

## Built-in skins

| Skin | Description | Agent branding | Visual character |
|------|-------------|----------------|------------------|
| `neon-theme` | Default SCI pink/magenta palette | `Sci Agent` | Pink headings, magenta response borders, pale-pink text and velvet-black status surfaces. Automatically available on fresh installations. |
| `ares` | War-god theme — crimson and bronze | `Ares Agent` | Deep crimson borders with bronze accents. Aggressive spinner verbs ("forging", "marching", "tempering steel"). Custom sword-and-shield ASCII art banner. |
| `mono` | Monochrome — clean grayscale | `Sci Agent` | All grays — no color. Borders are `#555555`, text is `#c9d1d9`. Ideal for minimal terminal setups or screen recordings. |
| `slate` | Cool blue — developer-focused | `Sci Agent` | Royal blue borders (`#4169e1`), soft blue text. Calm and professional. No custom spinner — uses default faces. |
| `poseidon` | Ocean-god theme — deep blue and seafoam | `Poseidon Agent` | Deep blue to seafoam gradient. Ocean-themed spinners ("charting currents", "sounding the depth"). Trident ASCII art banner. |
| `sisyphus` | Sisyphean theme — austere grayscale with persistence | `Sisyphus Agent` | Light grays with stark contrast. Boulder-themed spinners ("pushing uphill", "resetting the boulder", "enduring the loop"). Boulder-and-hill ASCII art banner. |
| `charizard` | Volcanic theme — burnt orange and ember | `Charizard Agent` | Warm burnt orange to ember gradient. Fire-themed spinners ("banking into the draft", "measuring burn"). Dragon-silhouette ASCII art banner. |

## Complete list of configurable keys

The classic gold default is no longer shipped. Older `display.skin: default`
settings resolve to `neon-theme`; existing custom skin files and explicit choices
are not overwritten. No local skin file is needed for the release theme.

### Colors (`colors:`)

Controls all color values throughout the CLI. Values are hex color strings.

| Key | Description | Default (`neon-theme` skin) |
|-----|-------------|--------------------------|
| `banner_border` | Panel border around the startup banner | `#8D123B` |
| `banner_title` | Title text color in the banner | `#FF7AA7` |
| `banner_accent` | Section headers in the banner (Available Tools, etc.) | `#FF356F` |
| `banner_dim` | Muted text in the banner (separators, secondary labels) | `#AF426B` |
| `banner_text` | Body text in the banner (tool names, skill names) | `#FFE3ED` |
| `ui_accent` | General UI accent color (highlights, active elements) | `#FF3F79` |
| `ui_label` | UI labels and tags | `#E965AF` |
| `ui_ok` | Success indicators (design's readable success ink) | `#7CE38B` |
| `ui_error` | Error indicators (design's readable error ink) | `#FF5C77` |
| `ui_warn` | Warning indicators (caution, approval prompts) | `#FFB17D` |
| `prompt` | Prompt text fallback; the layered composer uses `ui_accent` for its symbol | `#FFE8F0` |
| `input_rule` | Horizontal rule above the input area | `#F52566` |
| `response_border` | Border around the agent's response box (ANSI escape) | `#B93586` |
| `session_label` | Session label color | `#FF8FB6` |
| `session_border` | Session ID dim border color | `#853053` |
| `status_bar_bg` | Background color for the TUI status / usage bar | `#160811` |
| `voice_status_bg` | Background color for the voice-mode status badge | `#250D20` |
| `selection_bg` | Background color for the TUI mouse-selection highlighter. Falls back to `completion_menu_current_bg` when unset. | `#753052` |
| `completion_menu_bg` | Background color for the completion menu list | `#170914` |
| `completion_menu_current_bg` | Background color for the active completion row | `#5E173C` |
| `completion_menu_meta_bg` | Background color for the completion meta column | `#250D20` |
| `completion_menu_meta_current_bg` | Background color for the active completion meta column | `#782049` |

### Spinner (`spinner:`)

Controls the animated spinner shown while waiting for API responses.

| Key | Type | Description | Example |
|-----|------|-------------|---------|
| `waiting_faces` | list of strings | Faces cycled while waiting for API response | `["(⚔)", "(⛨)", "(▲)"]` |
| `thinking_faces` | list of strings | Faces cycled during model reasoning | `["(⚔)", "(⌁)", "(<>)"]` |
| `thinking_verbs` | list of strings | Verbs shown in spinner messages | `["forging", "plotting", "hammering plans"]` |
| `wings` | list of [left, right] pairs | Decorative brackets around the spinner | `[["⟪⚔", "⚔⟫"], ["⟪▲", "▲⟫"]]` |

When spinner values are empty (like in `neon-theme` and `mono`), hardcoded defaults from `display.py` are used.

### Branding (`branding:`)

Text strings used throughout the CLI interface.

| Key | Description | Default |
|-----|-------------|---------|
| `agent_name` | Name shown in banner title and status display | `Sci Agent` |
| `welcome` | Welcome message shown at CLI startup | `Welcome to Sci Agent! Type your message or /help for commands.` |
| `goodbye` | Message shown on exit | `Goodbye! ☤` |
| `response_label` | Label on the response box header | ` ☤ Sci ` |
| `prompt_symbol` | Symbol before the user input prompt (bare token, renderers add a trailing space) | `❯` |
| `help_header` | Header text for the `/help` command output | `(^_^)? Available Commands` |

### Other top-level keys

| Key | Type | Description | Default |
|-----|------|-------------|---------|
| `tool_prefix` | string | Character prefixed to tool output lines in the CLI | `┊` |
| `tool_emojis` | dict | Per-tool emoji overrides for spinners and progress (`{tool_name: emoji}`) | `{}` |
| `banner_logo` | string | Rich-markup ASCII art logo (replaces the default SCI_AGENT banner) | `""` |
| `banner_hero` | string | Rich-markup hero art (replaces the default caduceus art) | `""` |
| `customCSS` | string | Raw CSS injected into the desktop app and web dashboard while the skin is active (GUI surfaces only; ignored by the CLI/TUI). Capped at 32 KiB. | `""` |

### Optional native surfaces

These dark color roles are opt-in for custom skins. Omitting them preserves the
terminal's existing background rather than inheriting the default's black canvas.
Authored `dark_colors` overlays apply to native CLI colors and the React TUI.

| Key | Purpose | Default |
|-----|---------|----------------------|
| `background` | Full terminal canvas (OSC 11) | `#000000` |
| `terminal_bg` | Answer-panel canvas | `#000000` |
| `terminal_elevated` | Composer and banner surface | `#11080F` |
| `panel_bg` | Burgundy fill inside picker and approval boxes | `#260D1A` |
| `account_bg` | Verified-account card surface | `#0D1E12` |
| `account_border` | Verified-account card outline | `#40784A` |
| `hint_text` | Placeholder and helper text | `#A2788D` |
| `choice_text` | Unselected dialog options | `#D7B4C5` |
| `meter_foreground` | Context-meter accent | `#FF3F79` |
| `meter_background` | Context-meter surface | `#1E0B16` |

## Custom skins

Create YAML files under `~/.sci/skins/`. User skins inherit missing palette values
from `neon-theme`, except the optional surface roles above, so you only need to
specify the keys you want to change.

### Full custom skin YAML template

```yaml
# ~/.sci/skins/mytheme.yaml
# Complete skin template — all keys shown. Delete any you don't need;
# missing values automatically inherit from the 'neon-theme' skin.

name: mytheme
description: My custom theme

colors:
  banner_border: "#8D123B"
  banner_title: "#FF7AA7"
  banner_accent: "#FF356F"
  banner_dim: "#AF426B"
  banner_text: "#FFE3ED"
  ui_accent: "#FF3F79"
  ui_label: "#E965AF"
  ui_ok: "#D1F2CD"
  ui_error: "#FF385A"
  ui_warn: "#FFB17D"
  prompt: "#FFE8F0"
  input_rule: "#F52566"
  response_border: "#B93586"
  session_label: "#FF8FB6"
  session_border: "#853053"
  status_bar_bg: "#160811"
  voice_status_bg: "#250D20"
  selection_bg: "#753052"
  completion_menu_bg: "#170914"
  completion_menu_current_bg: "#5E173C"
  completion_menu_meta_bg: "#250D20"
  completion_menu_meta_current_bg: "#782049"

spinner:
  waiting_faces:
    - "(⚔)"
    - "(⛨)"
    - "(▲)"
  thinking_faces:
    - "(⚔)"
    - "(⌁)"
    - "(<>)"
  thinking_verbs:
    - "processing"
    - "analyzing"
    - "computing"
    - "evaluating"
  wings:
    - ["⟪⚡", "⚡⟫"]
    - ["⟪●", "●⟫"]

branding:
  agent_name: "My Agent"
  welcome: "Welcome to My Agent! Type your message or /help for commands."
  goodbye: "See you later! ⚡"
  response_label: " ⚡ My Agent "
  prompt_symbol: "⚡"
  help_header: "(⚡) Available Commands"

tool_prefix: "┊"

# Per-tool emoji overrides (optional)
tool_emojis:
  terminal: "⚔"
  web_search: "🔮"
  read_file: "📄"

# Custom ASCII art banners (optional, Rich markup supported)
# banner_logo: |
#   [bold #FFD700] MY AGENT [/]
# banner_hero: |
#   [#FFD700]  Custom art here  [/]
```

### Minimal custom skin example

Since everything inherits from `neon-theme`, a minimal skin only needs to change what's different:

```yaml
name: cyberpunk
description: Neon terminal theme

colors:
  banner_border: "#FF00FF"
  banner_title: "#00FFFF"
  banner_accent: "#FF1493"

spinner:
  thinking_verbs: ["jacking in", "decrypting", "uploading"]
  wings:
    - ["⟨⚡", "⚡⟩"]

branding:
  agent_name: "Cyber Agent"
  response_label: " ⚡ Cyber "

tool_prefix: "▏"
```

### Raw `customCSS`

For selector-level styling that colors can't express — font sizes, spacing, pseudo-elements, animations — drop raw CSS into `customCSS`. The desktop app and web dashboard inject it as a `<style>` tag while the skin is active and remove it when you switch to a skin without it.

```yaml
name: myskin

colors:
  background: "#1a1030"
  ui_accent: "#ff5fd2"

customCSS: |
  .chat-input { font-size: 16px; }
  .status-bar { background: rgba(0, 0, 0, 0.5); }
```

The field is capped at 32 KiB and applies to GUI surfaces only — the CLI and TUI ignore it. Because it lives in your skin YAML under `~/.sci/skins/`, it survives app updates (no more hacking `app.asar`).

## Sci Mod — Visual Skin Editor

[Sci Mod](https://github.com/cocktailpeanut/hermes-mod) is a community-built web UI for creating and managing skins visually. Instead of writing YAML by hand, you get a point-and-click editor with live preview.

![Sci Mod skin editor](https://raw.githubusercontent.com/cocktailpeanut/hermes-mod/master/nous.png)

**What it does:**

- Lists all built-in and custom skins
- Opens any skin into a visual editor with all Sci skin fields (colors, spinner, branding, tool prefix, tool emojis)
- Generates `banner_logo` text art from a text prompt
- Converts uploaded images (PNG, JPG, GIF, WEBP) into `banner_hero` ASCII art with multiple render styles (braille, ASCII ramp, blocks, dots)
- Saves directly to `~/.sci/skins/`
- Activates a skin by updating `~/.sci/config.yaml`
- Shows the generated YAML and a live preview

### Install

**Option 1 — Pinokio (1-click):**

Find it on [pinokio.computer](https://pinokio.computer) and install with one click.

**Option 2 — npx (quickest from terminal):**

```bash
npx -y sci-mod
```

**Option 3 — Manual:**

```bash
git clone https://github.com/cocktailpeanut/hermes-mod.git
cd sci-mod/app
npm install
npm start
```

### Usage

1. Start the app (via Pinokio or terminal).
2. Open **Skin Studio**.
3. Choose a built-in or custom skin to edit.
4. Generate a logo from text and/or upload an image for hero art. Pick a render style and width.
5. Edit colors, spinner, branding, and other fields.
6. Click **Save** to write the skin YAML to `~/.sci/skins/`.
7. Click **Activate** to set it as the current skin (updates `display.skin` in `config.yaml`).

Sci Mod respects the `SCI_HOME` environment variable, so it works with [profiles](../profiles.md) too.

## Operational notes

- Built-in skins load from `sci_cli/skin_engine.py`.
- Unknown skins automatically fall back to `neon-theme`.
- `/skin` updates the active CLI theme immediately for the current session.
- User skins in `~/.sci/skins/` take precedence over built-in skins with the same name.
- Skin changes via `/skin` are session-only. To make a skin your permanent default, set it in `config.yaml`.
- The `banner_logo` and `banner_hero` fields support Rich console markup (e.g., `[bold #FF0000]text[/]`) for colored ASCII art.
