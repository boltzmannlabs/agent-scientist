# Report file delivery for every formulation run

Use this protocol after a run produces recipes, simulations, a design study,
optimization iterations or cost comparisons. File creation is authorized as part
of the run; do not ask whether a report is wanted. Use the existing `terminal`
and file tools, and the current profile's output/artifact directory.

## Contents and format

Read `references/report-template.md`. Compose the full narrative from the exact
saved records for THIS execution batch, not every historical result in the project.
Record project, recipe revisions, run/study IDs and any earlier baseline records
used. A report needs an explicit objective outcome, all-result summary,
interpretation, applicable comparisons, recommendation, gaps and validation plan.
A list of raw outputs or a ZIP alone is not the report.

Default: a professional PDF plus a complete `.md` companion containing the same
conclusions and evidence. If the user explicitly requests Markdown only, that
file satisfies delivery. For DOCX use an available document-generation capability
and verify the result is a genuine Word document; never rename Markdown as DOCX.
Do not add an extra format-selection question. If a requested converter is absent
or export fails, deliver the complete Markdown file immediately, disclose the
format limitation and preserve results. Never silently substitute HTML or claim
an uncreated PDF/DOCX exists. Do not install new dependencies just to format a run.

## Existing package export

Discover the current `project/export` schema before calling it. The current
package request is:

```json
{"operation":"project","action":"export","project_id":"ACTUAL_PROJECT_ID","payload":{}}
```

Use actual saved IDs. Read the response's artifact metadata and verify the PDF
file exists, is nonempty and has a PDF signature. The ZIP contains supporting data
but does not replace the readable report. Inspect the PDF content; a native
project export may cover historical work or omit the agent's objective assessment,
interpretation or decision ledger. Do not describe it as the complete run report
unless that content is present. Supply the complete Markdown companion with exact
run scope and all required sections; label any broader PDF as a project export.
If a configured renderer can produce the full narrative PDF, use it and verify
its text/tables. Keep both artifacts traceable to the same saved run records.

## Completion check

- Every evaluation in the run is covered, including partial results and omissions.
- Objective outcome states the numerical support and unresolved objectives.
- Comparison tables use matched units, recipe identities and conditions; no
  baseline or cost evidence means explicitly not available, not a made-up value.
- Predicted objective achievement remains separate from experimental confirmation.
- Output names identify the project and execution batch and do not overwrite a
  previous run report. Verify readable UTF-8 text for Markdown, PDF content for
  PDF, or document XML/content for DOCX, as applicable.
- Present the Run Summary and specified results in chat, followed by readable
  report links using the artifact mechanism supported by the current UI. If only
  filesystem links are supported, say files are saved on the server rather than
  claiming they were attached. Do not expose source code or scratch file paths.
- For recipe-only output, deliver its report and still present the required mode
  selector. No pending selector or cancellation grants permission for extra runs.
