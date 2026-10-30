"""Specialist policies narrow direct calls, discovery, programmatic dispatch and nested delegates."""
from dataclasses import replace
import json
from types import SimpleNamespace
import time
import pytest

from agent.specialist_store import Specialist, save
from agent.specialist_runtime import capture, resolve
from agent.specialist_policy import SpecialistPolicy, specialist_scope
from sci_constants import get_sci_home


def parent_for(item):
    from tools.delegate_tool import DELEGATE_TASK_SCHEMA
    from copy import deepcopy
    parent = SimpleNamespace(enabled_toolsets=['delegation', 'file'], disabled_toolsets=[],
                             tools=[{'type': 'function', 'function': deepcopy(DELEGATE_TASK_SCHEMA)}],
                             _specialist_user_request='')
    capture(parent)
    parent._specialist_parent_tools = frozenset({'read_file', 'delegate_task'})
    return parent


def test_manual_snapshot_revocation_and_no_privilege_escalation():
    item = save(Specialist('reviewer', 'Review', tools=('read_file',)))
    parent = parent_for(item)
    before = json.dumps(parent.tools, sort_keys=True)
    with pytest.raises(ValueError, match='explicit'):
        resolve(parent, {'specialist': item.name})
    parent._specialist_user_request = 'Ask reviewer to compare these findings'
    _, policy = resolve(parent, {'specialist': item.name})
    assert policy.tools == {'read_file'}
    save(replace(item, tools=('terminal',)), expected_revision=item.revision)
    with pytest.raises(ValueError, match='edited'):
        resolve(parent, {'specialist': item.name})
    assert json.dumps(parent.tools, sort_keys=True) == before
    new_parent = parent_for(item)
    new_parent._specialist_user_request = 'reviewer'
    _, reduced = resolve(new_parent, {'specialist': item.name})
    assert 'terminal' not in reduced.tools
    assert 'terminal' in reduced.unavailable_tools
    save(Specialist('new-specialist', 'New'))
    with pytest.raises(ValueError, match='not enabled'):
        resolve(parent, {'specialist': 'new-specialist'})
    parent._specialist_policy = policy
    with pytest.raises(ValueError, match='approved named'):
        resolve(parent, {'goal': 'Bypass saved specialist'})


def test_enforcement_real_registry_and_deferred_catalog(monkeypatch):
    import model_tools
    from tools.registry import registry
    home = get_sci_home()
    called = []
    for name in ('specialist_allowed_fixture', 'specialist_denied_fixture'):
        registry.register(name=name, toolset='specialist-fixture', schema={'name': name, 'description': 'fixture',
                          'parameters': {'type': 'object', 'properties': {}}},
                          handler=lambda args, **kw: called.append('called') or '{"ok": true}')
    policy = SpecialistPolicy('reviewer', str(home.resolve()), 'rev', frozenset({'specialist_allowed_fixture'}),
                              frozenset(), frozenset(), ('reviewer',), time.monotonic() + 60)
    # Same cached toolset under different specialist grants must not leak definitions.
    with specialist_scope(policy):
        names = {t['function']['name'] for t in model_tools.get_tool_definitions(['specialist-fixture'], quiet_mode=True,
                                                                              skip_tool_search_assembly=True)}
        assert names == {'specialist_allowed_fixture'}
        assert json.loads(registry.dispatch('specialist_allowed_fixture', {}))['ok']
        assert 'error' in json.loads(registry.dispatch('specialist_denied_fixture', {}))
        assert 'error' in json.loads(model_tools.handle_function_call('specialist_denied_fixture', {}))
        described = model_tools.handle_function_call('tool_describe', {'names': ['specialist_denied_fixture']},
                                                      enabled_toolsets=['specialist-fixture'])
        assert '"description": "fixture"' not in described
        assert len(called) == 1
        with specialist_scope(replace(policy, tools=frozenset())):
            assert model_tools.get_tool_definitions(['specialist-fixture'], quiet_mode=True,
                                                    skip_tool_search_assembly=True) == []
        assert 'error' in json.loads(registry.dispatch('skill_view', {'name': 'not-selected'}))
    assert 'ok' in json.loads(registry.dispatch('specialist_denied_fixture', {}))
