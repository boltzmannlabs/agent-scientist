"""Boltzyme input workflow rules, without generation or remote submission."""
import json
import copy
from types import SimpleNamespace
import zipfile

import pytest


@pytest.mark.parametrize("job,payload,valid", [
    ("Function_Based_Enzyme_Generation", {"label": "1.1.1.1", "n_samples": 1}, True),
    ("Function_Based_Enzyme_Generation", {"label": " ", "n_samples": 1}, False),
    ("Function_Based_Enzyme_Generation", {"label": "1.1.1.-", "n_samples": 0}, False),
    ("Random_Controlled_Mutagenesis", {"seq": "ACD", "indices": [0, 0], "n_samples": 1, "mutaions_per_epoch": 1, "file_format": "csv"}, True),
    ("Random_Controlled_Mutagenesis", {"seq": "ACD", "indices": [3], "n_samples": 1, "mutaions_per_epoch": 1, "file_format": "csv"}, False),
    ("Random_Controlled_Mutagenesis", {"seq": "ACD", "indices": [0, 1, 2], "n_samples": 1, "mutaions_per_epoch": 1, "file_format": "csv"}, False),
    ("Random_Controlled_Mutagenesis", {"seq": "AXD", "indices": [], "n_samples": 1, "mutaions_per_epoch": 1, "file_format": "csv"}, False),
    ("Random_Controlled_Mutagenesis", {"seq": "ACD", "indices": [], "n_samples": 1, "mutaions_per_epoch": 110, "file_format": "csv"}, False),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 2, "complex_generation": "True", "top_k": 1}, True),
    ("Genzyme_Generation", {"input_substrate": "C" * 50, "input_product": "CC=O", "num_structures": 2, "complex_generation": "false", "top_k": 1}, True),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 1}, False),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 1, "complex_generation": "false"}, False),
    ("Genzyme_Generation", {"input_substrate": "invalid SMILES", "input_product": "CC=O", "num_structures": 2}, False),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 2, "complex_generation": "true"}, False),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 2, "complex_generation": "true", "top_k": 3}, False),
    ("Genzyme_Generation", {"input_substrate": "CCO", "input_product": "CC=O", "num_structures": 2, "complex_generation": "maybe"}, False),
    ("Ligand_MPNN", {"input_path": "fixture/input.pdb", "num_sequences": 0}, False),
    ("Solublempnn", {"input_path": "fixture/input.zip", "num_seq": "1.5"}, False),
    ("Solublempnn", {"input_path": "fixture/input.zip", "num_seq": "2"}, True),
    ("act_seek", {"input_path": "fixture/input.pdb", "reference_path": "fixture/ref.pdb", "active_sites": "CA1"}, False),
    ("Motiff_Scaffolding", {"pdb_path": "fixture/input.pdb", "contigs": "10-10,A100-110,10-10", "targets": "fixture", "min_lengths": 31, "max_lengths": 31, "samples_per_target": 1}, False),
    ("Motiff_Scaffolding", {"pdb_path": "fixture/input.pdb", "contigs": "10-10,A100-110,10-10", "targets": "fixture", "min_lengths": 31, "max_lengths": 32, "samples_per_target": 1}, True),
    ("Motiff_Scaffolding", {"pdb_path": "fixture/input.pdb", "contigs": "10-10,A100-110,10-10", "targets": "fixture", "min_lengths": 0, "max_lengths": 0, "samples_per_target": 1}, True),
])
def test_scalar_contracts_enforce_worker_input_rules(job, payload, valid):
    pytest.importorskip("rdkit")
    from plugins.boltzmann.contracts import ContractStore
    report = ContractStore().validate_payload(job, payload)
    assert bool(report.errors) is not valid, report.as_dict()


def structure():
    return ("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A   1       1.000   1.000   0.000  1.00 20.00           C\n"
            "ATOM      3  C   ALA A   1       2.000   0.000   0.000  1.00 20.00           C\n"
            "HETATM    4  C1  ACT B 500       3.000   0.000   0.000  1.00 20.00           C\nEND\n")


