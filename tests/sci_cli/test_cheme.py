"""Managed command contracts, real child execution and profile scope."""
import argparse
import json
import os
from pathlib import Path
import sys

import pytest


def arguments(*values):
    from sci_cli.subcommands.cheme import build_cheme_parser

    parser = argparse.ArgumentParser()
    build_cheme_parser(parser.add_subparsers())
    return parser.parse_args(["cheme", *map(str, values)])


def test_real_cli_parser_routes_engineering_arguments():
    from sci_cli.main import _build_cli_parser

    parser, _ = _build_cli_parser()
    args = parser.parse_args(["cheme", "--project", "my plant", "--", "validate", "--json"])
    assert args.project == Path("my plant")
    assert args.cheme_args == ["--", "validate", "--json"]
    assert callable(args.func)


def test_probe_never_installs(tmp_path, monkeypatch, capsys):
    import pm
    from sci_cli import cheme

    monkeypatch.setattr(pm, "environment_python", lambda name: None)
    monkeypatch.setattr(pm, "ensure_project_environment", lambda *a, **k: pytest.fail("probe installed"))
    assert cheme.run_command(arguments("--check-env")) == 2
    assert "--setup" in capsys.readouterr().err


@pytest.mark.parametrize("values", [("--setup", "--", "init"), ("--check-env", "--project", "."),
                                    ("--project", "missing project", "--", "validate")])
def test_invalid_request_does_not_prepare_runtime(tmp_path, monkeypatch, values):
    from sci_cli import cheme

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cheme, "_runtime", lambda **k: pytest.fail("invalid request installed"))
    assert cheme.run_command(arguments(*values)) == 2


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_real_child_preserves_arguments_cwd_and_exit(tmp_path, monkeypatch, exit_code):
    from sci_cli import cheme

    project = tmp_path / "plant ; literal ü"
    project.mkdir()
    capture = "import sys,json,pathlib; pathlib.Path('received.json').write_text(json.dumps(sys.argv[1:]));"
    monkeypatch.setattr(cheme, "ENTRYPOINT", capture + f"raise SystemExit({exit_code})")
    monkeypatch.setattr(cheme, "_runtime", lambda **k: (Path(sys.executable), dict(os.environ)))
    assert cheme.run_command(arguments("--project", project, "--", "validate", "--json")) == exit_code
    assert json.loads((project / "received.json").read_text()) == ["validate", "--json"]


def test_runtime_and_child_environment_follow_profile_a_b_a(tmp_path, monkeypatch):
    import pm
    from sci_cli import cheme
    from sci_constants import reset_sci_home_override, set_sci_home_override

    homes = [tmp_path / "a", tmp_path / "b"]
    interpreters = {}
    for number, home in enumerate(homes):
        generation = "gen-" + str(number + 1) * 32
        root = home / "environments" / cheme.ENVIRONMENT
        python = root / generation / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"identity only")
        (python.parent.parent / "pyvenv.cfg").write_text("home = test\n")
        (root / "active.json").write_text(json.dumps({"generation": generation}))
        interpreters[home] = python
    monkeypatch.setenv("PYTHONPATH", "application-path")
    monkeypatch.setenv("PYTHONHOME", "application-home")
    monkeypatch.setattr(pm, "ensure_project_environment", lambda *a, **k: pytest.fail("read-only installed"))
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            python, environment = cheme._runtime(check_only=True, explicit=False)
            assert python == interpreters[home]
            assert environment["SCI_HOME"] == str(home)
            assert environment["VIRTUAL_ENV"] == str(python.parent.parent)
            assert environment["PATH"].startswith(str(python.parent) + os.pathsep)
            assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
            assert os.environ["PYTHONPATH"] == "application-path"
        finally:
            reset_sci_home_override(token)
