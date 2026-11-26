# Portable specialist packages

Use packages to contribute a specialist created in main or a profile through a PR,
and recreate it on another server without copying credentials or machine state.
The old `/subagent export` and `import` remain **definition-only**; they deliberately
strip private integrations/references. Contributors prepare source packages using the documented format; `package` commands are for recipient installation and updates.

## Commands

| Command | Purpose |
| --- | --- |
| `/subagent package` | Catalog, installation and update menu |
| `/subagent catalog [search]` | Search/paginate this release's catalog and select installation |
| `/subagent package install <path-or-catalog:id> [--profile main\|name] [--name local-name]` | Review installation; destination picker by default |
| `/subagent package updates` | Read-only comparison with this release's catalog |
| `/subagent package update <local-name> [path-or-catalog:id]` | Reviewed update/resume in the active owning profile |

After successful install: `/new`, then `/subagent run <name> <assignment>`.
A ready, enabled package supports both automatic matching and explicit requests.
Updates take effect next conversation; current prompts/tool snapshots stay unchanged.

## Storage and files

A contribution folder contains `manifest.yaml`, `instructions.md`,
complete `skills/<name>/` bundles, approved `references/`, `tests/` fixtures, `tests/validation.json` evidence and README. Contributors do not generate integrity locks or the shared release snapshot; maintainers generate those internally.
See `contribution-templates/subagent/` for an editable starter. The distributed catalog starts empty until approved contributions are added.

Runtime files remain profile-local:

```text
<SCI_HOME>/subagents/<local-name>.json
<SCI_HOME>/subagent-data/<new-local-id>/
    config.yaml          # local private setup
    .env                 # recipient secrets, when needed; never exported
    package/             # reviewed source package
    skills/ plugins/ tools/ workspace/
<SCI_HOME>/subagent-runs/ # receipts; never distributed
```

A named native profile has its own SCI_HOME. A portable package does not require the recipient
to have the originating profile. Install generates IDs, resolves local paths, creates
fresh credentials/authorization and stores package ID/version/digest plus readiness.
Instructions, service access and source reading are reviewed separately.

## Declaring dependencies

Declare dependencies directly in `manifest.yaml`, not in a contributor's live config.
The top-level manifest fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer 1 for existing packages, or 2 for hierarchy-capable packages |
| `id`, `name` | Stable package ID and suggested local name; lowercase identifier |
| `version` | Quoted semantic version; bump for substantive content changes |
| `authors`, `license`, `description` | Attribution, redistribution license and purpose |
| `sci_requires` | SCI version requirement, for example `'>=0'` |
| `instructions`, `output` | Relative instruction file and expected output contract |
| `tools` | Exact required tool names; MCP aliases use `mcp:<dependency-id>/<raw-name>` |
| `skills` | Existing maintained skills or complete privately installed package skills |
| `skill_files` | Optional `<declared-skill>#<relative-module-file>` selections |
| `dependencies` | Program, plugin, MCP and/or Boltzmann requirements described below |
| `references` | Approved relative files/public URLs, label, license and access mode |
| `limits` | Positive `max_iterations`; v2 accepts `timeout_seconds: 0` for no overall deadline. V1 retains positive timeouts. |
| `platforms` | Nonempty supported platforms, e.g. `[any]` or `[linux-amd64]` |
| `fixtures` | Nonempty input/expected JSON file pairs with optional description |
| `automatic` | Legacy optional boolean; all ready, enabled specialists support matching tasks and explicit requests, including packages declaring `false` |
| `children` | V2-only list of role, package ID and compatible version requirements |

Unknown fields are rejected. Nonempty `children` is unsupported in v1; `unresolved` marks a
noninstallable draft and must be cleared by supplying real requirements before a PR.
Use the starter manifest as a complete syntactically valid example.

## Package hierarchies

The existing create → prepare package → local test → PR to dev → test merged dev →
promote to main process also applies to a team of specialists. Each specialist has its
own package. A schema-v2 parent declares its approved children, for example:

```yaml
schema_version: 2
# Other required fields remain as described above.
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
```

