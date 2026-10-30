"""Real daemon + PTY fixture workers: no production services or inference calls."""

import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from sci_cli.background_chats import connect, find_worker, locations, read_server, request, send

ROOT = Path(__file__).resolve().parents[2]
WORKER = r'''
import os, signal, sys, time
from pathlib import Path
from sci_cli.active_sessions import try_acquire_active_session
from sci_cli.background_chats import request
from sci_state import SessionDB
home = Path(os.environ['SCI_HOME'])
db = SessionDB(home / 'state.db')
db.create_session('fixture', 'cli', system_prompt='cached-' + home.name)
lease, error = try_acquire_active_session(session_id='fixture', surface='cli', config={})
assert lease and not error
def state(value):
    request('worker', pid=os.getpid(), session_id='fixture', state=value, background_tasks=0)
def close(signum, frame):
    lease.release()
    db.close()
    raise SystemExit(0)
signal.signal(signal.SIGTERM, close)
state('idle')
print('READY', flush=True)
for line in sys.stdin:
    text = line.strip()
    state('running')
    db.append_message('fixture', 'user', text)
    print('STARTED:' + text, flush=True)
    if text == 'approval':
        state('waiting for input')
        print('APPROVE?', flush=True)
        answer = sys.stdin.readline().strip()
        output = 'approved' if answer == 'yes' else 'cancelled'
    else:
        time.sleep(0.6)
        output = 'completed:' + text
    db.append_message('fixture', 'assistant', output)
    state('idle')
    print(output, flush=True)
'''


