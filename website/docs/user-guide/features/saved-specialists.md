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

Terminal and code-execution access require a specific review during setup. These capabilities
can use the configured execution environment: **a specialist tool allowlist is not an OS-level
filesystem or network sandbox**. Filesystem/network isolation still belongs to the profile's
execution backend. Configuration/credential management, skill authoring, memory writes,
scheduling and cross-platform messaging are not specialist grants.

Optional file/folder/HTTPS locations are references only. Saving them does not read, index,
download or upload their contents, nor grant source-specific access. Approve the material to be
used for the particular assignment. Do not put secrets or private sample contents into reusable
instructions. A selected file-reading tool is not restricted to those reference paths.

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
