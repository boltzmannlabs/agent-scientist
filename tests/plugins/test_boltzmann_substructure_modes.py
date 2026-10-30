"""Task-specific file requirements must survive connector preflight unchanged."""

from copy import deepcopy


def test_substructure_task_requires_file_but_toxic_requires_explicit_empty_string():
    from plugins.boltzmann.contracts import ContractStore

    store = ContractStore()
    base = {"library_path": "fixture/library.csv", "method": "rdkit",
            "screening_type": "in"}
    missing = object()
    for task, values in (
        ("substructure", [("fixture/patterns.csv", True), ("", False), ("  ", False),
                          (missing, False), (None, False)]),
        ("toxic", [("", True), ("fixture/patterns.csv", False), ("  ", False),
                   (missing, False), (None, False)]),
    ):
        for value, valid in values:
            payload = dict(base, task=task)
            if value is not missing:
                payload["substructures_path"] = value
            before = deepcopy(payload)
            report = store.validate_payload("Substructure_Screening", payload)
            assert (not report.errors) == valid, (task, value, report.errors)
            if valid:
                assert not report.warnings
            assert payload == before


def test_toxic_preflight_skips_empty_file_without_skipping_library_checks():
    from plugins.boltzmann.preflight import preflight_submission

    payload = {"library_path": "fixture/library.csv", "method": "rdkit",
               "screening_type": "in", "task": "toxic", "substructures_path": ""}
    before = deepcopy(payload)
    report = preflight_submission("Substructure_Screening", payload)
    assert not report.errors
    assert any("library_path" in warning for warning in report.warnings)
    assert not any("substructures_path" in warning for warning in report.warnings)
    assert payload == before
    report = preflight_submission("Substructure_Screening", dict(payload, task="substructure"))
    assert any("substructures_path" in error for error in report.errors)
