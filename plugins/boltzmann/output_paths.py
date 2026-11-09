"""Persistent, owning-profile destinations for scientific artifacts."""

from pathlib import Path


def output_directory(requested: str | None = None) -> Path:
    from sci_constants import get_sci_home
    from sci_cli.config import load_config
    from gateway.cwd_placeholder import CWD_PLACEHOLDERS

    home = get_sci_home()
    terminal = load_config().get("terminal", {})
    workspace = home / "workspace"
    configured = str(terminal.get("cwd") or "").strip()
    # Downloads run on the connector host, not inside a remote terminal. Never
    # reinterpret a container's /workspace or an SSH path as a local directory.
    if terminal.get("backend", "local") == "local" and configured and configured not in CWD_PLACEHOLDERS:
        configured_path = Path(configured).expanduser()
        workspace = configured_path if configured_path.is_absolute() else workspace / configured_path
    destination = Path(requested).expanduser() if requested else Path("outputs")
    return (destination if destination.is_absolute() else workspace / destination).resolve()
