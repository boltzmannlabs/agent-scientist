# Complete optimization specialist — development v1

This separately versioned bundle replaces the earlier library-only advisory scope
for a new investigation. It does not edit or reinterpret the frozen pilot, install
a profile, enable a specialist, or submit scientific work.

## Files and ownership

- `definition.json`: native saved-specialist data; same logical
  `smallmol-investigation` name, new revision, disabled and requiring review.
- `skills/smallmol-optimization/SKILL.md`: core scientific procedure.
- `skills/smallmol-optimization/references/`: CReM controls, evidence/continuation
  and attribution. The CReM guide is selected upfront for this CReM-only version;
  other relevant references remain available on demand.
- `assignment.schema.json`: actual task, current capability contract, host-computed
  summaries, exact parent/library choices, prior work and cumulative resources.
- `outcome.schema.json`: identity-bound episode outcome, scientific reasoning and
  actual candidate/job/artifact references.

The specialist chooses permitted scientific steps. The host owns
normal connector dispatch, admission, artifact association and assessment. The
existing environment owns campaign records. Do not create another scientific
submission client or let model-authored observations become calculated evidence.

The current runtime-compatible path is `host_mediated`: the native specialist
requests a supported next action; the qualified scientific interpreter executes
it through the ordinary SDK connector transport and resumes the investigator.
An `action_requested` outcome is a bound unexecuted request, not a pending-job
receipt. Do not dispatch a blocked/planning-only proposal automatically. Scientific
strategy remains with the specialist; this does not require another main-agent
reasoning call for each calculation.

## Native integration requirements

The inspected SDK's `agent.specialist_store.Specialist.parse` accepts the definition
format. Selecting `smallmol-optimization` causes
`agent.specialist_runtime.context_for` to inject its `SKILL.md` into the child
context. The host must make that exact skill discoverable in its isolated profile
before constructing the child. Merely storing the source in this repository is
not runtime installation or proof of loading.

`skill_files` selects exactly `smallmol-optimization#references/crem.md`: this SDK
injects that relevant module eagerly alongside the core skill. The current workflow
is CReM-only, so preloading this small guide avoids extra model/tool rounds without
dropping molecular evidence. The specialist must not reread the core or selected
module. Other references can be read with `skill_view` when needed.
The SDK automatically adds `skill_view` and `skills_list` to a skill-bearing
specialist's effective grants. No child agents, shell or general filesystem tools
are selected.

Only the core skill is selected. This SDK rejects viewing an unselected skill, so
the specialist cannot silently load `boltzmann:tools` or
`leadopt_env:lead-optimization`. The host must supply the current relevant
canonical scientific contract and permitted environment-operation schema as
assignment data. Optional skill loading requires an explicit supported runtime
configuration; do not claim an unavailable on-demand path.

The declared scientific tools are the existing `boltzmann_upload`,
`boltzmann_submit`, `boltzmann_status` and `boltzmann_download`, plus
`leadopt_campaign`. Naming them grants neither installed handlers nor service
authorization. The parent must have the live capabilities, and the environment
plugin must actually be present. Report missing dependencies rather than inventing
fallback execution.

Tool-name grants alone do not restrict job names, payloads or spending. Before
enabling execution, the host must enforce task-scoped dispatch admission and retain
original receipts. Limit `leadopt_campaign` to the intended read operations
(`describe`, `status`, `report`, `progress`); host code records actual scientific
observations, actions and usage. Do not mistake the environment's advisory resource
checks for hard execution limits.

## Contract and continuation

The JSON schemas check structure, not truth. Host semantic checks must bind task
and input digests to the canonical assignment, verify exact-form parent eligibility,
library content identities, action keys and the frozen property objective. Candidate
success, pending-job identity and resource accounting require actual evidence.

The specialist returns `action_requested` for an authorized host-mediated generate
action, with no invented pending job or final candidates. It returns `waiting`
with an original job/receipt or artifact reference
when execution or host assessment is unfinished. It can resume from a new snapshot
of the same logical assignment; resources do not reset. `completed` requires an
actual qualifying final selection. `stopped` preserves unsuccessful/partial work;
`blocked` names a concrete missing dependency. Runtime/iteration exhaustion is not
scientific success.

Use a new isolated development profile for the new version. Do not overwrite the
old saved definition or previous campaign merely because the logical name matches.
Actual core/module loading, native reasoning and host-mediated connector execution
are documented in the [4 November qualification](../../results/optimization-v1-validation.md).
These checks establish development execution readiness for the current example;
scientific benefit remains unproven.
