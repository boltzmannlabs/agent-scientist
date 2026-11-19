"""Inert contributor evidence and exact-dev-commit checks for main promotion."""
import json
from pathlib import Path
import re
import subprocess


def evidence(root, manifest, *, repo=None, dev_ref='refs/remotes/origin/dev', packages=None):
    path = Path(root) / 'tests/validation.json'
    try:
        report = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError('Provide tests/validation.json using the contribution template.') from exc
    if not isinstance(report, dict) or report.get('package_id') != manifest['id'] or report.get('package_version') != manifest['version']:
        raise ValueError('Validation evidence must identify this exact package ID/version.')
    local = report.get('local', {})
    _passed(local, 'Local validation')
    if repo is None:
        return
    integrated = report.get('integrated', {})
    _passed(integrated, 'Integrated dev validation')
    commit = integrated.get('tested_commit')
    if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Integrated validation requires the full tested dev commit SHA.')
    repo = Path(repo)
    def git(*args):
        return subprocess.run(['git', *args], cwd=repo, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if git('cat-file', '-e', commit + '^{commit}').returncode or git('merge-base', '--is-ancestor', commit, dev_ref).returncode:
        raise ValueError('Tested commit must exist in the fetched dev branch history.')
    roots = [Path(root)]
    if manifest.get('children'):
        if packages is None:
            from sci_cli.subagent_package_hierarchy import _sources
            _, packages = _sources(root, 'local validation')
        from sci_cli.subagent_package_graph import resolve_graph
        roots = [Path(packages[key]['path']) for key in resolve_graph(packages, [manifest['id']])]
    paths = []
    for folder in roots:
        relative = folder.resolve().relative_to(repo.resolve()).as_posix()
        paths += [relative, ':(exclude)' + relative + '/tests/validation.json',
                  ':(exclude)' + relative + '/files.lock.json']
    result = git('diff', '--exit-code', commit, '--', *paths)
    if result.returncode:
        raise ValueError('Package or its child hierarchy changed since the tested dev commit; '
                         'repeat integrated validation before main promotion.')


def _passed(section, label):
    if not isinstance(section, dict) or section.get('status') != 'passed' or not isinstance(section.get('environment'), str) or not section['environment'].strip():
        raise ValueError(label + ' needs passed status and an environment description.')
    checks = section.get('checks')
    if not isinstance(checks, list) or not checks or any(not isinstance(v, str) or not v.strip() for v in checks):
        raise ValueError(label + ' needs the checks actually performed.')
