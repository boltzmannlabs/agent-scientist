"""Local contribution evidence; maintainers review merged-dev test confirmations."""
import json
from pathlib import Path


def evidence(root, manifest):
    path = Path(root) / 'tests/validation.json'
    try:
        report = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError('Provide tests/validation.json using the contribution template.') from exc
    if not isinstance(report, dict) or report.get('package_id') != manifest['id'] or report.get('package_version') != manifest['version']:
        raise ValueError('Validation evidence must identify this exact package ID/version.')
    local = report.get('local', {})
    _passed(local, 'Local validation')


def _passed(section, label):
    if not isinstance(section, dict) or section.get('status') != 'passed' or not isinstance(section.get('environment'), str) or not section['environment'].strip():
        raise ValueError(label + ' needs passed status and an environment description.')
    checks = section.get('checks')
    if not isinstance(checks, list) or not checks or any(not isinstance(v, str) or not v.strip() for v in checks):
        raise ValueError(label + ' needs the checks actually performed.')