Use `{{child.reader}}` and `{{child.reviewer}}` in instructions or skill text to refer
to the installed local names. A parent must declare `delegate_task`. Each child declares
its own tools, skills, references and setup dependencies; those capabilities do not become
the parent's direct tools. Children can themselves declare children. Role names are unique
within their parent; several roles or parents may reference the same package.
Workers support automatic matching and explicit assignments by default. A parent can invoke
only its approved children; automatic matching does not expand that hierarchy grant.

Install the parent through the existing command:

```text
/subagent package install catalog:table-team --name my-team
```

SCI resolves child IDs against the reviewed release catalog. For local source testing,
place child folders beside the parent's folder using their package IDs as folder names.
A standalone parent ZIP requires its children in the release catalog. No arbitrary remote
package lookup or contributed setup script is introduced. The catalog supplies one version
per ID; all declared ranges must accept that version. Missing packages, incompatible ranges,
invalid relationships and cycles are reported before setup starts.

Review shows the complete tree's package versions/digests. Dependencies are prepared before
parents, using the existing capability and credential consent flows. A renamed parent works:
local child names are generated without overwriting conflicting specialists, and instruction
tokens are bound to the actual names. An unchanged, ready managed child with matching content,
grants and relationships can be reused. An unrelated same-named specialist is never adopted.

Definitions are published children first and parent last, after review. Cancelling preparation
does not replace existing definitions, though approved downloads/private setup may remain as
reported. Missing setup leaves a newly installed parent disabled. Retrying can reuse its
retained setup. An incomplete update preserves the previously working team. Updated children
use new local definitions rather than overwriting a child used by an existing team. Superseded
children and artifacts remain available; this operation does not delete them.
Updating a child directly does not overwrite a definition referenced by another
specialist. Update the parent hierarchy or install the child under a new local name.

The existing hierarchy review offers the required delegation depth if necessary. Changes
apply to new conversations after `/new`; current prompts and tool snapshots remain unchanged.
Normal runtime delegation uses the saved approved children. Missing, disabled,
or independently replaced child packages produce an explicit hierarchy/setup error rather than a
silent role substitution. This distributes existing saved children; it does not create new
temporary role definitions dynamically during a task.

Reviewed local instruction customizations retain their normal execution behavior. They are
not silently reused or overwritten as pristine catalog definitions during package updates.

When a compatible child changes but the parent source/version does not, `/subagent package
updates` can report a hierarchy update. Updating the parent reviews that new combination.
Customized local definitions remain protected by the existing rename/cancel flow.

For promotion, maintainers review the merged-dev confirmation for the complete
reachable hierarchy, including affected parents when a child changes. Detailed
integrated test records are optional. Catalog checks still resolve compatible child
versions and verify the generated release snapshot for that reviewed combination.

## Service and program requirements

An existing skill uses `{id: 'provider:skill', kind: existing}` with optional `sha256`
of its skill-view text. A custom skill uses `{id: my-skill, kind: package,
path: skills/my-skill}`; its SKILL.md frontmatter name must match. Include every
supporting file. Never include a copy of installed runtime state or authorization.
Built-in tools use their identifiers and must be enabled/available in the recipient's
scope. Missing setup is reported honestly; catalog membership grants no permissions.

Programs use a recipient-selected executable or an explicitly approved HTTPS artifact.
Declare version/check arguments and expected version output. Downloads require exact
SHA-256, format `file`, `zip` or `tar.gz`, platform such as `linux-amd64` or `macos-arm64`,
and relative executable path. Lookup is never automatic executable installation.
Version checks execute code and receive separate approval. No shell bootstrap runs.

For a private SeqKit workflow, include this in the manifest and use the program
token in instructions. The contributor prepares these files manually:

```yaml
platforms: [linux-amd64, macos-arm64]
dependencies:
  - id: seqkit
    kind: program
    version: '2.14.0'
    version_args: [version]
    version_contains: '2.14.0'
    artifacts: []  # recipient selects an installed executable
```

