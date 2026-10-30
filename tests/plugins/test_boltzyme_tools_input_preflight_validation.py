"""Boltzyme input preflight catches mistakes before transport and scopes receipts."""
import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest


@pytest.fixture(autouse=True)
def multiplex_profile_scope():
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    token = set_multiplex_context(True)
    try:
        yield
    finally:
        reset_multiplex_context(token)


def protein(count=12, *, omit=None, ligand=True, altloc=False):
    lines, serial = [], 0
    for i in range(1, count + 1):
        for name, offset in {"N": (-1.2, 0, 0), "CA": (0, 0, 0), "C": (1.3, .6, 0), "O": (1.7, 1.3, .2)}.items():
            if i == 1 and name == omit:
                continue
            serial += 1
            x, y, z = 3.8 * i + offset[0], offset[1], offset[2]
            alt = "A" if altloc and i == 1 and name == "CA" else " "
            lines.append(f"ATOM  {serial:5d} {name:^4s}{alt}ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {name[0]:>2s}")
    if ligand:
        lines.append(f"HETATM{serial+1:5d}  C1  ACT B 500      -2.000  -2.000  -2.000  1.00 20.00           C")
    return ("\n".join(lines) + "\nEND\n").encode()


@pytest.mark.parametrize("job,change,file_kind", [
    ("deepallo", {"chain_id": "Z"}, "valid"),
    ("deepallo", {}, "short"),
    ("deepallo", {}, "multimodel"),
    ("deepallo", {}, "missing_CA"),
    ("deepallo", {}, "altloc"),
    ("enzycontrol", {"motif_residues": ["9999"]}, "valid"),
    ("enzycontrol", {}, "missing_N"),
    ("Enzyme_RFD3", {"motif_residues": ["A9999"]}, "valid"),
    ("Enzyme_RFD3", {"ligand": "ZZZ"}, "valid"),
    ("Enzyme_RFD3", {"advanced_settings_enabled": "true", "advanced_settings": {"select_fixed_atoms": {"A1": "XX"}}}, "valid"),
    ("Enzyme_RFD3", {"min_length": 180, "max_length": 200, "advanced_settings_enabled": "true", "advanced_settings": {"partial_t": .5}}, "valid"),
    ("Mol_Probity", {}, "empty_cif"),
    ("Mol_Probity", {}, "multimodel_cif"),
    ("Mol_Probity", {}, "zip_no_structures"),
    ("Mol_Probity", {}, "zip_duplicate_ids"),
    ("Mol_Probity", {}, "zip_too_many"),
    ("Mol_Probity", {}, "zip_nested_gzip_invalid"),
])
def test_invalid_semantic_inputs_stop_before_upload(tmp_path, job, change, file_kind):
    gemmi = pytest.importorskip("gemmi")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from plugins.boltzmann.preflight import decision

    payloads = {
        "deepallo": {"chain_id": "A"},
        "enzycontrol": {"chain_id": "A", "motif_residues": ["1"], "smiles": "CCO", "seed": 1},
        "Enzyme_RFD3": {"motif_residues": ["A1"], "ligand": "ACT", "min_length": 10, "max_length": 20},
        "Mol_Probity": {},
    }
    payload = {**payloads[job], **change}
    data = protein()
    suffix = ".pdb"
    if file_kind.startswith("missing_"):
        data = protein(omit=file_kind.split("_", 1)[1])
    elif file_kind == "altloc":
        data = protein(altloc=True)
    elif file_kind == "short":
        data = protein(5)
    elif file_kind.startswith("multimodel"):
        part = protein().decode().removesuffix("END\n")
        data = ("MODEL        1\n" + part + "ENDMDL\nMODEL        2\n" + part + "ENDMDL\nEND\n").encode()
        if file_kind.endswith("cif"):
            data = gemmi.read_pdb_string(data.decode()).make_mmcif_document().as_string().encode()
            suffix = ".cif"
    elif file_kind == "empty_cif":
        data, suffix = b"data_not_a_structure\n", ".cif"
    path = tmp_path / ("candidate" + suffix)
    if file_kind.startswith("zip_"):
        path = tmp_path / "input.zip"
        with zipfile.ZipFile(path, "w") as archive:
            if file_kind == "zip_no_structures":
                archive.writestr("README.txt", "No structures")
            elif file_kind == "zip_duplicate_ids":
                archive.writestr("a/sample.pdb", data)
                archive.writestr("b/sample.pdb", data)
            elif file_kind == "zip_too_many":
                for i in range(1001):
                    archive.writestr(f"{i}.pdb", data)
            else:
                archive.writestr("bad.cif.gz", gzip.compress(b"not a CIF"))
    else:
        path.write_bytes(data)
    field = "pdb_path" if job == "enzycontrol" else "input_path"
    payload[field] = "fixture/" + path.name
    original = path.read_bytes()
    report = validate_file(path, ContractStore().file_rule(job, field), payload)
    assert report.errors, report.as_dict()
    assert decision(report, True)["status"] == "not_started"
    assert path.read_bytes() == original


