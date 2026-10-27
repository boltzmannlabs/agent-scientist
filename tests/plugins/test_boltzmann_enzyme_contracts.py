"""Supplied enzyme contracts enforce wire/file modes without claiming scientific validity."""

import copy
import gzip
import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def rfd3_submission(monkeypatch):
    from plugins.boltzmann import nodeapi_helpers, tools

    sent, checked = [], []
    real_preflight = tools.preflight_submission

    def preflight(job, payload):
        checked.append(payload)
        return real_preflight(job, payload)

    def post(url, **kwargs):
        assert url == nodeapi_helpers._SUBMIT_URL
        sent.append(kwargs["json"])
        return SimpleNamespace(status_code=200, json=lambda: {"success": True, "docId": "fixture-job"})

    monkeypatch.setattr(nodeapi_helpers.requests, "post", post)
    monkeypatch.setattr(tools, "preflight_submission", preflight)
    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    monkeypatch.setattr(tools, "current_key", lambda: "fixture-key")
    monkeypatch.setattr(tools, "time", SimpleNamespace(sleep=lambda _: None))

    def submit(payload, *, job="Enzyme_RFD3", approved=True):
        return json.loads(tools.handle_boltzmann_submit(
            job_name=job, experiment_name="fixture-confirmed-name", experiment_data=payload,
            allow_partial_validation=approved,
        ))

    return submit, sent, checked


@pytest.mark.parametrize("extras,prepared", [
    ({}, {}),
    ({"job_name": "explicit-worker-name", "n_samples": 2},
     {"job_name": "explicit-worker-name", "n_samples": 2}),
    ({"advanced_settings_enabled": False}, {"advanced_settings_enabled": "false"}),
    ({"advanced_settings_enabled": " TRUE ", "advanced_settings": None, "seed": None},
     {"advanced_settings_enabled": "true"}),
    ({"advanced_settings_enabled": True, "seed": "", "advanced_settings": {
        "partial_t": "", "contig": "  ", "ori_token": None, "select_buried": None,
        "inference_sampler": {"num_timesteps": None, "step_scale": "", "kind": " "}}},
     {"advanced_settings_enabled": "true", "advanced_settings": {"inference_sampler": {}}}),
    ({"advanced_settings_enabled": True, "seed": 0, "advanced_settings": {
        "ori_token": [0, 0, 0], "infer_ori_strategy": "hotspots", "select_hotspots": "false",
        "select_fixed_atoms": {"A108": "CA"}, "is_non_loopy": False,
        "inference_sampler": {"cfg_scale": 0, "s_trans": 0, "gamma_0": 0, "gamma_min": 0,
                              "s_jitter_origin": 0, "cfg_t_max": 0, "allow_realignment": False,
                              "use_classifier_free_guidance": "false", "n_recycle": 1}}},
     {"advanced_settings_enabled": "true", "seed": 0, "advanced_settings": {
        "ori_token": [0, 0, 0], "infer_ori_strategy": "hotspots", "select_hotspots": "false",
        "select_fixed_atoms": {"A108": "CA"}, "is_non_loopy": "false",
        "inference_sampler": {"cfg_scale": 0, "s_trans": 0, "gamma_0": 0, "gamma_min": 0,
                              "s_jitter_origin": 0, "cfg_t_max": 0, "allow_realignment": "false",
                              "use_classifier_free_guidance": "false", "n_recycle": 1}}}),
    ({"advanced_settings_enabled": " False ", "advanced_settings": {
        "partial_t": "", "inference_sampler": {"n_recycle": 0}}},
     {"advanced_settings_enabled": "false"}),
    ({"advanced_settings_enabled": True, "advanced_settings": {"inference_sampler": None}},
     {"advanced_settings_enabled": "true", "advanced_settings": {}}),
])
def test_rfd3_prepares_only_its_payload_before_real_preflight_and_wire_submission(rfd3_submission, extras, prepared):
    submit, sent, checked = rfd3_submission
    base = {"input_path": "fixture/authorized.pdb", "motif_residues": ["A108"],
            "ligand": "NAI", "min_length": 180, "max_length": 200}
    payload = dict(base, **copy.deepcopy(extras))
    original = copy.deepcopy(payload)
    expected = dict(base, job_name="fixture-confirmed-name", n_samples=1, task_name="rfd3",
                    advanced_settings_enabled="false")
    expected.update(prepared)

    # A missing receipt still requires explicit partial-validation approval.
    blocked = submit(payload, approved=False)
    assert blocked["status"] == "approval_required"
    assert not sent
    result = submit(payload)
    assert result["status"] == "accepted", result
    assert sent == [{"experimentData": expected, "job_name": "Enzyme_RFD3",
                     "experimentName": "fixture-confirmed-name"}]
    assert checked[-1] is sent[-1]["experimentData"]
    assert checked[-1] is not payload
    assert payload == original

    # The preparation branch must not affect another job's wire body.
    other = {"input_path": "fixture/authorized.pdb", "chain_id": "A"}
    result = submit(other, job="deepallo")
    assert result["status"] == "accepted", result
    assert sent[-1] == {"experimentData": other, "job_name": "deepallo",
                        "experimentName": "fixture-confirmed-name"}


