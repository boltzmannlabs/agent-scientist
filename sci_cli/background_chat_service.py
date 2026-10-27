"""Local service holding existing PtySession workers across terminal disconnects.

No model requests, prompts, or scientific submissions are retried here. The
classic CLI remains the only conversation writer and owns its normal lease.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import math
import os
from pathlib import Path
import secrets
import signal
import stat
import sys
import time
import uuid

import psutil

from sci_cli.background_chats import FRAME_LIMIT, TERMINAL_ENV_KEYS, locations
from sci_cli.pty_session import PtySession
from sci_cli.pty_bridge import PtyUnavailableError
from utils import atomic_json_write


class Peer:
    def __init__(self, writer):
        self.writer = writer
        self.lock = asyncio.Lock()

    async def _send(self, payload):
        self.writer.write(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
        await asyncio.wait_for(self.writer.drain(), 2)

    async def send(self, payload):
        async with self.lock:
            await self._send(payload)

    async def send_bytes(self, data):
        # Bound frames without interleaving live output into a buffered replay.
        async with self.lock:
            for offset in range(0, len(data), 32768):
                await self._send({"output": base64.b64encode(data[offset:offset + 32768]).decode()})

    async def close(self, code=0):
        with contextlib.suppress(OSError, asyncio.TimeoutError):
            await self.send({"closed": code})
        self.writer.close()


class ChatService:
    def __init__(self, home, *, worker_factory=None):
        if os.name != "posix":
            raise RuntimeError("Persistent CLI chats currently require Linux/macOS or WSL.")
        self.home, self.root, self.endpoint = locations(home)
        self.token = secrets.token_urlsafe(32)
        self.chats = {}
        self.start_lock = asyncio.Lock()
        self.stopping = asyncio.Event()
        self.worker_factory = worker_factory or self._spawn
        from sci_cli.config_effective import load_user_config_effective
        from sci_cli.config_defaults import DEFAULT_CONFIG
        cfg = load_user_config_effective(self.home / "config.yaml", fail_closed=True).get("session", {})
        defaults = DEFAULT_CONFIG["session"]
        self.idle_timeout = float(cfg.get("background_idle_timeout", defaults["background_idle_timeout"]))
        if not math.isfinite(self.idle_timeout) or self.idle_timeout < 0:
            raise ValueError("session.background_idle_timeout must be non-negative.")

    def _spawn(self, session_id, cwd, cols, rows, launch_args=None, terminal_env=None):
        from sci_cli.pty_bridge import PtyBridge
        from tools.environments.local import served_profile_child_env
        from sci_cli._launchers import runtime_command
        args = list(launch_args or ["--cli", "--no-daemon", "chat"])
        if session_id:
            args += ["--resume", session_id]
        env = served_profile_child_env(target_home=self.home, inherit_credentials=True)
        if terminal_env is not None:
            for name in TERMINAL_ENV_KEYS:
                env.pop(name, None)
            env.update(terminal_env)
        # Module loading must not depend on the user's chosen workspace cwd.
        repo = Path(__file__).resolve().parents[1]
        for name in ("SCI_PROFILE", "SCI_PROFILE_NAME", "SCI_YOLO_MODE", "SCI_IGNORE_RULES",
                     "SCI_IGNORE_USER_CONFIG", "SCI_SAFE_MODE", "SCI_SESSION_SOURCE",
                     "SCI_SESSION_SOURCE_EXPLICIT", "TERMINAL_CWD"):
            env.pop(name, None)
        command = runtime_command(repo, args, home=self.home)
        return PtyBridge.spawn(command, cwd=cwd, env=env, cols=cols, rows=rows)

    def _lookup(self, key=None, pid=None):
        matches = [chat for chat in self.chats.values()
                   if (key is not None and key in (chat["id"], chat["session_id"]))
                   or (pid is not None and pid == chat["process"].pid)]
        if matches:
            return next((chat for chat in matches if chat["pty"].alive), matches[-1])
        raise ValueError("No matching background chat in this profile.")

    def snapshot(self):
        result = []
        for c in self.chats.values():
            alive = c["pty"].alive and c["pty"].bridge.is_alive()
            state = c["state"] if alive else "stopped"
            if alive and state not in ("starting", "stopping") and time.monotonic() - c["reported"] > 10:
                state = "worker alive; execution status unavailable"
            result.append({"id": c["id"], "session_id": c["session_id"], "pid": c["process"].pid,
                           "alive": alive, "state": state, "attached": c["pty"].attached,
                           "background_tasks": c["background_tasks"]})
        return {"chats": result, "profile_home": str(self.home), "pid": os.getpid()}

    def persist(self):
        snapshot = self.snapshot()
        if snapshot != getattr(self, "_saved_snapshot", None):
            atomic_json_write(self.root / "chats.json", snapshot, mode=0o600)
            self._saved_snapshot = snapshot

    async def start(self, params):
        session_id = params.get("session_id") or None
        cwd = str(Path(params.get("cwd") or self.home).resolve())
        if not Path(cwd).is_dir():
            raise ValueError("The workspace directory does not exist.")
        async with self.start_lock:
            for item in self.snapshot()["chats"]:
                if session_id and session_id in (item["id"], item["session_id"]) and item["alive"]:
                    return {"id": item["id"], "existing": True}
            if session_id:
                from sci_cli.active_sessions import active_session_registry_snapshot
                if any(e.get("session_id") == session_id for e in active_session_registry_snapshot(self.home, strict=True)):
                    raise ValueError("This conversation still has a writer. Close it before moving it to background mode.")
                from sci_state import SessionDB
                with SessionDB(self.home / "state.db", read_only=True) as db:
                    if not db.get_session(session_id):
                        raise ValueError("Conversation not found in this profile.")
            key = uuid.uuid4().hex
            launch_args = params.get("launch_args")
            if launch_args is not None:
                from sci_cli.main import _light_chat_parser
                if not isinstance(launch_args, list) or not all(isinstance(a, str) for a in launch_args):
                    raise ValueError("Invalid chat launch arguments.")
                try:
                    parsed = _light_chat_parser().parse_args(launch_args)
                except SystemExit:
                    raise ValueError("Invalid chat launch arguments.") from None
                if parsed.command != "chat" or not parsed.no_daemon or not parsed.cli:
                    raise ValueError("A worker must be a foreground classic chat.")
            options = {"launch_args": launch_args} if launch_args is not None else {}
            if "terminal_env" in params:
                terminal_env = params["terminal_env"]
                if (not isinstance(terminal_env, dict)
                        or not terminal_env.keys() <= TERMINAL_ENV_KEYS
                        or any(not isinstance(value, str) or len(value) > 512 or "\x00" in value
                               for value in terminal_env.values())):
                    raise ValueError("Invalid terminal display environment.")
                options["terminal_env"] = terminal_env
            bridge = await asyncio.to_thread(self.worker_factory, session_id, cwd,
                                            int(params.get("cols", 80)), int(params.get("rows", 24)), **options)
            try:
                process = psutil.Process(bridge.pid)
            except psutil.Error:
                await asyncio.to_thread(bridge.close)
                raise ValueError("Background CLI exited before startup completed; no live worker was registered.") from None
            pty = PtySession(key, bridge, buffer_cap=2 * 1024 * 1024, read_timeout=0.1)
            self.chats[key] = {"id": key, "session_id": session_id, "pty": pty,
                               "process": process, "state": "starting",
                               "reported": time.monotonic(), "background_tasks": 0,
                               "idle_since": None, "attach_lock": asyncio.Lock()}
            await pty.start()
            self.persist()
            return {"id": key, "existing": False}

    async def close_worker(self, chat):
        peer = chat["pty"]._ws
        if peer:
            await peer.close(4410)
        await chat["pty"].close()

    async def stop(self, chat, *, force=False):
        chat["state"] = "stopping"
        self.persist()
        process = chat["process"]
        try:
            if force:
                process.kill()
            else:
                process.send_signal(signal.SIGTERM)
            if process.status() == psutil.STATUS_STOPPED:
                process.send_signal(signal.SIGCONT)
            await asyncio.to_thread(process.wait, timeout=5)
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            return {"state": "stopping", "message": "Stop requested; worker has not exited. Check status before resuming."}
        await self.close_worker(chat)
        self.persist()
        return {"state": "stopped", "message": "Local chat stopped. Already submitted remote jobs may continue."}

    async def control(self, params):
        handlers = {"status": self.status, "start": self.start, "worker": self.worker,
                    "detach": self.detach, "navigate": self.navigate, "stop": self.stop_request, "shutdown": self.shutdown}
        handler = handlers.get(params.get("action"))
        if handler is None:
            raise ValueError("Unknown background control action.")
        return await handler(params)

    async def status(self, params):
        return self.snapshot()

    async def worker(self, params):
        # Startup reports may arrive before the spawning thread returns.
        async with self.start_lock:
            try:
                chat = self._lookup(pid=params.get("pid"))
            except ValueError:
                return {"managed": False}
        state = params.get("state")
        if state not in ("idle", "running", "waiting for input"):
            raise ValueError("Invalid worker state.")
        chat.update(session_id=params.get("session_id"), reported=time.monotonic(),
                    background_tasks=int(params.get("background_tasks", 0)))
        if chat["state"] != "stopping":
            chat["state"] = state
        return {"managed": True}

    async def detach(self, params):
        chat = self._lookup(params.get("id"), params.get("pid"))
        peer = chat["pty"]._ws
        chat["pty"].detach(peer)
        if peer:
            await peer.close(0)
        self.persist()
        return {"state": "detached", "id": chat["id"]}

    async def navigate(self, params):
        chat = self._lookup(pid=params.get("pid"))
        peer = chat["pty"]._ws
        if not peer:
            raise ValueError("No terminal is attached; reconnect before switching conversations.")
        await peer.send({"relaunch": params["args"], "home": params["target_home"]})
        chat["pty"].detach(peer)
        await peer.close(0)
        return {"state": "detached"}

    async def stop_request(self, params):
        return await self.stop(self._lookup(params.get("id")), force=params.get("force") is True)

    async def shutdown(self, params):
        if any(c["alive"] for c in self.snapshot()["chats"]):
            raise ValueError("Stop the profile's background chats before stopping its service.")
        self.stopping.set()
        return {"state": "stopped"}

    async def handle(self, reader, writer):
        peer, chat = Peer(writer), None
        try:
            auth = json.loads(await asyncio.wait_for(reader.readline(), 5))
            if not isinstance(auth, dict):
                raise ValueError("Expected an authentication object.")
            if auth.get("home") != str(self.home) or not secrets.compare_digest(str(auth.get("token", "")), self.token):
                raise ValueError("Background service authentication failed.")
            params = json.loads(await asyncio.wait_for(reader.readline(), 5))
            if not isinstance(params, dict):
                raise ValueError("Expected a control object.")
            if params.get("action") != "attach":
                await peer.send(await self.control(params))
                return
            chat = self._lookup(params.get("id"))
            if not chat["pty"].alive or not chat["pty"].bridge.is_alive():
                raise ValueError("This worker stopped. Resume its saved session; no work was restarted.")
            async with chat["attach_lock"]:
                if chat["pty"].attached and params.get("takeover") is not True:
                    raise ValueError("Another terminal is attached. Use attach --takeover to move the viewer here.")
                await peer.send({"attached": chat["id"], "truncated": chat["pty"].buffer.truncated})
                chat["pty"].bridge.resize(int(params.get("cols", 80)), int(params.get("rows", 24)))
                if not await chat["pty"].attach(peer):
                    return
            self.persist()
            while line := await reader.readline():
                msg = json.loads(line)
                if not isinstance(msg, dict):
                    raise ValueError("Expected an input object.")
                # PtySession owns the generation fence: superseded peers cannot type.
                if chat["pty"]._ws is not peer:
                    break
                if msg.get("action") == "detach":
                    break
                if msg.get("action") == "resize":
                    chat["pty"].bridge.resize(int(msg["cols"]), int(msg["rows"]))
                elif msg.get("action") == "input":
                    if not await chat["pty"].write(peer, base64.b64decode(msg["data"], validate=True)):
                        break
        except (ValueError, TypeError, KeyError, OSError, asyncio.TimeoutError, PtyUnavailableError) as exc:
            with contextlib.suppress(OSError, asyncio.TimeoutError):
                await peer.send({"error": str(exc)})
        finally:
            if chat:
                chat["pty"].detach(peer)
                self.persist()
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()

    async def reap(self):
        while not self.stopping.is_set():
            await asyncio.sleep(2)
            now = time.monotonic()
            for chat in list(self.chats.values()):
                if not chat["pty"].bridge.is_alive():
                    await self.close_worker(chat)
                    chat["state"] = "stopped"
                    continue
                # Only a recently reported idle worker is eligible. Never guess
                # inactivity from an absence of output during a model/tool call.
                idle = (not chat["pty"].attached and chat["state"] == "idle"
                        and chat["background_tasks"] == 0 and now - chat["reported"] < 10)
                chat["idle_since"] = (chat["idle_since"] or now) if idle else None
                if idle and self.idle_timeout and now - chat["idle_since"] > self.idle_timeout:
                    await self.stop(chat)
            stopped = [key for key, chat in self.chats.items() if not chat["pty"].alive]
            for key in stopped[:-32]:
                self.chats.pop(key)
            self.persist()

    async def run(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        if self.endpoint.exists():
            info = self.endpoint.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():  # windows-footgun: ok — constructor requires POSIX
                raise ValueError("Unsafe existing background socket; refusing to replace it.")
            self.endpoint.unlink()
        server = await asyncio.start_unix_server(self.handle, path=str(self.endpoint), limit=FRAME_LIMIT)
        os.chmod(self.endpoint, 0o600)
        atomic_json_write(self.root / "server.json", {"pid": os.getpid(), "started": psutil.Process().create_time(),
                          "token": self.token}, mode=0o600)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stopping.set)  # windows-footgun: ok — constructor requires POSIX
        reaper = asyncio.create_task(self.reap())
        try:
            async with server:
                await self.stopping.wait()
        finally:
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
            for chat in self.chats.values():
                await self.stop(chat)
                if chat["pty"].bridge.is_alive():
                    await self.close_worker(chat)
            self.persist()
            (self.root / "server.json").unlink(missing_ok=True)
            self.endpoint.unlink(missing_ok=True)


def main():
    from sci_cli.active_sessions import _FileLock
    home, root, _ = locations(sys.argv[1])
    with _FileLock(root / "server.lock"):
        asyncio.run(ChatService(home).run())


if __name__ == "__main__":
    main()
