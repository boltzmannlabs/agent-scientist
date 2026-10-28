# tools.py — unified plugin tool handlers
# 5 handlers: 4 from sci-service (with server-side logging) + boltzmann_log_workflow from hermomics

import json
import os
import time
from agent.memory_provider import spawn_context_thread

from .nodeapi_helpers import (
    submit_request,
    fetch_status,
    download_from_signed_url,
    file_upload,
    fetch_tool_log,
)
from .auth import current_key, require_authorized
from .contracts import ContractStore
from .preflight import decision, preflight_submission, validated_upload

# Permanently retired platform jobs. Keep this enforcement at the submission
# boundary so stale conversations or manually supplied job names cannot invoke
# tools that are no longer part of Agent Scientist.
_RETIRED_JOB_NAMES = frozenset({
    "Fragment_based_generation_Inference",
    "Merge_Substructure",
    "Substructures",
    "Synergy_Prediction",
})

# ───────────────────────────────────────────────
# Tool-level timeouts (env var override, sensible defaults)
# ───────────────────────────────────────────────

_TOOL_TIMEOUTS = {
    "boltzmann_submit":        int(os.getenv("TOOL_TIMEOUT_SUBMIT", "120")),       # 2 min
    "boltzmann_status":        int(os.getenv("TOOL_TIMEOUT_STATUS", "600")),       # 10 min (long poll)
    "boltzmann_download":      int(os.getenv("TOOL_TIMEOUT_DOWNLOAD", "300")),     # 5 min (large files)
    "boltzmann_upload":        int(os.getenv("TOOL_TIMEOUT_UPLOAD", "180")),       # 3 min
    "boltzmann_fetch_tool_log": int(os.getenv("TOOL_TIMEOUT_FETCH_LOG", "120")),
}


def _run_with_timeout(fn, tool_name: str, kwargs: dict):
    """Run fn(**kwargs) with a tool-level timeout.

    Returns the function result. On timeout, returns a clean error dict
    so the LLM can understand and retry.
    """
    try:
        require_authorized()
    except PermissionError as exc:
        return json.dumps({"error": str(exc), "authorization_required": True})
    timeout = _TOOL_TIMEOUTS.get(tool_name, 300)
    result_holder = [None]
    error_holder = [None]

    def _worker():
        try:
            result_holder[0] = fn(**kwargs)
        except Exception as exc:
            error_holder[0] = exc

    thread = spawn_context_thread(_worker, name=f"boltzmann-{tool_name}")
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Thread is still running — it timed out
        print(f"[{tool_name}] Timed out after {timeout}s")
        return json.dumps({
            "error": f"{tool_name} timed out after {timeout}s. Its request may still be running. Do not repeat a submission or upload; check the existing job or ask the user to reconcile its outcome.",
            "stage": tool_name.removeprefix("boltzmann_"),
            "status": "unknown",
            "job_name": kwargs.get("job_name"),
            "doc_id": kwargs.get("doc_id"),
            "safe_to_retry": False,
            "timeout": True,
            "timeout_seconds": timeout,
        })

    if error_holder[0] is not None:
        from .results import safe_detail
        exc = error_holder[0]
        return json.dumps({"error": safe_detail(str(exc), current_key()) or "Boltzmann operation failed.",
                           "stage": tool_name.removeprefix("boltzmann_"), "status": "unknown",
                           "safe_to_retry": False})

    return result_holder[0]


def _get_api_key():
    """Resolve the API key at call time from the active profile scope."""
    return current_key()


def _get_conv_id(kwargs):
    return kwargs.get("conv_id") or ""


# ───────────────────────────────────────────────
# Boltzmann platform tools (from sci-service, with server-side logging)
# ───────────────────────────────────────────────

def _handle_boltzmann_submit_inner(**kwargs):
    """Inner logic — extracted so _run_with_timeout can wrap it."""
    job_name = kwargs.get("job_name")
    experiment_data = kwargs.get("experiment_data")
    experiment_name = kwargs.get("experiment_name")

    if isinstance(experiment_data, str):
        try:
            experiment_data = json.loads(experiment_data)
        except json.JSONDecodeError:
            return json.dumps({"error": "experiment_data must be an object, not a JSON string"})

    if isinstance(experiment_data, dict) and not experiment_name:
        experiment_data = dict(experiment_data)
        experiment_name = experiment_data.pop("experiment_name", None)

    missing = []
    if not job_name:
        missing.append("job_name")
    if not experiment_data:
        missing.append("experiment_data")
    if not experiment_name:
        missing.append("experiment_name")
    if missing:
        return json.dumps({"error": f"Missing required arguments: {', '.join(missing)}"})

    if job_name in _RETIRED_JOB_NAMES:
        return json.dumps({
            "error": f"The Boltzmann tool `{job_name}` has been permanently removed and cannot be submitted.",
            "removed_tool": True,
            "job_name": job_name,
        })

    if job_name == "Enzyme_RFD3" and isinstance(experiment_data, dict):
        from .enzyme_validation import prepare_rfd3_payload
        experiment_data = prepare_rfd3_payload(experiment_data, experiment_name)

    report = preflight_submission(job_name, experiment_data)
    blocked = decision(report, kwargs.get("allow_partial_validation"))
    if blocked:
        return json.dumps(blocked)

    conv_id = _get_conv_id(kwargs)
    token = _get_api_key()

    doc_id = submit_request(experiment_data, job_name, experiment_name, token=token, conv_id=conv_id)

    # Allow the auto-logged pending write to propagate before the next tool
    # call triggers another read-modify-write (critical for multi-step workflows).
    time.sleep(1)

    # submit_request now returns an error dict on auth failures instead of raising
    if isinstance(doc_id, dict) and "error" in doc_id:
        return json.dumps(doc_id)

    return json.dumps({"doc_id": doc_id, "job_name": job_name, "experiment_name": experiment_name,
                       "stage": "submit", "status": "accepted", "validation": report.as_dict(),
                       "message": "Job accepted, not completed. Poll this job; do not submit again."})


