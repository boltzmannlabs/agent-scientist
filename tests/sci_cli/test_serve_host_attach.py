"""A second `sci serve` attaches to the host backend instead of binding a second port.

Attach is a PROOF, not a guess: exit 0 means the recorded owner answered on its recorded port and
serves what the caller asked for. Every other shape falls through to the bind or refuses loudly.
"""

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from gateway import host_rendezvous as hr
from gateway.restart import GATEWAY_FATAL_CONFIG_EXIT_CODE
from sci_cli.main_dashboard import _attach_to_host_backend


def _args(**over):
    base = dict(host="127.0.0.1", port=9200, no_open=True, isolated=False, open_profile="")
    return SimpleNamespace(**{**base, **over})


@pytest.fixture
def host_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SCI_GATEWAY_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.delenv("SCI_DESKTOP", raising=False)
    monkeypatch.setattr("sys.argv", ["sci", "serve"])
    return tmp_path


@pytest.fixture
def owner(host_dir):
    """A live backend answering the identity handshake as THIS pid, on a real ephemeral port."""
    serves_spa = {"value": True}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler API
            if self.path != hr.HOST_IDENTITY_PATH:
                self.send_error(404)
                return
            body = json.dumps({"ok": True, "pid": os.getpid(), "role": hr.ROLE_SERVE,
                               "servesSpa": serves_spa["value"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002 — BaseHTTPRequestHandler API
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(port=server.server_port, serves_spa=serves_spa)
    finally:
        server.shutdown()
        server.server_close()


def _dead_port() -> int:
    spare = socket.socket()
    spare.bind(("127.0.0.1", 0))
    port = spare.getsockname()[1]
    spare.close()
    return port


def _publish(create_time, *, pid=None, port=9119, host="127.0.0.1"):
    record = hr.HostRecord(
        role=hr.ROLE_SERVE, pid=pid if pid is not None else os.getpid(), create_time=create_time,
        host=host, port=port, protocol_version=hr.HOST_PROTOCOL_VERSION,
        token_fingerprint="", profiles=("default", "alpha"),
        updated_at="2026-01-01T00:00:00+00:00")
    path = hr.record_path(hr.ROLE_SERVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_json()), encoding="utf-8")


def test_second_serve_attaches_to_the_live_host_backend(host_dir, owner, capsys):
    """A live record whose owner ANSWERS ends the second launch at exit 0 — it never binds."""
    _publish(hr.process_create_time(), port=owner.port)

    with pytest.raises(SystemExit) as exc:
        _attach_to_host_backend(_args(), headless_backend=True)

    assert exc.value.code == 0
    assert f"port {owner.port}" in capsys.readouterr().out


def test_inherited_desktop_flag_without_spawn_credential_still_attaches(host_dir, owner, monkeypatch):
    """A terminal spawned by Desktop inherits its marker, not Desktop ownership.

    Only the Desktop backend receives the per-spawn session credential.  A bare
    marker must therefore preserve the one-host-backend attach invariant.
    """
    monkeypatch.setenv("SCI_DESKTOP", "1")
    monkeypatch.delenv("SCI_DASHBOARD_SESSION_TOKEN", raising=False)
    _publish(hr.process_create_time(), port=owner.port)

    with pytest.raises(SystemExit) as exc:
        _attach_to_host_backend(_args(), headless_backend=True)

    assert exc.value.code == 0


def test_desktop_owned_backend_keeps_its_separate_lifecycle(host_dir, owner, monkeypatch):
    """Desktop's credential-bearing backend does not attach to the host owner."""
    monkeypatch.setenv("SCI_DESKTOP", "1")
    monkeypatch.setenv("SCI_DASHBOARD_SESSION_TOKEN", "desktop-spawn-token")
    _publish(hr.process_create_time(), port=owner.port)

    assert _attach_to_host_backend(_args(), headless_backend=True) is None


def test_stale_record_is_ignored_and_the_launch_proceeds(host_dir):
    """A record whose creation time does not match the live PID is a recycled PID, not a
    backend: the launch must fall through and bind, never attach."""
    _publish(1.0)

    assert _attach_to_host_backend(_args(), headless_backend=True) is None


def test_isolated_never_attaches(host_dir, owner):
    """`--isolated` is load-bearing for Desktop's SSH backend ownership proof."""
    _publish(hr.process_create_time(), port=owner.port)

    assert _attach_to_host_backend(_args(isolated=True), headless_backend=True) is None


def test_dashboard_new_instance_bypasses_owner_without_changing_its_record(host_dir, owner):
    import argparse
    from sci_cli.subcommands.dashboard import build_dashboard_parser

    parser = argparse.ArgumentParser()
    build_dashboard_parser(parser.add_subparsers(dest='command'),
                           cmd_dashboard=lambda args: None,
                           cmd_dashboard_register=lambda args: None)
    _publish(hr.process_create_time(), port=owner.port)
    before = hr.record_path(hr.ROLE_SERVE).read_bytes()
    args = parser.parse_args(['dashboard', '--new-instance', '--no-open'])
    assert _attach_to_host_backend(args, headless_backend=False) is None
    assert hr.record_path(hr.ROLE_SERVE).read_bytes() == before
    # Ordinary launches still reuse the existing owner after an explicit opt-out.
    with pytest.raises(SystemExit) as exc:
        _attach_to_host_backend(parser.parse_args(['dashboard', '--no-open']), headless_backend=False)
    assert exc.value.code == 0


@pytest.mark.parametrize('choice', [0, 1, None], ids=['new-instance', 'reuse', 'cancel'])
def test_plain_interactive_dashboard_offers_instance_choice(host_dir, owner, monkeypatch, choice):
    import sys
    from sci_cli import curses_ui, main_dashboard

    monkeypatch.setattr(sys, 'argv', ['sci', 'dashboard'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    prompts = []
    monkeypatch.setattr(curses_ui, 'curses_single_select',
                        lambda title, items: prompts.append((title, items)) or choice)
    _publish(hr.process_create_time(), port=owner.port)
    before = hr.record_path(hr.ROLE_SERVE).read_bytes()
    args = _args()
    if choice == 0:
        _attach_to_host_backend(args, headless_backend=False)
        assert args.isolated and args.port == owner.port + 1
        # The selected new server must not route back into the machine owner.
        monkeypatch.setattr('sci_cli.profiles.get_active_profile_name', lambda: 'research')
        assert main_dashboard._route_named_profile_dashboard(args, False, None, None) is None
    else:
        with pytest.raises(SystemExit) as exc:
            _attach_to_host_backend(args, headless_backend=False)
        assert exc.value.code == 0
        assert not args.isolated
    assert len(prompts) == 1 and str(owner.port) in prompts[0][0]
    assert hr.record_path(hr.ROLE_SERVE).read_bytes() == before


def test_a_record_whose_owner_does_not_answer_falls_through_to_the_bind(host_dir):
    """The graceful-shutdown window: the PID is still alive and the record still on disk, but the
    socket is already closed. Exiting 0 here reported success with NOTHING listening."""
    _publish(hr.process_create_time(), port=_dead_port())

    assert _attach_to_host_backend(_args(), headless_backend=True) is None


def test_unprovable_liveness_still_has_to_answer(host_dir, monkeypatch):
    """Without psutil the liveness answer is ``None`` (unprovable). Treating that as "alive" made
    a record for a long-dead PID a permanent silent outage — every launch exited 0 forever."""
    monkeypatch.setattr("sci_cli.process_identity._pid_alive_matches", lambda *_a, **_k: None)
    _publish(None, pid=2**22 - 1, port=_dead_port())

    assert _attach_to_host_backend(_args(), headless_backend=True) is None


@pytest.mark.parametrize(
    "argv,over",
    [(["sci", "serve", "--port", "8899"], {"port": 8899}),
     (["sci", "serve", "--host", "0.0.0.0"], {"host": "0.0.0.0"})],
    ids=["explicit-port", "explicit-host"],
)
def test_an_explicit_endpoint_the_owner_cannot_serve_is_refused(host_dir, owner, monkeypatch,
                                                                argv, over, capsys):
    """`--port 8899` answered with "use 127.0.0.1:<other>", or `--host 0.0.0.0` (LAN access)
    silently turned into a loopback attach, are both wrong answers: refuse, naming the owner."""
    monkeypatch.setattr("sys.argv", argv)
    _publish(hr.process_create_time(), port=owner.port)

    with pytest.raises(SystemExit) as exc:
        _attach_to_host_backend(_args(**over), headless_backend=True)

    # 78 (EX_CONFIG) is the deliberate refusal a supervisor parks on; exit 1 under
    # Restart=always was an infinite loop with nothing listening (#119824).
    assert exc.value.code == GATEWAY_FATAL_CONFIG_EXIT_CODE
    assert f"PID {os.getpid()}" in capsys.readouterr().out


def test_dashboard_is_never_routed_to_a_headless_backend(host_dir, owner, capsys):
    """`sci serve` and `sci dashboard` publish the same host role; only one mounts the SPA,
    so attaching a dashboard user to a headless backend opens a URL with no UI behind it."""
    owner.serves_spa["value"] = False
    _publish(hr.process_create_time(), port=owner.port)

    with pytest.raises(SystemExit) as exc:
        _attach_to_host_backend(_args(), headless_backend=False)

    assert exc.value.code == GATEWAY_FATAL_CONFIG_EXIT_CODE
    assert "no dashboard UI" in capsys.readouterr().out
