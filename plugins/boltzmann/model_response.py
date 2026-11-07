"""Display gateway-owned billing metadata; no pricing, deductions or ledger writes."""

from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import threading

from agent.account_usage import AccountUsageSnapshot

# One bounded, in-memory view per profile/endpoint, also bound to its current key.
# A new response replaces the old view, including when metadata is missing.
_latest = OrderedDict()
_lock = threading.Lock()


def _text(value, key, limit=254):
    if not isinstance(value, str):
        return ""
    return "".join(c for c in value.replace(key, "[redacted]") if c.isprintable())[
        :limit
    ]


def _credits(value):
    if type(value) not in (str, int, float) or len(str(value)) > 64:
        return "not provided"
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount.adjusted() > 18:
            return "not provided"
        return f"{amount:,.2f}"
    except InvalidOperation:
        return "not provided"


def _tokens(value):
    return (
        f"{value:,}" if type(value) is int and 0 <= value < 10**19 else "not provided"
    )


def _identity(home, base_url):
    return str(Path(home).resolve()), str(base_url).rstrip("/")


def remember_response(home, base_url, key, model, response):
    billing = getattr(response, "billing", None)
    account = getattr(response, "account", None)
    snapshot = None
    if isinstance(billing, dict) or isinstance(account, dict):
        billing = billing if isinstance(billing, dict) else {}
        account = account if isinstance(account, dict) else {}
        details = [
            f"Email: {_text(account.get('email'), key) or 'not provided'}",
            f"Available credits: {_credits(account.get('credits'))}",
            f"Frozen credits: {_credits(account.get('freezedCredits'))}",
            f"Latest gateway response: {model} · {_text(getattr(response, 'id', ''), key) or 'ID not provided'}",
            f"Gateway billing: {_text(billing.get('status'), key) or 'not provided'}",
        ]
        if billing:
            details.extend((
                f"Managed by: {_text(billing.get('managed_by'), key) or 'not provided'}"
                f" · Pricing model: {_text(billing.get('pricing_model'), key) or 'not provided'}"
                f" · Currency: {_text(billing.get('currency'), key) or 'not provided'}",
                f"Input credits: {_credits(billing.get('input_credits'))}"
                f" · Output credits: {_credits(billing.get('output_credits'))}"
                f" · Total credits: {_credits(billing.get('total_credits'))}",
                f"Request tokens: input {_tokens(billing.get('input_tokens'))}"
                f" (cached {_tokens(billing.get('cached_input_tokens'))}"
                f" · uncached {_tokens(billing.get('uncached_input_tokens'))})"
                f" · output {_tokens(billing.get('output_tokens'))}",
                f"Cache usage source: {_text(billing.get('cache_usage_source'), key) or 'not provided'}",
            ))
        usage = getattr(response, "usage", None)
        after_turn_lines = (
            f"Token usage: input {_tokens(getattr(usage, 'prompt_tokens', None))}"
            f" · output {_tokens(getattr(usage, 'completion_tokens', None))}"
            f" · total {_tokens(getattr(usage, 'total_tokens', None))}",
            f"Input credits: {_credits(billing.get('input_credits'))}"
            f" · Output credits: {_credits(billing.get('output_credits'))}"
            f" · Total credits: {_credits(billing.get('total_credits'))}"
            f" Available Credits: {_credits(account.get('credits'))}",
            "Type /usage to view detailed token usage, credits, and account information.",
        )
        snapshot = AccountUsageSnapshot(
            provider="boltzmann_models",
            source=str(base_url).rstrip("/") + "/chat/completions",
            fetched_at=datetime.now(timezone.utc),
            title="Boltzmann account · gateway response",
            details=tuple(details),
            after_turn_lines=after_turn_lines,
        )
    identity = _identity(home, base_url)
    with _lock:
        _latest[identity] = (hashlib.sha256(key.encode()).digest(), snapshot)
        _latest.move_to_end(identity)
        while len(_latest) > 128:
            _latest.popitem(last=False)


def latest_response(home, base_url, key):
    with _lock:
        record = _latest.get(_identity(home, base_url))
        if record is not None and record[0] == hashlib.sha256(key.encode()).digest():
            return record[1]
    return None
