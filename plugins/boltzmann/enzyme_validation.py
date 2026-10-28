"""RFD3 request preparation and enzyme contract checks, not scientific scoring."""

from copy import deepcopy
import json

from .contracts import ContractStore, validate_schema


def _wire_toggle(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return value.strip().lower() if isinstance(value, str) else value


def _prepare_optional_controls(controls, schema):
    # Only documented optional fields are placeholders. Unknown keys and required
    # geometry/selection contents must reach validation unchanged.
    for name, prop in schema.get("properties", {}).items():
        if name not in controls:
            continue
        value = controls[name]
        if name not in schema.get("required", []) and (
            value is None or isinstance(value, str) and not value.strip()
        ):
            del controls[name]
        elif any(branch.get("enum") == ["true", "false"]
                 for branch in [prop, *prop.get("oneOf", [])]):
            controls[name] = _wire_toggle(value)
        elif isinstance(value, dict) and "properties" in prop:
            _prepare_optional_controls(value, prop)


def _has_unsupported_fields(value, schema):
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False and value.keys() - props.keys():
            return True
        return any(_has_unsupported_fields(item, props[name])
                   for name, item in value.items() if name in props)
    if isinstance(value, list):
        return any(_has_unsupported_fields(item, schema.get("items", {})) for item in value)
    return False


def prepare_rfd3_payload(payload, experiment_name):
    """Prepare one private copy for both validation and submission; never repair invalid values."""
    prepared = deepcopy(payload)
    explicitly_disabled = ("advanced_settings_enabled" in prepared
                           and _wire_toggle(prepared["advanced_settings_enabled"]) == "false")
    for name, value in (("job_name", experiment_name), ("n_samples", 1),
                        ("task_name", "rfd3"), ("advanced_settings_enabled", "false")):
        prepared.setdefault(name, value)
    prepared["advanced_settings_enabled"] = _wire_toggle(prepared["advanced_settings_enabled"])
    props = ContractStore().tool("Enzyme_RFD3")["request_schema"]["properties"]
    _prepare_optional_controls(prepared, {"properties": {
        name: props[name] for name in ("seed", "advanced_settings")}})
    advanced = prepared.get("advanced_settings")
    if explicitly_disabled and isinstance(advanced, dict):
        # Disabled controls may be stale, but never hide unsupported keys from
        # the strict contract (including nested sampler/geometry keys).
        if not _has_unsupported_fields(advanced, props["advanced_settings"]):
            del prepared["advanced_settings"]
    return prepared


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
    if ("ori_token" not in advanced and advanced.get("infer_ori_strategy") == "hotspots"
            and advanced.get("select_hotspots") in (None, "", "false", {})):
        report.errors.append("hotspots origin strategy requires a meaningful select_hotspots selection.")
    samples = payload.get("n_samples", 1)
    batch, count = advanced.get("diffusion_batch_size"), advanced.get("n_batches")
    if batch is not None and count is not None and batch * count != samples:
        report.errors.append("diffusion_batch_size * n_batches must equal n_samples.")
    elif (batch and samples % batch) or (count and samples % count):
        report.errors.append("Supplied batch controls must divide n_samples.")
    elif batch is None and count is not None and samples // count > 2:
        report.errors.append("Derived diffusion_batch_size (n_samples / n_batches) must not exceed 2.")
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
