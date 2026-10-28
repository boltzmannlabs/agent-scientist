"""Install the pinned retrosynthesis environment into the default Sci profile."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import venv

from sci_constants import get_default_sci_root


RETROSYNTHESIS_REPO = "https://github.com/boltzmannlabs/science-environments.git"
RETROSYNTHESIS_COMMIT = "912d79c7f832b744f83b02d45fa977fbb2797308"
_SHA = re.compile(r"[0-9a-f]{40}\Z")


def _run(command: list[str], *, timeout: int = 1800, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True,
                            timeout=timeout, env=env)
    return result.stdout.strip()


def _chemistry_env() -> dict[str, str]:
    """Keep Sci's dependency overlay out of the chemistry interpreter."""
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME"}}
    return {**env, "PYTHONNOUSERSITE": "1"}


def _verify_chemistry_runtime(python: Path) -> None:
    env = _chemistry_env()
    try:
        _run([str(python), "-c",
              "import rdkit,pydantic,numpy,sklearn,httpx,yaml,synthesis_route_gym,syntheseus"],
             timeout=120, env=env)
        _run([str(python), "-m", "pip", "check"], timeout=120, env=env)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "dependency import/check failed").strip()
        raise RuntimeError(f"Retrosynthesis chemistry runtime is incomplete: {detail}") from exc


def fetch_pinned_source(repo_url: str, revision: str, destination: Path) -> Path:
    """Fetch one immutable Git object and reject moving refs or wrong checkout heads."""
    if not _SHA.fullmatch(revision):
        raise ValueError("A full 40-character Git revision is required")
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Environment source already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".retrosynthesis-source-", dir=destination.parent))
    try:
        _run(["git", "-C", str(stage), "init", "-q"], timeout=30)
        _run(["git", "-C", str(stage), "fetch", "--no-tags", "--depth=1", repo_url, revision],
             timeout=600)
        _run(["git", "-C", str(stage), "checkout", "--detach", "-q", "FETCH_HEAD"], timeout=60)
        actual = _run(["git", "-C", str(stage), "rev-parse", "HEAD"], timeout=30)
        if actual != revision:
            raise ValueError(f"Fetched environment revision mismatch: {actual}")
        if destination.exists():
            raise ValueError(f"Environment source appeared during install: {destination}")
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def _ensure_chemistry_runtime(package: Path, runtime: Path) -> Path:
    if runtime.exists() or runtime.is_symlink():
        raise ValueError(f"Chemistry runtime already exists: {runtime}")
    runtime.parent.mkdir(parents=True, exist_ok=True)
    try:
        venv.EnvBuilder(with_pip=True).create(runtime)
        python = runtime / "bin/python"
        _run([str(python), "-m", "pip", "install", "--no-input", f"{package}[search]"],
             timeout=1800, env=_chemistry_env())
        _verify_chemistry_runtime(python)
        return python
    except BaseException:
        shutil.rmtree(runtime, ignore_errors=True)
        raise


def _sci_executable() -> str:
    candidate = shutil.which("sci")
    if not candidate:
        raise RuntimeError("The sci executable is required to enable the environment")
    return candidate


def _check_discovery(home: Path) -> None:
    code = ("from sci_cli.plugins import discover_plugins\n"
            "from tools.registry import registry\n"
            "discover_plugins(force=True)\n"
            "if registry.get_entry('srg_action') is None:\n"
            "    raise RuntimeError('srg_action was not discovered')\n")
    python_path = os.pathsep.join(path for path in sys.path if path)
    _run([sys.executable, "-c", code], timeout=120,
         env={**os.environ, "SCI_HOME": str(home), "PYTHONPATH": python_path})


