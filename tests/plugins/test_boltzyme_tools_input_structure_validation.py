"""Boltzyme input structure checks using real Gemmi; no worker imports."""

import gzip
import copy
import hashlib
import io
import json
import sys
from types import SimpleNamespace
import zipfile

import pytest

from plugins.boltzmann import boltzyme_tools_input_structure_validation as validation


def _pdb(count=12, *, missing=None, alt=" ", degenerate=False, ligand=True):
    lines = []
    serial = 0
    for number in range(1, count + 1):
        for name, offset in (("N", (0, 0, 0)), ("CA", (1, 1, 0)), ("C", (2, 0, 0)), ("O", (2, -1, 0))):
            if name == missing:
                continue
            serial += 1
            x, y, z = offset
            if degenerate:
                y = 0
            x += 3 * (number - 1)
            lines.append(f"ATOM  {serial:5d} {name:>4s}{alt}ALA A{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           {name[0]:>2s}")
    if ligand:
        serial += 1
        lines.append(f"HETATM{serial:5d}   C1 LIG B   1       1.000   2.000   3.000  1.00 20.00           C")
    return ("\n".join(lines) + "\nEND\n").encode()


def _zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


def _inspect(data, profile="Mol_Probity", payload=None, extension=".pdb", filename=None):
    report = SimpleNamespace(errors=[], warnings=[], info=[])
    summary = validation.inspect_structure(data, extension, profile, payload or {}, report, filename=filename)
    assert len(json.dumps(summary).encode()) <= validation.MAX_SUMMARY_BYTES
    return report, summary


@pytest.mark.parametrize("fault", [None, "hash", "missing_member", "undeclared", "role_overlap",
    "duplicate_id", "duplicate_selector", "selector", "atom_names", "protected", "stereo", "isotope",
    "mapping_index", "wrong_version", "bad_json", "nonfinite", "duplicate_json_key", "no_manifest",
    "dictionary_atoms", "dictionary_bytes", "manifest_bytes", "path", "bound_and_good"])
def test_molprobity_ligand_bundle_roles_and_failures_use_public_file_validation(tmp_path, fault):
    """Tiny bundle is a parsing fixture, not a chemically validated restraint set."""
    pytest.importorskip("gemmi")
    pytest.importorskip("rdkit")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file

    dictionary = b"data_comp_LIG\nloop_\n_chem_comp_atom.atom_id\n_chem_comp_atom.type_symbol\nC1 C\n"
    binding = {"dictionary": "restraints/LIG.cif", "sha256": hashlib.sha256(dictionary).hexdigest(),
               "component_id": "LIG", "chain_id": "B", "residue_number": 1,
               "smiles": "C", "atom_mapping": {"C1": 0}}
    document = {"schema": "molprobity-ligand-bundle.v1", "structures": [
        {"path": "structures/complex.pdb", "ligands": [binding]}]}
    extra = []
    if fault == "hash": binding["sha256"] = "0" * 64
    if fault == "missing_member": binding["dictionary"] = "absent.cif"
    if fault == "undeclared": extra.append(("extra.pdb", _pdb()))
    if fault == "role_overlap": document["structures"].append({"path": binding["dictionary"], "ligands": []})
    if fault == "duplicate_id":
        document["structures"].append({"path": "other/complex.pdb", "ligands": []})
        extra.append(("other/complex.pdb", _pdb()))
    if fault == "duplicate_selector": document["structures"][0]["ligands"].append(copy.deepcopy(binding))
    if fault in {"selector", "bound_and_good"}: binding["residue_number"] = 999
    if fault == "bound_and_good":
        document["structures"].append({"path": "good.pdb", "ligands": []})
        extra.append(("good.pdb", _pdb(ligand=False)))
    if fault == "atom_names": binding["atom_mapping"] = {"XX": 0}
    if fault == "protected": binding["component_id"] = "ALA"
    if fault == "stereo": binding["smiles"] = "F[C@H](Cl)Br"
    if fault == "isotope": binding["smiles"] = "[13CH4]"
    if fault == "mapping_index": binding["atom_mapping"] = {"C1": 5}
    if fault == "wrong_version": document["schema"] = "unknown"
    if fault == "path": document["structures"][0]["path"] = "structures/../complex.pdb"
    if fault == "dictionary_atoms": dictionary += b"C2 C\n" * 2048
    if fault == "dictionary_bytes": dictionary += b"#" + b"x" * (1024 ** 2)
    if fault in {"dictionary_atoms", "dictionary_bytes"}: binding["sha256"] = hashlib.sha256(dictionary).hexdigest()
    manifest = json.dumps(document).encode()
    if fault == "bad_json": manifest = b"{"
    if fault == "nonfinite": manifest = manifest.replace(b'"residue_number": 1', b'"residue_number": NaN')
    if fault == "duplicate_json_key": manifest = manifest.replace(b'"residue_number": 1', b'"residue_number": 1, "residue_number": 1')
    if fault == "manifest_bytes": manifest += b" " * (1024 ** 2)
    entries = [("structures/complex.pdb", _pdb()), ("restraints/LIG.cif", dictionary), *extra]
    if fault != "no_manifest": entries.append(("ligand_manifest.json", manifest))
    source = tmp_path / "input.zip"
    original = _zip(entries)
    source.write_bytes(original)
    report = validate_file(source, ContractStore().file_rule("Mol_Probity", "input_path"), {})
    assert bool(report.errors) is (fault is not None), report.as_dict()
    assert source.read_bytes() == original
    if fault is None:
        candidates = report.inventory["data"]["candidates"]
        assert [c["candidate_id"] for c in candidates] == ["complex"]
        assert report.as_dict()["level"] == "partial"
        assert any("chemistry" in warning or "graph agreement" in warning for warning in report.warnings)


