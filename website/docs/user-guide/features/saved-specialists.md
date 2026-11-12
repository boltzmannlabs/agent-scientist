---
title: Saved specialist subagents
description: Create, run, copy and manage reusable specialists in main or any SCI profile.
---

# Saved specialist subagents

A saved specialist is a reusable task definition: a name, purpose, instructions,
selected skills and tools, expected output, and execution limits. Running it creates
a temporary child agent using SCI's existing delegation engine.

**You can create specialists in the base Agent Scientist (`main`) without creating a
profile.** You can also create them inside any profile. Main and each profile keep their
own definitions and run history. A specialist is neither a new profile nor a new installation.

Delegation is enabled by default in main and newly created native science profiles. Existing CLI
configurations receive a one-time upgrade to include it, including profiles created by the older
wizard that saved only terminal/file/skills. This enables assignment to specialists; it does not
grant them additional scientific tools or credentials. Changes take effect in a new conversation.
An intentional opt-out after the upgrade remains respected. Legacy restricted-worker profiles keep
their reviewed boundaries and require their existing migration flow before using native specialists.

## Quick start

Start the interactive CLI:

```bash
agent-sci
```

Create a specialist:

```text
/Create_subagent literature-reviewer
```

The wizard asks only for a name, purpose, skills/modules, tools/packages and expected output.
The review offers additional instructions and optional reference locations. New specialists support
**both explicit requests and automatic matching**; there is no separate mode question.

New specialists include available file operations (read/search/write/patch), terminal, Python execution
and process management from the owning profile. The final review displays these grants. Setup does
not execute source files. Assignments may use these tools when their instructions/task require them;
existing execution approval and backend rules remain effective. Older specialists keep their saved
selections; **Use standard tools** in review adds the available defaults before saving. Scientific
services still require their own credentials and authorization.

For purpose, enter ordinary text **or a local `.md`, `.markdown` or `.txt` path**. Setup reads
the complete instruction file, derives a short routing description and shows the full instructions
in review. The reviewed text is saved with the definition and supplied before the child's first
model request. Adding the same file under References or manually selecting `read_file` is unnecessary.
Additional instructions also accepts an instruction-file path. Invalid paths ask again without
discarding earlier answers. Updating an older bare-path definition imports its contents for review.

Searchable selectors have Select all, Clear selection and Done. When a search is active,
**Select matching / Clear matching** affect only the matching results. Unfiltered Select all
covers the entire section. You can deselect individual entries afterward.

Example choices:

- Purpose: compare evidence in supplied papers and identify limitations.
- Skills: your enabled literature-review skill, if available.
- Tools: the configured PubMed tools needed for the assignment.
- Output: a cited comparison with disagreements and unanswered questions.
- Additional instructions (optional): distinguish evidence from hypotheses.

Save, then start a fresh conversation and assign a task:

```text
/new
/subagent run literature-reviewer "Compare these two supplied abstracts and list their limitations"
```

The run command queues an explicit request into the ordinary SCI agent turn. The parent
uses `delegate_task` with the saved specialist name; it reports a blocker if the definition
is unavailable. Unavailable selected tools are excluded from the child and reported; they do not
block an informational task that does not need them. A queued request is not a submitted scientific job.

You can also ask naturally:

> Ask literature-reviewer to compare these supplied papers.

New specialists can be called explicitly **and** selected automatically for matching tasks,
including explanatory questions. Selection is model-driven, not a guarantee that every matching
request will be delegated. Use `/subagent run` when you want to assign a specific specialist.
Older explicit-only definitions retain their setting until reviewed and saved through
`/Update_subagent <name>`.

Creating or editing a specialist does not run a model, install software, submit research jobs,
or change the current conversation's cached prompt/tools. New or edited definitions require a
new conversation. The wizard clearly reports this; it never silently restarts your conversation.
The definition snapshot is retained in the existing session metadata, so resuming that conversation
keeps its specialist catalog unchanged. Execution still checks current revisions and enabled state:
an old snapshot cannot restore a disabled or replaced specialist's permission.

## Reviews inside a longer workflow

A specialist's report can be the final answer or an intermediate review. For example:

> Use my critic specialist to review these enzyme candidates. This is an intermediate
> review: evaluate its findings, then continue the already approved solubility step
> for candidates that pass. Stop if evidence or a new approval is required.

