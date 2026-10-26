"""Ligand hypotheses are distinct from receptor hypotheses; no service calls."""

import shutil


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
        # The sources disagree on donor visibility, but recorded submissions
        # document it. Keep that supported choice subject to explicit review.
        assert not store.validate_payload(job, dict(payload, features=["hb donor"])).errors
        for field in store.file_fields(job):
            csv = tmp_path / (field + ".csv")
            for text, valid in (("SMILES\nCCO\n", True), ("smiles\nCCO\n", False),
                                ("unrelated\nCCO\n", False), ("SMILES\n\"\"\n", False),
                                ("SMILES\n", False)):
                csv.write_text(text)
                check = validate_file(csv, store.file_rule(job, field), payload)
                assert bool(check.errors) is not valid
                assert csv.read_text() == text
                if valid:
                    assert check.warnings  # CSV shape does not certify SMILES or science.
