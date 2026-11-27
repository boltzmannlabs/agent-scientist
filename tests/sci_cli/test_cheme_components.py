"""Optional engineering components honor profile scope and preserve upstream overrides."""
import argparse
import json
import os
from pathlib import Path
import sys


def test_idaes_and_viewer_scope_a_b_a(tmp_path, monkeypatch):
    import pm
    from sci_cli import cheme_components as components
    from sci_constants import get_sci_home, reset_sci_home_override, set_sci_home_override

    homes = [tmp_path / "a", tmp_path / "b"]
    children = {}
    for index, home in enumerate(homes):
        root = home / "environments/cheme-idaes" / ("gen-" + str(index) * 32) / "venv"
        binary = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"identity only")
        children[home] = binary
    monkeypatch.setattr(pm, "environment_python", lambda name: children[Path(get_sci_home())])
    original = {"PATH": os.environ.get("PATH", ""), "MARKER": "preserved"}
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            result = components.idaes_environment(original)
            assert result["CHEME_IDAES_PYTHON"] == str(children[home])
            assert Path(result["IDAES_DATA"]).is_relative_to(home)
            assert components.viewer_path().is_relative_to(home)
            assert result["MARKER"] == "preserved"
            # An explicit external worker must not be replaced by a local runtime.
            external = {**original, "CHEME_IDAES_COMMAND": "remote-worker"}
            assert components.idaes_environment(external) == external
        finally:
            reset_sci_home_override(token)
    assert "CHEME_IDAES_PYTHON" not in original


def test_viewer_launch_uses_prepared_assets_and_real_child(tmp_path, monkeypatch):
    from sci_cli import cheme, cheme_components
    from sci_cli.subcommands.cheme import build_cheme_parser

    parser = argparse.ArgumentParser()
    build_cheme_parser(parser.add_subparsers())
    project = tmp_path / "plant with spaces"
    project.mkdir()
    ui = tmp_path / "viewer"
    monkeypatch.setattr(cheme_components, "viewer_path", lambda: ui)
    args = parser.parse_args(["cheme", "--project", str(project), "--viewer", "--port", "18765"])
    # Missing UI is refused before runtime installation or server launch.
    monkeypatch.setattr(cheme, "_runtime", lambda **kw: (_ for _ in ()).throw(AssertionError("installed")))
    assert cheme.run_command(args) == 2
    ui.mkdir()
    (ui / "index.html").write_text("viewer")
    monkeypatch.setattr(cheme, "_runtime", lambda **kw: (Path(sys.executable), dict(os.environ)))
    monkeypatch.setattr(cheme, "ENTRYPOINT", "import sys,json,pathlib; pathlib.Path('args.json').write_text(json.dumps(sys.argv[1:]))")
    assert cheme.run_command(args) == 0
    assert json.loads((project / "args.json").read_text()) == [
        "serve", "--repo", str(project), "--ui", str(ui), "--port", "18765"]
