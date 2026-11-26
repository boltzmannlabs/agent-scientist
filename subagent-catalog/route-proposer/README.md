# Literature-supported retrosynthesis route proposer

This standalone specialist proposes additional routes for an exact target while REBOLT runs its normal search. It uses retrieved literature, identifies stereochemical assumptions, and submits each hypothesis for backend verification. The two branches do not share predictions during generation.

## Install and use

Install the catalog package in a recipient profile using the reviewed subagent installer. Review both scopes: the specialist receives five private tools; Main needs separate permission to start and poll the combined scientific workflow. Use a host installer that recognizes the manifest's `owner_workflow` declaration. Provide the profile's normal model and scientific-service authentication. Neither credentials nor machine-specific runner paths belong in this package.

Start `/new` and give Main an ordinary request:

> Run retrosynthesis for vanillin (COc1cc(C=O)ccc1O) and show me the routes.

Main should start one combined workflow and return a workflow ID. Each new job uses the current conversation's model and provider. Changing that selection applies to the next new job; an active job keeps its original settings. The proposer receives only its own earlier proposals as feedback. It keeps attempting distinct routes while the model search is pending, with no elapsed-time limit on the workflow or proposer rounds. When search ends, it keeps completed verified hypotheses and stops unfinished work. No second model selection is required.

Poll `retrosynthesis_workflow_status` with the workflow ID. Inspect the two branch statuses and the recorded overlap. A successful start, a direct model job ID, or a standalone specialist run on its own does not demonstrate that both branches completed. Missing setup or service authorization should be reported; do not launch another search as an automatic fallback.

## Permissions, costs and limits

The private tools are `read_retrosynthesis_task`, `inspect_target_stereochemistry`, `search_route_literature`, `validate_route_hypotheses`, and `verify_retrosynthesis_result`. The specialist itself cannot submit a scientific job. Main resolves the reviewed installation, including its saved name, and verifies receipts against original bounds. Depth and total reactions are separate limits.

Linux amd64 is the tested platform. RDKit and jsonschema are required for backend validation. The configured model provider can receive the target, proposals and literature excerpts. Europe PMC receives literature queries. The scientific service receives retrosynthesis requests. Model calls and scientific jobs may incur charges. Repeated rounds can use more tokens than a single assignment. No stock, price, yield or laboratory outcome is implied by a verified graph.

## Evidence

The achiral, stereochemical and missing-target fixtures in `tests/` describe observable results. Empty verified output is valid. `tests/validation.json` distinguishes local validation from later testing on a merged dev commit. `tests/observed-results.json` is historical output from the earlier 0.6.0 contribution, not a new run of this version.

Author: Gopi Krishna. License: MIT. The supporting plugin revision is pinned in `manifest.yaml`.
