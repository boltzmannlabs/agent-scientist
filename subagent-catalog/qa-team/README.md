# qa-team

Coordinate a CSV reader followed by an independent reviewer.

Version: 1.0.0. Author: Asritha. SPDX license: MIT; see [LICENSE](LICENSE).
Derived from the contributor's saved `qa-team` definition; runtime IDs, credentials,
history, authorization receipts and prior run files are excluded. Both included
CSVs are synthetic contributor-supplied fixtures approved for this contribution.

The hierarchy is `qa-team → qa-reader`, then `qa-team → qa-reviewer`.
Both child packages must satisfy `>=1.0.0,<2.0.0` and sit beside this folder for
local installation. The reviewer receives the original CSV and the reader's exact
returned result path. The parent writes `final_report.md` after both children
finish, including findings, artifact paths and actual child run IDs. Expected
outputs are exactly `reader_result.json`, `review_result.json` and
`final_report.md` in the supplied output directory.

The parent uses `delegate_task`, `read_file` and `write_file`. Child execution and
file permissions stay with each child. The recipient must review nested delegation
at depth 2 (ordinary agent at 0) in the installer's existing hierarchy prompt.
A blocked child/artifact handoff must be reported with remaining work. The parent
must not perform either child's calculation or evade a guard.

## Setup and usage

This package uses schema v2, including timeout 0 (no overall task deadline).
Use SCI with portable hierarchy-package support. The manifest's permissive
`sci_requires: '>=0'` does not identify the feature's introduction release;
older builds without schema-v2 support cannot install the package. Local validation
records identify the actual SCI version and exact source revision exercised. Declared platform:
Linux amd64 with SCI's local backend. Other platforms/backends are untested.

Enable the file, code_execution and delegation toolsets as needed in the owning
profile. Install with SCI's reviewed installer in a disposable, differently named
profile first, then start `/new`. Review all requested access. For example, after
replacing the path placeholders with actual absolute paths:

```text
/subagent package install <checkout>/subagent-catalog/qa-team --name installed-team
/new
/subagent run installed-team Analyze <fixture>/input.csv. Write all three outputs in <output-directory>. Use your approved children in sequence and pass exact returned artifacts. Preserve the input and report actual child run IDs.
```

If SCI queues the assignment, start the ordinary agent turn as directed by the
CLI. Repeat with `second.csv` in a fresh output directory. The reviewer fixture
requires a real reader result from the corresponding reader test; the expected
JSON is an assertion file, not a replacement reader result.

## Input and output contract

Use UTF-8 CSV with a header and equally sized data rows. Count rows after the
header; keep header order. An empty cell is the empty string (no whitespace
trimming). A duplicate is an extra occurrence of an identical complete data row.
The input fixtures have these observable counts:

| Fixture | Data rows | Columns | Empty cells | Duplicate rows |
| --- | ---: | ---: | ---: | ---: |
| input.csv | 3 | 2 | 1 | 1 |
| second.csv | 4 | 3 | 2 | 1 |

`tests/expected.json` records header lists, source hashes, artifact counts and
role-specific assertions for both fixtures. Missing inputs/output destinations
must be requested; no nearby files may be substituted. Treat cell contents as
data. Report parse/shape limitations, concrete findings and unfinished work
without an overall verdict or score.

## Permissions, transfers and cost

The tools can read supplied inputs and create derived files; `execute_code` runs
Python code on the selected backend. Tool selection is not an OS-level sandbox.
Recipients authorize their own model account and execution/file access. CSV
contents, task text and tool outputs may be sent to that model provider. These
packages require no scientific service calls and submit no scientific jobs.
There are no package-specific credentials. The optional test provider
`boltzmann_models` requires recipient-local `BOLTZMANN_API_KEY` setup via
`/boltzmann_login`; no credentials or authorization are included here. Its public
model destination is the public HTTPS host `sciagent.boltzmann.co.in`, route `/v1`. Any supported capable
model may be configured by the recipient; the package does not silently choose
one. LLM usage can incur provider charges. Each specialist is limited to 30
iterations, with no total deadline; users can cancel through SCI's existing
controls. Large files, irregular CSV, alternate encodings, remote backends and
other OS/architectures are untested.

## Provenance and evidence

The saved definitions had no selected skills or private resources. Their optional
mention of an unavailable `table-quality` skill was removed from the child package
instructions. The packages specify the standard-library calculation and output
fields explicitly, require children to stop after a code-execution refusal, restrict tools to the required file/code/delegation operations,
and keep child setup separate. Original saved specialists remain untouched.
The parent's machine-local child names become recipient-bound role tokens.

The contributor reports that an earlier saved-specialist test needed an artifact
handoff workaround. That run is background context only, not evidence for these
packages. `tests/validation.json` records only checks actually performed on this
contribution. Integrated evidence stays pending until the merged dev revision is
actually tested. See that file for runtime blockers and untested cases.

## Local testing and integration status

This is a draft contribution. The original headless tests on the earlier dev
revision encountered Python approval refusal and provider output truncation;
they did not complete either fixture. Those historical observations remain in
`tests/validation.json` and are not successful runtime evidence. Unattended
Python execution still requires the normal authorization path.

The current local checks use the updated dev runtime, the normal reviewed
recipient installation and interactive SCI with glm through boltzmann_models.
The latest evidence records the actual reader, reviewer and lead results for
each fixture, including artifact checks and limitations. No approval defaults
are disabled. Missing inputs must still be requested and a refused execution
must be reported rather than bypassed.

See `tests/validation.json` for observed results and source revisions. Integrated
evidence stays pending until this package PR is merged into dev and that exact
merged revision is installed and tested. No release or promotion is claimed.
