"""Optional ChemE Viewer and numerical backends, prepared outside the Sci tree."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REVISION = "5b0576c63ae6e82ecad28db745c83f2ef2eb8994"
SOURCE = "https://github.com/ChemE-as-Code/core.git"
DWSIM_IMAGE = "cheme-dwsim:9.0.5"


def component_root() -> Path:
    from sci_constants import get_sci_home

    return Path(get_sci_home()) / "environments" / "cheme-components" / REVISION


def command(name: str) -> list[str]:
    from sci_platform.resolver import locate_command

    found = locate_command(name).command
    if not found:
        raise RuntimeError(f"{name} is required for this optional component")
    return list(found)


def _run(args, *, cwd=None, env=None, timeout=1800):
    subprocess.run(args, cwd=cwd, env=env, check=True, timeout=timeout)


def prepare_source(environment: dict[str, str]) -> Path:
    root = component_root()
    destination = root / "source"
    git = command("git")
    if destination.exists():
        revision = subprocess.check_output([*git, "rev-parse", "HEAD"], cwd=destination,
                                           env=environment, text=True, timeout=30).strip()
        if revision != REVISION:
            raise RuntimeError("ChemE component source revision differs from the pinned revision")
        return destination
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-", dir=root) as stage:
        checkout = Path(stage) / "core"
        _run([*git, "clone", "--no-checkout", "--filter=blob:none", SOURCE, str(checkout)], env=environment)
        _run([*git, "checkout", "--detach", REVISION], cwd=checkout, env=environment)
        checkout.rename(destination)
    return destination


def viewer_path() -> Path:
    return component_root() / "viewer"


def setup_viewer(environment: dict[str, str]) -> None:
    import pm

    node = pm.ensure("node", explicit=True, base_env=environment)
    npm = command("npm")
    source = prepare_source(environment) / "viewer"
    _run([*npm, "ci", "--no-audit", "--no-fund"], cwd=source, env=node.env)
    _run([*npm, "run", "build"], cwd=source, env=node.env)
    destination = viewer_path()
    # Keep a working build until the replacement has finished.
    with tempfile.TemporaryDirectory(prefix="viewer-", dir=component_root()) as stage:
        built = Path(stage) / "viewer"
        shutil.copytree(source / "dist", built)
        (built / "provenance.json").write_text(json.dumps({"source": SOURCE, "revision": REVISION,
                                                         "license": "AGPL-3.0-or-later"}) + "\n")
        shutil.copy2(source.parent / "LICENSE", built / "LICENSE")
        if destination.exists():
            shutil.rmtree(destination)
        built.rename(destination)
    print("ChemE Viewer prepared. Launch with: sci cheme --project PROJECT --viewer")


def setup_dwsim(environment: dict[str, str]) -> None:
    docker = command("docker")
    source = prepare_source(environment)
    _run([*docker, "build", "--platform", "linux/amd64", "-t", DWSIM_IMAGE,
          "-f", "docker/dwsim/Dockerfile", "."], cwd=source, env=environment, timeout=3600)


def idaes_environment(environment: dict[str, str]) -> dict[str, str]:
    import pm

    result = dict(environment)
    # Explicit upstream overrides remain available for remote/container workers.
    if not result.get("CHEME_IDAES_COMMAND") and not result.get("CHEME_IDAES_PYTHON"):
        python = pm.environment_python("cheme-idaes")
        if python is not None:
            result["CHEME_IDAES_PYTHON"] = str(python)
            result["IDAES_DATA"] = str(python.parents[3] / "solver-data")
    return result


def setup_idaes(environment: dict[str, str]) -> None:
    import pm

    project = Path(__file__).parent / "data" / "cheme-idaes-runtime"
    python = pm.ensure_project_environment("cheme-idaes", project, explicit=True)
    env = dict(environment)
    data = python.parents[3] / "solver-data"
    env["IDAES_DATA"] = str(data)
    # IDAES downloads and checksums its official platform-specific solver release.
    _run([str(python), "-c", "from idaes.commands.base import command_base; command_base()",
          "get-extensions", "--release", "3.4.2", "--to", str(data / "bin")], env=env)


def backend_status(environment: dict[str, str]) -> dict:
    env = idaes_environment(environment)
    status = {"viewer": {"ready": (viewer_path() / "index.html").is_file()},
              "idaes": {"ready": False}, "dwsim": {"ready": False}}
    python = env.get("CHEME_IDAES_PYTHON")
    if python:
        probe = subprocess.run([python, "-I", "-c", "import json,idaes; from pyomo.environ import SolverFactory; "
                                "s=SolverFactory('ipopt'); print(json.dumps({'version':idaes.__version__,"
                                "'ready':s.available(exception_flag=False)}))"], env=env, capture_output=True,
                               text=True, timeout=30)
        if probe.returncode == 0:
            status["idaes"] = json.loads(probe.stdout.splitlines()[-1])
        else:
            status["idaes"]["detail"] = probe.stderr[-500:]
    elif env.get("CHEME_IDAES_COMMAND"):
        status["idaes"]["detail"] = "External worker configured; readiness requires a real solve"
    from sci_platform.resolver import locate_command

    docker = locate_command("docker").command
    if docker:
        probe = subprocess.run([*docker, "image", "inspect", DWSIM_IMAGE], env=env,
                               capture_output=True, text=True, timeout=30)
        status["dwsim"] = {"ready": probe.returncode == 0, "image": DWSIM_IMAGE,
                            "detail": "Image present; numerical benchmark required"}
    return status
