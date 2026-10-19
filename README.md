![Agent Scientist — autonomous scientific agents for life sciences](assets/agent-scientist-banner.png)

# AGENT-SCIENTIST

**A scientific AI assistant by Boltzmann Labs.**

Research literature, analyze data, and run approved computational workflows from
your terminal. Connect scientific services, add reusable skills, and organize
work in named research profiles.

[Installation](#installation) · [First steps](#first-steps) · [Features](#features) ·
[Commands](#command-reference) · [Updates](#updates) · [Documentation](#documentation)

## Features

- **Scientific tools:** API-key-gated Boltzmann, plus optional ToolUniverse,
  PubMed, and other MCP services.
- **Reusable skills:** instructions for bioinformatics, chemistry, statistics,
  literature research, and visualization.
- **Research profiles:** separate conversations, permissions, settings, and workspaces.
- **Flexible models:** supported providers and compatible custom endpoints.
- **Persistent conversations:** saved chats and inspectable tool activity.
- **Extensible workflows:** add skills, tools, and service connections.

Skills are instructions—not installed software or proof of scientific validity.
External services may require credentials, credits, and additional dependencies.

## Installation

Install from this repository as your normal user. The installers prepare a managed
runtime, locked application dependencies, CLI launchers, and bundled skills, then
open provider setup in an interactive terminal. No manual system-Python package
installation is required.

Internet access and free disk space are required. Scientific model weights,
datasets, Docker images, and optional tool dependencies are **not** included.

### Ubuntu

Prerequisites: Git, Bash, curl, tar, awk, and a SHA256 verifier. If missing, install
the standard utilities through your system administrator or Ubuntu's package manager:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates tar gawk coreutils
```

Clone, install, and launch **without sudo**:

```bash
git clone https://github.com/boltzmannlabs/agent-scientist.git
cd agent-scientist
bash ./install-sci.sh
export PATH="$HOME/.local/bin:$PATH"
agent-sci
```

Follow provider setup using your own account or API key. The PATH command enables
the launcher in this terminal; open a new terminal for future sessions.

For unattended installation, use `bash ./install-sci.sh --non-interactive`,
then run `sci setup` interactively before chatting.

### Windows

Prerequisites: Git for Windows and PowerShell. Run from a normal PowerShell
window, not an administrator shell:

```powershell
git clone https://github.com/boltzmannlabs/agent-scientist.git
cd agent-scientist
.\install-sci.ps1
```

Follow provider setup, then open a new terminal and launch:

```powershell
agent-sci
```

If PowerShell blocks the local script, review it first. Where your organization's
policy permits, run it with a process-only execution-policy override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-sci.ps1
```

This override is temporary. Do not bypass organization-enforced controls.

If the launcher is not found, add its directory to this terminal's PATH:

```powershell
$sciBin = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'bin' } else { Join-Path $env:LOCALAPPDATA 'sci\bin' }
$env:Path = "$sciBin;$env:Path"
agent-sci
```

For unattended installation, use `.\install-sci.ps1 -NonInteractive`, then
`sci setup`. From CMD, `scripts\install.cmd` invokes the same installer.

**Keep the source checkout in its installed location:** the launchers refer to it.
Windows source installation is separate from a signed native installer; native
Windows/macOS package qualification remains pending. See the
[full installation guide](INSTALLATION.md) for macOS, optional builds, and recovery.

## First steps

1. Run `sci setup` if you skipped provider setup; use `sci model` to change it later.
2. Launch `agent-sci`, then type `/help`.
3. Try: “Explain the difference between a prediction and experimental evidence.”
4. Use `/capabilities` to inspect access and setup requirements without executing tools.
5. Connect services as needed, then restart for next-session additions.

Check the installation from your operating-system terminal:

```bash
sci --help
sci doctor
```

A successful chat confirms model access—not scientific-service readiness.

## Scientific services

### Boltzmann

Inside SCI, run:

```text
/add_boltzmann
```

Enter your own API key in the masked prompt. The connector remains locked until
the selected profile has a validated key and its authorization record.
After saving, restart SCI and use:

```text
/boltzmann_tools
/boltzmann_tools search docking
```

The catalog groups scientific tools by domain and module, not connector helpers.
Catalog visibility does not grant execution access.

When an authorized Boltzmann workflow matches a request, SCI prefers its installed
contract. Missing inputs or authentication failures must not trigger silent
provider switching; ambiguous submissions must not be duplicated.
See [Boltzmann integration](plugins/boltzmann/README.md).

### ToolUniverse, PubMed, and other services

Run `/capabilities setup` to review optional ToolUniverse and PubMed definitions.
Setup requires approval, connection discovery, and explicit tool selection.
ToolUniverse may need a managed dependency installation; the included PubMed
option uses a third-party MCP endpoint, not an NCBI-operated server.

Use `/Add_mcp <request or endpoint>` for other MCP-compatible services.
An ordinary website or REST API is not automatically an MCP server. Review
authentication, permissions, and data-transfer requirements before connecting.

## Research profiles

Create a project with selected science skills, tools, service credentials, and
optional local files or reference URLs:

```text
/Create_profile
/Update_profile "omics"
/profiles_list
/activate "omics"
/activate main
```

Use your chosen profile name in place of `omics`. Bare `/activate` opens a picker.

- Reuse an approved independent copy of a service key or enter a profile-specific
  key. Supported model-provider authentication can be shared.
- Profiles reuse supported installed runtimes/images with separate workspaces.
  No separate `--prepare` step is needed for the normal creation flow.
- Local execution is **not** an operating-system sandbox. Remote backends and
  missing scientific dependencies need separate setup.
- Sources have explicit access choices; adding a path or URL does not upload,
  read, or index its contents automatically.
- Switching preserves the departing conversation and resumes the destination's
  latest saved CLI conversation when available.

See [research profiles](website/docs/user-guide/features/science-profiles.md)
for capability selection, environment limits, and migration.

## Command reference

Shell commands such as `sci setup` run in your operating-system terminal.
Slash commands below run **inside Agent Scientist**.

| Command | Purpose |
|---|---|
| `/help` | Show available commands |
| `/model` | Review model/provider choices |
| `/model remove [provider]` | Review global removal and affected saved model routes |
| `/capabilities` | Inspect the active profile's capabilities and setup state |
| `/capabilities setup` | Review optional default MCP connections |
| `/add_boltzmann` | Authorize Boltzmann for this profile |
| `/boltzmann_tools [domain]` | Browse the scientific catalog; use `search <text>` to search |
| `/Add_skill` | Supply skill material or describe a workflow for a reviewed draft |
| `/Add_tool <request or URL>` | Ask the agent to add a tool |
| `/Add_mcp <request or endpoint>` | Ask the agent to connect an MCP service |
| `/skills` | Review skill instructions and management options |
| `/Create_profile` / `/Update_profile [name]` | Create or review a research profile |
| `/profiles_list` / `/activate [name]` | List or switch profiles |
| `/resume` / `/sessions` | Choose a saved conversation |
| `/new` | Start a new conversation |
| `/exit` | Leave the CLI |

Addition requests do not guarantee compatibility. Review downloads, execution,
permissions, and costs. Skill links/paths go to the agent; **Describe a workflow**
provides guided drafting.

Resuming displays retained user messages and agent replies in scrollback.
**Ctrl+O / F8** opens the transcript viewer; select a tool entry and press Enter
for details, then Escape to return. Nothing is rerun during restoration.
Saved transcript visibility is separate from the model's compressed context.

LLM providers added through `sci auth add` or `sci model` become available in
main and every profile. Each profile keeps its own selected model. Removing a
provider globally reviews saved defaults and auxiliary routes, including main;
choose a replacement or leave a route explicitly unconfigured. Re-adding clears
that provider's removal exclusions. Saved credentials are retained by removal.

For Codex, `sci auth add openai-codex --type oauth` offers the current Codex login,
SCI's saved login, or a fresh sign-in. SCI checks authentication before reporting
success. Reusing a Codex file login stores its path and follows current tokens;
Codex owns refresh. Open Codex to renew an expired shared token. Keyring, auto,
and ephemeral Codex stores currently require a fresh SCI login or an explicitly
configured Codex file login; SCI does not silently import a stale fallback file.
Other running conversations pick up provider configuration changes in a new session.

In the interactive CLI, `/login` opens the same provider/sign-in menu as `sci model`,
not a vendor portal. It returns to your unchanged conversation; saved defaults apply
to new sessions. Use `/model` for an explicit current-session model switch.
Selecting Codex in this setup automatically validates and reuses the current
file-backed Codex login (`CODEX_HOME`, or the current user's `.codex` directory),
ahead of stale SCI credentials, without another browser sign-in. This also applies
on a fresh installation. Missing logins use normal setup; invalid or unsupported
sources stop with recovery guidance, never a silent fallback or account switch.

## Release versions

Releases follow `v1.M.m.p` (Major.Milestone.Minor.Patch), starting at
`v1.0.0.0`. See [release versioning](RELEASE_VERSIONING.md) for bump rules
and native-package compatibility.

## Data and safety

SCI state defaults to `~/.sci` (`$HOME\.sci` on Windows). `SCI_HOME` selects
another state directory; it does not migrate existing data.

- `config.yaml`: settings; `SOUL.md`: persona instructions.
- Protected credential storage / `.env`: personal secrets.
- Conversations, memory, project state, and outputs remain separate from Git.
- Never paste keys into chat, screenshots, or issue reports.
- Installing a skill does not install its dependencies or authorize execution.
- Computational outputs need scientific review. Successful execution or a
  security scan does not establish experimental or clinical validity.

## Updates

For an installed Git checkout:

```bash
sci update --check
sci update
```

Inside SCI, `/update` exits the session and starts the updater. Startup update
recommendations are normally cached for 24 hours and do not install automatically.
The updater snapshots profile state before applying changes; keep your own backups,
and resolve local source edits before updating.

Source updates follow this repository's `main` branch. They are not a promise of
stable/native releases. Do not substitute another application's installer or feed.

## Troubleshooting

| Problem | Next step |
|---|---|
| `agent-sci` not found | Open a new terminal or use the PATH instructions above |
| Installation interrupted | Read the failed stage, fix its cause, and rerun the same installer |
| No model response | Check authentication with `sci setup` or `sci model` |
| Scientific service unavailable | Check `/capabilities`, credentials, and required dependencies |
| Newly added tools not visible | Restart SCI; do not assume an existing conversation refreshed |
| Startup stalls | Press Ctrl+C, retain the error, and run `sci doctor`; do not delete `.sci` |

## Documentation

- [Detailed installation and optional dashboard/desktop builds](INSTALLATION.md)
- [Research profiles](website/docs/user-guide/features/science-profiles.md)
- [Sessions and resume](website/docs/user-guide/sessions.md)
- [CLI commands](website/docs/reference/slash-commands.md)
- [Developer setup](CONTRIBUTING.md) — use `scripts/run_tests.sh` for Python tests
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Data privacy and handling](PRIVACY.md)
- [Security policy and private reporting guidance](SECURITY.md)

Dashboard, messaging, and desktop surfaces require separate setup; see the
installation guide for availability and build instructions.

## License

[MIT](LICENSE), with original copyright and third-party notices retained.
Bundled third-party components and skill resources retain their applicable licenses.