def template(atom_residue=1):
    atom = {"entity_type": "residue", "chain_id": "A", "residue_number": atom_residue, "atom_name": "CA", "mapping_key": "site"}
    return {"reaction_state": "software_fixture", "sources": ["fixture:user_defined"], "checks": [
        {"check_id": "distance", "type": "distance", "rationale": "Software validation fixture, not mechanistic evidence",
         "sources": ["fixture:user_defined"], "evidence_level": "user_defined", "atoms": [atom,
         {"entity_type": "residue", "chain_id": "A", "residue_number": 2, "atom_name": "CA"}], "min": 0, "max": 100}]}


def test_molprobity_receipt_binds_ligand_limits_but_not_documentation(tmp_path, monkeypatch):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight
    from plugins.boltzmann.contracts import ContractStore

    source = tmp_path / "input.pdb"
    source.write_bytes(protein())
    payload = {"input_path": "fixture/input.pdb"}
    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    store = ContractStore()
    monkeypatch.setattr(preflight, "ContractStore", lambda: store)
    with _profile_runtime_scope(tmp_path / "profile"):
        uploaded = preflight.validated_upload(source, "Mol_Probity", "input_path", payload, False, lambda _: payload["input_path"])
        assert uploaded["status"] == "uploaded", uploaded
        store.files["Mol_Probity"]["files"]["input_path"]["notes"] = "Documentation edit"
        assert not preflight.preflight_submission("Mol_Probity", payload).errors
        thresholds_digest = preflight._contract_digest(store, "Mol_Probity", "quality_thresholds")
        store.limits["Mol_Probity"]["ligand_bundle"]["maximum_dictionary_atoms"] = 1
        assert preflight._contract_digest(store, "Mol_Probity", "quality_thresholds") == thresholds_digest
        report = preflight.preflight_submission("Mol_Probity", payload)
        assert any("validation rules or dependent inputs changed" in error for error in report.errors)


@pytest.mark.parametrize("fault", [None, "missing_atom", "missing_binding", "wrong_candidate", "wrong_altloc", "stale_context", "validator_changed"])
def test_joint_receipts_use_real_files_and_profile_scope(tmp_path, monkeypatch, fault):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight

    monkeypatch.setattr(preflight, "current_key", lambda: "same-fixture-key-for-both-profiles")
    structures = tmp_path / "candidate.pdb"
    structures.write_bytes(protein(altloc=fault == "wrong_altloc"))
    rules = template()
    binding = {"mapping_keys": {"site": {"chain_id": "A", "residue_number": 9999 if fault == "missing_atom" else 1}}}
    if fault == "missing_binding":
        binding["mapping_keys"]["site"] = "unavailable_upstream_key"
    rule_file, binding_file = tmp_path / "template.json", tmp_path / "binding.json"
    rule_file.write_text(json.dumps(rules), encoding="utf-8")
    binding_file.write_text(json.dumps(binding), encoding="utf-8")
    payload = {"input_path": "fixture/renamed_by_server.pdb", "reaction_template": "fixture/template.json",
               "template_binding": "fixture/binding.json"}
    files = {"input_path": structures, "reaction_template": rule_file, "template_binding": binding_file}
    if fault == "wrong_candidate":
        mapping = tmp_path / "mapping.json"
        mapping.write_text(json.dumps({"wrong_candidate": {"upstream": {"chain_id": "A", "residue_number": 1}}}), encoding="utf-8")
        binding_file.write_text(json.dumps({"mapping_keys": {"site": "upstream"}}), encoding="utf-8")
        payload["mapping_path"] = "fixture/mapping.json"
        files["mapping_path"] = mapping
    uploads = []
    profile_a, profile_b = tmp_path / "profile_a", tmp_path / "profile_b"
    with _profile_runtime_scope(profile_a):
        for field, source in files.items():
            before = source.read_bytes()
            def upload(snapshot, field=field):
                uploads.append(Path(snapshot).read_bytes())
                return payload[field]
            result = preflight.validated_upload(source, "Catalytic_Geometry", field, payload, True, upload)
            assert result["status"] == "uploaded", result
            assert source.read_bytes() == before
        if fault == "stale_context":
            payload["input_source"] = "rfd3"
        if fault == "validator_changed":
            monkeypatch.setattr(preflight, "VALIDATOR_VERSION", "changed-validation-semantics")
        report = preflight.preflight_submission("Catalytic_Geometry", payload)
        assert bool(report.errors) == bool(fault), report.as_dict()
        if not fault:
            assert not report.warnings, report.as_dict()
        original = report.as_dict()
        with _profile_runtime_scope(profile_b):
            foreign = preflight.preflight_submission("Catalytic_Geometry", payload)
            assert any("no current-profile validation receipt" in w for w in foreign.warnings)
            assert "inventory" not in foreign.as_dict()
        assert preflight.preflight_submission("Catalytic_Geometry", payload).as_dict() == original
    assert len(uploads) == len(files)