@pytest.mark.parametrize("profile,payload,options,expected", [
    ("deepallo", {"chain_id": "A"}, {}, None),
    ("deepallo", {"chain_id": "Z"}, {}, "chain"),
    ("deepallo", {"chain_id": "A"}, {"count": 5}, "more than 10"),
    ("deepallo", {"chain_id": "A"}, {"missing": "CA"}, "CA"),
    ("deepallo", {"chain_id": "A"}, {"alt": "A"}, "alternate"),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1"]}, {}, None),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["99"]}, {}, "absent"),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1"]}, {"missing": "N"}, "N"),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1"]}, {"degenerate": True}, "degenerate"),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1", "2"]}, {"count": 2}, "non-motif"),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1"]}, {"count": 2001}, "2000"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG"}, {}, None),
    ("Enzyme_RFD3", {"motif_residues": ["A99"], "ligand": "LIG"}, {}, "Motif"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "UNK"}, {}, "Ligand"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG"}, {"count": 1025}, "residue limit"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "advanced_settings_enabled": "true", "advanced_settings": {"select_fixed_atoms": {"A1": "CB"}}}, {}, "CB"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "advanced_settings_enabled": "true", "advanced_settings": {"select_fixed_atoms": {"A1": "BKBN"}}}, {"missing": "O"}, "O"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "advanced_settings_enabled": "true", "advanced_settings": {"select_fixed_atoms": {"A1": "TIP"}}}, {}, None),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "min_length": 12, "max_length": 12, "advanced_settings_enabled": "true", "advanced_settings": {"partial_t": 0.5}}, {}, None),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "min_length": 50, "max_length": 60, "advanced_settings_enabled": "true", "advanced_settings": {"partial_t": 0.5}}, {}, "length"),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG", "min_length": 50, "max_length": 60, "advanced_settings_enabled": "true", "partial_t": 0.5}, {}, "length"),
])
def test_profile_checks_match_selected_structure(profile, payload, options, expected):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_pdb(**options), profile, payload)
    if expected:
        assert any(expected.lower() in error.lower() for error in report.errors)
        assert not summary["complete"]
    else:
        assert not report.errors
        assert summary["complete"]
        assert summary["candidates"][0]["models"][0]["residues"][0]["atoms"]


@pytest.mark.parametrize("extension", [".pdb", ".pdb.gz", ".cif", ".mmcif", ".mmcif.gz"])
def test_shared_parser_retains_residue_atom_and_altloc_inventory(extension):
    gemmi = pytest.importorskip("gemmi")
    data = _pdb(alt="A")
    if "cif" in extension:
        data = gemmi.read_pdb_string(data.decode()).make_mmcif_document().as_string().encode()
    if extension.endswith(".gz"):
        data = gzip.compress(data)
    report, summary = _inspect(data, extension=extension)
    assert not report.errors
    residue = summary["candidates"][0]["models"][0]["residues"][0]
    assert residue["chain_id"] == "A"
    assert ["CA", "A"] in residue["atoms"]


