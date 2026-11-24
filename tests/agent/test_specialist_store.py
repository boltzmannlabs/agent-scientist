"""Saved specialists stay local to main/profiles; edits are atomic and explicit."""
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest

from agent.specialist_store import Specialist, save, load, inventory, copy_to, delete
from sci_cli.native_profile_creation import profile_scope


def test_automatic_matching_upgrades_legacy_without_enabling_or_masking_edits(tmp_path, monkeypatch):
    from dataclasses import asdict
    import json
    from types import SimpleNamespace
    from sci_cli.specialist_portability import import_definition
    from sci_cli.subagent_package_install import definition_digest

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    monkeypatch.setenv('SCI_HOME', str(a))
    assert Specialist('new', 'Review evidence').automatic
    legacy = Specialist('legacy', 'Review evidence', automatic=False, enabled=False, needs_review=True,
                        tools=('read_file',), children=('worker',), sources=('/private',), timeout_seconds=120,
                        package_info={'state': 'ready', 'missing': []})
    raw = {**asdict(legacy), 'package_info': {**legacy.package_info, 'definition_digest': definition_digest(legacy)}}
    for home in (a, b):
        directory = home / 'subagents'
        directory.mkdir(parents=True)
        (directory / 'legacy.json').write_text(json.dumps(raw))
    for home in (a, b, a):
        with profile_scope(home):
            path = home / 'subagents/legacy.json'
            before = path.read_bytes()
            item = load('legacy')
            assert item.automatic and not item.enabled and item.needs_review
            assert (item.tools, item.children, item.sources, item.timeout_seconds, item.revision) == (
                legacy.tools, legacy.children, legacy.sources, legacy.timeout_seconds, legacy.revision)
            assert inventory()[0]['legacy'] == item and path.read_bytes() == before
            assert item.package_info['definition_digest'] == definition_digest(item)
    for payload in (raw, {**raw, 'version': 1, 'timeout_seconds': 900}):
        old = replace(legacy, version=payload['version'], timeout_seconds=payload['timeout_seconds'])
        payload = {**payload, 'package_info': {**payload['package_info'], 'definition_digest': definition_digest(old)}}
        upgraded = Specialist.parse(payload)
        assert upgraded.automatic and upgraded.package_info['definition_digest'] == definition_digest(upgraded)
        edited = Specialist.parse({**payload, 'purpose': 'Local edit'})
        assert edited.package_info['definition_digest'] != definition_digest(edited)
    for bad in (None, 0, 'false'):
        with pytest.raises(ValueError, match='automatic'):
            Specialist.parse({**raw, 'automatic': bad})
    assert Specialist.parse({k: v for k, v in raw.items() if k != 'automatic'}).automatic
    with profile_scope(a):
        copied = copy_to(load('legacy'), b, 'copied')
        assert copied.automatic and copied.needs_review and not copied.enabled
        assert not copied.children and not copied.sources
    portable = tmp_path / 'portable.json'
    portable.write_text(json.dumps(raw))
    class UI:
        def show(self, message):
            pass
        def choose(self, question, options):
            assert 'Import' in options
            return 'Import'
    with profile_scope(b):
        import_definition(SimpleNamespace(agent=None), UI(), [str(portable), 'imported'])
        imported = load('imported')
        assert imported.automatic and imported.needs_review and not imported.enabled
        assert not imported.children and not imported.sources


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
    assert copied.needs_review and not copied.enabled and copied.automatic
    assert not copied.children and not copied.sources
    (tmp_path / 'subagents' / 'broken.json').write_text('{')
    items, errors = inventory(tmp_path)
    assert 'reviewer' in items and errors
    with pytest.raises(ValueError):
        delete('reviewer', tmp_path, expected_revision='stale')
    delete('reviewer', tmp_path, expected_revision=item.revision)
    assert 'reviewer' not in inventory(tmp_path)[0]


def test_deadlines_migrate_only_the_old_implicit_default(tmp_path):
    from dataclasses import asdict
    defaults = Specialist('worker', 'Do useful work')
    assert save(defaults, tmp_path).timeout_seconds == 0
    legacy = {**asdict(defaults), 'version': 1, 'timeout_seconds': 900}
    assert Specialist.parse(legacy).timeout_seconds == 0
    assert Specialist.parse({**legacy, 'timeout_seconds': 120}).timeout_seconds == 120
    chosen = Specialist.parse({**legacy, 'version': 2})
    assert chosen.timeout_seconds == 900
    assert Specialist.parse(asdict(chosen)) == chosen
    from sci_cli.subagent_package_install import definition_digest
    package = replace(defaults, version=1, timeout_seconds=900,
                      package_info={'state': 'ready', 'missing': []})
    packaged = {**asdict(package), 'package_info': {**package.package_info, 'definition_digest': definition_digest(package)}}
    migrated = Specialist.parse(packaged)
    assert migrated.package_info['definition_digest'] == definition_digest(migrated)
    edited = Specialist.parse({**packaged, 'purpose': 'A local edit'})
    assert edited.package_info['definition_digest'] != definition_digest(edited)
    with pytest.raises(ValueError, match='version'):
        Specialist.parse({**asdict(defaults), 'version': True})
    for invalid in (-1, True, '0'):
        with pytest.raises(ValueError, match='timeout_seconds'):
            Specialist.parse({**asdict(defaults), 'timeout_seconds': invalid})
