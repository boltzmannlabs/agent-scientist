# Contribute a specialist or specialist hierarchy

Start here after creating and testing saved subagents in SCI. Follow these same
steps whether you prepare the contribution yourself or ask a coding assistant to
help. A team follows the same process as a standalone specialist.

**Create and test in SCI → prepare package(s) → test installed packages → PR to dev
→ test merged dev → record evidence → maintainer promotion to main.**

| Stage | Who does it | What establishes completion |
| --- | --- | --- |
| Create specialists | Contributor | Saved specialists perform the intended assignment in SCI. |
| Package and test | Contributor | A fresh installation works without the creator's private state. |
| Submit to dev | Contributor, then reviewers | Package PR is reviewed and merged into dev. |
| Test merged dev | Contributor | Actual results are recorded against the exact merged dev commit. |
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
   "not_run" and integrated status "pending".

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
parent's direct tools. Use automatic: false for workers intended only for approved
parent delegation or explicit assignments. Children may themselves declare children;
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
  },
  "integrated": {
    "status": "pending",
    "tested_commit": null,
    "environment": "",
    "checks": []
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
merges. Keep integrated evidence pending until merged-dev testing is complete.
Preparing a contribution does not itself authorize merging or promotion.

CI checks format, portability, declared resources, evidence consistency, version
changes and controlled regressions. It never executes contributed fixture scripts
or uses production credentials. Contributors remain responsible for their tests.

## 5. Test the merged dev revision

After the initial PR merges, create a separate checkout of merged dev.

**Terminal, from a repository checkout:**

~~~bash
git fetch origin dev
git worktree add --detach ../agent-sci-dev-validation origin/dev
cd ../agent-sci-dev-validation
git rev-parse HEAD
~~~

Save the **full 40-character commit SHA**. In this dev checkout, repeat the fresh
environment setup from step 3 and launch .venv/bin/python -m sci_cli.main. Do not
test through a global launcher that still runs your normal main installation.

In that SCI session, use /subagent catalog to select the package, or install it
directly:

~~~text
/subagent package install catalog:table-team --name dev-team
~~~

Choose **Current owning profile**, complete approved setup, then enter /new.
Repeat the actual fixture assignments through dev-team, including child delegation
and output inspection. For a standalone package, use its own ID/name. Record the
commit, package versions, environment, integrations, observed results and costs.

If anything fails, submit a correction to dev, wait for its merge and test the new
merged revision. An earlier local installation is not evidence for the new dev
revision. Any execution-content change after testing requires relevant retesting.

## 6. Submit merged-dev evidence

After successful integrated testing, update each affected package's validation file
through a **follow-up PR to dev**. Preserve local evidence and fill the integrated
section with actual observations:

~~~json
{
  "status": "passed",
  "tested_commit": "<actual full 40-character tested dev SHA>",
  "environment": "<actual SCI, OS/architecture, backend, model/provider and integrations>",
  "checks": [
    "<actual integrated check and observed result>",
    "<another actual check>"
  ]
}
~~~

Replace only the existing integrated object with your actual values, keeping the
package identity and local evidence in the surrounding JSON file.
Use the exact package ID/version. The tested commit must exist in fetched origin/dev
history. Do not substitute an untested PR branch SHA or invent results.

Base the evidence PR on current dev. Stage only the appropriate validation files.
Evidence-only updates need no version bump. Changes to instructions, skills,
dependencies, fixtures or other execution content require a version increase and
new tests.

A compatible child update changes the parent's tested workflow even when its own
source/version stays unchanged. Retest every affected parent on the new merged dev
revision and update its evidence too. Promotion checks the full reachable hierarchy
against that parent's exact tested commit.

**Stop at the evidence PR and report its URL.** Maintainer acceptance and main
promotion are separate stages.

## 7. Maintainer promotion and release

Maintainers review exact-dev-commit evidence, perform final acceptance and select
approved changes for a main-promotion branch. If dev contains unfinished work,
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
checker requires passed local/integrated evidence, a tested commit in dev history,
matching execution content and a current snapshot. For a parent, this includes its
children/grandchildren, even when only a descendant changed. Validation evidence
and generated integrity files are excluded from the execution-content comparison.
Release snapshots include actual versions and integrity digests.

The validator is inert: it does not execute contributor code or scientific jobs.
Passing checks evidence consistency, not scientific truth.

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
| Promotion says evidence is stale | Compare parent/child content with the recorded dev commit and retest the changed workflow. |
| Only local tests are complete | Open the initial dev PR with integrated evidence pending; test integrated behavior after merge. |

When handing this process to another person or coding assistant, provide **this
guide**, the owning profile, specialist names/hierarchy, approved fixtures/expected
outputs and the stage already completed. They should inspect the actual definitions,
follow the linked specification where needed, preserve working state and report
anything that could not actually be tested.
