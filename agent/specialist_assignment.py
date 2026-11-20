"""Immutable handoffs and bounded effect evidence for one specialist assignment."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

from sci_constants import get_sci_home, mkdir_under_sci_home
from utils import atomic_json_write


@dataclass(frozen=True)
class Assignment:
    id: str
    home: str
    request: str
    contract: str

    def context(self):
        return ("Original user assignment (inherited unchanged; parent handoffs cannot replace its inputs, "
                "parameters, limits or output requirements):\n" + self.request +
                "\n\nFrozen assignment contract:\n" + self.contract +
                "\nExecute only your assigned part. Wait for dependent results before auditing. "
                "Use the exact returned job IDs and artifact paths, never nearby historical results. "
                "A worker timeout is not evidence that external work did not happen. Reconcile recorded "
                "effects before retrying or reporting no submissions/cost. Do not substitute inputs. "
                "The structured contract above is canonical; a checksum retyped in a parent's prose cannot "
                "replace it. Pass exact paths through artifacts rather than copying checksums into handoffs.")


def current_assignment():
    from agent.specialist_policy import current_policy
    policy = current_policy()
    assignment = getattr(policy, 'assignment', None)
    return assignment if isinstance(assignment, Assignment) else None


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(parent, tasks, contract=None):
    """Run before constructing any child. Independent parallel assignments remain supported."""
    from tools.delegate_tool_results import _CHILD_CONSTRUCTION_LOCK
    with _CHILD_CONSTRUCTION_LOCK:
        return _prepare(parent, tasks, contract)


def _check_resume(assignment, contract):
    """Redundant handoff assertions may confirm saved evidence, never replace it."""
    if set(contract) - {'resume', 'inputs', 'tool_arguments', 'max_submissions'}:
        raise ValueError('Resume accepts the saved assignment ID and optional unchanged input/parameter assertions only.')
    original = json.loads(assignment.contract)
    for key in ('tool_arguments', 'max_submissions'):
        if contract.get(key, {}) not in ({}, original[key]):
            raise ValueError('Resume cannot change saved execution parameters or limits. Pass assignment.resume only.')
    if 'inputs' in contract:
        verified_artifacts(assignment, contract['inputs'])


def _prepare(parent, tasks, contract):
    policy = getattr(parent, '_specialist_policy', None)
    inherited = getattr(policy, 'assignment', None)
    if isinstance(inherited, Assignment):
        if isinstance(contract, dict) and contract.get('resume') == inherited.id:
            _check_resume(inherited, contract)
            parent._specialist_assignment = inherited
            return
        if contract is not None and contract != {'resume': inherited.id} and json.dumps(contract, sort_keys=True) != inherited.contract:
            raise ValueError('Children cannot replace the frozen assignment contract. Return the mismatch to the parent.')
        parent._specialist_assignment = inherited
        return
    request = getattr(parent, '_specialist_user_request', '')
    request = request if isinstance(request, str) else ''
    explicit = re.match(r'\s*Use my saved specialist ([\w-]+) for this assignment through delegate_task\b', request, re.I)
    if explicit and len(tasks) == 1 and not tasks[0].get('specialist'):
        tasks[0]['specialist'] = explicit[1].casefold()
    if not any(task.get('specialist') for task in tasks):
        if explicit:
            raise ValueError(f'This assignment explicitly selects {explicit[1]}. Dispatch that specialist once.')
        if contract is not None:
            raise ValueError('Assignment contracts require tasks[].specialist. Choose a saved specialist; '
                             'ordinary delegation without an assignment contract is unchanged.')
        return
    snapshot = getattr(parent, '_specialist_snapshot', {})
    selected = {task.get('specialist') for task in tasks}
    for name in selected:
        pending = list(getattr(snapshot.get(name), 'children', ()))
        visited = {name}
        while pending:
            child = pending.pop()
            if child in visited:
                continue
            if child in selected:
                raise ValueError('Do not dispatch a specialist and its descendants in parallel. Start the root '
                                 'specialist once; it delegates its own approved subtasks.')
            visited.add(child)
            pending.extend(getattr(snapshot.get(child), 'children', ()))
    if explicit and (len(tasks) != 1 or tasks[0].get('specialist') != explicit[1].casefold()):
        raise ValueError(f'This assignment explicitly selects {explicit[1]}. Dispatch that specialist once.')
    if contract is not None and any(not task.get('specialist') for task in tasks):
        raise ValueError('All tasks sharing an assignment contract must select a saved specialist.')
    existing = getattr(parent, '_specialist_assignment', None)
    if isinstance(existing, Assignment):
        if contract is None:
            return
    if contract is None:
        from agent.specialist_inputs import approved_paths
        supplied = approved_paths(SimpleNamespace(sources=(), source_manifest=''), request)
        contract = {'inputs': [path for path in supplied if Path(path).is_file()]}
    if isinstance(contract, dict) and 'resume' in contract:
        identity = contract['resume']
        if isinstance(existing, Assignment):
            if identity == existing.id:
                _check_resume(existing, contract)
                return
            raise ValueError('This turn already owns an assignment. Do not replace it with another assignment ID.')
        if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{32}', identity):
            raise ValueError('resume must name an existing assignment ID from this profile\'s run history.')
        restored = Assignment(identity, str(get_sci_home().resolve()), '', '')
        row = json.loads(_path(restored).read_text(encoding="utf-8-sig"))
        if row['assignment_id'] != identity:
            raise ValueError('Assignment evidence identity does not match.')
        restored = Assignment(identity, restored.home, row['request'], row['contract'])
        _check_resume(restored, contract)
        parent._specialist_assignment = restored
        return
    if not isinstance(contract, dict) or set(contract) - {'inputs', 'tool_arguments', 'max_submissions'}:
        raise ValueError('assignment accepts inputs, tool_arguments and max_submissions only.')
    inputs = contract.get('inputs', [])
    arguments = contract.get('tool_arguments', {})
    limits = contract.get('max_submissions', {})
    if (not isinstance(inputs, list) or not all(isinstance(p, str) for p in inputs)
            or not isinstance(arguments, dict) or not all(isinstance(k, str) and
                (isinstance(v, dict) or isinstance(v, list) and v and all(isinstance(r, dict) for r in v))
                for k, v in arguments.items())
            or not isinstance(limits, dict) or not all(isinstance(k, str) and type(v) is int and v > 0 for k, v in limits.items())):
        raise ValueError('Invalid assignment inputs, tool_arguments or positive submission limits.')
    if limits:
        rules = [rule for value in arguments.values() for rule in (value if isinstance(value, list) else [value])]
        for job in limits:
            if not any(rule.get('job_name') == job and isinstance(rule.get('experiment_data'), dict)
                       and rule['experiment_data'] for rule in rules):
                raise ValueError(f'Missing submission parameters for {job}. Complete assignment.tool_arguments '
                                 'before delegation; no child or upload was started.')
        from sci_cli.specialist_children import hierarchy_depth
        from tools.delegate_tool_config import _get_max_spawn_depth, _get_orchestrator_enabled
        for task in tasks:
            item = snapshot.get(task.get('specialist'))
            if item and item.children:
                required = hierarchy_depth(item, snapshot)
                if not _get_orchestrator_enabled() or required > _get_max_spawn_depth():
                    raise ValueError('The reviewed hierarchy exceeds this profile\'s delegation limits. '
                                     'Review Approved children in /Update_subagent before execution; no task started.')
    pinned = {}
    for raw in inputs:
        path = Path(raw).expanduser().resolve(strict=True)
        if not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError('Assignment inputs must be regular files of at most 256 MiB.')
        pinned[str(path)] = _digest(path)
    frozen = json.dumps({'inputs': pinned, 'tool_arguments': arguments, 'max_submissions': limits}, sort_keys=True, allow_nan=False)
    if len(frozen) > 64000 or len(request) > 128000:
        raise ValueError('Assignment contract is too large; keep data in input files.')
    if isinstance(existing, Assignment):
        if frozen == existing.contract:
            return
        path = _path(existing)
        from sci_cli.plugins_state import _locked_plugin_state
        with _locked_plugin_state(path):
            row = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {'effects': {}}
            original = json.loads(existing.contract)
            if original['tool_arguments'] or original['max_submissions'] or any(
                    effect.get('kind') != 'artifact' for effect in row['effects'].values()):
                raise ValueError('This assignment already has a frozen contract. Reuse it; do not change inputs mid-run.')
            if any(pinned.get(p, digest) != digest for p, digest in original['inputs'].items()):
                raise ValueError('A registered input changed. Preserve the original input bytes before continuing.')
            pinned = {**original['inputs'], **pinned}
            frozen = json.dumps({'inputs': pinned, 'tool_arguments': arguments, 'max_submissions': limits},
                                sort_keys=True, allow_nan=False)
            if len(frozen) > 64000:
                raise ValueError('Assignment contract is too large; keep data in input files.')
            assignment = Assignment(existing.id, existing.home, existing.request, frozen)
            if path.exists():
                row['contract'] = frozen
                atomic_json_write(path, row, mode=0o600)
        parent._specialist_assignment = assignment
        return
    assignment = Assignment(uuid4().hex, str(get_sci_home().resolve()), request, frozen)
    parent._specialist_assignment = assignment


def persist(parent):
    """Only validated dispatches create durable assignment records."""
    assignment = getattr(parent, '_specialist_assignment', None)
    if not isinstance(assignment, Assignment):
        return
    path = _path(assignment)
    from sci_cli.plugins_state import _locked_plugin_state
    with _locked_plugin_state(path):
        if not path.exists():
            atomic_json_write(path, {'assignment_id': assignment.id, 'request': assignment.request,
                                    'contract': assignment.contract, 'effects': {}}, mode=0o600)


def check_arguments(name, arguments):
    assignment = current_assignment()
    if assignment is None:
        return None
    contract = json.loads(assignment.contract)
    expected = contract['tool_arguments'].get(name)
    from agent.specialist_assignment_bindings import bound_argument
    rows = None

    def matches(expected, actual, path=()):
        nonlocal rows
        if (isinstance(expected, str) and expected.startswith('<') and expected.endswith('>')
                or isinstance(expected, dict) and set(expected) == {'$input'}):
            if rows is None:
                location = _path(assignment)
                rows = list(json.loads(location.read_text(encoding="utf-8-sig"))['effects'].values()) if location.exists() else []
            return bound_argument(expected, actual, tool=name, path=path, arguments=arguments,
                                  contract=contract, effects=rows)
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(k in actual and matches(v, actual[k], (*path, k)) for k, v in expected.items())
        if type(expected) in (int, float) and type(actual) in (int, float):
            return expected == actual
        return type(expected) is type(actual) and expected == actual

    rules = expected if isinstance(expected, list) else [expected]
    if expected is not None and not any(matches(rule, arguments) for rule in rules):
        return 'Tool arguments conflict with the frozen assignment. No action started; preserve the original inputs and parameters.'
    return None


def check_input(path, digest):
    assignment = current_assignment()
    if assignment is None:
        return None
    pinned = json.loads(assignment.contract)['inputs']
    original = pinned.get(str(Path(path).expanduser().resolve()))
    if original is not None and original != digest:
        return 'A frozen input file changed. Preserve its original bytes and use a new path for derived data. No upload started.'
    if digest in pinned.values():
        return None
    from agent.specialist_policy import current_policy
    rows = evidence(SimpleNamespace(_specialist_policy=current_policy())).get('recorded_effects', [])
    if (any(row.get('terminal_confirmed') is True for row in rows)
            and any(row.get('kind') == 'artifact' and row.get('sha256') == digest for row in rows)):
        return None
    return 'Upload does not match a frozen input or a recorded result of a confirmed prior step. No upload started.'


def record_artifacts(paths, *, replace_existing=False, **provenance):
    for raw in paths:
        path = Path(raw).expanduser().resolve(strict=True)
        if not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError('Artifact cannot be verified within the 256 MiB inspection budget.')
        record_effect('artifact:' + hashlib.sha256(str(path).encode()).hexdigest(), replace_artifact=replace_existing,
                      kind='artifact', path=str(path), sha256=_digest(path), **provenance)


def verified_artifacts(assignment, paths):
    """A handoff can include unchanged frozen inputs and this assignment's recorded outputs."""
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ValueError('artifacts must be a list of exact input or output file paths.')
    path = _path(assignment)
    rows = json.loads(path.read_text(encoding="utf-8-sig"))['effects'].values() if path.exists() else []
    outputs = {row['path']: row['sha256'] for row in rows if row.get('kind') == 'artifact'}
    # An input recorded again as an artifact cannot replace its original frozen digest.
    outputs.update(json.loads(assignment.contract).get('inputs', {}))
    result = []
    for raw in paths:
        try:
            target = Path(raw).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError(f'Dependent artifact is unavailable: {raw}. Restore this exact file before delegation.') from exc
        if str(target) not in outputs:
            raise ValueError(f'Dependent artifact is not a frozen input or recorded output of this assignment: {target}. '
                             'Pass its recorded exact path; do not substitute historical files.')
        if not target.is_file() or _digest(target) != outputs[str(target)]:
            raise ValueError(f'Dependent artifact bytes changed: {target}. Restore the original bytes; '
                             'keep the remaining verified paths in artifacts.')
        result.append(str(target))
    return tuple(result)


