# Contribute a specialist or specialist hierarchy

Start here after creating and testing saved subagents in SCI. Follow these same
steps whether you prepare the contribution yourself or ask a coding assistant to
help. A team follows the same process as a standalone specialist.

**Create and test in SCI → prepare package(s) → test installed packages → PR to dev
→ test merged dev → inform maintainers → maintainer promotion to main.**

| Stage | Who does it | What establishes completion |
| --- | --- | --- |
| Create specialists | Contributor | Saved specialists perform the intended assignment in SCI. |
| Package and test | Contributor | A fresh installation works without the creator's private state. |
| Submit to dev | Contributor, then reviewers | Package PR is reviewed and merged into dev. |
| Test merged dev | Contributor | Installation/execution from merged dev works; contributor informs maintainers. |
| Promote and distribute | Maintainers | Approved packages and the release catalog reach main and recipients. |

Opening a PR does not merge it. A dev merge does not finish integrated testing or
publish a release. Main promotion requires maintainer approval.

## Before you start

Collect the following from the specialists you already tested:

- Owning SCI profile, saved specialist names and parent → child relationships.
- A small approved/synthetic input and observable expected outputs.
- Required tools, skills/modules, MCPs, plugins and local programs.
- Author/license information, supported platforms, service destinations, credential
  names, charges and relevant limits.
- Known failures and tests not yet performed.

Keep your working specialists intact. Testing their saved definitions does not
establish that a portable package works; you will test the installation separately.
The SCI **main profile** and the Git **main branch** are different things. Packages
must not depend on the creator's profile name, private IDs or machine paths.

### Reading this guide

- **Terminal** blocks run outside SCI. Shell examples use Bash on Linux/macOS;
  PowerShell users must adapt shell syntax and environment setup.
- **SCI** blocks run inside the SCI CLI. Enter slash commands individually.
- Replace angle-bracket placeholders and example names with your own values.
  Use unused branch/checkout names and fresh package destinations.
