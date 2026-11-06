# Main-agent prompt entry

This integration exposes the small-molecule specialist through the owning Agent
Scientist profile. The user gives the main agent a prompt or a local Markdown task
file. The main agent reads the routing skill, checks the initialized assignment,
and uses native `delegate_task` for `smallmol-investigation`. The specialist reads
the checked host evidence through `smallmol_campaign` and submits its structured
decision through the same bridge. The host then runs the existing scientific
connector. The main agent reports actual status and can monitor existing jobs.

The first supported example is the private task file:

`/home/boltzmann13/.local/state/smallmol-specialist-v1/user-demo-20261104T081552Z/optimization-task.md`

The current task fixes the reference, Lipophilicity provider score range 0–3,
QED and similarity cutoffs, a three-job total allowance including one completed
shared batch, at most four episode admissions and an existing deadline. It allows
no more than two new CReM jobs. The task is bound to the separately prepared
campaign state; editing its JSON or prose after a packet is prepared invalidates
that packet.

## First prompt for the main agent

In a **new conversation** in the profile where the integration is installed, give
the main agent:

> Use the small-molecule optimization specialist to continue the initialized CReM
> task in `/home/boltzmann13/.local/state/smallmol-specialist-v1/user-demo-20261104T081552Z/optimization-task.md`.
> Read that file, keep every objective and budget fixed, and delegate the molecular
> decision to `smallmol-investigation`. Report the actual action or blocker and
> its evidence. Do not claim success unless the host reports a qualifying molecule.

For an implicit routing check, use:

> Continue the initialized CReM optimization described in
> `/home/boltzmann13/.local/state/smallmol-specialist-v1/user-demo-20261104T081552Z/optimization-task.md`.
> Preserve all thresholds and the remaining job allowance. Summarize the actual
> result and say clearly if no molecule qualifies.

The explicit prompt tests requested delegation. The second checks whether the
main agent recognizes the task without naming the specialist. An unrelated request
should not invoke it. Each new native child admission consumes the campaign's
finite episode-admission allowance, including attempts where the tool evidence
cannot be delivered. Do not repeatedly retry a failed delegation.

The specialist may return a waiting result while a job runs. In the same new
conversation, ask the main agent to collect status for the same task file. It can
monitor through `smallmol_campaign` without another specialist call. Once results
are imported and the task is still open, ask it to continue the same investigation;
the next specialist decision is based on the updated evidence.

This local example does not establish that the specialist beats the main agent.
The preceding paired first-decision control selected the same action in both arms,
and the separate development campaign ended with zero qualifying molecules.
Compare decisions and results under matched limits before making a performance
claim.

## Install and verify

The install script adds a profile-local bridge plugin, the routing and optimization
skills, a native saved specialist, and the small toolset to the current CLI profile.
It uses the existing SDK and scoring interpreters. It submits no scientific jobs.
An installation receipt identifies the exact role revision. Start a new main-agent
conversation so its specialist catalog includes the installed role; an old session
keeps its original snapshot.

`test_native_entry.py` exercises real plugin discovery, tool registration, native
catalog/resolution, skill loading, profile A→B→A scope and the host bridge with
fixture chemistry state. It uses no inference, platform network call or scientific
submission. Separate portable tests cover task binding, large evidence transport,
episode admission and idempotent host dispatch.
