---
sidebar_label: Research profiles
---

# Native research profiles

The interactive Agent Scientist CLI creates ordinary native SCI profiles with
separate configuration, service credentials, selected skills, conversations,
memory, workspaces, and a scientific persona.

```text
/Create_profile "omics"
/profiles_list
/activate
/activate "omics" profile
/activate main
/Update_profile "omics"
/capabilities
/boltzmann_tools
/resume
```

## Omics coordinator foundation

`/activate omics` offers a one-time **Create Omics** confirmation if that name is
unused. The bundled, versioned starter creates a private workspace and conversation
through native profiles. `/activate` also offers this starter in its picker.
Subsequent activation resumes the latest Omics conversation; `/activate main`
returns to main. `/resume` selects a different saved conversation.

This first stage is ready for conversation once model authentication is available,
not scientific execution. It includes an Omics coordinator persona and 16 foundation
instruction skills, with skill listing, loading and management enabled. Scientific
executors, service connections and child specialists are not installed. Generic
delegation remains disabled. Shared LLM authentication uses the normal SCI mechanisms; no service
keys, private research, conversations or main's tools are copied. Use `/login` if model
authentication needs attention. Normal session and configuration slash commands remain
available.

The runtime uses a separate profile context and workspace, not an OS sandbox. No
scientific environment, container image or dependencies are installed at activation;
those will be configured with the future scientific tools. The native opt-out marker
prevents automatic scientific skill seeding (essential SCI operating instructions may
still be synchronized).

An existing unrelated `omics` profile opens unchanged, with an explanatory notice;
it is never silently converted. Rename it explicitly before activating the bundled
starter if that is what you intend. The starter definition is shipped with SCI, but
existing Omics workspaces are not overwritten on activation or automatically upgraded.
Older bundled Omics workspaces receive an **Add foundation skills** offer. This installs
missing names only, preserving edited files, disabled choices, credentials and research.
Only the byte-identical original starter persona is updated; custom personas are kept.
After accepting, activate Omics and use `/new` to load the additions without rewriting
an existing conversation's cached instructions. Cancellation installs nothing; an
installation failure may retain earlier successfully installed skills and reports that.

The foundation covers question interpretation, biological knowledge, data discovery,
input validation, metadata, identifier mapping, study design, QC, statistics, workflow
planning, code verification, cross-omics integration, literature synthesis, hypotheses,
reporting and provenance/access review. Each skill includes source attribution and a
shared JSON-schema reference for `StudyManifest`, `AnalysisPlan`, `ToolResult`,
`RunRecord` and `EvidenceClaim`. These schemas check record shape, not scientific
correctness, cross-record consistency or runtime authorization. Interface names in the
skills are design contracts, not registered model functions. Linked sources are reference
documentation, not installed adapters; retrieval and execution require separately
configured tools. Loading a skill never installs software or runs an analysis.
Nested orchestration, specialist creation and contribution publishing are future stages.

## Create and review

The wizard asks for a name, scientific skills, tools, service credentials, optional
sources, and final confirmation. Skills are offered from bundled defaults and the
source profile, and copied with supporting files;
main's activation choices remain unchanged. The essential operating-manual skill
remains available through native skill synchronization. Missing capabilities can be
set up in main using `/Add_skill`, `/Add_tool`, and `/Add_mcp` first.

Tool choices come from main's installed plugins and configured MCP connections:

- Boltzmann: choose an existing main key or enter a masked new key. Its read-only
  authentication check requires approval and submits no scientific jobs. A successful
  save establishes a new profile-specific authorization receipt. All five helper
  operations are included together. This grants plugin-wide workflow access, not
  individual-workflow isolation. Without successful authorization, Boltzmann is omitted.
- MCP (including ToolUniverse): approve the connection check and any local process
  execution/package-runner download. After handshake/discovery, explicitly select
  tools. No business tools run during checking. The saved allowlist does not grant
  access to future server tools. Existing source allowlists remain an upper bound.
- Other installed plugins: review the complete plugin permission scope. Code is
  reused; updates or removal of that installation affect profiles using it. Only
  already-loaded integrations with known toolsets and no unreviewed dependency or
  custom-setting requirements can be reused. Credentialed plugins without a supported
  authentication checker require their native setup in the target profile, or an MCP
  connector. Metadata review is not an execution test.

Credentials are never displayed. Approved service keys are copied into the new
profile's private storage, not live-linked to main. Replacing a copy affects only
that profile; revocation at the service affects every copy of the revoked key.
OAuth connections require their normal, reviewed sign-in; only that connection's
staged credentials are saved. Cancelling can leave a remote OAuth grant or downloaded
package/image cache; these side effects are reported.