def artifact_snapshot(paths):
    return tuple((path, _digest(Path(path))) for path in paths)


def _path(assignment):
    root = Path(assignment.home) / 'subagent-runs'
    if root.is_symlink():
        raise ValueError('Assignment evidence directory must not be a symbolic link.')
    mkdir_under_sci_home(root)
    path = root / f'assignment-{assignment.id}.json'
    if path.is_symlink():
        raise ValueError('Assignment evidence must not be a symbolic link.')
    return path


def record_effect(identity, *, replace_artifact=False, **facts):
    """Only explicit, credential-free facts supplied by the executing adapter belong here."""
    assignment = current_assignment()
    if assignment is None:
        return
    from sci_cli.plugins_state import _locked_plugin_state
    path = _path(assignment)
    with _locked_plugin_state(path):
        row = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {'assignment_id': assignment.id,
            'request': assignment.request, 'contract': assignment.contract, 'effects': {}}
        previous = row['effects'].get(identity, {})
        if previous.get('kind') == 'artifact' and not previous.get('native_write'):
            # Reporting a downloaded result again must not make its original bytes replaceable.
            facts['native_write'] = False
        if previous.get('kind') == 'artifact' and previous.get('sha256') != facts.get('sha256'):
            if not replace_artifact or not previous.get('native_write'):
                raise ValueError('A recorded artifact changed. Preserve the original output; write derived data to a new path.')
            facts['previous_sha256'] = [*previous.get('previous_sha256', []), previous['sha256']]
        row['effects'][identity] = {**row['effects'].get(identity, {}), **facts}
        if len(json.dumps(row)) > 1024 * 1024:
            raise ValueError('Assignment evidence reached its 1 MiB limit. Reconcile existing effects before continuing.')
        atomic_json_write(path, row, mode=0o600)