The parent marks that assignment as an intermediate review and receives its result
through the ordinary delegation loop. It can evaluate the review and continue the
remaining authorized work without another message saying “Continue.” The original
review stays unchanged in the specialist's run receipt and transcript; `/subagent
status <run-id>` makes it available independently of the parent's subsequent answer.
Completion of a review does not establish that the entire pipeline succeeded.

Report-only assignments keep direct delivery of the original report. Older
assignments without a delivery choice retain that behavior. Failed or incomplete
reviews remain explicit outcomes; an intermediate review grants no new tools,
credentials or execution approval. The same distinction applies to background
completion notifications when the owning surface supports automatic delivery.

Compression retains the conversation's reviewed specialist-selection interface,
including discovery and delivery choices. Preview does not change it, and resume
uses the saved snapshot. New or edited specialists still require a new conversation;
compression does not silently adopt them.

## Commands

Command matching is case-insensitive; specialist names use lowercase letters, numbers,
hyphens or underscores. Quote task text or other arguments containing spaces.

| Command | Purpose |
|---|---|
| `/Create_subagent [name]` | Guided creation in main or the active profile |
| `/Update_subagent [name]` | Choose a saved specialist in the active profile, or open review directly by name; edit purpose, output, skills/modules, tools, instructions and references |
| `/subagents [search text]` | Searchable manager with saved specialists and run history |
| `/subagent show <name>` | Display the definition and enabled/review state |
| `/subagent run <name> <task>` | Queue an explicit assignment; prompts for a task if omitted |
| `/subagent copy <name> [profile-or-main] [new-name]` | Copy for review; omitting the destination opens a profile picker |
| `/subagent export <name> "<destination.json>"` | Export a portable definition for review |
| `/subagent import "<definition.json>" [new-name]` | Import disabled, then review in this profile |
| `/subagent duplicate <name> <new-name>` | Make another definition in the current profile for review |
| `/subagent disable <name>` | Block new assignments without silently stopping running work |
| `/subagent enable <name>` | Open the review workflow before enabling |
| `/subagent delete <name>` | Delete the definition after confirmation; keep run history |
| `/subagent status [run-id]` | Show recent runs or one run's saved result/error and transcript location |
| `/subagent history [page]` | Browse retained run receipts, ten per page |
| `/subagent stop <run-id>` | Request cancellation of a run owned by this conversation |
| `/subagent steer <run-id> <message>` | Send a course correction to an owned live run |

Existing `/agents`, live progress monitoring, and `/stop` continue to work. Stop/steer
preserve the delegation engine's ownership checks: a run ID alone is not permission to
control another conversation's agent. History can be viewed after restart, but controlling a
run requires its owning live conversation/process.

## Main, profiles and copying

```text
# In main:
/Create_subagent literature-reviewer

# Make a reviewed copy available to omics:
/subagent copy literature-reviewer omics
/activate omics
/Update_subagent literature-reviewer
/new
/subagent run literature-reviewer "Compare the supplied abstracts"

# Return to main:
/activate main
```

The copy is **disabled pending review in the destination profile**. It carries instructions
and capability names, but does not copy credentials, source references, child-delegation
grants, conversations or run history. Missing capabilities remain visible during review.
Configure them through the existing integration commands or deselect them. Duplicate names
never overwrite definitions; provide a new name or edit the existing definition explicitly.

A specialist uses the owning profile's existing delegation model configuration and authentication;
without a delegation override, it inherits the parent's model. There is no separate LLM login.
Research-service credentials stay with the profile and are never stored in a specialist definition.
An already-running child retains its assigned model/provider when the parent model changes. Run
receipts show the actual model/provider; cancel and start a new assignment to use a different route.

To move a specialist to another server:

```text
/subagent export literature-reviewer "/path/to/literature-reviewer.json"
```

Transfer that JSON file using your normal file-sharing method. On the destination server, in the
intended profile:

```text
/subagent import "/path/to/literature-reviewer.json"
/Update_subagent literature-reviewer
/new
```

Export/import also excludes source locations, child grants, credentials and run history. Review
instructions before sharing: they may contain private text you entered. Capability names and
selected module references travel with the definition; software and skills are not installed by
import. Imported definitions cannot run until reviewed and enabled.

## Recoverable editing and additional capabilities

`/Update_subagent` opens a searchable, paginated picker for the active profile, including disabled specialists. Select a name to open its review, or cancel without changing it. An empty profile offers creation. `/Update_subagent <name>` opens the review immediately; it does not repeat the creation questions.
Blank purpose/output edits keep the existing value. For references, `none`, `skip`, `back` or blank
skips the entry. A missing path or invalid URL asks again without throwing away the draft.

Cancellation retains the draft **in the current CLI process and owning profile**. Use
`/Create_subagent` or `/Update_subagent <name>` to resume it. `Discard draft` removes it explicitly;
previously saved definitions remain unchanged. Unfinished drafts do not survive a CLI restart.

From review, **Add capabilities** opens the existing Add skill, Add tool, Connect MCP or Configure
Boltzmann flow for the active profile. The draft remains available. Finish setup, resume the draft,
select the added capabilities, save and start `/new`. This does not borrow another profile's access.

### Add capabilities for one specialist only

Choose **Add for this subagent only** from creation/editing review. It offers:

- **Add tool (link or request):** enter the same request you would give `/Add_tool`, such as
  `add this tool: https://github.com/owner/repository`. A separate normal SCI setup conversation
  runs in this specialist's private destination using the owning agent's selected model/login.
  Review the provider/model and outbound request before starting. The setup agent uses existing
  installation/scanning/PM and capability-consent mechanisms, asks for action approvals, and reports
  unsupported integrations or partial setup. It does not receive the parent's conversation/references.
  After setup, separately approve loading/discovery of installed additions and select private plugin
  tools. Save the specialist and use `/new`. A repository link is a setup request, not a guarantee
  that every arbitrary repository can become a callable tool; executable adapters are not invented.
