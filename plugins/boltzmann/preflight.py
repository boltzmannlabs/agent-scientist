"""Bind validation to the uploaded bytes and owning profile, never to a filename claim."""

import hashlib
import json
from pathlib import Path
import tempfile

from sci_cli.plugins_state import PluginState

from .auth import current_key, fingerprint
from .contracts import ContractStore, ValidationReport
from .file_validation import MAX_FILE_BYTES, validate_file

VALIDATOR_VERSION = "enzyme-inputs-v2"

def _receipt_key(job, field, storage_path):
    digest = hashlib.sha256(json.dumps([job, field, storage_path]).encode()).hexdigest()
    return "upload:" + digest


def _contract_digest(store, job, field=None):
    def runtime_fields(value):
        if isinstance(value, dict):
            return {key: runtime_fields(item) for key, item in value.items()
                    if key not in {"description", "notes", "source", "coverage", "evidence"}}
        if isinstance(value, list):
            return [runtime_fields(item) for item in value]
        return value
    rules = store.files.get(job, {}).get("files", {})
    selected = {field: rules[field]} if field in rules else rules
    if any(rule.get("structure_profile") or rule.get("inventory_kind") or rule.get("semantic_values")
           or rule.get("sequence_validation") for rule in selected.values()):
        # File receipts depend on their actual checks, not unrelated sampling
        # defaults, documentation, or a different uploaded file's schema.
        properties = {}
        for rule in selected.values():
            for name in rule.get("validation_context", []):
                prop = store.tools[job]["request_schema"]
                for part in name.split("."):
                    prop = prop.get("properties", {}).get(part, {})
                properties[name] = prop
        inputs = [VALIDATOR_VERSION, selected, properties]
        if job == "Mol_Probity" and "input_path" in selected:
            inputs.append(store.limits.get(job, {}).get("ligand_bundle"))
    else:
        inputs = [store.tools[job]["request_schema"], store.files.get(job), store.limits.get(job)]
    return hashlib.sha256(json.dumps(runtime_fields(inputs), sort_keys=True).encode()).hexdigest()


def _context(rule, payload):
    if rule.get("structure_profile") == "Enzyme_RFD3":
        from .enzyme_validation import prepare_rfd3_payload
        # Bind receipts to effective file-dependent selections, not the caller's
        # optional-field spelling before the same submit preparation runs.
        payload = prepare_rfd3_payload(payload, "receipt-context")
    result = {}
    for name in {*rule.get("values_by_field", {}), *rule.get("validation_context", [])}:
        value = payload
        for part in name.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        result[name] = value
    return result


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
    try:
        if report.inventory.get("kind") == "structure" and not storage.lower().endswith(".zip"):
            # Workers derive single-candidate IDs from the downloaded object name,
            # which the upload service may have renamed. ZIP member IDs are stable.
            from .boltzyme_tools_input_structure_validation import _candidate_id
            summary = report.inventory["data"]
            if len(summary.get("candidates", [])) == 1:
                summary["candidates"][0]["candidate_id"] = _candidate_id(storage, rule["structure_profile"])
        receipt = {"authorization": fingerprint(current_key()), "sha256": digest,
                   "contract": _contract_digest(store, job, field), "context": _context(rule, payload),
                   "validation": report.as_dict(), "inventory": report.inventory}
        PluginState("boltzmann").set(_receipt_key(job, field, storage), receipt)
    except (OSError, ValueError, RuntimeError):
        return {"error": "File uploaded, but its validation receipt could not be saved. No job was submitted.",
                "stage": "upload", "status": "partial", "s3_path": storage,
                "uploaded": True, "safe_to_retry": False}
    return {"s3_path": storage, "stage": "upload", "status": "uploaded", "sha256": digest,
            "validation": report.as_dict()}


def preflight_submission(job, payload):
    if job == "Mol_Probity" and isinstance(payload, dict):
        from .enzyme_validation import prepare_molprobity_payload
        payload = prepare_molprobity_payload(payload)
    store = ContractStore()
    report = store.validate_payload(job, payload)
    if report.errors:
        return report
    inventories = {}
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
        if receipt.get("contract") != _contract_digest(store, job, field) or receipt.get("context") != _context(rule, payload):
            report.errors.append(f"{field}: validation rules or dependent inputs changed; validate and upload again.")
        else:
            # Inventories and warnings are trusted only with the same profile,
            # validator semantics and relevant parameter context as the upload.
            inventories[field] = receipt.get("inventory", {})
            report.warnings.extend(receipt["validation"]["warnings"])
            report.info.extend(receipt["validation"].get("info", []))
    if not report.errors and job == "Catalytic_Geometry":
        from .enzyme_validation import validate_joint_files
        validate_joint_files(payload, inventories, report)
    return report
