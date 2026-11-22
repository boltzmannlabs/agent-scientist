# monoclonal-antigen-researcher

Research antigen identity, presentation, structural context and source conflicts.

Replaces the saved local definition `antigen-researcher-v2`. Part of the monoclonal antibody
research hierarchy for issue #21.

## Hierarchy

Leaf worker under monoclonal-research-coordinator (role: antigen_researcher).

## Setup

No credentials or external services are required for research and review work.
Workers use read/search/web/write tools only. The owning MAIN executor owns any
scientific execution; this package never submits jobs.

## Usage

Install the parent package `antibody-specialist`; children resolve automatically:

    /subagent package install <checkout>/subagent-catalog/antibody-specialist --name antibody-team

Then assign a monoclonal research or review task with authoritative input paths.

## Permissions

- Read/search/web tools for evidence gathering; write only to the assigned output directory.
- No scientific execution, no uploads, no credential use.

## Limits

- Research/review quality depends on supplied sources; no affinity or functional claims.
- Not tested on macOS/Windows or non-Linux backends.
