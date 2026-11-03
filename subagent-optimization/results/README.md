# Validation evidence

- [Software record](software-validation.json): reproducible artificial tests,
  code hashes and controlled demonstration.
- [Policy test log](policy-tests.log): 32 behavioral checks.
- [Context test log](context-tests.log): 43 advisory/context checks.
- [Specialist adapter log](specialist-advisor-tests.log): artificial packet,
  invocation, freshness and response checks, separate from native integration.
- [Library audit log](library-audit-tests.log): structural-identity/review checks;
  the machine record states RDKit availability and any skips.
- [Library intake](../research/library-candidates.json): metadata-only real-file
  inspection, separate from artificial policy examples. No asset is approved.
- [Independent review](independent-review.md): earlier AI-subagent review and
  explicitly deferred scientific/native requirements.
- [Intake extension review](data-readiness-review.md): independent verification
  of current hashes, regenerated metadata and strict-parser corrections.
- [Native specialist canary](specialist-native-validation.json) and
  [XML](specialist-native-tests.xml): separate two-test native integration run,
  using temporary profiles and canned loopback responses. Earlier attempts are retained.
- [Specialist development review](specialist-development-review.md): read-only
  review of the local adapter, native canary and its scientific limits.
- [Library-alternatives study](../research/library-alternatives/README.md): actual
  structural material and standard coverage planning; separate validation and
  review records. It is not part of the earlier core/native test counts.

Regenerate the software artifacts with:

```bash
cd subagent-optimization/prototype/library_policy
python3 -B run_checks.py
```

These are software-mechanics and local structure-intake results. No candidate generator, property predictor,
scientific service or benchmark campaign ran in the combined checks. Native
integration uses a separate loopback fixture; actual LLM reasoning is not tested.
Artificial outcomes do not establish molecular-discovery performance.
