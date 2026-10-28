"""Contract coverage and preflight behavior; no scientific service is contacted."""


def test_diagnostic_collection_resolution_requires_exact_documented_mapping():
    import csv

    import pytest

    from plugins.boltzmann.contracts import ContractStore

    store = ContractStore()
    assert store.diagnostic_collection("Random_Antibody_Generation") == "AB_GEN"
    evidence = store.root.parents[2] / "contract_sources/diagnostic-collections.csv"
    with evidence.open() as source:
        for row in csv.DictReader(source):
            assert store.diagnostic_collection(row["job_name"]) == row["collection_name"]
    store.tools["fixture"] = {"diagnostics": [
        {"job_name": "another-job", "collection_name": "wrong", "mapping_status": "source_documented"},
        {"job_name": "fixture", "collection_name": "candidate", "mapping_status": "source_only"},
    ]}
    with pytest.raises(ValueError, match="No documented"):
        store.diagnostic_collection("fixture")
    with pytest.raises(ValueError, match="Unknown"):
        store.diagnostic_collection("invented-job")
    store.tools["fixture"]["diagnostics"] += [
        {"job_name": "fixture", "collection_name": name, "mapping_status": "source_documented"}
        for name in ("one", "two")
    ]
    with pytest.raises(ValueError, match="Ambiguous"):
        store.diagnostic_collection("fixture")


def test_every_catalog_tool_has_explicit_contract_coverage():
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.contract_docs import generated_modules

    store = ContractStore()
    assert store.tools
    assert set(store.files) <= set(store.tools)
    assert set(store.limits) <= set(store.tools)
    for path, content in generated_modules(store.root).items():
        assert path.read_text() == content
    for name, contract in store.tools.items():
        assert contract["job_name"] == name
        assert contract["request_schema"]["type"] == "object"
        assert "file_fields" not in contract
        for field in store.files.get(name, {}).get("files", {}):
            assert field in store.file_fields(name)
        for prop in contract["request_schema"]["properties"].values():
            assert prop["x-input-kind"] in {"file", "value", "file_or_value", "artifact"}
        assert (store.root / contract["source"]).is_file() or contract["status"] != "active"
        if contract.get("product_documentation"):
            document, anchor = contract["product_documentation"].split("#", 1)
            guide = store.root / document
            assert guide.is_file()
            headings = {line[3:].strip().lower().replace(" ", "-") for line in guide.read_text().splitlines()
                        if line.startswith("## ")}
            assert anchor in headings


def test_product_documentation_is_rendered_without_modifying_execution_schema():
    import copy

    from plugins.boltzmann.contract_docs import render_module

    module = {"id": "example", "title": "Example"}
    tool = {"job_name": "fixture", "display_name": "Fixture", "module_id": "example",
            "description": "Fixture product copy.",
            "request_schema": {"type": "object", "properties": {}, "required": []}}
    catalog = {"tools": {"fixture": tool}}
    files = limits = {"tools": {}}
    without_guide = render_module(module, catalog, files, limits)
    tool["product_documentation"] = "guide.md#example"
    before = copy.deepcopy(catalog)
    with_guide = render_module(module, catalog, files, limits)
    assert catalog == before
    link = "[Product description and result interpretation](../guide.md#example)\n\n"
    assert link in with_guide
    assert with_guide.replace(link, "") == without_guide


