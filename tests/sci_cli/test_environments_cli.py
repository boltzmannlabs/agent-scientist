"""The retrosynthesis environment installs from an immutable source revision."""

import argparse
import json
import subprocess
from pathlib import Path

import pytest


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_parser_exposes_install_and_run_without_model_override():
    from sci_cli.subcommands.environments import build_environments_parser

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    build_environments_parser(subparsers)
    args = parser.parse_args(["environments", "install", "retrosynthesis"])
    assert args.environment == "retrosynthesis"
    assert args.model_location is None
    args = parser.parse_args(["environments", "run", "retrosynthesis",
        "--target", "CCO", "--inventory", "stock.json", "--constraints", "limits.json"])
    assert args.target == "CCO"
    assert args.inventory == "stock.json"
    assert not hasattr(args, "model")


def test_clone_uses_only_exact_revision(tmp_path):
    from sci_cli.environments_install import fetch_pinned_source

    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.name", "Fixture")
    _git(source, "config", "user.email", "fixture@example.org")
    (source / "marker").write_text("first")
    _git(source, "add", "marker")
    _git(source, "commit", "-qm", "first")
    first = _git(source, "rev-parse", "HEAD")
    (source / "marker").write_text("second")
    _git(source, "commit", "-qam", "second")
    checkout = tmp_path / "checkout"
    fetch_pinned_source(str(source), first, checkout)
    assert (checkout / "marker").read_text() == "first"
    assert _git(checkout, "rev-parse", "HEAD") == first


def test_bad_revision_fails_without_destination(tmp_path):
    from sci_cli.environments_install import fetch_pinned_source

    with pytest.raises(ValueError, match="revision"):
        fetch_pinned_source(str(tmp_path), "main", tmp_path / "checkout")
    assert not (tmp_path / "checkout").exists()


def _stub_release(destination: Path) -> Path:
    package = destination / "environments/retrosynthesis"
    plugin = package / "integrations/agent_scientist"
    skill = package / "skills/retrosynthesis"
    plugin.mkdir(parents=True)
    skill.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: retrosynthesis\n")
    (skill / "SKILL.md").write_text("# Retrosynthesis\n")
    return destination


def test_default_install_writes_base_runtime_and_discovers(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source",
                        lambda repo, revision, destination: _stub_release(destination))
    monkeypatch.setattr(installer, "_ensure_chemistry_runtime",
                        lambda package, runtime: runtime / "bin/python")
    monkeypatch.setattr(installer, "_sci_executable", lambda: "sci")

    def run(command, **kwargs):
        calls.append(command)
        if "plugins" in command:
            assert kwargs["env"]["SCI_DISABLE_LAZY_INSTALLS"] == "1"
        return ""

    monkeypatch.setattr(installer, "_run", run)
    monkeypatch.setattr(installer, "_check_discovery", lambda home: calls.append(["discover", str(home)]))

    assert installer.install_retrosynthesis() == 0
    runtime = json.loads((tmp_path / "plugins/retrosynthesis/runtime.json").read_text())
    assert set(runtime) == {"SRG_PACKAGE_ROOT", "SRG_CHEMISTRY_PYTHON",
                            "SRG_BACKEND_TIMEOUT_SECONDS"}
    assert ["sci", "-p", "default", "plugins", "enable", "retrosynthesis",
            "--no-allow-tool-override"] in calls
    assert ["discover", str(tmp_path)] in calls


def test_discovery_failure_disables_and_cleans_new_files(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source",
                        lambda repo, revision, destination: _stub_release(destination))
    monkeypatch.setattr(installer, "_ensure_chemistry_runtime",
                        lambda package, runtime: runtime / "bin/python")
    monkeypatch.setattr(installer, "_sci_executable", lambda: "sci")
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: calls.append(command) or "")
    monkeypatch.setattr(installer, "_check_discovery",
                        lambda home: (_ for _ in ()).throw(RuntimeError("discovery failed")))
    with pytest.raises(RuntimeError, match="discovery failed"):
        installer.install_retrosynthesis()
    assert ["sci", "-p", "default", "plugins", "disable", "retrosynthesis"] in calls
    assert not (tmp_path / "plugins/retrosynthesis").exists()
    assert not (tmp_path / "environments/retrosynthesis/source").exists()


