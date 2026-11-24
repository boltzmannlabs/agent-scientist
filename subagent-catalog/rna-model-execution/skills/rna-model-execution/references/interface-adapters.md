# Interface classes and thin adapters

Supported interface classes (from the spec's `runtime_requirements.inference_interface`):

| Class | Preferred path | Adapter rules |
|---|---|---|
| python_api | import in a small file-based driver script | driver written to workspace; pins from the environment receipt |
| cli | the repository's own entry point | invoke exactly as official instructions state; capture exit codes |
| pytorch | torch.load / model.eval() driver | device chosen from approved hardware; seeds pinned |
| hf_transformers | transformers pipeline/from_pretrained | revision pinned to the spec commit/tag; cache path recorded |
| docker | approved container runtime | only with parent container approval; image digest recorded |
| bioinformatics_cli | installed bioinformatics binary | version captured with `--version` before use |
| rest_or_mcp | parent-owned endpoint/connector | called through its contract; never self-hosted substitutes |

Adapter discipline: adapters are thin (argument marshalling only), file-based (never inline `-c`/`-e`), recorded in
the report (`inference_status.adapter_path`), and never alter the cloned repository. An adapter is not a fork: if the
official path cannot be adapted without changing model semantics, that is a BLOCKED stage with the reason.
