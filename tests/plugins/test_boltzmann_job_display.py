"""Retained legacy jobs never reappear in the foreground-only chat dock."""

import importlib
from pathlib import Path
from types import SimpleNamespace

from agent.secret_scope import reset_multiplex_context, set_multiplex_context
from sci_cli.cli_subagent_monitor import install_dock
from sci_cli.native_profile_creation import profile_scope
from sci_cli.plugins import get_plugin_manager
from sci_cli.plugins_manifest import parse_manifest_file


def load_monitor():
    manager = get_plugin_manager()
    root = Path(__file__).resolve().parents[2] / "plugins/boltzmann"
    manager._load_plugin(parse_manifest_file(root / "plugin.yaml", root, "bundled", ""))
    loaded = manager._plugins["boltzmann"]
    assert not loaded.error
    return importlib.import_module(loaded.module.__name__ + ".job_monitor")


def test_legacy_jobs_remain_saved_without_painting_or_polling(monkeypatch):
    jobs = load_monitor()
    store = jobs.JobStore()
    row = store.track("global_binding_affinity", "fixture-job", session_id="owner")
    store.acquire("worker", "fixture-worker")

    def unexpected_poll(*args, **kwargs):
        raise AssertionError("Rendering must never poll a saved job")

    monkeypatch.setattr(jobs, "fetch_status", unexpected_poll)
    history = [{"role": "user", "content": "unchanged"}]
    cli = SimpleNamespace(session_id="owner", agent=None, conversation_history=history.copy())
    install_dock(cli)
    for state in ("pending", "running", "unknown", "paused_auth", "success"):
        store.update(row["id"], state=state)
        before = store.path.read_bytes()
        cli._subagent_monitor.refresh()
        assert not cli._subagent_monitor.jobs
        assert not cli._subagent_monitor.dock_text(columns=100, rows=24)
        assert store.path.read_bytes() == before
        assert store.get(row["id"])["state"] == state
    assert cli.conversation_history == history


def test_legacy_storage_is_untouched_across_profile_switches(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("SCI_HOME", str(a))
    token = set_multiplex_context(True)
    try:
        with profile_scope(a):
            jobs = load_monitor()
            store = jobs.JobStore()
            store.track("global_binding_affinity", "fixture-a", session_id="owner")
            before = store.path.read_bytes()
            first = SimpleNamespace(session_id="owner", agent=None)
            install_dock(first)
        with profile_scope(b):
            load_monitor()
            second = SimpleNamespace(session_id="owner", agent=None)
            install_dock(second)
            first._subagent_monitor.refresh()
            assert not first._subagent_monitor.jobs and not second._subagent_monitor.jobs
            assert not (b / "plugin-data").exists()
        with profile_scope(a):
            first._subagent_monitor.refresh()
            assert not first._subagent_monitor.jobs
            assert store.path.read_bytes() == before
            store.path.write_bytes(b"corrupt fixture database")
            first._subagent_monitor.refresh()
            assert not first._subagent_monitor.jobs
            assert store.path.read_bytes() == b"corrupt fixture database"
    finally:
        reset_multiplex_context(token)
