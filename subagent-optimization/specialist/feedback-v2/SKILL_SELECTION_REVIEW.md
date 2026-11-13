# Proposed correction: select the existing frozen-panel skill

Status: **user-authorized and applied to the saved specialist**.
Date: 12 November 2026. Related blocked run: `sa-0-73beb317`.

The specialist selects `boltzmann:tools` and the optimization, QSPR and toolbox
module references. A request to load `frozen-panel-molecular-design` was refused
by `agent/specialist_policy.py:59`, because that separate profile skill was not
selected. This is a specialist access-configuration issue, not a failed Boltzmann
job or another terminal-approval denial.

The skill exists at
`/home/boltzmann13/.sci/profiles/ankith/skills/frozen-panel-molecular-design/SKILL.md`.
Its complete contents were reviewed and read successfully through the native
skill loader with preprocessing/setup disabled. It documents resume identity,
frozen endpoint selection, molecular identity/stereo checks, provenance, complete
coverage and honest reporting. It does not add an external service or new
execution capability. A separate critic found it appropriate for this task.

The local-structure/scorer guidance applies only when relevant to the task;
it does not authorize extra preparation or Smina work. Background-process advice
concerns long local terminal calculations; hosted jobs retain native IDs and
status/download workflows. The current task's resource/scoring rules govern.

The [proposed definition](definition-with-frozen-panel-skill.json) adds exactly
`frozen-panel-molecular-design` to the selected skills. Tools, child grants,
model settings, modules, scientific budgets and approval settings are unchanged.
The source proposal remains disabled/needs-review reference data. The live update
was subsequently authorized by the user and applied through native persistence.

Full selected skills/modules are already supplied by the native runtime. Avoid
redundant calls to load the same content. Do not read an unselected skill through
its filesystem path as a way around a skill-access refusal. Any genuinely needed
additional grant must be reviewed by the parent/user.

The continuation explicitly prohibits profile changes, so this scientific run
does not itself authorize the saved-definition update. After separate user
authorization, apply through native revision-checked persistence with a private
backup, then use a fresh conversation so cached grants are replaced. Do not
reset or rerun the original campaign.

No scientific reservation occurred in this blocked continuation. The cumulative
three submissions remain used, and the amended two-hour clock has not started.

## Applied correction

The user approved the exact skills-array change. On 12 November 2026 at
09:21:25 UTC, native compare-and-swap persistence updated `smallmol-design`.
Read-back verified that **only `skills` and the native `revision` changed**.
The specialist remains enabled, with no pending review. `config.yaml` was
byte-for-byte unchanged. No tool/child grants, instructions, model settings,
module selections, runtime limits or scientific budgets were changed.

A private prior definition and receipt are retained at
`/home/boltzmann13/.local/state/smallmol-specialist-setup/frozen-panel-skill-r_ztrtnz/`.
The source `definition.json` now contains the same two selected skills. Use
`/new` before the next assignment; no further specialist-editor step is needed.
No scientific jobs were run and the continuation clock remains unstarted.
