"""Stdio MCP adapter for Boltzmann platform-tools mode only."""

import sys
from pathlib import Path
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parent
# Import this plugin as a package; its tools.py must not shadow Sci tools/.
sys.path = [entry for entry in sys.path if Path(entry).resolve() != PLUGIN_DIR]
sys.path.insert(0, str(PLUGIN_DIR.parent))

from mcp.server import MCPServer

from boltzmann.tools import (
    handle_boltzmann_download,
    handle_boltzmann_fetch_tool_log,
    handle_boltzmann_status,
    handle_boltzmann_submit,
    handle_boltzmann_upload,
)
from boltzmann.auth import require_authorized

mcp = MCPServer(
    "boltzmann",
    description="Authenticated Boltzmann scientific platform tools",
)


@mcp.tool()
def boltzmann_submit(
    job_name: str,
    experiment_data: dict[str, Any],
    experiment_name: str = "",
    allow_partial_validation: bool = False,
) -> str:
    """Submit one specified job; omit experiment_name for a generated platform label."""
    result = handle_boltzmann_submit(
        job_name=job_name,
        experiment_data=experiment_data,
        experiment_name=experiment_name,
        allow_partial_validation=allow_partial_validation,
    )
    from .job_monitor import monitor_result
    return monitor_result("boltzmann_submit", {}, result, session_id="mcp")


@mcp.tool()
def boltzmann_status(
    job_name: str,
    doc_id: str,
    output_folder: str | None = None,
) -> str:
    """Poll the existing Boltzmann job identified by job_name and doc_id."""
    result = handle_boltzmann_status(
        job_name=job_name,
        doc_id=doc_id,
        output_folder=output_folder,
    )
    from .job_monitor import monitor_result
    return monitor_result("boltzmann_status", {}, result, session_id="mcp")


@mcp.tool()
def boltzmann_download(download_url: str, output_folder: str) -> str:
    """Download one signed output artifact from a completed Boltzmann job."""
    return handle_boltzmann_download(
        download_url=download_url,
        output_folder=output_folder,
    )


@mcp.tool()
def boltzmann_upload(local_path: str, job_name: str, input_field: str,
                     experiment_data: dict[str, Any] | None = None,
                     allow_partial_validation: bool = False) -> str:
    """Upload one validated local input file to Boltzmann platform storage."""
    return handle_boltzmann_upload(local_path=local_path, job_name=job_name,
                                  input_field=input_field, experiment_data=experiment_data,
                                  allow_partial_validation=allow_partial_validation)


@mcp.tool()
def boltzmann_fetch_tool_log(experiment_id: str, collection: str | None = None,
                             job_name: str | None = None) -> str:
    """Read one durable record, resolving its collection from the exact submitted job name."""
    return handle_boltzmann_fetch_tool_log(
        collection=collection,
        experiment_id=experiment_id,
        job_name=job_name,
    )


def main() -> None:
    try:
        require_authorized()
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
