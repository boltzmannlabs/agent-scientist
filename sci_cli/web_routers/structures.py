"""Authenticated PyMOL desktop actions over the existing managed-files policy."""
import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from sci_cli import web_pymol
from sci_cli.web_routers._common import _config_profile_scope
from sci_cli.web_routers.files import _fs_read_bytes, _managed_readable_file
from sci_cli.web_deps import late
from sci_constants import get_sci_home

router = APIRouter()
_require_token = late("_require_token")


class LaunchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    desktop_id: str = Field(min_length=1, max_length=64)


def _root() -> Path:
    return get_sci_home() / "environments" / web_pymol.ENVIRONMENT


@router.get("/api/structures/pymol")
async def pymol_status(request: Request, profile: str | None = None):
    _require_token(request)
    with _config_profile_scope(profile):
        return await asyncio.to_thread(web_pymol.runtime_status, _root())


@router.post("/api/structures/pymol/install")
async def pymol_install(request: Request, profile: str | None = None):
    _require_token(request)
    with _config_profile_scope(profile):
        return await asyncio.to_thread(web_pymol.install_runtime, _root())


@router.post("/api/structures/pymol/launch")
async def pymol_launch(body: LaunchBody, request: Request, profile: str | None = None):
    _require_token(request)
    with _config_profile_scope(profile):
        _, target, _, _, _ = _managed_readable_file(request, body.path)
        suffix = target.suffix.lower()
        if suffix not in {".pdb", ".cif", ".mmcif"}:
            raise HTTPException(415, "Open a PDB/mmCIF structure, not a script or PyMOL session.")
        content = await asyncio.to_thread(_fs_read_bytes, target, web_pymol.MAX_BYTES + 1)
        if not content or len(content) > web_pymol.MAX_BYTES:
            raise HTTPException(413, "Structure must contain data and be no larger than 20 MiB.")
        return await web_pymol.launch_desktop(request, _root(), content, suffix, target.name, body.desktop_id)
