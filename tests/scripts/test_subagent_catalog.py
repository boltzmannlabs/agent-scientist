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


def test_main_promotion_requires_tested_dev_content_without_evidence_version_loop(tmp_path, monkeypatch):
    repo, root, command=world(tmp_path,monkeypatch)
    base=commit(repo,'Package under test on dev')
    git(repo,'update-ref','refs/remotes/origin/dev',base)
    # Main promotion cannot claim an integrated test which was never performed/reported.
    path=root / 'tests/validation.json'
    report=json.loads(path.read_text())
    report['local']['environment']+='; evidence update'
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='Integrated dev validation'):
        command.main(['--base',base,'--promotion','--write-snapshot'])
    report['integrated']={'status':'passed','tested_commit':base,'environment':'Fixture Linux isolated home',
                          'checks':['Recorded integration fixture checks']}
    path.write_text(json.dumps(report))
    # Evidence-only updates are accepted at the same version; otherwise testing loops forever.
    command.main(['--base',base,'--promotion','--write-snapshot'])
    command.main(['--base',base,'--promotion','--check-snapshot'])
    (root / 'instructions.md').write_text('New instructions after testing')
    with pytest.raises(ValueError,match='higher version'):
        command.main(['--base',base,'--promotion'])
    import sci_yaml as yaml
    manifest=yaml.safe_load((root / 'manifest.yaml').read_text());manifest['version']='1.1.0'
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    report['package_version']='1.1.0';path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='changed since'):
        command.main(['--base',base,'--promotion'])
