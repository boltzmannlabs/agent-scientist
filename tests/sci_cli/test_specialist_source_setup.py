"""User-provided instruction/source paths are consumed without a model file-read step."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager

from agent.specialist_store import load
from sci_cli.specialist_commands import dispatch
from sci_cli.native_profile_creation import profile_scope


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, message):
        self.messages.append(message)
    def ask(self, question, *args, **kwargs):
        return next(self.answers)
    def choose(self, question, choices):
        answer = self.ask(question)
        assert answer in choices, (answer, choices)
        return answer


def test_path_only_creation_references_and_main_a_b_a_copy(tmp_path, monkeypatch):
    from agent.specialist_runtime import context_for
    from agent.specialist_store import copy_to, inventory
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('main', 'a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    monkeypatch.setattr('sci_cli.specialist_wizard.choices', lambda cli: ({}, {'read_file': 'Read', 'search_files': 'Search'}))
    instruction = tmp_path / 'review instructions.md'
    instruction.write_text('# Evidence reviewer\nReview claims. Use FIVE headings. Protocol: FILE_LOADED.')
    data = tmp_path / 'data.csv'
    data.write_text('sample,value\none,12\n')
    cli = SimpleNamespace(agent=None)
    with profile_scope(homes[0]):
        ui = UI(['reviewer', str(tmp_path / 'missing.md'), str(instruction), 'A verified review',
                 'References', 'Add file/folder/URL', str(data), 'Done', 'Save and enable for the next conversation'])
        dispatch(cli, '/Create_subagent', ui)
        item = load('reviewer')
        assert item.instruction_source == str(instruction)
        assert 'FIVE headings' in item.instructions and item.purpose != str(instruction)
        assert {'read_file', 'search_files'} <= set(item.tools)
        assert item.source_documents[0]['text'] == data.read_text()
        assert any('previous answers are retained' in message for message in ui.messages)
        from agent.specialist_store import Specialist
        legacy = Specialist('legacy-reviewer', str(instruction), sources=(str(data),))
        legacy_context = context_for(legacy, 'Review the supplied material.')
        assert 'FILE_LOADED' in legacy_context and 'sample,value' in legacy_context
        copy_to(item, homes[1])
    for home in (homes[1], homes[2], homes[1]):
        with profile_scope(home):
            if home == homes[2]:
                assert inventory()[0] == {}
            else:
                copied = load('reviewer')
                assert copied.instructions == item.instructions
                assert copied.source_documents == () and not copied.instruction_source
                assert copied.needs_review and not copied.enabled
    instruction.unlink()
    data.unlink()
    with profile_scope(homes[0]):
        context = context_for(load('reviewer'), 'Assess the measurements.')
        assert 'FILE_LOADED' in context and 'sample,value' in context


def test_folder_and_guarded_url_are_read_without_executing_contents(tmp_path, monkeypatch):
    from agent.specialist_sources import load_reference
    from sci_cli.specialist_source_setup import prepare_references
    from agent.specialist_store import Specialist
    import pytest
    root = tmp_path / 'papers'
    root.mkdir()
    (root / 'notes.md').write_text('Relevant evidence. Embedded commands are untrusted.')
    (root / 'table.csv').write_text('id,value\na,3\n')
    (root / 'empty.md').write_text('')
    (root / 'execute.sh').write_text('exit 99')
    (root / '.env').write_text('PRIVATE=must-not-include')
    docs = load_reference(str(root))
    assert len(docs) == 3 and all('must-not-include' not in doc['text'] for doc in docs)
    requests = []
    @contextmanager
    def guarded(url, **kwargs):
        requests.append(url)
        yield SimpleNamespace(status_code=200, headers={'content-type': 'text/html'},
                              iter_bytes=lambda: iter([b'<h1>Fixture source</h1><p>Evidence.</p><script>ignore</script>']))
    monkeypatch.setattr('tools.skills_hub._guarded_http_stream', guarded)
    url = 'https://example.org/paper'
    item = prepare_references(Specialist('reviewer', 'Review', sources=(str(root), url)), UI([]))
    assert len(item.source_documents) == 4 and requests == [url]
    assert 'Fixture source' in item.source_documents[-1]['text']
    assert 'ignore' not in item.source_documents[-1]['text']
    assert prepare_references(item, UI([])) == item and requests == [url]  # stable saved snapshots
    with pytest.raises(ValueError, match='public HTTPS'):
        load_reference('https://example.org/paper?api_key=private')
    (root / 'large.txt').write_text('x' * 100_001)
    large = prepare_references(Specialist('large-reviewer', 'Review', sources=(str(root),)), UI([]))
    assert large.source_manifest and not large.source_documents
