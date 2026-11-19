"""Regression for #54: reviewed package graphs survive install, updates and profile switches."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import shutil
import sys

import pytest
import sci_yaml as yaml

from agent.specialist_store import Specialist, inventory, load, save
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope
from sci_cli.subagent_package_install import install
from sci_cli.subagent_package_schema import validate

pytestmark = pytest.mark.usefixtures('released_sci_version')


def package(parent, name, children=()):
    root = parent / name
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', root)
    manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
    manifest.update(schema_version=2, id=name, name=name, children=list(children),
                    tools=['delegate_task'] if children else ['read_file'])
    manifest['limits']['timeout_seconds'] = 0
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    if children:
        (root / 'instructions.md').write_text('Delegate to ' + ', '.join('{{child.' + c['role'] + '}}' for c in children))
    return root


def child(role, name, version='>=1.0,<2'):
    return {'role': role, 'package': name, 'version': version}


class UI:
    def __init__(self, cancel=None, defer=False):
        self.messages, self.cancel, self.defer = [], cancel, defer
        self.decisions = []

    def show(self, value):
        self.messages.append(str(value))

    def choose(self, question, choices):
        self.decisions.append((question, list(choices)))
        if self.cancel and self.cancel in question:
            from sci_cli.skill_add import Cancelled
            raise Cancelled()
        if self.defer and 'Defer setup' in choices:
            return 'Defer setup'
        return choices[0]

    def ask(self, question, *args, **kwargs):
        if 'executable' in question.lower():
            return sys.executable
        raise AssertionError('No manual child naming should be necessary')


@pytest.mark.parametrize('case', ['valid', 'shared-alias', 'missing', 'incompatible', 'cycle', 'duplicate-role',
    'invalid-version', 'legacy-children', 'legacy-leaf', 'unknown-role', 'negative-timeout', 'boolean-timeout',
    'zero-iterations', 'unknown-schema', 'invalid-child'])
def test_portable_hierarchy_declares_versions_and_retains_no_deadline(tmp_path, case):
    from sci_cli.subagent_package_graph import resolve_graph
    leaf = package(tmp_path, 'reader')
    root = package(tmp_path, 'lead', [child('reader', 'reader')])
    value = yaml.safe_load((root / 'manifest.yaml').read_text())
    if case == 'shared-alias':
        value['children'].append(child('review', 'reader'))
    if case == 'missing':
        value['children'][0]['package'] = 'absent'
    if case == 'incompatible':
        value['children'][0]['version'] = '>=2'
    if case == 'cycle':
        other = yaml.safe_load((leaf / 'manifest.yaml').read_text())
        other.update(children=[child('lead', 'lead')], tools=['delegate_task'])
        (leaf / 'manifest.yaml').write_text(yaml.safe_dump(other))
    if case == 'duplicate-role':
        value['children'].append(child('reader', 'reader'))
    if case == 'invalid-version':
        value['children'][0]['version'] = '1.0'
    if case == 'legacy-children':
        value['schema_version'], value['limits']['timeout_seconds'] = 1, 60
    if case == 'unknown-role':
        (root / 'instructions.md').write_text('Use {{child.undeclared}}')
    if case == 'negative-timeout':
        value['limits']['timeout_seconds'] = -1
    if case == 'boolean-timeout':
        value['limits']['timeout_seconds'] = False
    if case == 'zero-iterations':
        value['limits']['max_iterations'] = 0
    if case == 'unknown-schema':
        value['schema_version'] = 3
    if case == 'invalid-child':
        value['children'] = ['reader']
    if case == 'legacy-leaf':
        value.update(schema_version=1, children=[])
        value['limits']['timeout_seconds'] = 60
        (root / 'instructions.md').write_text('Read the supplied table')
    (root / 'manifest.yaml').write_text(yaml.safe_dump(value))

    def resolve():
        rows = {}
        for path in (root, leaf):
            manifest, _, digest = validate(path)
            rows[manifest['id']] = {'manifest': manifest, 'digest': digest, 'path': str(path)}
        return resolve_graph(rows, ['lead'])

    if case in {'valid', 'shared-alias', 'legacy-leaf'}:
        assert resolve() == (['lead'] if case == 'legacy-leaf' else ['reader', 'lead'])
    else:
        with pytest.raises(ValueError):
            resolve()


def test_hierarchy_install_update_recovery_and_scope_a_b_a(tmp_path, monkeypatch):
    from agent.specialist_extensions import extension_home
    from sci_cli.subagent_package_graph import installed_problem
    from sci_cli.skill_add import Cancelled
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'profile-a', tmp_path / 'different-profile'
    monkeypatch.setenv('SCI_HOME', str(a))
    for home in (a, b):
        home.mkdir()
        atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'skills', 'delegation']},
            'plugins': {'enabled': [], 'disabled': []}, 'mcp_servers': {}, 'memory': {'enabled': False}})
    sources = tmp_path / 'packages'; sources.mkdir()
    reader = package(sources, 'reader')
    package(sources, 'coordinator', [child('read', 'reader')])
    root = package(sources, 'lead', [child('coordinate', 'coordinator'), child('read', 'reader')])
    cli = SimpleNamespace(agent=SimpleNamespace(tools=['frozen'], _cached_system_prompt='unchanged'))
    saved = []
    for home in (a, b, a):
        with profile_scope(home):
            if home == a and saved:
                current = load('my-team')
                assert current.extension_id == saved[0].extension_id
                assert installed_problem(current) is None
                continue
            # A conflicting unmanaged name must never become an implicit child.
            collision = save(Specialist(
                'my-team-reader', 'Unrelated local specialist', instructions='KEEP_ME'))
            item = install(root, home, cli, UI(), name='my-team')
            assert item.enabled and installed_problem(item) is None
            assert load(collision.name).revision == collision.revision
            nodes = inventory()[0]
            assert len(nodes) == 4, nodes  # shared reader installed once, plus the unrelated collision
            assert all(n.package_info['state'] == 'ready' for n in nodes.values() if n.name != collision.name)
            assert all('{{child.' not in n.instructions for n in nodes.values())
            assert all(extension_home(n).parent == home / 'subagent-data' for n in nodes.values() if n.extension_id)
            saved.append(item)
    assert saved[0].extension_id != saved[1].extension_id
    assert cli.agent.tools == ['frozen'] and cli.agent._cached_system_prompt == 'unchanged'
    with profile_scope(a):
        old = load('my-team')
        old_nodes = {n.name: n for n in inventory()[0].values()}
        # Child-only repairs cannot bypass immutable versions for parent behavior changes.
        instructions = (root / 'instructions.md').read_text()
        (root / 'instructions.md').write_text(instructions + '\nChanged behavior without a version bump')
        conflict = UI(cancel='Name/version conflict')
        with pytest.raises(Cancelled):
            install(root, a, cli, conflict, name=old.name)
        assert 'Review managed update' not in next(choices for q, choices in conflict.decisions if q == 'Name/version conflict')
        (root / 'instructions.md').write_text(instructions)
        manifest = yaml.safe_load((reader / 'manifest.yaml').read_text())
        manifest['version'] = '1.1.0'
        (reader / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
        (reader / 'instructions.md').write_text('Updated reader instructions')
        old_reader = next(n for n in old_nodes.values() if n.package_info.get('id') == 'reader')
        child_conflict = UI(cancel='Name/version conflict')
        with pytest.raises(Cancelled):
            install(reader, a, cli, child_conflict, name=old_reader.name)
        assert 'Review managed update' not in next(choices for q, choices in child_conflict.decisions if q == 'Name/version conflict')
        assert load(old_reader.name).revision == old_reader.revision
        import sci_cli.subagent_package_catalog as catalog
        monkeypatch.setattr(catalog, 'CATALOG', sources)
        view = UI()
        catalog.updates(view)
        assert any('my-team:' in m and 'hierarchy update available' in m for m in view.messages)
        with pytest.raises(Cancelled):
            install(root, a, cli, UI(cancel='Prepare this package'), name=old.name)
        assert {n.name: n.revision for n in inventory()[0].values()} == {n: v.revision for n, v in old_nodes.items()}
        # A setup failure while updating must preserve the previously working team.
        manifest['tools'] = ['missing_fixture_tool']
        (reader / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
        with pytest.raises(ValueError, match='preserv'):
            install(root, a, cli, UI(), name=old.name)
        assert load(old.name).revision == old.revision and installed_problem(old) is None
        manifest['tools'] = ['read_file']
        (reader / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
        # A failure while publishing new children must not replace the old parent.
        import sci_cli.subagent_package_hierarchy as hierarchy
        real_save = hierarchy.save
        def fail_parent(item, **kwargs):
            if item.name == old.name:
                raise OSError('controlled parent publication failure')
            return real_save(item, **kwargs)
        with monkeypatch.context() as fault:
            fault.setattr(hierarchy, 'save', fail_parent)
            with pytest.raises(OSError, match='publication failure'):
                install(root, a, cli, UI(), name=old.name)
        assert load(old.name).revision == old.revision and installed_problem(old) is None
        updated = install(root, a, cli, UI(), name=old.name)
        assert updated.revision != old.revision and updated.package_info['version'] == old.package_info['version']
        assert installed_problem(updated) is None
        for name, item in old_nodes.items():
            if name != old.name:
                assert load(name).revision == item.revision  # no in-place child replacement
        # Evidence-only changes may be reviewed at the same execution version.
        evidence_file = root / 'tests/validation.json'
        evidence_file.write_text(evidence_file.read_text() + '\n')
        evidence_update = install(root, a, cli, UI(), name=updated.name)
        assert evidence_update.children == updated.children and evidence_update.package_info['version'] == updated.package_info['version']
        updated = evidence_update
        member = load(updated.children[0])
        # User-reviewed instruction changes are not a broken package relationship.
        edited_member = save(replace(member, instructions='My reviewed coordinator instructions'), expected_revision=member.revision)
        assert installed_problem(updated) is None
        save(replace(edited_member, enabled=False), expected_revision=edited_member.revision)
        assert 'disabled' in installed_problem(updated).lower()
        customized = save(replace(updated, instructions='Keep my local instructions'), expected_revision=updated.revision)
        with pytest.raises(Cancelled):
            install(root, a, cli, UI(cancel='Name/version conflict'), name=updated.name)
        assert load(updated.name).revision == customized.revision
        # An initially incomplete team retains private setup and resumes in place.
        program = package(sources, 'program-reader')
        program_manifest = yaml.safe_load((program / 'manifest.yaml').read_text())
        program_manifest['dependencies'] = [{'id': 'python', 'kind': 'program', 'version': sys.version.split()[0],
            'version_args': ['--version'], 'version_contains': sys.version.split()[0], 'artifacts': []}]
        (program / 'manifest.yaml').write_text(yaml.safe_dump(program_manifest))
        program_root = package(sources, 'program-lead', [child('reader', 'program-reader')])
        pending = install(program_root, a, cli, UI(defer=True))
        assert not pending.enabled and pending.package_info['state'] == 'setup_required'
        pending_child = load(pending.children[0])
        ready = install(program_root, a, cli, UI())
        assert ready.enabled and installed_problem(ready) is None
        assert ready.extension_id == pending.extension_id
        assert load(ready.children[0]).extension_id == pending_child.extension_id
    with profile_scope(b):
        assert load('my-team').revision == saved[1].revision
        assert installed_problem(load('my-team')) is None
