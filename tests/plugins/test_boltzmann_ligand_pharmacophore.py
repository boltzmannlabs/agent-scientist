"""Ligand hypotheses are distinct from receptor hypotheses; no service calls."""

import shutil

import pytest


@pytest.mark.parametrize("approved", [False, True])
def test_missing_validation_labels_is_rejected_before_upload(tmp_path, approved):
    from plugins.boltzmann.preflight import validated_upload

    source = tmp_path / "validation.csv"
    original = b"SMILES\nCCO\n"
    source.write_bytes(original)

    def forbidden_upload(_snapshot):
        pytest.fail("A validation CSV without LABELS must not reach upload transport")

    result = validated_upload(str(source), "ligand_pharmacophore", "validation_file",
                              {}, approved, forbidden_upload)
    assert isinstance(result, dict)
    assert result["stage"] == "validation" and result["status"] == "not_started", result
    assert any("LABELS" in error for error in result["validation"]["errors"])
    assert source.read_bytes() == original


@pytest.mark.parametrize("label", ["unknown", "Active", "1", "0", "active "])
def test_validation_rejects_undocumented_class_values_without_rewriting(tmp_path, label):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from plugins.boltzmann.preflight import decision

    source = tmp_path / "validation.csv"
    original = f"SMILES,LABELS\nCCO,{label}\n".encode()
    source.write_bytes(original)
    rule = ContractStore().file_rule("ligand_pharmacophore", "validation_file")
    report = validate_file(source, rule, {})
    assert report.errors, report.as_dict()
    assert any("LABELS" in error for error in report.errors)
    assert decision(report, True)["status"] == "not_started"
    assert source.read_bytes() == original


def test_ligand_contract_discovery_and_validated_input_modes(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from plugins.boltzmann.preflight import decision
    from sci_cli.science_catalog_view import catalog_rows

    source = ContractStore()
    installed = tmp_path / "installed-references"
    shutil.copytree(source.root, installed)
    job = "ligand_pharmacophore"
    payload = {
        "smiles_file": "fixture/training.csv", "validation_file": "fixture/validation.csv",
        "min_features": 2, "max_features": 5, "percentage": 0.5,
        "n_conformers": 20, "features": ["hb acceptor", "aromatic ring"],
    }
    for store in (source, ContractStore(installed)):
        tool = store.tool(job)
        rows = catalog_rows(store.root / "tool-contracts.v1.json", query="ligand pharmacophore hypothesis")
        assert any(row["name"] == tool["display_name"] for row in rows)
        assert set(store.file_fields(job)) == {"smiles_file", "validation_file"}
        assert store.diagnostic_collection(job) == "pharmacophorehypoligand"
        report = store.validate_payload(job, payload)
        assert not report.errors
        assert decision(report, False)["approval_required"]
        assert decision(report, True) is None
        assert store.validate_payload("Pharmacophore_Hypothesis", payload).errors
        for change in ({"min_features": 6}, {"percentage": 1.1}, {"percentage": -0.1},
                       {"n_conformers": "20"}, {"features": ["invented feature"]},
                       {"features": []}, {"validation_file": ""}):
            invalid = store.validate_payload(job, dict(payload, **change))
            assert invalid.errors, change
            assert decision(invalid, True)["status"] == "not_started"
        # Current public options and recorded submissions both include donor.
        assert not store.validate_payload(job, dict(payload, features=["hb donor"])).errors
        for field in store.file_fields(job):
            csv = tmp_path / (field + ".csv")
            cases = (("SMILES\nCCO\n", True), ("smiles\nCCO\n", False),
                     ("unrelated\nCCO\n", False), ("SMILES\n\"\"\n", False),
                     ("SMILES\n", False)) if field == "smiles_file" else (
                         ("SMILES,LABELS\nCCO,active\nCCN,inactive\n", True),
                         ("\ufeffSMILES,LABELS\r\nCCO,active\r\n", True),
                         ("SMILES\nCCO\n", False),
                         ("SMILES,LABEL\nCCO,active\n", False),
                         ("SMILES,labels\nCCO,active\n", False),
                         ("smiles,LABELS\nCCO,active\n", False),
                         ("SMILES,LABELS\nCCO,\n", False),
                         ("SMILES,LABELS\n,active\n", False),
                         ("SMILES,LABELS\n", False))
            for text, valid in cases:
                csv.write_bytes(text.encode())
                check = validate_file(csv, store.file_rule(job, field), payload)
                assert bool(check.errors) is not valid
                assert csv.read_bytes() == text.encode()
                if valid:
                    assert check.warnings  # CSV shape does not certify SMILES or science.