- **External skill:** provide a prepared `SKILL.md`, complete skill folder/ZIP, supported identifier,
  or public source URL. SCI reuses guarded source loading, quarantine, scanning, review and installation.
  Supporting files are preserved. Plain documents belong under References; this flow does not turn
  arbitrary material into a new skill automatically.
- **MCP service:** supply a public MCP endpoint or a local JSON/YAML file containing `mcpServers`
  or `mcp_servers`. Choose one connection, configure masked credentials or OAuth, approve external
  actions, test handshake/discovery, select an explicit tool allowlist, and confirm private saving.
  Local MCP servers are supported through configuration files with executable and separate arguments.
- **Use an already-installed program:** provide an existing executable/script, interpreter where needed, separate
  arguments, working directory, purpose, inputs, outputs and limitations. SCI saves a reviewed,
  scanned instruction skill. The program remains at its original location and is not run during
  setup. Private terminal/process access is included for final review, allowing execution when the
  assignment requests it, even if main does not expose terminal tools. This grants the backend's
  terminal access, not an executable-specific sandbox. This option does not install new software;
  choose Add tool for a broader installation/integration request.

These additions are stored beneath `<owning SCI_HOME>/subagent-data/<private-id>/`. Main, other
profiles and sibling specialists do not receive their skill index, tool schemas, connection settings
or private credentials. You may select existing inherited capabilities alongside private additions.
Inherited service tools continue using the owning profile's authorization; private MCP tools use
their own credential storage. Existing-key reuse is offered only where a matching configured secret
exists, and requires review; new keys use masked capture. OAuth follows the service's supported flow.
The LLM still uses the owning agent's resolved model/authentication; there is no second LLM login.

Review lists private skills and tools explicitly. **Remove private capability** removes a selected
grant without deleting retained software, connections or credentials. Save the specialist and start
`/new` before assigning work. Private configuration/credential/skill changes invalidate the reviewed
scope until a new review/save; an old conversation cannot silently adopt new private grants.

Private setup files can remain after a failed or cancelled draft, particularly OAuth grants or
approved package-runner downloads. The UI identifies the private destination. No parent settings
are rewritten. Copy/duplicate/export/import deliberately omit private capabilities and credentials;
configure them again in the destination. Parent-driven automatic selection and explicit runs both
work. Nested specialists with their own private capability scope currently require direct assignment
from the owning profile, rather than delegation through another specialist.

Private capability scope controls SCI discovery, configuration and credentials. It does not create
an operating-system sandbox: approved terminal programs and local MCP servers still have their
execution environment's access. Specialist results and requested artifacts are returned to the parent.

Example:

```text
/Update_subagent reviewer
# Choose Add for this subagent only → Add tool, External skill, MCP service or an installed program.
# Complete the review; Save and enable for the next conversation.
/new
/subagent run reviewer Use your private integration for this approved assignment.
```

## Skills, tools and integration permissions

Skills supply instructions; they do not grant execution permission. Selected skills are loaded
fully into the child's task context, without shell-template preprocessing or automatic dependency
installation. Loading linked skill reference files remains possible through the selected skill.

The exact selected tool names are enforced during direct calls, tool discovery and programmatic
registry dispatch. A child cannot gain tools that its parent/profile did not grant. Adding a tool
to an MCP server later does not automatically add it to an existing specialist.

Tool choices show locally available metadata without probing services. Actual availability is
checked when constructing the child. Configure missing MCPs, plugins or credentials using the
existing SCI flows, then start a new conversation.

Boltzmann is presented as **one “Boltzmann job tools” package** containing upload, submit, status,
download and diagnostic operations. The five helpers are not separate picker entries. The package
is offered only when this profile has its local credential and authorization record; execution
still performs the existing service authorization checks. A key in main does not authorize another
profile. Use `/add_boltzmann` in the owning profile to configure access.

