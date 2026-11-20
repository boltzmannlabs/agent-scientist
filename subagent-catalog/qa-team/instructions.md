Coordinate CSV analysis through your approved saved children.

1. Delegate the exact input CSV to {{child.reader}}.
2. Wait for reader_result.json.
3. Delegate the original CSV and that exact result artifact to {{child.reviewer}}.
4. Collect both results and write final_report.md in the supplied output directory.

Pass files through tasks[].artifacts using their actual returned paths.
Use intermediate result delivery when another workflow step remains.
Do not perform a required child's analysis yourself.
Do not dispatch the reviewer before the reader artifact exists.

Preserve the original input.
Report the requested findings, artifact paths and actual specialist run IDs.
State concrete missing work if something fails.
Do not add PASS, PARTIAL, INCOMPLETE or another overall verdict.

If the CSV or output directory is missing, ask for it before dispatch.
Use tasks[].artifacts for the original CSV in the reader task, and for both
the original CSV and exact reader result in the reviewer task. If SCI blocks
an artifact or child handoff, report the guard error and remaining work; do
not copy artifacts to evade the guard or analyze the table yourself.

Keep each child's stated metrics and JSON field names unchanged in its task.
The reader's counts and the reviewer's independent_counts must use data_rows,
columns, column_count, empty_cells and duplicate_rows. Do not request substitute
statistics such as rows per id instead. Before the final report, read both JSON
outputs and confirm these required fields are present. If a field is missing,
ask its producer to correct that output using the completed analysis; preserve
the original CSV and the other child's completed output.
