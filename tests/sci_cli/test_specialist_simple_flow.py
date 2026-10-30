"""Reported wizard failures: module packages, recoverable answers and portable copies."""
from dataclasses import replace
from types import SimpleNamespace
import json

from agent.specialist_store import Specialist, load, save
from sci_cli.specialist_commands import dispatch
from sci_cli.specialist_editor_state import drafts
from sci_cli.native_profile_creation import profile_scope


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, text):
        self.messages.append(text)
    def ask(self, question, *args, **kwargs):
        from sci_cli.skill_add import Cancelled
        answer = next(self.answers)
        if answer == 'Cancel':
            raise Cancelled()
        return answer
    def choose(self, question, choices):
        answer = self.ask(question)
        assert answer in choices, (answer, choices)
        return answer


def test_none_bad_path_blank_edit_and_cancel_retain_profile_draft(tmp_path, monkeypatch):
    monkeypatch.setattr('sci_cli.specialist_wizard.choices', lambda cli: ({}, {}))
    cli = SimpleNamespace(agent=None)
    ui = UI(['reviewer', 'Review documents', 'A summary', 'Additional instructions', 'Use citations',
             'References', 'Add file/folder/URL', '/missing/example/file', 'none', 'Done',
             'Edit purpose/output', '', '', 'Cancel'])
    dispatch(cli, '/Create_subagent', ui)
    assert 'reviewer' in drafts(cli)
    assert any('Try again' in text for text in ui.messages)
    assert drafts(cli)['reviewer'][0].purpose == 'Review documents'
    assert drafts(cli)['reviewer'][0].instructions == 'Use citations'
    with profile_scope(tmp_path / 'other'):
        assert drafts(cli) == {}
    dispatch(cli, '/Create_subagent reviewer', UI(['Resume draft', 'Save and enable for the next conversation']))
    saved = load('reviewer')
    assert saved.automatic and saved.sources == () and not drafts(cli)
    # Editing begins directly at review. Invalid path/name input never discards earlier fields.
    dispatch(cli, '/Update_subagent reviewer', UI(['Edit purpose/output', '', 'Revised output',
                                                  'Save and enable for the next conversation']))
    assert load('reviewer').purpose == saved.purpose
    assert load('reviewer').output == 'Revised output'
    # Cancelling inside reference editing retains the last accepted location, too.
    dispatch(cli, '/Update_subagent reviewer', UI(['References', 'Add file/folder/URL', str(tmp_path), 'Cancel']))
    assert drafts(cli)['reviewer'][0].sources == (str(tmp_path.resolve()),)
    assert load('reviewer').sources == ()
    dispatch(cli, '/Update_subagent reviewer', UI(['Resume draft', 'Save and enable for the next conversation']))
    assert load('reviewer').sources == (str(tmp_path.resolve()),)
    export = tmp_path / 'reviewer.json'
    dispatch(cli, f'/subagent export reviewer "{export}"', UI(['Export']))
    exported = json.loads(export.read_text())
    assert not exported['enabled'] and not exported['sources']
    with profile_scope(tmp_path / 'other'):
        dispatch(cli, f'/subagent import "{export}"', UI(['Import']))
        assert load('reviewer').needs_review and not load('reviewer').enabled
        before = load('reviewer')
        dispatch(cli, f'/subagent import "{export}"', UI(['Import']))
        assert load('reviewer') == before  # no overwrite on duplicate


def test_boltzmann_package_module_picker_and_filtered_selection(tmp_path, monkeypatch):
    from sci_cli.specialist_capabilities import tool_menu, skill_menu, expand_tools, BOLTZMANN_PACKAGE
    from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS, select_science_items
    root = tmp_path / 'references'
    (root / 'modules').mkdir(parents=True)
    for name in ('protein', 'rna'):
        (root / 'modules' / f'{name}.md').write_text(f'{name} instructions')
    catalog = root / 'tool-contracts.v1.json'
    catalog.write_text(json.dumps({'modules': [
        {'id': 'protein', 'domain': 'Protein Engineering', 'title': 'Protein review', 'path': 'modules/protein.md'},
        {'id': 'rna', 'domain': 'RNA', 'title': 'RNA review', 'path': 'modules/rna.md'}]}))
    monkeypatch.setattr('sci_cli.science_catalog_view.registry_path', lambda: catalog)
    monkeypatch.setattr('sci_cli.specialist_capabilities.boltzmann_ready', lambda: True)
    helpers = dict.fromkeys(BOLTZMANN_WORKFLOW_TOOLS, 'helper')
    options, selected = tool_menu(helpers, ('boltzmann_status',))
    assert list(options) == [BOLTZMANN_PACKAGE]
    assert set(expand_tools(selected)) == set(helpers)
    item = Specialist('reviewer', 'Review')
    options, selected, resources = skill_menu({'boltzmann:tools': 'all modules'}, helpers, item)
    picked = select_science_items(UI(['Search', 'protein', 'Select matching', 'Done']), 'Skills', options,
                                  selected=selected, filtered_controls=True)
    assert len(picked) == 1
    resource = resources[picked[0]]
    assert resource.endswith('modules/protein.md')
    stored = save(replace(item, skills=('boltzmann:tools',), skill_files=(resource,)), tmp_path)
    assert stored.skill_files == (resource,)
    missing = replace(stored, skill_files=('boltzmann:tools#references/modules/retired.md',))
    _, kept, _ = skill_menu({'boltzmann:tools': 'common'}, helpers, missing)
    assert missing.skill_files[0] in kept  # catalog changes must not silently erase saved selections
    monkeypatch.setattr('sci_cli.specialist_capabilities.boltzmann_ready', lambda: False)
    # No new Boltzmann choice without owning-profile authorization.
    menu, _ = tool_menu({}, ())
    assert BOLTZMANN_PACKAGE not in menu
