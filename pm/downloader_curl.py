"""Windows pinned archives use curl's native network stack without range probes.

The standalone PM bootstrap also imports this module before Sci is installed.
Publication and checksum validation remain the responsibility of Download.
Interrupted streams restart; they never mix with the sparse range cache.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.error
from email.parser import Parser
from pathlib import Path

from pm.network import retry_network


def windows_curl() -> str | None:
    try:
        from sci_platform.host.facts import os_family
        from sci_platform.resolver import locate_command
    except ModuleNotFoundError as exc:
        if exc.name != "sci_platform":
            raise
        # PM's independent bootstrap contains pm/ only, before app admission.
        return shutil.which("curl.exe") if os.name == "nt" else None
    if os_family() != "win32":
        return None
    command = locate_command("curl.exe").command
    return command[0] if command else None


def fetch_archive(curl, url, part, paused, tick, wait_retry) -> int:
    from pm.downloader import DownloadError, DownloadPaused, DownloadTransportError, _LOOPBACK, _UA

    def request(headers):
        if paused.is_set():
            raise DownloadPaused(url)
        # Disable user curlrc settings: neither insecure TLS nor credentials
        # from a user's curl defaults belong in a public package request.
        args = [curl, "--disable", "--silent", "--show-error", "--fail", "--location",
                "--proto", "=http,https" if url.startswith(_LOOPBACK) else "=https",
                "--proto-redir", "=https", "--connect-timeout", "20", "--max-time", "600",
                "--user-agent", _UA["User-Agent"], "--header", "Accept-Encoding: identity",
                "--output", str(part), "--dump-header", str(headers),
                "--write-out", "%{http_code}", "--url", url]
        # A failed HTTP response may not open --output, so clear old partials
        # explicitly. Complete destinations are untouched until hash validation.
        part.write_bytes(b"")
        headers.write_bytes(b"")
        tick([], 0)
        with tempfile.TemporaryFile() as diagnostics, tempfile.TemporaryFile() as status:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=status,
                                       stderr=diagnostics)
            try:
                while process.poll() is None:
                    if paused.wait(0.1):
                        raise DownloadPaused(url)
                    tick([(0, part.stat().st_size)], 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            if paused.is_set():
                raise DownloadPaused(url)
            status.seek(0)
            code = int(status.read(16).strip() or b"0")
            diagnostics.seek(0)
            detail = diagnostics.read(4096).decode("utf-8", errors="replace").strip()
        if process.returncode:
            if process.returncode == 22 and code >= 400:
                blocks = headers.read_text(encoding="iso-8859-1").strip().split("\n\n")
                response_headers = Parser().parsestr(blocks[-1].partition("\n")[2])
                raise urllib.error.HTTPError(url, code, detail, response_headers, None)
            if process.returncode in {5, 6, 7, 18, 28, 52, 55, 56}:
                raise urllib.error.URLError(ConnectionError(detail))
            # TLS, protocol, local filesystem and executable failures must not
            # be retried or disguised as a missing mirror.
            raise DownloadError(f"curl download failed ({process.returncode}) for {url}: {detail}")
        if code != 200:
            raise DownloadError(f"unexpected curl download status {code} for {url}")
        return part.stat().st_size

    def attempt():
        with tempfile.TemporaryDirectory(prefix="curl-", dir=part.parent) as directory:
            return request(Path(directory) / "headers")

    try:
        return retry_network(attempt, wait=wait_retry)
    except urllib.error.URLError as exc:
        raise DownloadTransportError(url, exc) from exc