@pytest.mark.parametrize("entries,expected", [
    ([("../bad.pdb", b"bad")], "Unsafe"),
    ([("C:/bad.pdb", b"bad")], "Unsafe"),
    ([("a.pdb", b"bad"), ("nested/a.cif", b"bad")], "Duplicate"),
    ([("notes.txt", b"nothing")], "no supported"),
    ([("bad.pdb", b"not a structure")], "No valid"),
    ([("bad.cif.gz", gzip.compress(b"malformed cif"))], "No valid"),
])
def test_archive_safety_and_empty_batches_fail(entries, expected):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_zip(entries), extension=".zip")
    assert any(expected.lower() in error.lower() for error in report.errors)
    assert not summary["complete"]


@pytest.mark.parametrize("bad_name,bad_content", [("bad.pdb", b"garbage"),
                                                 ("bad.pdb.gz", gzip.compress(b"garbage")),
                                                 ("bad.cif.gz", gzip.compress(b"malformed cif"))])
def test_mixed_batch_keeps_candidate_failures_local(bad_name, bad_content):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_zip([(bad_name, bad_content), ("good.pdb", _pdb())]), extension=".zip")
    assert not report.errors
    assert summary["complete"]
    assert [item["valid"] for item in summary["candidates"]] == [False, True]
    assert report.warnings


def test_missing_parser_is_explicitly_unchecked(monkeypatch):
    monkeypatch.setitem(sys.modules, "gemmi", None)
    report, summary = _inspect(_pdb())
    assert not report.errors
    assert not summary["complete"]
    assert not summary["candidates"]
    assert any("Gemmi is unavailable" in warning for warning in report.warnings)
    report, summary = _inspect(_zip([("../bad.pdb", b"bad")]), extension=".zip")
    assert any("Unsafe" in error for error in report.errors)
    assert not summary["complete"]


def test_budget_clears_inventory_instead_of_false_complete(monkeypatch):
    pytest.importorskip("gemmi")
    monkeypatch.setattr(validation, "MAX_SUMMARY_BYTES", 512)
    report, summary = _inspect(_pdb())
    assert summary["truncated"] and not summary["complete"]
    assert not summary["candidates"]
    assert any("inventory cleared" in warning for warning in report.warnings)


def test_contextual_ensemble_and_missing_mapping_inventory():
    pytest.importorskip("gemmi")
    body = _pdb().decode().removesuffix("END\n")
    data = ("MODEL        1\n" + body + "ENDMDL\nMODEL        2\n" + body + "ENDMDL\nEND\n").encode()
    report, summary = _inspect(data, "Catalytic_Geometry", {"reaction_template": {"checks": []}})
    assert report.errors
    report, summary = _inspect(data, "Catalytic_Geometry", {"reaction_template": {"checks": [{"type": "ensemble_occupancy"}]}})
    assert not report.errors
    assert len(summary["candidates"][0]["models"]) == 2
    assert summary["mapping_inventory_complete"]
    assert report.info
    assert any("Ensemble geometry" in warning for warning in report.warnings)


@pytest.mark.parametrize("template", [None, "uploaded/reaction_template.json"])
@pytest.mark.parametrize("extension", [".pdb", ".zip"])
def test_deferred_ensemble_context_preserves_valid_structural_receipt(template, extension):
    pytest.importorskip("gemmi")
    body = _pdb().decode().removesuffix("END\n")
    data = ("MODEL        1\n" + body + "ENDMDL\nMODEL        2\n" + body + "ENDMDL\nEND\n").encode()
    if extension == ".zip":
        data = _zip([("ensemble.pdb", data)])
    report, summary = _inspect(data, "Catalytic_Geometry", {"reaction_template": template}, extension)
    assert not report.errors and not report.warnings
    assert summary["complete"] and not summary["truncated"]
    assert summary["candidates"][0]["valid"]
    assert len(summary["candidates"][0]["models"]) == 2
    assert any("deferred to joint" in message for message in report.info)