@pytest.mark.parametrize("smiles", ["not a SMILES", "C" * 50])
def test_smiles_and_worker_compatibility_are_not_generic_approval_warnings(smiles):
    pytest.importorskip("rdkit")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.enzyme_validation import prepare_molprobity_payload

    report = ContractStore().validate_payload("enzycontrol", {"pdb_path": "fixture/input.pdb", "chain_id": "A",
        "motif_residues": ["1"], "smiles": smiles, "seed": 1})
    assert report.errors
    assert report.info  # Seed documentation no longer masquerades as an unchecked input.
    for stale in [{"garbage": True}, [], "fixture/unused.json", None]:
        original = {"input_path": "fixture/input.pdb", "execution_mode": "measurement_only", "quality_thresholds": stale}
        copy_of_original = copy.deepcopy(original)
        prepared = prepare_molprobity_payload(original)
        assert "quality_thresholds" not in prepared and original == copy_of_original
        assert not ContractStore().validate_payload("Mol_Probity", prepared).errors
        strict = ContractStore().validate_payload("Mol_Probity", dict(original, execution_mode="validation"))
        # An uploaded JSON path is a supported validation input; its contents
        # require a receipt, rather than being rejected by the request schema.
        assert bool(strict.errors) == (not isinstance(stale, str))


@pytest.mark.parametrize("job,extra", [
    ("Enzyme_RFD3", {}),
    ("Enzyme_RFD3", {"advanced_settings_enabled": "false", "advanced_settings": {"partial_t": .5}}),
    ("Mol_Probity", {"quality_thresholds": {"unsupported": True}}),
    ("Mol_Probity", {"execution_mode": "measurement_only", "quality_thresholds": "fixture/stale.json"}),
])
def test_uploaded_receipts_survive_wire_preparation(tmp_path, monkeypatch, job, extra):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import tools, preflight

    source = tmp_path / "input.pdb"
    source.write_bytes(protein())
    payload = {"input_path": "fixture/input.pdb", **extra}
    if job == "Enzyme_RFD3":
        payload.update(motif_residues=["A1"], ligand="ACT", min_length=10, max_length=20)
    original = copy.deepcopy(payload)
    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    monkeypatch.setattr(tools, "current_key", lambda: "fixture-key")
    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    monkeypatch.setattr(tools, "time", SimpleNamespace(sleep=lambda _: None))
    sent = []
    def submit_request(experiment_data, job_name, experiment_name, **kwargs):
        sent.append({"experiment_data": experiment_data, "job_name": job_name, "experiment_name": experiment_name})
        return "fixture-job"
    monkeypatch.setattr(tools, "submit_request", submit_request)
    with _profile_runtime_scope(tmp_path / "profile"):
        uploaded = preflight.validated_upload(source, job, "input_path", payload, False, lambda _: payload["input_path"])
        assert uploaded["status"] == "uploaded", uploaded
        result = json.loads(tools.handle_boltzmann_submit(job_name=job,
            experiment_name="fixture-confirmed", experiment_data=payload, allow_partial_validation=False))
        assert result["status"] == "accepted", result
    assert len(sent) == 1
    if job == "Mol_Probity":
        assert "quality_thresholds" not in sent[0]["experiment_data"]
    assert payload == original


