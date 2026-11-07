---
title: Boltzmann model billing — gateway handoff
description: Approved credit prices, usage calculation, wallet API, and migration from SCI client billing.
---

# Boltzmann model billing — gateway handoff

This document preserves the approved gateway billing rules from the removed SCI
implementation and documents the response metadata consumed by SCI. The supplied
gateway sample reports `billing.status: "submitted"`; SCI displays that status
without independently asserting wallet settlement.

## Current implementation state

- SCI client-side model-credit calculation and deduction have been removed.
- The SCI client does not call `agent-update`, reserve billing space, settle old
  receipts, or block inference because an old client receipt is unresolved.
- Boltzmann login, profile authorization, the four model routes, sync/async model
  clients and token-usage reporting remain. SCI displays `billing` and `account`
  directly from model responses, with read-only balance lookup when no response
  metadata is available.
- Historical client ledgers and their backups remain on disk for audit. Removing
  code does not refund or repeat a previously confirmed deduction.
- No gateway, wallet service, or model-server configuration is changed by this
  client integration. Model-credit deductions are the gateway's responsibility.
  Restart running SCI processes to unload old client billing code.

## 1. Billing scope and model mapping

Charge for each completed, billable model API response obtained through the
Boltzmann model gateway. One user task may require several API responses: an
initial tool call, a continuation using tool results, a specialist, title
generation, or compression. Account for each real model response once.

Do not charge again for rendering an answer, reading `/usage`, listing models,
verifying an account, polling a receipt, or resuming a stored conversation.
Scientific job fees are a separate platform concern and must not be added again
as LLM token charges. Other providers used outside Boltzmann are outside this policy.

Use a server-controlled routing table:

| Client `model` | Gateway/provider deployment may report | Approved pricing key |
|---|---|---|
| `glm` | `glm-5.3` | `glm-5.3` |
| `codex` | `codex` or a deployment ID | `gpt-6.1-terra` |
| `qwen` | `qwen3.8-27b` | `qwen3.8-27b` |
| `discoveryrsi` | `discoveryrsi-27b` | `discovery-rsi` |

The Codex pricing mapping is explicitly approved. It is a business pricing key,
not proof of which underlying deployment executed a request. Record the route,
actual returned model, and pricing key separately. Do not accept a client-supplied
price, discount, billing exemption, or arbitrary pricing-model override.

## 2. Approved rate card

**1 INR = 1 credit.** All prices below are already in INR. The supplied exchange
rate, `94.14 INR/USD`, is historical rate-card metadata; do not multiply these
prices by that exchange rate again.

**Input is priced per 1,000,000 tokens. Output is priced per 100,000 tokens.**
Using one million as the output denominator would undercharge by a factor of ten.

| Pricing key | Cached input / 1M | Uncached input / 1M | Output / 100K |
|---|---:|---:|---:|
| `glm-5.3` | 6.49 credits | 6.58 credits | 13.18 credits |
| `gpt-6.1-terra` | 4.71 credits | 94.14 credits | 47.07 credits |
| `qwen3.8-27b` | 1.88 credits | 3.77 credits | 21.65 credits |
| `discovery-rsi` | 1.88 credits | 3.77 credits | 21.65 credits |

Equivalent rate-card data:

```json
{
  "currency": "INR",
  "credits_per_inr": 1,
  "exchange_rate_usd_to_inr": 94.14,
  "pricing_unit": {
    "cached_input": "1M tokens",
    "uncached_input": "1M tokens",
    "output": "100K tokens"
  },
  "models": {
    "glm-5.3": {"cached_input": 6.49, "uncached_input": 6.58, "output": 13.18},
    "gpt-6.1-terra": {"cached_input": 4.71, "uncached_input": 94.14, "output": 47.07},
    "qwen3.8-27b": {"cached_input": 1.88, "uncached_input": 3.77, "output": 21.65},
    "discovery-rsi": {"cached_input": 1.88, "uncached_input": 3.77, "output": 21.65}
  }
}
```

Construct decimal values from exact strings or use an exact decimal money type.
Keep the rate card and policy version on the server. The former client's rate
identifier was `boltzmann-inr-v1`; `boltzmann-inr-v2` added the approved missing-cache
policy without changing prices. Version any future pricing or rounding change.

## 3. Trusted usage and token normalization

Use usage returned by the upstream provider to the gateway, never usage supplied
by a client, an assistant's prose, character counts, or an estimated tokenizer.

For the current OpenAI-compatible Chat Completions routes:

