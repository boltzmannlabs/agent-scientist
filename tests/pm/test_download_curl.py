"""Real curl + Store publication: no urllib probe, bounded retries and integrity."""

import hashlib
import threading

import pytest

from pm import downloader_curl, paths
from pm.downloader import Download, DownloadError, DownloadPaused, HashError, Source
from pm.store import Store
from sci_platform.resolver import locate_command
from tests.pm._range_server import RangeHandler, dl_server, url  # noqa: F401


@pytest.mark.parametrize("mode", [
    "retry", "exhausted", "forbidden", "hash", "truncated", "mirror", "python", "redirect",
    pytest.param("native", marks=pytest.mark.platforms("windows")),
])
def test_curl_store_verifies_before_publication(tmp_path, monkeypatch, dl_server, mode):
    curl = locate_command("curl.exe" if mode == "native" else "curl").command
    if not curl:
        pytest.skip("curl executable unavailable")
    if mode == "python":
        monkeypatch.setattr(downloader_curl, "windows_curl", lambda: None)
    elif mode != "native":
        # Inject a real transport, not a fake host OS. The native row exercises
        # automatic selection on Windows with the same Store entry point.
        monkeypatch.setattr(downloader_curl, "windows_curl", lambda: curl[0])
    monkeypatch.setattr(paths, "partials_root", lambda: tmp_path / "partials")
    body = b"pinned archive" * 1000
    digest = hashlib.sha256(body).hexdigest()
    RangeHandler.payloads = {"/tool.zip": body, "/mirror.zip": body}
    original = RangeHandler.do_GET
    calls, waits = [], []

    def respond(handler):
        calls.append((handler.path, handler.headers.get("Range")))
        if handler.path == "/tool.zip":
            if mode == "redirect":
                handler.send_response(302)
                handler.send_header("Location", url(dl_server, "/mirror.zip"))
                handler.end_headers()
                return
            if mode == "exhausted" or (mode == "retry" and len(calls) <= 2):
                handler.send_error(504)
                return
            if mode in {"forbidden", "mirror"}:
                handler.send_error(403)
                return
            if mode == "truncated" and len(calls) == 1:
                handler.send_response(200)
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body[:100])
                handler.close_connection = True
                return
        original(handler)

    monkeypatch.setattr(RangeHandler, "do_GET", respond)
    monkeypatch.setattr(Download, "_wait_retry", lambda self, delay: waits.append(delay))
    source_url = url(dl_server, "/tool.zip")
    if mode in {"mirror", "hash"}:
        import pm.artifact_mirror

        monkeypatch.setattr(pm.artifact_mirror, "pinned_source", lambda u, d, s:
                            Source(u, d, s, (url(dl_server, "/mirror.zip"),)))
    expected_error = {"exhausted": DownloadError, "forbidden": DownloadError,
                      "hash": HashError, "redirect": DownloadError}.get(mode)
    selected_digest = "0" * 64 if mode == "hash" else digest
    store = Store(tmp_path / "store")
    artifact = {"url": source_url, "sha256": selected_digest}
    seen = []
    with store.scratch() as scratch:
        if expected_error:
            with pytest.raises(expected_error):
                store.fetch_many([artifact], scratch)
            assert not store.published(f"fetch-{selected_digest}")
        else:
            result = store.fetch_many([artifact], scratch, progress=lambda *args: seen.append(args))[0]
            assert result.read_bytes() == body
            before = len(calls)
            assert store.fetch_many([artifact], scratch)[0] == result
            assert len(calls) == before  # verified cache requires no request
            assert seen[-1][0:2] == (len(body), len(body))
    if mode == "python":
        assert any(range_header for _, range_header in calls)
    else:
        assert all(range_header is None for _, range_header in calls)
    assert waits == {"retry": [1, 2], "exhausted": [1, 2, 4], "truncated": [1]}.get(mode, [])
    if mode == "exhausted":
        assert len(calls) == 4
    if mode in {"forbidden", "hash", "redirect"}:
        assert len(calls) == 1


def test_curl_pause_reaps_child_and_preserves_destination(tmp_path, monkeypatch, dl_server):
    curl = locate_command("curl").command
    if not curl:
        pytest.skip("curl executable unavailable")
    monkeypatch.setattr(downloader_curl, "windows_curl", lambda: curl[0])
    body = b"x" * (2 << 20)
    RangeHandler.payloads["/slow.zip"] = body
    RangeHandler.no_range = True
    RangeHandler.chunk = 64 << 10
    RangeHandler.slow_per_chunk = 0.05
    destination = tmp_path / "tool.zip"
    destination.write_bytes(b"previous destination")
    paused = threading.Event()
    children = []
    popen = downloader_curl.subprocess.Popen

    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(downloader_curl.subprocess, "Popen", spawn)
    job = Download([Source(url(dl_server, "/slow.zip"), destination, hashlib.sha256(body).hexdigest())],
                   partials_dir=tmp_path / "partials", pause_event=paused, native_archive_transport=True)

    def progress(done, total, ranges):
        if done:
            paused.set()

    with pytest.raises(DownloadPaused):
        job.run(progress)
    assert children and all(child.poll() is not None for child in children)
    assert destination.read_bytes() == b"previous destination"
    # A new invocation safely restarts the contiguous partial, then publishes.
    paused.clear()
    RangeHandler.slow_per_chunk = 0
    job.run()
    assert destination.read_bytes() == body
