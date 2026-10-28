"""Environment installation and task entry points."""

from __future__ import annotations


def _install(args):
    from sci_cli.environments_install import install_retrosynthesis

    return install_retrosynthesis(model_location=args.model_location,
                                  model_python=args.model_python)


def _run(args):
    from sci_cli.environment_tasks import run_retrosynthesis_task

    return run_retrosynthesis_task(args)


def build_environments_parser(subparsers) -> None:
    parser = subparsers.add_parser("environments", help="Install and run scientific environments")
    commands = parser.add_subparsers(dest="environment_action", required=True)
    install = commands.add_parser("install", help="Install a pinned environment into the main profile")
    install.add_argument("environment", choices=("retrosynthesis",))
    install.add_argument("--model-location", help="Existing approved LocalRetro/REBOLT root; optional")
    install.add_argument("--model-python", help="Python with LocalRetro scientific dependencies")
    install.set_defaults(func=_install)
    run = commands.add_parser("run", help="Run an environment task with the main Agent Scientist")
    run.add_argument("environment", choices=("retrosynthesis",))
    run.add_argument("--target", required=True, help="Target SMILES")
    run.add_argument("--inventory", required=True, help="Inventory JSON or JSON file path")
    run.add_argument("--constraints", required=True, help="Constraint JSON or JSON file path")
    run.add_argument("--budget", help="Optional budget JSON or JSON file path")
    run.set_defaults(func=_run)
