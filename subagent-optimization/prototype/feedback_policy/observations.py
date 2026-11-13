"""Offline adapter for host-qualified long observation records. No tool client."""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import io
import math
from pathlib import Path

from feedback_policy import require


MAX_BYTES = 32 * 1024 * 1024
POLICY_METRICS = ("qed", "crippen_logp", "solubility", "pampa", "vina")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_records(raw, required):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, "Nonempty bounded CSV bytes required")
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Invalid UTF-8 CSV") from exc
    require(rows and rows[0] and all(rows[0]) and len(set(rows[0])) == len(rows[0]),
            "Unique nonempty CSV headers required")
    require(set(required) <= set(rows[0]), "Required CSV columns missing")
    require(all(len(row) == len(rows[0]) for row in rows[1:]), "CSV row width mismatch")
    return [dict(zip(rows[0], row)) for row in rows[1:]]


def bundle_file(root, relative_path):
    """Bound every bundle read, including the manifest itself."""
    root = Path(root).resolve()
    relative = Path(relative_path)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "Bundle-relative source path required")
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "Source escapes bundle or is missing")
    require(path.stat().st_size <= MAX_BYTES, "Source exceeds adapter byte limit")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Source exceeds adapter byte limit")
    return raw


def verified_file(root, relative_path, manifest_rows):
    """Read only a requested, hash-matching manifest member inside the bundle."""
    matches = [r for r in manifest_rows if r["relative_path"] == relative_path]
    require(len(matches) == 1, "Source must have one manifest entry")
    raw = bundle_file(root, relative_path)
    require(str(len(raw)) == matches[0]["bytes"] and sha256(raw) == matches[0]["sha256"],
            "Source bytes/hash differ from recorded manifest: " + relative_path)
    return raw


def _binding(binding):
    required = {"source_metric", "target_metric", "producer_method", "unit", "qualified"}
    require(required <= set(binding) and type(binding["qualified"]) is bool,
            "Explicit metric meaning/method/unit/admission required")
    require(all(isinstance(binding[k], str) and binding[k] for k in required - {"qualified"}),
            "Nonempty metric mapping fields required")
    source, target = binding["source_metric"].lower(), binding["target_metric"]
    producer = binding["producer_method"].lower()
    if target == "vina":
        require("smina" not in source + producer and "diffdock" not in source + producer,
                "Smina/DiffDock cannot be relabelled platform Vina")
    if target == "crippen_logp":
        require(source not in {"lipophilicity", "solubility"},
                "Hosted property cannot be relabelled Crippen LogP")
    if target == "pampa":
        require(binding.get("output_kind") in {"class_label", "class_score"},
                "PAMPA mapping must distinguish native class labels from scores")


def prepare_basic_vina_csv(candidates):
    """Prepare exact SDK columns and ordered host manifest; perform no upload."""
    manifest, seen = [], set()
    for row in candidates:
        require(row.get("valid") is True and all(isinstance(row.get(k), str) and row[k]
                for k in ("identity", "smiles")), "Host-qualified identity and SMILES required")
        require(row["identity"] not in seen, "Select unique identities before preparing the batch")
        seen.add(row["identity"])
        name = "mol-" + sha256(row["identity"].encode())
        manifest.append({"candidate_id": name, "canonical_identity": row["identity"],
                         "SMILES": row["smiles"], "NAMES": name})
    require(manifest, "A nonempty admitted ligand batch is required")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["SMILES", "NAMES"])
    writer.writeheader()
    writer.writerows({k: row[k] for k in ("SMILES", "NAMES")} for row in manifest)
    raw = output.getvalue().encode()
    return {"csv_bytes": raw, "csv_sha256": sha256(raw), "input_manifest": manifest,
            "execution": "not_performed"}


