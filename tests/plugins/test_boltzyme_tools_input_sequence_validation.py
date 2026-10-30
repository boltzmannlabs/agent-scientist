"""Boltzyme input sequence/molecule checks preserve bytes and unrelated tools."""

import copy
import csv
import io
import sys

import pytest

from plugins.boltzmann.contracts import ValidationReport
from plugins.boltzmann.file_validation import validate_file
from plugins.boltzmann.boltzyme_tools_input_sequence_validation import validate_molecule


AA20 = "ACDEFGHIKLMNPQRSTVWY"


def _csv_file(tmp_path, headers, row):
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(headers)
    writer.writerow(row)
    path = tmp_path / "input.csv"
    path.write_text(text.getvalue(), encoding="utf-8")
    return path


@pytest.mark.parametrize("spec,value,valid", [
    ({"alphabet": AA20}, "ACDE", True),
    ({"alphabet": AA20}, "ACDX", False),
    ({"alphabet": AA20}, "ACD1", False),
    ({"alphabet": AA20}, "acde", False),
    ({"alphabet": AA20}, "ACＤE", False),
    ({"alphabet": AA20 + "BXZUO"}, "ACBXZUO", True),
    ({"alphabet": AA20 + "BXZUO"}, "ACJ", False),
    ({"alphabet": AA20 + "BXZUO", "whitespace": "remove"}, "AC D\tE\nX", True),
    ({"alphabet": AA20 + "BXZUO", "whitespace": "remove"}, "acde", False),
    ({"alphabet": AA20 + "BXZJUO", "case_sensitive": False, "whitespace": "remove"}, "ac d j", True),
    ({"alphabet": AA20 + "BXZUO.-", "whitespace": "strip_spaces"}, " AC DX.- ", True),
    ({"alphabet": AA20 + "BXZUO.-", "whitespace": "strip_spaces"}, "AC\tDX", False),
    ({"alphabet": AA20 + "BXZUO.-", "whitespace": "strip_spaces"}, "acd", False),
    ({"alphabet": AA20}, "AC DE", False),
    ({"alphabet": AA20}, "AC*DE", False),
])
def test_csv_alphabet_policy_is_explicit_and_never_rewrites_input(tmp_path, spec, value, valid):
    path = _csv_file(tmp_path, ["Seq_id", "Sequence"], ["fixture", value])
    rule = {"formats": ["csv"], "columns": ["Seq_id", "Sequences"],
            "aliases": {"Sequences": ["Sequence"]}, "values": {"Sequences": "protein"},
            "semantic_values": {"Sequences": spec}}
    before, original_rule = path.read_bytes(), copy.deepcopy(rule)
    report = validate_file(path, rule, {})
    assert bool(report.errors) is not valid
    assert not report.warnings
    assert path.read_bytes() == before
    assert rule == original_rule


@pytest.mark.parametrize("smiles,valid", [("CCO", True), ("[Na+].[Cl-]", True),
                                        ("C1CCCCC1", True), ("C1CC", False),
                                        ("not smiles", False), ("C(C)(C)(C)(C)C", False), ("", False)])
def test_opted_in_smiles_requires_a_nonempty_rdkit_molecule(tmp_path, smiles, valid):
    pytest.importorskip("rdkit")
    path = _csv_file(tmp_path, ["SMILES"], [smiles])
    rule = {"formats": ["csv"], "columns": ["SMILES"], "values": {"SMILES": "smiles"},
            "semantic_values": {"SMILES": {"smiles": True}}}
    before = path.read_bytes()
    report = validate_file(path, rule, {})
    assert bool(report.errors) is not valid
    assert not report.warnings
    assert path.read_bytes() == before


@pytest.mark.parametrize("properties,headers,row,valid", [
    (["tmPred_enzymes"], ["Sequences"], ["ACDX"], True),
    (["substrate_pred"], ["Sequences"], ["ACDX"], False),
    (["substrate_pred"], ["Sequences", "SMILES"], ["ACDX", "CCO"], True),
    (["pHPred", "substrate_pred"], ["Sequences", "Smiles"], ["ACDX", "bad"], False),
    (["tmPred_enzymes"], ["Sequences", "SMILES"], ["ACDX", "bad"], True),
])
def test_substrate_semantics_require_the_selected_column_only(tmp_path, properties, headers, row, valid):
    pytest.importorskip("rdkit")
    path = _csv_file(tmp_path, headers, row)
    rule = {"formats": ["csv"], "columns": ["Sequences"],
            "aliases": {"smiles": ["SMILES", "Smiles"]},
            "semantic_values": {"Sequences": {"alphabet": AA20 + "BXZUO"}},
            "semantic_values_by_field": {"property_name": {"substrate_pred": {"smiles": {"smiles": True}}}}}
    report = validate_file(path, rule, {"property_name": properties})
    assert bool(report.errors) is not valid
    assert not report.warnings