@pytest.mark.parametrize("job,field,payload,mode,valid", [
    ("act_seek", "reference_path", {"active_sites": "1_A"}, "pdb", True),
    ("act_seek", "reference_path", {"active_sites": "999_A"}, "pdb", False),
    ("act_seek", "input_path", {}, "corrupt_zip", False),
    ("tm_align", "input_path", {}, "corrupt_zip", False),
    ("tm_align", "input_path", {}, "duplicate_zip", False),
    ("tm_align", "wt_path", {}, "pdb", True),
    ("Ligand_MPNN", "input_path", {}, "no_backbone", False),
    ("Solublempnn", "input_path", {}, "corrupt_zip", False),
    ("Thermal_MPNN", "zip_path", {"chain": "Z"}, "zip", False),
    ("Thermal_MPNN", "zip_path", {"chain": ""}, "zip", True),
    ("Placer", "input_file_path", {"predict_ligand": "B-ACT-500"}, "cif", True),
    ("Placer", "input_file_path", {"predict_ligand": "B-ACT-999"}, "cif", False),
    ("Placer", "input_file_path", {"predict_ligand": "A-ACT-500"}, "same_chain_pdb", False),
    ("Placer", "input_file_path", {"predict_ligand": "A-ACT-500"}, "same_chain_cif", True),
    ("Placer", "input_file_path", {"predict_ligand": "B-ACT-500"}, "later_chain_overlap_pdb", False),
    ("RC_Plot", "dataPath", {}, "pdb", True),
])
def test_structure_selections_are_checked_before_upload(tmp_path, job, field, payload, mode, valid):
    gemmi = pytest.importorskip("gemmi")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    text = structure()
    if mode == "later_chain_overlap_pdb":
        second = "\n".join(line[:21] + "A" + line[22:] if line.startswith("HETATM") else line for line in text.splitlines()) + "\n"
        text = "MODEL        1\n" + text.removesuffix("END\n") + "ENDMDL\nMODEL        2\n" + second.removesuffix("END\n") + "ENDMDL\nEND\n"
    if mode.startswith("same_chain"):
        text = "\n".join(line[:21] + "A" + line[22:] if line.startswith("HETATM") else line for line in text.splitlines()) + "\n"
    if mode == "no_backbone":
        text = "\n".join(line for line in text.splitlines() if " CA " not in line)
    path = tmp_path / "input.pdb"
    if mode.endswith("zip"):
        path = tmp_path / "input.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("a/input.pdb", text)
            if mode == "corrupt_zip":
                archive.writestr("bad.pdb", "This is not a structure")
            elif mode == "duplicate_zip":
                archive.writestr("b/input.pdb", text)
    elif mode in {"cif", "same_chain_cif"}:
        path = tmp_path / "input.cif"
        path.write_text(gemmi.read_pdb_string(text).make_mmcif_document().as_string(), encoding="utf-8")
    else:
        path.write_text(text, encoding="utf-8")
    original = path.read_bytes()
    report = validate_file(path, ContractStore().file_rule(job, field), payload)
    assert bool(report.errors) is not valid, report.as_dict()
    assert path.read_bytes() == original


@pytest.mark.parametrize("job,field,headers,row,valid", [
    ("Cat_Pred", "input_path", "Seq_id,Sequences,SMILES", "fixture,MKT,CCO", True),
    ("Cat_Pred", "input_path", "Seq_id,Sequence,SMILES", "fixture,MKT,CCO", False),
    ("Cat_Pred", "input_path", "Seq_id,Sequences,SMILES", "fixture,M K T,CCO", False),
    ("kcat_km", "input_path", "seq_id,Sequences,smiles", "fixture,m k t j,CCO", True),
    ("kcatnet", "input_path", "Sequences,Smiles", "M K T,CCO", True),
    ("kcatnet", "input_path", "Sequences,Smiles", "mkt,CCO", False),
    ("kcatnet", "input_path", "Sequences,Sequence,Smiles", "MKT,MKT,CCO", False),
    ("Netsolp", "input_path", "Sequences", "MKT", True),
    ("Clean", "input_path", "Seq_id,Sequences", "fixture,M K X.-", True),
    ("Enzymes", "dataPath", "Seq_id,Sequences", "fixture,MKT1", False),
])
def test_canonical_csv_rules_match_worker_views(tmp_path, job, field, headers, row, valid):
    pytest.importorskip("rdkit")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    path = tmp_path / "input.csv"
    path.write_text(headers + "\n" + row + "\n", encoding="utf-8")
    before = path.read_bytes()
    report = validate_file(path, ContractStore().file_rule(job, field), {"property_name": ["enzyme_solubility"]})
    assert bool(report.errors) is not valid, report.as_dict()
    assert before == path.read_bytes()


