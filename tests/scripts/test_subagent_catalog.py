"""Source-only PRs stay independent; maintainer promotion checks evidence, versions and snapshots."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest


def git(repo, *args):
    return subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()


def commit(repo, message):
    git(repo,'add','subagent-catalog')
    git(repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm',message)
    return git(repo,'rev-parse','HEAD')


def world(tmp_path, monkeypatch):
    from scripts import validate_subagent_catalog as command
    import sci_cli.subagent_package_catalog as catalog
    repo=tmp_path / 'repo';repo.mkdir()
    git(repo,'init','-q')
    root=repo / 'subagent-catalog/table-reviewer'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent',root)
    report_path = root / 'tests/validation.json'
    fixture_report = json.loads(report_path.read_text())
    fixture_report['local'] = {'status':'passed', 'environment':'Isolated test fixture', 'checks':['Fixture test evidence']}
    report_path.write_text(json.dumps(fixture_report))
    monkeypatch.setattr(command,'ROOT',repo)
    monkeypatch.setattr(catalog,'CATALOG',root.parent)
    monkeypatch.setattr(catalog,'SNAPSHOT',repo / 'release-catalog.json')
    return repo, root, command


def test_dev_checks_source_without_forcing_shared_snapshot_edits(tmp_path, monkeypatch):
    import sci_yaml as yaml
    repo, root, command=world(tmp_path,monkeypatch)
    base=commit(repo,'Initial package')
    command.main(['--write-snapshot'])
    command.main(['--check-snapshot'])
    # Spelling the same semantic version differently cannot authorize changed code.
    manifest=yaml.safe_load((root / 'manifest.yaml').read_text());manifest['version']='1.0'
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    with pytest.raises(ValueError, match='higher version'):
        command.main(['--base', base])
    manifest=yaml.safe_load((root / 'manifest.yaml').read_text());manifest['version']='1.1.0'
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    report=json.loads((root / 'tests/validation.json').read_text());report['package_version']='1.1.0'
    (root / 'tests/validation.json').write_text(json.dumps(report))
    (root / 'instructions.md').write_text('Review the assigned CSV using only read_file and the declared skill.')
    command.main(['--base',base])  # No contributor snapshot regeneration required.
    with pytest.raises(ValueError,match='snapshot is stale'):
        command.main(['--base',base,'--check-snapshot'])
    command.main(['--base',base,'--write-snapshot'])
    command.main(['--base',base,'--check-snapshot'])


def test_main_promotion_accepts_pending_integrated_receipts_but_checks_versions_and_snapshot(tmp_path, monkeypatch):
    repo, root, command = world(tmp_path, monkeypatch)
    base = commit(repo, 'Locally tested package merged to dev')
    path = root / 'tests/validation.json'
    report = json.loads(path.read_text())
    report['local']['environment'] += '; evidence retained for maintainer review'
    path.write_text(json.dumps(report), encoding='utf-8')
    assert report['integrated']['status'] == 'pending'
    command.main(['--base', base, '--promotion', '--write-snapshot'])
    command.main(['--base', base, '--promotion'])
    assert json.loads(path.read_text()) == report  # Confirmation never invents a test receipt.

    (root / 'instructions.md').write_text('New instructions', encoding='utf-8')
    with pytest.raises(ValueError, match='higher version'):
        command.main(['--base', base, '--promotion'])
    import sci_yaml as yaml
    manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
    manifest['version'] = '1.1.0'
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    report['package_version'] = manifest['version']
    path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot is stale'):
        command.main(['--base', base, '--promotion'])
    command.main(['--base', base, '--promotion', '--write-snapshot'])
    command.main(['--base', base, '--promotion', '--check-snapshot'])


def test_promotion_snapshot_tracks_transitive_child_versions_without_followup_receipts(tmp_path, monkeypatch):
    import sci_yaml as yaml
    repo, root, command = world(tmp_path, monkeypatch)
    child = root.parent / 'reader'
    middle = root.parent / 'coordinator'
    shutil.copytree(root, child)
    shutil.copytree(root, middle)
    manifests, reports = {}, {}
    members = ((root, 'table-reviewer'), (middle, 'coordinator'), (child, 'reader'))
    for folder, identity in members:
        value = yaml.safe_load((folder / 'manifest.yaml').read_text())
        value.update(schema_version=2, id=identity, name=identity)
        if folder == root:
            value.update(children=[{'role': 'coordinate', 'package': 'coordinator', 'version': '>=1,<2'}], tools=['delegate_task'])
        elif folder == middle:
            value.update(children=[{'role': 'read', 'package': 'reader', 'version': '>=1,<2'}], tools=['delegate_task'])
        (folder / 'manifest.yaml').write_text(yaml.safe_dump(value), encoding='utf-8')
        report = json.loads((folder / 'tests/validation.json').read_text())
        report['package_id'] = identity
        (folder / 'tests/validation.json').write_text(json.dumps(report), encoding='utf-8')
        manifests[identity], reports[identity] = value, report
    base = commit(repo, 'Original hierarchy')
    command.main(['--base', base, '--promotion', '--write-snapshot'])
    manifests['reader']['version'] = '1.1.0'
    reports['reader']['package_version'] = manifests['reader']['version']
    (child / 'manifest.yaml').write_text(yaml.safe_dump(manifests['reader']), encoding='utf-8')
    (child / 'instructions.md').write_text('Updated child behavior', encoding='utf-8')
    (child / 'tests/validation.json').write_text(json.dumps(reports['reader']), encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot is stale'):
        command.main(['--base', base, '--promotion'])
    command.main(['--base', base, '--promotion', '--write-snapshot'])
    command.main(['--base', base, '--promotion'])
    snapshot = json.loads((repo / 'release-catalog.json').read_text())
    assert snapshot['reader']['manifest']['version'] == manifests['reader']['version']
    assert all(json.loads((folder / 'tests/validation.json').read_text())['integrated']['status'] == 'pending'
               for folder, _ in members)
