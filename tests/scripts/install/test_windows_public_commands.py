"""Public launcher verification uses native commands without writing the real User PATH."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("fault", ["none", "missing", "broken", "path", "shadowed"])
def test_published_commands_are_verified_before_success(tmp_path, fault):
    directory = tmp_path / "public bin with spaces"
    directory.mkdir()
    for name in ("sci", "agent-sci"):
        (directory / f"{name}.cmd").write_text(
            f"@echo off\necho SCI fixture version\nexit /b {23 if fault == 'broken' else 0}\n", encoding='utf-8')
    if fault == "missing":
        (directory / "agent-sci.cmd").unlink()
    script = tmp_path / "verify.ps1"
    helper = str(ROOT / "scripts/source-install-verify.ps1").replace("'", "''")
    path = str(directory).replace("'", "''")
    user_path = "unrelated" if fault == "path" else path
    if fault == "shadowed":
        old = tmp_path / "old commands"
        old.mkdir()
        (old / "sci.cmd").write_text("@echo off\necho Old unrelated SCI\nexit /b 0\n", encoding="utf-8")
        user_path = str(old).replace("'", "''") + ";" + path
    script.write_text(
        "$ErrorActionPreference='Stop'\n"
        f". '{helper}'\n"
        f"$verified=Test-SciPublishedCommands -BinDirectory '{path}' -UserPath '{user_path}'\n"
        "Show-SciCommandInstructions $verified\n", encoding="utf-8")
    host = shutil.which("powershell") or shutil.which("pwsh")
    assert host
    # Two Windows PowerShell startups plus launcher probes can exceed 30s on a
    # busy native runner. This is a functional check, not a performance test.
    result = subprocess.run([host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                            text=True, capture_output=True, timeout=120)
    if fault == "none":
        assert result.returncode == 0, result.stdout + result.stderr
        assert str(directory) in result.stdout and "--version" in result.stdout
        assert "Completely exit all VS Code windows" in result.stdout
    else:
        assert result.returncode != 0
        assert {"missing": "launcher is missing", "broken": "failed --version", "path": "persistent User PATH",
                "shadowed": "saved Windows PATH"}[fault] in result.stderr
