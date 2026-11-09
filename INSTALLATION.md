# Install Agent Scientist (SCI)

These instructions install this customized application, not another product.
Use a complete checkout from https://github.com/boltzmannlabs/Agent-Scientist.
No upstream repository is used as a fallback. Do not copy anyone else's `.sci`
directory or credentials.

## One-command installation: Linux / macOS

Run as your normal user, not with `sudo`. You need Git, Bash, `curl`, `tar`, `awk`, a
SHA256 verifier (`sha256sum` or `shasum`), internet access, and sufficient free
disk space for the managed runtime and dependencies. Full scientific models,
datasets, and optional container images need additional space and are not part
of this installation.

Clone and install:

```bash
git clone https://github.com/boltzmannlabs/Agent-Scientist.git
cd Agent-Scientist
bash ./install-sci.sh
```

The installer checks prerequisites, downloads checksum-verified managed tools,
installs the locked application dependencies, publishes `sci` and `agent-sci`
launchers, synchronizes bundled skills, and checks that the CLI starts. It does
not install developer/test dependency groups. In an interactive terminal it
reuses detected provider configuration, or opens the existing provider setup
wizard, then launches SCI. Use `--no-launch` (Windows: `-NoLaunch`) to configure
without starting chat. If setup is cancelled, software stays installed and
the installer reports that model setup is incomplete. Authenticate your chosen model
provider; SCI does not require a separate account with its original upstream.
Model charges and service usage remain subject to your providers' policies.

Fresh installations automatically use SCI's pink/magenta `neon-theme`, matching
the release palette in `assets/skins/neon-theme.yaml`. No manual skin-file copy
or theme command is needed. The classic gold default has been removed; older
`display.skin: default` settings resolve to neon. Existing custom theme choices
and user-authored skin files are preserved. The multicolor title and white
context-occupancy indicator are unchanged.

Optional model reasoning defaults to `medium`, with thinking text hidden
(`display.show_reasoning: false`). You can explicitly select another
effort with `/reasoning low`, `/reasoning medium`, or a level supported by your
model. Updates preserve existing saved effort choices and per-model overrides.

Keep the checkout in its installed location: the launchers refer to it. PATH is
registered automatically for your login and interactive shell (Bash, Zsh or
Fish); existing shell settings are preserved. The installer launches SCI by its
absolute path immediately. Subsequent terminals can use `sci` or `agent-sci`.
A script cannot change its parent Bash/Zsh process: if you skipped launch, open
a new terminal before using the short command in that shell.

### Prerequisite checks and recovery

The source setup engines check Git, download/archive/hash tools, supported
architecture, writable checkout/runtime/home/bin/temp directories, and at least
**2 GiB free on each destination filesystem** before bootstrap. This is a
bootstrap floor, not a guarantee for all dependencies: optional software,
scientific models, caches and build products can require substantially more.
HTTPS downloads test connectivity when needed; pinned cached artifacts are
reused. Download, hash or dependency failures stop installation at the failed
stage, rather than reporting success.

On Linux/macOS, missing utilities can be installed through an existing APT,
DNF, Pacman or Homebrew installation after confirmation. On Windows, missing
Git can be installed through an existing WinGet after confirmation. If the
package manager or permission is unavailable, the installer stops with manual
instructions; it does not install a new package manager. Run the installer as
your normal user; only OS package commands may request elevation.

For explicit unattended approval of missing OS prerequisites:

```bash
bash ./install-sci.sh --non-interactive --install-prerequisites
```

```powershell
.\install-sci.ps1 -NonInteractive -InstallPrerequisites
```

Without that option, unattended installation stops if an OS prerequisite is
missing. Git and the appropriate shell must already exist to run the clone
commands above; a script inside a checkout cannot repair a clone that never
started. The managed uv, Python and Python packages need no manual installation.
Model credentials are configured separately and are never invented or copied
from another person's installation. Detecting model configuration does not
prove that its credentials are currently accepted by the provider.

