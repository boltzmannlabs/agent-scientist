# Context-conditioned library-selection baseline

**Implemented offline baseline; scientific usefulness untested.** This is a
comparison reference and reusable helper, not an installed specialist, molecular
generator or trained prediction model. Python standard library only.

## Scientific action

Choose one **untried approved fragment-library asset** for a future
`Fragment_Based_Optimization` investigation. The inspected public contract accepts
`ref_mol` and `library_path`; the supplied CReM worker turns the library into a
fragment database. CReM retains its own GROW/MUTATE operations and radii.

The helper never submits a job, uploads a library, calculates a molecular score,
infers chemistry, edits a campaign, or grants execution permission. Its input
records are a proposed adapter format, not new scientific-service API fields.

## Decision rule

1. Return no action for a closed/frozen/satisfied task. Stop when an admitted,
   fully assessed candidate satisfies all fixed conditions.
2. Match the task, **original reference**, assessor, context, filter protocol,
   generation settings, rule thresholds and reviewed edit-family definition.
3. Bind source batches to immutable library content, normalized-input policy/set
   and capability-card identity. Never recommend a tried asset, an equal-content
   alias or another file declaring the same qualified normalized molecule set.
   The task freezes `library_identity_policy_id`; other policies are incompatible.
4. Use trusted upstream chemical/form IDs. Retain cross-library provenance and
   count each identity once per family; reject contradictory scores/annotations.
   This code does not canonicalize SMILES or validate molecular graphs.
5. From complete compatible batches, summarize reviewed isolated-edit pairs.
   Count hard-constraint coverage and each individual objective's coverage
   jointly with those constraints. Use exact fractions, not weighted raw scores.
6. Choose among **remaining untried** assets whose reviewed capability cards
   target those families. Keep nondominated coverage profiles and use frozen
   manifest order for ties. An unknown family is explicitly cold-start
   exploration, never a fabricated zero-valued profile.
7. Compare fixed-order selection using the same eligible assets, observations
   and data-quality checks. Pending/unknown attempts are reconciled before this
   serial advisor recommends another investigation. All actions consumed means
   no new action, not proof the scientific task is impossible.

Coverage denominators contain distinct, fully assessed, reviewed single-edit
pairs in the declared context. Missing/unreviewed annotations and missing values
cause abstention rather than convenient omission. Reviewed multi-edit products
are disclosed separately and cannot establish an isolated-edit effect. A fully
assessed winning row can establish first success even when another row is
unresolved; full-batch coverage is needed for transfer profiles, not that winner.
Unapproved/unadmitted source evidence causes abstention; it is not silently used.

## Reproduce

From this directory:

```bash
python3 -B -m unittest -v test_policy
python3 -B demo.py
python3 -B run_checks.py
```

`run_checks.py` writes the small software-validation record under `../../results/`.
The policy/context checks require no external packages, model files or account.
The combined runner also reports optional RDKit identity checks; missing RDKit
is an explicit skip. Nothing is installed automatically.

## Controlled artificial example

Source libraries A and B have already been processed; C and D are untried.
Two alternative histories keep IDs, sequence, counts and assets identical and
change only artificial metric values:

| History | Contextual baseline | Fixed-order reference |
| --- | --- | --- |
| Family F has stronger marginal coverage | C | C |
| Counterexamples weaken F relative to G | D | C |

No molecule, property prediction or measured endpoint is represented by these
fictional IDs and values. This engineered example establishes evidence-dependent
mechanics. It does not show better molecular discovery, general policy advantage,
calibration, or native model compliance. Marginal coverage does not imply both
objectives will occur together in a future molecule.

## Boundaries before real use

- A trusted annotator must qualify molecular/form identity, original-parent/site
  mapping, edit isolation, context and the versioned family definitions.
- A reviewed library card supports an exploratory transfer hypothesis. Same
  parent/context/family labels do not establish exchangeability between libraries.
  Inspect actual generated products to determine whether the intended family
  occurred; the library cannot guarantee an edit, site or scaffold preservation.
- Declared SHA-256 values must be verified against real assets by the host.
  This helper checks supplied bindings, not authenticity. Different CSV bytes
  can normalize/fragment into identical proposal material. The separate
  [intake audit](../library_audit/README.md) computes a normalized input-set
  identity; this baseline blocks attempted aliases under that protocol. Actual
  fragment-material identity and generated-output overlap remain unqualified.
- CReM internally enumerates and predicts properties for outputs. Its public
  contract exposes no generation-count cap. Equal jobs are not equal compute;
  internal work/cost remain unknown until measured. No resource limit or saving
  is claimed by this helper.
- Service readiness, model-bundle translation/units, native delegation permissions,
  scientifically useful library assets and actual agent benefit remain pending.

The first scratch implementation passed tests but was rejected in review because
it chose only after actions were exhausted and confounded evidence with recency.
This version selects untried actions and uses a controlled evidence comparison.
The rejected scratch code and private run artifacts are not included here.
