"""Capability browsing stays in pickers, local to the profile and read-only."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def homes(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    root = tmp_path / '.sci'
    monkeypatch.setenv('SCI_HOME', str(root))
    homes = [root, root / 'profiles/a', root / 'profiles/b']
    for home in homes:
        home.mkdir(parents=True)
        atomic_config_replace(home / 'config.yaml', {
            'platform_toolsets': {'cli': ['file', 'skills', 'no_mcp', f'mcp-{home.name}']},
            'mcp_servers': {f'mcp-{home.name}': {'url': 'https://example.invalid', 'tools': {'include': ['lookup']}}},
            'agent': {'disabled_toolsets': ['clarify']}})
        for index in range(11):
            directory = home / 'skills' / f'fixture-{home.name}-{index:02}'
            directory.mkdir(parents=True)
            (directory / 'SKILL.md').write_text(f'---\nname: fixture-{index}\ndescription: Test reference\n---\nInstructions')
    return homes


def test_category_picker_search_details_and_pagination_are_profile_local(homes, monkeypatch):
    from sci_cli.capability_overview import inventory, run
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skill_add import WizardUI
    from sci_cli.cli_modal_mixin import CLIModalMixin
    from sci_cli.cli_tui_mixin import CLITuiMixin
    from agent.secret_scope import is_multiplex_active, set_multiplex_active

    probe = Mock(side_effect=AssertionError('Browsing must not connect or execute'))
    monkeypatch.setattr('sci_cli.mcp_config._probe_single_server', probe)
    monkeypatch.setattr('sci_cli.science_integrations.setup_defaults', probe)
    notices = []
    monkeypatch.setattr(WizardUI, 'show', lambda self, text: notices.append(text))
    before = {p: p.read_bytes() for h in homes for p in h.rglob('*') if p.is_file()}
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        for home in (homes[0], homes[1], homes[2], homes[1]):
            with profile_scope(home):
                cli = SimpleNamespace(_app=SimpleNamespace(is_running=True), agent=SimpleNamespace(
                    tools=[{'function': {'name': 'read_file'}}], _cached_system_prompt='unchanged'),
                    conversation_history=[{'role': 'user', 'content': home.name}],
                    _science_deferred_mcp={f'mcp-{home.name}': True})
                original = deepcopy((cli.agent, cli.conversation_history))
                rows = inventory(cli)
                assert any(r.name == 'clarify' and r.enabled for r in rows)
                assert not any(r.name == f'mcp-{other.name}' for other in homes if other != home for r in rows)
                operations = iter([
                    lambda choices: next(c for c in choices if c.startswith('Skills (')),
                    'Next page', 'Previous page', 'Search', 'not-a-capability', 'Clear search', 'Back',
                    lambda choices: next(c for c in choices if c.startswith('Plugins (')),
                    'Back', 'Search', f'mcp-{home.name}',
                    lambda choices: next(c for c in choices if c.startswith(f'mcp-{home.name} [MCP]')),
                    'Back', 'Done',
                ])
                menus = []
                def clarify(batch):
                    question = batch[0]
                    options = question['choices']
                    assert not question['numbered_choices']
                    assert not any('Enable input dialogs' in c for c in options)
                    step = next(operations)
                    answer = step(options) if callable(step) else step
                    if options:
                        assert answer in options
                        if ' · Plugins\n' in question['question']:
                            assert not any('[provider]' in c for c in options)
                        cli._clarify_state = {'questions': batch, 'answers': {}, 'answer_meta': {}}
                        CLIModalMixin._clarify_batch_set_active(cli, cli._clarify_state, 0)
                        cli._clarify_state['selected'] = options.index(answer)
                        rendered = ''.join(text for _, text in CLITuiMixin._get_clarify_display_fragments(cli))
                        assert answer in rendered
                    menus.append((question['question'], options))
                    return {'outcome': 'submitted', 'answers': {'skill_add': answer}}
                cli._clarify_callback = clarify
                run(cli, '/capabilities')
                assert next(operations, None) is None
                assert any('No matches.' in title for title, _ in menus)
                assert any('Pending new conversation' in choice for _, choices in menus for choice in choices)
                assert any('Explicit allowlist: 1 entries.' in title for title, _ in menus)
                assert any('Service providers (' in choice for _, choices in menus for choice in choices)
                assert original == (cli.agent, cli.conversation_history)
                assert notices[-1] == 'Capabilities closed. Nothing changed.'
    finally:
        set_multiplex_active(previous)
    probe.assert_not_called()
    assert all(p.read_bytes() == data for p, data in before.items())
    # Full metadata is in the detail modal, never dumped page by page into chat.
    assert all(text == 'Capabilities closed. Nothing changed.' for text in notices)


def test_direct_search_empty_inventory_and_setup_cancel_are_reported_honestly(homes, monkeypatch):
    from sci_cli.capability_overview import run
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skill_add import Cancelled

    with profile_scope(homes[1]):
        cli = SimpleNamespace(agent=None)
        setup = Mock(side_effect=Cancelled)
        monkeypatch.setattr('sci_cli.science_integrations.setup_defaults', setup)
        choices = iter(['Set up missing defaults'])
        def choose(title, options):
            assert 'tooluniverse' in title or any('tooluniverse' in c for c in options)
            assert not any('pubmed [' in c for c in options)
            answer = next(choices)
            assert answer in options
            return answer
        ui = SimpleNamespace(choose=choose, show=Mock())
        run(cli, '/capabilities search universe', ui)
        setup.assert_called_once_with(cli, ui)
        assert 'Setup cancelled' in ui.show.call_args.args[0]
        ui.choose = Mock(side_effect=Cancelled)
        run(cli, '/capabilities', ui)
        assert ui.show.call_args.args[0] == 'Capabilities closed. Nothing changed.'
        monkeypatch.setattr('sci_cli.capability_overview.inventory', lambda _: [])
        ui.choose = Mock(side_effect=['Back', 'Done'])
        run(cli, '/capabilities search missing', ui)
        assert 'No matches.' in ui.choose.call_args_list[0].args[0]
        assert 'Set up missing defaults' not in ui.choose.call_args_list[1].args[1]
