---
name: rna-orchestration
description: Use when routing an RNA requirement through reviewed child-specialist bindings, chaining approved assignments, or relaying actual child outcomes.
version: 1.1.0
author: Agent Scientist
license: MIT
---

# Orchestration procedure

1. **Classify**: run the packaged router on the request text. Mechanism first: siRNA/RNAi → sirna leaf; CRISPR/gRNA →
   grna leaf; model/tool discovery → discovery leaf; spec execution → execution leaf. Ambiguous (silencing without a
   mechanism) → one structured ASK. Not-covered deliverables (ASO, mRNA vaccine, aptamer, lncRNA, modification) →
   report the gap; capability gaps in those domains route to discovery.
2. **Check the registry** (parent-supplied path, packaged CLI show): reuse before rediscovery; INSTALLED-or-beyond
   capabilities route USE.
3. **Assemble the brief** per the target leaf's contract: shared inputs (organism, versioned reference, objective,
   output root, safety context, authorizations) plus leaf-specific ones (requirement brief/frozen gates for sirna;
   nuclease/priorities for grna; search authorization for discovery; spec/destination/egress for execution).
4. **Delegate** per {{resource.references/delegation-contract.md}} using the installed child name in the
   coordinator's rendered binding table. Resolve required inputs and approvals before calling `delegate_task`.
5. **Relay outcomes** unchanged: run ID, outcome, blockers, artifact paths, registry state. Chain when the parent
   approves the next hop. Never perform leaf science, never merge claims, never re-ask to dodge refusals.

Read the delegation contract at {{resource.references/delegation-contract.md}} before your first directive.