The skill selector also offers **Boltzmann / domain / module** entries from the installed plugin's
maintained catalog. Search for a topic such as protein engineering and select the modules you need.
A module includes common platform instructions and preselects the job package for review. Only the
chosen module files are preloaded; unrelated scientific module files are not preloaded. Module
selection focuses instructions, not execution authorization: profile workflow restrictions still
apply, and the selected base skill can supply linked references when needed.

Missing selected tools are reported and withheld, not silently replaced. An unavailable
`browser_back`, for example, no longer prevents an answer that needs no browser. A task requiring
an unavailable tool must return the blocker rather than claim execution. This does not bypass
Boltzmann authorization, scientific-workflow restrictions, file validation, or job/upload approvals.
No research-service plugin is copied or rewritten by this feature.

Terminal and code-execution access are shown in the final capability review. These capabilities
can use the configured execution environment: **a specialist tool allowlist is not an OS-level
filesystem or network sandbox**. Filesystem/network isolation still belongs to the profile's
execution backend. Configuration/credential management, skill authoring, memory writes,
scheduling and cross-platform messaging are not specialist grants.

Adding a reference file, folder or public HTTPS URL reads its supported text during setup and
saves a snapshot. Selecting the source authorizes including that saved text in future assignments
to this profile's selected model; it does not authorize uploads to scientific services. References
are supplied automatically as source data, separate from the specialist's instructions. Folder
loading includes supported text/code files recursively, including Python, R, shell, JavaScript,
TypeScript, notebooks as JSON and common compiled-language source files. Hidden files, empty files,
dependency directories and unsupported binaries are excluded; skipped-file counts are reported.
Symlinks are rejected. Public URLs use the existing guarded
download path. Text-based PDFs use existing local extraction; missing dependencies are reported
without automatic installation. Inaccessible sources give a recoverable error.

Multiple files, folders and URLs can be added one at a time. Adding appends rather than replacing;
exact repeated sources are not duplicated. **Remove a reference** removes one selected source;
**Clear references** removes all. Saving an update retains unchanged snapshots.

Limits are 8 MiB per source file/download, 10,000 folder entries/documents and 256 MiB combined text
snapshots per collection. Instructions retain their 100,000-character bound and definitions retain
their 256 KB metadata limit. These are resource bounds, not a one-file restriction. Oversized inputs
are rejected without silently truncating them. Choose smaller sources when a limit is exceeded.
Small collections are preloaded. Collections above 40,000 characters or 20 documents live in a
private profile-local `subagent-sources/` library. The prompt contains a bounded catalog preview and
the complete catalog path; existing read/search tools retrieve relevant full snapshots as needed.
The collection does not occupy every request's context. Source paths are mapped through the existing
backend mount/sync bridge; dependencies and data formats still need to be supported by that backend.
**References → Refresh saved
contents** explicitly replaces snapshots for the next conversation. Changing or deleting original
files does not silently change reviewed snapshots. Earlier path-only definitions load their sources
before inference on assignment; review and save them to persist stable snapshots.

File reading and search are included automatically when available to the parent/profile and needed
for supplied paths. Read-only reviewers are limited to selected references and file/folder paths
in the user's assignment. Instruction-file provenance does not grant directory access. With inline
data and no approved paths, file-reading/search tools are withheld. Parent-invented file locations
do not broaden access. Terminal, file writing and scientific-service tools remain separate grants.
Execution/service workflows retain their existing backend access so they can inspect generated
artifacts; these restrictions are not an OS sandbox. Copy/export excludes reference snapshots and private source
locations, while preserving reviewed instruction text; destination review is still required.

Adding a `.py` file reads its source without importing or running it. If the user assigns execution,
the specialist can run the original project or reviewed snapshot using its granted tools. A project's
relative imports/data layout may require running from the original folder. Missing third-party
packages must be reported with actionable guidance; this feature does not install arbitrary script
dependencies into SCI. A public webpage/repository URL supplies readable page content, not an automatic
repository installation. Use a raw source URL or a prepared local project for executable code.
Binary spreadsheets, images, model weights and arbitrary binary datasets are not automatically
converted into text: use an available appropriate tool/reader or a supported export. Old immutable
snapshots may remain on disk for existing conversations after source removal; removal changes the
definition's future access, not an immediate erasure of historical data.

Children cannot open user clarification dialogs. They must return missing inputs or approval
requirements to the parent. Existing execution approval rules still apply; this feature does
not enable blanket automatic approval.

## Execution limits

The ordinary wizard does not ask about child specialists, iteration counts or runtime seconds.
Internal limits remain to prevent runaway work: new definitions have a maximum of 30 model
iterations and 900 seconds, further bounded by the existing profile/delegation settings. These are
execution safeguards, not an exact dollar spending cap. Service charges still follow the existing
approval policy. Older customized limits and child grants are preserved when editing; any retained
child grants appear in the review.

