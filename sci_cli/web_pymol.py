"""Optional PyMOL desktop runtime; launch fixed recipes in the server's GUI session."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

import pm
from fastapi import HTTPException, Request

from sci_cli._subprocess_compat import windows_hide_flags
from sci_platform.host import facts
from sci_platform.resolver.desktop_session import desktop_sessions

ENVIRONMENT = "pymol-desktop"
REQUIREMENTS = ["pymol-open-source-whl==3.2.0.2", "numpy>=2.2,<3", "PySide6>=6.10,<7"]
MAX_BYTES = 20 * 1024 * 1024
START_TIMEOUT = 30
WORKER = Path(__file__).with_name("pymol_desktop_worker.py")
_INSTALL_LOCK = threading.Lock()
_INSTALLING: set[str] = set()


def runtime_status(root: Path) -> dict:
    with _INSTALL_LOCK:
        installing = str(root) in _INSTALLING
    return {"installed": pm.environment_python(ENVIRONMENT, root=root) is not None,
            "installing": installing, "package": REQUIREMENTS[0],
            "desktops": [{"id": target.id, "label": target.label} for target in desktop_sessions()]}


def install_runtime(root: Path) -> dict:
    with _INSTALL_LOCK:
        if str(root) in _INSTALLING:
            raise HTTPException(409, "PyMOL installation is already in progress for this profile.")
        _INSTALLING.add(str(root))
    try:
        pm.ensure_environment(ENVIRONMENT, REQUIREMENTS, root=root, explicit=True, timeout=300)
    except pm.InstallError as exc:
        raise HTTPException(503, "PyMOL installation failed. Check platform support, network access, and available disk space.") from exc
    finally:
        with _INSTALL_LOCK:
            _INSTALLING.discard(str(root))
    return runtime_status(root)


async def launch_desktop(request: Request, root: Path, content: bytes, suffix: str, name: str, desktop_id: str) -> dict:
    target = next((item for item in desktop_sessions() if item.id == desktop_id), None)
    if target is None:
        raise HTTPException(409, "The selected server desktop is unavailable. Sign in to the server desktop and try again.")
    python = pm.environment_python(ENVIRONMENT, root=root)
    if python is None:
        raise HTTPException(409, "Install PyMOL Desktop for this profile first.")
    work = Path(tempfile.mkdtemp(prefix="sci-pymol-"))
    proc = None
    launched = False
    try:
        (work / ("structure" + suffix)).write_bytes(content)
        (work / "launch.json").write_text(json.dumps({"suffix": suffix, "name": name}), encoding="utf-8")
        # PyMOL gets display access, not SCI's credentials or user startup scripts.
        env = {"HOME": str(work), "USERPROFILE": str(work), "XDG_CONFIG_HOME": str(work / "config"),
               "TMPDIR": str(work), "TEMP": str(work), "TMP": str(work),
               "PATH": str(python.parent) + os.pathsep + os.defpath, "LANG": "C.UTF-8", **target.env}
        for key in ("SYSTEMROOT", "WINDIR"):
            if key in os.environ:
                env[key] = os.environ[key]
        with (work / "startup.log").open("wb") as log:
            spawning = asyncio.create_task(asyncio.to_thread(
                subprocess.Popen,
                [str(python), "-I", str(WORKER)],
                cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=log, start_new_session=facts.os_family() != "win32", creationflags=windows_hide_flags(),
            ))
            try:
                proc = await asyncio.shield(spawning)
            except asyncio.CancelledError:
                proc = await spawning
                raise
        deadline = time.monotonic() + START_TIMEOUT
        while not (work / "ready.json").is_file():
            if proc.poll() is not None:
                with (work / "startup.log").open("rb") as log:
                    log.seek(0, 2)
                    log.seek(max(0, log.tell() - 4096))
                    detail = log.read().decode("utf-8", errors="replace").strip()
                raise HTTPException(422, "PyMOL exited before loading the structure. " + (detail or "Check the structure, server display access, and Qt/OpenGL system libraries."))
            if await request.is_disconnected():
                raise HTTPException(499, "PyMOL launch cancelled before startup completed.")
            if time.monotonic() >= deadline:
                raise HTTPException(504, "PyMOL did not finish starting within 30 seconds; its process was stopped.")
            await asyncio.sleep(0.1)
        metadata = json.loads((work / "ready.json").read_text(encoding="utf-8-sig"))
        if proc.poll() is not None:
            raise HTTPException(422, "PyMOL closed before launch completed.")
        # The GUI belongs to the user after readiness, including after the HTTP request ends.
        threading.Thread(target=proc.wait, daemon=True, name="pymol-desktop-reaper").start()
        launched = True
        return {"pid": proc.pid, "desktop": target.label, **metadata}
    except OSError as exc:
        raise HTTPException(503, "Could not start PyMOL Desktop or create its temporary structure copy.") from exc
    finally:
        if not launched:
            if proc is not None and proc.poll() is None:
                proc.kill()
                await asyncio.to_thread(proc.wait)
            shutil.rmtree(work, ignore_errors=True)
