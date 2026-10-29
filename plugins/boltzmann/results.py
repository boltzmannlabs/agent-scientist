"""Safe, stage-specific service errors without losing useful validation diagnostics."""

import re

from agent.redact import redact_for_egress


_DIAGNOSTIC_FIELDS = ("info", "message", "msg", "error", "detail",
                      "errors", "details", "validation_errors")
_PRIVATE_DIAGNOSTIC_KEYS = frozenset({
    "input", "value", "authorization", "apikey", "token", "tokenid",
    "accesstoken", "refreshtoken", "password", "secret", "cookie", "headers",
})


def _safe_text(value, token):
    if token:
        value = value.replace(token, "[credential redacted]")
    value = re.sub(r"https?://[^\s\"'<>]+", "[service URL redacted]", value)
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value)
    return redact_for_egress(value)


def safe_detail(value, token=""):
    if isinstance(value, dict):
        value = value.get("message") or value.get("msg") or value.get("error") or value.get("detail") or ""
    if isinstance(value, list):
        value = "; ".join(safe_detail(item, token) for item in value[:10])
    if not isinstance(value, str):
        return ""
    return _safe_text(value, token)[:2000]


def service_diagnostics(result, token=""):
    """Keep nested worker diagnostics and tracebacks, not just their summary.

    Artifact URLs outside diagnostic fields must remain usable for downloads.
    """
    def scrub(value):
        if isinstance(value, str):
            return _safe_text(value, token)
        if isinstance(value, dict):
            return {key: "[redacted]" if re.sub(r"[^a-z]", "", key.lower()) in _PRIVATE_DIAGNOSTIC_KEYS
                    else scrub(item) for key, item in value.items()}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return {key: scrub(value) if key in _DIAGNOSTIC_FIELDS else value
            for key, value in result.items()}


def service_error(stage, response, token=""):
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = safe_detail(body, token)
    fallback = ("Service request failed without a usable diagnostic; job outcome is unknown."
                if stage in {"submit", "status"} else "Service request failed without a usable diagnostic.")
    diagnostics = service_diagnostics(body, token) if isinstance(body, dict) else {}
    result = {key: diagnostics[key] for key in _DIAGNOSTIC_FIELDS
              if key != "error" and key in diagnostics}
    # Summary and cause are separate service fields, not alternatives. Keep the
    # cause intact (including structured/long errors); auth wrappers may replace
    # the top-level error but must not destroy the original service diagnostic.
    cause = diagnostics.get("error")
    if cause:
        result["service_error"] = cause
    if isinstance(diagnostics.get("success"), bool):
        result["success"] = diagnostics["success"]
    result.update(error=cause or detail or fallback, stage=stage,
                  status="unknown" if stage in {"submit", "status"} else "failed",
                  authorization_required=response.status_code in {401, 403}, safe_to_retry=False)
    if isinstance(diagnostics.get("status"), str):
        # A rejected request is not proof of a failed scientific job. Preserve
        # the service's status separately from our submission-outcome certainty.
        result["service_status"] = _safe_text(diagnostics["status"], token)
    return result
