"""Real shell launch and detach lifecycle checks, separate from daemon transport tests."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from sci_cli.background_chats import find_worker, read_server, request
from tests.sci_cli.test_background_chats import ROOT, Viewer, _resume_with_terminal, wait_for


@pytest.mark.platforms("posix")
@pytest.mark.live_system_guard_bypass  # Our recorded daemon is reparented when the shell launcher exits.
@pytest.mark.parametrize("managed", [False, True])
def test_shell_starts_service_and_terminal_detach_keeps_worker(tmp_path, monkeypatch, managed):
    import psutil
    import select
    from tests.fakes.fake_llm_provider import FakeLLMServer, write_sci_home
    home = tmp_path / ".sci"
    daemon = None
    relay = None
    master = None
    with FakeLLMServer() as model:
        write_sci_home(home, model.base_url)
        env = {**os.environ, "HOME": str(tmp_path), "SCI_HOME": str(home), "PYTHONPATH": str(ROOT),
               "TERM": "xterm-256color", "SCI_STATE_DB_GUARD_BYPASS": "1"}
        prefix = [sys.executable, "-m", "sci_cli.main"]
        if managed:
            # Match installed SCI: store Python has no application dependencies
            # until bootstrap selects the separately managed dependency tree.
            from pm.environments import install_state_dir, site_packages
            from sci_cli._launchers import runtime_command
            monkeypatch.setenv("HOME", str(tmp_path))
            monkeypatch.setenv("SCI_HOME", str(home))
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
            store = home / "tools"
            store.mkdir()
            interpreter = Path(sys._base_executable).resolve()
            (store / "facts.json").write_text(json.dumps({"packages": {"python": {
                "entry": str(interpreter.parents[1])}}}))
            state = install_state_dir(ROOT)
            state.mkdir(parents=True)
            selected = state / "environments" / "fixture" / "venv"
            site = site_packages(selected)
            site.mkdir(parents=True)
            (selected / "pyvenv.cfg").write_text("home = fixture\n")
            (site / "test-dependencies.pth").write_text(str(site_packages(Path(sys.prefix))) + "\n")
            (state / "facts.json").write_text(json.dumps({"packages": {"venv": {"environment": str(selected)}}}))
            env.update(SCI_RUNTIME_DIR=str(store), SCI_DISABLE_LAZY_INSTALLS="1")
            prefix = runtime_command(ROOT, python=interpreter, home=home)
        try:
            result = subprocess.run([*prefix, "background", "start", "--detach", "--json"],
                env=env, cwd=tmp_path, capture_output=True, text=True, timeout=40)
            assert result.returncode == 0, result.stderr + result.stdout
            daemon = psutil.Process(read_server(home)["pid"])
            key = json.loads(result.stdout.strip().splitlines()[-1])["id"]
            master, slave = os.openpty()
            import fcntl
            import termios
            import struct
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
            relay = subprocess.Popen([*prefix, "background", "attach", key],
                env=env, cwd=tmp_path, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            output = b""
            deadline = time.monotonic() + 30
            while "❯ ".encode() not in output and time.monotonic() < deadline:
                if select.select([master], [], [], 0.2)[0]:
                    output += os.read(master, 65536)
            assert "❯ ".encode() in output, output[-2000:]
            os.write(master, b"\x1d")
            assert relay.wait(timeout=15) == 0
            worker = find_worker(key, home)
            assert worker["alive"]
            wait_for(lambda: not find_worker(key, home)["attached"])
            assert model.main_requests() == []
            request("stop", home=home, id=key)
            wait_for(lambda: not find_worker(key, home))
            assert request("shutdown", home=home)["state"] == "stopped"
        finally:
            if relay is not None and relay.poll() is None:
                relay.terminate()
                relay.wait(timeout=10)
            if master is not None:
                os.close(master)
            record = read_server(home)
            if record and daemon is None:
                daemon = psutil.Process(record["pid"])
            if daemon is not None:
                try:
                    daemon.terminate()
                    daemon.wait(timeout=15)
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    daemon.kill()


@pytest.mark.platforms("posix")
@pytest.mark.live_system_guard_bypass  # Only the daemon created under this test's temp home.
@pytest.mark.parametrize("action", ["background", "cancel_task", "exit", "suspend", "close"])
def test_normal_launch_lifecycle_has_no_special_background_start(tmp_path, action):
    import fcntl
    import psutil
    import select
    import struct
    import termios
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
    home = tmp_path / ".sci"
    daemon = None
    client = None
    master = None
    viewers = []
    with FakeLLMServer([Text("COMPLETE_" + "x" * 60, chunk_chars=1, delay_per_chunk=0.08)]) as model:
        write_sci_home(home, model.base_url)
        env = {**os.environ, "SCI_HOME": str(home), "HOME": str(tmp_path), "PYTHONPATH": str(ROOT),
               "TERM": "xterm-256color", "SCI_STATE_DB_GUARD_BYPASS": "1"}
        master, slave = os.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 36, 110, 0, 0))
        output = bytearray()

        def until(needle):
            deadline = time.monotonic() + 35
            while needle not in output and time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
            assert needle in output, output[-3000:]

        def while_reading(predicate, timeout=30):
            # A PTY needs a reading terminal even while the test waits for a
            # lifecycle transition. Otherwise repaint output can fill its queue
            # and block the viewer before it reads Ctrl+] or Ctrl+Z (macOS CI).
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.05)[0]:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        pass  # PTY EOF may precede process exit notification.
                value = predicate()
                if value:
                    return value
            raise AssertionError(f"Timed out waiting for lifecycle transition: {output[-3000:]!r}")

        try:
            client = subprocess.Popen([sys.executable, "-m", "sci_cli.main", "--cli"], env=env,
                cwd=tmp_path, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            until("❯ ".encode())
            daemon = psutil.Process(read_server(home)["pid"])
            os.write(master, b"hello lifecycle fixture")
            until(b"hello lifecycle fixture")
            time.sleep(0.5)
            os.write(master, b"\r")
            while_reading(lambda: model.main_requests())
            worker = while_reading(lambda: next((c for c in request("status", home=home)["chats"] if c["session_id"]), None))
            key, session = worker["id"], worker["session_id"]
            if action in ("background", "cancel_task", "exit"):
                os.write(master, b"\x03")
                until(b"Task is still running")
                os.write(master, {"cancel_task": b"1", "background": b"2", "exit": b"3"}[action])
            elif action == "suspend":
                os.write(master, b"\x1a")
                while_reading(lambda: psutil.Process(client.pid).status() == psutil.STATUS_STOPPED)
                assert psutil.Process(worker["pid"]).status() != psutil.STATUS_STOPPED
            else:
                os.close(master)
                master = None
                client.wait(timeout=15)

            if action == "cancel_task":
                while_reading(lambda: find_worker(key, home)["state"] == "idle")
                assert client.poll() is None and find_worker(key, home)["attached"]
                assert len(model.main_requests()) == 1
                os.write(master, b"\x1d")
                while_reading(lambda: client.poll() is not None, timeout=15)
                assert client.returncode == 0
            elif action == "exit":
                while_reading(lambda: client.poll() is not None, timeout=20)
                assert client.returncode == 0
                wait_for(lambda: find_worker(key, home) is None)
                from sci_cli.active_sessions import active_session_registry_snapshot
                assert not active_session_registry_snapshot(home)
                assert len(model.main_requests()) == 1
            else:
                wait_for(lambda: not find_worker(key, home)["attached"])
                _resume_with_terminal(home, session, tmp_path)
                viewer = Viewer(home, key); viewers.append(viewer)
                viewer.until(b"COMPLETE_" + b"x" * 60)
                assert find_worker(key, home)["pid"] == worker["pid"]
                assert len(model.main_requests()) == 1
        finally:
            for viewer in viewers:
                viewer.close()
            if client is not None and client.poll() is None:
                client.kill()  # Also reaps a deliberately suspended client; never touches the user CLI.
                client.wait(timeout=10)
            if master is not None:
                os.close(master)
            record = read_server(home)
            if record and daemon is None:
                daemon = psutil.Process(record["pid"])
            if daemon:
                try:
                    daemon.terminate()
                    daemon.wait(timeout=15)
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    daemon.kill()