The installer can be rerun after an interrupted installation. It uses managed
package state rather than installing Python packages into your system Python.
An error stops the installation and names the failed stage; do not interpret
a stopped installer as successful. Existing credentials and research profiles
are not distributed by this process.

### Unattended server installation

```bash
git clone https://github.com/boltzmannlabs/Agent-Scientist.git
cd Agent-Scientist
bash ./install-sci.sh --non-interactive
# Open a new terminal after unattended installation.
sci setup
sci
```

The `--non-interactive` installation installs software only. It does not configure model access,
invent credentials, approve scientific jobs, or open a public network port.
Run `sci setup` later in an interactive terminal before chatting.

## Windows

Check `git --version` before cloning. Install missing Git from
[Git for Windows](https://git-scm.com/download/win), or use
`winget install --id Git.Git -e --source winget`, then reopen PowerShell.

From a complete checkout in PowerShell:

```powershell
git clone https://github.com/boltzmannlabs/agent-scientist.git
cd agent-scientist
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\install-sci.ps1 -NoLaunch
if ($LASTEXITCODE -ne 0) { throw 'SCI installation failed; see the error above.' }
sci
```

Run the commands in order, proceeding only after each succeeds. Complete provider
setup when prompted. `&` invokes the installer in the current PowerShell process:
it updates this terminal's PATH and saves permanent User PATH, then verifies both
short commands in another PowerShell using the saved Windows environment. The
final `sci` starts chat immediately. No manual PATH assignment is needed.

The execution-policy override applies only to this PowerShell session and ends
when it closes. Review
the installer first and use the override where company policy permits. Company
Group Policy takes precedence; do not change machine-wide policy to install SCI.
If your existing policy permits scripts, the `Set-ExecutionPolicy` line can be
omitted.

For later launches in a fresh PowerShell terminal:

```powershell
sci
```

`-NoLaunch` completes setup without opening chat, so the last command opens it
once. Omit `-NoLaunch` and the final `sci` command to let the installer launch it.
The alternative `powershell -NoProfile -ExecutionPolicy Bypass -File
.\install-sci.ps1` still saves User PATH, but runs in a child process and cannot
refresh the terminal that invoked it. Use the same-process commands above when
you want the short `sci` command available immediately in that terminal.

`install-sci.ps1` is the Windows counterpart of `install-sci.sh`: it checks the
checkout, runs the local `setup-sci.ps1` engine in user mode (managed runtime
and locked dependencies without the developer/test groups), publishes the `sci`
and `agent-sci` launchers into `%LOCALAPPDATA%\sci\bin` (or `%SCI_HOME%\bin`),
synchronizes bundled skills, verifies that the CLI starts, and then opens the
provider setup wizard when no model configuration is detected, then launches
SCI in an interactive terminal. Use
`.\install-sci.ps1 -NonInteractive` on unattended machines and run `sci setup`
later. The engine adds the launcher directory to your persistent **User PATH** for
the current Windows account, which survives sign-out and reboot. The wrapper also
refreshes the PowerShell process running it. No manual persistent PATH edit is
required after a successful installation. If you started the installer through a
separate child PowerShell or CMD process, it cannot change the parent terminal's
environment. For VS Code, finish any terminal work, close the old terminal tabs
with their trash icons, exit all VS Code windows, then reopen from the Windows Start
menu and create a new terminal. Restored terminals can retain their original PATH
even after VS Code restarts. The installer verifies the published `sci` and
`agent-sci` commands, checks
persistent User PATH, and prints an absolute launch command (including custom paths).
Use that command immediately if a stale shell or another installation hides `sci`.
An error stops the installation and names
the failed stage; rerun the installer after an interruption.

The initial pinned `uv` download prefers `curl.exe`, with three retries for
transient download failures. If curl is unavailable, PowerShell provides the
same four-attempt limit. The archive must pass its pinned SHA-256 check before
installation. A 504 indicates a download gateway timeout; failed downloads
are discarded, and the installer reports the URL and stops after its retry budget.

The classic Windows CLI runs conversations in its persistent background service.
During a task with an empty composer, **Ctrl+C** offers Cancel task, Run in
background, or Exit. **Ctrl+]** detaches; reconnect with `/resume` or
`sci --resume SESSION_ID`. Explicit `sci --no-daemon` keeps foreground behavior.
Use `/btw` for a side discussion and **Ctrl+/** to switch views. Normal resume
pickers list main conversations; saved side history remains accessible by its
explicit session ID. See the [CLI guide](website/docs/user-guide/cli.md#saved-side-conversations).

Interactive setup menus support **Up/Down** and **Enter**; multi-selection menus
use **Space** to toggle items. Windows x64 receives the pinned `windows-curses`
package automatically through SCI's managed dependencies. Native ARM64 has no
upstream curses wheel, so SCI uses its bundled `prompt_toolkit` keyboard menu
when curses is unavailable. That renderer preserves search, selection, Escape
and setup's previous-step navigation. Numbered prompts remain a fallback for
terminals that cannot run the keyboard interface; redirected input does not
open an interactive picker. No separate pip command is required.

Developers working on the source keep using `.\setup-sci.ps1` directly with
`.\activate.ps1`, which additionally prepares the test environment and `.env`
template. The Bash installer does not target native Windows. Native installers
and desktop packaging are separate build products; source support is not a
claim that signed Windows/macOS release packages have been produced or tested
on this Linux host. From CMD in a complete checkout, `scripts\install.cmd` runs
the same local `install-sci.ps1` script. It does not download another
application's installer.

### Windows PATH repair

`$env:Path = "$env:LOCALAPPDATA\sci\bin;$env:Path"` adds SCI to the **current
PowerShell process** only. The installer separately saves User PATH for future
processes. Do not shorten it to `$env:Path = ";$env:LOCALAPPDATA\sci\bin"`:
that replaces the current PATH and removes other command directories for that
session. Neither assignment updates the permanent User PATH.

If SCI is installed but sometimes reports "not recognized", open a **new PowerShell
window from the Windows Start menu** under the Windows account that installed SCI.
For a custom installation, set `SCI_HOME` to the same home used during installation.
Run this one-time repair; no administrator shell is required:

```powershell
$sciBin = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'bin' } else { Join-Path $env:LOCALAPPDATA 'sci\bin' }
if (-not ((Test-Path -LiteralPath "$sciBin\sci.exe" -PathType Leaf) -or
          (Test-Path -LiteralPath "$sciBin\sci.cmd" -PathType Leaf))) {
    throw "SCI launcher missing in $sciBin. Rerun install-sci.ps1 from the installed checkout."
}

# Preserve existing User PATH; never save the combined process PATH into it.
$sciUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$sciPathEntries = @($sciUserPath -split ';' | ForEach-Object {
    [Environment]::ExpandEnvironmentVariables($_.Trim().Trim('"')).TrimEnd('\', '/')
})
if ($sciPathEntries -notcontains $sciBin.TrimEnd('\', '/')) {
    [Environment]::SetEnvironmentVariable('Path', "$sciBin;$sciUserPath", 'User')
}

# Also make SCI available immediately in this PowerShell window.
$env:Path = "$sciBin;$env:Path"
Get-Command sci -All
sci --version
```

After the repair:

1. Finish any work in existing VS Code terminals, then close those tabs with the
   trash icon. Hiding the terminal panel does not close a terminal.
2. Completely exit all VS Code windows. Reopen VS Code from the Windows Start menu,
   rather than launching it from an old shell with an outdated PATH.
3. Create a new PowerShell terminal and run `sci --version`, then `sci`.

VS Code can revive terminals using their original environment, so a restored tab
may still have the old PATH after a restart. If a fresh terminal still has an old
environment, sign out of Windows and sign in again after saving your work. Inspect
PowerShell profile scripts and VS Code's `terminal.integrated.env.windows` setting
for a PATH override if the problem persists. These behaviors are documented by
[Microsoft PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables)
and [VS Code](https://code.visualstudio.com/docs/terminal/advanced).

Successful User PATH registration survives restarts for this Windows account;
it does not install SCI in another account, WSL, a container, or an SSH host. Keep
the checkout in its installed location. If `sci --version` fails when using the
absolute launch command printed by the installer, repair that installation first;
PATH changes cannot repair a missing or broken launcher.

## Check the installation

```bash
sci --help
sci doctor
agent-sci
```

Inside SCI, use `/help`, then send a simple greeting. A model response requires
your own working provider authentication; software installation alone does not
provide free model credits. Exit and restart with `agent-sci` to test a fresh
session after saving new tools or skills.

## First-time use

1. Complete `sci setup`: select your model provider and authenticate using its
   supported login or your own API key. The installer does not include anyone
   else's account, service access or credits. Use `sci model` later to review
   or change the selected provider/model.
2. Start `agent-sci`. Enter `/help` to see the commands and `/skills` to review
   the installed skill instructions.
3. Try a simple conversation first, for example: `Explain the difference
   between antibody affinity and specificity.` A successful response confirms
   model access, not scientific-service readiness.
4. Add the services and material your research needs using the commands below.
   Review requested permissions and installation/execution actions. Restart
   `agent-sci` after saving capabilities that take effect next session.

For a research project, enter these commands inside the running CLI, not in
your operating-system shell:

```text
/Create_profile
/Update_profile
/capabilities
/capabilities setup
/boltzmann_tools
/profiles_list
/activate
/activate "antibody-project"
/activate main
```

During creation, name the project `antibody-project` (or use your own name),
choose suitable science skills/service tools, review existing/new credentials, and
optionally provide downloaded source-file paths or public URLs with access choices.
`/profiles_list` lists native profiles; `/activate` opens their picker. Activation
restarts the native CLI in that profile and resumes its latest CLI conversation if
one exists. `/activate main` returns to main. The left status label shows the destination
of both messages and slash commands.

New profiles reuse main's local runtime or Docker image with separate workspaces;
no `--prepare` is needed. Docker downloads require approval. Remote execution backends
need separate workspace/credential review and are not cloned by this wizard yet.
Missing scientific software is not automatically installed. Boltzmann keys are validated
without submitting jobs; MCP connections are checked before explicit tool selection.
Sources are not read, uploaded, or indexed by creation. See the
[profile guide](website/docs/user-guide/features/science-profiles.md) for limitations and migration.

Type `/exit` to leave the CLI. To start it again in a later terminal:

```bash
agent-sci
```

## Data, credentials, and scientific services

User settings, conversations, skills, and profiles default to `~/.sci`.
`SCI_HOME=/absolute/path agent-sci` selects a different state home. The managed
tool store is shared by your account; it is not an independent runtime copied
into every research profile. Never run the installer with another person's
home or copy private state into this repository.

Bundled science skills are instructions, not proof that their software is
installed or that a result is scientifically correct. Their supporting
references/scripts are shipped; optional skills remain opt-in. Existing users'
activation choices are preserved. External services use their own credentials.

```text
/boltzmann_login
/add_boltzmann
/Add_skill
/Add_tool <request or official URL>
/Add_mcp <request or documented MCP endpoint/configuration>
/Create_profile
```

Boltzmann tools remain locked until a valid API key is authorized through
`/boltzmann_login` or `/add_boltzmann`. Quick Setup offers this same flow before model setup;
it can be skipped. Obtain your key at [Boltzmann](https://app.boltzmann.co/home), enter it in the
masked prompt, and check the reported account email and credits. The validated key is saved
as `BOLTZMANN_API_KEY` in the active profile's `.env`. Start a fresh conversation after connecting.
Boltzmann login enables scientific tools; it does not configure your LLM provider.
Use `/capabilities setup` for the optional portable ToolUniverse
and PubMed definitions. ToolUniverse requires approved managed dependency installation
and separate execution approval; PubMed uses a reviewed third-party HTTPS MCP.
Both require handshake verification and explicit tool selection before saving.
Existing custom/disabled connections remain unchanged. Other MCP services require
their documented setup; a website URL is not necessarily an MCP endpoint.
New capabilities become available after a fresh runtime/new conversation, not by
changing the active conversation. `/Update_profile` offers a fresh-conversation restart.
Use `/resume` or `/sessions` to select saved conversations. Their retained messages,
are restored into terminal scrollback without tool activity; continue at the bottom.
Ctrl+O / F8 opens the transcript viewer: Tab selects tool entries, Enter expands details,
and Escape returns to chat. There is no separate `/history` command.
Never put API keys in chat, the repository, or screenshots.

For OAuth-protected MCP services, dynamic registration or a service-registered
client remains supported. CIMD-only services require your team's approved
hosted identity document in `oauth.client_metadata_url`; SCI does not borrow
another application's client identity. A template is included under
`examples/mcp/client-metadata.json.example`.

## Web dashboard and desktop: optional builds

The installer prepares the core CLI. Frontend bundles and native packages are
built separately from this same checkout, with the root npm workspace lock:

```bash
npm ci
npm run build --workspace web
sci dashboard
```

Keep the dashboard bound to localhost unless you deliberately configure
authentication, a secure proxy, and network access controls. For the Electron
desktop source build:

```bash
npm run build --workspace apps/desktop
npm run start --workspace apps/desktop
```

Electron may require OS-provided desktop libraries. On a headless server, use
the CLI/dashboard instead. Native release packaging also requires each target
platform's signing credentials and release configuration; no inherited update
host or installer is used as a substitute. Application artwork is intentionally
neutral pending an approved SCI logo.

## Maintenance and troubleshooting

For an installed Git checkout, check and apply source updates deliberately:

```bash
sci update --check
sci update
```

Alternatively, enter `/update` inside the CLI. Startup update recommendations
normally use a 24-hour cache and do not install anything automatically. Only
reviewed source pushed to this repository's `main` branch is delivered. Back up
your `~/.sci` state before maintenance; keep local code edits on a separate branch.

- Command not found: rerun the installer to register PATH, then open a new terminal. The
  checkout-local launcher is also available at `.sci/bin/agent-sci`.
- Interrupted download/dependency build: rerun `bash ./install-sci.sh`; read
  the stage/error before retrying. Do not work around it using system `pip`.
- Provider/authentication problem: run `sci setup` or `sci model`. Do not share
  secrets in an issue report. SCI does not silently switch providers.
- Missing scientific dependency: follow that tool's documented environment
  requirements; installing a skill does not install its models or datasets.
- Container execution: Docker must be separately installed and a suitable
  sandbox image built/configured. See `docker/sandbox-desktop.Dockerfile`.
- Moving the source checkout: reinstall from its new location so launchers are
  republished. Back up your state before maintenance.
- Source updates are enabled for Git installations from the approved SCI
  repository. Use `sci update --check`, then `sci update` (or `/update` inside
  the CLI). Startup recommendations normally cache checks for 24 hours; they
  do not automatically install software. Every new commit on `main` can be
  recommended, so maintainers should publish only tested source changes.
- Promoted stable/canary releases and native installer/desktop feeds still
  require separate publication, signing and qualification. These paths remain
  guarded. Source updates do not create those releases or change their settings.

For developer setup and tests, use `CONTRIBUTING.md` and `source ./activate`;
these deliberately include tools that ordinary end users do not need.
