"""Monitor results must return to their source chat, not the internal continuation."""

from pathlib import Path
from types import SimpleNamespace
import importlib
import queue

import pytest

from plugins.boltzmann import job_monitor as monitor
from plugins.boltzmann import job_notifications as notifications
from plugins.boltzmann.job_store import JobStore
from sci_cli.native_profile_creation import profile_scope
from sci_state import SessionDB
from tools.process_registry_notifications import format_process_notification


def test_origin_route_survives_stale_cron_context_and_continuation(monkeypatch):
    from gateway import session_context
    from plugins.boltzmann import job_continuation as continuation

    store = JobStore()
    with SessionDB(db_path=store.home / "state.db") as db:
        db.create_session("origin", "cli")
    current = {"SCI_SESSION_ID": "origin", "SCI_SESSION_KEY": "cron-stale"}
    monkeypatch.setattr(session_context, "get_session_env", lambda name: current.get(name, ""))
    monkeypatch.setattr(monitor, "ensure_worker", lambda _store: "running")
    monkeypatch.setattr(notifications, "watch", lambda _session: None)
    monkeypatch.setattr(continuation, "available", lambda: True)
    request = {"messages": [{"role": "system", "content": "cached prefix"}], "tools": []}
    continuation.checkpoint(session_id="origin", turn_id="fixture", user_message="Inspect fixture results",
                            request=request, available_tool_names=["boltzmann_status"], platform="cli")
    assert request == {"messages": [{"role": "system", "content": "cached prefix"}], "tools": []}
    row = monitor.observe("boltzmann_submit", {},
                          {"status": "accepted", "job_name": "fixture", "doc_id": "job-1"},
                          session_id="origin")
    assert row["notification_route"]["session_key"] == "origin"
    current.update(SCI_SESSION_ID="cron-child", SCI_SESSION_KEY="cron-child")
    row = monitor.observe("boltzmann_status", {},
                          {"status": "success", "job_terminal_confirmed": True,
                           "job_name": "fixture", "doc_id": "job-1"}, session_id="cron-child")
    assert row["notification_route"]["session_key"] == "origin"
    assert row["session_id"] == "origin"
    token = continuation._POLICY.set({"session_id": "origin", "checkpoint": row["checkpoint"],
                                      "notification_route": row["notification_route"],
                                      "accepted_fingerprints": set()})
    try:
        child = monitor.observe("boltzmann_submit", {},
                                {"status": "accepted", "job_name": "fixture-dependent", "doc_id": "job-2"},
                                session_id="cron-child")
        assert child["session_id"] == "origin"
        assert child["notification_route"] == row["notification_route"]
    finally:
        continuation._POLICY.reset(token)


