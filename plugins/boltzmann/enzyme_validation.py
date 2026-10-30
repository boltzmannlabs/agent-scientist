"""RFD3 request preparation and enzyme contract checks, not scientific scoring."""

from copy import deepcopy
import json
from pathlib import PurePosixPath
import re

from .contracts import ContractStore, validate_schema


def prepare_molprobity_payload(payload):
    """Match the worker's explicit measurement-only policy without editing user data."""
    prepared = deepcopy(payload)
    if prepared.get("execution_mode", "measurement_only") == "measurement_only":
        prepared.pop("quality_thresholds", None)
    return prepared


def validate_storage_paths(store, job, payload, report):
    for name, prop in store.file_fields(job).items():
        value = payload.get(name)
        if value is None or prop["x-input-kind"] == "file_or_value" and not isinstance(value, str):
            continue
        path = PurePosixPath(value)
        formats = store.file_rule(job, name).get("formats", [])
        if (not value or value != value.strip() or path.is_absolute() or ".." in path.parts
                or "\\" in value or ":" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
                or formats and not any(value.lower().endswith("." + suffix) for suffix in formats)):
            report.errors.append(f"{name}: expected a safe relative platform path with a documented file extension.")


def validate_enzycontrol(payload, report):
    from .boltzyme_tools_input_sequence_validation import validate_molecule
    validate_molecule(payload["smiles"], "smiles", report, maximum_atoms_including_hydrogens=128)


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
    report.info.append("Template shape and internal bounds checked; structural compatibility is checked against same-profile input receipts at submission. Source metadata is not proof of the scientific claims.")


def _template_selectors(check):
    yield from check.get("atoms", [])
    for group in check.get("groups", []):
        yield from group
    if "predicate" in check:
        yield from _template_selectors(check["predicate"])


def _check_reference(models, selector, mapping, *, ensemble):
    location = selector
    if selector.get("mapping_key"):
        key = selector["mapping_key"]
        if key not in mapping:
            raise ValueError(f"required mapping key {key!r} is missing")
        location = mapping[key]
    selected_models = models if ensemble else models[:1]
    for model in selected_models:
        matches = [row for row in model["residues"]
                   if row["chain_id"] == location["chain_id"]
                   and row["residue_number"] == location["residue_number"]
                   and row["insertion_code"] == location.get("insertion_code", "")
                   and (not selector.get("component_id") or
                        row["residue_name"].upper() == selector["component_id"].upper())]
        if len(matches) != 1:
            raise ValueError(f"residue/ligand {location['chain_id']}:{location['residue_number']} is missing or ambiguous")
        atoms = [atom for atom in matches[0]["atoms"] if atom[0] == selector["atom_name"]]
        if selector.get("altloc") is not None:
            atoms = [atom for atom in atoms if atom[1] == selector["altloc"]]
        elif any(atom[1] for atom in atoms):
            raise ValueError(f"atom {selector['atom_name']} requires an explicit alternate location")
        if len(atoms) != 1:
            raise ValueError(f"atom {selector['atom_name']} is missing or ambiguous")


def _bound_mappings(mappings, binding, mapping_complete, report):
    result = deepcopy(mappings)
    shared = result.setdefault("*", {})
    for role, target in binding.get("mapping_keys", {}).items():
        if isinstance(target, dict):
            shared[role] = target
    unresolved = set()
    for role, target in binding.get("mapping_keys", {}).items():
        if not isinstance(target, str):
            continue
        found = False
        if target in shared:
            shared[role] = shared[target]
            found = True
        for name, candidate in result.items():
            if name != "*" and target in candidate:
                candidate[role] = candidate[target]
                found = True
        if not found:
            if mapping_complete:
                report.errors.append(f"template_binding role {role!r} references unavailable mapping key {target!r}.")
            else:
                unresolved.add(role)
    return result, unresolved


def validate_joint_files(payload, inventories, report):
    """Match cached same-profile inputs, without downloads or scientific scoring."""
    expected = {"input_path": "structure", "reaction_template": "reaction_template",
                "template_binding": "template_binding"}
    if payload.get("mapping_path"):
        expected["mapping_path"] = "mapping"
    missing = [name for name, kind in expected.items() if inventories.get(name, {}).get("kind") != kind]
    if missing:
        report.warnings.append("Catalytic Geometry joint checks lack a current parsed receipt for: " + ", ".join(missing) + ".")
        return
    structure = inventories["input_path"]["data"]
    if structure.get("truncated") or not structure.get("candidates"):
        report.warnings.append("Catalytic Geometry atom/mapping references remain unchecked because the structure inventory is incomplete.")
        return
    template = inventories["reaction_template"]["data"]
    binding = inventories["template_binding"]["data"]
    mappings = inventories.get("mapping_path", {}).get("data", {})
    mapping_complete = structure.get("mapping_inventory_complete", False)
    mappings, unresolved = _bound_mappings(mappings, binding, mapping_complete, report)
    if report.errors:
        return
    if unresolved:
        report.warnings.append("Embedded upstream mappings were not inspected; binding roles remain unchecked: " + ", ".join(sorted(unresolved)) + ".")
    ensemble = any(check["type"] == "ensemble_occupancy" for check in template["checks"])
    known_invalid, usable, unknown = [], 0, bool(unresolved) or not structure.get("complete")
    for candidate in structure["candidates"]:
        if not candidate.get("valid"):
            known_invalid.append(str(candidate.get("candidate_id")))
            continue
        models = candidate["models"]
        candidate_id = candidate["candidate_id"]
        mapping = {**mappings.get("*", {}), **mappings.get(candidate_id, {})}
        try:
            if len(models) != 1 and not ensemble:
                raise ValueError("multiple models require an ensemble_occupancy template")
            for check in template["checks"]:
                for selector in _template_selectors(check):
                    key = selector.get("mapping_key")
                    if key not in mapping and key and (key in unresolved or not mapping_complete):
                        unknown = True
                        report.warnings.append(f"{candidate_id}: upstream mapping {key!r} could not be checked from the retained inventory.")
                        continue
                    _check_reference(models, selector, mapping, ensemble=check["type"] == "ensemble_occupancy")
            usable += 1
        except ValueError as exc:
            known_invalid.append(f"{candidate_id}: {exc}")
    if known_invalid:
        detail = "; ".join(known_invalid[:5])
        if not usable and not unknown:
            report.errors.append("No candidate has resolvable template references: " + detail)
        else:
            report.warnings.append("Some candidates have invalid or unresolved template inputs: " + detail)


