# Later Vina job — two-ligand technical readiness

Tracking: agent-scientist#33. Date: 11 November 2026.
Status: **completed job reviewed; technical readiness demonstrated for this run**.

Actual platform ID: `6af4406cfe20edb9107da5fa`.
Job: `Vina_basic_docking`. Native terminal state: Success.
Local attempt: `414038e2fb2446d388dd1a62aa0e4000`.

The user executed this later submission separately. Its report records explicit
user-reported backend nonacceptance confirmation and authorization for a further
request. This review does not independently reconcile earlier unknown attempts
or rewrite their original records.

| Ligand | Returned poses | Fixed selected pose | Native Score |
| --- | ---: | --- | ---: |
| SB2 control | 10 | CSV index 0 / SDF tag 1 | -9.234 |
| e072 supplied lead | 10 | CSV index 0 / SDF tag 1 | -8.216 |

All twenty CSV rows, JSON records and SDF poses reconcile. No explicit failures
or validation issues were recorded. Saved checks cover graph identity, specified
and coordinate-derived stereochemistry, finite coordinates, box containment and
native score/pose-tag association. Score units are not explicitly labelled in
the artifacts; preserve the returned precision and do not substitute Smina scores.

Selected SB2 heavy-atom RMSD: 0.5123426949191693 Å, minimized over eight full
stereochemical graph correspondences without alignment in the original receptor
frame. Interaction residue references were checked; distances/types were not
independently recomputed. Local validation used RDKit2025.09.4.

A read-only feasibility critic verified all three raw-artifact hashes and
reviewed the validation code/results. Parent review parsed the saved reports,
raw CSV cardinality/selected scores and ZIP members/CRC. No docking, model
prediction, remote lookup, download or resubmission occurred during this review.

This demonstrates execution and output handling for this run. It does not
establish e072 binding, general docking accuracy, Solubility eligibility,
optimization improvement or specialist advantage. Provider duration is 41
seconds; charges, detailed compute and deployed version/seed/preparation remain
unverified. The earlier unknown attempts remain separate accounting issues.

No additional docking is needed merely to repeat this readiness check.
Solubility qualification and the declared comparison setup remain separate work.

Private source report and validation:
`~/.sci/profiles/ankith/workspace/outputs/p38-vina-confirmed-resubmission-20261111T101601790587Z/`.
Raw job-ID-named JSON, CSV and SDF ZIP are in its parent outputs directory.
Generated/private artifacts remain outside the source repository.
