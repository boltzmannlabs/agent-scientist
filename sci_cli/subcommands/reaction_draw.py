"""Chemical-figure command, kept outside the model's core tool schema."""
from __future__ import annotations

from pathlib import Path


def _run(args):
    from sci_cli.reaction_draw import run_command

    raise SystemExit(run_command(args))


def build_reaction_draw_parser(subparsers):
    parser = subparsers.add_parser(
        "reaction-draw", help="Draw checked chemical structures and reaction mechanisms",
        description="Render a reaction-draw JSON specification as PNG, SVG and editable CDXML.")
    parser.add_argument("input", nargs="?", type=Path, help="Reaction-draw format-2 JSON input")
    parser.add_argument("--out", type=Path, help="Task-owned output directory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--setup", action="store_true", help="Prepare managed dependencies and check the renderer")
    modes.add_argument("--check-env", action="store_true", help="Check installed dependencies without installing")
    resolution = parser.add_mutually_exclusive_group()
    resolution.add_argument("--dpi", type=float, help="PNG resolution; upstream default is 600 dpi")
    resolution.add_argument("--png-width", type=int, help="PNG width in pixels instead of dpi")
    parser.add_argument("--quiet", action="store_true", help="Print concise results while retaining checks")
    parser.set_defaults(func=_run)
