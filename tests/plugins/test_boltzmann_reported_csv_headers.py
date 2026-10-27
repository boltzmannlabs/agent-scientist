"""Reported backend header requirements must be enforced before uploading bytes."""

from pathlib import Path

import pytest


@pytest.mark.parametrize("job,field,headers", [
    ("Clean", "input_path", ["Seq_id", "Sequences"]),
    ("kcatnet", "input_path", ["Sequences", "Smiles"]),
    ("Vaccines", "dataPath", ["Sequences"]),
    ("kcat_km", "input_path", ["seq_id", "Sequences", "smiles"]),
])
def test_reported_headers_gate_upload_without_rewriting(tmp_path, monkeypatch, job, field, headers):
    from plugins.boltzmann import preflight

    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    sent = []

    def upload(path):
        sent.append(Path(path).read_bytes())
        return "fixture/input.csv"

    source = tmp_path / "input.csv"
    invalid = []
    for index, header in enumerate(headers):
        changed = headers.copy()
        changed[index] = header.swapcase()
        invalid.append(changed)
        invalid.append([*headers[:index], *headers[index + 1:]])
    for columns, valid in [(h, False) for h in invalid] + [(headers, True)]:
        contents = (",".join(columns) + "\n" + ",".join("fixture" for _ in columns) + "\n").encode()
        source.write_bytes(contents)
        count = len(sent)
        result = preflight.validated_upload(str(source), job, field, {}, True, upload)
        assert source.read_bytes() == contents
        if valid:
            assert result["status"] == "uploaded", result
            assert len(sent) == count + 1 and sent[-1] == contents
        else:
            assert result["status"] == "not_started", result
            assert result["validation"]["errors"]
            assert len(sent) == count
