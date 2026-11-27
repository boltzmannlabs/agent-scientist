"""Managed chemical engineering CLI; upstream arguments stay with upstream."""
from __future__ import annotations

import argparse
from pathlib import Path


def _run(args):
    from sci_cli.cheme import run_command

    return run_command(args)


def build_cheme_parser(subparsers):
    parser = subparsers.add_parser(
        "cheme", help="Validate, calculate and draw chemical engineering projects",
        description="Run pinned ChemE-as-Code in an isolated managed environment. "
                    "Pass upstream arguments after --, e.g. sci cheme -- process --help.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--setup", action="store_true", help="Prepare the locked engineering runtime")
    modes.add_argument("--check-env", action="store_true", help="Check readiness without installing")
    modes.add_argument("--setup-viewer", action="store_true", help="Build the pinned interactive Viewer")
    modes.add_argument("--setup-idaes", action="store_true", help="Prepare IDAES and its numerical solvers")
    modes.add_argument("--setup-dwsim", action="store_true", help="Build the pinned DWSIM Docker image")
    modes.add_argument("--check-backends", action="store_true", help="Report optional component readiness as JSON")
    modes.add_argument("--viewer", action="store_true", help="Serve the project with the prepared Viewer on localhost")
    modes.add_argument("--chat-diagrams", action="store_true", help="Export enlarged process and stream-table images for chat")
    parser.add_argument("--port", type=int, default=8765, help="Local Viewer port (default: 8765)")
    parser.add_argument("--project", type=Path, help="Working directory for the engineering command")
    parser.add_argument("cheme_args", nargs=argparse.REMAINDER, help="ChemE-as-Code arguments after --")
    parser.set_defaults(func=_run)
