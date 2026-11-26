# transcriptomics

Portable standalone specialist for supplied bulk RNA-seq, single-cell RNA-seq,
and spatial transcriptomics assignments. Version `1.0.0` has passed the included
synthetic CSV fixture checks in a fresh profile. Broader scientific workflows and
their recipient-provided dependency requirements remain unverified.

## Purpose and limits

The specialist follows each assignment's required inputs, methods, output names,
schemas, and constraints. Its instructions emphasize inspecting the supplied data,
choosing methods from the actual experimental design, reporting uncertainty, and
checking output files against the report. It does not include a parent/child
hierarchy, private skill, dataset, credential, or service connection.

## Tools and setup

The manifest requests SCI's `execute_code`, `read_file`, `search_files`, `terminal`,
`write_file`, and `patch` tools and a recipient-provided Python 3.12+ interpreter.
The saved profile's tool list also contained `process_manage`; it is omitted from
this package because the portable task instructions do not require managing
long-running processes. Test whether the retained tools are sufficient for the
actual workflows before contribution.

Real transcriptomics tasks can require libraries such as AnnData/Scanpy, SciPy,
Pandas, plotting libraries, or a count-model implementation. Which software is
needed depends on the supplied data and requested analysis. This package does not
install those libraries or silently create environments. The recipient must
provide approved software/setup; the specialist must report missing dependencies
and use an alternative only when the assignment permits it. The included fixtures
do not verify those broader workflows. Treat these capabilities as unverified
until required libraries and representative workflows are tested and documented.

Review all file and execution access during installation. Input contents and tool
outputs may be sent to the recipient's configured model provider. The package
does not call scientific services or submit scientific jobs. Model usage may
incur provider charges. No credentials, authorization records, or external data
are included.

## Included fixtures

`tests/sample.csv` and `tests/second.csv` are synthetic long-form count tables
with different cell, condition, and gene totals. The task files specify the
analysis; `tests/expected.json` is a maintainer-side assertion and must not be
provided as model input. Write outputs to a caller-supplied directory, then
compare them with the expected observations. Both tables are intentionally too
small to support cell annotation, clustering, inferential differential
expression, or biological conclusions. Both fixtures were run through the
reviewed installer in a fresh SCI profile; see `tests/validation.json` for actual
run IDs and evidence.

## Installation and test plan

Use the reviewed command in a fresh disposable profile:

```text
/subagent package install <absolute-checkout>/subagent-catalog/transcriptomics --name installed-transcriptomics
/new
/subagent run installed-transcriptomics Follow the task in <absolute-checkout>/subagent-catalog/transcriptomics/tests/task-sample.md. Use its adjacent sample.csv and write outputs to <absolute-output-directory>.
/new
/subagent run installed-transcriptomics Follow the task in <absolute-checkout>/subagent-catalog/transcriptomics/tests/task-second.md. Use its adjacent second.csv and write outputs to <absolute-output-directory>.
```

Inspect the actual output files and compare their contents with
`tests/expected.json`. These two fixtures check descriptive table handling only;
they do not establish broad support for other analysis types. Record the SCI
revision, operating system, backend, model/provider, setup, outputs, failures,
costs, and untested cases in `tests/validation.json`. Historical runs of the saved
specialist remain supporting evidence and do not replace package fixture tests.

## Provenance, author, and license

The instructions were adapted from the saved `transcriptomics` definition in the
`agent_testing` profile. The synthetic test fixtures were created for this
package. The selected license is MIT; see [LICENSE](LICENSE). Contributor
attribution: Saneeya Kalangutkar. No profile paths, run logs, private datasets,
secrets, or saved definition JSON are packaged.
