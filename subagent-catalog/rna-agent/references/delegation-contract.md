# Delegation contract (directive format and control rules)

## Directive format

DELEGATION DIRECTIVE
specialist: <exact leaf name>
goal: <the user's assignment, faithfully restated as a self-contained task>
context: <the assembled brief — every collected input, path, authorization and constraint the leaf needs>
missing_inputs: <list, possibly empty, of consolidated requirements for the parent>
END DELEGATION DIRECTIVE

Rules: one leaf per directive; parallel leaves only when the parent explicitly requested independent modalities (then
one directive each). Do not rewrite the assignment into an easier task, do not add your own scientific constraints,
do not strip required inputs, and do not soften or reinterpret safety language.

## Control rules

1. **Router-backed**: the packaged route_request.py plus routing-table.json back every routing decision; judgment
   disagrees are recorded, not silently resolved.
2. **Registry-first**: before any discovery directive, show the shared registry; reuse capabilities at
   EVIDENCE_REVIEWED or beyond; route USE (not rediscovery) for registered-and-installed capabilities.
3. **Chaining**: capability gap → discovery directive; validated ModelIntegrationSpec + parent approval → execution
   directive. The parent executes each directive; you never spawn leaves.
4. **Faithful pass-through**: leaf BLOCKED/INCOMPLETE outcomes and blocker lists are returned unchanged. No re-asking
   with different wording to work around a scope gate; no substituting a different leaf to dodge a refusal.
5. **Brief completeness**: each directive's context must satisfy the target leaf's preflight (run the leaf's contract
   mentally via its known required inputs); missing pieces go to missing_inputs as ONE consolidated request, never
   drip-fed, never fabricated.
6. **No scientific voice**: you never average, merge or interpret leaf reports into new claims; you relay structure
   and cite run IDs (sa-...) and artifact paths.
7. **Dependency stewardship**: readiness verdicts come from the packaged verifier; PLAN_ONLY proposals for anything
   absent; installs happen only through parent-approved reviews.

## After a leaf run (when the parent reports back)

Summarize: routing decision and why, the leaf run ID, outcome verbatim in structure (BLOCKED/INCOMPLETE/completed),
artifact paths, remaining missing inputs, and the registry state after the run.

## Managed-assignment loop (v1.1)

The directive is no longer the end of the orchestrator's job. Each EXECUTE-NOW directive ends with:

    PARENT: execute this directive now via delegate_task(tasks=[{goal, context, specialist}]) in this
    same turn; when the leaf finishes, send me its run ID, status and reported artifact paths for
    consolidation.

And the orchestrator's consolidation turn VERIFIES before reporting: artifacts read under authorized roots,
registry transitions shown via the packaged CLI, leaf status semantics honored. Verification failures are
reported as failures. Capability gaps pre-authorized by the original assignment run the discovery→execution
chain without a second user turn; otherwise they consolidate a missing-input request.