def import_long_records(registry_raw, metrics_raw, *, bindings, expected_context,
                        reference_candidates=(), reference_roles=None,
                        valid_statuses=("VALID_CONNECTED_COMPLETE",), success_statuses=("SUCCESS",)):
    """Explicit long-record CSV contract; host owns identities/metric meanings.

    Original rows, phases, source methods and hashes are retained. Unknown or
    conflicting values cannot become silently qualified policy measurements.
    """
    registry = csv_records(registry_raw, {"candidate_id", "canonical_identity", "status"})
    metrics = csv_records(metrics_raw, {"candidate_id", "canonical_identity", "phase", "metric_id",
                                           "value", "unit", "status", "method_version", *expected_context})
    reference_roles = reference_roles or {}
    require(all(role in {"lead", "control"} for role in reference_roles.values()), "Invalid reference role")
    mappings = {}
    for binding in bindings:
        _binding(binding)
        key = binding["source_metric"]
        require(key not in mappings, "Ambiguous metric mapping")
        mappings[key] = deepcopy(binding)
    identities, canonical = {}, {}
    for source in [*registry, *reference_candidates]:
        cid, identity = source["candidate_id"], source["canonical_identity"]
        require(cid and identity and cid not in identities, "Missing/ambiguous host candidate identity")
        identities[cid] = identity
        valid = source["status"] in valid_statuses
        if identity in canonical:
            require(canonical[identity]["valid"] == valid, "Conflicting host identity validity")
        else:
            canonical[identity] = {"identity": identity, "smiles": identity, "valid": valid,
                                   "role": reference_roles.get(identity, "generated")}
    observations, groups, phases = [], defaultdict(list), set()
    unmapped = Counter()
    metrics_sha = sha256(metrics_raw)
    for index, source in enumerate(metrics, 1):
        require(all(source[k] == value for k, value in expected_context.items()),
                "Observation context differs from declared source run/case")
        cid = source["candidate_id"]
        require(cid in identities and source["canonical_identity"] == identities[cid],
                "Observation candidate/identity join failed")
        phase = source["phase"]
        require(phase and source["metric_id"], "Explicit phase and metric required")
        phases.add(phase)
        binding = mappings.get(source["metric_id"])
        record = {"source_row": index, "source_sha256": metrics_sha,
                  "source": deepcopy(source), "target_metric": binding["target_metric"] if binding else None}
        observations.append(record)
        if not binding:
            unmapped[source["metric_id"]] += 1
            continue
        try:
            value = float(source["value"])
            value = value if math.isfinite(value) else None
        except ValueError:
            value = None
        reason = None
        if source["status"] not in success_statuses:
            status = {"UNQUALIFIED": "unqualified", "UNAVAILABLE": "unavailable"}.get(source["status"], "failed")
            reason = source.get("reason") or "Producer did not report successful measurement"
        elif value is None:
            status, reason = "unavailable", "Successful source row has no finite numeric value"
        elif source["method_version"] != binding["producer_method"] or source["unit"] != binding["unit"]:
            status, reason = "unqualified", "Producer method/unit differs from admitted mapping"
        elif not binding["qualified"]:
            status, reason = "unqualified", "Host has not qualified this measurement interpretation"
        elif binding["target_metric"] == "pampa" and (
                (binding["output_kind"] == "class_label" and value not in (0, 1))
                or not 0 <= value <= 1):
            status, reason = "unavailable", "PAMPA value is outside the declared label/score domain"
        else:
            status = "ok"
        measurement = {"value": value if status == "ok" else None, "status": status,
                       "method": source["method_version"], "unit": source["unit"], "reason": reason}
        if "output_kind" in binding:
            measurement["output_kind"] = binding["output_kind"]
        record["measurement"] = measurement
        groups[(identities[cid], phase, binding["target_metric"])].append(record)
    projections = {phase: {i: {**deepcopy(row), "measurements": {
        key: {"value": None, "status": "unavailable", "method": None, "unit": None,
              "reason": "No observation supplied for this method/phase"} for key in POLICY_METRICS}}
        for i, row in canonical.items()} for phase in sorted(phases)}
    conflicts, duplicate_keys = [], []
    for (identity, phase, metric), records in sorted(groups.items()):
        signature = {(r["measurement"]["value"], r["measurement"]["status"],
                      r["measurement"]["method"], r["measurement"]["unit"],
                      r["measurement"].get("output_kind")) for r in records}
        if len(records) > 1:
            duplicate_keys.append({"identity": identity, "phase": phase, "metric": metric,
                                   "source_rows": [r["source_row"] for r in records]})
        if len(signature) != 1:
            conflicts.append({"identity": identity, "phase": phase, "metric": metric,
                              "source_rows": [r["source_row"] for r in records]})
            measurement = {"value": None, "status": "conflict", "method": None, "unit": None,
                           "reason": "Contradictory observations; no best-value selection or overwrite"}
        else:
            measurement = deepcopy(records[0]["measurement"])
        projections[phase][identity]["measurements"][metric] = measurement
    return {"adapter_version": "long-observations-v1", "source_state": "historical_frozen",
            "registry_sha256": sha256(registry_raw), "metrics_sha256": metrics_sha,
            "registry": registry, "observations": observations,
            "phase_candidates": {phase: [rows[i] for i in sorted(rows)] for phase, rows in projections.items()},
            "conflicts": conflicts, "duplicate_measurement_keys": duplicate_keys,
            "unmapped_metric_counts": dict(sorted(unmapped.items())),
            "execution": "not_performed"}


