# Run the conditional decision pilot

This runner freezes one public DRD2 task, imports a common CReM batch, and compares
at most one follow-up decision per arm. Read [PROTOCOL.md](PROTOCOL.md) first.
It does not install a specialist, change a profile, start live jobs or publish code
automatically. The arms are `base`, `base_algorithm` and
`base_algorithm_specialist`. If the common batch already succeeds, no arm runs.

Current task change: the user selected a supported platform-property objective
instead of DRD2. Its model, units, baseline, objectives and evaluator must be
qualified and frozen as a new task. The DRD2 assessor below remains a development
reference; selecting an unrelated platform model does not make it a valid
evaluator for the new objective. The prior unconfirmed attempt is retained.

## Prepare and freeze

Use the existing qualified Python environment with RDKit/NumPy and the pinned
task/model/library files. Work from the bundle directory:

```bash
cd /home/boltzmann13/agent-scientist-subagent-optimization/subagent-optimization
RUN_DIR=/home/boltzmann13/.local/state/smallmol-pilot/run-001
python3 -B -m pilot.runner init --task lipophilicity --run-dir "$RUN_DIR" --generation-parameters /private/path/generation.json --baseline-record /private/path/verified-reference.json --qualification /private/path/qualification.json --runtime-identity /private/path/runtime-identity.json
python3 -B -m pilot.runner next --run-dir "$RUN_DIR"
```

Choose a **new private directory outside the checkout**. `init` freezes the
protocol, implementation hashes and nonsecret runtime identity before outcomes.
The identity JSON has exactly `model` and `provider`, containing the actual
configured identifiers. Never put API keys in it. Required
`--generation-parameters /private/path/generation.json` freezes explicit
`global_models`/`custom_models` arrays with at least one named/identified model and
its threshold fields. Missing or empty selections are rejected before creating a
development run or uploading inputs. Caller-selected values are preserved;
worker-managed `attribute` fields are not an alternative objective. The runner
does not infer model IDs, units, bounds or scientific alignment. Unknown resource
costs remain unknown; numerical caps
are not enforced by this first runner.

## Collect and ingest observations

`next` prints the current stage/request without dispatching it. The first stage is
`common`. Use the existing authorized connector to collect its complete output,
then retain the actual downloaded CSV and an association receipt privately:

```json
{
  "request_id": "copy from this stage's request",
  "library_content_sha256": "copy from this stage's request",
  "status": "completed",
  "complete_output": true,
  "job_name": "Fragment_Based_Optimization",
  "doc_id": "actual original job ID",
  "artifact_sha256": "SHA-256 of the exact downloaded CSV bytes",
  "evidence_kind": "imported_nodeapi_artifact"
}
```

```bash
python3 -B -m pilot.runner ingest --run-dir "$RUN_DIR" --stage common --csv /private/path/output.csv --receipt /private/path/receipt.json
python3 -B -m pilot.runner next --run-dir "$RUN_DIR"
```

The receipt declares the association; imported JSON alone is not native execution
proof. `existing_connector_runtime` additionally requires this runner's recorded
submission and completed monitor receipt. `fixture` is restricted to fixture runs.
Keep failed/invalid/duplicate rows in the complete CSV. The fixed assessor retains
them and checks joint success on the same candidate. A completed identical import
can be replayed without another assessment.

If the connector returns `approval_required`, stop before retrying. Show the
concrete unchecked aspects and obtain the user's explicit best-effort approval.
Only then may the active host create the adapter with
`allow_partial_validation=True`, forwarding the connector's existing option for
the reviewed operation. It defaults to False, does not skip native validation,
and does not change scientific inputs or scoring rules. The adapter itself cannot
authenticate user consent. A general instruction to run or a local parser check
is not a substitute for approval of the warning. Retain the blocked attempt; when
runner code changes, prepare a fresh frozen run after approval rather than editing
old state. Confirm that no upload/submission occurred before any fresh attempt.

## Inspect and record a decision

If the common batch is unfinished and a meaningful choice remains:

