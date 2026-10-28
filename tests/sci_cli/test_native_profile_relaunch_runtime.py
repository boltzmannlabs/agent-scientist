"""Profile/chat handoffs retain the installation when PATH names another SCI."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("managed", [False, True])
def test_relaunch_bootstraps_dependencies_and_target_profile_from_neutral_cwd(tmp_path, monkeypatch, managed):
    from sci_cli import native_profile_session
    from sci_cli.config import atomic_config_replace

    root = Path(native_profile_session.__file__).resolve().parents[1]
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setenv("SCI_DISABLE_LAZY_INSTALLS", "1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(root / "sci_cli/main.py")])
    unrelated = tmp_path / "other-install"
    unrelated.mkdir()
    launcher = unrelated / "sci"
    launcher.write_text("#!/bin/sh\nexit 93\n")
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(unrelated) + os.pathsep + os.environ.get("PATH", ""))

    if managed:
        from pm.environments import install_state_dir, site_packages
        store = home / "tools"
        store.mkdir()
        interpreter = Path(sys._base_executable).resolve()
        (store / "facts.json").write_text(json.dumps({"packages": {
            "python": {"entry": str(interpreter.parents[1])}}}))
        monkeypatch.setenv("SCI_RUNTIME_DIR", str(store))
        state = install_state_dir(root)
        state.mkdir(parents=True)
        selected = state / "environments" / "fixture" / "venv"
        site = site_packages(selected)
        site.mkdir(parents=True)
        (selected / "pyvenv.cfg").write_text("home = fixture\n")
        (site / "fixture-dependencies.pth").write_text(str(site_packages(Path(sys.prefix))) + "\n")
        (state / "facts.json").write_text(json.dumps({"packages": {
            "venv": {"environment": str(selected)}}}))

    launches = []

    def exec_child(executable, argv, env):
        # Execute the actual generated bootstrap from the target workspace.
        # main imports sci_yaml/ruamel even for --help; no model request is made.
        result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        launches.append((argv, env, Path.cwd()))

    monkeypatch.setattr(os, "execvpe", exec_child)
    for name in ("a", "b", "a"):
        target = home / "profiles" / name
        (target / "workspace").mkdir(parents=True, exist_ok=True)
        atomic_config_replace(target / "config.yaml", {"terminal": {"backend": "local"}})
        args = ["--cli", "-p", name, "--help"]
        native_profile_session.relaunch_profile(SimpleNamespace(
            _pending_relaunch=args, _pending_profile_home=str(target)))
        argv, env, cwd = launches[-1]
        assert argv[-len(args):] == args
        assert env["SCI_HOME"] == str(target)
        assert cwd == target / "workspace"
        assert str(launcher) not in argv
