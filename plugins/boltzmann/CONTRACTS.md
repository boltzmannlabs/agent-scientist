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
The five enzyme tools and opted-in enzyme workflow utilities use lazy Gemmi
structure inspection and RDKit SMILES parsing, plus RFD3 cross-field and uploaded
JSON checks. Gemmi and
RDKit are declared plugin dependencies, installed only through the normal PM
dependency-consent flow; they participate in the shared environment's dependency
union. Discovery does not import them. If unavailable, the exact unchecked
operation is reported, without installing packages or claiming validation.

Structure checks cover models, selected chains/residues/atoms, finite coordinates,
documented backbone/size rules and bounded archive discovery. Catalytic Geometry
joins structure, template, binding and optional JSON mapping inventories from
current-profile upload receipts before submission. Inventories are bounded to
256 KiB per receipt, contain identifiers rather than coordinates, and never
silently truncate into a checked result. Incomplete inspection remains explicit.
Changing validator semantics or relevant selection values invalidates a receipt;
unrelated sampling controls and documentation do not. These checks do not run
inference, evaluate catalytic activity, verify cited evidence, or replace worker
validation. Native contig features, upstream mapping adapters and diffusion
scheduling that are not reproduced locally remain specifically disclosed.

For these five tools, review notes are informational, not unchecked-input warnings.
Other catalog entries retain their existing approval policies. Approval is still
required for actual unverified checks; known invalid input cannot be approved
away. For MolProbity measurement-only requests, preparation removes thresholds
before validation and transport, without mutating the caller's object. Validation
mode still requires nonempty supported thresholds or an inspected JSON upload.
Do not add unsupported
JSON Schema keywords and imply they are enforced. Threshold numeric strings and
explicitly permitted empty bounds are separate cases, not silent conversions.

### Remaining enzyme workflows

The existing CSV parser uses opt-in `semantic_values` with explicit per-column
alphabets, case and whitespace policies, or SMILES checks. Header rules remain
separate. Conditional `semantic_values_by_field` handles Enzymes `substrate_pred`:
that mode also needs a molecule column. `sequence_validation` applies documented
FASTA record/parent/position constraints; MLDE positions must match the supplied
single parent. No full parent sequence is retained in receipts. All normalization
is an inspection view matching the worker; original files and payloads are not
rewritten. Unsupported alphabets remain warnings rather than guessed restrictions.

The shared `protein_structure` profile inspects opted-in PDB/CIF/ZIP utilities.
It lives in `boltzyme_tools_input_structure_validation.py`; shared molecule parsing lives in
`boltzyme_tools_input_sequence_validation.py`. The `sequence_validation` JSON rule key stays
unchanged; it is contract data, not a Python module name.
It does not inherit MolProbity's single-model requirement or impose a complete
backbone everywhere. Only declared chain, active-site, ligand and any-backbone
requirements run. MPNN/RC checks permit MSE and resumed chain sections. Generic
inspection budgets are local bounds, not fabricated worker acceptance limits.
Workers that validate every batch member retain hard rejection of malformed
members; this is distinct from MolProbity's candidate-local parsing failures.

Random mutagenesis indices are zero-based **protected** positions, not positions
to mutate. GENzyme shares the molecule parser without inheriting EnzyControl's
128-atom cap. FrameFlow native contig compatibility remains explicitly unchecked.
NetSolP's `US` Node versus `SU` worker combined-mode mismatch is disclosed only
when selected; neither spelling is silently substituted. Missing current worker
sources and unverified deployment behavior are not promoted to tested/verified.

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

### Enzyme submission compatibility

MolProbity's optional `molprobity-ligand-bundle.v1` ZIP protocol is described in
`skills/boltzmann-tools/references/molprobity-ligand-bundles.md`. The root manifest
shape lives in the existing file-input contract, and bounded dictionary limits
in the existing input-limits contract. Inspection separates dictionary CIFs from
declared candidates, checks hashes/roles/selectors, and retains explicit chemistry
and live-backend caveats. No new request field, native validator dependency,
scientific generator, runtime registry or protein-only fallback was added.
Optional dictionary-provenance outputs must be retained with the original ZIP.

- `kcat_km`: before preflight, prepare a private payload copy and fill a missing
  worker `job_name` from the confirmed `experiment_name`. Preserve explicit
  values and reject invalid labels (1–100 characters) rather than silently
  repairing them. The outer routing name remains `kcat_km`. The same prepared
  payload is validated and sent; credentials and runtime IDs are not synthesized.
- `Genzyme_Generation`: the v5 FastAPI schema requires both
  `complex_generation` and `top_k`, and the live Node route rejected omission of
  the former. Require explicit values without inventing defaults. Native
  `1 <= top_k <= num_structures` applies when complex generation is enabled;
  do not impose that conditional bound on the disabled branch.
- `Motiff_Scaffolding`: preserve the current native exclusive upper length bound.
  Positive bounds must satisfy `min_lengths < max_lengths`; both zero remains
  the existing unrestricted mode. Fixed length L is represented by `[L,L+1)`.
  Reject equal positive bounds instead of silently adding one to user inputs.
  Full native contig compatibility remains disclosed as unchecked.
- PLACER PDB inputs require distinct protein and non-water ligand chain IDs,
  matching the observed native chain-collision failure. The check does not
  rename chains or apply that PDB-specific restriction to CIF inputs. Backend
  diagnostic fixes and scientific-worker repairs are outside this client change.

Successful input validation is not proof of a completed scientific job. Unknown
submissions must still be reconciled or explicitly authorized again. Do not mark
all tools live-ready from unit tests or from a successful run of another tool.

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
