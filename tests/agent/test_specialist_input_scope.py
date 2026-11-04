"""Inline-only assignments cannot silently read a nearby fixture or infer access from instruction provenance."""
from types import SimpleNamespace

from agent.specialist_store import Specialist, save
from agent.specialist_runtime import capture, resolve
from agent.specialist_policy import specialist_scope, check_call


def parent(request):
    p = SimpleNamespace(enabled_toolsets=['file', 'delegation'], disabled_toolsets=[],
                        platform='cli', tools=[], _specialist_user_request=request)
    capture(p)
    p._specialist_parent_tools = frozenset({'read_file', 'search_files', 'delegate_task'})
    return p


def test_inline_assignment_cannot_read_instruction_directory_or_parent_suggested_path(tmp_path):
    instruction = tmp_path / 'instructions.md'
    instruction.write_text('Use five sections.')
    nearby = tmp_path / 'measurements.csv'
    nearby.write_text('id,value\na,42\n')
    save(Specialist('auditor', 'Audit supplied records', instructions=instruction.read_text(),
                    instruction_source=str(instruction), tools=('read_file', 'search_files'), automatic=True))
    p = parent('Audit these supplied records: a,42. Use only this message.')
    _, policy = resolve(p, {'specialist': 'auditor', 'context': f'Look in {tmp_path}'})
    assert policy.read_paths == ()
    assert not {'read_file', 'search_files'} & policy.tools
    with specialist_scope(policy):
        assert check_call('read_file', {'path': str(nearby)})
        assert check_call('search_files', {'path': str(tmp_path), 'pattern': '*'})


def test_explicit_task_path_and_selected_reference_allow_only_their_scope(tmp_path):
    from dataclasses import replace
    path = tmp_path / 'input.csv'
    path.write_text('id,value\na,42\n')
    unrelated = tmp_path / 'other.csv'
    unrelated.write_text('private\n')
    item = save(Specialist('auditor', 'Audit supplied records', tools=('read_file', 'search_files'), automatic=True))
    p = parent(f'Audit "{path}"')
    _, policy = resolve(p, {'specialist': 'auditor'})
    with specialist_scope(policy):
        assert check_call('read_file', {'path': str(path)}) is None
        assert check_call('read_file', {'path': str(unrelated)})
        assert check_call('search_files', {'path': str(tmp_path), 'pattern': '*'})
        assert check_call('search_files', {'pattern': '*'})
    # A selected folder reference grants its descendants, without broadening to its parent.
    folder = tmp_path / 'approved'
    folder.mkdir()
    child = folder / 'data.csv'
    child.write_text('approved\n')
    save(replace(item, sources=(str(folder),)), expected_revision=item.revision)
    _, policy = resolve(parent('Audit the saved reference.'), {'specialist': 'auditor'})
    with specialist_scope(policy):
        assert check_call('read_file', {'path': str(child)}) is None
        assert check_call('read_file', {'path': str(unrelated)})
    # Explicit execution access retains backend file access for newly generated artifacts.
    from agent.specialist_store import load
    current = load('auditor')
    save(replace(current, tools=('read_file', 'terminal'), sources=()), expected_revision=current.revision)
    p = parent('Run the local calculation and inspect its outputs.')
    p.enabled_toolsets = ['file', 'terminal', 'delegation']
    p._specialist_parent_tools |= {'terminal'}
    _, policy = resolve(p, {'specialist': 'auditor'})
    assert policy.read_paths is None
