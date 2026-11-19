# Source verification checklist

Verify each parameter-catalog entry against the approved source before it enters an experiment.

1. **Locate**: find the defining file (config module, thresholds JSON, runner script, parser block). Note the absolute
   path inside the approved source root.
2. **Read the declaration**: default value, type, allowed range, units. Units unknown at source (e.g. duplex ΔG scale)
   are recorded as "units unverified", never silently assumed.
3. **Classify**: frozen-by-contract (gate thresholds, hard vetoes, required stages) vs experimentally tunable
   (windows, top-k, weights within profile semantics, tool CLI flags).
4. **Cross-check the binary**: for CLI tools, capture `--help` / `--version` output from the actual installed binary;
   the binary's flags outrank any documentation.
5. **Record**: append findings to the run's parameter sheet with source citations; flag stale catalog entries for the
   run record. A disagreement between catalog and source is a result, not an error to hide.
6. **Never** treat a verified parameter as permission: source access, execution and egress still follow the parent's
   approvals and the frozen workflow contract.
