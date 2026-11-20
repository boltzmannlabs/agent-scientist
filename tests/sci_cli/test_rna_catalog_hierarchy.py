"""Portable RNA packages install through native child bindings without creator state."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import shutil

import pytest

from agent.specialist_store import load
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope
from sci_cli.subagent_package_graph import installed_problem
from sci_cli.subagent_package_install import install

pytestmark = pytest.mark.usefixtures('released_sci_version')


class MetadataOnlyUI:
    def __init__(self):
        self.messages = []

    def show(self, text):
        self.messages.append(str(text))

    def choose(self, question, choices):
        # Exercise actual installation while leaving every optional program/service unconfigured.
        if 'Defer setup' in choices:
            return 'Defer setup'
        return 'Done' if 'Done' in choices else choices[0]

    def ask(self, *args, **kwargs):
        raise AssertionError('Native hierarchy setup must not require creator paths or credentials')


def test_rna_hierarchy_installs_renamed_children_in_owner_a_b_a(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    sources = Path(__file__).resolve().parents[2] / 'subagent-catalog'
    a, b = tmp_path / 'owner-a', tmp_path / 'owner-b'
    monkeypatch.setenv('SCI_HOME', str(a))
    for owner in (a, b):
        owner.mkdir()
        atomic_config_replace(owner / 'config.yaml', {
            'platform_toolsets': {'cli': ['file', 'terminal', 'code_execution', 'skills', 'delegation']},
            'plugins': {'enabled': [], 'disabled': []}, 'mcp_servers': {}, 'memory': {'enabled': False},
            'delegation': {'max_spawn_depth': 3}})
        (owner / '.env').write_text('PRIVATE_FIXTURE_KEY=owner-only\n', encoding='utf-8')
    cli = SimpleNamespace(agent=SimpleNamespace(tools=['cached'], _cached_system_prompt='frozen'))
    installed = []
    for owner in (a, b, a):
        with profile_scope(owner):
            if owner == a and installed:
                item = load('my-rna')
                assert item.revision == installed[0].revision
            else:
                ui = MetadataOnlyUI()
                item = install(sources / 'rna-agent', owner, cli, ui, name='my-rna')
                assert item.enabled, ui.messages
                installed.append(item)
            assert installed_problem(item) is None
            bindings = item.package_info['resolved']['@children']
            assert set(item.children) == {row['name'] for row in bindings.values()}
            assert 'delegate_task' in item.tools and '{{child.' not in item.instructions
            for row in bindings.values():
                child = load(row['name'])
                assert child.package_info['id'] == row['package']
                assert child.name in item.instructions
                assert not child.children
            assert (owner / '.env').read_text(encoding='utf-8-sig') == 'PRIVATE_FIXTURE_KEY=owner-only\n'
    assert installed[0].extension_id != installed[1].extension_id
    assert cli.agent.tools == ['cached'] and cli.agent._cached_system_prompt == 'frozen'


def test_dependency_bindings_use_only_owning_profile_and_installed_child_names(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'subagent-catalog/rna-agent/scripts/dependency_plan.py'
    spec = importlib.util.spec_from_file_location('rna_dependency_scope_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    package = 'rna-model-discovery'
    bindings = {package: 'my-rna-discovery'}
    a, b, main = tmp_path / 'a', tmp_path / 'b', tmp_path / '.sci'
    for owner in (a, b, main):
        definitions = owner / 'subagents'; definitions.mkdir(parents=True)
        (definitions / 'my-rna-discovery.json').write_text(json.dumps({
            'package_info': {'id': package, 'resolved': {'python_core': {'path': str(owner / 'python')}}}}), encoding='utf-8')
    (main / 'active_profile').write_text('b', encoding='utf-8')
    for owner in (a, b, a):
        monkeypatch.setenv('SCI_HOME', str(owner / 'subagent-data' / 'coordinator'))
        assert module.bound_programs(package, bindings) == {'python_core': str(owner / 'python')}
        assert module.bound_programs(package) == {}  # No borrowing an unbound creator-local name.
    shutil.rmtree(a / 'subagents')
    assert module.bound_programs(package, bindings) == {}
    monkeypatch.delenv('SCI_HOME')
    assert module.bound_programs(package, bindings) == {}
