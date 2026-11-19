# Specialist hierarchy contribution example

To contribute a lead and two children, copy this starter into three sibling folders:

```text
subagent-catalog/
  table-team/
  table-reader/
  table-reviewer/
```

Give each manifest and `tests/validation.json` its own matching package ID/version.
Each child keeps its own instructions, tools, skills and required integrations.
Use `automatic: false` for children that should only run through approved parent
delegation or explicit user requests.
For `table-team`, set schema version 2 and merge these fields into its manifest:

```yaml
schema_version: 2
id: table-team
name: table-team
tools: [delegate_task]
children:
  - role: reader
    package: table-reader
    version: '>=1.0.0,<2.0.0'
  - role: reviewer
    package: table-reviewer
    version: '>=1.0.0,<2.0.0'
limits:
  max_iterations: 30
  timeout_seconds: 0
```

Example parent instructions:

```text
Assign the supplied CSV to {{child.reader}} to report rows, columns and missing cells.
Then give that report and the original input to {{child.reviewer}} for independent checking.
Use the exact returned artifact paths when passing generated files.
Collect both reports and deliver the requested findings. Preserve the input unchanged.
Report concrete missing work; do not substitute your own work for a required child.
```

Adapt the reader's instructions to count the supplied synthetic table, and the
reviewer's instructions to check those counts against that same input. The starter
CSV has three data rows, one empty value and one repeated row. Define each child's
observable output and the parent's combined expected output accordingly. Fill the
validation records only after actually exercising this installed team.

Install the local parent folder with the normal package installer; sibling folder
names must match their package IDs. A recipient may rename the parent, and SCI binds
the child tokens to actual local names. No separate child naming/setup commands are
needed. Submit all new packages and required version changes through the same PR to
dev. Test the merged dev team, then record its exact tested commit before promotion.