def wait_for(predicate, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for fixture state")


def service(home, *, real_cli=False, worker_source=WORKER):
    home.mkdir(parents=True, exist_ok=True)
    code = f'''
import asyncio, os, sys
from pathlib import Path
from sci_cli.background_chat_service import ChatService
from sci_cli.pty_bridge import PtyBridge
from tools.environments.local import served_profile_child_env
home = Path({str(home)!r})
def spawn(session_id, cwd, cols, rows, terminal_env=None):
    env = served_profile_child_env(target_home=home, inherit_credentials=True)
    env['PYTHONPATH'] = {str(ROOT)!r}
    env.update(terminal_env or {{}})
    return PtyBridge.spawn([sys.executable, '-u', '-c', {worker_source!r}], cwd=cwd, env=env, cols=cols, rows=rows)
asyncio.run(ChatService(home, worker_factory={"None" if real_cli else "spawn"}).run())
'''
    p = subprocess.Popen([sys.executable, "-u", "-c", code], cwd=ROOT,
        env={**os.environ, "SCI_HOME": str(home), "HOME": str(home.parent), "TERM": "xterm-256color",
             "SCI_STATE_DB_GUARD_BYPASS": "1"}, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        wait_for(lambda: read_server(home) or (p.poll() is not None and (_ for _ in ()).throw(AssertionError(p.communicate()))))
    except BaseException:
        p.kill()
        p.communicate(timeout=10)
        raise
    return p


@pytest.mark.platforms("posix")
def test_service_reconnects_across_long_and_changed_tmpdirs_without_profile_crossover(tmp_path, monkeypatch):
    import tempfile

    long_temp = tmp_path / ("long-temp-" * 14)
    long_temp.mkdir()
    monkeypatch.setenv("TMPDIR", str(long_temp))
    monkeypatch.setattr(tempfile, "tempdir", str(long_temp))
    homes = [tmp_path / "a", tmp_path / "b"]
    daemons = []
    endpoints = []
    try:
        for home in homes:
            daemons.append(service(home))
            endpoints.append(locations(home)[2])
        assert endpoints[0] != endpoints[1]
        assert all(len(os.fsencode(path)) <= 100 for path in endpoints)
        changed_temp = tmp_path / "other-temp"
        changed_temp.mkdir()
        monkeypatch.setenv("TMPDIR", str(changed_temp))
        monkeypatch.setattr(tempfile, "tempdir", str(changed_temp))
        for index in (0, 1, 0):
            result = request("status", home=homes[index])
            assert result["profile_home"] == str(homes[index].resolve())
            assert result["pid"] == daemons[index].pid
    finally:
        for daemon in daemons:
            daemon.terminate()
            daemon.wait(timeout=15)
    assert not any(path.exists() for path in endpoints)


@pytest.mark.platforms("posix")
def test_start_is_not_capped_by_retained_workers_and_keeps_profile_owners(tmp_path):
    homes = [tmp_path / "a", tmp_path / "b"]
    source = "import time; print('READY', flush=True); time.sleep(300)"
    daemons = [service(home, worker_source=source) for home in homes]
    try:
        owners = []
        # Past the former eight-worker limit, new chats must neither fail nor
        # evict existing idle/running/waiting conversations to make room.
        for index in range(9):
            chat = request("start", home=homes[0], cwd=str(tmp_path))
            row = find_worker(chat["id"], homes[0])
            request("worker", home=homes[0], pid=row["pid"], session_id=f"saved-{index}",
                    state=("idle", "running", "waiting for input")[index % 3])
            owners.append((chat["id"], row["pid"]))
        other = request("start", home=homes[1], cwd=str(tmp_path))
        other_pid = find_worker(other["id"], homes[1])["pid"]
        resumed = request("start", home=homes[0], session_id="saved-0", cwd=str(tmp_path))
        assert resumed == {"id": owners[0][0], "existing": True}
        current = request("status", home=homes[0])["chats"]
        assert {(row["id"], row["pid"]) for row in current if row["alive"]} == set(owners)
        assert find_worker(other["id"], homes[1])["pid"] == other_pid
        assert find_worker(other["id"], homes[0]) is None
    finally:
        for daemon in daemons:
            daemon.terminate()
            try:
                daemon.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.communicate(timeout=10)


class Viewer:
    def __init__(self, home, key, takeover=False):
        self.sock = connect(home)
        self.sock.settimeout(30)
        send(self.sock, {"action": "attach", "id": key, "takeover": takeover})
        self.stream = self.sock.makefile("rb")
        self.reply = self.read()
        self.output = b""

    def read(self):
        return json.loads(self.stream.readline())

    def until(self, text):
        end = time.monotonic() + 20
        while text not in self.output and time.monotonic() < end:
            try:
                item = self.read()
            except TimeoutError:
                raise AssertionError(f"No fixture output: {self.output[-3000:]!r}") from None
            assert "error" not in item, item
            if "output" in item:
                self.output += base64.b64decode(item["output"])
            if "closed" in item:
                break
        assert text in self.output, self.output[-2000:]

    def type(self, text):
        send(self.sock, {"action": "input", "data": base64.b64encode(text.encode()).decode()})

    def close(self):
        self.stream.close()
        self.sock.close()


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("task", ["work", "approval"])
def test_live_work_survives_viewer_loss_and_reconnects_without_replay(tmp_path, task):
    from sci_state import SessionDB
    homes = [tmp_path / "a", tmp_path / "b"]
    services = [service(h) for h in homes]
    viewers = []
    try:
        keys = [request("start", home=h, cwd=str(h))["id"] for h in homes]
        first = Viewer(homes[0], keys[0]); viewers.append(first)
        first.until(b"READY")
        owner = find_worker("fixture", homes[0])
        first.type(task + "\n")
        first.until(b"STARTED:")
        first.close(); viewers.remove(first)  # Abrupt disconnect, not an orderly /exit.
        wait_for(lambda: not request("status", home=homes[0])["chats"][0]["attached"])
        if task == "approval":
            wait_for(lambda: find_worker("fixture", homes[0])["state"] == "waiting for input")
        else:
            wait_for(lambda: find_worker("fixture", homes[0])["state"] == "idle")
        # A -> B -> A; no new worker, conversation or model request on reattach.
        second = Viewer(homes[1], keys[1]); viewers.append(second)
        second.until(b"READY")
        again = Viewer(homes[0], keys[0]); viewers.append(again)
        again.until(b"APPROVE?" if task == "approval" else b"completed:work")
        if task == "approval":
            again.type("yes\n")
            again.until(b"approved")
        assert find_worker("fixture", homes[0])["pid"] == owner["pid"]
        duplicate = request("start", home=homes[0], session_id="fixture", cwd=str(homes[0]))
        assert duplicate == {"id": keys[0], "existing": True}
        rejected = Viewer(homes[0], keys[0]); viewers.append(rejected)
        assert "error" in rejected.reply
        moved = Viewer(homes[0], keys[0], takeover=True); viewers.append(moved)
        moved.until(b"READY")
        wait_for(lambda: find_worker("fixture", homes[0])["state"] == "idle")
        with SessionDB(homes[0] / "state.db", read_only=True) as db:
            assert db.get_session("fixture")["system_prompt"] == "cached-a"
            assert [m["content"] for m in db.get_messages("fixture")] == [task, "approved" if task == "approval" else "completed:work"]
        with SessionDB(homes[1] / "state.db", read_only=True) as db:
            assert db.get_messages("fixture") == []
        assert request("stop", home=homes[0], id=keys[0])["state"] == "stopped"
        assert find_worker("fixture", homes[1])["alive"]
    finally:
        for viewer in viewers:
            viewer.close()
        for p in services:
            p.terminate()
            p.communicate(timeout=20)


@pytest.mark.platforms("posix")
def test_service_auth_scope_controls_and_crash_do_not_restart_work(tmp_path):
    import psutil
    from sci_cli.active_sessions import active_session_registry_snapshot
    p = service(tmp_path)
    try:
        home, root, endpoint = locations(tmp_path)
        assert root.stat().st_mode & 0o077 == 0
        assert (root / "server.json").stat().st_mode & 0o077 == 0
        for token, profile in [("wrong", str(home)), (read_server(home)["token"], str(home / "other"))]:
            with socket.socket(socket.AF_UNIX) as s:
                s.settimeout(5)
                s.connect(str(endpoint))
                send(s, {"token": token, "home": profile})
                assert "authentication failed" in s.recv(65536).decode()
        key = request("start", home=home, cwd=str(home))["id"]
        viewer = Viewer(home, key)
        viewer.until(b"READY")
        viewer.close()
        with pytest.raises(RuntimeError, match="Stop the profile"):
            request("shutdown", home=home)
        with pytest.raises(RuntimeError, match="No matching"):
            request("stop", home=home, id="someone-elses-chat")
        worker = find_worker("fixture", home)
        p.kill()  # No durable queue replays the previous request after service failure.
        p.communicate(timeout=10)
        wait_for(lambda: not psutil.pid_exists(worker["pid"]) or psutil.Process(worker["pid"]).status() == psutil.STATUS_ZOMBIE)
        assert read_server(home) is None
        assert active_session_registry_snapshot(home) == []
        assert (home / "state.db").is_file()
    finally:
        if p.poll() is None:
            p.terminate()
        p.communicate(timeout=20)


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("detach_method", ["disconnect", "ctrl_c", "slash"])
def test_real_cli_disconnect_resume_keeps_one_request_and_cached_prompt(tmp_path, detach_method):
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
    from sci_state import SessionDB
    home = tmp_path / ".sci"
    viewers = []
    with FakeLLMServer([Text("BACKGROUND_DONE", chunk_chars=1, delay_per_chunk=0.1), Text("SECOND_DONE")]) as model:
        write_sci_home(home, model.base_url, extra_config="session:\n  background_idle_timeout: 0\n")
        process = service(home, real_cli=True)
        try:
            key = request("start", home=home, cwd=str(tmp_path))["id"]
            viewer = Viewer(home, key); viewers.append(viewer)
            viewer.until("❯ ".encode())
            viewer.type("hello background fixture")
            viewer.until(b"hello background fixture")
            time.sleep(0.5)  # Match the CLI's paste-vs-Enter input pacing.
            viewer.type("\r")
            try:
                wait_for(lambda: model.main_requests(), seconds=15)
            except AssertionError:
                viewer.until(b"BACKGROUND_DONE")
                raise
            worker = wait_for(lambda: next((c for c in request("status", home=home)["chats"] if c["session_id"]), None))
            if detach_method == "ctrl_c":
                viewer.type("\x03")
                viewer.until(b"Task is still running")
                viewer.type("2")
            elif detach_method == "slash":
                viewer.type("/background")
                viewer.until(b"/background")
                time.sleep(0.5)
                viewer.type("\r")
            else:
                viewer.close(); viewers.remove(viewer)
            wait_for(lambda: not find_worker(key, home)["attached"])
            _resume_with_terminal(home, worker["session_id"], tmp_path)
            resumed = Viewer(home, worker["session_id"]); viewers.append(resumed)
            resumed.until(b"BACKGROUND_DONE")
            assert len(model.main_requests()) == 1
            assert find_worker(key, home)["pid"] == worker["pid"]
            resumed.type("hello second fixture")
            resumed.until(b"hello second fixture")
            time.sleep(0.5)
            resumed.type("\r")
            resumed.until(b"SECOND_DONE")
            requests = model.main_requests()
            assert len(requests) == 2
            assert [m for m in requests[0]["messages"] if m["role"] == "system"] == [m for m in requests[1]["messages"] if m["role"] == "system"]
            assert requests[0]["tools"] == requests[1]["tools"]
            request("stop", home=home, id=key)
            with SessionDB(home / "state.db", read_only=True) as db:
                messages = db.get_messages(worker["session_id"])
                assert sum(m.get("content") == "hello background fixture" for m in messages) == 1
                assert any(m.get("content") == "SECOND_DONE" for m in messages)
        finally:
            for viewer in viewers:
                viewer.close()
            process.terminate()
            process.communicate(timeout=20)


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


def _resume_with_terminal(home, session_id, cwd, *, visit=None):
    """The ordinary CLI resume entry must attach without stopping the live writer."""
    import fcntl
    import select
    import struct
    import termios
    master, slave = os.openpty()
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    env = {**os.environ, "HOME": str(home.parent), "SCI_HOME": str(home),
           "PYTHONPATH": str(ROOT), "TERM": "xterm-256color", "SCI_STATE_DB_GUARD_BYPASS": "1"}
    process = subprocess.Popen([sys.executable, "-m", "sci_cli.main", "--cli", "--resume", session_id],
        env=env, cwd=cwd, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = b""
    try:
        deadline = time.monotonic() + 30
        while b"\x1b[3J" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        assert b"\x1b[3J" in output, output[-3000:]
        assert b"This chat is open in another" not in output
        if visit:
            for target in (visit, session_id):
                command = f"/resume {target}".encode()
                output = b""
                os.write(master, command)
                deadline = time.monotonic() + 30
                while command not in output and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 65536)
                assert command in output, output[-3000:]
                time.sleep(0.5)
                os.write(master, b"\r")
                deadline = time.monotonic() + 30
                while not find_worker(target, home)["attached"] and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        try:
                            output += os.read(master, 65536)
                        except OSError:
                            break
                import re
                plain = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", output)
                assert find_worker(target, home)["attached"], plain[-12000:].decode(errors="replace")
        os.write(master, b"\x1d")
        # A real terminal consumes replay while waiting; a PTY's small output
        # queue otherwise blocks its writer and creates an artificial deadlock.
        deadline = time.monotonic() + 15
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        assert process.wait(timeout=5) == 0, output[-3000:]
        wait_for(lambda: not find_worker(session_id, home)["attached"])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        os.close(master)


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


@pytest.mark.platforms("posix")
def test_slash_resume_moves_the_viewer_between_live_conversations(tmp_path):
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
    home = tmp_path / ".sci"
    viewers = []
    with FakeLLMServer([Text("FIRST_COMPLETE"), Text("SECOND_COMPLETE")]) as model:
        write_sci_home(home, model.base_url)
        daemon = service(home, real_cli=True)
        try:
            owners = []
            for name in ("FIRST", "SECOND"):
                key = request("start", home=home, cwd=str(tmp_path))["id"]
                viewer = Viewer(home, key); viewers.append(viewer)
                viewer.until("❯ ".encode())
                viewer.type("hello " + name)
                viewer.until(("hello " + name).encode())
                time.sleep(0.5)
                viewer.type("\r")
                viewer.until((name + "_COMPLETE").encode())
                owner = wait_for(lambda: next((c for c in request("status", home=home)["chats"]
                    if c["id"] == key and c["session_id"] and c["state"] == "idle"), None))
                owners.append(owner)
                viewer.close(); viewers.remove(viewer)
                wait_for(lambda: not find_worker(key, home)["attached"])
            _resume_with_terminal(home, owners[0]["session_id"], tmp_path, visit=owners[1]["session_id"])
            assert len(model.main_requests()) == 2
            for owner in owners:
                assert find_worker(owner["id"], home)["pid"] == owner["pid"]
        finally:
            for viewer in viewers:
                viewer.close()
            daemon.terminate()
            daemon.communicate(timeout=20)