def test_legacy_plugin_is_rejected_before_fetch(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    (tmp_path / "config.yaml").write_text("plugins:\n  enabled:\n    - synthesis-route-gym\n")
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    with pytest.raises(ValueError, match="legacy synthesis-route-gym"):
        installer.install_retrosynthesis()
    assert not (tmp_path / "environments").exists()


def test_model_option_delegates_to_pinned_local_asset_setup(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source",
                        lambda repo, revision, destination: _stub_release(destination))
    monkeypatch.setattr(installer, "_ensure_chemistry_runtime",
                        lambda package, runtime: runtime / "bin/python")
    monkeypatch.setattr(installer, "_sci_executable", lambda: "sci")
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: calls.append(command) or "")
    monkeypatch.setattr(installer, "_check_discovery", lambda home: None)

    assert installer.install_retrosynthesis(model_location="/assets/REBOLT-FEATURES",
                                            model_python="/models/bin/python") == 0
    setup = next(command for command in calls if "setup_retrosynthesis.py" in " ".join(command))
    assert "--existing-rebolt-root" in setup
    assert "/assets/REBOLT-FEATURES" in setup
    assert "--existing-rebolt-python" in setup
    assert not (tmp_path / "plugins/retrosynthesis/runtime.json").exists()


def test_model_python_requires_model_location():
    from sci_cli.environments_install import install_retrosynthesis

    with pytest.raises(ValueError, match="requires --model-location"):
        install_retrosynthesis(model_python="/models/bin/python")


def test_discovery_check_fails_when_python_optimized(tmp_path, monkeypatch):
    from sci_cli.environments_install import _check_discovery

    monkeypatch.setenv("PYTHONOPTIMIZE", "1")
    with pytest.raises(subprocess.CalledProcessError):
        _check_discovery(tmp_path)


def test_install_home_resolves_named_profile_to_default_root(tmp_path, monkeypatch):
    from sci_constants import get_default_sci_root

    root = tmp_path / "sci-root"
    named = root / "profiles/sirna"
    named.mkdir(parents=True)
    monkeypatch.setenv("SCI_HOME", str(named))
    assert get_default_sci_root() == root
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "isolated-root"))
    assert get_default_sci_root() == tmp_path / "isolated-root"


def test_chemistry_install_does_not_inherit_sci_pythonpath(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setenv("PYTHONPATH", "/foreign/sci/site-packages")
    monkeypatch.setattr(installer.venv.EnvBuilder, "create", lambda self, path: None)
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: calls.append(kwargs) or "")
    installer._ensure_chemistry_runtime(tmp_path / "package", tmp_path / "runtime")
    assert all("PYTHONPATH" not in call["env"] for call in calls)
    assert all(call["env"]["PYTHONNOUSERSITE"] == "1" for call in calls)


def test_final_chemistry_verification_runs_after_enable(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source",
                        lambda repo, revision, destination: _stub_release(destination))
    monkeypatch.setattr(installer, "_ensure_chemistry_runtime",
                        lambda package, runtime: runtime / "bin/python")
    monkeypatch.setattr(installer, "_sci_executable", lambda: "sci")
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: calls.append(command) or "")
    monkeypatch.setattr(installer, "_check_discovery", lambda home: calls.append(["discover"]))
    installer.install_retrosynthesis()
    enable_index = next(i for i, command in enumerate(calls) if "enable" in command)
    pip_check_index = next(i for i, command in enumerate(calls) if command[-2:] == ["pip", "check"])
    assert enable_index < pip_check_index


def test_final_dependency_failure_rolls_back_install(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    calls = []
    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source",
                        lambda repo, revision, destination: _stub_release(destination))
    monkeypatch.setattr(installer, "_ensure_chemistry_runtime",
                        lambda package, runtime: runtime / "bin/python")
    monkeypatch.setattr(installer, "_sci_executable", lambda: "sci")
    monkeypatch.setattr(installer, "_check_discovery", lambda home: None)

    def run(command, **kwargs):
        calls.append(command)
        if command[-2:] == ["pip", "check"]:
            raise subprocess.CalledProcessError(1, command, stderr="pydantic missing")
        return ""

    monkeypatch.setattr(installer, "_run", run)
    with pytest.raises(RuntimeError, match="pydantic missing"):
        installer.install_retrosynthesis()
    assert ["sci", "-p", "default", "plugins", "disable", "retrosynthesis"] in calls
    assert not (tmp_path / "plugins/retrosynthesis").exists()
