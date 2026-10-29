"""Integrations keep profile credentials and skill loading boundaries under saved specialists."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import time
import pytest

from agent.specialist_store import Specialist, save
from agent.specialist_runtime import capture, context_for, resolve
from agent.specialist_policy import SpecialistPolicy, specialist_scope
from sci_cli.native_profile_creation import profile_scope


def test_service_auth_is_profile_scoped_and_nested_permissions_only_narrow(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_active, get_secret
    from tools.registry import registry
    import model_tools
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / n for n in ('a', 'b')]
    for h in homes:
        h.mkdir()
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    registry.register(name='specialist_service_fixture', toolset='mcp-specialist-fixture',
                      schema={'name': 'specialist_service_fixture', 'description': 'profile service',
                              'parameters': {'type': 'object', 'properties': {}}},
                      handler=lambda args, **kw: json.dumps({'authorized': bool(get_secret('SPECIALIST_FIXTURE_KEY'))}),
                      check_fn=lambda: bool(get_secret('SPECIALIST_FIXTURE_KEY')))
    set_multiplex_active(True)
    try:
        for home, secrets, expected in ((homes[0], {'SPECIALIST_FIXTURE_KEY': 'a-fixture'}, True),
                                        (homes[1], {}, False), (homes[0], {'SPECIALIST_FIXTURE_KEY': 'a-fixture'}, True)):
            with profile_scope(home, secrets=secrets):
                policy = SpecialistPolicy('worker', str(home.resolve()), 'r', frozenset({'specialist_service_fixture'}),
                                          frozenset(), frozenset(), ('worker',), time.monotonic() + 30)
                with specialist_scope(policy):
                    definitions = model_tools.get_tool_definitions(['mcp-specialist-fixture'], quiet_mode=True,
                                                                   skip_tool_search_assembly=True)
                    assert bool(definitions) is expected
                    assert json.loads(registry.dispatch('specialist_service_fixture', {}))['authorized'] is expected
        with profile_scope(homes[0], secrets={'SPECIALIST_FIXTURE_KEY': 'a-fixture'}):
            save(Specialist('reviewer', 'Review', tools=('read_file',)))
            lead = SimpleNamespace(enabled_toolsets=['file', 'delegation'], disabled_toolsets=[], platform='cli')
            capture(lead)
            lead._specialist_parent_tools = frozenset({'read_file', 'delegate_task'})
            lead._specialist_policy = SpecialistPolicy('lead', str(homes[0].resolve()), 'r', frozenset({'delegate_task'}),
                                                       frozenset(), frozenset({'reviewer'}), ('lead',), time.monotonic() + 30)
            with pytest.raises(ValueError, match='exceed'):
                resolve(lead, {'specialist': 'reviewer'})
            lead._specialist_policy = replace(lead._specialist_policy, tools=frozenset({'read_file', 'delegate_task'}))
            _, child_policy = resolve(lead, {'specialist': 'reviewer'})
            assert child_policy.deadline <= lead._specialist_policy.deadline
            lead._specialist_policy = replace(lead._specialist_policy, ancestry=('lead', 'reviewer'))
            with pytest.raises(ValueError, match='cycle'):
                resolve(lead, {'specialist': 'reviewer'})
            # A nested specialist's own cap AND its lead's pool apply to its whole subtree.
            from agent.iteration_budget import IterationBudget
            lead_budget = IterationBudget(5)
            child_budget = IterationBudget(2, parent=lead_budget)
            grandchild_budget = IterationBudget(9, parent=child_budget)
            assert grandchild_budget.consume() and grandchild_budget.consume()
            assert not grandchild_budget.consume()
            assert child_budget.used == 2 and lead_budget.remaining == 3
            grandchild_budget.refund()
            assert child_budget.remaining == 1 and lead_budget.remaining == 4
    finally:
        set_multiplex_active(False)


def test_skill_preload_never_preprocesses_or_installs_and_selection_is_enforced(monkeypatch):
    from sci_constants import get_sci_home
    from tools.skills_tool import skill_view
    home = get_sci_home()
    directory = home / 'skills' / 'evidence'
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text('---\nname: evidence\ndescription: Compare evidence\n---\nRead the provided evidence.\n')
    (directory / 'selected.md').write_text('SELECTED MODULE INSTRUCTIONS')
    (directory / 'unselected.md').write_text('UNSELECTED MODULE INSTRUCTIONS')
    def forbidden(*args, **kwargs):
        raise AssertionError('setup or shell preprocessing must not run')
    monkeypatch.setattr('tools.skills_tool._preprocess_skill', forbidden)
    monkeypatch.setattr('tools.skills_tool._skill_readiness', forbidden)
    item = Specialist('reviewer', 'Review evidence', skills=('evidence',), skill_files=('evidence#selected.md',))
    context = context_for(item, 'Assignment text')
    assert 'Read the provided evidence' in context
    assert 'SELECTED MODULE INSTRUCTIONS' in context
    assert 'UNSELECTED MODULE INSTRUCTIONS' not in context
    policy = SpecialistPolicy('reviewer', str(home.resolve()), 'r', frozenset({'skill_view', 'skills_list'}),
                              frozenset({'evidence'}), frozenset(), ('reviewer',), time.monotonic() + 30)
    with specialist_scope(policy):
        assert json.loads(skill_view('evidence'))['success']
        assert 'error' in json.loads(skill_view('unselected'))
