"""Cross-field checks from the supplied enzyme contracts, not scientific scoring."""

import json

from .contracts import validate_schema


def _ordered(check, report, path):
    for lo, hi in (("min", "max"), ("distance_min", "distance_max"), ("angle_min", "angle_max")):
        if lo in check and hi in check and check[lo] > check[hi]:
            if check.get("type") != "dihedral":
                report.errors.append(f"{path}: {lo} must not exceed {hi}.")
    for atoms in [check.get("atoms", []), *check.get("groups", [])]:
        if len({json.dumps(atom, sort_keys=True) for atom in atoms}) != len(atoms):
            report.errors.append(f"{path}: atom references within a group must be distinct.")


def validate_template(value, schema, report):
    """The schema checks shapes; these checks cover relationships it cannot express."""
    checks = value["checks"]
    if len({check["check_id"] for check in checks}) != len(checks):
        report.errors.append("Template check_id values must be unique.")
    for check in checks:
        _ordered(check, report, "template check")
        if check["type"] == "ensemble_occupancy":
            predicate = check["predicate"]
            alternatives = []
            for branch in schema["properties"]["checks"]["items"]["oneOf"]:
                if branch["properties"]["type"]["const"] == "ensemble_occupancy":
                    continue
                alternatives.append(dict(branch, required=[k for k in branch["required"]
                    if k not in {"check_id", "rationale", "sources", "evidence_level"}]))
            validate_schema(predicate, {"oneOf": alternatives}, report, "predicate")
            if not report.errors:
                _ordered(predicate, report, "predicate")
    report.warnings.append("Template shape and internal bounds checked; actual atom existence, mappings, evidence and multi-model suitability need review.")


def validate_request(check, payload, report):
    if check != "enzyme_rfd3":
        raise ValueError(f"Unknown request check: {check}")
    motifs = payload["motif_residues"]
    ligands = payload["ligand"].split(",")
    if len(set(ligands)) != len(ligands):
        report.errors.append("ligand component codes must be distinct.")
    if payload["max_length"] < len(motifs):
        report.errors.append("max_length must include all selected motif residues.")
    advanced = payload.get("advanced_settings", {})
    if advanced and payload.get("advanced_settings_enabled", "false") != "true":
        report.errors.append('advanced_settings requires advanced_settings_enabled="true"; do not silently ignore supplied controls.')
    if "ori_token" in advanced and "infer_ori_strategy" in advanced:
        report.errors.append("ori_token and infer_ori_strategy are mutually exclusive.")
    if advanced.get("infer_ori_strategy") == "hotspots" and advanced.get("select_hotspots") in (None, "", "false", {}):
        report.errors.append("hotspots origin strategy requires a meaningful select_hotspots selection.")
    samples = payload.get("n_samples", 1)
    batch, count = advanced.get("diffusion_batch_size"), advanced.get("n_batches")
    if batch is not None and count is not None and batch * count != samples:
        report.errors.append("diffusion_batch_size * n_batches must equal n_samples.")
    elif (batch and samples % batch) or (count and samples % count):
        report.errors.append("Supplied batch controls must divide n_samples.")
    for rule in advanced.get("geometry_constraints", []):
        _ordered(rule, report, "geometry constraint")
        expected = {"distance": 2, "angle": 3}[rule["type"]]
        if len(rule["atoms"]) != expected:
            report.errors.append(f"{rule['type']} requires exactly {expected} atom references.")
        if rule["type"] == "angle" and rule["max"] > 180:
            report.errors.append("angle maximum must not exceed 180 degrees.")
        for atom in rule["atoms"]:
            if ("residue" in atom and atom["residue"] not in motifs) or ("ligand" in atom and atom["ligand"] not in ligands):
                report.errors.append("Geometry atom selectors must belong to the selected motifs/ligands.")
    if "partial_t" in advanced or "contig" in advanced:
        report.warnings.append("Review contig coverage/512-residue limit and partial-diffusion noise-level compatibility with the native worker; these specialized checks are not locally implemented.")