def import_basic_vina_csv(raw, input_manifest, *, context, method, unit,
                          selected_pose_index, qualified=False, verified_pose_keys=()):
    """Prospective mapping for the inspected basic_docking source, not deployment.

    Manifest order is the submitted CSV order. NAMES/SMILES are cross-checks;
    host canonical identity remains separate. Pose keys use (input ordinal,
    zero-based CSV pose). Actual score/pose qualification belongs to the host.
    """
    require(type(selected_pose_index) is int and 0 <= selected_pose_index < 10,
            "Explicit supported zero-based pose selection required")
    require(isinstance(method, str) and method and isinstance(unit, str) and unit
            and type(qualified) is bool, "Explicit producer method/unit/qualification required")
    inputs = {}
    for ordinal, entry in enumerate(input_manifest, 1):
        require(all(isinstance(entry.get(k), str) and entry[k] for k in (
            "candidate_id", "canonical_identity", "SMILES", "NAMES")), "Complete host input manifest required")
        inputs[ordinal] = deepcopy(entry)
    rows = csv_records(raw, {"SMILES", "NAMES", "Ligand_no", "Pose", "Score"})
    poses, by_input = [], defaultdict(dict)
    verified = set(verified_pose_keys)
    for index, source in enumerate(rows, 1):
        try:
            ordinal, pose = int(source["Ligand_no"]), int(source["Pose"])
        except ValueError as exc:
            raise ValueError("Integer input ordinal and CSV pose required") from exc
        require(ordinal in inputs and -1 <= pose < 10, "Unknown ligand ordinal or unsupported pose")
        expected = inputs[ordinal]
        require(all(source[k] == expected[k] for k in ("SMILES", "NAMES")),
                "Native output differs from retained input manifest")
        require(pose not in by_input[ordinal], "Ambiguous duplicate ligand/pose row")
        try:
            score = float(source["Score"])
            score = score if math.isfinite(score) else None
        except ValueError:
            score = None
        if pose == -1:
            status, reason = "FAILED", "Native ligand failure sentinel; finite Score is not a measurement"
        elif score is None:
            status, reason = "UNAVAILABLE", "No finite native pose score"
        elif not qualified or (ordinal, pose) not in verified:
            status, reason = "UNQUALIFIED", "Producer/pose identity and score evidence not qualified by host"
        else:
            status, reason = "SUCCESS", ""
        measurement = {**context, "candidate_id": expected["candidate_id"],
                       "canonical_identity": expected["canonical_identity"], "metric_id": "vina",
                       "value": source["Score"] if status == "SUCCESS" else "", "unit": unit,
                       "status": status, "reason": reason, "method_version": method,
                       "sample_id": f"input-{ordinal}:csv-pose-{pose}",
                       "csv_pose_index": pose, "sdf_pose_number": pose + 1 if pose >= 0 else None}
        record = {"source_row": index, "source": deepcopy(source), "measurement": measurement}
        poses.append(record)
        by_input[ordinal][pose] = record
    selected = []
    for ordinal, expected in inputs.items():
        records = by_input[ordinal]
        require(not (-1 in records and len(records) > 1), "Failure and success poses coexist for one ligand")
        record = records.get(-1) or records.get(selected_pose_index)
        if record:
            selected.append(deepcopy(record["measurement"]))
        else:
            selected.append({**context, "candidate_id": expected["candidate_id"],
                             "canonical_identity": expected["canonical_identity"], "metric_id": "vina",
                             "value": "", "unit": unit, "status": "UNAVAILABLE",
                             "reason": "Declared pose absent; no substitution or re-ranking",
                             "method_version": method, "sample_id": f"input-{ordinal}:absent"})
    return {"mapping_status": "source_defined_deployment_unverified", "source_sha256": sha256(raw),
            "selected_pose_index": selected_pose_index, "pose_records": poses,
            "selected_measurements": selected, "execution": "not_performed"}