Existing shared LLM authentication uses SCI's native provider credential store.
The wizard does not copy main's entire `.env` or arbitrary service credentials.
Provider-specific authentication rules still apply; credentials available only as
shell variables or inline configuration are not automatically shared.

Review lists skills, tool counts, hidden credential choices, backend, workspace, and
source access. Creation stages the profile outside discovery and publishes it only
after confirmation. Duplicate names cannot overwrite existing profiles. After saving,
choose **Activate now** or **Stay in current profile**.

## Selection and updating

`/Update_profile` opens the native profile picker; `/Update_profile "omics"` edits
that profile directly. Existing choices are preselected. The available choices merge
bundled science skills, main-available capabilities, and profile-local entries. A local
skill version wins over the bundled version with the same path. Custom entries and
unchanged credentials are preserved; keeping an existing connection does not probe it.

Skills, MCP connections, plugins, and each discovered MCP tool list have independent
**Select all**, **Clear selection**, and **Done** controls. Select all covers the whole
section, including filtered-out search results. Individual items remain reversible.
Plugin permissions are plugin-wide, not per-tool sandboxing. Selecting everything does
not bypass authentication, process execution consent, or connection checking.

Review the additions/removals and choose **Save and enable for the next session**.
Deselecting disables profile access without uninstalling shared software. History,
memory, workspace, persona and backend settings are retained. Changes to source mounts
on non-local backends require separate environment review and are currently rejected
before saving. Restricted legacy profiles require a separate reviewed migration, not
automatic conversion by this command.

The config commit is atomic and rejects intervening config/metadata edits. The entire
operation is not a multi-file transaction: a failed commit can retain copied files,
staged credentials, or approved downloads/OAuth grants. Failures report that possibility
and do not claim rollback. Existing conversations keep their cached prompt and toolset;
the active profile offers an explicit fresh-conversation restart after saving.

## Capability overview and standard connections

`/capabilities` (or `/capabilities search pubmed`) is a searchable, paginated local
inventory of tools, skills, MCPs and plugins. It distinguishes saved enablement from
tools visible in this conversation. Deferred-discovery availability, authentication,
dependencies, and connection readiness are labeled **not verified** where local metadata
cannot establish them. Inventory viewing does not install, authenticate, probe, or run
scientific tools.

`/capabilities setup` offers missing ToolUniverse and PubMed definitions on both fresh
and existing installations. Nothing connects automatically merely because SCI was
installed. Existing custom, disabled, or excluded connections are not overwritten.

