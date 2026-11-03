# Context and advisory-contract reference

This is the earlier standalone engineering prototype, retained as reusable
context-handling work. It contains no native child launcher, scientific executor,
new campaign database or prediction model. Fixtures and advice are artificial.

It demonstrates focused context with explicit omissions, retention of original
rules/evidence qualifiers/resource unknowns, host-only evidence retrieval,
freshness checks, strict advice references, terminal/pending safeguards and local
receipt replay. The host supplies authoritative records and stopping state;
hashes establish content association, not scientific authenticity or correctness.

Run from this directory:

```bash
python3 -B -m unittest -v test_context_contract
python3 -B check.py
python3 -B demo.py
```

There are no external dependencies or platform calls. `check.py` prints JSON;
`demo.py` prints a canned receipt, never a model decision or scientific score.

## Limits

- The wrapper format is proposed adapter data, not an existing campaign API.
- Context character limits do not establish token savings or better reasoning.
- Host action/termination policy is not independently derived task success.
- Pending-candidate checks are conservative; exact operation identities need a
  reviewed native adapter before allowing independent concurrent evaluations.
- Receipt replay uses a caller-supplied list, not a persistent idempotency service.
- `not_assessed`/`not_performed` labels do not semantically validate prose.
- Native schema validation, actual child permissions and scientific efficacy
  remain unqualified. No production integration is implied.

The main agent and any specialist should receive the same execution safeguards
when comparing scientific strategies; infrastructure improvements are a separate
experimental factor.
