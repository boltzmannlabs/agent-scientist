Independently check the exact CSV and reader_result.json supplied by your parent.

Use Python's csv module through execute_code to recalculate the counts.
Compare the recalculated counts and input SHA-256 with the reader's report.

Write review_result.json into the supplied output directory.
Include your independently calculated counts, concrete discrepancies, and
the exact input and reader-result paths checked.

Preserve the input and reader report unchanged.
Do not invent missing artifacts or inspect unrelated files.
Report findings without an overall verdict or score.

Use UTF-8 CSV with a header and Python csv.reader. Report columns as the
ordered header list and column_count as its length. Count data rows after
the header, empty_cells as cells equal to the empty string, and duplicate_rows
as repeated complete data rows beyond their first occurrence. Preserve cell
values without trimming. If parsing fails or rows have a different field count
from the header, report that limitation rather than guessing.
Use the same field names inside independent_counts. Also include
source_path, source_sha256, reader_result_path, reader_result_sha256 and
discrepancies (an array of concrete mismatches, empty when there are none).
If the CSV, reader result or output directory is missing, request it and stop.
Do not create a substitute report or write final_report.md; the parent owns it.

If execute_code is refused or the required Python calculation cannot run,
report the exact blocker and stop. Do not replace it with manual counts,
file-tool calculations, terminal execution, another model/service, or a
configuration change. Never request that a guard be disabled.

Use these exact five keys inside independent_counts: data_rows, columns,
column_count, empty_cells, duplicate_rows. In particular, use data_rows rather
than row_count or total_rows. Before returning, read back your saved JSON and
confirm it includes these fields, the checked paths/hashes and discrepancies.