The existing nested-delegation permission checks remain: children cannot exceed a lead's tools or
skills, create cycles, extend its deadline or multiply its iteration budget. New specialists do not
receive child-delegation grants from this simplified wizard.

There is no small fixed limit on saved definitions. Concurrent execution is bounded by the existing
delegation settings; this feature does not add an unlimited task queue.

## Status, results and persistence

Every constructed named run gets a private receipt and uses the existing live transcript and
child session storage. Status includes the specialist name, run ID, outcome, available result/error,
and transcript path. Budget-exhausted results retain their truncation indicator.

A saved definition survives restarts. Active execution is process-local: closing/stopping the owning
session may stop its children, and this feature does not automatically resume interrupted work.
When a retained receipt has no known live worker and no final result, status says **unknown** rather
than claiming the task is still running. It may belong to another process; inspect that process
or the remote service using an existing job ID. Never resubmit an uncertain scientific job blindly.

Stopping a local subagent is not proof that an already submitted remote job was cancelled.

Paths are resolved from the active SCI home, including custom homes:

```text
<active SCI_HOME>/subagents/<name>.json       # reviewed definitions
<active SCI_HOME>/subagent-runs/<run-id>.json # private result receipts
<active SCI_HOME>/cache/delegation/...       # existing delegation transcripts
<active SCI_HOME>/state.db                  # existing session history
```

Definitions use atomic, conflict-checked saves. They are local user state, not bundled into another
user's clone. The feature code lives in the repository and is shared by the installed launcher;
there is no second specialist plugin copy to keep synchronized.

## Implementation and verification

- Storage: `agent/specialist_store.py`.
- Definition snapshots, child setup and named delegation: `agent/specialist_runtime.py`.
- Runtime permissions: `agent/specialist_policy.py` and existing dispatch boundaries.
- Run receipts: `agent/specialist_runs.py`.
- CLI management and editor: `sci_cli/specialist_commands.py`, `sci_cli/specialist_wizard.py`.
- Existing child runtime: `tools/delegate_tool*.py`; no separate agent engine.

Targeted tests cover main/A/B isolation, copying and destination review, competing edits,
case-insensitive commands, cancellation, manual requests, stale definitions, tool filtering and
execution denial, profile-scoped service credentials, read-only skill loading, nested restrictions,
runtime limits, and the existing delegation lifecycle. A loopback HTTP/SSE model fixture exercises
real child construction, the provider adapter, completion, saved receipts/transcripts, and unchanged
parent prompt/tool state. No production scientific jobs or paid model requests are needed.

The setup/management interface is currently the interactive Python CLI (including a desktop's
terminal). A dedicated desktop/web specialist editor, per-specialist model overrides, persistent
specialist memory, cross-profile task routing and restart-resumable execution are not implemented
by this change.

## Verification record — 27 October 2026

The implementation is in `/home/boltzmann20/storage2/Perception_agent` on the development
machine. The installed `agent-sci` launcher routes through the same checkout. Bootstrap import
checks confirmed that specialist storage, runtime and CLI modules load from that checkout;
there is no separately installed specialist plugin requiring a second update. Restart a running
CLI to load the new Python code. After creating or changing a definition, use `/new` as shown above.

In the interactive classic CLI, `/new` starts a fresh runtime for the active profile so saved
tool/configuration changes and updated Python code are loaded together. The departing conversation
remains saved, and its cached prompt is not rewritten. Detached work is not resubmitted.
Opening another terminal can reconnect to an existing background worker rather than restart it.
When Python source files have changed since that worker started, attachment offers **Reload saved
conversation with updated code** or **Keep existing runtime**. Reload uses the existing reviewed
close/resume flow: it warns about local work, waits for the previous writer to exit, and resumes
saved history without replaying the last request. Submitted remote jobs may continue independently.

Completed checks using `scripts/run_tests.sh`:

- 108 tests passed across the specialist feature, CLI registration, system-prompt,
  diagnostic and timeout suites.
- After the nested-budget refinement, 19 budget, integration and real-child tests passed.
  Some overlap the preceding set; these are separate run counts, not an additive total.
- The existing general delegation file passed all 69 tests. Its database assertion was corrected
  to compare file identity, because the registry canonicalizes paths and this machine's test
  directory is a symlink. The production database-resolution behavior was unchanged.
- The existing orphan-completion recovery file passed all 12 tests.
- Python compilation, Ruff's `F` checks on the new implementation modules, and
  `git diff --check` passed.

The controlled walkthrough used the real CLI modal adapter for creation, then exercised cancel,
copy, destination review, explicit assignment, status and disabling with temporary profile homes.
The HTTP/SSE canary used a loopback fixture, real child construction and the existing provider
adapter. It verified result persistence, retained transcripts, parent prompt/tool stability,
resumed definition snapshots and revocation. No production scientific experiment was submitted.
Individual remote MCP/plugin backends were not certified by these fixture tests.

