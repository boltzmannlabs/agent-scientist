"""Exercise the source bootstrap's real download call against controlled HTTP responses.

The helper is host-independent PowerShell; Windows CI uses Windows PowerShell 5.1,
while other hosts can exercise the same function with pwsh. No installation runs.
"""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import os
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile

import pytest

pytestmark = pytest.mark.platforms("any")
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def powershell():
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        pytest.skip("PowerShell is required for the bootstrap download integration test")
    return executable


def download(tmp_path, powershell, route, responses, *, valid_digest=True):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("uv.exe", b"controlled archive; never executed")
    payload = buffer.getvalue()
    statuses = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/uv.zip")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = responses[min(len(statuses), len(responses) - 1)]
            statuses.append(code)
            body = payload if code == 200 else b"controlled download failure"
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    script = tmp_path / "download.ps1"
    script.write_text(r'''
$ErrorActionPreference = 'Stop'
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:FIXTURE_SOURCE, [ref]$null, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$definition = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-SciBootstrapArchive'
}, $true)
. ([scriptblock]::Create($definition.Extent.Text))
if ($env:FIXTURE_ROUTE -eq 'powershell') {
    # Capability seam: this host has no usable curl.exe. The fallback HTTP
    # requests, retry decisions, file writes and hash verification stay real.
    function Get-Command {
        param($Name, $CommandType, $ErrorAction)
        if ($Name -eq 'curl.exe') { return }
        Microsoft.PowerShell.Core\Get-Command @PSBoundParameters
    }
} else {
    function Invoke-WebRequest { throw 'curl.exe was available but was not used' }
}
$artifact = @{ url=$env:FIXTURE_URL; sha256=$env:FIXTURE_SHA }
$archive = $env:FIXTURE_ARCHIVE
$call = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Get-SciBootstrapArchive'
}, $true)
& ([scriptblock]::Create($call.Extent.Text))
''', encoding="utf-8")
    target = tmp_path / "archive with spaces.zip"
    target.write_bytes(b"leftover bytes must not survive failure or contaminate success")
    env = {**os.environ, "FIXTURE_SOURCE": str(ROOT / "setup-sci.ps1"),
           "FIXTURE_ROUTE": route, "FIXTURE_ARCHIVE": str(target),
           "FIXTURE_SHA": hashlib.sha256(payload if valid_digest else b"wrong pin").hexdigest()}
    if route == "curl" and not shutil.which("curl.exe"):
        curl = shutil.which("curl")
        if not curl:
            pytest.skip("curl is required to test the preferred downloader")
        # A real curl executable under its Windows name, not a downloader mock.
        binary = tmp_path / "bin"
        binary.mkdir()
        (binary / "curl.exe").symlink_to(curl)
        env["PATH"] = str(binary) + os.pathsep + env["PATH"]
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env["FIXTURE_URL"] = f"http://127.0.0.1:{server.server_port}/redirect"
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=100)
        finally:
            server.shutdown()
            thread.join(timeout=5)
    return result, target, payload, statuses, env["FIXTURE_URL"]


@pytest.mark.parametrize("route", ["curl", "powershell"])
def test_transient_failures_retry_then_publish_only_verified_bytes(tmp_path, powershell, route):
    result, target, payload, statuses, _ = download(tmp_path, powershell, route, [504, 503, 200])
    assert result.returncode == 0, result.stdout + result.stderr
    assert statuses == [504, 503, 200]
    assert target.read_bytes() == payload


@pytest.mark.parametrize("route", ["curl", "powershell"])
@pytest.mark.parametrize("failure", ["permanent", "exhausted", "digest"])
def test_failed_download_is_bounded_and_leaves_no_usable_archive(tmp_path, powershell, route, failure):
    codes = {"permanent": [403], "exhausted": [504], "digest": [200]}[failure]
    result, target, _, statuses, url = download(tmp_path, powershell, route, codes, valid_digest=failure != "digest")
    assert result.returncode != 0
    assert not target.exists()
    assert len(statuses) == (4 if failure == "exhausted" else 1)
    output = result.stdout + result.stderr
    assert "uv bootstrap download failed" in output and url in output
    if failure == "digest":
        assert "sha256 mismatch" in output
