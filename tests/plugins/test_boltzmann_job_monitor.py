"""Issue #35: queued jobs, durable monitoring and non-replaying continuations."""

import copy
import json
from pathlib import Path
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from plugins.boltzmann import job_continuation as continuation
from plugins.boltzmann import job_monitor as monitor
from plugins.boltzmann import job_store
from plugins.boltzmann import nodeapi_helpers as helpers


@pytest.mark.parametrize("responses,expected,timeout,calls", [
    ([(404, {"status": "pending", "message": "job is pending"}),
      (404, {"status": "running", "info": {"queue": "active"}}),
      (200, {"status": "Success"})], "success", False, 3),
    ([(404, {"status": "pending", "message": "job is pending"})], "pending", True, 3),
    ([(200, {"status": "pending"}), (200, {"status": "success"})], "success", False, 2),
    ([(404, {"status": "failed", "message": "worker rejected input"})], "failed", False, 1),
    ([(200, {"status": "cancelled"})], "cancelled", False, 1),
    ([(404, {"status": "canceled", "message": "job canceled", "doc_id": "fixture", "job_name": "Boltz2"})], "canceled", False, 1),
    ([(404, {"status": "pending"})], "unknown", False, 1),
    ([(404, {"detail": "Not Found"})], "unknown", False, 1),
    ([(404, {"status": "unexpected", "message": "missing route"})], "unknown", False, 1),
    ([(404, [])], "unknown", False, 1),
    ([(200, {"status": []})], "unknown", False, 1),
    ([(200, {"status": "running", "docId": "another-job"})], "unknown", False, 1),
    ([(401, {"status": "pending", "message": "expired key"})], "unknown", False, 1),
    ([(403, {"message": "forbidden"})], "unknown", False, 1),
    ([(404, {"status": "deleted", "message": "removed", "doc_id": "fixture", "job_name": "Boltz2"})],
     "deleted", False, 1),
    ([(404, {"status": "not_found", "message": "missing job"})], "unknown", False, 1),
])
def test_status_classification_and_deadlines_never_submit_or_cancel(monkeypatch, responses, expected, timeout, calls):
    clock, seen, pauses = [0.0], [], []

    def get(url, **kwargs):
        assert url == helpers._FETCH_URL
        assert kwargs["json"] == {"docId": "fixture", "job_name": "Boltz2"}
        code, body = responses[min(len(seen), len(responses) - 1)]
        seen.append(kwargs)
        return SimpleNamespace(status_code=code, json=lambda: body)

    def sleep(seconds):
        pauses.append(seconds)
        clock[0] += seconds

    def forbidden(*args, **kwargs):
        raise AssertionError("Status checks must never submit, cancel or top up work")

    monkeypatch.setattr(helpers.requests, "get", get)
    monkeypatch.setattr(helpers.requests, "post", forbidden)
    monkeypatch.setattr(helpers.requests, "delete", forbidden)
    monkeypatch.setattr(helpers, "_log_platform_terminal", lambda *args: None)
    monkeypatch.setattr(helpers, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep))
    result = helpers.fetch_status("Boltz2", "fixture", token="fixture-key", watch_time=1, max_wait=3)
    assert result["status"].lower() == expected
    assert bool(result.get("timeout")) == timeout
    assert len(seen) == calls
    if expected == "pending":
        assert "error" not in result and len(pauses) == 3
        assert "Polling window ended" in result["polling_message"]
    if seen[-1]["json"] == {"docId": "fixture", "job_name": "Boltz2"} and expected == "unknown":
        assert result.get("error")


