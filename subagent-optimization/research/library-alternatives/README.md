# Actual library alternatives and a planning algorithm

2026-11-03. **Local structural study; all assets pending scientific review.**

[Validation record](run-v1/validation.json) and [independent AI-subagent review](review.md).

The [protocol](protocol-v1.json) was saved before acquiring a bounded 1,000-record
structure-only ChEMBL 37 snapshot. Selection used no activity, DRD2 classifier,
QED or similarity outcomes. After explicit filters, there were 640 N/O/S-rich
and 118 N/O/S-poor sources; 159 had exactly three N/O/S atoms, and 83 were excluded.
Deterministic selection produced 20 pairs matched on exact source heavy-atom and
ring counts. The mixed reference alternates groups across those pairs, sharing
ten sources with each focused library. This is a convenience pilot sample.

| Source library | Source molecules | Logical DB rows | Lead-applicable lookup tuples |
| --- | ---: | ---: | ---: |
| N/O/S-rich | 20 | 2,482 | 178 |
| N/O/S-poor (`carbon_rich_sources`) | 20 | 3,821 | 280 |
| Mixed reference | 20 | 3,854 | 238 |

Twenty is the source-library size, not the generator output count or an evaluation
budget. Carbon-rich does not mean carbon-only: F/Cl/Br are outside the N/O/S count.
Zero net charge does not exclude internally charged groups. See
[curation](run-v1/curation.json) and [data attribution](DATA_NOTICE.md).

## Structural qualification

The supplied v5 CReM scripts built temporary databases with one worker and radii
1/2/3. Reference lookup used the worker's actual GROW/MUTATE size windows. The
reconstructed core sets matched the supplied `get_replacements` core sets in all
18 library/radius/operation combinations. This is source-level lookup verification,
not hosted-service or assembled-product parity.

The focused libraries share 16 lookup tuples; 162 are exclusive to the rich set
and 264 to the poor set. Among 18 shared compact single-attachment slots, ten
offer exclusive rich-set N/O/S-bearing and poor-set no-N/O/S replacements of the
same incoming size at the same symbolic parent context. Four contrasts are at
radius 1, five at radius 2 and one at radius 3. See [material.json](run-v1/material.json).

For example, a three-heavy-atom carboxyl fragment `O=C(O)[*:1]` and an isopropyl
fragment `CC(C)[*:1]` appear at the same aromatic context. Other examples include
azide-containing groups. These are review candidates, not blanket desirable
chemistry or evidence of better polarity, activity, QED or synthesis. Matched
symbolic contexts do not identify unique sites or guarantee successful assembly.
RDKit emitted dummy-neighbor hydrogen warnings during inspection; successful
lookup is not candidate validation. Original unspecified lead stereo is retained.

## Implemented algorithm and worked example

[coverage.py](../../prototype/library_options/coverage.py) implements **standard
greedy maximum coverage**: add the library contributing the most new potential
lookup tuples to a hypothetical union, using fixed order for ties. Identical
renamed material adds nothing. Fixed-order and largest-library comparisons share
the same data and zero-addition checks. This is a known baseline, not a new model.

The [worked example](run-v1/coverage-demo.json) hypothetically includes the mixed
reference first, then permits one library addition:

| Remaining source library | Total | Shared with mixed | Additional lookup tuples |
| --- | ---: | ---: | ---: |
| N/O/S-rich | 178 | 66 | 112 |
| N/O/S-poor | 280 | 188 | 92 |

Coverage chooses the smaller rich library, giving a union of 350; largest-library
selection gives 330. **Fixed order also chooses the rich library.** This illustrates
overlap accounting, not superiority over fixed order, a base agent or a specialist.
No mixed-library scientific run or candidate evaluation actually occurred.

Tuples include radius, operation, context, outgoing and incoming core. They are
not unique fragments, independent experiments or valid/scored molecules. Equal
library additions do not mean equal compute or spending. Including a library in
this mathematical plan does not prove any products were generated or evaluated.
`plan()` trusts the supplied index and grants no execution authority.

## Specialist use and next step

Code should calculate identity, overlap and arithmetic; the specialist should
justify scientific decisions using actual reviewed results. It may agree with,
reject or abstain from the coverage plan. This index is not wired into automatic
delegation and cannot bypass existing review/invocation gates. All three assets
remain unavailable for operational policy use.

Next: SME review, actual hosted qualification and a common initial observation
batch with the fixed assessor. Delegate only if the task remains unfinished and
a meaningful choice remains; stop on genuine success. Give every comparison arm
the same helpers and evidence. Reviewed product/edit mappings and library cards
are still missing. ChEMBL provenance does not establish training independence.

From `subagent-optimization/`:

```bash
python3 -B -m unittest -v prototype.library_options.test_coverage
python3 -B -m prototype.library_options.demo \
  --index research/library-alternatives/run-v1/lookup-index.json
```

The index was extracted through read-only reinspection of existing databases,
reproducing saved material/source identities. No database was rebuilt for the
algorithm example. Raw acquisition and temporary DBs are retained separately.
