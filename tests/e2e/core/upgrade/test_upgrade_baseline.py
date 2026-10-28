"""Upgrade fixtures must exercise an older install even before the first release tag."""

import os

import pytest


@pytest.fixture
def history(tmp_path, monkeypatch):
    from tests.e2e.core.upgrade import _install_helpers as install

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("SCI_E2E_UPGRADE_BASE", raising=False)
    monkeypatch.setattr(install.H, "WORKTREE", tmp_path)

    def git(*args):
        return install.git(*args, cwd=tmp_path)

    git("init", "-q")
    (tmp_path / "scripts").mkdir()
    installer = tmp_path / "scripts" / "install.sh"
    commits = []
    for index in range(3):
        installer.write_text(f"#!/bin/sh\n# fixture revision {index}\n", encoding="utf-8")
        git("add", "scripts/install.sh")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", f"revision {index}")
        commits.append(git("rev-parse", "HEAD"))
    monkeypatch.setattr(install, "PRERELEASE_UPGRADE_BASE", commits[0])
    return install, git, commits


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("release_tag", ["v1.0.0.0", "0.1.0"])
def test_baseline_prefers_explicit_then_stable_then_prerelease(history, monkeypatch, capsys, release_tag):
    install, git, commits = history
    git("tag", "v2026.9.14", commits[1])  # Inherited CalVer is not a SCI release.
    git("tag", "v1.0.0.1-rc.1", commits[1])
    assert install.previous_upgrade_ref() == commits[0]
    assert "prerelease snapshot" in capsys.readouterr().out
    git("tag", release_tag, commits[1])
    assert install.previous_upgrade_ref() == release_tag
    monkeypatch.setenv("SCI_E2E_UPGRADE_BASE", commits[0])
    assert install.previous_upgrade_ref() == commits[0]


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("bad_base", ["HEAD", "missing", "unrelated"])
def test_baseline_rejects_unusable_history_instead_of_skipping(history, monkeypatch, bad_base):
    install, git, commits = history
    if bad_base == "unrelated":
        git("checkout", "--orphan", "unrelated")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "unrelated root")
        git("checkout", "--detach", commits[-1])
    monkeypatch.setenv("SCI_E2E_UPGRADE_BASE", bad_base)
    with pytest.raises(AssertionError):
        install.previous_upgrade_ref()
