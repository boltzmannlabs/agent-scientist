"""PepPatch input/receipt invariants; no remote jobs or local ligand chemistry."""

from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import zipfile

from plugins.boltzmann.contracts import ContractStore
from plugins.boltzmann.file_validation import validate_file
from plugins.boltzmann import preflight


def _pdb(ligand=False):
    protein = "ATOM      1   CA ALA A   1       1.000   2.000   3.000  1.00 20.00           C\n"
    extra = "HETATM    2   C1 LIG B   1       5.000   2.000   3.000  1.00 20.00           C\n" if ligand else ""
    return (protein + extra + "END\n").encode()


def _manifest():
    return {"schema": "peppatch-complex-input.v1", "structure": "poses/complex.pdb",
            "ligands": [{"chain_id": "B", "residue_number": 1, "insertion_code": "",
                         "component_id": "LIG", "smiles": "C", "atom_mapping": {"C1": 0},
                         "chemistry_source": "Synthetic fixture; not a validated ligand state"}]}


def _zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
    return output.getvalue()


def test_peppatch_legacy_and_complex_uploads_preserve_bytes_and_approval_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    monkeypatch.setitem(sys.modules, "rdkit", None)
    store = ContractStore()
    assert set(store.tool("Pep_Patch")["request_schema"]["properties"]) == {"input_path"}
    assert set(store.file_fields("Pep_Patch")) == {"input_path"}
    assert store.validate_payload("Pep_Patch", {"input_path": "fixture/x.pdb", "scale": "rdkit-crippen"}).errors
    uploaded = []

    def upload(snapshot):
        uploaded.append(Path(snapshot).read_bytes())
        return "fixture/" + Path(snapshot).name

    document = _manifest()
    # Bad SMILES is intentionally accepted by the lightweight client. A partial
    # receipt must never imply worker chemistry validation or bypass approval.
    document["ligands"][0]["smiles"] = "not-a-SMILES"
    integral = deepcopy(document)
    integral["ligands"][0]["residue_number"] = 1.0
    integral["ligands"][0]["atom_mapping"]["C1"] = 0.0
    fixtures = [("protein.pdb", _pdb(), False),
                ("protein.zip", _zip([("nested/", b""), ("nested/protein.pdb", _pdb())]), False),
                ("complex.zip", _zip([("poses/complex.pdb", _pdb(True)),
                                       ("peppatch_manifest.json", json.dumps(document))]), True),
                ("complex-integral-json.zip", _zip([("poses/complex.pdb", _pdb(True)),
                                       ("peppatch_manifest.json", json.dumps(integral))]), True)]
    for filename, contents, partial in fixtures:
        source = tmp_path / filename
        source.write_bytes(contents)
        before = len(uploaded)
        result = preflight.validated_upload(str(source), "Pep_Patch", "input_path", {}, False, upload)
        if partial:
            assert result["status"] == "approval_required", result
            assert len(uploaded) == before
            result = preflight.validated_upload(str(source), "Pep_Patch", "input_path", {}, True, upload)
        assert result["status"] == "uploaded", result
        assert uploaded[before:] == [contents]
        assert source.read_bytes() == contents
        payload = {"input_path": result["s3_path"]}
        report = preflight.preflight_submission("Pep_Patch", payload)
        assert not report.errors, report.as_dict()
        assert bool(report.warnings) is partial, report.as_dict()
        assert len(report.upload_receipt_ids) == 1
        if partial:
            assert any("worker" in warning and "chem" in warning.lower() for warning in report.warnings)
            assert preflight.decision(report, False)["status"] == "approval_required"
        assert preflight.decision(report, True) is None
        assert payload == {"input_path": result["s3_path"]}


def test_peppatch_rejects_bad_bundle_identity_and_manifest_shape_without_chemistry(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "rdkit", None)
    rule = ContractStore().file_rule("Pep_Patch", "input_path")
    document = _manifest()
    mutations = []
    for field, value in (("chain_id", "Z"), ("residue_number", True), ("insertion_code", "A"),
                         ("component_id", "UNK"), ("atom_mapping", {"XX": 0}),
                         ("atom_mapping", {"C1": True}), ("atom_mapping", {"C1": 1}),
                         ("chemistry_source", " \t")):
        changed = deepcopy(document)
        changed["ligands"][0][field] = value
        mutations.append(changed)
    changed = deepcopy(document)
    changed["ligands"].append(deepcopy(changed["ligands"][0]))
    mutations.extend([changed, {**document, "ligands": []},
                      {**document, "structure": "absent.pdb"},
                      {**document, "structure": "../poses/complex.pdb"},
                      {**document, "schema": "wrong-version"},
                      {**document, "extra": "undocumented"}])
    entries = [[("poses/complex.pdb", _pdb(True)), ("peppatch_manifest.json", json.dumps(changed))]
               for changed in mutations]
    entries.extend([
        [("peppatch_manifest.json", json.dumps(document))],
        [("a.pdb", _pdb()), ("b.pdb", _pdb())],
        [("poses/complex.pdb", _pdb(True))],
        [("protein.pdb", _pdb()), ("notes.txt", "extra")],
        [("protein.pdb", _pdb()), ("extra.json", "{}")],
        [("../escaped.pdb", _pdb())],
        [("PROTEIN.PDB", _pdb()), ("protein.pdb", _pdb())],
        [("poses/complex.pdb", _pdb(True)), ("peppatch_manifest.json", json.dumps(document).replace(
            '"C1": 0', '"C1": 0, "C1": 0'))],
    ])
    for index, members in enumerate(entries):
        source = tmp_path / f"bad_{index}.zip"
        original = _zip(members)
        source.write_bytes(original)
        report = validate_file(source, rule, {})
        assert report.errors, (index, report.as_dict())
        assert preflight.decision(report, True)["status"] == "not_started"
        assert source.read_bytes() == original
    raw = tmp_path / "complex.pdb"
    raw.write_bytes(_pdb(True))
    assert validate_file(raw, rule, {}).errors  # A residue name is not reference chemistry.
