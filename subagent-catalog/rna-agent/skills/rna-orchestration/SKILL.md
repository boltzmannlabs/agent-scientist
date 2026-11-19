---
name: rna-orchestration
description: Use when routing an RNA requirement to a leaf specialist, emitting a delegation directive, chaining discovery to execution, or relaying leaf outcomes.
version: 1.0.0
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
4. **Emit the directive** exactly per [the delegation contract](../../../references/delegation-contract.md).
5. **Relay outcomes** unchanged: run ID, outcome, blockers, artifact paths, registry state. Chain when the parent
   approves the next hop. Never perform leaf science, never merge claims, never re-ask to dodge refusals.

Read [the delegation contract](../../../references/delegation-contract.md) before your first directive.
