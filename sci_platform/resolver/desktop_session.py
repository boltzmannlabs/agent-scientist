"""Passive discovery of the current user's desktop display, never another user's."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os

import psutil

from sci_platform.host import facts

_DISPLAY_KEYS = frozenset({"DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY",
                           "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_TYPE"})
_DESKTOP_PROCESSES = frozenset({"gnome-shell", "gnome-session-binary", "plasmashell",
                              "xfce4-session", "mate-session", "cinnamon", "lxqt-session"})


@dataclass(frozen=True)
class DesktopSession:
    id: str
    label: str
    env: dict[str, str]


def desktop_sessions() -> list[DesktopSession]:
    if facts.os_family() != "linux":
        return [DesktopSession("local", "Server desktop", {})] if facts.interactive_session() else []
    candidates = []
    # A desktop-terminal launch can support desktops outside our passive process list.
    if not os.environ.get("SSH_CONNECTION") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        candidates.append({k: os.environ[k] for k in _DISPLAY_KEYS if k in os.environ})
    for proc in psutil.process_iter(["name", "uids"]):
        try:
            if proc.info["name"] not in _DESKTOP_PROCESSES or proc.info["uids"].real != os.getuid():
                continue
            env = proc.environ()
            candidates.append({k: env[k] for k in _DISPLAY_KEYS if k in env})
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    targets = {}
    for env in candidates:
        display = env.get("WAYLAND_DISPLAY") or env.get("DISPLAY")
        if not display:
            continue
        identity = display + "|" + env.get("XDG_RUNTIME_DIR", "")
        key = hashlib.sha256(identity.encode()).hexdigest()[:16]
        targets[key] = DesktopSession(key, f"Server desktop ({display})", env)
    return sorted(targets.values(), key=lambda target: target.label)
