"""Reject unsafe or nonportable packages before any installation or service call."""
from pathlib import Path
import shutil
import stat
import zipfile

import pytest

from sci_cli.subagent_package_io import seal, open_package
from sci_cli.subagent_package_schema import validate


def source(tmp_path):
    package = tmp_path / 'package'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', package)
    return package


@pytest.mark.parametrize('case', ['tamper', 'secret', 'local-path', 'hidden-state', 'symlink', 'unknown-field',
                                  'draft', 'unknown-token', 'wrong-kind-token', 'credential-url', 'missing-fixture', 'blocked-tool'])
def test_validation_rejects_unreviewed_or_nonportable_content(tmp_path, case):
    import sci_yaml as yaml
    package = source(tmp_path)
    text = {'secret': 'api_key: sk-' + 'A' * 30, 'local-path': '/home/contributor/private/data.csv',
            'unknown-token': '{{program.absent}}', 'wrong-kind-token': '{{program.remote}}',
            'credential-url': 'https://name:password@example.com/file'}
    if case in text:
        (package / 'instructions.md').write_text(text[case])
    manifest_path = package / 'manifest.yaml'
    manifest = yaml.safe_load(manifest_path.read_text())
    if case == 'wrong-kind-token':
        manifest['dependencies'] = [{'id': 'remote', 'kind': 'mcp', 'tools': ['lookup'], 'config': {'url': 'https://example.com/mcp'}}]
    if case == 'hidden-state':
        (package / '.env').write_text('NOT_A_SECRET=value')
    if case == 'symlink':
        (package / 'link').symlink_to(package / 'instructions.md')
    if case == 'unknown-field':
        manifest['run_on_install'] = 'arbitrary script'
    if case == 'draft':
        manifest['unresolved'] = ['An undeclared external integration']
    if case == 'missing-fixture':
        manifest['fixtures'] = []
    if case == 'blocked-tool':
        manifest['tools'] = ['manage_connections']
    manifest_path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(ValueError):
        seal(package)
        if case == 'tamper':
            (package / 'instructions.md').write_text('Changed without review')
        validate(package)


@pytest.mark.parametrize('case', ['traversal', 'symlink', 'case-collision', 'valid'])
def test_zip_extraction_checks_integrity_and_never_executes_resources(tmp_path, case):
    package = source(tmp_path)
    archive = tmp_path / 'package.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        for file in package.rglob('*'):
            if file.is_file():
                z.write(file, file.relative_to(package))
        if case == 'traversal':
            z.writestr('../escape.txt', 'bad')
        if case == 'symlink':
            entry = zipfile.ZipInfo('link'); entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(entry, 'instructions.md')
        if case == 'case-collision':
            z.writestr('Instructions.md', 'duplicate')
    if case == 'valid':
        with open_package(archive) as root:
            manifest, _, _ = validate(root)
            assert manifest['id'] == 'table-reviewer'
        assert not root.exists()
    else:
        with pytest.raises(ValueError):
            with open_package(archive):
                pytest.fail('Unsafe archive was extracted')
    assert not (tmp_path / 'escape.txt').exists()