For downloadable software an artifact is an object with `platform`, public HTTPS `url`,
exact `sha256`, `format` and relative `executable`. Never invent hashes/version evidence;
use the verified supplier information. Optional dependencies use `optional: true`;
if a tool is also listed as required in `tools`, that required tool must still be ready.

Use `{{program.id}}`, `{{program.id.dir}}`, `{{workspace}}`,
`{{resource.references/file.md}}` and `{{tool.connection.raw_tool}}` in instructions
or skill files. These are rendered into recipient-local paths/names during setup.
Fixtures remain inert data; expected JSON values are reviewable assertions, not
an automatic arbitrary-code test runner.

MCP dependency example:

```yaml
- id: literature
  kind: mcp
  tools: [search_papers]  # exact names, never wildcard grants
  config:
    url: https://approved-service.example/mcp
    headers:
      Authorization: 'Bearer ${LITERATURE_API_KEY}'
```

Manifest tool reference: `mcp:literature/search_papers`. The installer offers an
explicitly selected existing account/template or a new private connection. It uses
native masked credentials/OAuth and approved handshake/discovery; it does not call
business tools. OAuth requires a fresh profile-owned sign-in. Selecting a different
existing service is a recipient review decision; names alone do not verify scientific
semantics. New server tools are not automatically granted. Check changed remote
schemas/service behavior during service review; package checksums do not pin a remote
server's implementation.

Plugin requirements declare `kind: plugin`, public HTTPS `source`, exact 40-character
commit `revision`, required `tools` and `skills`. Setup reuses native source scanning,
PM dependency admission, capability consent and credential prompts. Plugins have
whole-plugin host access; per-tool selection is not a process sandbox. Third-party
plugin source belongs in its own repository, not copied into every specialist.

The `route-proposer` package can request a second installation of its reviewed
support plugin in Main's scope with `owner_workflow: true`. This is a specific
supported integration, not a general install hook. Review the separate owner
permission: it enables the combined workflow, which can submit a scientific job
and invoke the active model. The child keeps its five private tools. Use a fresh
profile if an owner installation or configuration already exists; the installer
does not replace it silently. Service authentication remains profile-specific.

MCP commands should use portable names or declared program/resource tokens. Arbitrary
interpreter/package-runner commands are displayed and require execution consent.

Boltzmann requirements declare `kind: boltzmann`, optional exact `contract_sha256`
and maintained `modules: [references/modules/<module>.md]`. Contributors specify the maintained modules actually used, selected `boltzmann:tools` skill and required helper tool names; do not copy keys/receipts. Add all five helper operations together. Recipients must authenticate and get a new
local authorization record; no contributor key/receipt is exported. All five connector
helpers are included together. **Module selection focuses instructions; it is not
an enforced scientific-workflow allowlist.** A mismatched pinned contract requires
review/update. Setup validates authorization, not scientific job execution or charges.

A concrete maintained-module declaration (merge these keys into your full manifest):

```yaml
tools:
  - boltzmann_upload
  - boltzmann_submit
  - boltzmann_status
  - boltzmann_download
  - boltzmann_fetch_tool_log
skills:
  - id: 'boltzmann:tools'
    kind: existing
skill_files:
  - 'boltzmann:tools#references/modules/protein-optimization.md'
dependencies:
  - id: boltzmann
    kind: boltzmann
    modules: [references/modules/protein-optimization.md]
```

Choose only maintained module paths that actually support the specialist's work. This
example declares a module dependency, not a scientific input/payload or an authorization
to submit jobs. For other tools, never invent job names or service schema fields.

Reference examples, in the manifest's `references` list:

```yaml
references:
  - path: references/checklist.md
    label: Approved checklist
    license: Company-authorized redistribution
    required: true
    mode: snapshot
  - url: https://approved-source.example/document
    label: Public source
    license: Source terms permit this use
    required: false
    mode: original
```

Use real approved public URLs, not these illustrative example domains. Do not submit
signed links or links with account tokens. A recipient must separately approve source
reading/model transmission; copying a URL into a package is not blanket access consent.

## References, safety and readiness