@pytest.mark.parametrize("mutation,expected", [
    (lambda data: data.replace(b"   1.000", b"     nan", 1), "nonfinite"),
    (lambda data: data.splitlines()[0] + b"\n" + data, "duplicate atom"),
    (lambda data: data.replace(b"END\n", b"") + data, "duplicate"),
    (lambda data: data.replace(b"  33.000", b" 100.000"), "connected"),
])
def test_coordinate_identity_and_partial_backbone_defects(mutation, expected):
    pytest.importorskip("gemmi")
    payload = {"motif_residues": ["A1"], "ligand": "LIG", "min_length": 12, "max_length": 12,
               "advanced_settings_enabled": "true", "advanced_settings": {"partial_t": 0.5}}
    report, summary = _inspect(mutation(_pdb()), "Enzyme_RFD3", payload)
    assert any(expected in error.lower() for error in report.errors)
    assert not summary["complete"]


def test_expansion_and_member_limits_are_enforced_without_parser(monkeypatch):
    monkeypatch.setitem(sys.modules, "gemmi", None)
    monkeypatch.setitem(validation.PROFILES, "Mol_Probity", (100, 20000, 500000))
    report, summary = _inspect(gzip.compress(b"x" * 101), extension=".pdb.gz")
    assert any("byte limit" in error for error in report.errors)
    assert not summary["complete"]
    report, summary = _inspect(_zip([("big.pdb", b"x" * 101)]), extension=".zip")
    assert any("member byte limit" in error for error in report.errors)


def test_zip_entry_and_ratio_caps_do_not_depend_on_gemmi(monkeypatch):
    monkeypatch.setitem(sys.modules, "gemmi", None)
    report, summary = _inspect(_zip([(f"{i}.txt", b"x") for i in range(1001)]), extension=".zip")
    assert any("1000 entries" in error for error in report.errors)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.pdb", b"x" * 100000)
    report, summary = _inspect(output.getvalue(), extension=".zip")
    assert any("ratio" in error for error in report.errors)


@pytest.mark.parametrize("metadata,complete", [([], True), ([("residue_mapping.csv", b"uninspected")], False),
                                            ([("entity_mapping.json", b"{}")], False)])
def test_mapping_coverage_depends_on_embedded_metadata(metadata, complete):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_zip([("design.pdb", _pdb()), *metadata]), "Catalytic_Geometry",
                               {"reaction_template": {"checks": []}}, extension=".zip")
    assert not report.errors
    assert summary["mapping_inventory_complete"] is complete
    assert any("mapping metadata" in warning for warning in report.warnings) is not complete


def test_single_filename_uses_same_molprobity_identity_as_archives():
    pytest.importorskip("gemmi")
    report, single = _inspect(_pdb(), filename="folder/My design.pdb")
    zipped_report, zipped = _inspect(_zip([("folder/My design.pdb", _pdb())]), extension=".zip")
    assert not report.errors and not zipped_report.errors
    assert single["candidates"][0]["candidate_id"] == zipped["candidates"][0]["candidate_id"]
    assert report.info and not report.warnings


@pytest.mark.parametrize("fixed,redesign,reject", [
    ("true", "true", False), (True, True, False),
    ("false", "true", True), (False, True, True), (None, "true", True),
    ({}, True, True), ({"A1": "ALL"}, True, True),
    ("false", "false", False), (None, False, False),
    ({"A1": "CA"}, False, False), ("not-an-atom-map", False, True),
])
def test_rfd3_fixed_flags_and_backbone_defaults(fixed, redesign, reject):
    pytest.importorskip("gemmi")
    payload = {"motif_residues": ["A1", "A2"], "ligand": "LIG", "advanced_settings_enabled": "true",
               "advanced_settings": {"select_fixed_atoms": fixed, "redesign_motif_sidechains": redesign}}
    report, summary = _inspect(_pdb(missing="O"), "Enzyme_RFD3", payload)
    assert bool(report.errors) is reject
    assert summary["complete"] is not reject


@pytest.mark.parametrize("flag", [None, False, "false", " FALSE "])
def test_rfd3_disabled_or_unspecified_advanced_settings_are_ignored(flag):
    pytest.importorskip("gemmi")
    payload = {"motif_residues": ["A1"], "ligand": "LIG", "min_length": 100, "max_length": 101,
               "partial_t": 0.5, "select_fixed_atoms": {"A1": "CB"},
               "advanced_settings": {"select_fixed_atoms": {"A1": "TIP"}, "partial_t": 0.5,
                                     "redesign_motif_sidechains": "true"}}
    if flag is not None:
        payload["advanced_settings_enabled"] = flag
    report, summary = _inspect(_pdb(missing="O"), "Enzyme_RFD3", payload)
    assert not report.errors and not report.warnings
    assert summary["complete"]