```text
P = usage.prompt_tokens                 # total input, including cached input
O = usage.completion_tokens             # output, including reported reasoning
C = reported cached input tokens
U = P - C                              # uncached input
```

Accepted total-input aliases are `prompt_tokens` and `input_tokens`; output
aliases are `completion_tokens` and `output_tokens`. Multiple reported aliases
must agree. Counters must be non-negative integers; booleans, fractional values,
negative values, malformed details, and conflicting counters are invalid.

Recognize cached input from these equivalent fields when present:

- `prompt_tokens_details.cached_tokens`
- `input_tokens_details.cached_tokens`
- `cache_read_input_tokens`
- `prompt_cache_hit_tokens`
- `cached_tokens`

If only `prompt_cache_miss_tokens` is provided, derive `C = P - misses` and verify
that misses do not exceed input. If both hit and miss counts exist, verify that
they sum to `P`. A reported zero is a valid count, not a missing value.

Cache creation/write tokens are fresh input at the uncached rate. They are already
part of `U`; do not charge them as an additional input bucket. Recognized write
fields included `prompt_tokens_details.cache_write_tokens`,
`prompt_tokens_details.cache_creation_input_tokens`,
`input_tokens_details.cache_write_tokens`, `cache_creation_input_tokens`, and
`cache_write_tokens`. Validate that write counts do not exceed `U`.

`completion_tokens_details.reasoning_tokens` and
`output_tokens_details.reasoning_tokens` are breakdowns of output, not additional
output charges. Do not add them again. Likewise, `total_tokens` is a consistency
check (`P + O`), not a third billable bucket. Do not subtract output from a prompt
counter which already represents input.

### Approved missing-cache policy

If no cache count is reported, or details are null, **bill all input at the
uncached rate**: use `C = 0`, `U = P` for billing. Record
`cache_usage_source: "unreported_priced_uncached"` and show that assumption.
This is not a claim that the upstream server actually used no cache.

The observed DiscoveryRSI response shape was:

```json
{
  "prompt_tokens": 18587,
  "completion_tokens": 342,
  "total_tokens": 18929,
  "prompt_tokens_details": null,
  "completion_tokens_details": null
}
```

This shape follows the approved uncached-input policy. Missing input/output
totals or inconsistent counters are different errors: retain the evidence and
require reconciliation rather than inventing usage or a deduction.

## 4. Exact calculation and rounding

```text
cached_cost_exact   = C × cached_input_rate   / 1,000,000
uncached_cost_exact = U × uncached_input_rate / 1,000,000
input_credits      = round_half_up(cached_cost_exact + uncached_cost_exact, 2)

output_cost_exact  = O × output_rate / 100,000
output_credits     = round_half_up(output_cost_exact, 2)

total_credits      = input_credits + output_credits
```

Use exact decimal arithmetic throughout. Add cached and uncached input costs
**before rounding input once**. Round output separately. Add those rounded
amounts for the total; do not instead round an unrounded combined input/output
cost. Display every credit amount with exactly two decimal places.

Illustrative Python calculation for a gateway implementation:

```python
from decimal import Decimal, ROUND_HALF_UP

def credits(cached_tokens, uncached_tokens, output_tokens,
            cached_rate, uncached_rate, output_rate):
    # Validate counters and construct rates from decimal strings before calling.
    cent = Decimal("0.01")
    input_exact = (
        Decimal(cached_tokens) * Decimal(cached_rate)
        + Decimal(uncached_tokens) * Decimal(uncached_rate)
    ) / Decimal("1000000")
    output_exact = Decimal(output_tokens) * Decimal(output_rate) / Decimal("100000")
    input_credits = input_exact.quantize(cent, rounding=ROUND_HALF_UP)
    output_credits = output_exact.quantize(cent, rounding=ROUND_HALF_UP)
    return input_credits, output_credits
```

There is no approved minimum fee or accumulated fractional debt. A very small
request can round to `0.00`. For example, `0.004987` credits becomes `0.00` under
the required two-decimal rule. Qwen output of 10,000 tokens costs exactly `2.165`
credits before rounding and therefore becomes **2.17**, not 2.16.

### Worked examples

