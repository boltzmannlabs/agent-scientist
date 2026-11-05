# Agent Scientist — Subagents

Quick user guide

A subagent is a reusable specialist with its own purpose, instructions, selected capabilities and expected output. Examples: a data reviewer, literature reviewer or FASTA quality reviewer.

### 1. Choose main or a project profile

You can create specialists directly in main or inside any profile. To change profile, type /activate and use the picker. Definitions and credentials belong to their owning main/profile; another profile does not automatically receive them.

### 2. Create your specialist

```text
/Create_subagent
```

1. Enter a unique name, such as demo-quality-auditor.
2. Describe its purpose and when it should be used. You may provide an instruction Markdown file path instead; its contents are saved.
3. Select relevant skills or scientific modules. Use Search, then Done. Choose only what the specialist needs.
4. Review tools and integration packages. Available standard file, terminal, Python and process tools are included for new specialists; actual availability still depends on setup.
5. Specify the expected output. Add optional instructions or references from the final review.
6. Choose Save and enable for the next conversation, then type /new.

Search selectors support Select all/Clear selection. During a search, Select matching/Clear matching affect the filtered results.

### 3. Assign work

```text
/subagent run demo-quality-auditor <your task>
```

Or type /subagent run demo-quality-auditor without a task to be prompted. You can also ask naturally: “Ask demo-quality-auditor to review this file.”

New specialists support explicit requests and automatic matching. Automatic selection is model-driven; the explicit run command selects the named specialist. Queued means the assignment was handed to the agent, not that a scientific job has already run.

---

## Skills, tools and references

### 4. Select existing capabilities or add private ones

Edit skills/tools selects capabilities already available to the owning main/profile. A skill supplies instructions; tool permissions and credentials determine what can actually execute.

For Boltzmann, choose the relevant scientific modules and the Boltzmann job tools package. Its upload, submit, status, download and diagnostic operations are included together. Execution still requires valid authorization in the applicable scope.

From final review, Add for this subagent only offers:

| Option | Use it when… |
| --- | --- |
| Add tool (link or request) | You want agent-assisted setup from a tool request, repository link or path, like /Add_tool. Review the model/request and action approvals. |
| External skill | You have a prepared SKILL.md, complete skill folder/ZIP or supported source URL. Supporting files are preserved. |
| MCP service | You have an MCP endpoint or JSON/YAML connection configuration. Configure credentials, approve discovery and select tools. |
| Use an already-installed program | The executable/script already exists. Supply its interpreter, arguments, working directory, inputs, outputs and limitations. SCI saves invocation instructions. |

Private additions are scoped to that specialist. They are not automatically exposed to main or sibling specialists. Approved terminal programs and plugin/MCP code retain their backend’s host access; private configuration is not an operating-system sandbox.

Existing specialists can use Use standard tools to add available standard capabilities for review. Missing dependencies, permissions or authentication must be resolved before the affected execution can work.

### 5. Add reference material

Choose References → Add file/folder/URL. Add entries one at a time; they append. You can remove individual references, refresh saved contents or clear the collection.

Supported readable documents, code and data are saved as reference snapshots. Small collections are provided to the selected model; large collections are read on demand. Adding code does not execute it. Refresh when you want updated source contents.

Use public HTTPS links without embedded credentials. Do not put passwords, API keys or unapproved private data into instructions or references. Model access to reference text is separate from authorization to upload it to a research service.

---

## Manage specialists and their runs

### 6. Browse and update

```text
/subagents
/Update_subagent
```

Use the picker to choose a specialist. Editing opens its review. Change purpose/output, skills/tools, instructions or references, then save and start /new. Blank purpose/output edits preserve the current value.

For reference entries, none, skip or blank skips the entry. Invalid paths ask again. Cancelled drafts remain in the current CLI/profile and can be resumed; unfinished drafts do not survive restarting the CLI.

### 7. Useful commands

| Command | What it does |
| --- | --- |
| `/subagent show <name>` | Show saved instructions, grants and review state. |
| `/subagent status [run-id]` | Show recent runs, or a specific result/error and transcript location. |
| `/subagent history [page]` | Browse retained run receipts. |
| `/agents` | Open the existing live-agent monitoring interface. |
| `/subagent stop <run-id>` | Request cancellation of a live run owned by this conversation. |
| `/subagent steer <run-id> <message>` | Send a correction to an owned live run. |
| `/subagent disable <name>` | Prevent new assignments; does not silently stop current work. |
| `/subagent enable <name>` | Review before enabling the specialist. |
| `/subagent delete <name>` | Confirm deletion of the definition; retained run history remains. |

Use the runtime sa-… run ID from status/receipts. A filename or model-written report label may be a different identifier. A blocked task can be recorded as failed with task outcome blocked. Stopping the subagent does not prove a submitted remote job was cancelled.

### 8. Copy, duplicate and recover

In /subagents, select a specialist, then Copy to profile to choose a destination, or Duplicate to enter a new name in the current profile. Copies are disabled until reviewed in the destination; use /Update_subagent, save and /new.

Definition-only sharing is also available through `/subagent export <name> "<file.json>"` and `/subagent import "<file.json>"`. It excludes private integrations, credentials, references and history; configure those separately at the destination.

If installation succeeded but grants are missing, choose Review installed private additions, review, save and /new. Do not reinstall solely because a skill is unauthorized. If “Private capabilities changed” repeatedly appears without intentional changes, stop and report it to maintainers rather than entering a reinstall loop.

---

## Demo: audit a measurement CSV

This demonstration uses synthetic data, file reading and supplied rules. It needs no research-service account.

### Step A — prepare the file

Save the following text as measurements.csv in a folder of your choice. Note its full absolute path.

```text
sample_id,value
A1,10
A2,20
A2,
A4,-1
A5,30
```

### Step B — create the specialist

```text
/Create_subagent demo-quality-auditor
```

Purpose: Audit supplied measurement CSV files using only the user’s validation rules. Identify every affected record and do not invent replacement values.

Skills: none required for this simple demo; choose Done. Keep file reading available. Expected output: Sources/rules, record counts, issue table, readiness verdict and recommended next actions. Additional instructions: Preserve the input; do not execute scripts, use other datasets or contact external services.

Save and start a fresh conversation:

```text
/new
```

### Step C — run the audit

Replace /absolute/path/measurements.csv below with your actual file path. Keep paths containing spaces quoted.

```text
/subagent run demo-quality-auditor Audit /absolute/path/measurements.csv. Rules: sample_id is required and unique; value is required, numeric and between 0 and 100 inclusive. Number data records from 1 after the header. Flag every occurrence of duplicate IDs. Count each affected record once even if it has several issues. Preserve the input; do not run scripts or use other datasets. Return counts, an issue table, a readiness verdict and next actions.
```

### Expected checks

- Total data records: 5, excluding the header.
- Distinct affected records: 3 — records 2, 3 and 4.
- Records without identified violations: 2 — records 1 and 5.
- Both A2 records are duplicates; record 3 also lacks a value; record 4 has an out-of-range value (-1).

Inspect the recorded result with /subagent status, then `/subagent status <returned-run-id>`. For a later automatic-matching demonstration, ask SCI to audit another supplied measurement CSV with explicit rules.
