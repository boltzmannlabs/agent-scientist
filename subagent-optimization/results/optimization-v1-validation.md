# Optimization specialist v1 — development qualification

Date: 4 November 2026. Tracking: agent-scientist#33.

The [workflow](../workflow/README.md) is ready for a bounded local user test of
the current CReM/Lipophilicity example. This is a development runner, with a fresh
private named-specialist profile per reasoning episode. It is not installed into
every Agent Scientist profile or qualified for every molecular tool. Its
profile-local main-agent plugin is installed in `/home/boltzmann13/.sci`; the
actual SDK discovered the bridge tool and enabled saved specialist. Natural-prompt
model routing has not yet been exercised.

## What was implemented

- One optimization specialist with an actual loaded core skill and CReM reference.
- Scientific choices over exact parent forms and content-identified fragment-source
  libraries, while retaining the original task reference for final assessment.
- A checked, reversible identifier presentation that retains scientific records
  and reduces repeated opaque identifiers in model context.
- Host admission around the existing upload, submit, status and download wrappers.
  The private reasoning profile receives no copied platform credentials.
- Durable action intents, original job receipts, result identity checks, cumulative
  submission allowances, explicit uncertainty and restart handling in the existing
  campaign database.
- A bounded CLI that monitors existing jobs without repeated model calls, resumes
  from private state and stops on unresolved outcomes instead of resubmitting.
- A profile-local plugin and main routing skill, with explicit specialist-only
  evidence/apply operations and parent inspect/collect operations.
- A main-agent Markdown task entry point and an install receipt bound to the
  actual native saved-specialist revision.

## Actual scientific development run

The task required the same valid, distinct nonreference molecule to satisfy all
of: provider Lipophilicity score in 0–3 inclusive, QED strictly above
0.800452829768805, and sparse Morgan count radius-2 similarity strictly above
0.7 to the original reference. These are the selected computational constraints.
Provider score units and exact model revision remain unverified.

| Observation | Result |
| --- | --- |
| Generation jobs | 3 including 1 previously completed shared batch; 2 new jobs |
| Actual specialist reasoning episodes | 2 |
| Returned rows across the three batches | 834 |
| Distinct structures including original reference | 790 |
| Candidates meeting all constraints | 0 |
| Final state | Stopped: submission allowance exhausted |
| Pending scientific jobs | None at campaign close |

The specialist first selected a carbon-rich source library and then a hetero-rich
source library after the first result failed the objective. Both actions used the
same evidence-selected parent and matched the configured deterministic policy's
choice at those decision points. All constraints were retained. The host closed
the campaign at the allowance; it did not request an extra final narrative call.

A job can score many rows internally. The three-job allowance is **not** a
100-oracle-call limit. Total backend prediction work, credits and full billing
accounting remain unknown. Counts above are not experimental measurements or a
held-out optimization benchmark.

## Actual model controls and context

A fresh task-guided main agent and the named specialist received the same frozen
first-decision evidence, action choices and reversible identifier presentation.
They used the same configured model/provider route. The main control had no
saved molecular role, selected skill or delegated child. Neither control executed
scientific jobs. Both requested the **same parent and carbon-rich library**.

This single decision shows no specialist advantage. It is not a complete matched
workflow comparison, an unrestricted Agent Scientist baseline or evidence of
better molecular properties.

For that specialist first-decision packet, identifier presentation reduced
250,708 canonical characters to 124,506 transmitted characters while retaining
296 rows and 200 eligible choices. Reported input tokens were 121,573 before this
presentation and 52,478 in the later specialist control; both chose the same
action. These are observed input counts, not a verified billing or general speed
improvement. The main control reported 48,084 input tokens for its different role
instructions. Original credentials remained unchanged in the recorded checks.

## Verification and limits

The machine-readable [qualification record](optimization-v1-validation.json)
records **112 passing portable checks**, zero skips and current source hashes;
see the [test log](optimization-v1-portable-tests.log). The actual SDK middleware
canary passed **2 tests, zero skips** through the SDK's required test harness; see
[XML](optimization-v1-native-gate-tests.xml). The main-entry canary passed **1
test, zero skips** through the same harness; see
[main-entry XML](main-entry-native-tests.xml). It covered real profile-scoped
plugin discovery, bridge tool registration, named-specialist catalog and grants,
skill loading and main inspection through the scoring host, using fixture state.
Neither SDK canary used model inference or submitted scientific jobs.

Earlier dated pilot and software reports remain historical. Raw structures,
model conversations, job IDs, signed links and credentials are excluded from
this publication report. Full evidence stays in the private campaign directory.

Remaining work includes a full matched main-agent versus specialist workflow
comparison, repeated tasks and protected evaluation, ordinary-profile routing,
qualification of other tools/objectives, and evidence that specialized decisions
improve outcomes enough to justify their additional reasoning cost. No new
prediction model was trained in this increment.