def test_opt_in_does_not_change_unannotated_tools_or_unknown_alphabets(tmp_path):
    path = _csv_file(tmp_path, ["Sequences"], ["arbitrary old data"])
    rule = {"formats": ["csv"], "columns": ["Sequences"], "values": {"Sequences": "protein"}}
    report = validate_file(path, rule, {})
    assert not report.errors
    assert any("protein semantics" in warning for warning in report.warnings)
    rule["semantic_values"] = {"Sequences": {"alphabet": ""}}
    report = validate_file(path, rule, {})
    assert not report.errors
    assert any("explicit audited alphabet" in warning for warning in report.warnings)


@pytest.mark.parametrize("contents,positions,valid", [
    (">parent\nACDE\n", "A1 C2", True),
    (">parent\nac\nde\n", ["A1", "E4"], True),
    (">parent\nACDE\n", "A1 A1", False),
    (">parent\nACDE\n", "A1 E9", False),
    (">parent\nACDE\n", "C1", False),
    (">parent\nACDE\n", "A0", False),
    (">parent\nACDE\n", "a1", False),
    (">parent\nACDE\n", "", False),
    (">parent\nACDE\n", [], False),
    (">parent\nACDE\n>second\nACDE\n", "A1", False),
    (">parent\nACXE\n", "A1", False),
    (">parent\nAC DE\n", "A1", False),
    (">parent\n", "A1", False),
    ("ACDE\n", "A1", False),
])
def test_single_parent_fasta_validates_positions_in_worker_view_without_rewriting(tmp_path, contents, positions, valid):
    path = tmp_path / "parent.fasta"
    path.write_text(contents, encoding="utf-8")
    rule = {"formats": ["fa", "fasta"], "sequence_validation": {
        "alphabet": AA20, "case_sensitive": False, "max_records": 1, "positions_field": "positions"}}
    before = path.read_bytes()
    report = validate_file(path, rule, {"positions": positions})
    assert bool(report.errors) is not valid
    assert not report.warnings
    assert path.read_bytes() == before
    assert not report.inventory  # No full sequence retained in receipts.


@pytest.mark.parametrize("contents,valid", [(">record\nACXBZUO.-\n", True),
                                          (">record\nACD\n>record\nACE\n", False),
                                          (">record\nACJ\n", False),
                                          (">record\nacd\n", False)])
def test_fasta_record_constraints_are_separate_from_csv_alphabets(tmp_path, contents, valid):
    path = tmp_path / "netsolp.fasta"
    path.write_text(contents, encoding="utf-8")
    rule = {"formats": ["fasta"], "sequence_validation": {"alphabet": AA20 + "XBZUO.-", "unique_ids": True}}
    report = validate_file(path, rule, {})
    assert bool(report.errors) is not valid
    assert not report.warnings


def test_missing_context_and_optional_parser_are_unchecked_not_false_validation(tmp_path, monkeypatch):
    path = tmp_path / "parent.fasta"
    path.write_text(">parent\nACD\n", encoding="utf-8")
    report = validate_file(path, {"sequence_validation": {"alphabet": AA20, "positions_field": "positions"}}, {})
    assert not report.errors
    assert any("request context" in warning for warning in report.warnings)
    monkeypatch.setitem(sys.modules, "rdkit", None)
    report = ValidationReport()
    validate_molecule("CCO", "smiles", report, 128)
    assert not report.errors
    assert any("RDKit is unavailable" in warning and "128" in warning for warning in report.warnings)


def test_shared_molecule_checker_applies_only_explicit_hydrogen_inclusive_limits():
    pytest.importorskip("rdkit")
    value = "C" * 50
    unconstrained, constrained = ValidationReport(), ValidationReport()
    validate_molecule(value, "ligand", unconstrained)
    validate_molecule(value, "smiles", constrained, 128)
    assert not unconstrained.errors and not unconstrained.warnings
    assert any("128 atoms including hydrogens" in error for error in constrained.errors)


@pytest.mark.parametrize("singular", ["Sequence", "sequence", "SEQUENCE", "Smile", "sMiLe", " Sequence "])
@pytest.mark.parametrize("opted_in", [True, False])
def test_forbidden_headers_reject_singular_plural_mixtures_only_when_opted_in(tmp_path, singular, opted_in):
    headers = ["Seq_id", "Sequences", "SMILES", singular]
    path = _csv_file(tmp_path, headers, ["fixture", "ACDE", "CCO", "unused"])
    rule = {"formats": ["csv"], "columns": ["Seq_id", "Sequences", "SMILES"],
            "extra_columns": True, "header_case_sensitive": True}
    if opted_in:
        rule["forbidden_columns"] = ["sequence", "smile"]
    before = path.read_bytes()
    report = validate_file(path, rule, {})
    assert bool(report.errors) is opted_in
    if opted_in:
        assert any("forbidden" in error for error in report.errors)
    assert path.read_bytes() == before
