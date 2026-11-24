"""Local evidence stays required; merged-dev confirmation is reviewed by maintainers."""
from pathlib import Path
import json
import shutil

import pytest

from sci_cli.subagent_package_schema import validate
from sci_cli.subagent_package_review import evidence


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


@pytest.mark.parametrize('integrated', [None, {'status': 'pending', 'tested_commit': None},
    {'status': 'passed', 'tested_commit': 'historical-reference', 'checks': ['Retained historical report']}])
def test_review_preserves_optional_integration_history(tmp_path, integrated):
    root = tmp_path / 'table-reviewer'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', root)
    path = root / 'tests/validation.json'
    report = json.loads(path.read_text())
    report['local'] = {'status': 'passed', 'environment': 'Isolated fixture', 'checks': ['Fixture calculation']}
    report.pop('integrated', None)
    if integrated is not None:
        report['integrated'] = integrated
    path.write_text(json.dumps(report), encoding='utf-8')
    before = path.read_bytes()
    manifest, _, _ = validate(root)
    evidence(root, manifest)
    assert path.read_bytes() == before
