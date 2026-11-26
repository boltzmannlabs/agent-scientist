"""Run the pinned chemical renderer in a locked, isolated PM environment."""
from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys

ENVIRONMENT = "reaction-draw"


def bundle_root() -> Path:
    from third_party import reaction_draw

    return Path(reaction_draw.__file__).resolve().parent


def _runtime(*, check_only: bool, explicit: bool):
    import pm

    if check_only:
        python = pm.environment_python(ENVIRONMENT)
        if python is None:
            raise RuntimeError("Drawing dependencies are not prepared. Run: sci reaction-draw --setup")
        if not pm.is_installed("chromium"):
            raise RuntimeError("Managed Chromium is not prepared. Run: sci reaction-draw --setup")
        browser_env = pm.env_for("chromium")
    else:
        python = pm.ensure_project_environment(
            ENVIRONMENT, bundle_root() / "runtime", explicit=explicit)
        browser_env = pm.ensure("chromium", explicit=explicit).env
    environment = dict(browser_env)
    # The application's import paths and venv must not leak into its isolated renderer.
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(key, None)
    environment["VIRTUAL_ENV"] = str(python.parent.parent)
    environment["PATH"] = str(python.parent) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONIOENCODING"] = "utf-8"
    return python, environment


def run_command(args) -> int:
    check_only = bool(args.check_env)
    setup = bool(args.setup)
    if (check_only or setup) and (args.input is not None or args.out is not None):
        print("Environment checks do not take input/output paths.", file=sys.stderr)
        return 2
    if not (check_only or setup):
        if args.input is None or args.out is None:
            print("Supply INPUT.json and --out DIR, or use --check-env / --setup.", file=sys.stderr)
            return 2
        if not args.input.is_file():
            print(f"Input file does not exist: {args.input}", file=sys.stderr)
            return 2
        if args.out.exists() and not args.out.is_dir():
            print("The output path must be a directory.", file=sys.stderr)
            return 2
    for name in ("dpi", "png_width"):
        value = getattr(args, name)
        if value is not None and (value <= 0 or isinstance(value, float) and not math.isfinite(value)):
            print("Image resolution must be a finite positive value.", file=sys.stderr)
            return 2
    from pm import InstallError

    try:
        python, environment = _runtime(check_only=check_only, explicit=setup)
        command = [str(python), str(bundle_root() / "upstream" / "scripts" / "draw_figure.py")]
        if check_only or setup:
            command.append("--check-env")
        else:
            command.extend([str(args.input.resolve()), "--out", str(args.out.resolve())])
            for flag, value in (("--dpi", args.dpi), ("--png-width", args.png_width)):
                if value is not None:
                    command.extend([flag, str(value)])
            if args.quiet:
                command.append("--quiet")
        return subprocess.call(command, env=environment)
    except (InstallError, RuntimeError, OSError) as exc:
        print(f"Reaction drawing unavailable: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Reaction drawing cancelled; inspect the saved check status before using any output.", file=sys.stderr)
        return 130