def track_file_result(name, result):
    """Record explicit file results, never paths guessed from prose or workspace scans."""
    if name not in {'write_file', 'patch', 'execute_code'} or current_assignment() is None:
        return result
    try:
        data = json.loads(result) if isinstance(result, str) else result
    except ValueError:
        return result
    if not isinstance(data, dict):
        return result
    files = data.get('files_modified')
    if name == 'execute_code':
        if data.get('status') not in {'success', 'error'}:
            return result
    elif data.get('error'):
        return result
    if not files:
        return result
    try:
        if not isinstance(files, list) or not all(isinstance(p, str) and Path(p).is_absolute() for p in files):
            raise ValueError('Return files_modified as a list of absolute output paths.')
        if name == 'execute_code':
            from tools.terminal_tool import _get_env_config
            if _get_env_config()['env_type'] != 'local':
                raise ValueError('Code output provenance requires files on the owning local filesystem.')
        record_artifacts(files, replace_existing=True, native_write=True,
                         producer_tool=name, producer_status=data.get('status', 'success'))
        data['files_modified'] = files
    except (OSError, ValueError, RuntimeError) as exc:
        data['assignment_evidence_warning'] = ('Tool completed, but artifact evidence failed (' +
            type(exc).__name__ + '). Preserve the file and reconcile before using it downstream. '
            'Return files_modified as absolute paths on the owning local filesystem; do not repeat completed analysis.')
    return json.dumps(data) if isinstance(result, str) else data


def evidence(child):
    policy = getattr(child, '_specialist_policy', None)
    assignment = getattr(policy, 'assignment', None)
    if not isinstance(assignment, Assignment):
        return {}
    try:
        path = _path(assignment)
        row = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {'effects': {}}
        return {'assignment_id': assignment.id, 'recorded_effects': list(row['effects'].values()),
                'recovery_note': 'Assignment-wide evidence, including sibling/descendant work. A timeout or empty '
                                 'record does not prove no remote side effects. Reconcile pending/unknown attempts; '
                                 'never infer zero cost or resubmit from a missing child summary.'}
    except (OSError, ValueError, KeyError) as exc:
        return {'assignment_id': assignment.id, 'evidence_error': type(exc).__name__,
                'recovery_note': 'Effect evidence unavailable. Outcome is unresolved; do not resubmit or claim no side effects.'}