Only explicitly approved redistributable references are included; preserve attribution.
Use `mode: original` for an approved PDF/binary document that must remain original;
`snapshot` reads supported text through existing source handling. Large readable
collections use the existing on-demand reference library. Mark mandatory references
`required: true`; skipping one keeps setup incomplete. There is no implicit upload,
indexing or private-dataset redistribution. Automatic credential/path detection is
not exhaustive, especially inside binary documents; manually review every resource.

Validation rejects unknown schema fields, secrets it recognizes, machine-home paths,
unsafe ZIP entries, symlinks, hidden/runtime state, ambiguous tool grants and missing
resources/checksums. Limits are 50 MiB and 1,000 files; use reviewed external artifact
requirements for larger software. No pickle/model binary is executed during validation.

Required failures/deferred authentication produce **setup_required**, with a disabled
specialist and retained source/dependencies. The runtime refuses to bypass this through
a generic enable operation. Retry a saved setup-required install/update to resume, reviewing grants. An unsaved cancelled staging directory is retained for manual review; it is not automatically trusted or activated.
Ready means required local setup checks passed, not a scientific guarantee. Handshake,
version probe and actual workflow/output validation are different verification levels.

Cancellation/failure can retain approved downloads, credentials and private directories;
the installer reports their location. There is no automatic destructive rollback,
uninstallation or background business-job submission. The final definition is saved
with a revision check. Concurrent package operations are serialized per destination.
Updates use a new private generation and retain old files; they never uninstall shared
software, erase histories or silently expand access. Locally modified definitions or
private setup require review/another installation name.

Schema v1 rejects child-specialist pipelines and cannot provision local-program
dependencies on remote/Docker backends; it preserves the selected backend and reports
setup required. Generic plugin checks cannot certify arbitrary SaaS authentication.
Live service behavior, scientific suitability and license/redistribution rights require
separate review. Removed catalog entries stop new catalog installs; existing users keep
their files and must explicitly disable/delete them if needed. There is no silent remote
revocation policy.

## Demo and PR

Copy `contribution-templates/subagent/` to your own `subagent-catalog/<id>/`, edit its
identity, instructions, requirements and fixtures, and test with
`/subagent package install "/full/path/to/your-package"`. Choose the destination,
review setup, save, start `/new` and assign the prepared fixture. The starter's sample
CSV illustrates three data rows, two columns, one empty cell and one duplicate row;
replace these with meaningful checks for your own specialist. No example is installed
or offered in the released catalog automatically. Use `/subagents` and
`/subagent status <run-id>` for local definitions and results.

Follow [the contributor checklist](../../../../subagent-catalog/README.md) in the repo.
In a separate checkout based on dev, add only the package folder and actual test evidence. Maintainers
review scientific behavior and permissions, and run clean installs plus approved canaries.
Git merge distributes inert catalog data; it never copies employee credentials or enables
services for recipients. SCI's normal release/update distributes the catalog; installation
and managed specialist updates remain explicit user choices.


## Company PR and acceptance process

Follow `subagent-catalog/README.md`: prepare and test locally → PR to **dev** →
merge and test installation/execution from merged dev → inform maintainers →
maintainer review and promotion to **main** → release. A successful merged-dev test
can be reported directly to the maintainer. No evidence-only follow-up PR is required.
Submit corrective code/package PRs when a test exposes a problem.

`tests/validation.json` identifies `package_id`, `package_version` and local test
evidence. Local evidence needs `status: passed`, a nonempty `environment` and a
nonempty `checks` list of checks actually performed. Integrated records are optional
supporting information; existing pending/historical records need not be rewritten.
Never invent successful results. The maintainer records the team's confirmation in
the promotion PR description and reviews the specific versions being shipped.

CI retains package/source validation, published-version rules, dependency checks
and release snapshot freshness/integrity. It does not gate main promotion on an
integrated JSON receipt or exact tested-commit field. When content changes after
testing, review and test the relevant behavior before approving that new version.

The developer-side internal validator remains available to maintainers/CI; no export,
seal or validation slash-command workflow is provided to contributors. Generated
snapshots belong to main promotion/release, reducing shared-file PR conflicts. The
recipient installer still validates every package internally before granting access.
