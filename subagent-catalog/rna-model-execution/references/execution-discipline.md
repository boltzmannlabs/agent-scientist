# Execution discipline rules

1. Isolation is absolute: fresh destination prefix per integration; never an existing environment, the SCI runtime,
   or a shared interpreter. The main Agent Scientist environment is never modified.
2. The clone is pristine: original repository files are read-only; adapters, drivers and configs live in your
   workspace. The resolved commit hash is recorded, not the requested one.
3. Checkpoint provenance is binary: VERIFIED against the spec's checksum, or a BLOCKED stage. Unverified checkpoints
   are not downloaded-and-hoped; random/partial weights are never substituted.
4. Inference claims require execution: "successful inference" means a completed run with per-record outputs on disk.
   Never report an expected result, a dry run, or the model's README example as inference.
5. Input-to-output mapping is preserved: every output row traces to an input record id; failures are per-record.
6. Failure is reported, not laundered: failed integrations keep their recovery state (completed steps, exact resume
   point, pending approvals) and never advance the registry past the last true state.
7. Resumability: receipts and manifests are written as stages complete, so an interrupted integration continues
   rather than restarts.
8. Mechanical vs scientific: installation and inference success establish capability, not validity. Benchmark
   validation uses parent-supplied labels under a frozen protocol; PRODUCTION_APPROVED additionally requires an
   explicit parent directive, quoted.
9. Egress and cost: every network operation (clone, install, download) carries the parent's authorization reference
   in the report. No retries with alternative sources after a failure without a new parent decision.
