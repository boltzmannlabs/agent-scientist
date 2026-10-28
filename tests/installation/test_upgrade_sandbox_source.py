"""Fresh-install fixtures explicitly choose SCI and redirect Git to a local origin."""

import subprocess

import pytest


@pytest.mark.platforms("posix")
def test_installer_source_is_explicit_and_clone_stays_local(tmp_path):
    from tests.e2e.core.upgrade import _install_helpers as install

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    sandbox = install.new_sandbox(tmp_path / "sandbox", origin)
    source = sandbox.env["SCI_REPO_URL"]
    assert source == install.OFFICIAL_HTTPS
    result = sandbox.run(["git", "clone", "-q", source, str(sandbox.checkout)], timeout=15)
    assert result.returncode == 0, result.stderr
    assert sandbox.checkout.is_dir()
    origin_config = (sandbox.checkout / ".git/config").read_text(encoding="utf-8-sig")
    assert f"url = {source}" in origin_config


@pytest.mark.platforms("posix")
def test_previous_upgrade_uses_sci_tags_not_calver_or_prereleases(tmp_path, monkeypatch):
    from tests.e2e.core.upgrade import _install_helpers as install

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
            cwd=tmp_path, check=True, capture_output=True, text=True, encoding="utf-8",
        )

    git("init", "-q")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/install.sh").write_text("#!/bin/sh\n# fixture installer\n", encoding="utf-8")
    git("add", "scripts/install.sh")
    for tag in ("v1.0.0.0", "v1.1.0.0", "v2026.10.1", "v1.2.0.0-rc1"):
        git("commit", "--allow-empty", "-qm", tag)
        git("tag", tag)
    git("commit", "--allow-empty", "-qm", "unreleased")
    monkeypatch.setattr(install.H, "WORKTREE", tmp_path)
    assert install.previous_upgrade_ref() == "v1.1.0.0"