def test_queued_report_recovers_until_owner_handles_it_without_reexecution(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from sci_cli.cli_process_notifications import CLIProcessNotificationsMixin
    from sci_cli.plugins import PluginManager
    from sci_cli.plugins_manifest import parse_manifest_file
    from tools.process_registry import ProcessRegistry

    class Consumer(CLIProcessNotificationsMixin):
        def __init__(self, session_id):
            self.session_id = session_id
            self._pending_input = queue.Queue()

        def _background_notifications_suppressed(self):
            return False

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    monkeypatch.setenv("SCI_HOME", str(a))
    scope = set_multiplex_context(True)
    queued = []
    try:
        with profile_scope(a):
            manager = PluginManager()
            plugin_dir = Path(monitor.__file__).parent
            manager._load_plugin(parse_manifest_file(plugin_dir / "plugin.yaml", plugin_dir, "bundled", ""))
            loaded = manager._plugins["boltzmann"]
            assert not loaded.error
            notifications = importlib.import_module(loaded.module.__name__ + ".job_notifications")
            registry = ProcessRegistry()
            monkeypatch.setattr("tools.process_registry.process_registry", registry)
            with SessionDB(db_path=a / "state.db") as db:
                db.create_session("origin", "cli")
                db.append_message("origin", "user", "Fixture task")
                db.append_message("origin", "assistant", "Monitoring in background")
                before = db.get_messages("origin")
            store = JobStore()
            row = store.track("fixture", "job-1", session_id="origin")
            row = store.update(row["id"], state="success", continuation="reported", notice_queued=True,
                               notification_route={"session_key": "cron-wrong"},
                               continuation_result={"ok": True, "response": "Saved artifact verified"})
            def broken_queue(_event):
                raise OSError("fixture queue unavailable")

            with pytest.raises(OSError):
                notifications.deliver_ready(store, row, broken_queue)
            assert store.get(row["id"])["notification_error"]
            assert notifications.deliver_ready(store, row, queued.append)
            event = queued[-1]
            assert event["session_key"] == "origin"
            assert CLIProcessNotificationsMixin._owns_process_notification(SimpleNamespace(session_id="origin"), event)
            assert not CLIProcessNotificationsMixin._owns_process_notification(SimpleNamespace(session_id="other"), event)
            registry.completion_queue.put(event)
            foreign, owner = Consumer("other"), Consumer("origin")
            foreign._drain_process_notifications("fixture")
            assert foreign._pending_input.empty()
            owner._drain_process_notifications("fixture")
            assert owner._pending_input.get_nowait() == format_process_notification(event)
            assert not store.get(row["id"]).get("notice_delivered")
            assert not notifications.deliver_ready(store, store.get(row["id"]), queued.append)
            # Simulate a lost queue and restarted process after its delivery lease expires.
            with store.connect() as conn:
                conn.execute("DELETE FROM leases")
            monkeypatch.setattr(notifications, "_DELIVERY_OWNER", "restarted-process")
            assert notifications.deliver_ready(store, store.get(row["id"]), queued.append)
            assert queued[-1]["session_id"] == event["session_id"]
        with profile_scope(b):
            manager.invoke_hook("post_llm_call", session_id="origin", user_message=format_process_notification(event),
                                      assistant_response="Saved artifact verified")
            assert JobStore().list() == []
        with profile_scope(a):
            manager.invoke_hook("post_llm_call", session_id="other", user_message=format_process_notification(event),
                                      assistant_response="Saved artifact verified")
            assert not store.get(row["id"]).get("notice_delivered")
            manager.invoke_hook("post_llm_call", session_id="origin", user_message=format_process_notification(event),
                                      assistant_response="Saved artifact verified")
            # Foreground-only registration never acknowledges or starts legacy
            # notification work. Existing workers retain their explicit handler.
            assert not store.get(row["id"])["notice_delivered"]
            notifications.acknowledge(session_id="origin", user_message=format_process_notification(event),
                                      assistant_response="Saved artifact verified")
            assert store.get(row["id"])["notice_delivered"]
            assert not notifications.deliver_ready(store, store.get(row["id"]), queued.append)
            with SessionDB(db_path=a / "state.db") as db:
                assert db.get_messages("origin") == before
            assert store.get(row["id"])["continuation_result"]["response"] == "Saved artifact verified"
            # A second job's reply was persisted, but the process died before its hook.
            second = store.track("fixture-second", "job-2", session_id="origin")
            second = store.update(second["id"], state="success", continuation="reported",
                                  continuation_result={"ok": True, "response": "Second artifact verified"})
            assert notifications.deliver_ready(store, second, queued.append)
            with SessionDB(db_path=a / "state.db") as db:
                db.create_session("resumed", "cli", parent_session_id="origin")
                db.append_message("resumed", "user", format_process_notification(queued[-1]))
                db.append_message("resumed", "assistant", "Second artifact verified")
            from plugins.boltzmann.job_routes import owns_session
            assert owns_session(store, second, "resumed")
            with store.connect() as conn:
                conn.execute("DELETE FROM leases")
            monkeypatch.setattr(notifications, "_DELIVERY_OWNER", "another-process")
            count = len(queued)
            assert not notifications.deliver_ready(store, store.get(second["id"]), queued.append)
            assert len(queued) == count
            assert store.get(second["id"])["notice_delivered"]
    finally:
        reset_multiplex_context(scope)
