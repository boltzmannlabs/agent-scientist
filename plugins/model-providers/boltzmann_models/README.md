# Boltzmann models

This bundled provider uses the same profile-local account as the Boltzmann
scientific tools. It does not require a separate model API key.

1. Run `/boltzmann_login` and authenticate your account.
2. Open `/model` (or `sci model`), choose **boltzmann_models**, then choose
   a model from the gateway's authenticated `/v1/models` catalog, including
   **discoveryrsi-q4ks** when advertised by your gateway.
3. Confirm the model selection. Saved defaults apply to new conversations;
   `/model` uses the existing explicit conversation-switch flow.

The selected ID is sent as `model`, for example `"model": "glm"`. There is no
additional `provider` request field. Responses may identify the underlying
deployment with a different model name. This integration uses Chat Completions
for gateway model routes, including `codex`; it does not use Codex OAuth.

The gateway controls the model list. SCI uses its existing credential-scoped
catalog cache and validates inference against that catalog. Setup refreshes the
list; an unavailable catalog with no cached models blocks selection or execution
instead of silently substituting a fixed model list. Context/output limits use
the exact selected ID's gateway metadata or configured limits; missing limits
are labeled as estimates, never copied from another deployment alias.

## Authentication and profiles

Each inference request checks the owning profile's saved `BOLTZMANN_API_KEY`, its
authorization receipt, and the account-verification service. Missing or rejected
authorization stops the request. A main-profile key is not inherited by another
profile. Specialists use their owning profile's model account without copying
the key into their private workspace. Background title/compression clients retain
the same authorization checks, including asynchronous clients.

There is no automatic switch to another account or provider after a failure.
Removing or replacing the key is checked again on the next request, including
requests using an already-created client. Login enables scientific tools for a
new conversation; choosing a model is a separate explicit action.

## Responses, usage and credits

- SCI reads the assistant answer from `choices[].message.content` and executes
  supported structured `tool_calls` through its existing permission checks.
- The gateway currently accepts **non-streaming JSON only**. SCI waits for the
  full response and adapts it to its existing renderer; tokens are not delivered
  incrementally by the server.
- Provider-reported token usage, including cached/reasoning counts when returned,
  uses SCI's existing usage reporting. Thinking visibility follows SCI's display
  setting; this integration does not enable thinking display.
- Completions return `billing` and `account` alongside the answer and token usage.
  The post-response footer shows only token input/output/total, available credits,
  and input/output/total credits, with a hint to use `/usage` for details. Provider
  and email are shown in `/usage`. These counts and charges
  come from the same latest response. `Available Credits` is the returned
  `account.credits` value, without subtracting frozen credits.
  `/usage` retains frozen credits (`freezedCredits`), billing status, pricing
  model, currency, cached/uncached input counts and cache-data source.
  Credit amounts display with two decimal places. SCI uses the returned amounts;
  it does not calculate prices, subtract frozen credits, or submit a deduction.
- The gateway ignores `max_tokens` on `codex`. SCI omits that unsupported field;
  output limits for this route are server-managed. Reasoning-effort controls are
  not sent because the gateway does not declare a contract for them.

## Billing ownership

SCI does not calculate model-credit prices, POST credit deductions, reserve
billing space, reconcile old receipts, or block model requests because of an
old client-side billing record. It forwards authorized model requests and reports
provider token usage. Billing status is shown exactly as reported: `submitted`
is not relabeled `confirmed`, and missing values are not invented.

The latest response summary stays in memory, scoped to the owning profile,
gateway URL and credential. It is a snapshot of that response, not a live balance
or a conversation total. Background calls may become the latest response too;
the request ID and model identify which one is shown. Missing metadata in a later
response clears the old summary. Before any such response, or after a restart,
the existing read-only authentication lookup supplies account details instead.
No extra account request is made to display a gateway-provided summary.

The gateway owns deduction. Existing client ledger files and already confirmed
deductions remain untouched; they are not refunded, deleted, or replayed.
Restart SCI to load this response display and unload any older billing code.

The exact approved rate card, token rules, rounding, wallet API contract, examples,
server implementation requirements and cutover checklist are in the
[gateway billing handoff](../../../website/docs/developer-guide/boltzmann-gateway-billing.md).

## Endpoint configuration

The supplied gateway defaults to `https://sciagent.boltzmann.co.in/v1`; the CLI host must
be able to reach it. Configure a replacement endpoint in the owning profile's
`config.yaml` before selecting the model:

```yaml
providers:
  boltzmann_models:
    base_url: https://sciagent.boltzmann.co.in/v1
```

The URL must not contain credentials, query parameters or fragments. Existing
clients reject an endpoint change until the provider is selected again. Keep the
API key in the profile's secret storage, never in this configuration or prompts.
