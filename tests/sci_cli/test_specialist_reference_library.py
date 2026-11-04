"""Multiple code/data references append, survive edits, and stay out of large prompts."""
from types import SimpleNamespace
from pathlib import Path
import json

from agent.specialist_store import Specialist, save, load, copy_to
from sci_cli.native_profile_creation import profile_scope
from sci_cli.specialist_source_setup import prepare_references


class UI:
    def __init__(self, answers=()):
        self.answers, self.messages = iter(answers), []
    def show(self, message):
        self.messages.append(message)
    def ask(self, question, *args, **kwargs):
        return next(self.answers)
    def choose(self, question, choices):
        value = self.ask(question)
        assert value in choices, (value, choices)
        return value


def test_append_code_folder_url_refresh_remove_and_large_catalog(tmp_path, monkeypatch):
    from sci_cli.specialist_commands import dispatch
    from agent.specialist_source_library import read_manifest, library_documents
    from agent.specialist_runtime import context_for
    from contextlib import contextmanager
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / 'main'))
    script = tmp_path / 'calculate.py'
    script.write_text("print('APPROVED_FIXTURE_RESULT', 6 * 7)\n")
    folder = tmp_path / 'data'
    folder.mkdir()
    for index in range(30):
        (folder / f'data-{index}.txt').write_text(f'Fixture record {index}.\n' + 'value\n' * 500)
    (folder / 'unsupported.bin').write_bytes(b'\x00\x01')
    save(Specialist('analyst', 'Use approved code and datasets.'))
    cli = SimpleNamespace(agent=None)
    requests = []
    @contextmanager
    def guarded(url, **kwargs):
        requests.append(url)
        yield SimpleNamespace(status_code=200, headers={'content-type': 'text/plain'},
                              iter_bytes=lambda: iter([b'Fixture URL reference.']))
    monkeypatch.setattr('tools.skills_hub._guarded_http_stream', guarded)
    url = 'https://example.org/reference.txt'
    dispatch(cli, '/Update_subagent analyst', UI(['References', 'Add file/folder/URL', str(script),
        'Done', 'Save and enable for the next conversation']))
    original = load('analyst')
    assert original.sources == (str(script),) and script.read_text() in original.source_documents[0]['text']
    ui = UI(['References', 'Add file/folder/URL', str(folder), 'Add file/folder/URL', url,
             'Done', 'Save and enable for the next conversation'])
    dispatch(cli, '/Update_subagent analyst', ui)
    saved = load('analyst')
    assert saved.sources == (str(script), str(folder), url)
    assert saved.source_manifest and not saved.source_documents
    docs = read_manifest(saved.source_manifest)['documents']
    assert len(docs) == 32 and requests == [url]
    assert any('skipped' in message for message in ui.messages)
    assert len(context_for(saved, 'Use relevant data.')) < 20_000
    assert len(json.dumps(saved.__dict__)) < 10_000  # reference text is not embedded in definitions
    script.write_text("print('NEW_VERSION')\n")
    assert 'APPROVED_FIXTURE_RESULT' in next(library_documents(saved.source_manifest))['text']
    dispatch(cli, '/Update_subagent analyst', UI(['References', 'Refresh saved contents', 'Done',
                                               'Save and enable for the next conversation']))
    assert 'NEW_VERSION' in next(library_documents(load('analyst').source_manifest))['text']
    dispatch(cli, '/Update_subagent analyst', UI(['References', 'Remove a reference', str(folder),
                                               'Done', 'Save and enable for the next conversation']))
    reduced = load('analyst')
    assert reduced.sources == (str(script), url)
    assert len(reduced.source_documents) == 2 and not reduced.source_manifest
    assert requests == [url, url]  # append/removal do not unnecessarily refetch existing URLs


def test_library_profile_a_b_a_copy_and_tamper_detection(tmp_path, monkeypatch):
    from agent.specialist_source_library import read_manifest, library_documents
    import pytest
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    data = tmp_path / 'big.py'
    data.write_text('# Harmless source comment\n' * 6000)
    with profile_scope(homes[0]):
        saved = save(prepare_references(Specialist('analyst', 'Read code', sources=(str(data),)), UI()))
        assert saved.source_manifest
        copy_to(saved, homes[1])
    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            if home == homes[1]:
                copied = load('analyst')
                assert not copied.source_manifest and copied.needs_review
                with pytest.raises(ValueError, match='another profile'):
                    read_manifest(saved.source_manifest)
            else:
                assert next(library_documents(saved.source_manifest))['text'] == data.read_text()
    with profile_scope(homes[0]):
        # Existing mount/path bridge covers snapshot storage for remote backends too.
        from tools.credential_files import get_cache_directory_mounts, map_cache_path_to_container
        mounts = get_cache_directory_mounts()
        assert any(Path(mount['host_path']).resolve() == Path(saved.source_manifest).parent.resolve()
                   for mount in mounts)
        mapped = map_cache_path_to_container(saved.source_manifest)
        assert mapped == '/root/.sci/subagent-sources/' + Path(saved.source_manifest).name
        doc = read_manifest(saved.source_manifest)['documents'][0]
        from agent.specialist_policy import SpecialistPolicy, specialist_scope
        from agent.specialist_source_library import reading_paths
        import model_tools
        import time
        policy = SpecialistPolicy('analyst', str(homes[0].resolve()), 'fixture', frozenset({'read_file', 'search_files'}),
                                  frozenset(), frozenset(), ('analyst',), time.monotonic() + 60,
                                  read_paths=reading_paths(saved.source_manifest))
        snapshot = str(Path(saved.source_manifest).parent / doc['file'])
        with specialist_scope(policy):
            read = json.loads(model_tools.handle_function_call('read_file', {'path': snapshot, 'limit': 2},
                                                               enabled_toolsets=['file']))
            assert 'Harmless source comment' in read.get('content', ''), read
        (Path(saved.source_manifest).parent / doc['file']).write_text('corrupted')
        with pytest.raises(ValueError, match='changed'):
            list(library_documents(saved.source_manifest))
