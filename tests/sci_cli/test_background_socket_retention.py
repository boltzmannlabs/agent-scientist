"""Live sockets survive scratch retention and remain scoped to their service owner."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import pytest

from sci_cli import background_chats as client
from sci_constants import prune_scratch_dir, reset_sci_home_override, set_sci_home_override

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def running_service(home, *, legacy=False):
    scratch = home / "cache" / "scratch"
    scratch.mkdir(parents=True)
    code = """
import asyncio, sys
from pathlib import Path
from sci_cli.background_chat_service import ChatService
service = ChatService(Path(sys.argv[1]))
if sys.argv[2]:
    service.endpoint = Path(sys.argv[2])
asyncio.run(service.run())
"""
    digest = hashlib.sha256(str(home.resolve()).encode()).hexdigest()[:24]
    old_endpoint = scratch / f"sci-chat-{os.getuid()}-{digest}.sock"  # windows-footgun: ok — POSIX tests
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c", code, str(home), str(old_endpoint) if legacy else ""],
        cwd=ROOT, env={**os.environ, "HOME": str(home.parent), "SCI_HOME": str(home),
                       "TMPDIR": str(scratch)},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 30
        while not (record := client.read_server(home)):
            if proc.poll() is not None:
                raise AssertionError(proc.communicate())
            if time.monotonic() > deadline:
                raise AssertionError("Service did not become ready")
            time.sleep(0.05)
        if legacy:
            record.pop("endpoint")
            (home / "runtime/background-chats/server.json").write_text(json.dumps(record), encoding="utf-8")
        yield proc, old_endpoint if legacy else Path(record["endpoint"])
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=10)


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("legacy", [False, True])
def test_scratch_cleanup_preserves_service_connections_across_profiles(monkeypatch, legacy):
    # no-tmp: ok — exercise real legacy AF_UNIX paths within macOS's 104-byte limit.
    with tempfile.TemporaryDirectory(prefix="scibg-", dir="/tmp") as directory:
        homes = [Path(directory).resolve() / "a", Path(directory).resolve() / "b"]
        with running_service(homes[0], legacy=legacy) as first, running_service(homes[1], legacy=legacy) as second:
            services = [first, second]
            ancient = time.time() - 48 * 3600
            for home, (_, endpoint) in zip(homes, services):
                scratch = home / "cache/scratch"
                expired = scratch / "expired.txt"
                expired.write_text("disposable", encoding="utf-8")
                os.utime(expired, (ancient, ancient))
                os.utime(endpoint, (ancient, ancient))
                nested = scratch / "nested"
                nested.mkdir()
                with socket.socket(socket.AF_UNIX) as listener:
                    listener.bind(str(nested / "control.sock"))
                    listener.listen()
                    os.utime(nested / "control.sock", (ancient, ancient))
                    os.utime(nested, (ancient, ancient))
                    assert prune_scratch_dir(scratch) == 1
                    assert (nested / "control.sock").is_socket()
                assert not expired.exists()
                assert endpoint.is_socket()
                if not legacy:
                    assert not endpoint.is_relative_to(scratch)
            monkeypatch.setattr(tempfile, "tempdir", directory)
            for index in (0, 1, 0):
                token = set_sci_home_override(homes[index])
                try:
                    result = client.request("status")
                    assert result["profile_home"] == str(homes[index])
                    assert result["pid"] == services[index][0].pid
                    assert result["chats"] == []
                finally:
                    reset_sci_home_override(token)


@pytest.mark.platforms("posix")
def test_missing_socket_reports_owner_without_replacing_service(tmp_path):
    # Long profile paths also exercise the short, TMPDIR-independent fallback.
    home = tmp_path / ("long-profile-" * 10)
    with running_service(home) as (proc, endpoint):
        assert len(os.fsencode(endpoint)) <= 100
        assert client.request("status", home=home)["pid"] == proc.pid
        endpoint.unlink()
        with pytest.raises(RuntimeError, match="socket is missing or refusing connections") as failure:
            client.ensure_server(home)
        assert str(proc.pid) in str(failure.value)
        assert "No replacement" in str(failure.value)
        assert client.read_server(home)["pid"] == proc.pid
        assert proc.poll() is None
