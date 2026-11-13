# smallmol-design — current setup and next run

Status, 12 November 2026: **installed and enabled in the ankith profile**.
Tracking: agent-scientist#33. The bounded scientific continuation has completed;
see the [completion review](../../results/p38-refinement-feedback-completion-review.md).

The user saved the initial role update. After a continuation exposed a missing
skill selection, the user separately approved adding that one existing skill.
Native persistence and read-back verified the change; only skills and the native
revision changed. There is no further review/save step pending.

Selected skills:

- `boltzmann:tools`
- `frozen-panel-molecular-design`

Selected Boltzmann modules:

- Molecule Optimization
- QSPR Modelling
- Toolbox

Original tool and child grants remain unchanged. Instructions come from
[INSTRUCTIONS.md](INSTRUCTIONS.md). The [source definition](definition.json)
is a disabled, reviewable reference for future installation, not a command or
an instruction to overwrite an existing specialist. Native import does not
replace an existing name.

## Completed pilot

The [authorized continuation prompt](../../research/p38-refinement-continuation-prompt.md)
was executed successfully as `sa-0-1ce61f20`. All seven cumulative submissions
were used and ten final generated slots were assessed. No further scientific
execution is authorized by that completed pilot. Preserve its records and design
a separately authorized evaluation before another test.

The user chose a temporary profile-wide automatic-approval override separately.
Its risks and the framework attribution issue are documented in the
[team report](../../research/agent-scientist-subagent-approval-issue.md).
The skill correction did not modify that setting.

To edit this specialist later, use `/Update_subagent smallmol-design`, review
changes, save, then `/new`. Never revive an obsolete unsaved wizard draft over
the current definition; choose Start over when opening an old retained draft.
