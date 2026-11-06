"""Native campaign tool; scientific execution stays in the qualified host.

Runtime paths are installed profile data, never model arguments. The caller role
comes from the SDK's current SpecialistPolicy, not claimed JSON fields.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

EXPECTED_SPECIALIST = 'smallmol-investigation'
RUNTIME_FILE = Path(__file__).with_name('runtime.json')
PATH_KEYS = frozenset({'bundle_root', 'environment_source', 'host_root', 'sdk_python',
                       'scoring_python', 'owner_home', 'state_root'})
SCHEMA = {
    'name': 'smallmol_campaign',
    'description': ('Inspect or collect an initialized small-molecule task. The named molecular '
                    'specialist can obtain bounded evidence and apply an identity-bound decision.'),
    'parameters': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'operation': {'type': 'string', 'enum': ['inspect', 'evidence', 'evidence_part', 'apply', 'collect']},
            'task_file': {'type': 'string', 'description': 'Absolute path to the initialized molecular task Markdown.'},
            'episode': {'type': 'integer', 'minimum': 1, 'description': 'Exact episode number returned by evidence; evidence_part or apply only.'},
            'part': {'type': 'integer', 'minimum': 1, 'description': 'Evidence part number from the manifest; evidence_part only.'},
            'outcome': {'type': 'object', 'description': 'The specialist decision matching the evidence outcome schema; apply only.'},
        },
        'required': ['operation', 'task_file'],
    },
}
ROUTING_HINT = (
    'For a scoped small-molecule optimization task supplied as a prompt or Markdown, '
    'load smallmol-optimization:smallmol-routing. For initialized task files use '
    'smallmol_campaign inspect and delegate the investigation to the saved '
    'smallmol-investigation specialist. Only that native specialist may request '
    'evidence or apply decisions. The main agent may inspect or collect original '
    'jobs and present actual results. An unsupported or uninitialized task needs '
    'explicit intake, not assumed objectives or fabricated authorization.'
)


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('A regular installed JSON file is required')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('An installed configuration object is required')
    return value


def _no_symlink(path):
    return not any(p.is_symlink() for p in (path, *path.parents))


def _runtime():
    if not _no_symlink(Path(RUNTIME_FILE)):
        raise ValueError('Installed runtime configuration cannot be a symbolic link')
    runtime = _json(RUNTIME_FILE)
    if set(runtime) != PATH_KEYS | {'specialist_revision'}:
        raise ValueError('Installed runtime configuration has unsupported or missing fields')
    if not isinstance(runtime['specialist_revision'], str) or not runtime['specialist_revision']:
        raise ValueError('The installed native specialist revision is required')
    for key in PATH_KEYS:
        value = runtime[key]
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Installed runtime paths must be absolute text')
        # Existing prepared Python executables can legitimately be symlinks.
        if key not in {'scoring_python', 'sdk_python'} and not _no_symlink(Path(value)):
            raise ValueError('Installed runtime directories cannot be symbolic links')
    for key in ('bundle_root', 'environment_source', 'host_root', 'owner_home', 'state_root'):
        if not Path(runtime[key]).is_dir():
            raise ValueError('An installed runtime directory is unavailable')
    for key in ('scoring_python', 'sdk_python'):
        if not Path(runtime[key]).is_file() or not os.access(runtime[key], os.X_OK):
            raise ValueError('An already prepared runtime interpreter is required')
    if not (Path(runtime['bundle_root']) / 'workflow/delegated_bridge.py').is_file():
        raise ValueError('The installed host bridge source is unavailable')
    if not (Path(runtime['environment_source']) / 'leadopt_env/core.py').is_file():
        raise ValueError('The installed molecular environment source is unavailable')
    return runtime


def _caller(runtime, operation):
    from sci_constants import get_sci_home
    from agent.specialist_policy import current_policy
    home = str(get_sci_home().resolve())
    if home != str(Path(runtime['owner_home']).resolve()):
        raise PermissionError('The plugin belongs to a different owning profile')
    policy = current_policy()
    if policy is None:
        if operation not in {'inspect', 'collect'}:
            raise PermissionError('Delegate evidence and decisions to the native molecular specialist')
        return {'transport': 'main-agent-tool', 'home': home}, 120.0
    if (policy.name != EXPECTED_SPECIALIST or policy.revision != runtime['specialist_revision']
            or policy.home != home):
        raise PermissionError('This specialist is not the installed molecular investigator')
    from gateway.session_context import get_session_env
    session_id = get_session_env('SCI_SESSION_ID', '')
    if not isinstance(session_id, str) or not session_id.strip():
        raise PermissionError('The native specialist session identity is unavailable')
    remaining = policy.deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0:
        raise PermissionError('The native specialist episode has expired')
    return {'transport': 'native-specialist-tool', 'specialist': policy.name,
            'revision': policy.revision, 'home': home,
            'session_id': session_id}, min(120.0, remaining)


def _arguments(args):
    if not isinstance(args, dict) or set(args) - {'operation', 'task_file', 'episode', 'part', 'outcome'}:
        raise ValueError('Only the declared campaign arguments are accepted')
    operation = args.get('operation')
    if operation not in {'inspect', 'evidence', 'evidence_part', 'apply', 'collect'}:
        raise ValueError('Choose a declared campaign operation')
    task = args.get('task_file')
    if not isinstance(task, str) or not Path(task).is_absolute():
        raise ValueError('An absolute initialized task-file path is required')
    if not _no_symlink(Path(task)) or not Path(task).is_file():
        raise ValueError('A regular initialized task file is required')
    if operation == 'apply':
        if (type(args.get('episode')) is not int or args['episode'] < 1
                or not isinstance(args.get('outcome'), dict) or 'part' in args):
            raise ValueError('Apply requires the exact evidence episode and structured outcome')
    elif operation == 'evidence_part':
        if (type(args.get('episode')) is not int or args['episode'] < 1
                or type(args.get('part')) is not int or args['part'] < 1 or 'outcome' in args):
            raise ValueError('Evidence parts require exact manifest episode and positive part number')
    elif {'episode', 'part', 'outcome'} & set(args):
        raise ValueError('Episode and part are accepted for evidence parts; episode and outcome for apply')
    return dict(args)


def _write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def _response(value):
    return json.dumps(value, allow_nan=False)


def _routing_hint(session_info):
    from agent.specialist_policy import current_policy
    # The investigator already has its selected skill and role instructions.
    # Routing guidance belongs in the main agent's cached prompt only.
    return ROUTING_HINT if current_policy() is None else ''


def handle(args, **kwargs):
    """One bounded bridge process. A timeout never triggers an automatic retry."""
    try:
        arguments = _arguments(args)
        runtime = _runtime()
        caller, timeout = _caller(runtime, arguments['operation'])
    except Exception as exc:
        return _response({'phase': 'blocked', 'reason': 'Campaign request or installed runtime validation failed',
                          'error_type': type(exc).__name__, 'scientific_execution_confirmed': False})
    try:
        rpc_root = Path(runtime['state_root']) / 'main-entry-rpc'
        if not _no_symlink(rpc_root):
            raise ValueError('RPC state cannot be a symbolic link')
        rpc_root.mkdir(mode=0o700, exist_ok=True)
        if rpc_root.stat().st_mode & 0o077:
            raise ValueError('RPC state must be private')
        folder = Path(tempfile.mkdtemp(prefix='call-', dir=rpc_root))
        request, response = folder / 'request.json', folder / 'response.json'
        _write(request, {'runtime': runtime, **arguments, 'caller': caller})
        env = dict(os.environ)
        for name in ('__SCI_ACTIVATED', '__SCI_TEST_PYTHON', 'PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
            env.pop(name, None)
        env.update({'PYTHONDONTWRITEBYTECODE': '1', 'SCI_DISABLE_LAZY_INSTALLS': '1'})
        command = [runtime['scoring_python'], '-B', '-m', 'workflow.delegated_bridge',
                   '--request', str(request), '--response', str(response)]
        try:
            process = subprocess.run(command, cwd=runtime['bundle_root'], env=env,
                                     capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            _write(folder / 'process.json', {'phase': 'outcome_unknown', 'reason': 'host_process_timeout',
                                           'recorded_utc': datetime.now(timezone.utc).isoformat()})
            return _response({'phase': 'needs_attention', 'reason': 'Host process timed out; do not repeat the action',
                              'private_rpc_directory': str(folder), 'scientific_execution_confirmed': False,
                              'execution_outcome': 'unknown'})
        _write(folder / 'process.json', {'returncode': process.returncode,
                                        'stdout': process.stdout, 'stderr': process.stderr})
        if process.returncode != 0 or not response.is_file():
            return _response({'phase': 'needs_attention', 'reason': 'Host process did not retain a qualified response',
                              'private_rpc_directory': str(folder), 'scientific_execution_confirmed': False,
                              'execution_outcome': 'unknown'})
        return _response(_json(response))
    except Exception as exc:
        return _response({'phase': 'needs_attention', 'reason': 'Local bridge failure; preserve original state before continuing',
                          'error_type': type(exc).__name__, 'scientific_execution_confirmed': False,
                          'execution_outcome': 'unknown'})


def register(ctx):
    runtime = _runtime()
    from sci_constants import get_sci_home
    if Path(runtime['owner_home']).resolve() != get_sci_home().resolve():
        raise ValueError('Install this plugin in its owning profile')
    ctx.register_tool(name='smallmol_campaign', toolset='smallmol_optimization', schema=SCHEMA,
                      handler=handle, description=SCHEMA['description'])
    ctx.register_skill('smallmol-routing', Path(runtime['bundle_root']) / 'integration/skills/smallmol-routing/SKILL.md',
                       description='Delegate scoped molecular optimization tasks.')
    ctx.register_system_prompt_section('smallmol.optimization-routing', _routing_hint, max_chars=1200)
