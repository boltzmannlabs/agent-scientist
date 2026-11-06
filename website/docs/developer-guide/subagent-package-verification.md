# Specialist contribution workflow: verification report

Verified 2026-11-06 in an isolated checkout of the exact package-only staged files,
before publication. No production scientific job was submitted during verification.
The distributed table-reviewer example is excluded; only the editable starter remains.

## Current implementation

Contributors prepare a documented source package themselves, test it and submit a
PR to **dev**. They then test the merged dev revision, submit any corrections to dev
and notify maintainers with exact-commit evidence. Maintainers independently review,
select an approved batch, generate release artifacts and promote to **main**.

Removed the package exporter module and contributor-facing package export, seal and
validation slash commands. The package menu now offers catalog/install/updates.
Existing definition-only export/import is preserved as a separate sharing feature.

Added/updated:

- Complete editable starter package under `contribution-templates/subagent/`, full
  manifest/dependency specification, contribution checklist and specialized PR template.
- Source-only PRs: no generated checksum lock or shared release snapshot is required
  from contributors. Every source package is still validated internally before install.
- Recipient installations generate local integrity records. Released/embedded packages
  require intact generated locks and verified catalog metadata.
- Contributor evidence in `tests/validation.json`: exact package identity/version,
  local environment and checks, initially pending integrated status.
- Dev CI checks source format, portability and local evidence. Main promotion also
  requires passed integrated evidence, an existing tested commit in fetched dev history,
  unchanged package content since that commit and a current generated release snapshot.
- Evidence-only updates do not require a version bump; substantive content changes do.
  This avoids an endless version/test/evidence cycle.
- Controlled Git fixture tests cover approved cherry-pick-compatible promotion checks,
  stale/unknown commits, changed content, pending evidence and snapshot freshness.
- Workflow runs for PRs targeting dev/main without path filters so a required acceptance
  status does not remain pending on unrelated PRs. Its check name is
  `Specialist package acceptance`. No automatic merge is configured.

Existing recipient scope, private credentials, dependency setup, managed update conflict
protection, pending-readiness enforcement and prompt-cache behavior remain intact.

## Verification

**79 tests passed across 25 files**, zero failures/retries, in 48.6 seconds through
the repository runner. This is targeted specialist/package coverage, not the full app.

```bash
SCI_PYTHON=/path/to/isolated-test-environment/bin/python scripts/run_tests.sh \
  tests/agent/test_specialist*.py \
  tests/sci_cli/test_specialist*.py \
  tests/sci_cli/test_subagent_package*.py \
  tests/scripts/test_subagent_catalog.py \
  tests/tools/test_specialist_integrations.py \
  tests/tools/test_saved_specialist_execution.py \
  -j 4 -q --file-timeout 180 --file-retries 0
```

Coverage includes real imports under isolated SCI homes, A→B→A separation, manual
source assembly without contributor locks, complete skill resources, recipient-only
credentials, picker installation, conflict/update behavior, deferred setup/resume,
real local executable checks and stdio MCP discovery/dispatch, exact tool allowlists,
private Boltzmann authorization, unsafe ZIP/secret/path/tamper rejection, embedded
catalog verification, and real delegated-child execution using a loopback model with
byte-stable parent prompt/tools. The blank template is not accepted as passed evidence.

Additional checks passed: source/release snapshot validator, generated desktop command
registry check, Ruff F/E9 checks and `git diff --check`.

Boltzmann's external auth transport was stubbed; local storage, receipt, registration
and permission checks were real. No live scientific job or third-party plugin download
was performed. Native Windows/macOS behavior and hosted GitHub execution were not tested.

## Before production promotion

No table-reviewer example is distributed. The catalog snapshot is empty; editable
starter files remain under contribution-templates. No real integrated dev result is
invented. Future contributed packages must follow the dev acceptance/evidence cycle.

After pushing, GitHub administrators must configure dev/main rulesets to require PR
reviews and `Specialist package acceptance`, and restrict direct pushes. Local files
cannot set those remote protections. Human approval and scientific review remain
necessary; CI verifies evidence consistency, not whether a contributor's claims are true.

Schema v1 still rejects nested-specialist packages and remote-backend local-program
provisioning. Partial setup can retain approved files/credentials at reported locations.
Scans are heuristic, plugin code has host access, remote MCP implementations are not
pinned by a local hash, and module selection is not a Boltzmann workflow allowlist.

See `subagent-catalog/README.md` for the complete contributor/maintainer process and
[the package specification](../user-guide/features/subagent-packages.md) for file format.