- [ToolUniverse](https://github.com/mims-harvard/ToolUniverse): explicitly approve the
  pinned managed Python environment installation, then separately approve starting its
  stdio MCP and handshake. No ad hoc installation into SCI's own environment is used.
- [PubMed MCP](https://pubmed.caseyjhand.com/): the offered HTTPS endpoint is a public
  third-party service, not NCBI-operated. It needs no local server installation. Review
  that destination and approve discovery before selecting tools. Its availability and
  access policy can change; a failed handshake saves no enabled connection.

Save an explicit allowlist of discovered tools. New MCP tools are not silently granted.
ToolUniverse's `execute_tool` is itself a dispatcher into its internal catalog: granting
it is **not** per-scientific-tool isolation, including when that internal catalog changes.
Choose only discovery operations if you do not want to grant dispatcher access.

These saves defer MCP activation in this CLI only. Other running processes retain their
watcher behavior. If another config edit arrives while changes are deferred, this CLI
reports it and asks for restart or an explicit `/reload-mcp`; it cannot automatically
reload only that edit because the existing reloader reconnects all servers. Explicit
reload also rebuilds the conversation's tool prefix.

## Boltzmann scientific catalog

```text
/boltzmann_tools
/boltzmann_tools protein
/boltzmann_tools search docking
```

The paginated view uses the installed scientific module registry, grouped by domain,
module and tool name—not the five connector operations. Unavailable/on-hold entries
are labeled separately; removed/ignored entries are omitted. Catalog visibility grants
no execution access. The local authorization receipt and profile restrictions are shown
without revealing keys or making a network request. Natural-language inventory guidance
points to this same installed registry in main and named profiles.

The previously reported connector input-schema defect remains a separate execution
readiness blocker. This catalog/update feature does not establish that a scientific job
can run, that every contract is verified, or that results are scientifically valid.

## Environment

No `/activate … --prepare` step is needed for new native profiles.

| Main's backend | New profile |
|---|---|
| Local | Same installed host software, separate workspace |
| Docker | Reviewed image pinned to its ID, separate container/workspace |
| SSH/cloud/other remote backend | Creation stops with guidance; a safe workspace/credential-copy adapter is required |

The local backend is profile separation, **not OS-level filesystem isolation**.
Docker covers terminal execution; trusted host plugins and local MCP processes are
not automatically containerized. Main's writable mounts, credential-file mounts,
and environment forwarding are not copied. Docker must already be installed/running;
a missing image requires download approval. There is no silent backend fallback.
Scientific dependencies, datasets, GPU support, and result validity remain separate
requirements; selecting a skill does not install its scientific software.

## Sources

Add a local file/folder or public HTTPS reference URL. Each source has a reviewed mode:

- **Reference only:** ask before reading or retrieving contents.
- **Allow local reading/processing:** ask before sending contents to a model or service.
- **Allow relevant contents to selected model:** permits that model, not arbitrary services.

Creation reads no source contents and does not download, upload, or index them.
Do not enter signed URLs or secrets. Approved Docker-local sources are mounted
read-only under `/sources/<index>`. Moving a referenced source breaks its location.
Source-access instructions guide the agent; on the local backend they are not an
OS sandbox or a substitute for filesystem permissions.

## Listing and activation

`/profiles_list` uses the same registry as `sci profile list`, including profiles
created outside this wizard. `/activate` presents a picker with the current profile
marked; a name activates it directly. The status bar's left label shows `[main]`,
`[omics]`, etc., shortened on narrow terminals.

Switching hands off to a fresh native CLI process after normal shutdown. It resumes
the destination's latest CLI session when one exists, otherwise starts a new one.
This switches slash commands as well as messages: `/add_boltzmann`, `/Add_tool`,
`/Add_mcp`, and skill commands affect the selected profile. Finish or cancel running
work first. No live agent/toolset is transplanted between profiles, and activation
does not rewrite an existing cached system prompt.

Before switching, the departing conversation must flush successfully; failure leaves
the current conversation in place. `/resume` and `/sessions` open a searchable, paginated
picker for the active profile with title, last activity, message count, and session ID.
`/resume <session-id>` still selects directly. Interactive resumption uses a fresh native
CLI runtime, so current permission gates apply rather than reviving revoked tool access.

Resume restores **retained** user/assistant messages in full, including compression ancestry,
without tool activity in the chat. Ctrl+O / F8 opens a scrollable, searchable transcript;
Tab selects a tool entry and Enter expands its stored arguments or result. Escape returns
to the unchanged chat prompt. There is no separate `/history` command.
Detected secrets are masked and reasoning text
is hidden. Deleted or unrecorded history cannot be reconstructed. Visible history is
separate from model context: replay does not append historical tokens, rerun tools, or
change the cached prompt. Your terminal's own scrollback capacity still applies.

Existing legacy science profiles also activate directly, without migration or setup
questions. Their saved files, credentials, history and isolation settings are preserved.
The native CLI applies their existing execution checks and permission gate before model
turns. A profile whose local setup was never completed still has no local execution;
activation neither prepares it nor grants new access. Invalid or changed legacy sandbox
configuration blocks execution with an error, not a setup wizard or host fallback.

`/add_boltzmann` is always offered in the interactive CLI, including profiles that did
not select Boltzmann during creation. The command itself grants no tool access.
Successful masked-key validation enables the connector in the active profile for
the next session. Legacy isolated profiles add only the five Boltzmann operations
to their reviewed policy, retaining per-operation external-access approval and
all local execution restrictions. Their activation stays deferred even with `--now`.

In the creation tool picker, ToolUniverse and Boltzmann appear first when available.
Select entries to toggle them, then choose Done; the full description is printed
after selection even when its menu label was shortened.

## Optional routing and collaboration

Creation does not opt a profile into automatic routing or data sharing.

```text
/activate main
/profile_routing on
/profile_routing off
```

Choose eligible profiles and approve the displayed router model/destination.
Only the new request and profile-purpose metadata go to the router, not earlier
conversation history or project files. The router cannot grant tools or permissions.
Native routed turns use the profile's native configuration and provider; legacy
routed projects retain their restricted execution checks. Manual activation uses
the native CLI rather than this routing transport. Routing opt-in is session-local
and must be renewed after a native CLI restart.

Multi-profile steps run sequentially with bounded turn time and step count. Existing
directional sharing grants do not imply reverse grants. New or potentially sensitive
transfers require confirmation; detection is not exhaustive. Final aggregation also
requires approval before sending outputs to the coordinator. Provider charges apply.
Failures do not silently switch provider/profile or automatically retry. Cancellation
may retain completed outputs; owned-worker cleanup failures are reported.
