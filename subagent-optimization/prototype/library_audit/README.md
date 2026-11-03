# Local library intake and review binding

This optional helper inspects existing local files using an already installed
RDKit. It does not generate candidates, predict properties, build a fragment
database, approve a library or execute a platform tool.

## What it checks

- UTF-8 CSV with exactly one case-sensitive `SMILES` header and consistent rows.
  Headerless SMI can be inspected, but is not a qualified public CReM input.
- Raw byte identity and three separate canonical-input identities: unique set,
  first-occurrence unique order, and multiplicity. Hashes include the policy,
  actual RDKit version and global stereo settings. These identify parsed
  representations, not physical samples, assay conditions or fragment databases.
- Strict parsing rejects trailing molecule names/tokens and CXSMILES. Canonical
  isomeric SMILES retain supported encoded stereo, charge, isotopes, disconnected
  components and tautomer forms without deliberate neutralization or tautomer
  standardization. Default hydrogen removal is recorded. Multicomponent rows
  require review. Invalid rows, empty libraries, discarded tetrahedral tags and
  unsupported query/dummy/radical/bond/extended stereo prevent complete identity.
- File pairs report normalized-set overlap. A renamed or reordered copy cannot
  establish a fresh molecule set. Raw/canonical structures are not exported.
- A review record is checked against an immutable subject digest. Changing the
  asset, normalization policy, context, family definition or annotation mapping
  invalidates the binding. Matching a record does **not** authenticate its author
  or confer approval; every audit and binding result keeps availability false.

The 16 MiB read bound is an engineering inspection limit, not a scientific budget.
`public_input_format_ready` means CSV shape only; it is not chemical, licensing,
service or scientific readiness. No dependency is installed by this helper.
Parsing does not establish physical stereochemical validity or sample identity.
Do not change process-global RDKit settings concurrently during an audit.

## Reproduce

```bash
cd subagent-optimization/prototype/library_audit
python3 -B check.py
python3 -B audit.py --input /path/to/existing/library.csv --format csv
python3 -B inspect_assets.py --source-root /path/to/BOLTCHEM-FEATURES
```

The last command inspects only three explicit files and writes metadata to
standard output. The recorded snapshot is [library-candidates.json](../../research/library-candidates.json).
Missing files fail explicitly. Missing RDKit skips structural tests with a stated
reason; review-binding tests still run. A skipped identity suite does not qualify
an asset. No string-based chemistry fallback exists.

## Relationship to CReM and the selection baseline

Inspected worker `duplicate_removal` uses `Chem.CanonSmiles`, drops invalids and
deduplicates in first-occurrence order. Our audit blocks clean identity on invalid
or unsupported rows and uses stricter parsing instead of silently losing input.
The public CSV contract is stricter than some internal header aliases.

The selection baseline consumes host-verified `content_sha256`,
`normalized_input_set_sha256` and `normalization_policy_id`; the task freezes its
`library_identity_policy_id`. Attempted byte-identical or normalized-set-identical
inputs are excluded from another recommendation. The helper does not load this
unapproved intake report directly into the policy.

Different normalized molecule sets can still yield the same fragment material.
The inspected fragment preparation removes stereochemistry by default and uses
context/radius/core/frequency information. Establishing fragment equivalence needs
the actual qualified preparation protocol and logical database rows. We have not
built or compared those databases, and do not claim the guard proves a new search
space, candidate novelty or equal compute. See [readiness requirements](../../research/data-readiness.md).
