---
name: smallmol-routing
description: Delegate a bounded small-molecule CReM optimization task from a supplied task Markdown file to the saved smallmol-investigation specialist, and monitor its original campaign through the campaign bridge.
---

# Small-molecule investigation from the main agent

Use this route for the current qualified, initialized CReM optimization task.
The user can provide its Markdown file or request the task described there in
ordinary language. Preserve the requested reference, objectives and allowance.
The current implementation supports the qualified Lipophilicity 0–3 task only;
report unsupported tasks and missing inputs instead of substituting this example.

Read the supplied task Markdown. Call `smallmol_campaign(operation="inspect",
task_file="/absolute/task.md")` to check its identity, readiness and fixed limits.
Do not ask the user to run the internal CLI. Do not paste the full molecular
evidence archive into your conversation or the delegation context.

When ready, use the native `delegate_task` tool with one task:

```json
{
  "tasks": [{
    "specialist": "smallmol-investigation",
    "goal": "Investigate the bounded molecular optimization task. Fetch its checked evidence through smallmol_campaign, choose a scientifically justified supported action, apply the structured decision through that bridge, and report its actual receipt and limitations.",
    "context": "Task file: /absolute/task.md. Preserve its fixed reference, objectives and cumulative allowance."
  }]
}
```

Native main-agent delegation is asynchronous. An initial dispatch handle is not
the specialist's completed decision or an accepted scientific job. Use the native
delegation lifecycle and actual returned results; do not create a substitute child
with a different tool grant if the saved role is unavailable.

The specialist owns molecular choices. The main agent communicates with the user
and can call `inspect` or `collect` on the existing campaign. `evidence` and `apply`
are specialist-bound operations. Do not author or submit its decisions yourself.
While scientific jobs are pending, monitoring requires no new specialist call.
When imported observations make the campaign ready again, delegate its next
decision with the same task path. Continue within the user's requested run scope
and fixed limits; never busy-poll or create a fresh campaign to reset allowances.

Report objective success only from host-calculated qualification. Retain failed
attempts and uncertain receipts. If no candidate qualifies, state that plainly.
Raw provider scores are computational predictions with unverified physical units.
