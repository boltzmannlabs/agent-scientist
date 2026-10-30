"""The retrosynthesis environment installs from an immutable source revision."""

import argparse
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.pm._fixtures import (
    _wheel,
    build_worker as build_worker,
    client as client,
    isolated_python as isolated_python,
)


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, check=True,
                          capture_output=True, text=True,
                          env={k: v for k, v in os.environ.items()
                               if not k.startswith("GIT_")}).stdout.strip()


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


def test_clone_uses_only_exact_revision(tmp_path, monkeypatch):
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
    monkeypatch.setenv("GIT_DIR", str(source / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(source))
    fetch_pinned_source(str(source), first, checkout)
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_WORK_TREE")
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
    monkeypatch.setenv("OPENAI_API_KEY", "named-profile-secret")
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
            assert "OPENAI_API_KEY" not in kwargs["env"]
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


def test_discovery_uses_default_profile_without_inherited_provider_key(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    monkeypatch.setenv("OPENAI_API_KEY", "named-profile-secret")
    seen = {}
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: seen.update(kwargs) or "")
    installer._check_discovery(tmp_path)
    assert seen["env"]["SCI_HOME"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in seen["env"]
    assert "PYTHONPATH" in seen["env"]


def test_discovery_child_imports_checkout_from_unrelated_directory(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    def run(command, **kwargs):
        result = subprocess.run(
            [command[0], "-c", "import sci_cli.plugins"],
            cwd=tmp_path, env=kwargs["env"], capture_output=True,
            text=True, encoding="utf-8", check=False,
        )
        assert result.returncode == 0, result.stderr
        return ""

    monkeypatch.setattr(installer, "_run", run)
    installer._check_discovery(tmp_path)


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


@pytest.mark.platforms("posix")
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


def test_chemistry_install_uses_pm_interpreter_without_sci_pythonpath(tmp_path, monkeypatch):
    import pm
    from sci_cli import environments_install as installer

    calls = []
    python = tmp_path / "pm-selected-interpreter"
    package, runtime = tmp_path / "package", tmp_path / "runtime"
    monkeypatch.setenv("PYTHONPATH", "/foreign/sci/site-packages")

    def build(**kwargs):
        assert kwargs["source"] == package and kwargs["out"] == runtime
        assert kwargs["extras"] == ["search"] and kwargs["explicit"] is True
        assert kwargs["frozen"] is False
        assert "PYTHONPATH" not in kwargs["env"]
        runtime.mkdir()
        return python

    monkeypatch.setattr(pm, "build_environment", build)
    monkeypatch.setattr(installer, "_run", lambda command, **kwargs: calls.append((command, kwargs)) or "")
    assert installer._ensure_chemistry_runtime(package, runtime) == python
    assert calls[0][0][:3] == [str(python), "-I", "-c"]
    assert all("PYTHONPATH" not in call[1]["env"] for call in calls)
    assert all(call[1]["env"]["PYTHONNOUSERSITE"] == "1" for call in calls)


@pytest.mark.platforms("windows")
def test_native_windows_model_assets_fail_before_download(tmp_path, monkeypatch):
    from sci_cli import environments_install as installer

    monkeypatch.setattr(installer, "get_default_sci_root", lambda: tmp_path)
    monkeypatch.setattr(installer, "fetch_pinned_source", lambda *args: pytest.fail("download started"))
    with pytest.raises(ValueError, match="POSIX environment"):
        installer.install_retrosynthesis(model_location=str(tmp_path / "assets"))
    assert not (tmp_path / "environments").exists()


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
    import_check_index = next(i for i, command in enumerate(calls) if command[1:3] == ["-I", "-c"])
    assert enable_index < import_check_index


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
        if command[1:3] == ["-I", "-c"]:
            raise subprocess.CalledProcessError(1, command, stderr="pydantic missing")
        return ""

    monkeypatch.setattr(installer, "_run", run)
    with pytest.raises(RuntimeError, match="pydantic missing"):
        installer.install_retrosynthesis()
    assert ["sci", "-p", "default", "plugins", "disable", "retrosynthesis"] in calls
    assert not (tmp_path / "plugins/retrosynthesis").exists()


def test_chemistry_runtime_builds_real_isolated_pm_environment(tmp_path, monkeypatch, build_worker):
    """Exercise the PM worker with offline fixture wheels, not a science install."""
    from sci_cli import environments_install as installer

    package = tmp_path / "fixture package"
    wheels = package / "wheels"
    wheels.mkdir(parents=True)
    _wheel(wheels, "base_dep")
    _wheel(wheels, "search_dep")
    (package / "pyproject.toml").write_text(
        '[project]\nname="retrosynthesis-fixture"\nversion="1"\nrequires-python=">=3.11"\n'
        'dependencies=["base-dep==1.0"]\n'
        '[project.optional-dependencies]\nsearch=["search-dep==1.0"]\n'
        '[tool.uv]\npackage=false\nno-index=true\nfind-links=["wheels"]\n',
        encoding="utf-8",
    )
    verified = []

    def verify(python):
        result = subprocess.run(
            [str(python), "-I", "-c", "import base_dep, search_dep; print(search_dep.__version__)"],
            check=True, capture_output=True, text=True, encoding="utf-8",
            env=installer._chemistry_env(), timeout=30,
        )
        assert result.stdout.strip() == "1.0"
        verified.append(python)

    monkeypatch.setattr(installer, "_verify_chemistry_runtime", verify)
    runtime = tmp_path / "isolated runtime"
    python = installer._ensure_chemistry_runtime(package, runtime)
    assert verified == [python]
    assert python.is_file() and (runtime / "pyvenv.cfg").is_file()
    assert (package / "uv.lock").is_file()
