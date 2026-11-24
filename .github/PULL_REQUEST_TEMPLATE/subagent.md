## Specialist contribution — target `dev`

Package ID and version:
Hierarchy, child package IDs and version requirements (if applicable):
Purpose and expected outputs:
Author, provenance and redistribution license:

### Requirements and access

- Tools, complete custom skills, plugins/MCPs/programs and versions:
- Supported OS/architecture/backend and SCI version:
- Credential **names only** and approved external destinations:
- Data transfers, execution permissions, service charges and resource limits:
- Known limitations:

### Contributor evidence

- [ ] Package is under `subagent-catalog/<id>/` and matches the documented format.
- [ ] Required child packages/version changes are included; affected parents are identified for retesting.
- [ ] All necessary supporting files and approved synthetic fixtures are included.
- [ ] No keys, tokens, private SCI state, machine paths or installed environments are included.
- [ ] Local install/execution, output inspection and missing-input/authorization behavior were tested.
- [ ] `tests/validation.json` identifies this ID/version and actual local environment/checks.
- [ ] After merge, I will test installation/execution from dev and inform maintainers of the result.
- [ ] This PR targets `dev`; generated release snapshot/checksums are maintainer work.

### After merge to dev

For a hierarchy, list its child package IDs/version requirements and the versions
actually exercised. Include affected parents when a child changes, even if their
own manifests are unchanged. Verify installation into a differently named profile,
actual nested delegation, missing child setup and cancellation/update recovery.

Inform maintainers whether installation/execution from merged dev worked and report
any failures or limitations. Version/environment details and detailed receipts are
useful when available, but no evidence-only follow-up PR or integrated JSON update
is required. Submit fixes through corrective PRs to dev and retest affected behavior.
Maintainers record the team's confirmation in the promotion PR and perform final
review; confirmation does not grant service access or certify scientific accuracy.
