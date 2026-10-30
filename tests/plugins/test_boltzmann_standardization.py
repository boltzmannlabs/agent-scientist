"""All-catalog contract invariants; fixtures are synthetic, never scientific jobs."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "plugins/boltzmann/skills/boltzmann-tools/references"
CATALOG = json.loads((ROOT / "tool-contracts.v1.json").read_text(encoding="utf-8-sig"))


def shape_fixture(schema):
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type", "string")
    if isinstance(kind, list):
        kind = kind[0]
    if kind == "object":
        fixture = {name: shape_fixture(prop) for name, prop in schema.get("properties", {}).items()}
        alternatives = schema.get("oneOf", [])
        if alternatives:
            selected = set(schema.get("required", [])) | set(alternatives[0].get("required", []))
            mode_fields = {name for branch in alternatives for name in branch.get("required", [])}
            for name in mode_fields - selected:
                fixture.pop(name, None)
        return fixture
    if kind == "array":
        return [shape_fixture(schema["items"])] if schema.get("items") else []
    if kind in {"integer", "number"}:
        return schema.get("minimum", 1)
    if kind == "boolean":
        return False
    return "1" if schema.get("x-numeric-string") else "fixture"


def test_solublempnn_requires_numeric_string_count_in_distributed_contract(tmp_path):
    """The reported backend accepts a string count, not a JSON number."""
    import shutil

    from plugins.boltzmann.contracts import ContractStore

    installed = tmp_path / "installed-references"
    installed.mkdir()
    for filename in ("tool-contracts.v1.json", "file-input-contracts.v1.json", "input-limits.v1.json"):
        shutil.copy2(ROOT / filename, installed / filename)
    for root in (ROOT, installed):
        store = ContractStore(root)
        for count in ("1", "20"):
            payload = {"input_path": "fixture/already-uploaded.zip", "num_seq": count}
            assert not store.validate_payload("Solublempnn", payload).errors
            assert payload["num_seq"] == count  # Validation never coerces the wire value.
        for count in (20, 20.0, True, None, "", "twenty", "NaN", "Infinity"):
            report = store.validate_payload("Solublempnn", {
                "input_path": "fixture/already-uploaded.zip", "num_seq": count})
            assert any("num_seq" in error for error in report.errors), count


def test_binding_affinity_modes_and_paired_csv_contract(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file
    from sci_cli.science_catalog_view import catalog_rows

    store = ContractStore(ROOT)
    job = "global_binding_affinity"
    for payload in ({"smiles": "fixture-smiles", "sequence": "fixture-sequence"},
                    {"input_csv": "fixture/pairs.csv"}):
        assert not store.validate_payload(job, payload).errors
    for payload in ({}, {"smiles": "fixture-smiles"}, {"sequence": "fixture-sequence"},
                    {"input_csv": ""}, {"smiles": "fixture-smiles", "sequence": ""}):
        assert store.validate_payload(job, payload).errors
    assert set(store.file_fields(job)) == {"input_csv"}
    source = tmp_path / "pairs.csv"
    rule = store.file_rule(job, "input_csv")
    for contents, valid in (("SMILES,SEQUENCE\nfixture-smiles,fixture-sequence\n", True),
                            ("SMILES,SEQUENCES\nfixture-smiles,fixture-sequence\n", False),
                            ("SMILES,SEQUENCE\nfixture-smiles,\n", False)):
        source.write_text(contents, encoding="utf-8")
        report = validate_file(source, rule, {})
        assert bool(report.errors) is not valid
        if valid:
            assert report.warnings  # Shape checks are not scientific validation.
    rows = catalog_rows(ROOT / "tool-contracts.v1.json", query="Binding Affinity Energy")
    assert any(row["name"] == store.tool(job)["display_name"]
               and row["domain"] == "Small Molecule Design" for row in rows)


@pytest.mark.parametrize("job", sorted(CATALOG["tools"]))
def test_every_job_has_one_input_definition_and_accepts_its_documented_shape(job):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.preflight import _contract_digest

    store = ContractStore(ROOT)
    tool = store.tool(job)
    schema = tool["request_schema"]
    props = schema["properties"]
    assert "file_fields" not in tool
    assert set(schema.get("required", [])) <= set(props)
    examples = [example["experiment_data"] for example in tool.get("examples", [])
                if isinstance(example, dict) and "experiment_data" in example]
    fixture = json.loads(json.dumps(examples[0])) if examples else shape_fixture(schema)
    # Generic shape strings are not sequences, molecules or residue selections.
    # Concrete software fixtures exercise the newly implemented semantic checks.
    fixture.update({
        "Genzyme_Generation": {"input_substrate": "CCO", "input_product": "CC=O", "complex_generation": "false"},
        "Random_Controlled_Mutagenesis": {"seq": "ACD", "indices": [], "mutaions_per_epoch": 1},
        "act_seek": {"active_sites": "1_A"},
        "Placer": {"suffix": "B-ACT-500", "predict_ligand": "B-ACT-500"},
        "Motiff_Scaffolding": {"min_lengths": 1, "max_lengths": 2},
    }.get(job, {}))
    for field in store.file_fields(job):
        rule = store.files.get(job, {}).get("files", {}).get(field, {})
        if rule.get("execution_blocked") and field not in schema.get("required", []) and not examples:
            fixture.pop(field, None)
            continue
        formats = rule.get("formats", [])
        if (formats and (rule.get("structure_profile") or rule.get("semantic_values") or rule.get("sequence_validation"))
                and isinstance(fixture.get(field), str)
                and not any(fixture[field].lower().endswith("." + suffix) for suffix in formats)):
            fixture[field] = "fixture/input." + formats[0]
    for name, bound in store.limits.get(job, {}).get("fields", {}).items():
        assert name in props
        assert "required" not in bound and "type" not in bound
        if examples:
            continue  # Reviewed multi-field examples preserve their documented relationships.
        if "minimum" in bound:
            fixture[name] = bound["minimum"]
        elif "exclusive_minimum" in bound:
            fixture[name] = bound["exclusive_minimum"] + 1
        elif "maximum" in bound:
            fixture[name] = min(1, bound["maximum"])
        if props[name].get("x-numeric-string"):
            fixture[name] = str(fixture[name])
    for group in store.limits.get(job, {}).get("any_of_nonempty", []):
        assert set(group) <= set(props)
        if not any(fixture.get(name) for name in group):
            fixture[group[0]] = ["fixture"]
    for left, right in schema.get("x-equal-fields", []):
        fixture[right] = fixture[left]
    report = store.validate_payload(job, fixture)
    assert not report.errors, (job, report.errors)
    for name in schema.get("required", []):
        missing = dict(fixture)
        del missing[name]
        assert store.validate_payload(job, missing).errors, (job, name, "missing required field accepted")
    for name, prop in props.items():
        # The same schema must reject incompatible wire types, not merely accept
        # the generated happy path. No scientific values are inferred here.
        bad = [] if prop.get("type") == "boolean" else True
        assert store.validate_payload(job, dict(fixture, **{name: bad})).errors, (job, name)
        if prop.get("x-numeric-string"):
            assert "string" in prop["type"]
    for condition in schema.get("x-required-if", []):
        assert set(condition["when"]) | set(condition["required"]) <= set(props)
        selected = dict(fixture, **condition["when"])
        for name in condition["required"]:
            missing = dict(selected)
            missing.pop(name, None)
            assert any(name in error for error in store.validate_payload(job, missing).errors)
    for name, prop in store.file_fields(job).items():
        alternatives = prop.get("oneOf", prop.get("anyOf", [prop]))
        assert any("string" in (p.get("type") if isinstance(p.get("type"), list)
                                else [p.get("type")]) for p in alternatives)
        if prop["x-input-kind"] != "artifact":
            assert isinstance(store.file_rule(job, name), dict)
    for field in store.files.get(job, {}).get("files", {}):
        assert field in store.file_fields(job)
    # Documentation edits must not invalidate uploaded-byte validation receipts.
    before = _contract_digest(store, job)
    tool["description"] = "Changed documentation only"
    for prop in props.values():
        prop["description"] = "Changed documentation only"
    assert _contract_digest(store, job) == before


def test_file_modes_nested_models_and_known_invalid_values(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from plugins.boltzmann.file_validation import validate_file

    store = ContractStore(ROOT)
    assert store.file_rule("rna_siRNA_gen", "input_fasta")["formats"]
    assert not store.file_fields("Multimer_Structure_Prediction")
    with pytest.raises(ValueError):
        store.file_rule("Multimer_Structure_Prediction", "input_path")
    assert store.file_rule("Geometry_Optimization", "molecule_path")
    job = "Lead_Generation_Graph_GA"
    payload = {"smiles": "fixture", "n_mols": 1, "n_steps": 1,
               "global_models": [{"name": "Solubility", "min_threshold": "", "max_threshold": ""}]}
    assert not store.validate_payload(job, payload).errors
    payload["global_models"] = ["Solubility"]
    assert store.validate_payload(job, payload).errors
    fasta = tmp_path / "fixture.fasta"
    fasta.write_text(">fixture\nACGU\n", encoding="utf-8")
    assert not validate_file(fasta, {"formats": ["fasta"]}, {}).errors
    fasta.write_text("ACGU\n", encoding="utf-8")
    assert validate_file(fasta, {"formats": ["fasta"]}, {}).errors
    pdb = tmp_path / "fixture.pdb"
    pdb.write_text("ATOM      1  O   HOH A   1       0.000   0.000   0.000  1.00  0.00           O\nEND\n", encoding="utf-8")
    assert not validate_file(pdb, {"formats": ["pdb"]}, {}).errors
    pdb.write_text("not a coordinate file\n", encoding="utf-8")
    assert validate_file(pdb, {"formats": ["pdb"]}, {}).errors
