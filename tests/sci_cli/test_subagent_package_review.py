"""Dev contributions and main promotion accept exact tested content, not stale or invented evidence."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest

from sci_cli.subagent_package_schema import validate
from sci_cli.subagent_package_review import evidence


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def record(repo, message):
    git(repo,'add','subagent-catalog')
    git(repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm',message)
    return git(repo,'rev-parse','HEAD')


def test_source_packages_need_no_generated_artifacts_but_require_real_local_evidence(tmp_path):
    root = tmp_path / 'table-reviewer'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', root)
    report_path = root / 'tests/validation.json'
    fixture_report = json.loads(report_path.read_text())
    fixture_report['local'] = {'status':'passed', 'environment':'Isolated test fixture', 'checks':['Fixture test evidence']}
    report_path.write_text(json.dumps(fixture_report))
    manifest, _, _ = validate(root)
    assert not (root / 'files.lock.json').exists()
    evidence(root,manifest)
    template = Path(__file__).resolve().parents[2] / 'contribution-templates/subagent'
    template_manifest, _, _ = validate(template)
    with pytest.raises(ValueError, match='Local validation'):
        evidence(template, template_manifest)  # A blank template must never count as passed testing.
    report_path=root / 'tests/validation.json'
    report=json.loads(report_path.read_text())
    for mutation in ('failed','empty_checks','wrong_version'):
        value=json.loads(json.dumps(report))
        if mutation=='failed':
            value['local']['status']='failed'
        if mutation=='empty_checks':
            value['local']['checks']=[]
        if mutation=='wrong_version':
            value['package_version']='99.0.0'
        report_path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            evidence(root,manifest)


def test_main_promotion_checks_fetched_dev_commit_and_identical_package_content(tmp_path):
    repo=tmp_path / 'repo';repo.mkdir()
    git(repo,'init','-q')
    root=repo / 'subagent-catalog/table-reviewer'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent',root)
    report_path = root / 'tests/validation.json'
    fixture_report = json.loads(report_path.read_text())
    fixture_report['local'] = {'status':'passed', 'environment':'Isolated test fixture', 'checks':['Fixture test evidence']}
    report_path.write_text(json.dumps(fixture_report))
    dev=record(repo,'Package on dev')
    git(repo,'update-ref','refs/remotes/origin/dev',dev)
    manifest, _, _=validate(root)
    with pytest.raises(ValueError,match='Integrated dev validation'):
        evidence(root,manifest,repo=repo)
    path=root / 'tests/validation.json'
    report=json.loads(path.read_text())
    report['integrated']={'status':'passed','tested_commit':dev,'environment':'Linux isolated SCI_HOME, local fixture',
                          'checks':['Install selected catalog package, execute fixture, inspect outputs and authorization failures']}
    path.write_text(json.dumps(report))
    record(repo,'Validation evidence only')
    evidence(root,manifest,repo=repo)
    # Arbitrary existing commits outside dev, and changed instructions after testing, both fail.
    report['integrated']['tested_commit']='f'*40
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='fetched dev'):
        evidence(root,manifest,repo=repo)
    report['integrated']['tested_commit']=dev;path.write_text(json.dumps(report))
    (root / 'instructions.md').write_text('Changed after testing')
    with pytest.raises(ValueError,match='changed since'):
        evidence(root,manifest,repo=repo)
    git(repo,'checkout',dev,'--',str(root.relative_to(repo) / 'instructions.md'))
    evidence(root,manifest,repo=repo)