def _write_runtime(path: Path, package: Path, chemistry_python: Path) -> None:
    settings = {"SRG_PACKAGE_ROOT": str(package),
                "SRG_CHEMISTRY_PYTHON": str(chemistry_python),
                "SRG_BACKEND_TIMEOUT_SECONDS": "300"}
    fd, temp = tempfile.mkstemp(prefix=".runtime-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(settings, stream, indent=2)
            stream.write("\n")
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _check_legacy_plugin(home: Path) -> None:
    config = home / "config.yaml"
    if not config.is_file():
        return
    from sci_yaml import safe_load

    parsed = safe_load(config.read_text()) or {}
    plugins = parsed.get("plugins", {}) if isinstance(parsed, dict) else {}
    enabled = plugins.get("enabled", []) if isinstance(plugins, dict) else []
    if isinstance(enabled, list) and "synthesis-route-gym" in enabled:
        raise ValueError("Disable the legacy synthesis-route-gym plugin before installing retrosynthesis")


def install_retrosynthesis(*, model_location: str | None = None,
                           model_python: str | None = None) -> int:
    """Install the no-model environment, or add approved local LocalRetro assets."""
    if model_python and not model_location:
        raise ValueError("--model-python requires --model-location")
    home = get_default_sci_root().expanduser().resolve()
    checkout = home / "environments/retrosynthesis/source"
    package = checkout / "environments/retrosynthesis"
    runtime = home / "runtimes/retrosynthesis"
    plugin = home / "plugins/retrosynthesis"
    skill = home / "skills/retrosynthesis"
    model_assets = home / "models/retrosynthesis/localretro"
    model_preexisting = model_assets.exists() or model_assets.is_symlink()
    _check_legacy_plugin(home)
    if any(path.exists() or path.is_symlink() for path in (checkout, runtime, plugin, skill)):
        raise ValueError("Retrosynthesis is already installed or partially installed in this profile")
    fetch_pinned_source(RETROSYNTHESIS_REPO, RETROSYNTHESIS_COMMIT, checkout)
    enable_attempted = False
    try:
        source_plugin = package / "integrations/agent_scientist"
        source_skill = package / "skills/retrosynthesis"
        if not (source_plugin / "plugin.yaml").is_file() or not (source_skill / "SKILL.md").is_file():
            raise ValueError("Pinned release lacks the retrosynthesis plugin or skill")
        chemistry = _ensure_chemistry_runtime(package, runtime)
        sci = _sci_executable()
        # The parent CLI has completed bootstrap. Nested Sci invocations must not
        # prepare a second PM generation or republish checkout launchers using a
        # custom profile's interpreter.
        env = {**os.environ, "SCI_HOME": str(home), "SCI_DISABLE_LAZY_INSTALLS": "1"}
        if model_location:
            with tempfile.TemporaryDirectory(prefix=".sci-default-", dir=home) as wrapper_dir:
                wrapper = Path(wrapper_dir) / "sci-default"
                wrapper.write_text(f"#!/bin/sh\nexec {shlex.quote(sci)} -p default \"$@\"\n")
                wrapper.chmod(0o700)
                command = [sys.executable, str(package / "scripts/setup_retrosynthesis.py"), "install",
                           "--sci-home", str(home), "--chemistry-python", str(chemistry),
                           "--sci-executable", str(wrapper),
                           "--existing-rebolt-root", str(Path(model_location).expanduser())]
                if model_python:
                    command.extend(["--existing-rebolt-python", str(Path(model_python).expanduser())])
                enable_attempted = True
                _run(command, timeout=1800, env=env)
        else:
            plugin.parent.mkdir(parents=True, exist_ok=True)
            skill.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_plugin, plugin)
            shutil.copytree(source_skill, skill)
            _write_runtime(plugin / "runtime.json", package, chemistry)
            enable_attempted = True
            _run([sci, "-p", "default", "plugins", "enable", "retrosynthesis",
                  "--no-allow-tool-override"],
                 timeout=1800, env=env)
        _check_discovery(home)
        _verify_chemistry_runtime(chemistry)
    except BaseException:
        if enable_attempted:
            try:
                _run([_sci_executable(), "-p", "default", "plugins", "disable", "retrosynthesis"],
                     timeout=120, env={**os.environ, "SCI_HOME": str(home),
                                       "SCI_DISABLE_LAZY_INSTALLS": "1"})
            except Exception:
                pass
        shutil.rmtree(plugin, ignore_errors=True)
        shutil.rmtree(skill, ignore_errors=True)
        shutil.rmtree(runtime, ignore_errors=True)
        if not model_preexisting:
            shutil.rmtree(model_assets, ignore_errors=True)
        shutil.rmtree(checkout, ignore_errors=True)
        raise
    print(f"Retrosynthesis installed from {RETROSYNTHESIS_COMMIT} in {home}; srg_action discovered.")
    return 0
