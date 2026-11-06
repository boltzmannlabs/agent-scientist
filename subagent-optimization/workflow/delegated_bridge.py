"""Task-bound host operations; no model calls or alternate scientific client.

The SDK plugin verifies actual caller scope. Caller fields here retain trusted
transport provenance, and are not an authentication mechanism for arbitrary CLI
callers. Run with the qualified scoring interpreter.
"""
from argparse import Namespace
from contextlib import contextmanager
from copy import deepcopy
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from workflow import run
from workflow.identifiers import present_assignment, restore_assignment, expand_outcome, wire_outcome_schema
from workflow.native_episode import unique_json, validate_outcome
from workflow.session import digest

RUNTIME_KEYS = {'environment_source', 'host_root', 'sdk_python', 'owner_home'}
OPTIONAL_RUNTIME_KEYS = {'bundle_root', 'scoring_python', 'state_root', 'specialist_revision'}
TASK_KEYS = {'schema_version', 'workflow_state', 'assignment_id', 'reference_representation', 'objective', 'limits'}
OPERATIONS = {'inspect', 'evidence', 'evidence_part', 'apply', 'collect'}
PART_CHARACTERS = 30_000
MAX_PART_JSON_CHARACTERS = 48_000


def _regular(path, *, directory=False):
    path = Path(path).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Task and state paths must not traverse symbolic links')
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError('An existing regular task file or state directory is required')
    return path.resolve()


def _private(path, runtime, *, directory=False):
    path = _regular(path, directory=directory)
    owner = Path(runtime['owner_home']).expanduser().resolve()
    if (path.is_relative_to(run.BUNDLE.parent) or path.is_relative_to(owner)
            or path.is_relative_to(Path(runtime['host_root']).expanduser().resolve())):
        raise ValueError('Keep task and campaign outside the checkout and owning profile')
    return path


def _task(request):
    if not isinstance(request, dict) or set(request) - {'operation', 'task_file', 'runtime', 'episode', 'part', 'outcome', 'caller'}:
        raise ValueError('Unsupported bridge request fields')
    if request.get('operation') not in OPERATIONS:
        raise ValueError('Unknown bridge operation')
    runtime = request.get('runtime')
    if (not isinstance(runtime, dict) or not RUNTIME_KEYS <= set(runtime)
            or set(runtime) - RUNTIME_KEYS - OPTIONAL_RUNTIME_KEYS
            or any(not isinstance(v, str) or not v for v in runtime.values())):
        raise ValueError('Explicit qualified host runtime paths are required')
    if runtime.get('bundle_root') and Path(runtime['bundle_root']).resolve() != run.BUNDLE.resolve():
        raise ValueError('Installed bundle path differs from the running host bridge')
    path = _private(request['task_file'], runtime)
    if path.suffix.lower() != '.md' or path.stat().st_size > 1_000_000:
        raise ValueError('Use a Markdown task file no larger than one megabyte')
    raw = path.read_bytes()
    blocks = re.findall(r'^```json[ \t]*\r?\n(.*?)^```[ \t]*$', raw.decode('utf-8-sig'), flags=re.MULTILINE | re.DOTALL)
    if len(blocks) != 1:
        raise ValueError('Task Markdown must contain exactly one fenced json assignment')
    task = unique_json(blocks[0])
    if not isinstance(task, dict) or set(task) != TASK_KEYS or type(task.get('schema_version')) is not int or task['schema_version'] != 1:
        raise ValueError('Task assignment must use the exact schema_version 1 fields')
    if not isinstance(task['workflow_state'], str) or not Path(task['workflow_state']).is_absolute():
        raise ValueError('workflow_state must name the original absolute private state path')
    state = _private(task['workflow_state'], runtime, directory=True)
    if runtime.get('state_root') and not state.is_relative_to(_regular(runtime['state_root'], directory=True)):
        raise ValueError('Campaign is outside the configured state root')
    caller = request.get('caller')
    if not isinstance(caller, dict) or Path(caller.get('home', '')).resolve() != Path(runtime['owner_home']).resolve():
        raise ValueError('SDK caller provenance must match the owning profile')
    if request['operation'] in {'evidence', 'evidence_part', 'apply'} and (
            caller.get('specialist') != 'smallmol-investigation'
            or not runtime.get('specialist_revision')
            or caller.get('revision') != runtime['specialist_revision']
            or caller.get('transport') != 'native-specialist-tool'
            or not isinstance(caller.get('session_id'), str)
            or not caller['session_id'].strip() or len(caller['session_id']) > 256):
        raise ValueError('SDK-verified named-specialist provenance is required')
    args = Namespace(state_dir=state, **{k: runtime[k] for k in RUNTIME_KEYS}, invoke=False, native_timeout=None, execute=True)
    return task, path, hashlib.sha256(raw).hexdigest(), args


