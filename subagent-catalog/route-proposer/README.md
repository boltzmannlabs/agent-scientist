# Route proposer

One saved LLM specialist proposes explicit, connected retrosynthesis graphs for an exact molecular target. It retrieves supporting public literature, preserves encoded stereochemistry and describes control origins or unresolved assumptions. Backend tools validate molecular structures, topology, limits and evidence receipts. These checks do not establish reaction feasibility, yield or experimental stereoselectivity.

## Contribution status

Version 0.6.0 pins the supporting plugin `krish-200212/retrosynthesis-specialists` to `8f22ee2da3bd0fb7ac548cc34372f7a724ffa377`. Official reviewed installation and deterministic Main/private-child/Main handoffs passed. Two fresh officially installed GLM-5.3 fixtures each returned one accepted hypothesis (121.78 seconds achiral; 127.42 seconds stereo), followed by host owner-backend API acceptance. Live parent-LLM selection was not tested; it was exercised separately with a deterministic provider. Backend setup and two proposed installer prerequisites were required. Chemical feasibility and lower cost remain unproven; exact merged-dev validation remains pending in `tests/validation.json`.

This standalone package has no children. The existing combined model-search workflow and Main default-routing integration are supplied by the supporting plugin, not by this specialist definition. Installing a leaf specialist alone does not establish that concurrent workflow integration works.

## Requirements and permissions

The specialist requires exactly these plugin tools: `read_retrosynthesis_task`, `inspect_target_stereochemistry`, `search_route_literature`, `validate_route_hypotheses`, and `verify_retrosynthesis_result`. Main needs an explicitly installed owner instance of the supporting plugin. The child dependency is private to the installed specialist; its receipt store is not the owner's store. The local integration introduces `accept_specialist_retrosynthesis_result` to resolve the saved specialist's reviewed private dependency and accept its receipt. This bridge is present in the pinned published dependency and its renamed private-child handoff was tested. The older owner `accept_retrosynthesis_result` call alone does not establish acceptance of a privately installed child's receipt. A recipient-owned Python backend with RDKit and jsonschema is needed; its actual supported versions and setup must be verified in the clean installation. Scope currently targets Linux amd64 only. No other platform is claimed tested.

The LLM provider/model is recipient-configured and must support tool calls. Model requests may include target structures, route hypotheses and retrieved excerpts. Literature queries contact Europe PMC public services; the plugin can retrieve available article context. Provider credentials and any scientific-service credentials are recipient-owned and must use supported setup. No credentials, private profiles, inventory, run history, or machine paths are distributed.

Model inference may incur provider charges. The standalone proposer does not submit model-based scientific search jobs. The separate combined workflow may incur scientific-service charges and has its own authorized setup. Unknown token usage and cost remain unknown.

## Installation and use

Use a fresh profile and the reviewed `/subagent package install` flow, installing under a different local name. Complete required setup, start `/new`, then assign each fixture through `/subagent run <installed-name> <assignment>`. Pass fixture contents or an approved input path through Main; the leaf has no general filesystem tool.

For an immutable task assignment, the child reads the task ID and validates against its original bounds. For direct delegation it first inspects the exact target. It returns the backend verification envelope unchanged. For the local bridge integration, Main calls `accept_specialist_retrosynthesis_result` with `specialist` set to the actual installed name (including a local rename), `final_envelope` unchanged, and the original `target`, `requested_count`, `max_depth`, and `max_total_reactions`. It must not adopt limits chosen by the child or supply an arbitrary receipt-store path. The owner plugin and recipient backend must be configured explicitly. The published pin and clean-install handoff checks are complete; configure the owner plugin explicitly and test your recipient environment.

## Test contract

`tests/achiral-input.json` checks a general synthesis task; `tests/stereo-input.json` checks an exact enantiomer; `tests/missing-target-input.json` checks that missing identity is requested. Expected files list observable assertions. Route counts are upper bounds: empty proposals are valid and must never be padded.

Record actual run IDs, provider/model, timing, verification receipts, route counts, failures and output locations in a redacted test report. Inspect actual artifacts; do not infer success from a final chat summary. Test renamed installation, unavailable dependencies, cancellation and duplicate-submission avoidance for the combined workflow. Run fake-provider backend tests separately from live model tests. `tests/validation.json` records exact-published installation, native handoff and fresh live fixture checks, with future merged-dev validation pending. The live owner acceptance used the host backend API; parent model tool selection was a separate deterministic test. Reasoning prose, Markdown fences, an invalid envelope, or a failed provider call must fail strict host acceptance and must not be reported as a passing generation fixture. A valid empty response is contract completion, reported separately from nonempty route generation. Old local-profile runs do not establish portability or this version's correctness.

## Provenance and limitations

Author: Gopi Krishna. Package license: MIT, matching the existing local package declaration. The supporting plugin source was published separately; the pinned revision includes the tested bridge and compact-handoff changes. No article full text or third-party datasets are bundled. Retrieved quotations and references must retain their source identity and comply with source terms.

Literature retrieval is bounded and may miss relevant papers or patents. Stock and prices are unknown unless a configured backend inventory or sourced record supplies them. The specialist may return fewer routes or no route. Graph consistency, stereo declarations and text binding do not prove chemical feasibility. Live service/model failures must be reported explicitly.

## Observed outputs

`tests/observed-results.json` bundles exact fresh observed proposals, model/timing/token provenance and the missing-target reply. These observations are not executable fixtures or experimentally validated routes. The achiral rationale contains unsupported quantitative/high-yield language; graph acceptance does not validate those assertions. A fresh concurrent run preserved two model routes and added one unique unassessed proposal (three selected), in682.37seconds with115.99seconds overlap. No chemical/cost improvement or controlled speedup is claimed. The original failure-isolation trial remains recorded. Exact merged-dev validation is pending.