- Use this page as the entry point, following these supporting references as needed:
  [starter package](../contribution-templates/subagent/README.md),
  [hierarchy example](../contribution-templates/subagent-hierarchy.md),
  [complete specification](../website/docs/user-guide/features/subagent-packages.md)
  and [development environment setup](../website/docs/reference/package-management.md#developer-workflow).

SCI has no package export, seal or validation slash commands for preparing a
contribution. Prepare ordinary source files using the template and specification.
Existing /subagent export and import share definitions only; they do not assemble
complete packages with private integrations and supporting resources.

## 1. Prepare a contribution checkout

Use a separate checkout based on **origin/dev**, leaving your working agent checkout
and SCI home intact. For hierarchy contributions, first ensure dev contains the
hierarchy-package support available on main. If not, ask maintainers to bring it
into dev first; your package PR should not duplicate the implementation.

**Terminal, from your existing repository:**

~~~bash
git fetch origin dev
git worktree add -b subagents/my-specialist ../agent-sci-contribution origin/dev
cd ../agent-sci-contribution
~~~

These commands prepare a source checkout; they do not copy or package your saved
specialists. Use your usual fork-based PR setup if you cannot push a branch to origin.

## 2. Prepare one source package per specialist

### Find the tested definition and its resources

Read `<owning-SCI_HOME>/subagents/<name>.json` for the purpose, instructions, output
contract, grants, selected skills/modules and approved children. Private supporting
skills live under `<owning-SCI_HOME>/subagent-data/<extension-id>/skills/`.

Translate the requirements into the portable manifest. Do not copy the live
definition or its entire private directory. Local service setup, credentials,
installed programs and authorization records are recipient-owned state.

### Copy and adapt the starter

For a standalone specialist, copy the starter into a fresh destination:

~~~bash
cp -R contribution-templates/subagent subagent-catalog/my-specialist
~~~

For the example team, use three copies instead:

~~~bash
cp -R contribution-templates/subagent subagent-catalog/table-team
cp -R contribution-templates/subagent subagent-catalog/table-reader
cp -R contribution-templates/subagent subagent-catalog/table-reviewer
~~~

Edit each copy. Copying the starter alone does not establish test results.

~~~text
subagent-catalog/<package-id>/
    manifest.yaml                  # identity and required capabilities
    instructions.md                # portable task instructions
    README.md                      # purpose, setup, permissions, usage and limits
    skills/<custom-skill>/          # when declaring a packaged skill
        SKILL.md                   # include its required references/scripts too
    references/                    # optional approved redistributable resources
    tests/
        sample.csv                 # approved/synthetic fixture; format may differ
        expected.json              # observable expected results
        validation.json            # actual local and merged-dev test evidence
~~~

For **every package**:

1. Set its unique ID, suggested local name, quoted version such as "1.0.0", author,
   license, purpose and output contract. Its folder name must match its ID.
2. Write the actual instructions and declare the tools, skills and dependencies it
   needs. Use the specification for MCP/plugin/program/Boltzmann requirements.
   Availability on your machine does not make a dependency portable.
3. Include complete licensed supporting resources. If renaming a packaged skill,
   update its manifest entry and SKILL.md frontmatter consistently.
4. Supply meaningful fixture/expected files. Each child needs its own test; the
   parent also needs an end-to-end test.
5. Set matching ID/version in tests/validation.json. Begin with local status
   "not_run". The optional integrated section may remain pending; no follow-up evidence PR is required.

Do not include .env, secret values, OAuth tokens, authorization receipts, history,
memory, private datasets, run logs, caches, environments, installed binaries or
absolute contributor paths. Credential **names** and approved synthetic fixtures
are appropriate. Reference maintained Boltzmann modules instead of copying the connector.

Do not generate files.lock.json or sci_cli/data/subagent_catalog.json for the initial
PR. Maintainers generate release integrity artifacts.

### Declare the hierarchy, when present

Each parent uses schema v2 and declares its direct children by package ID and
compatible version. Merge these fields into its **complete** starter manifest:

~~~yaml
schema_version: 2
id: table-team
name: table-team
tools: [delegate_task]
children:
  - role: reader
    package: table-reader
    version: '>=1.0.0,<2.0.0'
  - role: reviewer
    package: table-reviewer
    version: '>=1.0.0,<2.0.0'
limits:
  max_iterations: 30
  timeout_seconds: 0
~~~

This fragment does not replace the other required fields. Add other parent tools
only when needed. V2 accepts timeout 0 for no overall task deadline; existing v1
standalone packages retain positive timeouts.

In portable parent instructions, use role tokens instead of creator-local child names:

~~~text
Assign the supplied CSV to {{child.reader}} to calculate the requested counts.
Then pass the original CSV and that worker's exact result artifact to {{child.reviewer}}.
Collect the requested findings and output paths. Preserve the original input.
~~~

Each child keeps its own permissions and integrations; they do not become the
parent's direct tools. All ready, enabled specialists support automatic matching and explicit
assignments. Parents may delegate only to their approved children. Children may themselves declare children;
include every required new package, including grandchildren.

For local installation, place child folders beside the parent using package IDs as
folder names. Already distributed dependencies may come from the reviewed catalog.
SCI checks missing packages, incompatible versions and cycles before setup.

## 3. Install and test the prepared packages

Use a **new terminal** and launch the intended checkout explicitly. A global sci
launcher may still point to your normal installation.

**Terminal, in the contribution checkout:**

~~~bash
export SCI_HOME="$(mktemp -d)"
export SCI_RUNTIME_DIR="$(mktemp -d)"
python -m pm.build_env --source . --out .venv --group dev --group test
.venv/bin/python -m sci_cli.main
~~~

Use the repository's bootstrap Python if python is unsuitable. The build output must
be fresh; do not replace an environment used by another process. Building can download
declared dependencies. Keep the temporary-home paths if you need to resume this test.
Use a separate terminal for your normal SCI installation.

Configure your test model and required service credentials through supported setup.
Do not copy your full personal state or secrets into the test home.

**SCI, for the standalone package:**

~~~text
/subagent package install <absolute-contribution-checkout>/subagent-catalog/my-specialist --name installed-specialist
~~~

**SCI, for the example team's parent instead:**

~~~text
/subagent package install <absolute-contribution-checkout>/subagent-catalog/table-team --name installed-team
~~~

Choose **Current owning profile**, review access and complete approved setup.
Install the parent once; SCI resolves its declared children. You do not need to
recreate them manually. Review any required hierarchy-depth prompt. Then enter:

~~~text
/new
~~~

Assign the actual fixture using absolute input/output paths, for example:

~~~text
/subagent run installed-team Analyze <absolute-fixture-path>. Use your approved children in the declared sequence, pass exact result artifacts between them, preserve the input, and return the requested counts, output paths and actual specialist run IDs.
~~~

For a standalone specialist, use its installed name and appropriate assignment.
If the command reports a queued assignment, follow the CLI prompt to start the
ordinary agent turn. Inspect the actual output files, not only the final answer.

### What to check

| Check | Evidence to look for |
| --- | --- |
| Expected behavior | Actual output content/counts match the fixture contract. |
| Portability | Renamed installation works without the original definitions/private paths. |
| Skills and services | Required skills/tools are actually used; catalog visibility alone is not execution evidence. |
| Hierarchy | Actual parent/child runs occur and dependent work receives exact preceding artifacts. |
| Missing input/setup | SCI requests needed input or identifies missing setup without substituting unrelated files/services. |
| Cancellation/recovery | Where relevant, outputs/job IDs survive and unfinished work resumes without duplicate scientific submissions. |
| Isolation | The original profile is unchanged; repeat in a differently named disposable profile when testing profile portability. |

Use /subagent history and /subagent status <run-id> to inspect runs. Try a second
fixture with different expected results. For hierarchies, also exercise missing
child setup and update/recovery where relevant. Record tests actually performed and
cases not covered; do not claim every OS, service or failure mode was verified.

### Record local evidence

After actual package tests, update each package's tests/validation.json. This example
shows the shape for the starter fixture. Replace its environment/checks with actual
observations; do not copy a passed status for unrun tests:

~~~json
{
  "package_id": "table-team",
  "package_version": "1.0.0",
  "local": {
    "status": "passed",
    "environment": "Replace with actual SCI version/commit, OS/architecture, backend, model/provider and integrations",
    "checks": [
      "Renamed parent installed with both children in an isolated SCI home.",
      "Actual child runs returned 3 data rows, 2 columns, 1 empty cell and 1 duplicate row for the starter fixture.",
      "The input remained unchanged and the review worker checked the reader artifact."
    ]
  }
}
~~~

Record child-specific observations in each child's evidence. Report limitations,
untested modes and charges; distinguish scientific charges from model usage. If a
test fails, fix the package and repeat the relevant tests before claiming it passed.

## 4. Open the initial PR to dev

**Terminal, in the contribution checkout, for a standalone package:**

~~~bash
git add subagent-catalog/my-specialist
git diff --cached
git commit -m "Add my-specialist specialist package"
git push -u origin subagents/my-specialist
~~~

For the example team, stage all three folders instead:

~~~bash
git add subagent-catalog/table-team subagent-catalog/table-reader subagent-catalog/table-reviewer
~~~

Use your actual branch/package names. Do not use `git add .`. Review the staged diff
for secrets, unrelated changes and generated artifacts before committing.

Open the GitHub PR with **base: dev** and your contribution branch as the head.
Use [the specialist PR template](../.github/PULL_REQUEST_TEMPLATE/subagent.md).
Include purpose, expected outputs, provenance/license, requirements, permissions,
credential names only, external data transfers, costs, limitations and actual tests.
List the hierarchy, child version requirements and versions exercised. Submit all
required new/changed packages together.

**Stop this stage at the open PR and report its URL.** Reviewers decide when it
merges. After merge, test the installed package and inform maintainers of the result.
No second evidence-only PR is required. Preparing a contribution does not itself
authorize merging or promotion.

CI checks format, portability, declared resources, evidence consistency, version
changes and controlled regressions. It never executes contributed fixture scripts
or uses production credentials. Contributors remain responsible for their tests.

## 5. Test installation and execution from merged dev

After the initial PR merges, test the version available on dev in a fresh SCI
profile. On a test installation, use the normal updater in a terminal outside SCI:

~~~bash
sci update --branch dev
sci profile create subagent-dev-test
sci -p subagent-dev-test
~~~

Restart SCI after updating. The updater changes application code for all profiles
of that test installation; the fresh profile keeps test configuration and saved
specialists separate. Configure the model and required integrations through normal
setup. Do not copy creator definitions or authorization receipts.

Alternatively, use a separate merged-dev checkout and isolated environment as in
step 3. Launch that checkout explicitly instead of a global launcher pointing to
your normal installation.

Inside SCI, install the parent from the updated checkout's source folder:

~~~text
/subagent package install <updated-checkout>/subagent-catalog/table-team --name dev-team
/new
~~~

Choose **Current owning profile**, review access and complete normal setup. The
installer resolves the declared children. Use source folders at this stage;
release-catalog publication happens during main promotion.

Repeat the actual fixture assignments through dev-team and inspect the output
files, counts and child runs. Check input preservation and exact artifact handoffs.
If something fails, report it and submit a correction to dev, then retest the
corrected version. A successful installation alone does not establish execution.

## 6. Inform maintainers

Tell the maintainer whether installation and execution from merged dev worked,
and mention any failures or limitations. For example:

~~~text
Installed the merged-dev team in a fresh profile. Both fixtures produced the
expected files and counts through the reader and reviewer. No blockers observed.
~~~

Package/version and SCI commit information are useful when available. Detailed
receipts and integrated JSON records are optional supporting evidence, not a
second contributor task. **No evidence-only follow-up PR is required.** Preserve
existing local evidence and historical records; do not change pending records to
passed without actual results.

Maintainers use the contributor's confirmation and normal review to approve the
specific package versions. Record that confirmation in the promotion PR description.
When a child changes, review/test the affected parent's workflow as well; the
installer and catalog validator continue checking the complete dependency graph.

## 7. Maintainer promotion and release

Maintainers review the contributor's merged-dev test confirmation and select
approved package versions and their required shared fixes for a main-promotion branch. If dev contains unfinished work,
select the approved changes rather than merging the entire branch.

On that reviewed checkout, fetch history and use its PM interpreter to generate
and check the release snapshot:

~~~bash
git fetch origin main dev
git rev-parse origin/main
python scripts/validate_subagent_catalog.py --write-snapshot
python scripts/validate_subagent_catalog.py --base <full-origin-main-SHA> --promotion --check-snapshot
git add sci_cli/data/subagent_catalog.json
~~~

Replace the base placeholder with the full origin/main SHA printed above. The
checker validates package format, local evidence, published-version changes,
complete dependency graphs and a current release snapshot with integrity digests.
It does not require integrated JSON records or a second contributor PR. Maintainer
review confirms which tested versions and shared runtime fixes are being promoted.
Keep existing validation records unchanged unless reporting actual new results.

The validator is inert: it does not execute contributor code or scientific jobs.
Passing validates package consistency, not scientific accuracy.

Maintainers open/review the promotion PR to main, then release normally. Required
reviews and acceptance checks for dev/main are repository-admin settings; this guide
and local code cannot enforce them. This feature does not automatically merge,
release, activate services or grant recipients execution permissions.

## 8. Verify recipient installation and updates

After main acceptance, update the recipient's SCI to a build containing the approved
catalog. On another server or clean environment, without relying on the contributor's
source folders, run:

~~~text
/subagent catalog table-team
/subagent package install catalog:table-team --name my-team
~~~

Review access, complete recipient-owned setup and enter /new. Run the actual fixture
through my-team and inspect results/child runs again. This tests the distributed
package rather than only the local contribution folders.

For a later reviewed catalog update, first update SCI, then use:

~~~text
/subagent package updates
/subagent package update my-team
~~~

Review the new hierarchy and enter /new. Update the parent to review the combination
together; do not overwrite a managed child shared by another team. Customized local
definitions remain protected by the rename/cancel flow. Existing conversations
retain their current prompt/tool snapshots until a new conversation.

## Troubleshooting and handing off the work

| Symptom | What to check |
| --- | --- |
| Parent rejects children | Parent uses schema v2 and the running checkout has hierarchy-package support. |
| Child cannot be resolved | Its sibling folder matches its package ID, or it exists in the reviewed catalog; its version satisfies the requirement. |
| New specialist/tools are absent | Complete approved setup, enter /new, and verify the owning profile and actual launcher/checkout. |
| Service appears but cannot execute | Inspect required access, credentials and connection readiness; do not substitute another service silently. |
| Promotion says the snapshot is stale | Maintainers regenerate the release catalog after reviewing the selected package versions. |
| Only local tests are complete | Open the dev PR, then test the merged-dev installation and inform maintainers; no evidence-only follow-up PR is required. |

When handing this process to another person or coding assistant, provide **this
guide**, the owning profile, specialist names/hierarchy, approved fixtures/expected
outputs and the stage already completed. They should inspect the actual definitions,
follow the linked specification where needed, preserve working state and report
anything that could not actually be tested.