@pytest.mark.parametrize("job,field,contents,options", [
    ("Enzymes", "dataPath", "Seq_id,Sequences\nfixture,MKT\n", {"property_name": ["enzyme_solubility"]}),
    ("Clean", "input_path", "Seq_id,Sequences\nfixture,MKT\n", {}),
    ("kcatnet", "input_path", "Sequences,Smiles\nMKT,CCO\n", {}),
    ("kcat_km", "input_path", "seq_id,Sequences,smiles\nfixture,MKT,CCO\n", {"prediction_type": "kcat"}),
    ("kcat_km", "input_path", "seq_id,Sequences,smiles\nfixture,MKT,CCO\n", {"prediction_type": "kcat", "job_name": "explicit-run"}),
    ("Cat_Pred", "input_path", "Seq_id,Sequences,SMILES\nfixture,MKT,CCO\n", {}),
    ("Netsolp", "input_path", "Sequence_ID,Sequences\nfixture,MKT\n", {"prediction_type": "S"}),
    ("Vaccines", "dataPath", "Sequences\nMKT\n", {"property_name": ["Toxicity"]}),
    ("Insilico_Directed_Evolution", "fasta_path", ">parent\nMKT\n", {"positions": "M1", "property_name": "Solubility_ESM"}),
    ("Ligand_MPNN", "input_path", None, {"num_sequences": 1}),
])
def test_remaining_tools_use_existing_upload_submit_and_multiplex_receipts(tmp_path, monkeypatch, job, field, contents, options):
    pytest.importorskip("gemmi")
    pytest.importorskip("rdkit")
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import preflight, tools

    suffix = ".fasta" if field == "fasta_path" else ".pdb" if contents is None else ".csv"
    source = tmp_path / ("input" + suffix)
    source.write_text(structure() if contents is None else contents, encoding="utf-8")
    reference = "fixture/" + source.name
    payload = {field: reference, **options}
    original = copy.deepcopy(payload)
    monkeypatch.setattr(preflight, "current_key", lambda: "same-fixture-key")
    monkeypatch.setattr(tools, "current_key", lambda: "same-fixture-key")
    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    monkeypatch.setattr(tools, "time", SimpleNamespace(sleep=lambda _: None))
    sent = []
    def submit(data, job_name, name, **kwargs):
        sent.append((data, job_name, name))
        return "fixture-job"
    monkeypatch.setattr(tools, "submit_request", submit)
    token = set_multiplex_context(True)
    try:
        with _profile_runtime_scope(tmp_path / "a"):
            uploaded = preflight.validated_upload(source, job, field, payload, job == "Vaccines", lambda _: reference)
            assert uploaded["status"] == "uploaded", uploaded
            before = preflight.preflight_submission(job, payload).as_dict()
            with _profile_runtime_scope(tmp_path / "b"):
                foreign = preflight.preflight_submission(job, payload)
                assert any("no current-profile validation receipt" in warning for warning in foreign.warnings)
            assert preflight.preflight_submission(job, payload).as_dict() == before
            result = json.loads(tools.handle_boltzmann_submit(job_name=job,
                experiment_name="fixture", experiment_data=payload, allow_partial_validation=True))
            assert result["status"] == "accepted", result
            if field == "fasta_path":
                changed = {**payload, "positions": "K2"}
                assert preflight.preflight_submission(job, changed).errors
    finally:
        reset_multiplex_context(token)
    expected = {"job_name": "fixture", **payload} if job == "kcat_km" else payload
    assert sent == [(expected, job, "fixture")]
    assert payload == original


@pytest.mark.parametrize("inner_name", ["", None, "x" * 101])
def test_kcat_explicit_invalid_run_name_is_not_repaired(tmp_path, monkeypatch, inner_name):
    from gateway.run import _profile_runtime_scope
    from plugins.boltzmann import tools

    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    def unexpected_submit(*args, **kwargs):
        pytest.fail("Invalid worker run name must not reach transport")
    monkeypatch.setattr(tools, "submit_request", unexpected_submit)
    payload = {"input_path": "fixture/input.csv", "prediction_type": "kcat", "job_name": inner_name}
    original = copy.deepcopy(payload)
    with _profile_runtime_scope(tmp_path / "profile"):
        result = json.loads(tools.handle_boltzmann_submit(job_name="kcat_km",
            experiment_name="confirmed", experiment_data=payload, allow_partial_validation=True))
    assert result.get("error"), result
    assert payload == original


def test_generic_backbone_accepts_mse_and_repeated_chain_sections(tmp_path):
    pytest.importorskip("gemmi")
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    text = structure().removesuffix("END\n")
    # A chain section resumes after a ligand on another chain, as PDB permits.
    text += structure().split("HETATM", 1)[0].replace("A   1", "A   2") + "END\n"
    path = tmp_path / "input.pdb"
    rule = ContractStore().file_rule("Ligand_MPNN", "input_path")
    for contents in (text, structure().replace("ATOM  ", "HETATM").replace("ALA", "MSE")):
        path.write_text(contents, encoding="utf-8")
        report = validate_file(path, rule, {})
        assert not report.errors, report.as_dict()


def test_canonical_netsolp_fasta_rejects_duplicate_identifiers(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file

    rule = ContractStore().file_rule("Netsolp", "input_path")
    path = tmp_path / "input.fasta"
    for second_id, valid in (("other", True), ("same", False)):
        contents = f">same\nMKT\n>{second_id}\nACD\n".encode()
        path.write_bytes(contents)
        report = validate_file(path, rule, {})
        assert bool(report.errors) is not valid, report.as_dict()
        if not valid:
            assert any("duplicate" in error for error in report.errors)
        assert path.read_bytes() == contents


def test_public_structure_file_validation_reports_corrupt_gzip(tmp_path):
    import gzip

    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file

    valid_gzip = gzip.compress(structure().encode(), mtime=0)
    corrupt = bytearray(valid_gzip)
    corrupt[10] = 0xFF  # Reserved DEFLATE block type, not merely a bad gzip header.
    path = tmp_path / "input.pdb.gz"
    store = ContractStore()
    for job in ("Mol_Probity", "Catalytic_Geometry"):
        for contents, valid in ((valid_gzip, True), (bytes(corrupt), False)):
            path.write_bytes(contents)
            report = validate_file(path, store.file_rule(job, "input_path"), {})
            assert bool(report.errors) is not valid, report.as_dict()
            if not valid:
                assert "Invalid gzip content." in report.errors
            assert path.read_bytes() == contents
