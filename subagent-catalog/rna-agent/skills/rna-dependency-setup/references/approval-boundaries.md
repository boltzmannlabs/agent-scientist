# Approval boundaries for dependency setup

- **You propose; the parent disposes.** Every install, download, clone or environment mutation is a parent decision.
  Your proposals are PLAN_ONLY text with exact commands, pins and destinations.
- **Bindings, not discoveries, unlock leaves.** A program found on the host by the verifier is a candidate, not a
  grant. The leaf package install review binds program ids to executable paths with version checks and sha256
  records; only then may a leaf use them.
- **Fresh prefixes only.** Pinned recipes (the leaves' dependencies/ conda environments) must build into fresh,
  parent-approved destinations. Never install into an existing prefix, SCI, or a shared interpreter. Never merge the
  grna leaf's separate interpreter profiles.
- **Optional means optional.** A PARTIAL leaf still runs its core modes; report which endpoints stay blocked rather
  than pushing installs the parent did not ask for.
- **Integrations defer gracefully.** The sirna leaf's optional Boltzmann integration stays deferred until the parent
  authorizes it at install; do not treat its absence as a defect.
- **Model environments belong to execution.** Dependencies that only exist inside a ModelIntegrationSpec (frameworks,
  checkpoints) are the execution leaf's isolated-environment work under its own egress approvals — never part of leaf
  dependency setup.
- **Cost and egress**: every network operation in any proposed command (recipe fetch, wheel download, clone) must be
  visible in the proposal so the parent's approval covers it explicitly.
