# PAMPA live readiness — binary label output

Tracking: agent-scientist#33. Date: 11 November 2026.
Status: **live result delivery/identity coverage verified; label interpretation
source-supported; no optimization or specialist comparison performed**.

The user executed one Property_Prediction job, document ID
6af455a44bcdd4891fc0f85f, with global_models=["PAMPA"], uncertainty=0 and
explainability=0. Native state: Success.

| Input | Raw PAMPA value | Source-supported interpretation |
| --- | ---: | --- |
| e072 | 1.0 | Positive/high-permeability class |
| SB2 | 1.0 | Positive/high-permeability class |

The source Property_Prediction export selects the native binary label, computed
before probability rounding. No raw score or distance from the boundary was
returned. These are not probabilities of exactly one or measured permeability.
Identity and specified sulfur stereochemistry matched the inputs in the saved
validation. No missing inputs, explicit failures or nonfinite PAMPA values were
reported. Parent review verified the raw CSV hash and two cells, without rerunning
chemistry or submitting requests.

Exact-ID diagnostic lookup returned HTTP404 without JSON. Runtime head/checkpoint
and loading trace remain unavailable; the interpretation is supported by source,
not independently tied to a confirmed deployed revision. This is a stated limit,
not proof that the prediction failed or that the job is absent.

Provider duration: 49 seconds. Billing amount: 2 with no explicit unit/currency.
Separate reported durations 129 seconds and total_tool_runtime=63 are retained;
they are not assumed to describe the same interval. One upload/submission, no
retries or top-ups, and no generation, optimization or docking were performed.

The pilot now uses common-assessor PAMPA class=1 with QED>=0.5 and Crippen LogP
0–5. Both current inputs pass, so there is no observed PAMPA deficit. Docking
quality is the refinement objective while these constraints are maintained.
GA's internal score step remains separately 0.5; its probabilities must not be
merged with common labels. Additional assessor calls count against the future
declared live allowance.

The offline component and long-record adapter now preserve class/score types,
accept only 0/1 in label mode and detect cross-kind conflicts. All 70 local tests
pass. A read-only critic reviewed the distinction. These checks do not establish
model accuracy, cross-route parity or improved molecular outcomes.

Private source evidence:
~/.sci/profiles/ankith/workspace/outputs/pampa-readiness-20261111T114615850213Z/.
Raw CSV SHA-256:
71c6adc528113005be6d3eef14989e50d2933dc29d901b3d941c7acc43ddcf0e.
Original records and saved profile/specialist are unchanged.
