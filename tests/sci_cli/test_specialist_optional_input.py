"""Exercise optional specialist edits through the real modal-to-wizard adapter."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.specialist_store import Specialist, load, save
from sci_cli.native_profile_creation import profile_scope
from sci_cli.specialist_commands import dispatch
from sci_cli.specialist_editor_state import SpecialistUI
from sci_cli.skill_add import Cancelled
from sci_cli.skill_add_status import WizardInputTimeout


def adapter(answers):
    replies = iter(answers)
    questions = []
    def clarify(batch):
        question = batch[0]
        questions.append(question)
        value = next(replies)
        if isinstance(value, dict):
            return value
        return {'outcome': 'submitted', 'answers': {question['qid']: value}}
    cli = SimpleNamespace(agent=None, _app=SimpleNamespace(is_running=True), _clarify_callback=clarify)
    ui = SpecialistUI(cli)
    ui.show = lambda text: None
    return cli, ui, questions


def test_optional_edits_accept_terminal_empty_answers_without_skipping_required_input(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    for profile in ('a', 'b', 'a'):
        with profile_scope(tmp_path / profile):
            if not (tmp_path / profile / 'subagents/reviewer.json').exists():
                save(Specialist('reviewer', 'Original purpose', output='Original output', instructions='Saved instructions'))
            previous_output = load('reviewer').output
            cli, ui, questions = adapter(['Edit purpose/output', 'New purpose', None,
                'References', 'Add file/folder/URL', None, 'Done', 'Additional instructions',
                'Replace instructions', None, 'Save and enable for the next conversation'])
            dispatch(cli, '/Update_subagent reviewer', ui)
            item = load('reviewer')
            assert (item.purpose, item.output, item.instructions, item.sources) == (
                'New purpose', previous_output, 'Saved instructions', ())
            assert len([q for q in questions if q['question'].startswith('Expected output')]) == 1
            cli, ui, _ = adapter(['Edit purpose/output', None, 'Changed output', 'Save and enable for the next conversation'])
            dispatch(cli, '/Update_subagent reviewer', ui)
            assert load('reviewer').purpose == 'New purpose'
            assert load('reviewer').output == 'Changed output'
    # Missing answers, required input and closed menus do not acquire blank values.
    cli, ui, questions = adapter([{'outcome': 'submitted', 'answers': {}}, None, 'required'])
    assert ui.ask('Required') == 'required' and len(questions) == 3
    _, ui, questions = adapter([{'outcome': 'submitted', 'answers': {}}, None])
    assert ui.ask('Optional', allow_blank=True) == '' and len(questions) == 2
    _, ui, _ = adapter([None, 'Keep'])
    assert ui.choose('Menu', ['Keep', 'Cancel']) == 'Keep'
    for outcome, error in [('cancelled', Cancelled), ('timed_out', WizardInputTimeout)]:
        _, ui, _ = adapter([{'outcome': outcome, 'answers': {'specialist': None}}])
        with pytest.raises(error):
            ui.ask('Optional', allow_blank=True)


def test_instruction_keep_replace_append_clear_and_paste_save_actual_text(tmp_path, monkeypatch):
    from sci_cli.cli_stream_mixin import CLIStreamMixin
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    with profile_scope(tmp_path / 'owner'):
        original = save(Specialist('reviewer', 'Review', output='Report',
            instructions='Original instructions', instruction_source=str(tmp_path / 'original.md')))
        for action, value, expected in [
            ('Keep current instructions', None, 'Original instructions'),
            ('Back', None, 'Original instructions'),
            ('Done', None, 'Original instructions'),
            ('Replace instructions', None, 'Original instructions'),
            ('Append instructions', 'Also cite sources.', 'Original instructions\n\nAlso cite sources.'),
            ('Replace instructions', 'Use a table.', 'Use a table.'),
            ('Clear instructions', None, ''),
        ]:
            current = load('reviewer')
            save(replace(current, instructions=original.instructions, instruction_source=original.instruction_source),
                 expected_revision=current.revision)
            replies = ['Additional instructions', action]
            if action in ('Replace instructions', 'Append instructions'):
                replies.append(value)
            replies.append('Save and enable for the next conversation')
            cli, ui, _ = adapter(replies)
            dispatch(cli, '/Update_subagent reviewer', ui)
            item = load('reviewer')
            assert item.instructions == expected
            assert item.instruction_source == (original.instruction_source if expected == original.instructions else '')
        pasted = tmp_path / 'paste.txt'
        pasted.write_text('First instruction.\nSecond instruction.')
        cli, ui, _ = adapter(['Additional instructions',
                              f'[Pasted text #1: 2 lines → {tmp_path / "missing.txt"}]',
                              f'[Pasted text #2: 2 lines → {pasted}]',
                              'Save and enable for the next conversation'])
        cli._expand_paste_references = lambda text: CLIStreamMixin._expand_paste_references(cli, text)
        dispatch(cli, '/Update_subagent reviewer', ui)
        assert load('reviewer').instructions == pasted.read_text()
        assert '[Pasted text #' not in load('reviewer').instructions
