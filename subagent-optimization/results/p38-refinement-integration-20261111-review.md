# First refinement pilot — separate read-only review

Tracking: agent-scientist#33. Reviewed 12 November 2026.
Source run: `sa-0-d12ee796`, ankith profile, directory
`workspace/08_results/p38_refinement_feedback/integration_20261111T125648839983Z/`.
Status: **partial integration; final evaluation incomplete**. No continuation
was authorized or executed by this review.

The reviewer read the report, decisions, ledger/manifest, subset commitment,
eligibility data and provisional ranking, and inspected the native run receipt
and live transcript around the denial. A separate critic reviewed the scientific
follow-up and contract. This is a read-only review, not independent redocking or
experimental validation.

## Verified progress

All 61 inventoried artifact hashes matched. Recomputing the sorted-identity
seed-1101 selection reproduced the 40 selected identities from 240 unique inputs.
Reported commitment precedes common assessment; the transcript supports the
sequence. This does not independently prove absence of every possible preview.

The three native jobs completed: CReM generation, common PAMPA and search Vina.
Forty new candidates were assessed, 16 jointly eligible; all 42 PAMPA inputs,
including both references, returned class 1. The remaining 200 generated
identities are unassessed.

The stored ranking reproduces a top-ten search mean of -8.6369 and best -9.748.
Nine of 16 scored new candidates are more favorable than same-batch e072
(-8.216); one is more favorable than SB2 (-9.234). These are native-score
comparisons only; units were not reported. The top candidate is near the QED
eligibility boundary. There is no committed/freshly assessed final panel, executed
feedback effect, biological outcome or specialist-superiority result.

## Critique of the follow-up

| Outcome among the 40 candidates | Count |
| --- | ---: |
| All constraints passed | 16 |
| Failed QED alone | 10 |
| Failed LogP alone | 1 |
| Failed both QED and LogP | 13 |

Retaining e072 while changing mixed to hetero-rich source material is a coherent
exploratory choice: it avoids simultaneously changing the parent and source
library, and actual source LogP is lower at matched average source size/rings.
It does not establish that emitted products will be smaller, more eligible or
better dockers. QED is the dominant eligibility failure; reducing LogP alone
would rescue only one existing assessed identity if its other properties stayed
unchanged. Effects on new products and QED remain untested. Polarity/TPSA may also
increase. The frozen decision appropriately records this counterevidence.

Judge any authorized follow-up on jointly eligible yield, QED/LogP failures,
actual product changes and retained-panel quality, not merely lower source LogP
or a better single score. Unequal CReM enumeration and stochastic/hidden worker
behavior prevent a causal or matched-compute interpretation of one comparison.

## Why execution stopped

The live transcript records a local preparation/reservation command at
13:29:19 UTC followed by `BLOCKED: User denied this command` at 13:29:26 UTC.
Further investigation on 12 November found the decisive profile agent.log entry
at **11 November 13:29:26.581 UTC**: `Subagent auto-denied dangerous command`,
with detector reason `script execution via -e/-c flag`. Native
`tools/delegate_tool_config.py` installs a noninteractive deny callback by default;
`tools/approval.py` renders its deny result as the generic "User denied" message.
This was an automatic subagent-policy refusal, not evidence of a human rejection.
The command constructed followup_payload.json and reserved an attempt in local
tracking files through pilot.py; it did not call the scientific service. Earlier
inline commands were smart-auto-approved. The exact smart verdict/reason for
this command was not recovered; the fallback auto-deny is directly logged.

The command did not run. The hetero library upload succeeded; there was
no follow-up scientific submission or pending job. Respecting the denial was
correct. It is not a CReM server failure.

The original submission deadline was **11 November 2026, 14:59:32.978055 UTC**.
Unused counters do not authorize new submissions after that deadline. Any
continuation requires explicit steering addressing both the denial and time
extension; neither the input assets nor counters should be silently reset.

## Options and recommendation

The critic identified final-only completion as the smallest useful continuation:
commit ten existing eligible identities and make one fresh final Vina submission.
It would complete panel evaluation without testing the proposed library change.

For the original goal of exercising an actual feedback action, the recommended
development continuation is the already proposed single library-change episode,
then final assessment: at most four additional submissions within the original
seven-attempt ceiling. This adds a real test of the recorded hypothesis while
preserving the parent, objective, assays and selection rule. It is still an
exploratory integration experiment. A separately prepared user-run amendment is
available in `research/p38-refinement-continuation-prompt.md`; it grants no
authority unless the user chooses to send it.

Stopping here remains an operator choice. Before a continuation, resolve the
scoped approval route: prose authorization alone does not demonstrate that the
subagent's fallback will stop auto-denying commands. Do not turn on blanket
dangerous-command auto-approval merely to get this pilot through. No original
artifact, counter, report, profile or scientific outcome was modified by review.
