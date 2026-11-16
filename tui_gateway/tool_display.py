"""Bounded, redacted tool output for expandable browser cards and saved history."""

import json
import logging

MAX_TOOL_DISPLAY_CHARS = 64 * 1024
_log = logging.getLogger(__name__)


def tool_display_text(value: object) -> str:
    if value is None:
        return ""
    from agent.redact import redact_sensitive_text
    from agent.tool_dispatch_helpers import _multimodal_text_summary

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            pass  # Ordinary tool output need not be JSON.
    try:
        text = redact_sensitive_text(
            _multimodal_text_summary(value), force=True, redact_url_credentials=True,
        )
    except Exception:
        # Rendering must never fall back to unredacted content.
        _log.warning("Tool display redaction failed; output withheld")
        return "[Output unavailable: redaction failed.]"
    if len(text) > MAX_TOOL_DISPLAY_CHARS:
        return text[:MAX_TOOL_DISPLAY_CHARS] + "\n[Display truncated; additional output is not shown.]"
    return text
