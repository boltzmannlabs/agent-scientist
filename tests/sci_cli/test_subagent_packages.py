"""Portable packages recreate private capabilities without source-profile state or cached-prompt changes."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import shutil

import pytest

from sci_cli.subagent_package_io import seal
from sci_cli.subagent_package_schema import validate
from sci_cli.subagent_package_install import install
from sci_cli.native_profile_creation import profile_scope
from sci_cli.config import atomic_config_replace
from agent.specialist_store import load, save
from agent.specialist_extensions import extension_home


class UI:
    def __init__(self, answers=()):
        self.answers, self.messages = iter(answers), []
    def show(self, value):
        self.messages.append(str(value))
    def ask(self, question, *args, **kwargs):
        return next(self.answers)
    def choose(self, question, choices):
        from sci_cli.skill_add import Cancelled
        answer = next(self.answers)
        assert answer in choices, (question, answer, choices)
        if answer == 'Cancel':
            raise Cancelled()
        return answer


def example(tmp_path):
    source = Path(__file__).resolve().parents[2] / 'contribution-templates/subagent'
    destination = tmp_path / 'package'
    shutil.copytree(source, destination)
    return destination


def owner(home):
    home.mkdir(parents=True)
    atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'terminal', 'skills', 'delegation']},
                                               'plugins': {'enabled': [], 'disabled': []}, 'mcp_servers': {}})


def test_package_install_a_b_a_private_scope_conflicts_updates_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / n for n in ('main', 'different-project')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    for home in homes:
        owner(home)
    package = example(tmp_path)
    agent = SimpleNamespace(system_prompt='cached-prefix', tools=[{'name': 'original'}])
    cli = SimpleNamespace(agent=agent)
    created = []
    for home in homes:
        before = (home / 'config.yaml').read_bytes()
        with profile_scope(home):
            item = install(package, home, cli, UI(['Prepare package', 'Save and enable for the next conversation']))
            assert item.enabled and item.package_info['state'] == 'ready'
            assert item.private_skills == ('table-quality',)
            assert item.tools == ('read_file',)
            assert load(item.name).revision == item.revision
            assert (extension_home(item) / 'skills/table-quality/SKILL.md').is_file()
            assert not (extension_home(item) / '.env').exists()
            created.append(item)
        assert (home / 'config.yaml').read_bytes() == before
    assert created[0].extension_id != created[1].extension_id
    assert agent.system_prompt == 'cached-prefix' and agent.tools == [{'name': 'original'}]
    with profile_scope(homes[0]):
        assert load('table-reviewer').extension_id == created[0].extension_id
        # User changes stay authoritative: a higher package version must not overwrite them.
        import sci_yaml as yaml
        manifest_path = package / 'manifest.yaml'
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest['version'] = '1.1.0'
        manifest_path.write_text(yaml.safe_dump(manifest))
        seal(package)
        edited = save(replace(load('table-reviewer'), instructions='My local customization'), expected_revision=load('table-reviewer').revision)
        from sci_cli.skill_add import Cancelled
        with pytest.raises(Cancelled):
            install(package, homes[0], cli, UI(['Cancel']))
        assert load('table-reviewer').revision == edited.revision
        installed = install(package, homes[0], cli, UI(['Rename', 'table-reviewer-company', 'Prepare package', 'Save and enable for the next conversation']))
        assert installed.name == 'table-reviewer-company'
        manifest['version'] = '1.2.0'
        manifest_path.write_text(yaml.safe_dump(manifest)); seal(package)
        updated = install(package, homes[0], cli, UI(['Review managed update', 'Prepare package', 'Save and enable for the next conversation']), name=installed.name)
        assert updated.package_info['version'] == '1.2.0'
        assert updated.extension_id != installed.extension_id
        assert load('table-reviewer').instructions == 'My local customization'


def test_manually_prepared_profile_contribution_installs_without_source_credentials_or_locks(tmp_path, monkeypatch):
    from sci_cli.specialist_private_setup import prepare_home
    from agent.specialist_store import Specialist
    from agent.specialist_extensions import fingerprint
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'project-a', tmp_path / 'project-b'
    monkeypatch.setenv('SCI_HOME', str(a))
    owner(a); owner(b)
    cli = SimpleNamespace(agent=None)
    with profile_scope(a):
        item, private = prepare_home(Specialist('my-reviewer', 'Review assigned tables', tools=('read_file',)))
        skill = private / 'skills/my-quality'; skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: my-quality\ndescription: Review table quality\n---\nRead references/check.md and inspect the assigned table.\n')
        (skill / 'references').mkdir(); (skill / 'references/check.md').write_text('Do not alter original data.')
        (private / '.env').write_text('PRIVATE_KEY=never-distribute-this-secret\n')
        save(replace(item, skills=('my-quality',), private_skills=('my-quality',), extension_revision=fingerprint(private)))
        destination = example(tmp_path)
        import sci_yaml as yaml
        manifest_path = destination / 'manifest.yaml'
        manifest = yaml.safe_load(manifest_path.read_text())
        manifest.update(id='my-reviewer', name='my-reviewer', skills=[{'id':'my-quality','kind':'package','path':'skills/my-quality'}])
        manifest_path.write_text(yaml.safe_dump(manifest))
        shutil.rmtree(destination / 'skills')
        shutil.copytree(skill, destination / 'skills/my-quality')
        # Contributors assemble approved source files themselves; no exporter or sealing command.
        assert not (destination / 'files.lock.json').exists()
    manifest, files, _ = validate(destination)
    assert 'skills/my-quality/references/check.md' in files
    assert not any(b'never-distribute' in value or str(a).encode() in value for value in files.values())
    with profile_scope(b):
        installed = install(destination, b, cli, UI(['Prepare package', 'Save and enable for the next conversation']))
        assert installed.enabled
        assert installed.private_skills == ('my-quality',)
        assert extension_home(installed).parent == b / 'subagent-data'
        assert load(installed.name).package_info['id'] == manifest['id']
        validate(extension_home(installed) / 'package', require_lock=True)