def test_known_invalid_is_blocked_but_missing_detailed_file_rules_are_partial(tmp_path):
    import zipfile

    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from plugins.boltzmann.preflight import decision

    store = ContractStore()
    # A harmless molecular geometry fixture. No backend or chemistry software runs.
    water = tmp_path / "water.xyz"
    water.write_text("3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n")
    report = validate_file(water, {"formats": ["xyz"], "coverage": "partial"}, {})
    assert not report.errors
    assert report.warnings  # Not a claim of scientific correctness.
    payload = {"task_name": "water", "molecule_path": "fixture/upload.xyz",
               "method": "B3LYP", "basis": "def2-TZVP", "charge": 0,
               "spin_multiplicity": "1", "dispersion": "D3BJ"}
    assert not store.validate_payload("Single_Point_Energy", payload).errors
    del payload["task_name"]
    assert any("task_name" in error for error in store.validate_payload("Single_Point_Energy", payload).errors)
    csv = tmp_path / "input.csv"
    rule = {"formats": ["csv"], "columns": ["id", "value"], "extra_columns": False,
            "values": {"value": "number"}, "header_case_sensitive": True}
    csv.write_text("id,wrong\nx,1\n")
    assert validate_file(csv, rule, {}).errors
    csv.write_text("id,value\nx,NaN\n")
    assert validate_file(csv, rule, {}).errors
    csv.write_text("id,value\nx,1\n")
    assert not validate_file(csv, rule, {}).errors
    csv.write_text("ID,value\nx,1\n")
    assert validate_file(csv, rule, {}).errors
    assert not validate_file(csv, dict(rule, header_case_sensitive=False), {}).errors
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "fixture")
    unsafe = validate_file(archive, {"formats": ["zip"], "coverage": "partial"}, {})
    assert unsafe.errors and decision(unsafe, True)["status"] == "not_started"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("fixture.txt", "harmless")
    partial = validate_file(archive, {"formats": ["zip"], "coverage": "partial"}, {})
    assert not partial.errors and partial.warnings
    assert decision(partial, False)["approval_required"]
    assert decision(partial, True) is None
    blocked = validate_file(water, {"formats": ["xyz"], "execution_blocked": True}, {})
    assert decision(blocked, True)["status"] == "not_started"


