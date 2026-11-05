"""Retained private installs reconcile shared defaults and survive failed finalization."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.specialist_store import Specialist, save, load
from agent.specialist_sources import DEFAULT_TOOLS
from agent.specialist_extensions import extension_home, fingerprint
from sci_cli.specialist_private_setup import prepare_home, setup
from sci_cli.specialist_editor_state import drafts
from sci_cli.specialist_commands import dispatch


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, message):
        self.messages.append(message)
    def ask(self, question, *args, **kwargs):
        from sci_cli.skill_add import Cancelled
        answer = next(self.answers)
        if answer == 'Cancel':
            raise Cancelled()
        return answer
    def choose(self, question, choices):
        answer = self.ask(question)
        assert answer in choices, (question, answer, choices)
        return answer


def installed(home, name):
    directory = home / 'skills' / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Read the approved fixture\n---\nUse only supplied fixture inputs.\n')


def test_review_retained_additions_without_reinstall_or_automatic_grants_a_b_a(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import profile_scope
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / n for n in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    for owner in homes:
        owner.mkdir()
        with profile_scope(owner):
            atomic_config_replace(owner / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'terminal', 'skills', 'delegation']}})
            item, private = prepare_home(Specialist('reviewer', 'Review fixture', tools=tuple(DEFAULT_TOOLS), automatic=True))
            installed(private, 'quality-review')
            cfg = read_user_config_raw(private / 'config.yaml')
            cfg['platform_toolsets']['cli'].append('terminal')
            atomic_config_replace(private / 'config.yaml', cfg)
            item = save(replace(item, skills=('quality-review',), private_skills=('quality-review',),
                                extension_revision=fingerprint(private)))
            installed(private, 'program-local')  # setup completed, old finalization failed
    def no_setup(*args, **kwargs):
        raise AssertionError('Repair must not run setup, import plugins, probe, or download')
    monkeypatch.setattr('sci_cli.specialist_private_setup.setup', no_setup)
    monkeypatch.setattr('agent.specialist_extensions.private_definitions', no_setup)
    for owner in (homes[0], homes[1], homes[0]):
        with profile_scope(owner):
            cli = SimpleNamespace(agent=None)
            item = load('reviewer')
            private = extension_home(item)
            before = {str(p): p.read_bytes() for p in private.rglob('*') if p.is_file()}
            owner_before = (owner / 'config.yaml').read_bytes()
            dispatch(cli, '/Update_subagent reviewer', UI(['Review installed private additions', 'Cancel']))
            assert load('reviewer').private_skills == item.private_skills
            assert 'program-local' in drafts(cli)['reviewer'][0].private_skills
            dispatch(cli, '/Update_subagent reviewer', UI(['Resume draft', 'Save and enable for the next conversation']))
            repaired = load('reviewer')
            assert set(repaired.private_skills) == {'quality-review', 'program-local'}
            assert {'terminal', 'process_manage'} <= set(repaired.shared_tools)
            assert repaired.extension_id == item.extension_id
            assert before == {str(p): p.read_bytes() for p in private.rglob('*') if p.is_file()}
            assert (owner / 'config.yaml').read_bytes() == owner_before


def test_finalization_failure_retains_new_installs_and_preserves_real_name_conflicts(tmp_path, monkeypatch):
    from sci_cli.specialist_private_inventory import reconcile
    from sci_cli.config import atomic_config_replace
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path))
    cli = SimpleNamespace(agent=None)
    item = Specialist('reviewer', 'Review', tools=tuple(DEFAULT_TOOLS), skills=('inherited-skill',), automatic=True)
    def partial_setup(cli, ui, home):
        installed(home, 'retained-integration')
        installed(home, 'inherited-skill')
        raise ValueError('fixture finalization failed after installation')
    monkeypatch.setattr('sci_cli.specialist_tool_setup.add_tool', partial_setup)
    with pytest.raises(ValueError, match='fixture finalization'):
        setup(cli, UI(['Add tool (link or request)']), item)
    candidate = drafts(cli)['reviewer'][0]
    assert 'retained-integration' in candidate.private_skills
    assert 'inherited-skill' not in candidate.private_skills
    assert not (tmp_path / 'subagents/reviewer.json').exists()
    private = extension_home(candidate)
    atomic_config_replace(private / 'config.yaml', {'platform_toolsets': {'cli': ['skills', 'terminal']}})
    recovered = reconcile(candidate)
    assert {'terminal', 'process_manage'} <= set(recovered.shared_tools)
    assert 'retained-integration' in recovered.private_skills
