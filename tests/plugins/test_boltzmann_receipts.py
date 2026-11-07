"""Issue #32: durable capacity admission and conservative upload-evidence retirement."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.boltzmann import preflight, receipt_store as rs, tools
from sci_cli.plugins_state import PluginState


def evidence():
    return {"authorization": "fixture-fingerprint", "sha256": "fixture-digest", "contract": "fixture",
            "context": {}, "validation": {"warnings": [], "errors": []}, "inventory": {}}


def uploaded(store, ref="fixture/object.xyz"):
    data = evidence()
    identity = store.reserve_upload(data)
    key = preflight._receipt_key("fixture-job", "input", ref)
    store.complete_upload(identity, key, ref, data)
    return identity, key


def terminal(job, doc):
    return {"job_name": job, "doc_id": doc, "status": "completed", "job_terminal_confirmed": True}


@pytest.fixture
def clock(monkeypatch):
    now = [100000.0]
    monkeypatch.setattr(rs, "time", SimpleNamespace(time=lambda: now[0]))
    return now


@pytest.mark.parametrize("interruption", ["copy", "source_removal"])
def test_migration_recovers_interruption_preserving_authorization_and_concurrent_state(monkeypatch, interruption):
    state = PluginState("boltzmann")
    authorization = {"fingerprint": "fixture-key-hash", "authorized": True}
    state.set("authorization", authorization)
    state.set("unrelated", {"keep": [1, 2, 3]})
    keys = [preflight._receipt_key("job", "file", str(i)) for i in range(2)]
    receipts = [evidence(), evidence()]
    receipts[0]["inventory"] = {"data": "x" * (9 * 1024 * 1024)}
    for key, data in zip(keys, receipts):
        state.set(key, data)
    original = state.path.read_bytes()
    store = rs.ReceiptStore()
    real_write = store._write

    def stop_after_copy(row):
        real_write(row)
        raise KeyboardInterrupt("simulated crash after durable copy")

    def stop_before_removal(*args, **kwargs):
        raise KeyboardInterrupt("simulated crash before atomic source removal")

    with monkeypatch.context() as patch:
        if interruption == "copy":
            patch.setattr(store, "_write", stop_after_copy)
        else:
            patch.setattr(rs, "atomic_json_write", stop_before_removal)
        with pytest.raises(KeyboardInterrupt):
            store.migrate()
    assert state.path.read_bytes() == original
    state.set("concurrent", "preserve this later update")
    assert rs.ReceiptStore().migrate() == 2
    assert rs.ReceiptStore().migrate() == 0
    assert json.loads(state.path.read_text()) == {
        "authorization": authorization, "unrelated": {"keep": [1, 2, 3]}, "concurrent": "preserve this later update"}
    assert [store.get(k) for k in keys] == receipts
    assert len(store.inspect()["records"]) == 2
    assert all(r["legacy_unknown"] for r in store.inspect()["records"])


@pytest.fixture
def water(tmp_path, monkeypatch):
    source = tmp_path / "water.xyz"
    source.write_text("3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")
    return source


@pytest.mark.parametrize("failure", ["quota", "disk", "write"])
def test_upload_rejects_capacity_or_persistence_before_external_action(water, monkeypatch, failure):
    calls = []
    if failure == "quota":
        monkeypatch.setattr(rs, "LIMIT_BYTES", 1)
    elif failure == "disk":
        monkeypatch.setattr(rs.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    else:
        def deny(*args, **kwargs):
            raise PermissionError("fixture denied")
        monkeypatch.setattr(rs, "atomic_write_bytes", deny)
    result = preflight.validated_upload(str(water), "Single_Point_Energy", "molecule_path", {}, True,
                                        lambda path: calls.append(path))
    assert not calls
    assert result["status"] == "not_started" and result["uploaded"] is False
    assert "boltzmann-receipts" in result["error"]
    assert PluginState("boltzmann").get("authorization") is None


def test_invalid_file_never_reserves_and_successful_upload_has_preallocated_slot(water, monkeypatch):
    store = rs.ReceiptStore()
    calls = []

    def upload(snapshot):
        rows = store.inspect()["records"]
        assert len(rows) == 1 and rows[0]["state"] == "reserved"
        assert (store.root / (rows[0]["id"] + ".json")).stat().st_size == rows[0]["capacity"]
        assert Path(snapshot).read_bytes() == water.read_bytes()
        calls.append(snapshot)
        return "fixture/water.xyz"

    empty = water.with_name("empty.xyz")
    empty.touch()
    bad = preflight.validated_upload(str(empty), "Single_Point_Energy", "molecule_path", {}, True, upload)
    assert bad["status"] == "not_started" and not store.inspect()["records"]
    result = preflight.validated_upload(str(water), "Single_Point_Energy", "molecule_path", {}, True, upload)
    assert result["status"] == "uploaded" and len(calls) == 1
    key = preflight._receipt_key("Single_Point_Energy", "molecule_path", result["s3_path"])
    assert store.get(key)["sha256"] == result["sha256"]
    assert PluginState("boltzmann").get(key) is None


def test_key_rotation_does_not_grant_validation_but_keeps_reference_for_retention(water, monkeypatch):
    result = preflight.validated_upload(str(water), "Single_Point_Energy", "molecule_path", {}, True,
                                        lambda _: "fixture/water.xyz")
    monkeypatch.setattr(preflight, "current_key", lambda: "replacement-fixture-key")
    payload = {"task_name": "water", "molecule_path": result["s3_path"], "method": "B3LYP",
               "basis": "def2-TZVP", "charge": 0, "spin_multiplicity": "1", "dispersion": "D3BJ"}
    report = preflight.preflight_submission("Single_Point_Energy", payload)
    assert any("no current-profile validation receipt" in warning for warning in report.warnings)
    assert preflight.decision(report, False)["approval_required"]
    assert report.upload_receipt_ids == [result["receipt_id"]]


def test_concurrent_reservations_cannot_oversubscribe(monkeypatch):
    monkeypatch.setattr(rs, "LIMIT_BYTES", 60 * 1024)
    def reserve(_):
        try:
            return rs.ReceiptStore().reserve_upload(evidence())
        except rs.ReceiptStorageError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sum(result is not None for result in results) == 1
    assert rs.ReceiptStore().inspect()["used_bytes"] <= rs.LIMIT_BYTES


def test_small_reservation_preserves_disk_headroom_for_large_pending_upload(monkeypatch):
    store = rs.ReceiptStore()
    large = evidence()
    large["inventory"] = {"fixture": "x" * (2 * 1024 * 1024)}
    identity = store.reserve_upload(large)
    capacity = store.inspect()["records"][0]["capacity"]
    monkeypatch.setattr(rs.shutil, "disk_usage", lambda _: SimpleNamespace(free=capacity))
    with pytest.raises(rs.ReceiptStorageError, match="disk space"):
        store.reserve_upload(evidence())
    assert [r["id"] for r in store.inspect()["records"]] == [identity]


def test_migration_capacity_failure_preserves_source_and_reports_failure(monkeypatch, capsys):
    from plugins.boltzmann.receipt_cli import receipt_command
    state = PluginState("boltzmann")
    state.set("authorization", {"fingerprint": "keep"})
    state.set(preflight._receipt_key("job", "field", "object"), evidence())
    before = state.path.read_bytes()
    monkeypatch.setattr(rs, "LIMIT_BYTES", 1)
    assert receipt_command(SimpleNamespace(receipt_action="migrate")) == 1
    result = json.loads(capsys.readouterr().out)
    assert "capacity" in result["error"] and state.path.read_bytes() == before


def test_full_legacy_state_no_longer_blocks_large_validated_upload(water, monkeypatch):
    state = PluginState("boltzmann")
    state.set("authorization", {"fingerprint": "unchanged"})
    state.set("unrelated", ["also unchanged"])
    old = evidence()
    old["inventory"] = {"fixture": "x" * (9 * 1024 * 1024)}
    state.set("upload:legacy-evidence", old)
    large = evidence()
    large["inventory"] = {"fixture": "x" * (2 * 1024 * 1024)}
    with pytest.raises(ValueError, match="quota"):
        state.set("upload:new-evidence", large)
    real_validate = preflight.validate_file
    def validated(*args):
        report = real_validate(*args)
        report.inventory = large["inventory"]
        return report
    monkeypatch.setattr(preflight, "validate_file", validated)
    result = preflight.validated_upload(str(water), "Single_Point_Energy", "molecule_path", {}, True,
                                        lambda _: "fixture/new.xyz")
    assert result["status"] == "uploaded"
    assert json.loads(state.path.read_text()) == {
        "authorization": {"fingerprint": "unchanged"}, "unrelated": ["also unchanged"]}
    assert rs.ReceiptStore().get("upload:legacy-evidence") == old
    assert rs.ReceiptStore().get(preflight._receipt_key(
        "Single_Point_Energy", "molecule_path", result["s3_path"]))["inventory"] == large["inventory"]


def test_post_upload_write_failure_is_partial_and_reservation_remains_pinned(water, monkeypatch, clock):
    def fail(*args):
        raise rs.ReceiptStorageError("fixture finalization failure")
    monkeypatch.setattr(rs.ReceiptStore, "complete_upload", fail)
    result = preflight.validated_upload(str(water), "Single_Point_Energy", "molecule_path", {}, True,
                                        lambda _: "fixture/accepted.xyz")
    assert result["status"] == "partial" and result["s3_path"] == "fixture/accepted.xyz"
    assert result["uploaded"] and not result["safe_to_retry"]
    clock[0] += 2 * rs.RETENTION_SECONDS
    assert rs.ReceiptStore().cleanup() == []
    assert rs.ReceiptStore().inspect()["records"][0]["state"] == "reserved"


def test_all_linked_jobs_must_finish_then_reuse_extends_retention(clock):
    store = rs.ReceiptStore()
    identity, key = uploaded(store)
    first = store.begin_submission("job", [identity])
    store.accept_submission(first, "first")
    second = store.begin_submission("job", [identity])
    store.accept_submission(second, "second")
    store.observe("job", "first", terminal("job", "first"))
    clock[0] += rs.RETENTION_SECONDS + 1
    assert store.cleanup() == [] and store.get(key)
    store.observe("job", "second", {"status": "unknown", "timeout": True})
    assert store.cleanup() == []
    store.observe("job", "second", terminal("job", "second"))
    clock[0] += rs.RETENTION_SECONDS - 1
    assert store.get(key) and store.cleanup() == []
    third = store.begin_submission("job", [identity])
    store.accept_submission(third, "third")
    clock[0] += 2
    assert store.cleanup() == []
    store.observe("job", "third", terminal("job", "third"))
    clock[0] += rs.RETENTION_SECONDS + 1
    assert store.cleanup() == [identity]
    assert store.get(key) is None and not store.inspect()["records"]


def test_unknown_upload_submission_and_legacy_history_never_expire(clock):
    store = rs.ReceiptStore()
    store.reserve_upload(evidence())  # interrupted/ambiguous upload
    identity, key = uploaded(store)
    store.begin_submission("job", [identity])  # interrupted before saving job ID
    legacy = preflight._receipt_key("old", "file", "old-object")
    PluginState("boltzmann").set(legacy, evidence())
    store.migrate()
    clock[0] += 100 * rs.RETENTION_SECONDS
    assert store.cleanup() == []
    assert store.get(key) and store.get(legacy)
    assert len(store.inspect()["records"]) == 4


@pytest.mark.parametrize("result", [
    {"status": "failed", "error": "HTTP failure"},
    {"status": "error", "authorization_required": True, "job_terminal_confirmed": True},
    {"status": "completed", "timeout": True, "job_terminal_confirmed": True},
    {"status": "running", "job_terminal_confirmed": True},
])
def test_ambiguous_status_never_authorizes_cleanup(clock, result):
    store = rs.ReceiptStore()
    identity, key = uploaded(store)
    attempt = store.begin_submission("job", [identity])
    store.accept_submission(attempt, "doc")
    store.observe("job", "doc", dict(result, job_name="job", doc_id="doc"))
    clock[0] += 2 * rs.RETENTION_SECONDS
    assert store.cleanup() == [] and store.get(key)


def test_expired_unused_receipts_clean_automatically_but_write_failures_are_reported(clock, monkeypatch, capsys):
    from plugins.boltzmann.receipt_cli import receipt_command
    store = rs.ReceiptStore()
    identity, key = uploaded(store)
    clock[0] += rs.RETENTION_SECONDS + 1
    store.reserve_upload(evidence())
    assert store.get(key) is None
    assert receipt_command(SimpleNamespace(receipt_action="status")) == 0
    output = json.loads(capsys.readouterr().out)
    assert "authorization" not in json.dumps(output) and output["limit_bytes"] == rs.LIMIT_BYTES
    second, _ = uploaded(store, "another.xyz")
    clock[0] += rs.RETENTION_SECONDS + 1
    real_unlink = Path.unlink
    def deny(path, *args, **kwargs):
        if path.name == second + ".json":
            raise PermissionError("fixture cleanup denied")
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", deny)
    assert receipt_command(SimpleNamespace(receipt_action="cleanup")) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert (store.root / (second + ".json")).exists()


def test_real_handlers_pin_before_submit_and_status_failure_preserves_remote_result(water, monkeypatch, clock):
    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    monkeypatch.setattr(tools, "current_key", lambda: "fixture-key")
    monkeypatch.setattr(tools, "time", SimpleNamespace(sleep=lambda _: None))
    monkeypatch.setattr(tools, "file_upload", lambda *a, **k: "fixture/water.xyz")
    upload = json.loads(tools.handle_boltzmann_upload(local_path=str(water), job_name="Single_Point_Energy",
                       input_field="molecule_path", allow_partial_validation=True))
    payload = {"task_name": "water", "molecule_path": upload["s3_path"], "method": "B3LYP",
               "basis": "def2-TZVP", "charge": 0, "spin_multiplicity": "1", "dispersion": "D3BJ"}
    store = rs.ReceiptStore()
    seen = []
    def submit(*args, **kwargs):
        rows = store.inspect()["records"]
        attempt = next(r for r in rows if r["kind"] == "submission")
        assert attempt["state"] == "unknown" and upload["receipt_id"] in attempt["receipts"]
        seen.append(True)
        return "fixture-doc"
    monkeypatch.setattr(tools, "submit_request", submit)
    with monkeypatch.context() as patch:
        patch.setattr(rs, "LIMIT_BYTES", store.inspect()["used_bytes"])
        blocked = json.loads(tools.handle_boltzmann_submit(job_name="Single_Point_Energy", experiment_data=payload,
                             experiment_name="fixture", allow_partial_validation=True))
        assert blocked["status"] == "not_started" and blocked["submitted"] is False and not seen
    submitted = json.loads(tools.handle_boltzmann_submit(job_name="Single_Point_Energy", experiment_data=payload,
                           experiment_name="fixture", allow_partial_validation=True))
    assert submitted["status"] == "accepted" and seen
    assert any(r.get("doc_id") == "fixture-doc" for r in rs.ReceiptStore().inspect()["records"])
    result = terminal("Single_Point_Energy", "fixture-doc")
    monkeypatch.setattr(tools, "fetch_status", lambda *a, **k: deepcopy(result))
    status = json.loads(tools.handle_boltzmann_status(job_name="Single_Point_Energy", doc_id="fixture-doc"))
    assert status["job_terminal_confirmed"] and not status.get("receipt_storage_warning")
    def deny(*args):
        raise rs.ReceiptStorageError("fixture failure")
    monkeypatch.setattr(rs.ReceiptStore, "observe", deny)
    status = json.loads(tools.handle_boltzmann_status(job_name="Single_Point_Energy", doc_id="fixture-doc"))
    assert status["doc_id"] == "fixture-doc" and status["status"] == "completed"
    assert "receipt_storage_warning" in status


def test_profile_scopes_a_b_a_preserve_separate_receipts_and_state(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from sci_cli.native_profile_creation import profile_scope
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    monkeypatch.setenv("SCI_HOME", str(a))
    token = set_multiplex_context(True)
    try:
        with profile_scope(a):
            PluginState("boltzmann").set("authorization", {"fingerprint": "A"})
            identity, key = uploaded(rs.ReceiptStore())
            before = PluginState("boltzmann").path.read_bytes()
        with profile_scope(b):
            assert rs.ReceiptStore().get(key) is None
            assert PluginState("boltzmann").get("authorization") is None
            uploaded(rs.ReceiptStore(), "B-only.xyz")
        with profile_scope(a):
            assert rs.ReceiptStore().find(key)[1] == identity
            assert PluginState("boltzmann").path.read_bytes() == before
            assert len(rs.ReceiptStore().inspect()["records"]) == 1
    finally:
        reset_multiplex_context(token)


@pytest.mark.parametrize("requested", [180, 900, 0])
def test_status_legacy_wait_hint_does_not_end_foreground_wait(monkeypatch, requested):
    calls = []
    monkeypatch.setattr(tools, "require_authorized", lambda: None)
    monkeypatch.setattr(tools, "fetch_status", lambda *args, **kwargs: calls.append(kwargs) or {
        "status": "success", "job_terminal_confirmed": True,
        "job_name": "fixture-job", "doc_id": "fixture-doc",
    })
    monkeypatch.setattr(tools.ReceiptStore, "observe", lambda *args, **kwargs: None)
    monkeypatch.setattr(tools.time, "sleep", lambda *_: None)

    response = json.loads(tools.handle_boltzmann_status(
        job_name="fixture-job", doc_id="fixture-doc", wait_seconds=requested))

    assert response["status"] == "success"
    assert calls[0]["wait_until_terminal"] is True
    assert "max_wait" not in calls[0] and "poll_once" not in calls[0]


@pytest.mark.platforms("posix")
def test_storage_is_private_and_rejects_symlinked_records():
    store = rs.ReceiptStore()
    identity, key = uploaded(store)
    path = store.root / (identity + ".json")
    assert store.root.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    target = store.root / "outside"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(rs.ReceiptStorageError):
        store.cleanup()
    assert target.exists()