def test_single_checks_and_monitor_survive_days_restart_and_profile_switches(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from sci_cli.native_profile_creation import profile_scope

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    monkeypatch.setenv("SCI_HOME", str(a))
    clock = [1000.0]
    monkeypatch.setattr(job_store, "time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(monitor, "time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(monitor, "require_authorized", lambda: "fixture-key")
    results = iter([
        {"status": "pending", "message": "queued"},
        {"status": "unknown", "error": "connection unavailable"},
        {"status": "running"},
        {"status": "success", "job_terminal_confirmed": True, "job_name": "Boltz2", "doc_id": "fixture"},
    ])
    seen = []

    def fetch(job, doc_id, **kwargs):
        assert kwargs["poll_once"] is True and kwargs["max_wait"] == 30
        seen.append((job, doc_id))
        return next(results)

    monkeypatch.setattr(monitor, "fetch_status", fetch)
    token = set_multiplex_context(True)
    try:
        with profile_scope(a):
            row = job_store.JobStore().track("Boltz2", "fixture")
            assert job_store.JobStore().acquire("worker", "old-process")
            assert not job_store.JobStore().acquire("worker", "second-process")
            clock[0] += 121  # A dead process lease expires; records survive.
            assert job_store.JobStore().acquire("worker", "restarted-process")
            for expected in ("pending", "unknown", "running", "success"):
                clock[0] += 24 * 60 * 60
                store = job_store.JobStore()  # Reopen from disk on each observation.
                row = monitor.check(store, store.get(row["id"]))
                assert row["state"] == expected
            assert row["checks"] == 4
        with profile_scope(b):
            assert job_store.JobStore().list() == []
            assert job_store.JobStore().get(row["id"]) is None
        with profile_scope(a):
            assert job_store.JobStore().get(row["id"])["state"] == "success"
            monitor.check(job_store.JobStore(), row)
            assert seen == [("Boltz2", "fixture")] * 4
    finally:
        reset_multiplex_context(token)


def test_monitor_stop_auth_recovery_and_capacity_preserve_remote_job(monkeypatch):
    store = job_store.JobStore()
    row = store.track("Boltz2", "fixture")

    def unauthorized():
        raise PermissionError("fixture auth revoked")

    monkeypatch.setattr(monitor, "require_authorized", unauthorized)
    paused = monitor.check(store, row)
    assert paused["state"] == "paused_auth" and paused["doc_id"] == "fixture"
    monkeypatch.setattr(monitor, "require_authorized", lambda: "fixture-key")

    def completed(*args, **kwargs):
        store.update(row["id"], stopped=True)
        return {"status": "success", "job_terminal_confirmed": True}

    monkeypatch.setattr(monitor, "fetch_status", completed)
    stopped = monitor.check(store, store.update(row["id"], next_check=0))
    assert stopped["stopped"] and stopped["state"] == "paused_auth"
    before = store.get(row["id"])
    monkeypatch.setattr(job_store, "MAX_RECORD_BYTES", 1)
    with pytest.raises(ValueError, match="capacity"):
        store.update(row["id"], stopped=False)
    assert store.get(row["id"]) == before  # Transaction rollback, not a partly updated record.


def test_idle_worker_handoff_cannot_leave_new_jobs_with_a_stale_owner():
    store = job_store.JobStore()
    assert store.acquire("worker", "old")
    row = store.track("Boltz2", "first")
    assert not store.finish_if_idle("old")
    store.update(row["id"], state="success")
    store.update(row["id"], checkpoint="checkpoint:fixture")
    assert not store.finish_if_idle("old")  # A just-attached continuation is work too.
    store.update(row["id"], continuation="reported")
    assert store.finish_if_idle("old")
    assert not store.worker_health()
    new = store.track("Boltz2", "second")
    assert store.acquire("worker", "new")
    store.release("worker", "old")  # Late teardown must not clear a replacement owner.
    assert store.worker_health() and not store.finish_if_idle("new")
    assert store.get(new["id"])["state"] == "accepted"


def test_checkpoint_continuation_is_frozen_permission_limited_and_not_replayed(monkeypatch):
    monkeypatch.setattr(continuation, "available", lambda: True)
    monkeypatch.setattr(continuation, "current_key", lambda: "fixture-secret")
    monkeypatch.setattr(monitor, "ensure_worker", lambda store: "running")
    request = {"tools": [{"function": {"name": "boltzmann_status"}}]}
    history = [{"role": "user", "content": "fixture-secret"}]
    original = copy.deepcopy((request, history))
    continuation.checkpoint(session_id="source", turn_id="turn", user_message="Inspect the existing results",
                            conversation_history=history, request=request, model="fixture-model", provider="fixture-provider")
    accepted = {"status": "accepted", "doc_id": "fixture", "job_name": "Boltz2"}
    inputs = {"input_path": "fixture/authorized.csv"}
    row = monitor.observe("boltzmann_submit", {"experiment_data": inputs}, accepted, session_id="source")
    source = row["checkpoint"]
    saved = job_store.JobStore().get(source)
    assert "fixture-secret" not in json.dumps(saved)
    assert (request, history) == original
    continuation.checkpoint(session_id="source", turn_id="new-turn", user_message="A different task",
                            request=request)
    assert job_store.JobStore().get(source) == saved
    calls = []

    def runner(data, rows):
        calls.append(rows)
        assert data["user_request"] == "Inspect the existing results"
        assert continuation.guard("boltzmann_status") is None
        assert continuation.guard("terminal")["action"] == "block"
        assert continuation.replay_error("Boltz2", inputs)["status"] == "not_started"
        assert continuation.replay_error("Boltz2", {"input_path": "fixture/other.csv"}) is None
        return {"ok": True, "response": "Fixture results verified"}

    store = job_store.JobStore()
    continuation.continue_ready(store, runner)
    assert not calls
    store.update(row["id"], state="success", last_result={"status": "success"})
    continuation.continue_ready(store, runner)
    continuation.continue_ready(job_store.JobStore(), runner)
    assert len(calls) == 1
    assert store.get(row["id"])["continuation"] == "reported"
    assert continuation.guard("terminal") is None  # Original conversation's policy is unchanged.


def test_continuation_uses_existing_cron_execution_without_scheduling_a_second_copy(monkeypatch):
    from cron import scheduler
    from cron.jobs import get_job

    seen = []

    def run(job):
        seen.append(job)
        assert not job["enabled"] and job["deliver"] == "local"
        assert "Never" in job["prompt"] or "NEVER" in job["prompt"]
        return True, "Fixture report", "Fixture verified output", None

    monkeypatch.setattr(scheduler, "run_job", run)
    result = continuation._run({"user_request": "Finish approved analysis", "history": []}, [
        {"job_name": "Boltz2", "doc_id": "accepted-fixture", "state": "success"}])
    assert result["ok"] and len(seen) == 1
    assert get_job(result["cron_job_id"])["enabled"] is False


@pytest.mark.parametrize("reason", ["ambiguous", "interrupted", "specialist"])
def test_unresolved_submissions_and_interrupted_continuations_are_never_replayed(monkeypatch, reason):
    monkeypatch.setattr(continuation, "available", lambda: True)
    monkeypatch.setattr(monitor, "ensure_worker", lambda store: "running")
    monkeypatch.setattr("agent.specialist_policy.current_policy", lambda: object() if reason == "specialist" else None)
    continuation.checkpoint(session_id="source", turn_id="turn", user_message="Finish approved work",
                            request={"body": {"tools": [{"function": {"name": "tool_call"}}]}},
                            available_tool_names=["boltzmann_submit", "boltzmann_status"])
    store = job_store.JobStore()
    row = monitor.observe("boltzmann_submit", {},
                          {"status": "accepted", "job_name": "Boltz2", "doc_id": "fixture"}, session_id="source")
    source = row["checkpoint"]
    assert store.get(source)["allowed_tools"] == ["boltzmann_status", "boltzmann_submit"]
    store.update(row["id"], state="success")
    if reason == "interrupted":
        saved = store.get(source)
        with store.connect() as conn:
            store._save(conn, source, {**saved, "continuation": "running", "handled": [row["id"]]})
    elif reason == "ambiguous":
        monitor.observe("boltzmann_submit", {}, {"status": "unknown", "stage": "submit"}, session_id="source")

    def forbidden(*args):
        raise AssertionError("Unresolved execution must not be replayed")

    continuation.continue_ready(store, forbidden)
    outcome = store.get(row["id"])["continuation"]
    assert {"ambiguous": "reconcile", "interrupted": "interrupted", "specialist": "specialist"}[reason] in outcome


def test_real_worker_process_uses_saved_profile_key_and_only_local_status_gets(tmp_path, monkeypatch):
    from plugins.boltzmann.auth import authorize_saved_key
    from sci_cli.config import save_env_value
    from sci_cli import _launchers

    monkeypatch.setenv("SCI_HOME", str(tmp_path / "profile"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_DISABLE_LAZY_INSTALLS", "1")
    monkeypatch.setenv("SCI_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("conv_id", "unrelated-launch-conversation")
    monkeypatch.setenv("output_folder", str(tmp_path / "unrelated-launch-output"))
    monkeypatch.setattr(_launchers, "resolve_store_python", lambda root: Path(sys.executable))
    save_env_value("BOLTZMANN_API_KEY", "fixture-valid")
    authorize_saved_key()
    calls = []
    first_status = threading.Event()
    children = []
    real_popen = monitor.subprocess.Popen

    def launch(*args, **kwargs):
        assert Path(kwargs["env"]["SCI_HOME"]) == tmp_path / "profile"
        assert "conv_id" not in kwargs["env"] and "output_folder" not in kwargs["env"]
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(monitor.subprocess, "Popen", launch)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            assert self.headers["Authorization"] == "Bearer fixture-valid"
            pending = calls.count("/result") == 1
            body = ({"status": "pending" if pending else "success", "message": "fixture job"}
                    if self.path == "/result" else {"status": "success"})
            self.send_response(404 if self.path == "/result" and pending else 200)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())
            if self.path == "/result":
                first_status.set()

        def do_POST(self):
            raise AssertionError("Monitoring must not submit or cancel")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        store = job_store.JobStore()
        row = store.track("Boltz2", "fixture")
        endpoint = f"http://127.0.0.1:{server.server_port}"
        # A genuine installed plugin override: exercise CLI discovery and the real
        # installation-bound launcher, not a helper-only substitute process.
        plugin = tmp_path / "profile/plugins/boltzmann"
        shutil.copytree(Path(helpers.__file__).parent, plugin, ignore=shutil.ignore_patterns("__pycache__"))
        helper = plugin / "nodeapi_helpers.py"
        content = helper.read_text(encoding="utf-8-sig")
        content = content.replace(helpers._FETCH_URL, endpoint + "/result").replace(helpers._AUTH_CHECK_URL, endpoint + "/auth")
        helper.write_text(content, encoding="utf-8")
        assert monitor.ensure_worker(store) in {"running", "starting; startup not yet confirmed"}
        assert first_status.wait(20)
        deadline = time.monotonic() + 20
        while store.get(row["id"])["state"] == "accepted" and time.monotonic() < deadline:
            time.sleep(0.05)
        assert store.get(row["id"])["state"] == "pending"
        store.update(row["id"], next_check=0)
        children[0].wait(timeout=20)
        assert children[0].returncode == 0
        restored = job_store.JobStore().get(row["id"])
        assert restored["state"] == "success" and restored["checks"] == 2
        assert calls == ["/auth", "/result", "/auth", "/result"]
        assert not store.worker_health()
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.platforms("posix")
def test_monitor_database_is_private_and_symlinked_storage_is_rejected(tmp_path):
    store = job_store.JobStore()
    store.track("Boltz2", "fixture")
    assert store.root.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600
    outside = tmp_path / "unrelated.sqlite3"
    store.path.rename(outside)
    store.path.symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic"):
        store.list()


def test_live_outcomes_use_existing_notification_routing_without_cross_session_delivery():
    from plugins.boltzmann.job_notifications import deliver_ready
    from sci_cli.cli_process_notifications import CLIProcessNotificationsMixin
    from tools.process_registry_notifications import format_process_notification

    store = job_store.JobStore()
    row = store.track("Boltz2", "fixture", session_id="source")
    row = store.update(row["id"], state="paused_auth", notification_route={"session_key": "source"},
                       last_result={"error": "Restore the profile key. The remote job is unchanged."})
    queued = []
    assert deliver_ready(store, row, queued.append)
    assert not deliver_ready(store, store.get(row["id"]), queued.append)
    row = store.update(row["id"], state="success", continuation="reported", alert_queued=False,
                       continuation_result={"response": "Fixture artifacts verified"})
    assert deliver_ready(store, row, queued.append)
    assert queued[0]["session_id"] != queued[1]["session_id"]
    assert "Fixture artifacts verified" in format_process_notification(queued[-1])
    owner = SimpleNamespace(session_id="source")
    other = SimpleNamespace(session_id="other")
    assert CLIProcessNotificationsMixin._owns_process_notification(owner, queued[-1])
    assert not CLIProcessNotificationsMixin._owns_process_notification(other, queued[-1])
