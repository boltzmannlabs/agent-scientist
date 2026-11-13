# SB202190 shared initial packet — separate review

Reviewed 12 November 2026. Tracking: agent-scientist#33.
Status: **initial packet integrity reviewed; neither comparison arm executed**.

Source packet:
`/home/boltzmann13/.sci/profiles/ankith/workspace/08_results/p38_refinement_matched/shared_sb202190_20261112T105759899917Z/`

Its manifest SHA-256 is
`dfa4d7f81c5a29a4917ca9fe761d663411dcca4bb5c602e416c93281cd1c3c74`.
The source directory and earlier experiments were not edited.

## Findings

- Initial CReM job `6af59bde57c3010cb90eb9cf` returned 109 unique new forms;
  subset seed 1101 committed 40 before outcomes. Sixty-nine remain unassessed.
- Common PAMPA `6af59d9157c3010cb90eb9f1` returned class 1 for all 42 inputs.
  This supplies no permeability ranking and is not experimental permeability.
- Joint eligibility is 3/40 (7.5%); exclusive failures: one QED only, two LogP
  only, 34 both, no PAMPA/missing failures. The overlap must remain visible.
- Search Vina `6af59fc3042419d6c2a5eda3` assessed three eligible generated
  forms plus the lead/control. Generated scores -8.582, -8.705 and -8.615 are
  less favorable on this native scale than SB202190 -8.888; SB2 scored -9.234.
  Units were not exposed. No final-panel or biological outcome is established.

A separate critic reproduced all 82 member hashes, 18 unchanged source originals,
five fixed assets, request digests, 109 strict identities, seeded subset, all
42 local descriptor records and common PAMPA joins. It checked all 50 returned
CSV/JSON/SDF pose scores, graphs, specified stereo and finite coordinates,
including all five selected poses. The parent independently verified the 82
members and exercised the new common adapter against every member.

No packet integrity blocker was found. This is independent artifact review, not
independent molecular computation or experimental confirmation. The review made
no recommendation of a continuation parent or library for either arm.

## Helper compatibility and endpoint checks

The frozen raw `observations.verified_file` expects decimal-text byte counts;
the packet correctly stores JSON integer counts. Separately supplied common
`evaluation_support.verified_packet_file` normalizes this interface without
changing the packet, weakening path/hash checks or making scientific calls.

The legacy `summarize_final` can produce a measurement-only mean despite an
ineligible final record. The new common `confirmed_panel_summary` makes the
primary mean null unless all ten slots have confirmed eligibility and valid
final observations/poses. Its host-input flags still require actual evidence.
Both arms receive the identical adapter and original helper snapshots. Seven
contract tests cover integer/text manifests, tampering/path escape, duplicate
IDs, missing/replacement slots, eligibility and failed/invalid pose/score flags.

## Next boundary

The [development-pair kit](../specialist/feedback-v2/evaluation/matched-v1/case-sb202190-v1/arms-v1/README.md)
uses new conversations in the existing profile, with no role/configuration edit.
This is procedurally separated and operationally asymmetric; enforced isolation
and matched model compute are not established. Shared scientific opportunities
and guidance are equal by contract. No superiority claim follows from a single
pair. The execution critic reviewed budgets, exclusion rules, stopping and the
separation of selection ties from numerical evaluator variation.

No new scientific job, Git action, profile change or original-source edit was
performed during review/preparation of this kit. Only the user-run assignment
can authorize new scientific operations.