| Request | Input calculation | Output calculation | Total |
|---|---|---|---:|
| Codex: 16,644 uncached input; 21 output | `16644 × 94.14 / 1000000` → **1.57** | `21 × 47.07 / 100000` → **0.01** | **1.58** |
| DiscoveryRSI: 18,587 input, cache unreported; 342 output | `18587 × 3.77 / 1000000` → **0.07** | `342 × 21.65 / 100000` → **0.07** | **0.14** |
| GLM: 1,000,000 input, 400,000 cached; 100,000 output | `(400000 × 6.49 + 600000 × 6.58) / 1000000` → **6.54** | `100000 × 13.18 / 100000` → **13.18** | **19.72** |
| Codex: 16,644 entirely cached input; no output | `16644 × 4.71 / 1000000` → **0.08** | **0.00** | **0.08** |

The GLM input example is `2.596 + 3.948 = 6.544`, rounded once to `6.54`.
Rounding each input component first would incorrectly produce `6.55`.

## 5. Account authentication and current wallet API

The client currently sends its chosen route to the model gateway, not a separate
provider field:

```http
POST /v1/chat/completions
Authorization: Bearer <end-user Boltzmann API key>
Content-Type: application/json

{"model":"discoveryrsi","messages":[{"role":"user","content":"..."}],"stream":false}
```

The gateway should authenticate the account and resolve upstream credentials
server-side. The existing account-verification contract is:

```http
GET https://nodejsdev.grsmano.shop/api/agent-authenticate
Content-Type: application/json

{"apiToken":"<end-user Boltzmann API key>"}
```

It uses a GET **with a JSON body**, not URL query parameters. Its confirmed
response fields include `success`, `message`, `email`, `credits`, and the
service-spelled `freezedCredits`. Do not invent an available balance by
subtracting these two credit values unless the wallet service defines that rule.

After a model response has valid usage, the former client sent this exact update
contract. Move this responsibility into the trusted gateway:

```http
POST https://nodejsdev.grsmano.shop/api/agent-update
Content-Type: application/json
Accept: application/json

{
  "apiToken": "<end-user Boltzmann API key>",
  "input_credits": 0.07,
  "output_credits": 0.07
}
```

- These are JSON **numbers**, not quoted strings, tokens, percentages, or USD.
- The token is the same end-user Boltzmann key which authorized that inference,
  not the upstream Qwen/GLM/Codex provider credential.
- Encode the JSON credit numbers with two decimal places, including `0.00` or
  `1.20` when applicable. JSON numbers do not themselves preserve display scale;
  the UI must still format them to two decimals.
- The old HTTP client used a 15-second timeout, no redirects, no automatic retry,
  and a 64 KiB response bound. These are useful baseline controls, not a substitute
  for server-side transaction idempotency.
- Never log or persist `apiToken`, authorization headers, or provider secrets.

An illustrative successful acknowledgement, using fictitious account values:

```json
{
  "success": true,
  "message": "API credits updated successfully",
  "userId": "<account-id>",
  "email": "researcher@example.invalid",
  "creditsDeducted": 0.14,
  "credits": 99.86
}
```

Confirm a deduction only when HTTP status is 200, `success` is the boolean `true`,
and the finite, non-negative `creditsDeducted` agrees with
`input_credits + output_credits` at two decimals. Check the acknowledgement, not
merely its human-readable message. Tiny binary float tails in server balances,
such as `2258.8700000000003`, should not leak into the UI; use decimal/cent storage
for money and format displayed balances to two decimals.

## 6. Required gateway transaction design

The current wallet body has **no documented idempotency key or request-status
lookup**. Moving the old POST into a server process alone does not solve an
accepted deduction followed by a timeout. Implement the transaction contract
alongside the gateway migration.

1. Authenticate the account. Ignore/reject client-supplied prices, usage,
   deduction amounts, or flags asking to skip billing.
2. Create a durable server-generated inference ID and bind it to that account,
   requested model, upstream route, and applicable price-policy version.
3. Forward inference using gateway-owned provider credentials. Check admission
   and balance/budget rules according to the wallet's defined semantics; the old
   API does not provide a reservation contract, so do not pretend one exists.
4. Persist the returned usage and provider response ID before attempting a wallet
   update. Securely retain the result or a result reference when needed for replay;
   do not generate it again merely because billing acknowledgement was lost.
5. Normalize usage, record whether cache data was reported or assumed, calculate
   exact amounts, and retain the rounded invoice with its price version.
6. Use an idempotent wallet transaction keyed by account plus inference ID. This
   requires an agreed API addition, such as an `Idempotency-Key` header, or an
   internal atomic wallet operation. Do not invent an unsupported request field
   on the existing endpoint. Repeating the same transaction must return the
   original outcome without deducting again.
