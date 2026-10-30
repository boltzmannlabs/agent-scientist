"""Long and wrapped menus must fit the terminal and stop at their actual endpoints."""

from types import SimpleNamespace
from unittest.mock import Mock


def test_clarify_long_list_stops_without_growing_past_terminal(monkeypatch):
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.data_structures import Size
    from sci_cli.cli_tui_mixin import CLITuiMixin

    output = DummyOutput()
    monkeypatch.setattr(output, 'get_size', lambda: Size(rows=24, columns=80))
    choices = [f'project-{i} ' + 'long description ' * 8 for i in range(30)] + ['Cancel']
    entry = {'qid': 'profile', 'question': 'Choose a profile', 'choices': choices,
             'allow_other': False, 'numbered_choices': False}
    state = {'questions': [entry], 'answers': {}, 'choices': choices, 'selected': 0, 'allow_other': False}
    cli = SimpleNamespace(_clarify_state=state, _clarify_freetext=False)
    event = SimpleNamespace(app=Mock())
    with create_app_session(output=output):
        for _ in range(len(choices) + 20):
            CLITuiMixin._tui_clarify_down(cli, event)
            rendered = ''.join(text for _, text in CLITuiMixin._get_clarify_display_fragments(cli))
            assert len(rendered.splitlines()) <= 18
            assert '❯' in rendered
        assert state['selected'] == len(choices) - 1
        assert 'Cancel' in rendered
        last = rendered
        for _ in range(20):
            CLITuiMixin._tui_clarify_down(cli, event)
            assert ''.join(text for _, text in CLITuiMixin._get_clarify_display_fragments(cli)) == last
        for _ in range(len(choices) + 20):
            CLITuiMixin._tui_clarify_up(cli, event)
        assert state['selected'] == 0
        assert 'project-0' in ''.join(text for _, text in CLITuiMixin._get_clarify_display_fragments(cli))
