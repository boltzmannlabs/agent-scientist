"""Omics metadata remains readable after a Windows editor adds a UTF-8 BOM."""

from pathlib import Path

import pytest


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_omics_loaders_accept_bom_without_changing_skill_content(tmp_path, monkeypatch, encoding):
    from sci_cli import omics_foundation, omics_starter

    expected = (omics_starter.definition(), omics_foundation.foundation(),
                [bundle.files for bundle in omics_foundation.bundles()])
    source = Path(omics_starter.__file__).parent / "data"
    target = tmp_path / "data"
    target.mkdir()
    for name in ("omics-starter.json", "omics-foundation.json", "omics-contracts.schema.json"):
        (target / name).write_text((source / name).read_text(encoding="utf-8-sig"), encoding=encoding)
    for module in (omics_starter, omics_foundation):
        monkeypatch.setattr(module, "__file__", str(tmp_path / Path(module.__file__).name))
    actual = (omics_starter.definition(), omics_foundation.foundation(),
              [bundle.files for bundle in omics_foundation.bundles()])
    assert actual == expected