7. Update the balance atomically across gateway workers and profiles. Save a
   wallet transaction ID and its confirmed amounts/balance. Unknown outcomes
   remain unknown until an authoritative status lookup or idempotent replay
   resolves them. An HTTP timeout is not evidence of zero deduction.
8. Return the model answer plus server-confirmed billing metadata. Do not label
   a pending or mismatched deduction as confirmed or silently switch accounts.

Use server-side decimal money or integer hundredths of a credit. Keep audit
records outside a single growing plugin-state JSON object. Use atomic durable
storage, restrictive access, bounded growth, and an explicit retention policy.
The former client used a profile-scoped SQLite ledger, a 64 MiB bound, an 8 KiB
pre-inference record reservation, and 90-day retention for confirmed/definite
failed records. It never automatically deleted active/unknown records. A shared
server needs account-scoped durable storage and a deliberate server retention
policy rather than copying profile-local files blindly.

For future streaming support, settle from final authoritative usage once per
inference, never per rendered chunk. The current gateway is non-streaming.

## 7. Completion metadata displayed by SCI

The gateway response supplied for this integration adds these objects to the
ordinary Chat Completions JSON (account identity below is a fixture):

```json
{
  "billing": {
    "managed_by": "boltzmann_gateway",
    "status": "submitted",
    "currency": "INR",
    "pricing_model": "gpt-6.1-terra",
    "cache_usage_source": "reported",
    "input_tokens": 214,
    "cached_input_tokens": 0,
    "uncached_input_tokens": 214,
    "output_tokens": 115,
    "input_credits": "0.02",
    "output_credits": "0.05",
    "total_credits": "0.07"
  },
  "account": {
    "email": "researcher@example.invalid",
    "credits": 2253.93,
    "freezedCredits": 320
  }
}
```

SCI's request is unchanged: `model`, `messages`, and `stream: false`, authenticated
by the profile's Boltzmann key. It displays these added response fields without
recalculating prices or POSTing a deduction. All credit values are formatted to
two decimal places. Missing or invalid values display as unavailable; the model
answer remains usable. `submitted`, `pending`, and `failed` are shown as returned,
never silently converted to a confirmed payment.

The provider wrapper captures metadata before adapting non-streaming responses
to SCI's stream renderer, for both synchronous and asynchronous clients. Existing
account-usage views consume the latest snapshot in memory, bound to the profile,
endpoint and credential. The detailed `/usage` view includes the requested model
and response ID. The post-response footer shows only token input/output/total,
input/output/total credits, available credits (`account.credits` as returned),
and a reminder to use `/usage` for more details. Email, provider and other account
details remain in `/usage`. Footer token counts and credits describe the same
gateway response.
It is the latest response (including auxiliary calls), not a sum of a turn's
charges or a continuously refreshed wallet balance. No history ledger is added.
Restarting clears the snapshot; the existing read-only authentication lookup then
provides account details. A later response with no metadata clears older charges.

The gateway's internal transaction correctness and idempotency are separate from
this display integration; the sample alone does not verify those properties.

## 8. Deployment and verification checklist

- Deploy the SCI client rollback and restart old SCI processes. Already loaded
  old client code can continue charging until those processes exit.
- Add gateway-owned billing and wallet idempotency together. Restrict wallet
  updates to trusted server callers; end-user API keys alone must not authorize
  arbitrary client-selected deductions as the enforcement mechanism.
- Prevent old SCI clients from applying a second deduction after a gateway charge.
  Use a coordinated cutover and reject legacy direct client wallet updates.
  Do not trust a client-provided `billing_disabled` flag to skip server billing.
- Define a cutover timestamp and reconcile historical client receipts with
  confirmed wallet records. Never import a client ledger as trusted proof of
  usage, automatically rebill confirmed entries, or refund charges merely because
  client code was removed. Preserve pending/unknown audit records for review.
- Test all four mappings, all token units, cached/uncached input, null/absent
  telemetry, alias conflicts, invalid usage, reasoning already included in output,
  round-half-up ties, tiny `0.00` charges, and the worked examples above.
- Test sync/async calls, tool continuations, background requests, duplicate HTTP
  submissions, parallel workers, insufficient funds, crashes before/after wallet
  acceptance, timeouts, lost acknowledgements, and replay without re-generation.
- Verify account isolation, no key leakage, no invoice mutation under a later
  rate card, and read-only client balance/status views. Use controlled fixtures
  before conducting any explicitly authorized live financial test.

SCI consumes the gateway metadata as display data. It does not restore
client-side money authority.
