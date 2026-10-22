"""Bind validation to the uploaded bytes and owning profile, never to a filename claim."""

import hashlib
import json
from pathlib import Path
import tempfile

from sci_cli.plugins_state import PluginState

from .auth import current_key, fingerprint
from .contracts import ContractStore, ValidationReport
from .file_validation import MAX_FILE_BYTES, validate_file


def _receipt_key(job, field, storage_path):
    digest = hashlib.sha256(json.dumps([job, field, storage_path]).encode()).hexdigest()
    return "upload:" + digest


def _contract_digest(store, job):
    def runtime_fields(value):
        if isinstance(value, dict):
            return {key: runtime_fields(item) for key, item in value.items()
                    if key not in {"description", "notes", "source", "coverage", "evidence"}}
        if isinstance(value, list):
            return [runtime_fields(item) for item in value]
        return value
    return hashlib.sha256(json.dumps(runtime_fields([store.tools[job]["request_schema"], store.files.get(job), store.limits.get(job)]),
                                    sort_keys=True).encode()).hexdigest()


def _context(rule, payload):
    return {name: payload.get(name) for name in rule.get("values_by_field", {})}


def decision(report, approved):
    if report.errors:
        return {"error": "Input validation failed; no upload or job submission was performed.",
                "stage": "validation", "status": "not_started", "validation": report.as_dict(),
                "safe_to_retry": False}
    if report.warnings and approved is not True:
        return {"error": "Validation is partial, not failed. Review the unchecked aspects and ask for explicit best-effort approval.",
                "stage": "validation", "status": "approval_required", "approval_required": True,
                "validation": report.as_dict(), "safe_to_retry": False}
    return None


def validated_upload(local_path, job, field, payload, approved, upload):
    store = ContractStore()
    try:
        rule = store.file_rule(job, field)
    except ValueError as exc:
        return {"error": str(exc), "stage": "validation", "status": "not_started",
                "uploaded": False, "submitted": False, "safe_to_retry": False}
    source = Path(local_path).expanduser()
    report = ValidationReport()
    if source.is_symlink() or not source.is_file() or not 0 < source.stat().st_size <= MAX_FILE_BYTES:
        report.errors.append("Input must be a nonempty regular file within the connector's 256 MiB inspection budget.")
        return decision(report, approved)
    # Validate and upload one private snapshot; a changed original cannot invalidate the check.
    with tempfile.TemporaryDirectory(prefix="sci-boltzmann-input-") as temporary:
        snapshot = Path(temporary) / source.name
        with source.open("rb") as incoming, snapshot.open("wb") as outgoing:
            copied = 0
            while chunk := incoming.read(1024 * 1024):
                copied += len(chunk)
                if copied > MAX_FILE_BYTES:
                    report.errors.append("Input grew beyond the inspection budget while being read.")
                    return decision(report, approved)
                outgoing.write(chunk)
        report = validate_file(snapshot, rule, payload)
        blocked = decision(report, approved)
        if blocked:
            return blocked
        digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        storage = upload(str(snapshot))
    if isinstance(storage, dict):
        return storage
    if not isinstance(storage, str) or not storage:
        return {"error": "Upload response omitted its storage reference.", "stage": "upload", "status": "unknown"}
    receipt = {"authorization": fingerprint(current_key()), "sha256": digest,
               "contract": _contract_digest(store, job), "context": _context(rule, payload),
               "validation": report.as_dict()}
    try:
        PluginState("boltzmann").set(_receipt_key(job, field, storage), receipt)
    except (OSError, ValueError, RuntimeError):
        return {"error": "File uploaded, but its validation receipt could not be saved. No job was submitted.",
                "stage": "upload", "status": "partial", "s3_path": storage,
                "uploaded": True, "safe_to_retry": False}
    return {"s3_path": storage, "stage": "upload", "status": "uploaded", "sha256": digest,
            "validation": report.as_dict()}


def preflight_submission(job, payload):
    store = ContractStore()
    report = store.validate_payload(job, payload)
    if report.errors:
        return report
    for field, prop in store.file_fields(job).items():
        storage = payload.get(field)
        if not storage:
            continue
        if prop["x-input-kind"] == "file_or_value" and not isinstance(storage, str):
            # Inline object/array modes were already validated by the request schema.
            continue
        rule = store.files.get(job, {}).get("files", {}).get(field, {})
        if rule.get("execution_blocked"):
            report.errors.append(f"{field}: this input is explicitly blocked pending an approved validator.")
            continue
        if not isinstance(storage, str):
            report.errors.append(f"{field}: expected a file reference string.")
            continue
        if storage.startswith(("/", "~/", "file:")):
            report.errors.append(f"{field}: upload the local file before submitting; local paths are not platform references.")
            continue
        receipt = PluginState("boltzmann").get(_receipt_key(job, field, storage))
        if prop["x-input-kind"] == "file_or_value" and not receipt:
            # Inline values are an explicitly documented mode, not inferred from
            # the field's name or filename extension. Uploaded references retain receipts.
            report.warnings.append(f"{field}: no upload receipt; confirm this is the documented inline value or an authorized platform reference.")
            continue
        if prop["x-input-kind"] == "artifact" and not receipt:
            report.warnings.append(f"{field}: confirm this reference came from the authorized upstream job; no new local upload is required.")
            continue
        if not receipt or receipt.get("authorization") != fingerprint(current_key()):
            report.warnings.append(f"{field}: no current-profile validation receipt for this reference. Contents were not checked; confirm its authorized provenance and best-effort use.")
            continue
        if receipt.get("contract") != _contract_digest(store, job) or receipt.get("context") != _context(rule, payload):
            report.errors.append(f"{field}: validation rules or dependent inputs changed; validate and upload again.")
        elif receipt["validation"]["warnings"]:
            # Preserve the caveat in the submission result even after upload approval.
            report.warnings.extend(receipt["validation"]["warnings"])
    return report
