# Boltzmann definitions and execution

There are three runtime definition files under `skills/boltzmann-tools/references/`:

| File | Owns |
|---|---|
| `tool-contracts.v1.json` | Exact jobs, descriptions, payload fields/types, requiredness, input modes, examples and diagnostic mappings |
| `file-input-contracts.v1.json` | Additional checks for specific file inputs: formats, CSV layouts, archive contents |
| `input-limits.v1.json` | Documented bounds and relationships, not duplicate field types or requiredness |

The catalog's `schema_version` identifies the internal format. Filenames remain
stable so existing skill references resolve. In format 2, each request property
owns its `x-input-kind`: `value`, `file`, `file_or_value`, or `artifact`.
There is no separately maintained upload allowlist. File and limit records are
sparse: an absent record means no additional documented rule, not an unavailable
tool. Nothing may invent missing scientific requirements or service identifiers.

## One execution path

1. Read the selected job's generated module and collect required user values.
2. For a local file, `boltzmann_upload` resolves the field from that request
   schema, checks a private snapshot and uploads those exact bytes.
3. Insert the returned platform reference unchanged into the declared field.
   Inline values and already-authorized upstream artifacts use their documented
   modes; they do not require a fictitious local upload.
4. `boltzmann_submit` checks the request and applicable rules and submits once.
5. Poll the returned job identity, retain every artifact link and download the
   requested outputs. Report actual service status/errors, never fabricated success.

`contracts.py` owns request checks, `file_validation.py` owns bounded non-executing
file inspection, and `preflight.py` ties inspected bytes to profile-scoped upload
receipts. This separation does not create additional sources of tool definitions.
Receipts contain hashes, not credentials. Documentation-only changes do not
invalidate them; changed validation rules or dependent input values do.

CSV, FASTA, PDB, XYZ and SDF have basic syntax checks; ZIPs receive integrity and
security checks. These checks do not establish scientific correctness. Known
invalid inputs stop with a concrete error. Unimplemented specialized checks are
disclosed and can proceed after explicit approval, using the existing
`allow_partial_validation` flag. Missing specialized checks alone do not cause
a blanket missing-contract refusal. The flag never overrides authorization,
profile permissions, unsafe archives or unsupported serialized executable inputs.

The validator implements only the schema vocabulary used and tested here:
types, properties, required, enums/constants, additionalProperties/propertyNames,
items, array length/uniqueness, string length/pattern, property count, numeric bounds,
anyOf/oneOf/allOf, conditional if/then/else/not, plus documented `x-*` annotations.
The five enzyme-tool addition also checks RFD3 cross-field relationships and
uploaded JSON template/binding/mapping/threshold shapes. Structure chemistry,
contig parsing and native diffusion scheduling still require explicit review.
Do not add unsupported
JSON Schema keywords and imply they are enforced. Threshold numeric strings and
explicitly permitted empty bounds are separate cases, not silent conversions.

## Enzyme CSV headers and credit-calculation errors

For `Enzymes`, prepare CSV files with exact `Seq_id,Sequences` headers, matching
the frontend's `ENZ_PROP` credit checker. `Sequence_ID` is not a supported alias.
The connector rejects incompatible headers before upload and reports the expected
columns. Best-effort approval does not bypass a known header error. If an existing
input needs conversion, create a separately reviewed copy without changing its
sequences or overwriting the original. The canonical file rule and generated
workflow sheet provide the same guidance.

HTTP 500 with `Failed to calculate credits` is a submission-stage service error,
not evidence of missing credentials, a DNS failure, or an insufficient balance.
Preserve the server's diagnostic and distinguish it from local input validation.
Without a returned job ID, report submission outcome as unknown; do not resubmit
automatically, fabricate a credit amount, or bypass `/api/submit-job` through the
browser's private submission flow. Reconcile the previous experiment before a
retry, or obtain explicit approval for a separately named new test. Acceptance
does not establish completed predictions or the actual credit charge.

## Maintenance and verification

Module Markdown is generated, never independently edited:

```bash
python plugins/boltzmann/contract_docs.py --write
python plugins/boltzmann/contract_docs.py --check
scripts/run_tests.sh tests/plugins/test_boltzmann_standardization.py tests/plugins/test_boltzmann_contract_validation.py tests/plugins/test_boltzmann_authorization.py tests/plugins/test_boltzmann_mcp_contract.py tests/plugins/test_boltzmann_distribution.py
```

Developer evidence is retained in `contract_sources/`, outside active skill
knowledge. It is historical evidence, not a second runtime catalog. See
`READINESS_AUDIT.md` for the current verification boundary and full inventory.

`contract_sources/diagnostic-collections.csv` preserves explicit job-to-collection
evidence recovered from the maintained `tool-outcome-collections.csv`; sample
document IDs and machine-specific paths are intentionally excluded. Its mappings
are incorporated into canonical `diagnostics`, not loaded as another runtime
registry. `ContractStore.diagnostic_collection()` resolves exact-job `matched`
or `source_documented` records only and rejects missing or conflicting mappings.
Historical evidence does not establish present service availability.

The diagnostic helper accepts `job_name` and `experiment_id`, preserving legacy
explicit `collection` calls. If both job and collection are supplied, they must
agree. Normal status polling still uses the original job name and document ID;
diagnostic-resolution failure neither blocks polling nor implies job failure.

Native and MCP interfaces share the same handlers. Status always refreshes from
the service rather than reusing terminal responses with expired signed links.
Downloads preserve same-named artifacts instead of overwriting earlier files.
Neither status nor downloading resubmits a job. Ambiguous submission outcomes
must retain uncertainty and must not be retried automatically.

## Rollout

Test the repository first. Back up and update installed plugin code and generated
knowledge while preserving config, credentials and profile state. Profile plugin
links may share code, but authorization and receipts remain profile-scoped.
Start a fresh process/conversation to load changed schemas and instructions;
do not reload a running conversation's cached prompt.
