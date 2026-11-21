# Changelog

## 1.2.0 — native portable hierarchy

Use schema v2 to declare the four child packages with compatible versions. The normal SCI package installer
reviews their capabilities, binds renamed local children and preserves profile isolation. The coordinator uses
its reviewed child grants directly; the previous external-installer requirement is superseded. Local packaging
checks do not establish scientific readiness or replace merged-dev validation.

## 1.0.0 — orchestrator package

First package release of the rna-agent orchestrator, replacing the bare local definition: deterministic table-backed
router (script + machine-readable table), delegation-contract reference, leaf dependency matrix with PLAN_ONLY
planning and read-only host verification, shared registry CLI copy, routing/preflight fixtures and unit tests
(including registry-copy identity assertion). Children wiring remains a parent-side installer step because SCI
package schema v1 rejects manifest children declarations.

## 1.1.0 — managed-assignment loop + roster self-knowledge

The user now calls rna-agent alone and it owns the task end to end: (1) new references/subagent-roster.json +
scripts/roster.py (list/describe/capabilities/check) give the orchestrator machine-readable self-knowledge of its
four specialists — domains, modes, real capabilities, per-mode REQUIRED INPUTS (briefs assembled complete instead
of bouncing NEEDS_INPUT) and scope limits; (2) the contract becomes a managed-assignment loop: EXECUTE-NOW
directive → parent executes the leaf in the same turn → result reported back → orchestrator VERIFIES completion
itself (artifacts, registry transitions, status semantics) before the consolidated report; verification failure is
reported, never papered over; (3) the capability chain (discovery→execution) runs automatically when the original
assignment pre-authorized acquisition, with authorization gates intact.

## 1.1.1 — verifier profile fallback fix

Live managed-loop test caught the child verifier reporting PARTIAL despite bound leaf bindings: when SCI_HOME is
absent from the terminal process env, bound_programs() fell back to the default profile (~/.sci) instead of the
active one. Now reads ~/.sci/active_profile and resolves the profile home, matching the session's actual
specialist definitions.

## 1.1.2 — verifier home resolution under scoped child environments

Second live catch: inside a specialist child, SCI_HOME points at the child's scoped extension home
(subagent-data/<hash>), which contains no definitions — the verifier reported PARTIAL despite bound bindings.
bound_programs now probes candidate homes in order (env SCI_HOME if it has the definition, the active profile,
the default root) and uses the first that actually holds subagents/<leaf>.json. Verified under the child's exact
env condition (SCI_HOME at an extension home) -> READY.
