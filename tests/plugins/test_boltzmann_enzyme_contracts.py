"""Supplied enzyme contracts enforce wire/file modes without claiming scientific validity."""

import copy
import gzip
import json


def test_enzyme_payload_and_file_relationships_survive_distributed_contracts(tmp_path):
    import shutil

    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from sci_cli.science_catalog_view import catalog_rows

    source = ContractStore()
    installed = tmp_path / "references"
    shutil.copytree(source.root, installed)
    jobs = ("deepallo", "enzycontrol", "Enzyme_RFD3", "Catalytic_Geometry", "Mol_Probity")
    for store in (source, ContractStore(installed)):
        for job in jobs:
            tool = store.tool(job)
            payload = copy.deepcopy(tool["examples"][0]["experiment_data"])
            assert not store.validate_payload(job, payload).errors
            rows = catalog_rows(store.root / "tool-contracts.v1.json", query=tool["display_name"])
            assert any(row["name"] == tool["display_name"] and row["domain"] == "Protein Engineering" for row in rows)
            assert store.diagnostic_collection(job)
        deep = source.tools["deepallo"]["examples"][0]["experiment_data"]
        assert store.validate_payload("deepallo", dict(deep, chain_id="AB")).errors
        enzy = copy.deepcopy(store.tool("enzycontrol")["examples"][0]["experiment_data"])
        del enzy["seed"]
        assert store.validate_payload("enzycontrol", enzy).errors
        rfd = copy.deepcopy(store.tool("Enzyme_RFD3")["examples"][0]["experiment_data"])
        invalid = [dict(rfd, advanced_settings_enabled=True), dict(rfd, advanced_settings_enabled="True"),
                   dict(rfd, min_length=rfd["max_length"]+1), dict(rfd, motif_residues=["A108", "A108"]),
                   dict(rfd, ligand="NAI,NAI"), dict(rfd, job_name="Enzyme_RFD3")]
        for change in ({"ori_token": [0, 0, 0], "infer_ori_strategy": "com"},
                       {"n_batches": 2}, {"ori_token": [0, 0]},
                       {"inference_sampler": {"n_recycle": 0}},
                       {"geometry_constraints": [{"type": "distance", "atoms": [{"residue": "A108", "atom": "CA"}], "min": 1, "max": 2}]}):
            altered = copy.deepcopy(rfd)
            altered["advanced_settings"].update(change)
            invalid.append(altered)
        for payload in invalid:
            assert store.validate_payload("Enzyme_RFD3", payload).errors
        mol = {"input_path": "fixture/input.pdb"}
        for thresholds in ({}, {"max_clashscore": -1}, {"max_rotamer_outlier_percent": 101},
                           {"max_cbeta_outliers": 0.5}, {"invented_threshold": 1}):
            assert store.validate_payload("Mol_Probity", dict(mol, execution_mode="validation", quality_thresholds=thresholds)).errors
        assert store.validate_payload("Mol_Probity", dict(mol, quality_thresholds={"max_clashscore": 0})).errors
        assert store.validate_payload("Mol_Probity", dict(mol, execution_mode="validation")).errors
        assert not store.validate_payload("Mol_Probity", dict(mol, execution_mode="validation", quality_thresholds={"max_clashscore": 0})).errors
        assert not store.validate_payload("Mol_Probity", dict(mol, execution_mode="validation", quality_thresholds="fixture/gates.json")).errors
        rule = store.file_rule("Mol_Probity", "quality_thresholds")
        path = tmp_path / "gates.json"
        for text, valid in (('{"max_clashscore": 10}', True), ('{}', False),
                            ('{"max_clashscore": 0,"max_clashscore": 10}', False),
                            ('{"max_clashscore": NaN}', False), ('not json', False)):
            path.write_text(text)
            assert bool(validate_file(path, rule, {}).errors) is not valid
        binding = store.file_rule("Catalytic_Geometry", "template_binding")
        path.write_text('{"mapping_keys":{"fixture":{"chain_id":"A","residue_number":1}}}')
        assert not validate_file(path, binding, {}).errors
        path.write_text('{"mapping_keys":{}}')
        assert validate_file(path, binding, {}).errors
        path.write_text(' ' * (binding["max_bytes"] + 1))
        assert validate_file(path, binding, {}).errors
        csv = tmp_path / "mapping.csv"
        csv.write_text("candidate_id,mapping_key,chain_id,residue_number\nx,m,A,1\n")
        assert validate_file(csv, store.file_rule("Catalytic_Geometry", "mapping_path"), {}).errors
        gz = tmp_path / "structure.pdb.gz"
        gz.write_bytes(gzip.compress(b"ATOM      1  O   HOH A   1       0.000   0.000   0.000  1.00  0.00           O\nEND\n"))
        assert not validate_file(gz, store.file_rule("Mol_Probity", "input_path"), {}).errors
        # Valid template shapes cannot silently accept inverted bounds or duplicate IDs.
        atom = {"entity_type": "residue", "chain_id": "A", "residue_number": 1, "atom_name": "CA"}
        check = {"check_id": "fixture", "type": "distance", "rationale": "test shape only",
                 "sources": ["fixture"], "evidence_level": "user_defined", "atoms": [atom, dict(atom, residue_number=2)], "min": 1, "max": 2}
        template = {"reaction_state": "fixture", "sources": ["fixture"], "checks": [check]}
        rule = store.file_rule("Catalytic_Geometry", "reaction_template")
        path.write_text(json.dumps(template))
        assert not validate_file(path, rule, {}).errors
        check["min"] = 3
        path.write_text(json.dumps(template))
        assert validate_file(path, rule, {}).errors
        check["min"] = 1
        template["checks"].append(copy.deepcopy(check))
        path.write_text(json.dumps(template))
        assert validate_file(path, rule, {}).errors
