"""Real pinned engine: propagation, analytical balance, diagrams and invalid data.

Run with -m integration -o cheme_python=<prepared interpreter>. Never installs
dependencies or uses a real profile. Default CI skips this native integration file.
"""
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def engine(request, tmp_path, monkeypatch):
    import pm
    from sci_cli.cheme import run_command
    from sci_cli.subcommands.cheme import build_cheme_parser
    import argparse

    python = request.config.getini("cheme_python")
    if not python:
        pytest.skip("Prepared engineering interpreter has not been supplied")
    assert Path(python).is_file()
    monkeypatch.setattr(pm, "ensure_project_environment", lambda *a, **k: Path(python))
    parser = argparse.ArgumentParser()
    build_cheme_parser(parser.add_subparsers())

    def run(project, *values):
        return run_command(parser.parse_args(["cheme", "--project", str(project), "--", *values]))

    return run


def test_real_engine_initializes_project_and_exposes_schema(tmp_path, capfd, engine):
    project = tmp_path / "new plant"
    assert engine(tmp_path, "init", str(project), "--name", "Engineering study") == 0
    capfd.readouterr()
    assert (project / "plant.yaml").is_file()
    assert (project / "process/flowsheet.yaml").is_file()
    assert engine(project, "schema", "process-flowsheet") == 0
    schema = json.loads(capfd.readouterr().out)
    assert "streams" in schema["properties"]


def test_real_engine_mixer_conservation_diagrams_and_invalid_input(tmp_path, capfd, engine):
    project = tmp_path / "plant with spaces"
    template = ROOT / "skills/science/process-engineering/cheme-as-code/templates/mixer"
    shutil.copytree(template, project)
    assert engine(project, "process", "propagate", "--fill", "--json") == 0
    propagation = json.loads(capfd.readouterr().out)
    assert propagation["results"][0]["status"] == "converged"
    assert engine(project, "process", "streams", "--json") == 0
    streams = json.loads(capfd.readouterr().out)
    assert streams["balances"] and all(b["status"] == "ok" for b in streams["balances"])
    output = next(s for s in streams["streams"] if s["id"] == "S3")["state"]
    assert output["flow"]["value"] == pytest.approx(100 + 300)
    assert output["flow"]["provenance"] == "calculated"
    composition = output["composition"]
    assert composition["provenance"] == "calculated"
    fractions = composition["values"]
    # Independent conversion of the saved mole fractions back to a mass fraction.
    mw = {"ETOH": 46.069, "H2O": 18.015}
    w_ethanol = fractions["ETOH"] * mw["ETOH"] / sum(fractions[k] * mw[k] for k in mw)
    assert w_ethanol == pytest.approx(100 / 400, abs=0.001 / 400)
    assert engine(project, "process", "build") == 0
    capfd.readouterr()
    assert engine(project, "render", "process/BFD.xml", "process/PFD.xml") == 0
    capfd.readouterr()
    assert engine(project, "render", "process/BFD.xml", "process/PFD.xml", "--png") == 0
    capfd.readouterr()
    for name in ("BFD", "PFD"):
        assert ET.parse(project / "process" / f"{name}.xml").getroot() is not None
        assert ET.parse(project / "build" / f"{name}.svg").getroot().tag.endswith("svg")
        assert (project / "build" / f"{name}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert engine(project, "validate", "--json") == 0
    validation = json.loads(capfd.readouterr().out)
    assert not [f for f in validation["findings"] if f["level"] == "error"]
    # Exercise the actual package rasterizer and check that chat export focuses
    # the process while preserving the original engineering source.
    from sci_cli.cheme import _runtime
    from sci_cli.cheme_diagrams import export_diagrams
    from PIL import Image

    source_bytes = (project / "process/PFD.xml").read_bytes()
    python, environment = _runtime(check_only=False, explicit=False)
    exported = export_diagrams(project, python, environment)
    assert project / "build/PFD-chat.png" in exported
    assert project / "build/PFD-streams.png" in exported
    assert (project / "process/PFD.xml").read_bytes() == source_bytes
    focused = ET.parse(project / "build/PFD-chat.svg").getroot()
    full = ET.parse(project / "build/PFD.svg").getroot()
    assert float(focused.get("height")) < float(full.get("height"))
    with Image.open(project / "build/PFD-chat.png") as preview:
        assert preview.width > 2000 and preview.height > 100
    # Invalid composition must be diagnosed and must stop drawing generation.
    flow = project / "process/flowsheet.yaml"
    text = flow.read_text()
    # Change only the synthetic feed input through its actual schema representation.
    import sci_yaml as yaml
    data = yaml.safe_load(text)
    data["streams"][0]["state"]["design"]["composition"]["values"]["ETOH"] = 1.5
    flow.write_text(yaml.safe_dump(data, sort_keys=False))
    assert engine(project, "validate", "--json") != 0
    invalid = json.loads(capfd.readouterr().out)
    assert any(f["level"] == "error" for f in invalid["findings"])
    assert engine(project, "process", "build") != 0