**Broader regression verification is not fully clean.** `test_async_delegation.py` and
`test_delegate_capacity_interrupt.py` exceeded the 240-second file limit in the wider run.
An isolated existing activity-age assertion also failed (30.4 seconds against a maximum of 20).
Worker observations and timeout stacks showed database-write/schema waits. The existing
`test_iteration_budget_warning.py` exceeded a 180-second file limit in another run.
These results are recorded as unresolved wider-suite timing/SQLite checks, not waived or counted
as passes. The feature's completion canary uses a longer fixture timeout; its separate deadline
test checks expiration directly, without relying on filesystem speed. No production timeout was
raised to make tests pass.

No commit or push was performed for this feature. Full release certification still requires
clearing the wider-suite failures/timeouts above and validating any production integrations
that will be used by specialists.

## UX revision and verification — 28 October 2026

The reported creation/editing problems are addressed by module-level Boltzmann instruction choices,
one complete job-tool package, explicit-plus-automatic use, a shorter review flow, recoverable
reference/name errors, profile-local in-memory drafts, and portable definition export/import.
Unavailable selected tools no longer prevent unrelated informational assignments. Existing tool,
credential and workflow checks still deny unavailable operations.

Verification through `scripts/run_tests.sh`:

- **139 tests passed across 10 files**, including the general delegation and command suites.
- After preserving missing/renamed module references in the picker, **6 focused tests passed**
  across three files. These overlap the preceding run and are not an additional unique total.
- A real child with unavailable `browser_back` completed a harmless arithmetic assignment through
  a loopback HTTP model fixture, with no browser schema granted. Parent prompt/tools stayed stable.
- Real temporary profile homes A → B → A demonstrated that a Boltzmann credential plus local
  authorization receipt in A does not grant the package in B. No live credential check or research
  job was sent; production handlers retain their independent service checks.
- Selected skill module content was preloaded without reading an unselected module or running
  preprocessing/setup. A disabled base skill could not be reintroduced through module choices.
- Controlled CLI flows covered invalid paths, `none`, blank edits, cancellation with retained
  references, resuming drafts, export/import, destination review and duplicate protection.
- Ruff `F` checks and `git diff --check` passed.

The installed launcher's committed dependency environment successfully imported the changed runtime,
commands and capability selector from this checkout. An initial probe with an empty temporary
runtime failed to locate dependencies; checking the actual installed dependency environment resolved
that diagnostic discrepancy. No installed-runtime repair was required.

No production scientific jobs were submitted, and no commit or push was performed. This focused
regression run does not certify every external backend or supersede the unrelated wider-suite
checks recorded above. Restart the CLI to load the changed code; then review existing specialists
and use `/new` before assigning work with their updated definitions.

## Combined regression verification — 29 October 2026

The previously reported delegation timing failures are resolved in the test fixtures:
first-open SQLite setup occurs before cancellation deadlines, activity age is checked against
the actual sample time, and asynchronous workers finish before the next test changes profile
scope. The terminal handoff fixture also supplies the current worker identity and isolates the
separately tested runtime-refresh operation. Production timeouts and persistence were unchanged.

Specialist definitions and run receipts now accept Unicode and BOM-prefixed JSON written by
external editors. Regression checks cover definition loading across main → A → B → A and
completing a saved run receipt without losing its original context.

The final combined run used `scripts/run_tests.sh` with retries disabled:

- **715 passed, 0 failed, 2 skipped across 47 Python test files**, including background chat,
  runtime reload, profile isolation, real-child specialists, general/async delegation,
  cancellation, iteration budgets, and Boltzmann authorization/schema checks.
- The unchanged frontend batch passed **352 web tests**, **1,613 TUI tests**, and
  **198 targeted desktop tests**. Web, TUI and desktop typechecks passed. Existing lint
  warnings remain; these checks do not constitute a complete native-installer certification.
- Ruff, Windows portability lint, shell shebangs, config-writer checks, OS-marker checks,
  generated command/gateway contracts, Boltzmann documentation synchronization, and
  `git diff --check` passed.

This run supersedes the unresolved timing results above for the three named delegation/budget
files. It is a targeted regression run, not the entire repository suite or a native Windows/macOS
execution run. No production scientific jobs were submitted.

The development machine's installed Boltzmann code and documentation were synchronized with
the repository, with a recoverable code backup. Credentials, authorization state, and configuration
files remained byte-identical. An isolated import check verified complete connector schemas and
that an unauthorized temporary profile stays locked, without a service request.

## Delegation defaults — 29 October 2026

The native science-profile baseline now includes `delegation`. Config migration v50 enables it
once for existing CLI configurations, including unstamped wizard-created profiles, and removes an
old delegation-only global exclusion while preserving unrelated exclusions. Later intentional
opt-outs remain effective. Main's existing `sci-cli` composite already includes delegation.