@contextmanager
def _locked(state):
    fd = os.open(state / '.delegated-bridge.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('This assignment already has an active host operation') from None
        yield
    finally:
        os.close(fd)


def _bind(task, session):
    expected = {'assignment_id': session.assignment_id,
                'reference_representation': session.spec['reference']['representation'],
                'objective': session.spec['objective'], 'limits': session.spec['limits']}
    if any(task[key] != value for key, value in expected.items()):
        raise ValueError('Task identity, reference, objective or limits differ from the prepared assignment')


def _faults(state):
    return sorted(state.glob('delegated-bridge-fault-*.json'))


def _replace(path, data):
    """Atomic private-state update while the assignment lock is held."""
    if path.is_symlink():
        raise ValueError('Private bridge state cannot be a symbolic link')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    run._write(temporary, data)
    os.replace(temporary, path)


def _admission_state(state):
    path = state / 'delegated-native-sessions.json'
    return run._read(path) if path.exists() else {'sessions': {}}


def _admit_native(state, session, caller):
    admissions = _admission_state(state)
    identity = caller['session_id']
    if identity in admissions['sessions']:
        if admissions['sessions'][identity] != caller:
            raise ValueError('An admitted native session changed its caller provenance')
        return True
    if len(admissions['sessions']) >= session.spec['limits']['max_episodes']:
        return False
    admissions['sessions'][identity] = deepcopy(caller)
    _replace(state / 'delegated-native-sessions.json', admissions)
    return True


def _open_packet(state):
    folders = sorted((state / 'episodes').glob('episode-*'))
    return bool(folders and (folders[-1] / 'wire.json').is_file()
                and not (folders[-1] / 'execution.json').exists())


def _close_terminal(state, session):
    status = run._status(session, new_episode=False)
    if status['phase'] == 'frozen' or any(a['state'] not in run.SETTLED for a in session.attempts()):
        return status
    reason = None
    if status['qualified_candidate_ids']:
        reason = 'objective_achieved'
    elif status['phase'] in run.CLOSE_EMPTY:
        reason = status['phase']
    elif not _open_packet(state):
        if status['episodes_started'] >= session.spec['limits']['max_episodes']:
            reason = 'episode_allowance_reached'
        elif len(_admission_state(state)['sessions']) >= session.spec['limits']['max_episodes']:
            reason = 'native_session_admission_allowance_reached'
    if reason:
        session.finish(status['qualified_candidate_ids'] if reason == 'objective_achieved' else [], reason)
        status = run._status(session, new_episode=False)
        status['host_terminal_close'] = {'objective_achieved': reason == 'objective_achieved', 'stop_reason': reason}
    return status


def _parts(packet):
    """Lossless data transport, bounded below the SDK's tool-result spill cap."""
    text = json.dumps({'assignment': packet['assignment'], 'outcome_schema': packet['outcome_schema']},
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    parts, offset = [], 0
    while offset < len(text):
        low, high = 1, min(PART_CHARACTERS, len(text) - offset)
        while low < high:
            middle = (low + high + 1) // 2
            if len(json.dumps({'content': text[offset:offset + middle]})) < MAX_PART_JSON_CHARACTERS - 2000:
                low = middle
            else:
                high = middle - 1
        parts.append(text[offset:offset + low])
        offset += low
    return text, parts


def _delivered(folder, caller, packet, parts=None):
    path = folder / 'evidence-delivery.json'
    delivery = run._read(path) if path.exists() else {'wire_input_digest': packet['assignment']['input_digest'], 'sessions': {}}
    if delivery['wire_input_digest'] != packet['assignment']['input_digest']:
        raise ValueError('Evidence delivery record belongs to another snapshot')
    seen = delivery['sessions'].setdefault(caller['session_id'], [])
    if parts is not None:
        delivery['sessions'][caller['session_id']] = sorted(set(seen) | set(parts))
        _replace(path, delivery)
    return set(delivery['sessions'][caller['session_id']])


def _folder(state, episode):
    if type(episode) is not int or episode < 1:
        raise ValueError('An original positive episode number is required')
    return _regular(state / 'episodes' / ('episode-' + str(episode).zfill(4)), directory=True)


def _packet(folder, task_path, task_sha):
    packet = run._read(folder / 'wire.json')
    if packet['task_file'] != str(task_path) or packet['task_file_sha256'] != task_sha:
        raise ValueError('Task file changed after the evidence packet was prepared')
    canonical = run._read(folder / 'assignment.json')
    if restore_assignment(packet['assignment'], packet['alias_manifest']) != canonical:
        raise ValueError('Prepared packet and canonical assignment disagree')
    return packet, canonical


def _delivery_result(folder, packet, session, caller):
    text, parts = _parts(packet)
    full = {'assignment': packet['assignment'], 'outcome_schema': packet['outcome_schema']}
    result = {'phase': 'evidence_ready', 'episode': int(folder.name.split('-')[-1])}
    if len(parts) == 1 and len(text) <= PART_CHARACTERS and len(json.dumps(full)) < MAX_PART_JSON_CHARACTERS:
        _delivered(folder, caller, packet, [1])
        return {**result, 'delivery': 'inline', 'evidence': full}
    manifest = {'assignment_id': packet['assignment']['assignment_id'],
                'episode_id': packet['assignment']['episode_id'],
                'input_digest': packet['assignment']['input_digest'],
                'fixed_reference': deepcopy(session.spec['reference']),
                'objective': deepcopy(session.spec['objective']), 'limits': deepcopy(session.spec['limits']),
                'outcome_schema': packet['outcome_schema'],
                'total_parts': len(parts),
                'part_sha256': [hashlib.sha256(p.encode()).hexdigest() for p in parts],
                'packet_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'encoding': 'UTF-8 JSON data: concatenate content from evidence_part 1 through total_parts, then parse the exact full assignment and outcome_schema',
                'requirement': 'Retrieve every part before deciding; the manifest is not the complete scientific evidence.'}
    if len(json.dumps(manifest)) > 20_000:
        raise ValueError('Fixed evidence manifest exceeds the supported transport size')
    _delivered(folder, caller, packet)
    return {**result, 'delivery': 'paged', 'evidence_manifest': manifest}


def _evidence(args, state, session, task_path, task_sha, caller):
    attention = run._pending_attention(session)
    if attention:
        return {'phase': 'needs_attention', 'reason': attention}
    status = run._status(session, new_episode=False)
    if status['phase'] != 'ready':
        return status
    folders = sorted((state / 'episodes').glob('episode-*'))
    folder = None
    if folders:
        latest = _regular(folders[-1], directory=True)
        executed = latest / 'execution.json'
        if executed.exists():
            if run._read(executed).get('phase') not in {'waiting', 'completed', 'stopped'}:
                return {'phase': 'needs_attention', 'reason': 'Previous episode needs review'}
        else:
            if not (latest / 'wire.json').is_file() or (latest / 'native-result.json').exists():
                return {'phase': 'needs_attention', 'reason': 'Existing preparation needs review; no replacement episode was created'}
            folder = latest
    if folder is None:
        prepared = run._prepare(args, state, session)
        if prepared['phase'] != 'prepared':
            return prepared
        folder = Path(prepared['episode_directory'])
        canonical = run._read(folder / 'assignment.json')
        wire, manifest = present_assignment(canonical)
        schema = wire_outcome_schema(run._read(run.BUNDLE / 'specialist/optimization-v1/outcome.schema.json'))
        run._write(folder / 'wire.json', {'assignment': wire, 'alias_manifest': manifest, 'outcome_schema': schema,
                                        'task_file': str(task_path), 'task_file_sha256': task_sha})
    packet, canonical = _packet(folder, task_path, task_sha)
    if canonical['evidence_snapshot_digest'] != digest(session.report()):
        return {'phase': 'needs_attention', 'reason': 'Prepared evidence is stale; no replacement episode was created'}
    return _delivery_result(folder, packet, session, caller)


def _evidence_part(request, state, session, task_path, task_sha):
    folder = _folder(state, request.get('episode'))
    if (folder / 'execution.json').exists() or (folder / 'delegated-apply-intent.json').exists():
        return {'phase': 'needs_attention', 'reason': 'This episode has already been applied or has an unresolved intent'}
    packet, assignment = _packet(folder, task_path, task_sha)
    if assignment['evidence_snapshot_digest'] != digest(session.report()):
        return {'phase': 'needs_attention', 'reason': 'The requested evidence snapshot is stale'}
    text, parts = _parts(packet)
    part = request.get('part')
    if type(part) is not int or not 1 <= part <= len(parts):
        raise ValueError('Part must be a one-based index within the manifest')
    delivered = _delivered(folder, request['caller'], packet, [part])
    content = parts[part - 1]
    result = {'phase': 'evidence_part', 'episode': request['episode'], 'part': part,
              'total_parts': len(parts), 'content': content,
              'sha256': hashlib.sha256(content.encode()).hexdigest(),
              'packet_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'input_digest': packet['assignment']['input_digest'],
              'all_parts_delivered': len(delivered) == len(parts)}
    if len(json.dumps(result)) >= 50_000:
        raise ValueError('Evidence data part exceeds the supported transport size')
    return result


def _apply(request, args, state, session, task_path, task_sha):
    folder = _folder(state, request.get('episode'))
    if (folder / 'execution.json').exists() or (folder / 'delegated-apply-intent.json').exists():
        return {'phase': 'needs_attention', 'reason': 'This episode already has an execution or unresolved apply intent; it was not repeated'}
    packet, assignment = _packet(folder, task_path, task_sha)
    _, parts = _parts(packet)
    if _delivered(folder, request['caller'], packet) != set(range(1, len(parts) + 1)):
        return {'phase': 'needs_attention', 'reason': 'Retrieve all evidence data parts in this native session before applying a decision'}
    outcome = deepcopy(request.get('outcome'))
    validate_outcome(packet['assignment'], outcome, packet['outcome_schema'])
    expanded = expand_outcome(outcome, packet['alias_manifest'])
    validate_outcome(assignment, expanded, run._read(run.BUNDLE / 'specialist/optimization-v1/outcome.schema.json'))
    from workflow.controller import advance_delegated
    run._write(folder / 'delegated-apply-intent.json', {'task_file_sha256': task_sha,
               'episode_id': assignment['episode_id'], 'wire_outcome': outcome, 'caller': request['caller']})
    result = advance_delegated(session, assignment, outcome, packet['alias_manifest'], run._dispatcher(args, state), provenance=request['caller'])
    run._write(folder / 'execution.json', result)
    return {**result, 'episode': request['episode'], 'next': run._status(session)}


def handle_request(request):
    """Process one host operation; never initialize, invoke a model or retry."""
    task, task_path, task_sha, args = _task(request)
    state = Path(args.state_dir)
    with _locked(state):
        loaded, session = run._load(args)
        _bind(task, session)
        operation = request['operation']
        status = _close_terminal(state, session)
        if operation == 'inspect':
            return {**status, 'task_file_sha256': task_sha,
                    'native_session_admissions': len(_admission_state(state)['sessions']),
                    'native_session_admission_allowance': session.spec['limits']['max_episodes'],
                    'native_invocation_or_total_llm_cap': 'not established; a denied child may already have invoked a model',
                    'bridge_faults_requiring_review': len(_faults(state))}
        if status['phase'] == 'frozen':
            return status
        if operation in {'evidence', 'evidence_part', 'apply'} and _faults(state):
            return {'phase': 'needs_attention', 'reason': 'A previous host processing fault needs review'}
        try:
            if operation in {'evidence', 'evidence_part'} and not _admit_native(state, session, request['caller']):
                return {'phase': 'needs_attention', 'reason': 'Distinct native-session admission allowance reached; no evidence was delivered'}
            if operation == 'apply' and request['caller']['session_id'] not in _admission_state(state)['sessions']:
                return {'phase': 'needs_attention', 'reason': 'This native session has not been admitted to the evidence snapshot'}
            if operation == 'evidence':
                return _evidence(args, state, session, task_path, task_sha, request['caller'])
            if operation == 'evidence_part':
                return _evidence_part(request, state, session, task_path, task_sha)
            if operation == 'apply':
                return _apply(request, args, state, session, task_path, task_sha)
            attention = run._pending_attention(session)
            if attention:
                return {'phase': 'needs_attention', 'reason': attention}
            result = run._collect(args, state, session)
            result['next'] = _close_terminal(state, session)
            return result
        except Exception as exc:
            fault = state / ('delegated-bridge-fault-' + uuid.uuid4().hex + '.json')
            run._write(fault, {'operation': operation, 'error_type': type(exc).__name__,
                              'task_file_sha256': task_sha, 'reason': str(exc)})
            return {'phase': 'needs_attention', 'reason': 'Host operation failed; review original private evidence before retrying',
                    'error_type': type(exc).__name__, 'private_fault': str(fault)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--response', type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    request = unique_json(_regular(args.request).read_text() if args.request else sys.stdin.read())
    result = handle_request(request)
    if args.response:
        run._write(args.response, result)
    else:
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
