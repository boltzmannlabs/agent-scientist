"""Drawing command contracts: real child processes, read-only probes and profile scope."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def arguments(*values):
    from sci_cli.subcommands.reaction_draw import build_reaction_draw_parser

    parser = argparse.ArgumentParser()
    build_reaction_draw_parser(parser.add_subparsers())
    return parser.parse_args(["reaction-draw", *map(str, values)])


def test_command_is_available_through_real_cli_parser():
    from sci_cli.main import _build_cli_parser

    parser, _ = _build_cli_parser()
    selected = parser.parse_args(["reaction-draw", "--check-env"])
    assert selected.check_env
    assert callable(selected.func)


def test_readiness_probe_never_installs(tmp_path, monkeypatch, capsys):
    import pm
    from sci_cli import reaction_draw

    monkeypatch.setattr(pm, "environment_python", lambda name: None)
    monkeypatch.setattr(pm, "ensure_project_environment", lambda *a, **k: pytest.fail("read-only probe installed dependencies"))
    monkeypatch.setattr(pm, "ensure", lambda *a, **k: pytest.fail("read-only probe installed a browser"))
    assert reaction_draw.run_command(arguments("--check-env")) == 2
    assert "--setup" in capsys.readouterr().err


@pytest.mark.parametrize("extra", [("--dpi", "nan"), ("--dpi", "0"), ("--png-width", "-1")])
def test_invalid_resolution_is_rejected_before_dependencies(tmp_path, monkeypatch, extra):
    from sci_cli import reaction_draw

    spec = tmp_path / "input.json"
    spec.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reaction_draw, "_runtime", lambda **k: pytest.fail("invalid request prepared dependencies"))
    assert reaction_draw.run_command(arguments(spec, "--out", tmp_path / "results", *extra)) == 2
    assert not (tmp_path / "results").exists()


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_renderer_arguments_and_exit_status_survive_real_child(tmp_path, monkeypatch, exit_code):
    from sci_cli import reaction_draw

    bundle = tmp_path / "bundle"
    script = bundle / "upstream" / "scripts" / "draw_figure.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "args=sys.argv[1:]\nout=Path(args[args.index('--out')+1])\n"
        "out.mkdir(parents=True,exist_ok=True)\n"
        "(out/'received.json').write_text(json.dumps(args),encoding='utf-8')\n"
        f"raise SystemExit({exit_code})\n", encoding="utf-8")
    spec = tmp_path / "input ; literal ü.json"
    spec.write_text("{}", encoding="utf-8")
    output = tmp_path / "output folder ü"
    monkeypatch.setattr(reaction_draw, "bundle_root", lambda: bundle)
    monkeypatch.setattr(reaction_draw, "_runtime", lambda **k: (Path(sys.executable), dict(os.environ)))
    assert reaction_draw.run_command(arguments(spec, "--out", output, "--dpi", "300", "--quiet")) == exit_code
    received = json.loads((output / "received.json").read_text(encoding="utf-8-sig"))
    assert received == [str(spec.resolve()), "--out", str(output.resolve()), "--dpi", "300.0", "--quiet"]


def test_isolated_runtime_does_not_mutate_browser_environment(tmp_path, monkeypatch):
    import pm
    from sci_cli import reaction_draw

    python = tmp_path / "renderer" / "bin" / "python"
    original = {"PATH": "browser-path", "PYTHONPATH": "application-path", "PYTHONHOME": "application-home", "VIRTUAL_ENV": "application-venv"}
    monkeypatch.setattr(pm, "ensure_project_environment", lambda *a, **k: python)
    monkeypatch.setattr(pm, "ensure", lambda *a, **k: type("Browser", (), {"env": original})())
    selected, environment = reaction_draw._runtime(check_only=False, explicit=True)
    assert selected == python
    assert environment["VIRTUAL_ENV"] == str(python.parent.parent)
    assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
    assert environment["PATH"].startswith(str(python.parent) + os.pathsep)
    assert original["PYTHONPATH"] == "application-path"
    assert original["VIRTUAL_ENV"] == "application-venv"


def test_runtime_selection_returns_to_owning_profile(tmp_path, monkeypatch):
    import pm
    from sci_cli import reaction_draw
    from sci_constants import reset_sci_home_override, set_sci_home_override

    homes = [tmp_path / "a", tmp_path / "b"]
    interpreters = {}
    for number, home in enumerate(homes):
        generation = "gen-" + str(number + 1) * 32
        root = home / "environments" / reaction_draw.ENVIRONMENT
        python = root / generation / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"interpreter identity only; not executed")
        (python.parent.parent / "pyvenv.cfg").write_text("home = test\n", encoding="utf-8")
        (root / "active.json").write_text(json.dumps({"generation": generation}), encoding="utf-8")
        interpreters[home] = python
    monkeypatch.setattr(pm, "is_installed", lambda name: True)
    monkeypatch.setattr(pm, "env_for", lambda name: {"PATH": "browser"})
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            selected, _ = reaction_draw._runtime(check_only=True, explicit=False)
            assert selected == interpreters[home]
        finally:
            reset_sci_home_override(token)


@pytest.mark.platforms("linux", "macos", "windows")
def test_output_lock_excludes_other_native_process_and_releases(tmp_path):
    from sci_cli.reaction_draw import bundle_root

    module_path = bundle_root() / "upstream" / "scripts" / "output_lock.py"
    spec = importlib.util.spec_from_file_location("reaction_output_lock", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock_path = tmp_path / "drawing.lock"
    probe = (
        "import importlib.util,sys\nfrom pathlib import Path\n"
        "s=importlib.util.spec_from_file_location('drawing_lock',sys.argv[1])\n"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
        "with Path(sys.argv[2]).open('a+b') as handle:\n"
        " try:m.acquire(handle)\n"
        " except OSError:raise SystemExit(73)\n"
    )
    with lock_path.open("a+b") as handle:
        module.acquire(handle)
        held = subprocess.run([sys.executable, "-c", probe, str(module_path), str(lock_path)], timeout=15)
        assert held.returncode == 73
    released = subprocess.run([sys.executable, "-c", probe, str(module_path), str(lock_path)], timeout=15)
    assert released.returncode == 0
