# Subagent approval fallback reports an automatic policy denial as a user rejection

Prepared: 12 November 2026. This is a team handoff, not a published issue or an
implemented framework fix. No scientific job was retried during investigation.

## Summary

A named specialist's local Python command reached the CLI subagent approval
fallback. The framework automatically returned `deny`, without presenting an
approval request to the user, but its tool response stated **"User denied this
command"**. The specialist consequently stopped an otherwise progressing workflow
and requested new user steering.

The default auto-deny policy is intentional and documented: child worker threads
cannot read directly from the parent's terminal without risking a deadlock.
The confirmed defect is incorrect decision attribution. A related workflow
enhancement is needed for explicitly authorized unattended specialist work:
reviewable scoped authorization or a supported parent-mediated approval route.
This report does not request unconditional approval of commands merely because
an agent describes them as useful or a task prompt contains broad permission.

## Observed environment

- Interface: interactive Agent Scientist CLI with a named delegated specialist.
- Specialist: `smallmol-design`; native run ID `sa-0-d12ee796`.
- Delegation: `deleg_80604055`; child session `20261111_125720_e3a42f`.
- Model/provider recorded for the child: `gpt-6.1-sol` / `openai-codex`.
- Runtime: Linux, Python scientific environment; terminal tool enabled.
- Configuration at failure: `delegation.subagent_auto_approve` was absent from
  the inspected profile configuration, so the framework default `false` applied.
- Source code was inspected locally on 12 November. The exact source revision
  loaded by the original process and the original upstream author/commit were
  not independently established. Paths/line numbers below refer to the inspected
  checkout; this behavior was not added by this specialist-configuration work.

## What the specialist was doing

The specialist had completed three scientific jobs: initial CReM generation,
common property prediction and search docking. It then chose a documented
follow-up and uploaded the chosen fragment source library successfully.

The next command assembled the follow-up request from saved records and reserved
one generation attempt in local accounting. Normalized paths below preserve the
operations; `<RUN_DIR>` represents the actual existing investigation directory.
This is evidence, not an instruction to rerun the stopped investigation.

```bash
python -c "import sys; sys.path.insert(0, '<RUN_DIR>'); import pilot as p; x=p.load('followup_decision.json')['public_payload']; x['library_path']=p.load('followup_upload.json')['s3_path']; p.dump('followup_payload.json', x); p.reserve('generation', 'Fragment_Based_Optimization', 1, x)"
```

Inspection of the saved `pilot.py` shows that these operations write the request
and update the local manifest/accounting. They do not submit a remote job.
The approval detector identified the interpreter's inline-code form:
`script execution via -e/-c flag`.

## Exact evidence

The profile's `logs/agent.log` records the following at **11 November 2026,
13:29:26.581 UTC**. Command/path details are abbreviated here:

```text
WARNING tools.delegate_tool:
Subagent auto-denied dangerous command: <the Python command above>
(script execution via -e/-c flag).
Set delegation.subagent_auto_approve: true to allow.
```

At **13:29:26.592 UTC**, the terminal tool reported:

```text
exit_code: -1
status: blocked
error: BLOCKED: User denied this command. The user has NOT consented to this action.
       Do NOT retry this command, do NOT rephrase it, and do NOT attempt the same
       outcome via a different command.
```

The child live transcript corroborates that the command did not run. No
follow-up generation or fresh final docking was submitted. There was no pending
remote job to poll or cancel. The user did not receive an approval prompt for
this callback; the automatic-denial log establishes the decision source.

Earlier inline Python commands in this run were smart-auto-approved. Therefore,
`false` does not block every terminal command. This particular request reached
the fallback. The exact preceding smart-review verdict/reason was not recovered;
do not claim that the reviewer proved the script unsafe or that a human rejected it.

## Code path to inspect

Paths are relative to the Agent Scientist source checkout.

| Location | Relevant behavior |
| --- | --- |
| `sci_cli/config_defaults.py:1386` | Documents noninteractive subagent approvals and sets `subagent_auto_approve` to `False` at line 1389. |
| `tools/delegate_tool_config.py:42` | `_subagent_auto_deny()` logs automatic denial and returns the unqualified string `"deny"`. |
| `tools/delegate_tool_config.py:55` | `_get_subagent_approval_callback()` selects deny by default, or the auto-approve callback when the flag is true. |
| `tools/delegate_tool_child_run.py:856` | Worker executor initializer installs that noninteractive approval callback. |
| `tools/approval_detection.py:976` | Interpreter inline-code detection produces the `script execution via -e/-c flag` description. |
| `tools/approval.py:915` | The approval gate receives the callback response. |
| `tools/approval.py:927` | A returned `"deny"` is rendered with `spec.cli_denied` and outcome `"denied"`, without retaining the automatic decision source. |
| `tools/approval.py:721` | The command gate's `cli_denied` template says `"BLOCKED: User denied this command."`. |
| `tools/approval.py:512` | `_user_summary()` also uses the generic outcome, allowing user-facing summaries to attribute refusal to the user. |