def validate_request(check, payload, report):
    workflows = {"random_mutagenesis": validate_mutagenesis, "genzyme": validate_genzyme,
                 "solublempnn": validate_solublempnn, "motif_scaffolding": validate_scaffolding,
                 "netsolp": validate_netsolp}
    if check in workflows:
        workflows[check](payload, report)
        return
    if check == "enzycontrol":
        validate_enzycontrol(payload, report)
        return
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
    contig = advanced.get("contig", "")
    generated = []
    indexed = set()
    contig_upper = 0
    for token in re.split(r"[,/]", contig):
        token = token.strip()
        match = re.fullmatch(r"([A-Za-z]?)(\d+)(?:-(\d+))?", token)
        if not match:
            continue  # Native syntax beyond this subset remains explicitly unchecked.
        chain, start, end = match.groups()
        start, end = int(start), int(end or start)
        if chain:
            if end < start:
                report.errors.append("contig: indexed residue ranges must be ascending.")
            indexed.update(motif for motif in motifs if motif[0] == chain and start <= int(motif[1:]) <= end)
            contig_upper += max(0, end - start + 1)
        else:
            contig_upper += end
            if end:
                generated.append(token)
    if contig_upper + len(set(motifs) - indexed) > 512:
        report.errors.append("contig plus unindexed motifs exceeds 512 residues.")
    if "partial_t" in advanced and generated:
        report.errors.append("partial_t cannot be combined with contig segments that add new residues.")
    if "partial_t" in advanced or contig:
        report.warnings.append("Native RFD3 contig interpretation and diffusion noise-level compatibility remain unchecked; the worker must validate them before generation.")
    native_selections = [name for name in ("select_unfixed_sequence", "select_buried", "select_partially_buried",
        "select_exposed", "select_hbond_donor", "select_hbond_acceptor", "select_hotspots")
        if advanced.get(name) not in (None, "", "false", {}, [])]
    if native_selections:
        report.warnings.append("Native RFD3 conditioning selections remain unchecked: " + ", ".join(native_selections) + ".")


def validate_mutagenesis(payload, report):
    sequence, indices = payload["seq"], payload["indices"]
    if any(index < 0 or index >= len(sequence) for index in indices):
        report.errors.append("indices: protected positions must be zero-based positions within seq.")
    if len(set(indices)) >= len(sequence):
        report.errors.append("indices: at least one sequence position must remain available for mutation.")


def validate_genzyme(payload, report):
    from .boltzyme_tools_input_sequence_validation import validate_molecule
    for field in ("input_substrate", "input_product"):
        validate_molecule(payload[field], field, report)
    enabled = payload.get("complex_generation", "false").strip().lower()
    if enabled not in {"true", "false"}:
        report.errors.append("complex_generation: expected a true/false string.")
    if enabled == "true":
        top_k = payload.get("top_k")
        if type(top_k) is not int or not 1 <= top_k <= payload["num_structures"]:
            report.errors.append("top_k: complex generation requires a positive integer not exceeding num_structures.")


def validate_solublempnn(payload, report):
    if not payload["num_seq"].isdigit() or int(payload["num_seq"]) < 1:
        report.errors.append("num_seq: expected a positive integer string.")


def validate_scaffolding(payload, report):
    minimum, maximum = payload["min_lengths"], payload["max_lengths"]
    if (minimum, maximum) != (0, 0) and (minimum <= 0 or maximum <= minimum):
        report.errors.append("Scaffold lengths must both be zero (unrestricted), or satisfy 0 < min_lengths < max_lengths; the native maximum is exclusive.")
    for field in ("contigs", "targets"):
        if not payload[field].strip():
            report.errors.append(f"{field}: a nonblank value is required.")
    if not report.errors:
        report.warnings.append("Native FrameFlow contig interpretation and target/motif compatibility remain unchecked locally.")


def validate_netsolp(payload, report):
    if payload.get("prediction_type") == "US":
        report.warnings.append("NetSolP combined mode is US in the Node contract but SU in the inspected worker; deployed mode compatibility remains unverified. Do not silently substitute either spelling.")