Verification: 33 tests passed across nine files using `scripts/run_tests.sh`, covering new native
profiles, real tool-schema resolution, versioned/unversioned migration, A → B → A isolation,
later opt-out, legacy restricted boundaries, real child execution and migration regressions.
The local `test-del` configuration was repaired with a private backup; all 14 local main/native
profiles resolved delegation. Nine legacy restricted profiles were preserved without conversion.
Restart the CLI and use `/new` to obtain a fresh tool snapshot. No commit or push was performed.

## Instruction/source loading fixes — 4 November 2026

The CLI now accepts a bare Markdown/text path for purpose or additional instructions. It loads
and reviews complete instructions during setup and stores their contents with a routing summary.
Reference files, supported folder contents and guarded public URLs are saved as bounded text
snapshots, then supplied as source data before inference. File reading/search are included from
available parent/profile grants. Existing path-only definitions load before inference without
rewriting a live parent prompt; review/save once to persist their snapshots.

Delegation hints now preserve a named specialist's workflow/report format rather than adding
conflicting terminal or output-format requirements. Short, single-sentence promises of future
work with zero tool activity are conservatively marked `failed / incomplete_response`, preserving
raw output. This narrow check is not a general semantic correctness verifier. The runtime does not
silently retry or replace such a child. Receipts identify its assigned model/provider and explain
that parent model switches affect new assignments rather than already-running children.

Verification through `scripts/run_tests.sh`: 87 tests passed across nine files, including 69 general
delegation tests. After final legacy-loading and receipt checks, an overlapping 18-test focused
recheck passed across eight files. Controlled tests covered path-only creation, recoverable missing
files, source snapshots, empty folder files, guarded URL extraction, size limits, copying without
private references, main → A → B → A isolation, and unchanged parent prompt/tool state. A real
child used the existing provider adapter against loopback HTTP/SSE responses: its first request
contained reviewed instruction/reference text even after original files were deleted. A separate
fixture response containing only a plan was reported incomplete, with one request and no retry.
No production model endpoint or scientific service was contacted. Ruff F checks and diff whitespace
checks passed. External provider reachability and arbitrary model instruction-following are not
certified by fixture tests. No commit or push was performed.

## Preserve specialist reports — 4 November 2026

For a report-only assignment, when a saved specialist completes in the interactive CLI, its original report is delivered directly
through the normal response/persistence path, without a parent-model rewriting call. Its requested
headings, protocol markers, tables and wording survive. Completed batches consisting entirely of
saved specialists with final delivery show each full report separately. Intermediate reviews
return control to the parent as described above. A pod lead still finishes its own assignment;
ordinary temporary delegation retains its synthesis behavior. A later explicit user request can
ask SCI to summarize or reformat an already delivered report.

Full output is recovered from the owning profile's run receipt if the model-facing delegation
summary was shortened for context limits. Missing full output, failures and truncated work are
identified as incomplete rather than silently presented as a complete report. Response-rewriting
hooks are skipped for these already-final reports. Transcript persistence and prompt caching
continue through the existing turn finalizer.

Read-only specialists use inline data directly and cannot discover neighboring fixtures from the
instruction file's location. Reading/search dispatch validates task/reference paths, including
normalized traversal and scope boundaries. Explicit execution/service permissions retain backend
access for generated artifacts; this is not a new filesystem sandbox. Saved instructions and
expected output remain the specialist's reporting contract; parent delegation hints forbid adding
unnecessary calculation-tool requirements or independently redoing completed specialist work.

Verification for report preservation: 49 delivery/finalization/notification tests and 83
specialist/general-delegation regression tests passed across 18 distinct files using
`scripts/run_tests.sh`. After refining the read-only boundary, an overlapping 12-test final
recheck passed. The loopback model canary exercised the real child runtime, production CLI
notification carrier/staging and parent turn finalizer: delivery made zero parent inference
requests, and the returned/persisted assistant report exactly matched the child's saved text.
Long-report tests recovered complete text across summary trimming and profile A → B → A;
ordinary/nested delegation and turn ownership retained their existing behavior. Scope tests
covered inline-only denial, explicit file access, adjacent-file/search denial and selected-folder
access. Execution workflows retained generated-artifact access. Prompt/tool snapshots remained
unchanged. No production provider or scientific service was contacted. Ruff F and whitespace
checks passed. No commit or push was performed. Restart/reload the CLI worker and start `/new`
before retesting; existing conversations keep their cached setup.

## Code references, source libraries and execution defaults — 4 November 2026

