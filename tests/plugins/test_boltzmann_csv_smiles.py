"""CSV shorthand molecule checks share the optional RDKit validation gate."""

import sys

import pytest

from plugins.boltzmann.file_validation import validate_file
from plugins.boltzmann.preflight import decision


RULE = {"formats": ["csv"], "columns": ["SMILES"],
        "values": {"SMILES": "smiles"}, "extra_columns": False}


@pytest.mark.parametrize("value,valid", [("CCO", True), ("C1CC", False)])
def test_csv_smiles_are_parsed_without_rewriting_or_generic_warning(tmp_path, value, valid):
    pytest.importorskip("rdkit")
    source = tmp_path / "molecules.csv"
    content = f"SMILES\n{value}\n".encode()
    source.write_bytes(content)
    report = validate_file(source, RULE, {})
    assert bool(report.errors) is not valid
    assert not report.warnings
    assert (decision(report, False) is None) is valid
    if not valid:
        assert decision(report, True)["status"] == "not_started"
    assert source.read_bytes() == content


def test_csv_smiles_without_rdkit_keep_the_explicit_approval_gate(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "rdkit", None)
    source = tmp_path / "molecules.csv"
    source.write_text("SMILES\nCCO\n", encoding="utf-8")
    report = validate_file(source, RULE, {})
    assert not report.errors
    assert any("RDKit is unavailable" in message for message in report.warnings)
    assert decision(report, False)["status"] == "approval_required"
    assert decision(report, True) is None