```bash
python3 -B -m pilot.runner context --run-dir "$RUN_DIR" --arm base_algorithm
python3 -B -m pilot.runner decide --run-dir "$RUN_DIR" --arm base_algorithm --advice /private/path/advice.json
python3 -B -m pilot.runner next --run-dir "$RUN_DIR"
```

`context` provides the exact `input_digest`, admissible evidence and advice fields.
Its compact tables retain all rows and source columns; shared assay metadata and
structures appear once, with a hash binding to the full saved evidence. This
reduces repeated context without selecting only favorable candidates. Oversized
native assignments are rejected explicitly rather than silently truncated.
The Lipophilicity protocol freezes a 262,144-character assignment-data allowance
for all three arms. The legacy reference defaults to 24,000 characters. These
technical bounds are not token/cost limits; actual parent/child usage is separate.
`decide` imports advice for contract testing; it does **not** run a model. Importing
specialist-arm advice records `routing_failure` and creates no follow-up stage.
For accepted recommendations the follow-up stage ID is the arm name. Use its
frozen request, then ingest its complete output as above. Abstention is retained.

## Native runtime APIs

The native APIs depend on the separate, already configured Agent Scientist SDK
checkout at `/home/boltzmann13/agent-scientist`. Run them inside that active host
with both its modules and this bundle importable; do not substitute the research
checkout for the SDK. Existing profile authorization and an enabled saved matching
`smallmol-investigation` definition are prerequisites. No setup is performed here.
The scoring CLI must retain the pinned RDKit/NumPy runtime; the SDK may use a
different interpreter. Reopen the same private run for native decisions and
connector calls, and assess downloaded output with the qualified scoring runtime.

`NativeDecisionDriver(parent_factory(existing_host_options), runtime_identity)`
constructs the instrumented decision driver. Use the **same existing model options
and profile for every arm**, with secrets kept in memory. `runtime_identity` must
match the nonsecret identity frozen at initialization. An explicit
`run.invoke(arm, driver)` performs model inference; it is not part of the CLI
commands above. The specialist arm explicitly invokes the named child and checks
the frozen role. Model/provider are verified; complete inference-setting and
fresh-session equivalence remain caller assumptions. Retain all parent/child
usage and unknown costs. This does not establish a qualified causal comparison.
The full role is supplied once through the native role context. Assignment data
carry its identity binding rather than another copy of its instructions.

`NodeAPIAdapter.from_active_host(**existing_dispatch_context)` uses the active
host's ordinary session and tool grants. `NodeAPIAdapter(call_tool)` also accepts
an existing dispatcher callback; only `from_active_host(...)` instruments the
actual host dispatcher. The adapter calls existing Boltzmann upload/submit/status/
download tools and adds no HTTP client or scientific implementation.

Live execution is an explicit separate action: use `run.dispatch(stage_id, adapter)`
to persist intent before upload/submit, `run.monitor(stage_id, adapter)` for status,
and `adapter.download(actual_signed_https_url, private_output_directory)` for the
native download. Do not call upload/submit separately from the runner. Review the
request and normal host authorization before taking those actions. Nothing in the
CLI guide dispatches them automatically.

## Report and recover

```bash
python3 -B -m pilot.runner report --run-dir "$RUN_DIR"
python3 -B -m pilot.runner recover --run-dir "$RUN_DIR" --stage common
```

`recover` reprocesses the retained local CSV/receipt after processing interruption;
it never uploads, submits or polls. It cannot resolve an uncertain scientific
submission. Preserve its original receipt and reconcile the original attempt with
`run.reconcile(stage_id, original_submit_receipt)`; never create a replacement to
work around an unknown outcome. Source drift requires a fresh frozen run.

The report separates shared actual work, attributed arm work, imported/fixture/native
evidence, costs and unfinished attempts. This bounded development comparison has
no protected holdout or causal specialist-gain claim. Keep receipts, signed URLs,
credentials, outputs and native traces out of commits. These steps perform no
installation, Git push or automatic live call.
