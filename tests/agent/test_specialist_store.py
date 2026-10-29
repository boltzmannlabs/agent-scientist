"""Saved specialists stay local to main/profiles; edits are atomic and explicit."""
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest

from agent.specialist_store import Specialist, save, load, inventory, copy_to, delete
from sci_cli.native_profile_creation import profile_scope


def test_main_a_b_a_copy_and_concurrent_edits(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_active
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / n for n in ('main', 'a', 'b')]
    for home in homes:
        home.mkdir()
        (home / 'config.yaml').write_text('model: {default: fixture}\n')
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    set_multiplex_active(True)
    try:
        with profile_scope(homes[0]):
            original = save(Specialist('reviewer', 'Review evidence — 生物学', tools=('read_file',), sources=('/private/papers',)))
            path = homes[0] / 'subagents' / 'reviewer.json'
            path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
        with profile_scope(homes[1]):
            assert inventory()[0] == {}
            a = save(Specialist('reviewer', 'Profile A reviewer'))
            copy_to(a, homes[2], 'copied')
        with profile_scope(homes[2]):
            copied = load('copied')
            assert not copied.enabled and copied.needs_review
            assert not copied.sources and not copied.children
            with pytest.raises(FileNotFoundError):
                load('reviewer')
        with profile_scope(homes[1]):
            assert load('reviewer') == a
        with profile_scope(homes[0]):
            assert load('reviewer') == original
        def writer(i):
            try:
                return save(replace(original, purpose=f'Edit {i}'), homes[0], expected_revision=original.revision)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, range(2)))
        assert sum(r is not None for r in results) == 1
        assert all((h / 'config.yaml').read_text() == 'model: {default: fixture}\n' for h in homes)
    finally:
        set_multiplex_active(False)


def test_store_rejects_conflicts_malformed_paths_and_copies_without_grants(tmp_path):
    item = save(Specialist('reviewer', 'Review', children=('analyst',), sources=('/private',)), tmp_path)
    with pytest.raises(FileExistsError):
        save(item, tmp_path)
    for name in ('../outside', '/absolute', 'Bad Name'):
        with pytest.raises(ValueError):
            save(replace(item, name=name), tmp_path)
    copied = copy_to(item, tmp_path, 'copy')
    assert copied.needs_review and not copied.enabled and not copied.automatic
    assert not copied.children and not copied.sources
    (tmp_path / 'subagents' / 'broken.json').write_text('{')
    items, errors = inventory(tmp_path)
    assert 'reviewer' in items and errors
    with pytest.raises(ValueError):
        delete('reviewer', tmp_path, expected_revision='stale')
    delete('reviewer', tmp_path, expected_revision=item.revision)
    assert 'reviewer' not in inventory(tmp_path)[0]
