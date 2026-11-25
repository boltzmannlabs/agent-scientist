"""Native rendering against the upstream Apache-2.0 fixture set.

Prepare the managed drawing runtime and Chromium first. The two explicit
reaction_draw_* pytest options select already-prepared dependencies; these tests
never install anything or use a real profile. Ordinary CI excludes integration
tests unless the native browser environment is prepared for them.
Fixtures: t-0hmura/reaction-draw dd0a01d773c4f94910f0e1f8def67dca01b5da6a.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "third_party" / "reaction_draw" / "upstream"
SKILL = ROOT / "skills" / "science" / "chemistry" / "reaction-draw"
CASES = sorted((BUNDLE / "templates").glob("*.json")) + sorted(
    (Path(__file__).resolve().parent.parent / "reaction_draw_cases").glob("*.json"))
CASES += sorted(path for path in (SKILL / "templates").glob("*.json")
                if not (BUNDLE / "templates" / path.name).is_file())


@pytest.fixture
def render(tmp_path, request):
    python = request.config.getini("reaction_draw_python")
    browser = request.config.getini("reaction_draw_browser")
    if not python or not browser:
        pytest.skip("native drawing runtime/browser paths have not been supplied")
    assert Path(python).is_file() and Path(browser).is_file()
    environment = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(key, None)
    environment.update(AGENT_BROWSER_EXECUTABLE_PATH=browser, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8", SCI_HOME=str(tmp_path / "home"))

    def run(source, output):
        return subprocess.run(
            [python, str(BUNDLE / "scripts" / "draw_figure.py"), str(source), "--out", str(output), "--quiet"],
            env=environment, cwd=tmp_path, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180)
    return run


def assert_checked_outputs(output):
    checked = json.loads((output / "checks.json").read_text(encoding="utf-8-sig"))
    assert checked["result"]["ok"], checked["result"]["failed"]
    control = checked["positive_control"]
    assert control["ok"]
    assert control["detected"] == control["planted"]
    assert control["detectors_covered"] == control["detectors"]
    assert (output / "figure.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert ET.parse(output / "figure.svg").getroot().tag.endswith("svg")
    assert ET.parse(output / "figure.cdxml").getroot().tag == "CDXML"
    report = json.loads((output / "report.json").read_text(encoding="utf-8-sig"))
    assert report["atoms"] and report["bonds"]
    assert report["reload"]


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.parent.name + "-" + p.stem)
def test_upstream_cases_pass_native_checks_and_roundtrip(case, tmp_path, render):
    output = tmp_path / "drawing"
    response = render(case, output)
    assert response.returncode == 0, response.stdout + response.stderr
    assert "RESULT: all checks pass" in response.stdout
    assert_checked_outputs(output)


def test_edit_and_invalid_stereochemistry_preserve_last_passing_figure(tmp_path, render):
    source = tmp_path / "input.json"
    data = json.loads((SKILL / "templates" / "proton_transfer.json").read_text(encoding="utf-8-sig"))
    source.write_text(json.dumps(data), encoding="utf-8-sig")
    output = tmp_path / "edited"
    first = render(source, output)
    assert first.returncode == 0, first.stdout + first.stderr
    assert_checked_outputs(output)
    data["panels"][0]["title"] = "Reviewed reactant"
    source.write_text(json.dumps(data), encoding="utf-8")
    edited = render(source, output)
    assert edited.returncode == 0, edited.stdout + edited.stderr
    assert_checked_outputs(output)
    assert "Reviewed reactant" in (output / "figure.svg").read_text(encoding="utf-8-sig")
    hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
              for name in ("figure.png", "figure.svg", "figure.cdxml")}
    data["expected_stereo"] = {"unknown:999": "R"}
    source.write_text(json.dumps(data), encoding="utf-8")
    invalid = render(source, output)
    assert invalid.returncode == 2
    assert "input error" in invalid.stdout
    assert not (output / "figure.png").exists()
    for name, digest in hashes.items():
        assert hashlib.sha256((output / "last_pass" / name).read_bytes()).hexdigest() == digest
