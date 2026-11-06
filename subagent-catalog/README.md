# Contributing company specialists: dev → validation → main

Create specialists in **main or any profile**. The SCI main profile and Git main
branch are different things. A portable package must not depend on the creator's
profile name, private IDs or machine state.

**Contributors prepare source files and test them. SCI does not provide package
export, seal or validation slash commands.** Maintainers own internal checks,
release artifacts, review and distribution. Existing definition-only JSON sharing
is not a complete contribution package.

## What to submit

Copy and edit [the starter template](../contribution-templates/subagent/README.md).
[The complete package specification](../website/docs/user-guide/features/subagent-packages.md)
describes every manifest field, dependency type and runtime mapping. The starter
template contains editable sample files; no example specialist is distributed in the catalog.

```text
subagent-catalog/<package-id>/
    manifest.yaml                  # portable definition and required capabilities
    instructions.md                # task instructions, no machine paths/secrets
    README.md                      # purpose, license, permissions, setup, usage, limits
    skills/<custom-skill>/          # complete custom skill, references and scripts
        SKILL.md
    references/                    # optional approved redistributable resources
    tests/
        sample.csv                 # harmless approved/synthetic fixture
        expected.json              # observable expected results
        validation.json            # contributor's actual local and dev test evidence
```

Do not include generated `files.lock.json` or `sci_cli/data/subagent_catalog.json`;
these are maintainer-generated integrity/release artifacts. Do not include `.env`,
API keys, OAuth tokens, authorization receipts, history, memory, run logs, private
data, caches, environments, installed binaries or absolute contributor paths.
Skills can contain supporting resources, not only SKILL.md; include everything needed
and licensed. Reference maintained Boltzmann modules instead of copying the connector.

## 1. Prepare and test locally

Use a separate contribution checkout based on **origin/dev**, leaving your working
agent checkout and SCI_HOME intact. These are ordinary Git operations, not commands
that assemble/validate a specialist for you:

```bash
git fetch origin dev
git worktree add -b subagents/my-specialist ../agent-sci-contribution origin/dev
cd ../agent-sci-contribution
```

After creating your specialist, manually prepare `subagent-catalog/<id>/` using the
template. Read the saved definition in `<owning-SCI_HOME>/subagents/<name>.json` for
its instructions, grants and selected modules. Private supporting skills live under
`<owning-SCI_HOME>/subagent-data/<extension-id>/skills/`; service configuration and
software there are **not** portable state to copy wholesale. Translate the required
capabilities into the manifest using the specification.

Test with a clean SCI home and a differently named profile. Use your own test model
and service credentials through supported setup, never commit them. Verify actual
fixture outputs and artifact counts, missing inputs/authorization, cancellation,
private skill/tool availability and separation from other profiles. A service merely
appearing in a catalog is not execution evidence. Record charges/limits and untested
modes honestly. Testable expected values go in `tests/expected.json`.

Fill the local section of `tests/validation.json` only with checks actually passed;
leave integrated status **pending** at this point. Update ID/version consistently.
No special exporter, sealing or validation slash command is needed.

## 2. Open a PR to dev

```bash
git add subagent-catalog/my-specialist
git diff --cached
git commit -m "Add my-specialist specialist package"
git push -u origin subagents/my-specialist
```

Open the PR with **base: dev**, preferably using `.github/PULL_REQUEST_TEMPLATE/subagent.md`.
Include purpose, output contract, provenance/license, SCI/platform/backend requirements,
integrations, credential names only, data transfers, permissions, costs and limitations.
Do not use `git add .`. Do not edit the shared generated catalog snapshot.

Maintainers review the package and internal CI before merging to dev. CI checks source
format, portability, known secret/path patterns, declared resources, local evidence,
version changes and controlled integration regressions. It never runs contributed
fixture scripts or uses production credentials. Contributors remain responsible for
their tests; maintainer review is independent acceptance, not a transfer of that duty.

## 3. Test the merged dev revision

After the PR is merged, fetch and create a **separate** test checkout. A global
`agent-sci` launcher may point to your normal main checkout, so launch the dev
checkout explicitly; otherwise you may accidentally test the wrong code.

```bash
git fetch origin dev
git worktree add --detach ../agent-sci-dev-validation origin/dev
cd ../agent-sci-dev-validation
git rev-parse HEAD
export SCI_HOME="$(mktemp -d)"
export SCI_RUNTIME_DIR="$(mktemp -d)"
python -m pm.build_env --source . --out .venv --group dev --group test
.venv/bin/python -m sci_cli.main
```

The build output must be fresh; do not replace an existing environment used by another
process. Use the repository's documented bootstrap Python if `python` is not suitable.
This setup can download declared dependencies. Configure model/test credentials through
the usual setup in the isolated home; do not copy your full personal state.

In that dev CLI: `/subagent catalog`, choose the package, install into **Current owning
profile** or your disposable test profile, review access, `/new`, then
`/subagent run <name> <fixture assignment>`. Repeat the real case study and inspect
outputs. Missing credentials should produce setup-required behavior, not fallback.

Record the full 40-character `git rev-parse HEAD`, package version, SCI version,
OS/architecture/backend, integrations exercised, commands/assignments, expected versus
observed results and any costs. Notify maintainers through the PR and update
`tests/validation.json` through a follow-up **PR to dev**. Updating evidence alone does
not require a version bump; changing instructions/skills/dependencies/fixtures does.

If anything fails, fix the package in a PR to dev, merge, test the new dev commit and
replace stale evidence. Do not claim passed based on the contributor's old installation.

## 4. Maintainer promotion and release

Review the contributor's exact-dev-commit evidence, perform final scientific/software
acceptance and select only approved changes for a main-promotion branch. If dev contains
unfinished work, do not merge the entire branch; select the approved release batch.

On that reviewed promotion checkout, maintainers generate the release snapshot:

```bash
python scripts/validate_subagent_catalog.py --write-snapshot
python scripts/validate_subagent_catalog.py --base <full-origin-main-SHA> --promotion --check-snapshot
git add sci_cli/data/subagent_catalog.json
```

Use the checkout's PM interpreter. Main PR CI requires local and integrated evidence,
a tested commit in fetched origin/dev history, identical package contents to that
commit (excluding evidence/integrity artifacts), and a fresh release snapshot. This
also supports approved cherry-picks without requiring all dev commits on main.

The final maintainer approval remains mandatory; CI checks evidence consistency, not
scientific truth. Configure GitHub branch protection/rulesets for **dev and main** to
require PR review and the `Specialist package acceptance` check, and restrict direct pushes.
Local code cannot enforce those repository-admin settings; the workflow must be pushed
before GitHub can run it. No automatic merge or release is performed by this feature.

After main acceptance, release normally. Users get the catalog with the SCI update,
select a specialist, review permissions and supply their own credentials. Merge does
not activate services or overwrite customized local specialists. Catalog install and
reviewed updates use the existing recipient commands; conversation changes apply at
`/new`.
