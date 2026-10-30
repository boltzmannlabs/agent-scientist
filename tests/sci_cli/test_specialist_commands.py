"""Controlled modal walkthrough: create, cancel, copy, review, assign and inspect."""
from types import SimpleNamespace
from pathlib import Path
from agent.specialist_store import inventory, load
from sci_cli.specialist_commands import dispatch
from sci_cli.skill_add import Cancelled


class UI:
    def __init__(self, answers=()):
        self.answers = iter(answers)
        self.messages = []
    def show(self, text):
        self.messages.append(text)
    def ask(self, question, *args, **kwargs):
        value = next(self.answers)
        if value == 'Cancel':
            raise Cancelled()
        return value
    def choose(self, question, choices):
        result = self.ask(question)
        assert result in choices, (question, result, choices)
        return result


def test_create_cancel_copy_update_and_run(tmp_path, monkeypatch):
    from sci_constants import get_sci_home
    from agent.specialist_runtime import capture
    from sci_cli.native_profile_creation import profile_scope
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = get_sci_home()
    monkeypatch.setattr('sci_cli.profiles._get_default_sci_home', lambda: home)
    monkeypatch.setattr('sci_cli.profiles._get_profiles_root', lambda: home / 'profiles')
    dest = home / 'profiles' / 'omics'
    dest.mkdir(parents=True)
    (dest / 'config.yaml').write_text('model: {default: fixture}\n')
    monkeypatch.setattr('sci_cli.specialist_wizard.choices', lambda cli: ({}, {}))
    cli = SimpleNamespace(agent=None, _pending_agent_seed=None, _app=SimpleNamespace(is_running=True))
    ui = UI(['reviewer', 'Review literature', 'A cited comparison',
             'Save and enable for the next conversation'])
    def clarify(questions):
        question = questions[0]
        answer = ui.ask(question['question'])
        if question['choices']:
            assert answer in question['choices']
        return {'outcome': 'submitted', 'answers': {question['qid']: answer}}
    cli._clarify_callback = clarify
    monkeypatch.setattr('cli._cprint', ui.show)
    # Use the production WizardUI and its terminal-modal callback, not a replacement editor.
    dispatch(cli, '/CrEaTe_sUbAgEnT')
    assert load('reviewer').purpose == 'Review literature'
    assert 'Saved reviewer' in '\n'.join(ui.messages)
    dispatch(cli, '/Create_subagent', UI(['Cancel']))
    assert list(inventory()[0]) == ['reviewer']
    dispatch(cli, '/subagent copy reviewer omics', UI(['Copy for review']))
    assert load('reviewer', dest).needs_review
    with profile_scope(dest):
        dispatch(cli, '/Update_subagent reviewer', UI(['Save and enable for the next conversation']))
        assert load('reviewer').enabled and not load('reviewer').needs_review
    agent = SimpleNamespace(valid_tool_names={'delegate_task'})
    capture(agent)
    cli.agent, cli._init_agent = agent, lambda: True
    dispatch(cli, '/subagent run reviewer "Compare these two papers"', UI())
    assert 'Compare these two papers' in cli._pending_agent_seed
    assert 'tasks[].specialist="reviewer"' in cli._pending_agent_seed
    ui = UI()
    dispatch(cli, '/subagent status', ui)
    assert 'Specialist runs: 0' in '\n'.join(ui.messages)
    dispatch(cli, '/subagent disable reviewer', UI(['Disable']))
    assert not load('reviewer').enabled
    # Unavailable integrations must stay visible on edit, even when the catalog is empty.
    from sci_cli.specialist_wizard import pick
    selected = pick(UI(['Done']), 'Tools', {}, ('temporarily_unavailable',))
    assert selected == ['temporarily_unavailable']


def test_registry_case_insensitive_and_dispatch(monkeypatch):
    from cli import SciCLI
    from sci_cli.commands import resolve_command, COMMANDS
    cli = SciCLI.__new__(SciCLI)
    cli.config, cli.session_id = {}, 'fixture'
    seen = []
    monkeypatch.setattr('sci_cli.specialist_commands.dispatch', lambda c, command: seen.append(command))
    for name in ('Create_subagent', 'Update_subagent', 'subagents', 'subagent'):
        assert resolve_command(name.lower()) is not None
        assert '/' + name.lower() in COMMANDS
        assert cli.process_command('/' + name.upper() + ' reviewer') is True
    assert len(seen) == 4


def test_update_picker_scopes_selection_and_preserves_cancelled_definitions(tmp_path, monkeypatch):
    from agent.specialist_store import Specialist, save
    from sci_cli.native_profile_creation import profile_scope
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    cli = SimpleNamespace(agent=None)
    for home in homes:
        home.mkdir()
        with profile_scope(home):
            for index in range(7):
                save(Specialist(f'reviewer-{index}', f'Only {home.name}', enabled=index != 6))

    class PickerUI(UI):
        def choose(self, question, choices):
            if question.startswith('Choose a specialist to edit'):
                assert all(f'Only {home.name}' in choice for choice in choices if 'reviewer-' in choice)
            return super().choose(question, choices)

    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            before = {p.name: p.read_bytes() for p in (home / 'subagents').glob('*.json')}
            ui = PickerUI(['Next page', f'reviewer-6 [disabled] — Only {home.name}', 'Cancel'])
            dispatch(cli, '/UpDaTe_SuBaGeNt', ui)
            assert any('Specialist: reviewer-6' in message for message in ui.messages)
            assert before == {p.name: p.read_bytes() for p in (home / 'subagents').glob('*.json')}
            dispatch(cli, '/Update_subagent', PickerUI(['Cancel']))
            ui = PickerUI(['Search', 'reviewer-6', f'reviewer-6 [disabled] — Only {home.name}',
                           'Resume draft', 'Save and enable for the next conversation'])
            dispatch(cli, '/subagent edit', ui)
            assert load('reviewer-6').enabled
            # Direct editing still skips the picker.
            dispatch(cli, '/Update_subagent reviewer-6', UI(['Save and enable for the next conversation']))
            # Restore disabled state for the return to A.
            item = load('reviewer-6')
            from dataclasses import replace
            save(replace(item, enabled=False), expected_revision=item.revision)


def test_update_empty_picker_offers_creation_without_mutating_on_cancel(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    monkeypatch.setattr('sci_cli.specialist_wizard.choices', lambda cli: ({}, {}))
    cli = SimpleNamespace(agent=None)
    ui = UI(['Cancel'])
    dispatch(cli, '/Update_subagent', ui)
    assert any('No saved specialists' in message for message in ui.messages)
    assert not inventory()[0]
    dispatch(cli, '/Update_subagent', UI(['Create specialist', 'new-reviewer', 'Review supplied evidence',
                                        'A concise review', 'Save and enable for the next conversation']))
    assert load('new-reviewer').purpose == 'Review supplied evidence'
