"""Run ChemE-as-Code without importing its dependencies into the agent."""
from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys

ENVIRONMENT = "cheme-as-code"
ENTRYPOINT = "from chemeascode.interfaces.cli import app; app()"


def runtime_project() -> Path:
    return Path(__file__).resolve().parent / "data" / "cheme-runtime"


def _runtime(*, check_only: bool, explicit: bool):
    import pm
    from tools.environments.local import served_profile_child_env

    if check_only:
        python = pm.environment_python(ENVIRONMENT)
        if python is None:
            raise RuntimeError("Engineering dependencies are not prepared. Run: sci cheme --setup")
    else:
        python = pm.ensure_project_environment(ENVIRONMENT, runtime_project(), explicit=explicit)
    environment = served_profile_child_env()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(key, None)
    environment["VIRTUAL_ENV"] = str(python.parent.parent)
    environment["PATH"] = str(python.parent) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONIOENCODING"] = "utf-8"
    from sci_cli.cheme_components import idaes_environment

    return python, idaes_environment(environment)


def run_command(args) -> int:
    values = list(args.cheme_args)
    if values[:1] == ["--"]:
        values.pop(0)
    probe = args.check_env or args.setup
    optional_setup = args.setup_viewer or args.setup_idaes or args.setup_dwsim or args.check_backends
    if (probe or optional_setup) and (values or args.project is not None):
        print("Environment checks do not take project paths or engineering arguments.", file=sys.stderr)
        return 2
    project = args.project.resolve() if args.project is not None else Path.cwd()
    if not project.is_dir():
        print(f"Project working directory does not exist: {project}", file=sys.stderr)
        return 2
    if args.viewer and (values or not 1 <= args.port <= 65535):
        print("Viewer requires a valid port and no upstream arguments.", file=sys.stderr)
        return 2
    if args.chat_diagrams and values:
        print("Chat diagram export takes no upstream arguments.", file=sys.stderr)
        return 2
    from pm import InstallError

    try:
        if optional_setup:
            from tools.environments.local import served_profile_child_env
            from sci_cli.cheme_components import backend_status, setup_dwsim, setup_idaes, setup_viewer

            environment = served_profile_child_env()
            if args.check_backends:
                print(json.dumps(backend_status(environment), indent=2))
            else:
                action = next(fn for selected, fn in [(args.setup_viewer, setup_viewer),
                              (args.setup_idaes, setup_idaes), (args.setup_dwsim, setup_dwsim)] if selected)
                action(environment)
            return 0
        if args.viewer:
            from sci_cli.cheme_components import viewer_path

            ui = viewer_path()
            if not (ui / "index.html").is_file():
                raise RuntimeError("Viewer is not prepared. Run: sci cheme --setup-viewer")
            values = ["serve", "--repo", str(project), "--ui", str(ui), "--port", str(args.port)]
        python, environment = _runtime(check_only=args.check_env, explicit=args.setup)
        if args.chat_diagrams:
            from sci_cli.cheme_diagrams import export_diagrams

            for output in export_diagrams(project, python, environment):
                print(output)
            return 0
        return subprocess.call(
            [str(python), "-c", ENTRYPOINT, *(["--version"] if probe else values or ["--help"])],
            cwd=project, env=environment)
    except (InstallError, RuntimeError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"Chemical engineering unavailable: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Engineering command cancelled; inspect saved results before using them.", file=sys.stderr)
        return 130
