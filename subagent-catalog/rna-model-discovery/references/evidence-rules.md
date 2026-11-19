# Evidence, weights and honesty rules

1. Every claim carries a citation: URL (or file path), access date, and the commit/version when the source is a
   repository. Uncited claims are deleted, not softened.
2. Weights verdicts are per-candidate and required: WEIGHTS_PUBLIC / WEIGHTS_RESTRICTED / NO_WEIGHTS, established by
   resolving the artifact location itself, not by README assertions.
3. NO_WEIGHTS models are never inference-ready. They may appear as alternatives with that verdict, and never as a
   SPEC's selected_model with checkpoint URLs attached.
4. Selection is multi-criteria with the ranked table shown. Published accuracy is one row. "Do not select models
   solely on published accuracy" is a hard rule: a selection rationale citing only accuracy is invalid.
5. Registry states this agent may write: DISCOVERED, EVIDENCE_REVIEWED, WEIGHTS_AVAILABLE — adjacent transitions,
   evidence notes required. Skipping is refused (the packaged CLI enforces it).
6. Search without authorization, clones without egress approval, and checkpoint downloads are all out of scope for
   this specialist; each requires the parent's explicit decision.
7. A discovery that ends with no qualifying candidate reports the scope searched, the queries used and why each
   candidate failed. Fabricating a plausible-looking candidate or spec is the worst possible failure mode.
8. The spec describes; it never promises: no installation, execution, benchmark or superiority claim derives from a
   ModelIntegrationSpec.