@pytest.mark.parametrize("extras,valid", [
    ({"advanced_settings": {"ori_token": [0, 0, 0], "infer_ori_strategy": "com"}}, True),
    ({"advanced_settings": {"ori_token": [0, 0, 0], "infer_ori_strategy": "hotspots"}}, True),
    ({"advanced_settings": {"infer_ori_strategy": "hotspots", "select_hotspots": "A108"}}, True),
    ({"advanced_settings": {"infer_ori_strategy": "hotspots", "select_hotspots": "false"}}, False),
    ({"advanced_settings": {"ori_token": None, "infer_ori_strategy": "hotspots"}}, False),
    ({"advanced_settings": {"ori_token": [0, 0]}}, False),
    ({"n_samples": 6, "advanced_settings": {"n_batches": 2}}, False),
    ({"n_samples": 6, "advanced_settings": {"n_batches": 3}}, True),
    ({"n_samples": 5, "advanced_settings": {"n_batches": 3}}, False),
    ({"n_samples": 6, "advanced_settings": {"diffusion_batch_size": 3, "n_batches": 2}}, False),
    ({"n_samples": 6, "advanced_settings": {"diffusion_batch_size": 2, "n_batches": 3}}, True),
    ({"n_samples": 5, "advanced_settings": {"diffusion_batch_size": 2}}, False),
    ({"n_samples": 6, "advanced_settings": {"diffusion_batch_size": 2}}, True),
    ({"advanced_settings": {"inference_sampler": {"n_recycle": 0}}}, False),
    ({"advanced_settings": {"partial_t": 0}}, False),
    ({"advanced_settings": {"inference_sampler": {"noise_scale": 0}}}, False),
    ({"advanced_settings": {"inference_sampler": {"invented": None}}}, False),
    ({"advanced_settings_enabled": False, "advanced_settings": {"invented": None}}, False),
    ({"advanced_settings_enabled": False, "advanced_settings": {"inference_sampler": {"invented": ""}}}, False),
    ({"invented": None}, False),
    ({"n_samples": None}, False),
    ({"n_samples": 0}, False),
    ({"n_samples": "1"}, False),
    ({"task_name": ""}, False),
    ({"job_name": " "}, False),
    ({"advanced_settings_enabled": None}, False),
    ({"advanced_settings_enabled": "yes"}, False),
    ({"advanced_settings_enabled": 0}, False),
])
def test_rfd3_preparation_preserves_validation_rejections(rfd3_submission, extras, valid):
    submit, sent, checked = rfd3_submission
    payload = {"input_path": "fixture/authorized.pdb", "motif_residues": ["A108"],
               "ligand": "NAI", "min_length": 180, "max_length": 200,
               "advanced_settings_enabled": "true"}
    payload.update(copy.deepcopy(extras))
    original = copy.deepcopy(payload)
    result = submit(payload)
    assert payload == original
    if valid:
        assert result["status"] == "accepted", result
        assert len(sent) == 1
        assert sent[0]["experimentData"] is checked[0]
    else:
        assert result["status"] == "not_started", result
        assert result["validation"]["errors"]
        assert not sent


def test_rfd3_explicit_worker_job_name_is_distinct_from_routing_name():
    from plugins.boltzmann.contracts import ContractStore

    store = ContractStore()
    payload = copy.deepcopy(store.tool("Enzyme_RFD3")["examples"][0]["experiment_data"])
    payload["job_name"] = "fixture-rfd3-worker-run"
    original = copy.deepcopy(payload)
    report = store.validate_payload("Enzyme_RFD3", payload)
    assert not report.errors, report.errors
    assert store.tool("Enzyme_RFD3")["job_name"] == "Enzyme_RFD3"
    assert payload == original


def test_rfd3_worker_job_name_rejects_empty_and_runtime_credentials():
    from plugins.boltzmann.contracts import ContractStore

    store = ContractStore()
    base = copy.deepcopy(store.tool("Enzyme_RFD3")["examples"][0]["experiment_data"])
    for value in ("", "   ", "\t\n", None, 123, True):
        report = store.validate_payload("Enzyme_RFD3", dict(base, job_name=value))
        assert report.errors, value
    valid = dict(base, job_name="fixture-rfd3-worker-run")
    for field in ("tokenid", "user_id", "experiment_id", "invented_field"):
        assert store.validate_payload("Enzyme_RFD3", dict(valid, **{field: "offline-fixture"})).errors
    assert not store.validate_payload("Enzyme_RFD3", base).errors


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
                   dict(rfd, ligand="NAI,NAI"), dict(rfd, job_name="")]
        for change in ({"n_batches": 2}, {"ori_token": [0, 0]},
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