def test_enzyme_csv_requires_frontend_headers_without_rewriting_inputs(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from plugins.boltzmann.preflight import decision

    store = ContractStore()
    rule = store.file_rule("Enzymes", "dataPath")
    source = tmp_path / "enzymes.csv"
    payload = {"property_name": ["enzyme_solubility"]}
    fixtures = [
        (b"Seq_id,Sequences\nenzyme-1,MKT\n", True),
        (b"\xef\xbb\xbfSeq_id,Sequences\r\nenzyme-1,MKT\r\n", True),
        (b"Seq_id,Sequences,smiles\nenzyme-1,MKT,CC\n", True),
        (b"Sequence_ID,Sequences\nenzyme-1,MKT\n", False),
        (b"seq_id,Sequences\nenzyme-1,MKT\n", False),
        (b"Seq_id,Sequence\nenzyme-1,MKT\n", False),
        (b"Seq_id,Sequences\nenzyme-1,\n", False),
        (b"Seq_id,Sequences\n,MKT\n", False),
        (b"Seq_id,Sequences\n", False),
        (b"Seq_id,Sequences,Sequences\nenzyme-1,MKT,MKT\n", False),
    ]
    for content, valid in fixtures:
        source.write_bytes(content)
        report = validate_file(source, rule, payload)
        assert bool(report.errors) is not valid, (content, report.as_dict())
        assert source.read_bytes() == content
        if valid:
            assert not report.warnings
        else:
            assert decision(report, True)["status"] == "not_started"


def test_historical_worker_failure_warns_without_prohibiting_reviewed_submission():
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.preflight import decision

    store = ContractStore()
    payload = {"target_name": "fixture", "processed_pdb": "fixture/receptor.pdb",
               "center_x": "0", "center_y": "0", "center_z": "0",
               "max_radius_size": "1", "exhaustivness": "8", "upload_sdf": "False",
               "smiles": "fixture/ligands.csv"}
    # Pure preflight only: no upload, network access or scientific execution.
    report = store.validate_payload("Vina_basic_docking", payload)
    assert not report.errors
    assert report.warnings
    assert decision(report, False)["approval_required"]
    assert decision(report, True) is None
    del payload["processed_pdb"]
    assert decision(store.validate_payload("Vina_basic_docking", payload), True)["status"] == "not_started"


def test_current_small_molecule_ui_wire_contracts_reject_stale_payloads():
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.nodeapi_helpers import _tool_timeout

    store = ContractStore()
    current = {
        "Custom_Property_Model_DL": {
            "property_name": "fixture", "filepath": "fixture/train.csv", "modeltype": "regression",
            "modelName": "DL", "model_category": "DL",
        },
        "Custom_Property_Model_Automl": {
            "property_name": "fixture", "filepath": "fixture/train.csv", "modeltype": "regression",
            "features": "fingerprints", "splittype": "scaffoldsplit",
            "modelName": ["automl"], "model_category": "ML",
        },
        "Butina_Clustering": {
            "Path": "fixture/library.csv", "model": "Butina", "DimReduce": "tSNE",
            "sampling_type": "Min-Max", "cutoff": 0.4, "sampling": "yes",
        },
        "K_Means_Clustering": {
            "Path": "fixture/library.csv", "Features": "descriptors", "DimReduce": "tSNE",
            "no_of_cluster": "4",
        },
        "Binding_Site_Prediction": {"pdb_path": "8AZY"},
        "dataset_creation": {"scrap_id": "EGFR", "data_type": "IC50", "assay_type": "Cell free"},
        "Lead_Generation_Reinvent": {
            "n_mols": 10, "n_steps": 1, "finetune": "False", "dataType": "Global",
            "global_models": [{"name": "CaCo2 permeability", "min_threshold": "11", "max_threshold": ""}],
            "custom_models": [{"id": "fixture-model", "min_threshold": "", "max_threshold": "22"}],
        },
        "Vina_Score_only_docking": {
            "target_name": "fixture", "processed_pdb": "fixture/receptor.pdb",
            "center_x": "-1.5", "center_y": "2", "center_z": "3.25",
            "max_radius_size": "20", "exhaustivness": "16", "upload_sdf": "True",
            "sdf_file": "fixture/ligand.sdf",
        },
    }
    for job, payload in current.items():
        assert not store.validate_payload(job, payload).errors, job

    stale = [
        ("Custom_Property_Model_DL", dict(current["Custom_Property_Model_DL"], transformation="no")),
        ("Custom_Property_Model_Automl", dict(current["Custom_Property_Model_Automl"], modelName=["AutoML"])),
        ("Custom_Property_Model_Automl", dict(current["Custom_Property_Model_Automl"], transformation="no")),
        ("Butina_Clustering", dict(current["Butina_Clustering"], DimReduce="TSNE", sampling_type="Min_max")),
        ("Butina_Clustering", dict(current["Butina_Clustering"], sampling_type="Min_Max")),
        ("K_Means_Clustering", {
            "Path": "fixture/library.csv", "Features": "descriptors", "DimReduce": "tSNE",
            "no_of_clusters": "4",
        }),
        ("K_Means_Clustering", dict(current["K_Means_Clustering"], no_of_cluster=4)),
        *[("Lead_Generation_Reinvent", dict(current["Lead_Generation_Reinvent"], **{field: "fixture"}))
          for field in ("name", "reward", "tar_seq", "off_tar_seqs")],
        *[("Vina_Score_only_docking", dict(current["Vina_Score_only_docking"], **{field: "fixture"}))
          for field in ("pdb_file", "smiles")],
    ]
    for job, payload in stale:
        assert store.validate_payload(job, payload).errors, job

    assert store.file_fields("Binding_Site_Prediction")["pdb_path"]["x-input-kind"] == "file_or_value"
    assert set(store.file_fields("Vina_Score_only_docking")) == {"processed_pdb", "sdf_file"}
    assert _tool_timeout("K_Means_Clustering", {"num_smiles": 1_000, "no_of_cluster": "auto"}) \
        > _tool_timeout("K_Means_Clustering", {"num_smiles": 1_000, "no_of_cluster": "4"})


def test_unreconciled_entries_are_visible_without_granting_execution():
    from plugins.boltzmann.contracts import ContractStore
    from sci_cli.science_catalog_view import catalog_rows

    store = ContractStore()
    pending = store.catalog["unavailable_entries"]
    rows = catalog_rows(store.root / "tool-contracts.v1.json")
    for entry in pending:
        assert any(row["name"] == entry["display_name"] and row["status"] != "active" for row in rows)
        assert entry["availability_reason"]
        if entry.get("job_name"):
            assert store.validate_payload(entry["job_name"], {}).errors