@pytest.mark.parametrize("data", [b"ATOM\n", b"ATOM      1      ALA A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n"])
def test_lenient_pdb_parser_cannot_admit_empty_atom_records(data):
    pytest.importorskip("gemmi")
    report, summary = _inspect(data)
    assert report.errors
    assert not summary["complete"]


@pytest.mark.parametrize("limits", [(50 * validation.MIB, 2, 500000), (50 * validation.MIB, 20000, 2)])
def test_molprobity_local_inventory_caps_are_unchecked_not_service_rejections(monkeypatch, limits):
    pytest.importorskip("gemmi")
    monkeypatch.setitem(validation.PROFILES, "Mol_Probity", limits)
    report, summary = _inspect(_pdb())
    assert not report.errors
    assert not summary["complete"]
    assert any("Local per-model" in warning for warning in report.warnings)


def _wrap_structure(data, wrapping):
    if wrapping == "pdb":
        return data, ".pdb"
    if wrapping == "gzip":
        return gzip.compress(data), ".pdb.gz"
    name = "candidate.pdb.gz" if wrapping == "zip-gzip" else "candidate.pdb"
    return _zip([(name, gzip.compress(data) if wrapping == "zip-gzip" else data)]), ".zip"


@pytest.mark.parametrize("wrapping", ["pdb", "gzip", "zip", "zip-gzip"])
@pytest.mark.parametrize("field", [b"        ", b"     nan", b"     inf", b"invalid!"])
def test_pdb_numeric_fields_are_required_before_permissive_parsing(wrapping, field):
    pytest.importorskip("gemmi")
    data = _pdb()
    # Keep the rest of a valid structure: the malformed atom cannot be skipped.
    data = data[:30] + field + data[38:]
    data, extension = _wrap_structure(data, wrapping)
    report, summary = _inspect(data, extension=extension)
    assert report.errors
    assert not summary["complete"]
    if extension == ".zip":
        assert summary["candidates"][0]["valid"] is False
        assert "PDB atom record" in summary["candidates"][0]["error"]
    else:
        assert any("PDB atom record" in error for error in report.errors)


@pytest.mark.parametrize("wrapping", ["pdb", "gzip", "zip", "zip-gzip"])
@pytest.mark.parametrize("field", [b"   0.000", b"  -1.250", b" 1.0e+02"])
def test_strict_pdb_numeric_checks_preserve_valid_float_coordinates(wrapping, field):
    pytest.importorskip("gemmi")
    data = _pdb()
    data, extension = _wrap_structure(data[:30] + field + data[38:], wrapping)
    report, summary = _inspect(data, extension=extension)
    assert not report.errors
    assert summary["complete"]
    assert summary["candidates"][0]["valid"]


@pytest.mark.parametrize("extension", [".pdb", ".cif"])
def test_molprobity_multimodel_candidates_fail_without_poisoning_mixed_batches(extension):
    gemmi = pytest.importorskip("gemmi")
    body = _pdb().decode().removesuffix("END\n")
    data = ("MODEL        1\n" + body + "ENDMDL\nMODEL        2\n" + body + "ENDMDL\nEND\n").encode()
    if extension == ".cif":
        data = gemmi.read_pdb_string(data.decode()).make_mmcif_document().as_string().encode()
    report, summary = _inspect(data, extension=extension)
    assert any("exactly one model" in error for error in report.errors)
    assert not summary["complete"]
    report, summary = _inspect(_zip([("bad" + extension, data), ("good.pdb", _pdb())]), extension=".zip")
    assert not report.errors
    assert summary["complete"]
    assert [candidate["valid"] for candidate in summary["candidates"]] == [False, True]