The source comments explain why simply letting the worker call `input()` or
inherit an unsuitable terminal callback is not a correct fix.

The specialist definition and `/Create_subagent` / `/Update_subagent` editor
do not expose a per-specialist execution-approval policy. Relevant locations are
`agent/specialist_store.py:19` and `sci_cli/specialist_wizard.py:180`. Choosing
terminal access grants the capability; it does not change the separate approval
fallback. Ordinary instructions saved in the specialist are not an enforced
runtime authorization grant.

## Expected behavior and requested changes

### 1. Correct the denial attribution

Keep policy refusal as refusal, but make its source explicit. For example:

```text
Blocked by the subagent execution policy. This command was not run.
No user approval request was presented. The current fallback policy is deny.
```

Preserve structured distinctions between policy denial, smart-review denial,
actual human rejection, timeout and cancellation. Suggested fields such as
`decision_source` and `user_prompted` are proposals, not existing API guarantees.
Do not represent an automatic policy response as a human consent decision.
Update both model-facing text and user-facing summaries/receipts.

### 2. Make unattended specialist permissions explicit

For legitimate bounded workflows, provide or document a supported way to
authorize operations before execution. A possible design is a reviewed grant
bound to the owning profile, specialist/run, allowed operations/resources and
scope. Out-of-scope actions must still block. A natural-language task instruction
alone should not silently disable runtime checks.

If interactive approval is supported, route a correlated request through the
owning conversation/UI using a thread-safe mechanism. Do not read the terminal
from the child worker, deadlock the parent, or silently execute the blocked action
through the parent as an alternative. Gateway approval behavior is a separate
existing path; this observation concerns the CLI child fallback.

The smallest bug fix is accurate attribution. Scoped unattended approval or
parent routing can be delivered as a separately reviewed enhancement. The safe
default need not change to fix the misleading message.

## Reproduction guidance

1. Use an isolated test profile with the flag unset or false and a specialist
   permitted to use the terminal. Use temporary local JSON files, not this
   scientific campaign or a production service.
2. Delegate a local JSON-preparation task whose command is flagged for review.
3. In a controlled test, ensure smart approval proceeds to the fallback, such as
   with a deterministic ESCALATE fixture. Merely using `python -c` is not a
   deterministic reproduction because smart approval can approve it directly.
4. Observe `_subagent_auto_deny()` returning `"deny"` and the final response
   attributing that automatic result to the user.

No production reproduction or new scientific execution was performed for this report.

## Suggested acceptance checks

- Unset/false retains the intentional noninteractive deny behavior, without
  claiming the user rejected the command or displaying a nonexistent prompt.
- An actual human rejection remains clearly identified as a human decision;
  smart/policy denial, timeout and cancellation remain distinguishable.
- `true` remains an explicit broad opt-in with accurate automatic-approval
  reporting. It must not be presented as a per-command or per-specialist grant.
- A child approval path cannot block on terminal stdin, cross profile boundaries,
  lose correlation with the originating run, or duplicate an operation after a
  continuation/restart. Test both normal completion and parent interruption.
- If scoped grants are added, operations inside the reviewed scope can complete
  unattended; operations outside it still stop. Test with two isolated profiles
  to ensure grants do not leak.
- Add integration coverage for the callback-to-tool-result/summary path. Existing
  tests in `tests/tools/test_delegate.py:1790` establish the intended default;
  extending only those callback unit tests would miss the attribution defect.

## Impact and current workaround

The run stopped after 240 generated identities, 40 candidate assessments and
16 jointly eligible scored molecules. Its feedback action and final evaluation
remained unexecuted. The misleading error led both agents and user to investigate
a human rejection that had not occurred.

The user has now explicitly chosen this temporary profile override:

```yaml
delegation:
  subagent_auto_approve: true
```

The saved YAML was verified on 12 November. This applies broadly to commands
reaching the subagent approval callback in that profile; it is not scoped to the
single command above. No post-change scientific run or live success is claimed.
The original run's submission deadline expired; the override does not renew that
window, reset counters or authorize job duplication. Approval settings and
workflow scientific/resource authorization remain separate.

## Local evidence for maintainers

- Root checkout inspected: `/home/boltzmann13/agent-scientist/`.
- Decisive log: `/home/boltzmann13/.sci/profiles/ankith/logs/agent.log`, lines
  16363–16364 at the time of inspection.
- Child transcript:
  `/home/boltzmann13/.sci/profiles/ankith/cache/delegation/live/deleg_80604055/task-0.log`.
- Native run receipt:
  `/home/boltzmann13/.sci/profiles/ankith/subagent-runs/sa-0-d12ee796.json`.
- Run evidence:
  `/home/boltzmann13/.sci/profiles/ankith/workspace/08_results/p38_refinement_feedback/integration_20261111T125648839983Z/`.

Share this report or narrowly selected redacted excerpts. Full logs, profile
configuration and scientific output directories can contain unrelated private
data or signed artifact URLs; they are not required as public issue attachments.