def handle_boltzmann_submit(**kwargs):
    return _run_with_timeout(_handle_boltzmann_submit_inner, "boltzmann_submit", kwargs)


def _handle_boltzmann_status_inner(**kwargs):
    """Inner logic — extracted so _run_with_timeout can wrap it."""
    job_name = kwargs.get("job_name")
    doc_id = kwargs.get("doc_id")
    if not job_name or not doc_id:
        missing = [k for k in ("job_name", "doc_id") if not kwargs.get(k)]
        return json.dumps({"error": f"Missing required arguments: {', '.join(missing)}. You must provide the job_name and doc_id returned by boltzmann_submit."})

    conv_id = _get_conv_id(kwargs)
    token = _get_api_key()
    output_folder = kwargs.get("output_folder") or os.getenv("output_folder") or None

    # Always refresh from the service: completed responses may contain expiring
    # signed artifact URLs. A terminal-state cache is not an artifact URL cache.
    result = fetch_status(job_name, doc_id, token=token, conv_id=conv_id, output_folder=output_folder)

    # Allow the auto-logged terminal write to propagate before the next tool
    # call triggers another read-modify-write (critical for multi-step workflows).
    time.sleep(1)

    # fetch_status now returns an error dict on auth failures instead of raising
    if isinstance(result, dict) and "error" in result:
        return json.dumps(result)

    if isinstance(result, dict):
        return json.dumps(result)
    return result


def handle_boltzmann_status(**kwargs):
    return _run_with_timeout(_handle_boltzmann_status_inner, "boltzmann_status", kwargs)


def _handle_boltzmann_download_inner(**kwargs):
    """Inner logic — extracted so _run_with_timeout can wrap it."""
    download_url = kwargs.get("download_url")
    output_folder = kwargs.get("output_folder")
    if not download_url or not output_folder:
        missing = [k for k in ("download_url", "output_folder") if not kwargs.get(k)]
        return json.dumps({"error": f"Missing required arguments: {', '.join(missing)}"})
    output_folder = os.path.expanduser(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    token = _get_api_key()
    result = download_from_signed_url([download_url], output_folder, token=token)
    if isinstance(result, dict):
        return json.dumps(result)
    return result


def handle_boltzmann_download(**kwargs):
    return _run_with_timeout(_handle_boltzmann_download_inner, "boltzmann_download", kwargs)


def _handle_boltzmann_upload_inner(**kwargs):
    """Inner logic — extracted so _run_with_timeout can wrap it."""
    local_path = kwargs.get("local_path")
    if not local_path:
        return json.dumps({"error": "Missing required argument: local_path"})
    job, field = kwargs.get("job_name"), kwargs.get("input_field")
    if not job or not field:
        return json.dumps({"error": "Provide job_name and input_field so the actual upload can be checked against its intended use.",
                           "stage": "validation", "status": "not_started"})
    token = _get_api_key()
    result = validated_upload(local_path, job, field, kwargs.get("experiment_data") or {},
                              kwargs.get("allow_partial_validation"),
                              lambda snapshot: file_upload(snapshot, token=token))
    return json.dumps(result)


def handle_boltzmann_upload(**kwargs):
    return _run_with_timeout(_handle_boltzmann_upload_inner, "boltzmann_upload", kwargs)


# ───────────────────────────────────────────────
# Read-only durable tool log lookup
# ───────────────────────────────────────────────

def _handle_boltzmann_fetch_tool_log_inner(**kwargs):
    collection = kwargs.get("collection")
    job_name = kwargs.get("job_name")
    experiment_id = kwargs.get("experiment_id")
    try:
        if not experiment_id:
            raise ValueError("Missing required argument: experiment_id.")
        if job_name:
            resolved = ContractStore().diagnostic_collection(job_name)
            if collection and collection != resolved:
                raise ValueError(f"Collection conflicts with the documented mapping for {job_name}: {resolved}.")
            collection = resolved
        elif not collection:
            raise ValueError("Provide job_name for documented collection resolution, or a verified collection.")
    except ValueError as exc:
        return json.dumps({"error": str(exc), "stage": "diagnostic_lookup", "status": "not_started",
                           "job_name": job_name, "experiment_id": experiment_id,
                           "note": "Only diagnostic lookup stopped; the submitted job's outcome is unchanged."})
    result = fetch_tool_log(collection, experiment_id, token=_get_api_key())
    return json.dumps(result) if isinstance(result, dict) else result


def handle_boltzmann_fetch_tool_log(**kwargs):
    return _run_with_timeout(
        _handle_boltzmann_fetch_tool_log_inner,
        "boltzmann_fetch_tool_log",
        kwargs,
    )