@pytest.mark.parametrize("profile,payload", [
    ("deepallo", {"chain_id": "A"}),
    ("enzycontrol", {"chain_id": "A", "motif_residues": ["1"]}),
    ("Enzyme_RFD3", {"motif_residues": ["A1"], "ligand": "LIG"}),
    ("Catalytic_Geometry", {"reaction_template": {"checks": []}}),
])
def test_distinct_protein_and_hetero_entities_may_share_residue_number(profile, payload):
    pytest.importorskip("gemmi")
    data = _pdb().replace(b"LIG B   1", b"LIG A   1")
    report, summary = _inspect(data, profile, payload)
    assert not report.errors
    assert summary["complete"]
    rows = summary["candidates"][0]["models"][0]["residues"]
    assert sum(row["chain_id"] == "A" and row["residue_number"] == 1 for row in rows) == 2


@pytest.mark.parametrize("wrapping", ["pdb", "gzip", "zip", "zip-gzip"])
def test_ligand_residue_number_must_not_default_to_zero(wrapping):
    pytest.importorskip("gemmi")
    data, extension = _wrap_structure(_pdb().replace(b"LIG B   1", b"LIG B    "), wrapping)
    report, summary = _inspect(data, extension=extension)
    assert report.errors and not summary["complete"]
    diagnostics = report.errors + report.warnings
    assert any("explicit residue number" in message for message in diagnostics)


@pytest.mark.parametrize("profile", ["deepallo", "enzycontrol"])
@pytest.mark.parametrize("limits", [(100, 20000, 500000), (50 * validation.MIB, 2, 500000),
                                   (50 * validation.MIB, 20000, 2)])
def test_deepallo_enzycontrol_connector_caps_are_not_worker_rejections(monkeypatch, profile, limits):
    pytest.importorskip("gemmi")
    monkeypatch.setitem(validation.PROFILES, profile, limits)
    report, summary = _inspect(_pdb(), profile, {"chain_id": "A", "motif_residues": ["1"]})
    assert not report.errors and not summary["complete"]
    assert any("Local" in warning and "budget" in warning for warning in report.warnings)


@pytest.mark.parametrize("bad", [b"not gzip", gzip.compress(_pdb())[:-4], gzip.compress(b"")])
@pytest.mark.parametrize("bad_first", [True, False])
def test_corrupt_or_empty_gzip_discovery_aborts_even_mixed_valid_batches(bad, bad_first):
    pytest.importorskip("gemmi")
    entries = [("bad.pdb.gz", bad), ("good.pdb", _pdb())]
    report, summary = _inspect(_zip(entries if bad_first else entries[::-1]), extension=".zip")
    assert report.errors and not summary["complete"]
    assert any("gzip" in error or "empty" in error for error in report.errors)


@pytest.mark.parametrize("profile,payload", [("Mol_Probity", {}),
                                            ("Catalytic_Geometry", {"reaction_template": {"checks": []}})])
def test_gemmi_hybrid36_residue_numbers_remain_supported(profile, payload):
    pytest.importorskip("gemmi")
    data = _pdb().replace(b"LIG B   1", b"LIG BA000")
    report, summary = _inspect(data, profile, payload)
    assert not report.errors and summary["complete"]
    ligand = summary["candidates"][0]["models"][0]["residues"][-1]
    assert ligand["residue_number"] == 10000


@pytest.mark.parametrize("source", ["rfd3", "RFD3", "enzycontrol", "canonical"])
def test_explicit_native_zip_source_requires_adapter_review(source):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_zip([("x.pdb", _pdb())]), "Catalytic_Geometry",
                               {"input_source": source, "reaction_template": {"checks": []}}, ".zip")
    assert not report.errors
    assert summary["candidates"][0]["valid"]
    assert any("Native adapter/output-kind eligibility is unchecked" in warning for warning in report.warnings)


@pytest.mark.parametrize("source", ["auto", "generic", " AUTO "])
@pytest.mark.parametrize("prefix", ["", "backbones/"])
def test_auto_generic_zip_mapping_coverage_accounts_for_backbone_bundles(source, prefix):
    pytest.importorskip("gemmi")
    report, summary = _inspect(_zip([(prefix + "x.pdb", _pdb())]), "Catalytic_Geometry",
                               {"input_source": source, "reaction_template": {"checks": []}}, ".zip")
    assert not report.errors
    assert summary["candidates"][0]["valid"]
    assert summary["mapping_inventory_complete"] is (not bool(prefix))
    assert bool(report.warnings) is bool(prefix)
    if prefix:
        assert any("mapping metadata/adapters are uninspected" in warning for warning in report.warnings)
