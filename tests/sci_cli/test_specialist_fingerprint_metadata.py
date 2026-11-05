"""Bookkeeping must not invalidate approval of unchanged private capabilities."""

import pytest

from agent.specialist_extensions import fingerprint


@pytest.mark.parametrize('relative', [
    'skills/.usage.json',
    'skills/.usage.json.lock',
    'skills/.curator_ledger.jsonl',
    'skills/.locks/ledger.lock',
    'skills/.hub/audit.log',
])
def test_runtime_bookkeeping_does_not_change_private_fingerprint(tmp_path, relative):
    skill = tmp_path / 'skills/reviewer/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('Reviewed instructions\n')
    approved = fingerprint(tmp_path)
    metadata = tmp_path / relative
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text('Runtime bookkeeping\n')
    assert fingerprint(tmp_path) == approved
    metadata.write_text('Updated runtime bookkeeping\n')
    assert fingerprint(tmp_path) == approved


@pytest.mark.parametrize('relative', [
    'config.yaml',
    '.env',
    'skills/reviewer/SKILL.md',
    'skills/reviewer/.instructions',
    'skills/.hub/lock.json',
    'plugins/reviewer/handler.py',
    'plugins/reviewer/.usage.json',
])
def test_capability_changes_still_change_private_fingerprint(tmp_path, relative):
    source = tmp_path / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('Reviewed capability\n')
    approved = fingerprint(tmp_path)
    source.write_text('Changed capability\n')
    assert fingerprint(tmp_path) != approved


def test_bookkeeping_symlinks_remain_rejected(tmp_path):
    target = tmp_path / 'outside'
    target.write_text('Not approved\n')
    skills = tmp_path / 'skills'
    skills.mkdir()
    (skills / '.usage.json').symlink_to(target)
    with pytest.raises(ValueError, match='symbolic links'):
        fingerprint(tmp_path)