References now accept common code formats, including Python, alongside the existing text/data
formats. Each addition appends; updates preserve earlier files/folders/URLs. The reference menu
supports removing one source, clearing all, and refreshing saved versions. Folder inspection
reports skipped unsupported/hidden files. Inspection never imports or executes source code.

Small sources remain preloaded. Larger collections use immutable private snapshots and a complete
catalog under the owning profile's `subagent-sources/`, outside the definition and model prompt.
Read/search can retrieve relevant documents through the existing tool dispatch. Limits are
8 MiB per file/download, 10,000 folder entries/documents and 256 MiB saved collection text.
Instruction and definition-size bounds remain. Copy/export strips the source library and private
references; destination review is still required. Retained snapshots support existing conversations.
The library participates in the existing backend mount/sync and agent-visible path mapping.

New native science profiles now include code execution in addition to file/terminal/skills/delegation.
Config migration v51 upgrades existing native/main CLI lists once and removes old exclusions for
those baseline toolsets, preserving unrelated settings and later deliberate opt-outs. New
specialists receive available read/search/write/patch, terminal, Python and process tools in final
review. Existing specialists keep their selections; Use standard tools adds defaults through review
and explicit save. Research services retain their key/authorization checks. Legacy restricted
profiles retain isolation and are not silently converted. Project-specific libraries are not
installed automatically; an unavailable runtime/dependency must be reported honestly.

Verification using scripts/run_tests.sh:
- 74 tests passed across 12 files, covering source management, real Python execution, new/native
  profile creation, A→B→A scope, configuration migration, child execution and cache mounts.
- An overlapping 22-test migration/library run and a 12-test capability/permission recheck passed.
- After adding real snapshot retrieval through the production read_file dispatch, both library
  tests passed again. The fixture .py file did not run on import/inspection; explicit execute_code
  ran it in the real kernel, returned RESULT 42 and produced its expected local artifact.
- Large-reference tests verified bounded context, append without replacement, source removal,
  refresh, duplicate protection, guarded URL loading, skipped binaries, profile-copy stripping,
  profile ownership, snapshot integrity and backend path mapping.
- Installed-runtime import checks loaded the changed modules from this checkout and confirmed
  Python-execution prerequisites available. Ruff F and whitespace checks passed.

On this machine, all 15 main/native profile tool schemas were checked. Fourteen configurations
needed the code-execution baseline update and have private backups under
/home/boltzmann20/.sci/backups/specialist-tool-defaults-20261104T100150052004.
Nine legacy restricted profiles were preserved. No scientific jobs, production model requests or
arbitrary dependency installs were used for testing. Remote path/mount contracts were tested;
this does not certify a live Docker/SSH/cloud backend or every third-party package. Restart/reload
SCI and use /new. For an existing specialist, review Use standard tools, save, then start /new.
No commit or push was performed.

## Retained-install reconciliation and blocked outcomes — 5 November 2026

Private setup accepts overlap with inherited **standard** tools such as terminal/process management.
The definition records shared ownership, so copying/exporting or removing private access does not
accidentally remove an inherited standard grant. Genuine skill or nonstandard-tool name collisions
remain reported; they do not discard unrelated installed additions. Private file/code/process work
uses the private backend's terminal policy and workspace, while inherited service handlers retain
the owning profile's credentials.

If setup stops after installation, the recoverable draft retains discovered additions. To recover
an older incomplete save without reinstalling:

```text
/Update_subagent <name>
```

Choose **Review installed private additions**, inspect the candidate skills/tools, then **Save and
enable for the next conversation** and `/new`. Recovery reads local metadata and does not download,
install, run the program or probe an MCP. If installed plugin tools need discovery, loading their
code requires a separate explicit choice. Cancelling review leaves saved grants unchanged.

A model response finishing successfully does not mean its assigned work completed. An explicit
`Outcome: BLOCKED BEFORE EXECUTION`, incomplete/failed outcome header, or JSON `task_outcome` is
recorded as failed with its specific task outcome. Run-history views also interpret those explicit
headers in older receipts without silently rewriting the retained evidence. The raw report and
stored tool activity remain intact. Subagents receive the authoritative runtime `sa-…` identifier;
blocked-report delivery shows it separately from any model-written report/file label.


Controlled verification covers private skill/MCP/plugin discovery, child execution, A → B → A
profile isolation, cancelled review, retained installation recovery, standard-tool overlaps,
blocked receipts and unchanged parent prompts/tool schemas. Tests use temporary homes and
loopback services; no production scientific jobs are submitted. These checks do not certify
arbitrary third-party installations or scientific correctness.

## Portable packages and company contributions

For complete skill/resource/dependency sharing, use `/subagent package` and
`/subagent catalog`. This is separate from definition-only JSON export/import.
See [Portable specialist packages](subagent-packages.md) for setup, recipient keys,
profile-independent PR contributions, clean-install verification and reviewed updates.