@pytest.mark.parametrize("ensemble", [False, True])
def test_ensemble_eligibility_is_resolved_with_uploaded_template(tmp_path, monkeypatch, ensemble):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight

    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    part = protein().decode().removesuffix("END\n")
    source = tmp_path / "models.pdb"
    source.write_text("MODEL        1\n" + part + "ENDMDL\nMODEL        2\n" + part + "ENDMDL\nEND\n", encoding="utf-8")
    rules = template()
    if ensemble:
        check = rules["checks"][0]
        predicate = {key: value for key, value in check.items() if key in {"type", "atoms", "min", "max"}}
        rules["checks"] = [{**{key: value for key, value in check.items() if key in {
            "check_id", "rationale", "sources", "evidence_level"}}, "type": "ensemble_occupancy",
            "predicate": predicate, "min": 0, "max": 1}]
    paths = {"input_path": source, "reaction_template": tmp_path / "template.json",
             "template_binding": tmp_path / "binding.json"}
    paths["reaction_template"].write_text(json.dumps(rules), encoding="utf-8")
    paths["template_binding"].write_text(json.dumps({"mapping_keys": {"site": {"chain_id": "A", "residue_number": 1}}}), encoding="utf-8")
    payload = {name: "fixture/" + path.name for name, path in paths.items()}
    with _profile_runtime_scope(tmp_path / "profile"):
        for name, path in paths.items():
            result = preflight.validated_upload(path, "Catalytic_Geometry", name, payload, False, lambda _, name=name: payload[name])
            assert result["status"] == "uploaded", result
        report = preflight.preflight_submission("Catalytic_Geometry", payload)
        assert bool(report.errors) is not ensemble, report.as_dict()
        if ensemble:
            assert not report.warnings, report.as_dict()


@pytest.mark.parametrize("change,valid", [("documentation", True), ("sampling", True), ("selection", False), ("validator", False)])
def test_receipts_follow_only_relevant_semantics(tmp_path, monkeypatch, change, valid):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight

    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    source = tmp_path / "input.pdb"
    source.write_bytes(protein())
    store = preflight.ContractStore()
    monkeypatch.setattr(preflight, "ContractStore", lambda: store)
    payload = {"input_path": "fixture/input.pdb", "motif_residues": ["A1"], "ligand": "ACT", "min_length": 10, "max_length": 20,
               "advanced_settings_enabled": "true"}
    with _profile_runtime_scope(tmp_path / "profile"):
        result = preflight.validated_upload(source, "Enzyme_RFD3", "input_path", payload, False, lambda _: payload["input_path"])
        assert result["status"] == "uploaded"
        if change == "documentation":
            store.files["Enzyme_RFD3"]["files"]["input_path"]["notes"] = "Documentation only"
        elif change == "sampling":
            payload.update(n_samples=2, seed=99)
            payload["advanced_settings"] = {"inference_sampler": {"num_timesteps": 300}}
        elif change == "selection":
            payload["motif_residues"] = ["A2"]
        else:
            monkeypatch.setattr(preflight, "VALIDATOR_VERSION", "next-version")
        report = preflight.preflight_submission("Enzyme_RFD3", payload)
        assert bool(report.errors) is not valid, report.as_dict()


@pytest.mark.parametrize("failure", ["renamed_file", "state_quota"])
def test_postupload_failure_retains_storage_reference(tmp_path, monkeypatch, failure):
    pytest.importorskip("gemmi")
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight

    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    source = tmp_path / "input.pdb"
    source.write_bytes(protein())
    reference = "fixture/no-supported-suffix" if failure == "renamed_file" else "fixture/input.pdb"
    if failure == "state_quota":
        def full(*args, **kwargs):
            raise ValueError("State quota exceeded")
        monkeypatch.setattr(preflight.PluginState, "set", full)
    with _profile_runtime_scope(tmp_path / "profile"):
        result = preflight.validated_upload(source, "Mol_Probity", "input_path", {}, False, lambda _: reference)
    assert result["s3_path"] == reference and result["uploaded"] is True
    assert result["status"] == "partial" and result["safe_to_retry"] is False


def test_missing_chemistry_dependency_is_disclosed(monkeypatch):
    import sys
    from plugins.boltzmann.contracts import ValidationReport
    from plugins.boltzmann.enzyme_validation import validate_enzycontrol
    monkeypatch.setitem(sys.modules, "rdkit", None)
    report = ValidationReport()
    validate_enzycontrol({"smiles": "CCO"}, report)
    assert not report.errors and any("RDKit is unavailable" in warning for warning in report.warnings)
