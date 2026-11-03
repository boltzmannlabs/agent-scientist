# Delegation integration boundary

Status: updated local source inspection, 2026-11-03. Earlier public-lifecycle
findings below are retained as history; the current development bundle uses the
newer saved-specialist interface, not an unchanged upstream plugin installation.

## Current selected route

The supplied Agent Scientist working checkout has a native saved-specialist
definition store, portable import/review commands, `tasks[].specialist` resolution,
conversation-scoped definition snapshots and execution-time grants. Exact inspected
files are listed in [source-inspection.json](source-inspection.json).

Our [definition](../specialist/definition.json) is disabled pending destination
review and selects no tools, skills or child specialists. The existing named
runtime narrows tools to those exact selections; empty named grants do not mean
ordinary child inheritance. The host adapter prepares the assignment and validates
its advisory return. No core files, scientific wrappers or live profile settings
are changed by this work.

Import/review and `/new` use the native setup flow. Merely adding purpose text
does not enforce scientific invocation gates: automatic matching is model-driven.
The first controlled harness must prepare the packet, dispatch its explicit named
request and check fresh source before acceptance. Invocation, context and real
costs must be measured; there is no new model-routing or memory implementation.

This is specific to the inspected working checkout. It does not establish support
in every upstream Hermes version or a deployed installation.

## Earlier public-lifecycle findings

The official Hermes advanced-delegation reference separates model routes from
profile routes. A route chooses a child execution configuration; scientific
specialisation comes from task/skill guidance. Profile routes include the target
profile's credentials and terminal policy. Keep model-routing experiments
separate from the first scientific comparison and use the same LLM initially.

The reviewed upstream plugin depends on Hermes's delegation-provider registration
seam. The earlier Agent Scientist source inspection found a public
`PluginContext.subagent_lifecycle` but did not establish compatibility with that
upstream provider interface. Do not install the plugin unchanged by assumption.

Checks retained from the earlier local lifecycle inspection:

- Use the public supported plugin interface with an active parent; do not rebuild
  another child runtime or scientific connector.
- Dataclass fields do not establish implemented support: per-launch timeout,
  working-directory overrides and per-tool blocking were rejected in that snapshot.
- Empty toolsets inherited parent capabilities. Coarse file/skill bundles could
  write; MCP configuration could add inherited tools. Inspect resolved child
  schemas and actual execution permissions. Prompt wording is not confinement.
- Public launch lacked output-schema support. The separate delegate output helper
  could accept parsed JSON without shape validation when jsonschema was absent.
  Domain evidence checking and scientific review remain separate responsibilities.
- Handles were process-local. Durable campaign evidence does not make a serialized
  child reconnect after restart; never replay unresolved scientific submissions.
- Character-count reduction does not demonstrate token/cost savings. Preserve
  exact constraints, qualifiers, negative evidence and resource unknowns, then
  measure real parent/child usage and decision quality.

These are dated findings about another integration seam, not permission conclusions
for the current named-specialist route. The local adapter tests do not establish
actual LLM compliance, scientific gain or production-service readiness.

Reference: [official advanced-delegation documentation](https://hermes-agent.nousresearch.com/docs/plugins/advanced-delegation).
