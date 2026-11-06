"""Small host-mediated investigator CLI; no work occurs on import.

Run with the qualified scoring Python. ``prepare --invoke`` explicitly requests
one native reasoning episode; ``execute --execute`` admits its scientific action.
``collect`` only observes original jobs and assesses downloaded results. ``step
--execute`` performs at most one collect/decision/action pass, never a retry loop.
``run --execute`` repeats safe passes within a bounded wait/deadline, without
reasoning while jobs wait. Unknown/faulted operations require operator attention.
All state, raw receipts, model results and logs stay in a private state directory.
"""
import argparse
from copy import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid


BUNDLE = Path(__file__).resolve().parents[1]
SETTLED = {'complete', 'failed', 'upload_blocked'}
CLOSE_EMPTY = {'deadline_reached', 'submission_allowance_reached', 'episode_allowance_reached', 'no_admissible_action'}


def _now():
    return datetime.now(timezone.utc)


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('A regular host-owned JSON file is required')
    return json.loads(path.read_text())


def _write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def _state_path(value):
    path = Path(value).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or path.resolve().is_relative_to(BUNDLE.parent):
        raise ValueError('Choose a private nonsymlink state directory outside the repository')
    return path.resolve()


def _store(args):
    source = Path(args.environment_source).expanduser().resolve()
    if not (source / 'leadopt_env/core.py').is_file():
        raise ValueError('--environment-source must identify the existing environment src directory')
    sys.path.insert(0, str(source))
    from leadopt_env.core import CampaignStore
    if not Path(sys.modules['leadopt_env.core'].__file__).resolve().is_relative_to(source):
        raise ValueError('Another environment source is already imported in this process')
    return CampaignStore


def _load(args):
    state = _state_path(args.state_dir)
    meta = _read(state / 'workflow.json')
    if Path(meta['environment_source']).resolve() != Path(args.environment_source).resolve():
        raise ValueError('Use the environment source recorded at initialization')
    if not (state / 'campaign.sqlite').is_file():
        raise ValueError('Original campaign database is missing; do not create a replacement')
    from workflow.session import WorkflowSession
    return state, WorkflowSession(_store(args)(state / 'campaign.sqlite'), meta['assignment_id'])


def _status(session, *, new_episode=True):
    view, attempts = session.search_view(), session.attempts()
    phase = 'ready'
    if view['assignment_frozen']:
        phase = 'frozen'
    elif view['evaluation_blockers']:
        phase = 'evaluation_blocked'
    elif view['qualified_candidate_ids']:
        phase = 'objective_achieved'
    elif any(a['state'] not in SETTLED for a in attempts):
        phase = 'waiting_or_reconciliation'
    elif _now() >= datetime.fromisoformat(session.spec['limits']['deadline_utc']):
        phase = 'deadline_reached'
    elif len(attempts) >= session.spec['limits']['max_scientific_submissions']:
        phase = 'submission_allowance_reached'
    elif not view['eligible_actions']:
        phase = 'no_admissible_action'
    with session.store._db() as db:
        episodes = db.execute('SELECT episodes FROM smallmol_assignments WHERE id=?', (session.assignment_id,)).fetchone()[0]
    if phase == 'ready' and new_episode and episodes >= session.spec['limits']['max_episodes']:
        phase = 'episode_allowance_reached'
    return {'phase': phase, 'assignment_id': session.assignment_id, 'campaign_id': session.campaign_id,
            'candidate_count': len(view['rows']), 'qualified_candidate_ids': view['qualified_candidate_ids'],
            'evaluation_blockers': view['evaluation_blockers'], 'episodes_started': episodes,
            'scientific_actions_reserved': len(attempts),
            'shared_prior_jobs': sum(bool(a.get('shared_prior')) for a in attempts),
            'actions': [{'action_key': a['action_key'], 'state': a['state']} for a in attempts]}


def _runtime(args):
    if not all(getattr(args, key, None) for key in ('host_root', 'sdk_python', 'owner_home')):
        raise ValueError('Explicit --host-root, --sdk-python and --owner-home are required for runtime operations')


def _dispatcher(args, state):
    _runtime(args)
    from workflow.connector_process import OwningHostDispatcher
    return OwningHostDispatcher(args.host_root, args.sdk_python, args.owner_home, state / 'connector-rpc',
                                timeout_seconds=getattr(args, 'connector_timeout', 120))


def initialize(args):
    state = _state_path(args.state_dir)
    if state.exists():
        raise ValueError('Initialization requires a fresh state directory; use inspect to resume')
    supplied = (args.common_csv, args.common_sha256, args.common_stage)
    if any(supplied) and not all(supplied):
        raise ValueError('Import requires --common-csv, --common-sha256 and --common-stage together')
    if all(supplied) and args.max_submissions < 1:
        raise ValueError('The shared prior counts as one scientific job in the declared allowance')
    protocol_path = Path(args.protocol).expanduser().resolve()
    protocol = _read(protocol_path)
    from workflow.context import from_property_protocol
    from workflow.session import WorkflowSession
    limits = {'max_scientific_submissions': args.max_submissions, 'max_episodes': args.max_episodes,
              'deadline_utc': args.deadline_utc}
    spec, task = from_property_protocol(protocol, args.assignment_id, state / 'artifacts', limits)
    stage = None
    if all(supplied):
        csv = Path(args.common_csv)
        sha = hashlib.sha256(csv.read_bytes()).hexdigest()
        stage = _read(args.common_stage)
        if 'stages' in stage:
            stage = stage['stages']['common']
        if sha != args.common_sha256 or sha != stage['batch']['artifact_sha256']:
            raise ValueError('Common CSV bytes do not match the supplied original result identity')
    state.mkdir(parents=True, mode=0o700)
    session = WorkflowSession.create(_store(args)(state / 'campaign.sqlite'), spec, task)
    if stage is not None:
        session.import_shared_prior(stage)
        session.import_csv(args.common_csv, {'artifact_sha256': args.common_sha256,
            'source': 'Completed shared prior job ' + stage['submit']['doc_id'] + '; original receipts retained in host campaign'},
            parent_id=spec['reference']['id'])
    _write(state / 'workflow.json', {'schema_version': 1, 'assignment_id': session.assignment_id,
        'source_protocol_sha256': hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        'source_protocol': str(protocol_path), 'environment_source': str(Path(args.environment_source).resolve()),
        'created_utc': datetime.now(timezone.utc).isoformat()})
    return _status(session)


def _prepare(args, state, session):
    status = _status(session)
    if status['phase'] != 'ready':
        return status
    if not args.host_root:
        raise ValueError('--host-root is required to read the canonical capability contract')
    contract_path = Path(args.host_root) / 'plugins/boltzmann/skills/boltzmann-tools/references/tool-contracts.v1.json'
    entry = _read(contract_path)['tools']['Fragment_Based_Optimization']
    if entry.get('status') != 'active' or entry.get('execution_blocked'):
        raise ValueError('Canonical CReM capability is unavailable or blocked')
    capability = {'execution_mode': 'host_mediated', 'job_name': 'Fragment_Based_Optimization',
                  'canonical_contract': entry, 'canonical_contract_sha256': hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                  'source_path': str(contract_path.resolve()),
                  'execution_boundary': 'Specialist requests one action; owning host validates and executes through the existing connector'}
    if args.invoke:
        _runtime(args)
        if state.is_relative_to(Path(args.owner_home).expanduser().resolve()):
            raise ValueError('Keep the isolated investigation state outside the original owning profile')
    if args.native_timeout is not None and args.native_timeout <= 0:
        raise ValueError('Native process timeout must be positive')
    from workflow.context import episode_context
    assignment = episode_context(session, capability)
    if assignment['resources']['scientific_submission_allowance_this_episode'] < 1:
        raise ValueError('No scientific action allowance was available for this episode')
    folder = state / 'episodes' / ('episode-' + str(status['episodes_started'] + 1).zfill(4))
    folder.mkdir(parents=True, mode=0o700)
    _write(folder / 'assignment.json', assignment)
    result = {'phase': 'prepared', 'episode_directory': str(folder), 'assignment_file': str(folder / 'assignment.json')}
    if not args.invoke:
        return result
    from workflow.runtime_launch import run_script
    home = folder / 'reasoning-home'; home.mkdir(mode=0o700)
    output = folder / 'native-result.json'
    remaining = (datetime.fromisoformat(session.spec['limits']['deadline_utc']) - _now()).total_seconds()
    role = _read(BUNDLE / 'specialist/optimization-v1/definition.json')
    timeout = min(args.native_timeout or role['timeout_seconds'] + 60, remaining)
    try:
        native = run_script(host_root=args.host_root, interpreter=args.sdk_python, sci_home=home,
            script=BUNDLE / 'workflow/native_episode.py', timeout_seconds=timeout,
            arguments=('--host-root', str(Path(args.host_root).resolve()), '--owner-home', str(Path(args.owner_home).resolve()),
                       '--assignment', str(folder / 'assignment.json'), '--output', str(output), '--mode', 'host_mediated'))
        _write(folder / 'process-output.json', {'returncode': native.returncode, 'stdout': native.stdout, 'stderr': native.stderr})
        passed = native.returncode == 0 and output.is_file() and _read(output).get('validation_status') == 'passed'
    except Exception as exc:
        _write(folder / 'process-output.json', {'error_type': type(exc).__name__, 'outcome': 'No qualified native episode result'})
        passed = False
    return {**result, 'phase': 'decision_ready' if passed else 'native_episode_failed',
            'native_result_file': str(output), 'scientific_submissions': 0}


def _episode(args, state):
    folder = state / 'episodes' / ('episode-' + str(args.episode).zfill(4))
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('An original prepared episode is required')
    return folder


def _execute(args, state, session):
    if not args.execute:
        return {'phase': 'execution_disabled', 'scientific_submissions': 0, 'required_option': '--execute'}
    folder = _episode(args, state)
    if (folder / 'execution.json').exists():
        return {'phase': 'already_executed', 'private_result': str(folder / 'execution.json')}
    status = _status(session, new_episode=False)
    if status['phase'] != 'ready':
        return status
    from workflow.controller import advance
    result = advance(session, _read(folder / 'assignment.json'), _read(folder / 'native-result.json'), _dispatcher(args, state))
    _write(folder / 'execution.json', result)
    return {'phase': result['phase'], 'action_key': result.get('action_key'), 'private_result': str(folder / 'execution.json')}


def _collect(args, state, session):
    from workflow.controller import collect
    result = collect(session, _dispatcher(args, state))
    path = state / ('collection-' + uuid.uuid4().hex + '.json')
    _write(path, result)
    return {'phase': 'collection_finished', 'outcomes': [{k: r[k] for k in ('action_key', 'phase') if k in r} for r in result],
            'private_result': str(path), 'next': _status(session)}


def _pending_attention(session):
    from workflow.session import native_status
    for action in session.attempts():
        if action['state'] in SETTLED:
            continue
        if action['state'] not in {'accepted', 'results_ready', 'downloaded'} or not action.get('submit', {}).get('doc_id'):
            return 'original_attempt_requires_reconciliation'
        monitor = action.get('monitor', {})
        if monitor.get('error') and native_status(monitor) != 'pending':
            return 'original_job_observation_requires_attention'
    return None


def _saved_episode(state):
    """Reuse the latest unexecuted valid decision; never repeat a blocked one."""
    folders = sorted(p for p in (state / 'episodes').glob('episode-*') if p.is_dir())
    if not folders:
        return None, None
    folder = folders[-1]
    if folder.is_symlink():
        return None, 'invalid_episode_path'
    execution = folder / 'execution.json'
    if execution.exists():
        phase = _read(execution).get('phase')
        return (None, None) if phase in {'waiting', 'completed', 'stopped'} else (None, 'previous_episode_requires_attention')
    native = folder / 'native-result.json'
    if not native.exists():
        return None, 'prepared_episode_has_no_qualified_native_result'
    result = _read(native)
    if result.get('validation_status') != 'passed' or result.get('mode') != 'host_mediated':
        return None, 'previous_native_episode_failed_or_unqualified'
    if result.get('outcome', {}).get('status') not in {'action_requested', 'completed', 'stopped'}:
        return None, 'previous_native_outcome_requires_attention'
    return int(folder.name.split('-')[-1]), None


def _step(args, state, session):
    """One shared collect/decision/action pass used by both step and run."""
    status = _status(session, new_episode=False)
    attention = _pending_attention(session)
    if attention:
        return {'phase': 'needs_attention', 'reason': attention}
    if any(a['state'] not in SETTLED for a in session.attempts()) and status['phase'] != 'frozen':
        collected = _collect(args, state, session)
        bad = [r for r in collected['outcomes'] if r.get('phase') not in {'waiting', 'observations_ready', 'complete', 'failed', 'upload_blocked'}]
        if bad:
            return {'phase': 'needs_attention', 'reason': 'artifact_or_local_processing_unfinished', 'private_result': collected['private_result']}
        status = _status(session, new_episode=False)
    if status['phase'] != 'ready' or not args.execute:
        return status
    episode, attention = _saved_episode(state)
    if attention:
        return {'phase': 'needs_attention', 'reason': attention}
    if episode is not None:
        args.episode = episode
        return _execute(args, state, session)
    status = _status(session)
    if status['phase'] != 'ready':
        return status
    args.invoke = True
    prepared = _prepare(args, state, session)
    if prepared['phase'] != 'decision_ready':
        return prepared
    args.episode = int(Path(prepared['episode_directory']).name.split('-')[-1])
    return _execute(args, state, session)


def _emit(value):
    print(json.dumps(value, sort_keys=True, allow_nan=False), flush=True)


def _run_report(state, session, started, phase, reason):
    status = _status(session)
    report = session.report()
    path = state / ('run-report-' + uuid.uuid4().hex + '.json')
    result = {'event': 'final', 'phase': phase, 'stop_reason': reason, 'status': status,
              'objective_satisfied': bool(status['qualified_candidate_ids']),
              'assignment_frozen': bool(report.get('freezes')), 'elapsed_seconds': round(time.monotonic() - started, 3),
              'recorded_usage': report.get('resource_summary', {}), 'limits': session.spec['limits'],
              'internal_backend_oracle_work': 'unknown',
              'source_protocol_digest': session.spec.get('source_protocol_digest'),
              'private_paths': {'state': str(state), 'campaign_database': str(session.store.path),
                                'artifacts': session.spec['artifact_directory'], 'native_usage': str(state / 'episodes'),
                                'run_report': str(path)}}
    try:
        _write(path, result)
    except Exception as exc:
        result['report_write_error'] = type(exc).__name__
    return result


def _run(args, state, session):
    """Bounded owner-driven loop; all scientific dispatch remains in _step."""
    for key, minimum in (('poll_seconds', 1), ('max_wait_seconds', 0)):
        value = getattr(args, key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < minimum or (minimum == 0 and value == 0):
            raise ValueError('Use a finite poll interval >=1 and positive maximum wait')
    if args.native_timeout is not None and (type(args.native_timeout) not in (int, float)
            or not math.isfinite(args.native_timeout) or args.native_timeout <= 0):
        raise ValueError('Native process timeout must be finite and positive')
    started = time.monotonic()
    if not args.execute:
        return _run_report(state, session, started, 'execution_disabled', 'Explicit --execute is required for the run loop')
    deadline = datetime.fromisoformat(session.spec['limits']['deadline_utc'])
    try:
        native_default = _read(BUNDLE / 'specialist/optimization-v1/definition.json')['timeout_seconds'] + 60
        while True:
            status = _status(session)
            settled = all(a['state'] in SETTLED for a in session.attempts())
            _emit({'event': 'progress', 'phase': status['phase'], 'candidate_count': status['candidate_count'],
                   'episodes_started': status['episodes_started'], 'scientific_actions_reserved': status['scientific_actions_reserved']})
            attention = _pending_attention(session)
            if attention:
                return _run_report(state, session, started, 'needs_attention', attention)
            if status['phase'] == 'frozen':
                return _run_report(state, session, started, 'frozen', 'assignment_already_frozen')
            if status['phase'] == 'objective_achieved' and settled:
                session.finish(status['qualified_candidate_ids'], 'objective_achieved')
                return _run_report(state, session, started, 'completed', 'objective_achieved')
            saved, attention = _saved_episode(state)
            if attention and settled:
                return _run_report(state, session, started, 'needs_attention', attention)
            if status['phase'] in CLOSE_EMPTY and settled and not (status['phase'] == 'episode_allowance_reached' and saved is not None):
                session.finish([], status['phase'])
                return _run_report(state, session, started, 'stopped', status['phase'])
            if status['phase'] == 'evaluation_blocked':
                return _run_report(state, session, started, 'needs_attention', 'unresolved_evaluation_blockers')
            remaining_deadline = (deadline - _now()).total_seconds()
            remaining_wait = args.max_wait_seconds - (time.monotonic() - started)
            if remaining_deadline <= 0:
                return _run_report(state, session, started, 'deadline_reached', 'Outstanding work remains; assignment was not frozen')
            if remaining_wait <= 0:
                return _run_report(state, session, started, 'max_wait_reached', 'Bounded driver wait elapsed; resume the original state')
            limited = copy(args)
            limited.connector_timeout = min(120, remaining_deadline, remaining_wait)
            limited.native_timeout = min(args.native_timeout or native_default, remaining_deadline, remaining_wait)
            recoveries = set(Path(session.spec['artifact_directory']).glob('receipt-recovery-*.json'))
            result = _step(limited, state, session)
            _emit({'event': 'progress', 'phase': result['phase']})
            if set(Path(session.spec['artifact_directory']).glob('receipt-recovery-*.json')) - recoveries:
                return _run_report(state, session, started, 'needs_attention', 'Private receipt recovery evidence requires review')
            if result['phase'] in {'needs_attention', 'blocked', 'waiting', 'native_episode_failed', 'upload_unfinished', 'submission_unresolved', 'prepared', 'already_executed'}:
                # waiting is healthy only with a concrete accepted original job.
                waiting = result['phase'] == 'waiting' and any(a['state'] == 'accepted' and a.get('submit', {}).get('doc_id') for a in session.attempts())
                if not waiting:
                    return _run_report(state, session, started, 'needs_attention', result.get('reason', result['phase']))
            after = _status(session)
            if after['phase'] == 'ready' and after == status:
                return _run_report(state, session, started, 'needs_attention', 'No durable progress was recorded')
            if any(a['state'] not in SETTLED for a in session.attempts()):
                delay = min(args.poll_seconds, 30, args.max_wait_seconds - (time.monotonic() - started), (deadline - _now()).total_seconds())
                if delay > 0:
                    time.sleep(delay)
    except KeyboardInterrupt:
        return _run_report(state, session, started, 'interrupted', 'Operator interrupted; original receipts retained for resume')
    except Exception as exc:
        return _run_report(state, session, started, 'needs_attention', 'Local failure: ' + type(exc).__name__)


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('init', 'inspect', 'prepare', 'execute', 'collect', 'step', 'run'):
        p = sub.add_parser(command)
        p.add_argument('--state-dir', type=Path, required=True)
        p.add_argument('--environment-source', type=Path, required=True)
        if command == 'init':
            p.add_argument('--protocol', type=Path, required=True)
            p.add_argument('--assignment-id', required=True)
            p.add_argument('--max-submissions', type=int, required=True)
            p.add_argument('--max-episodes', type=int, required=True)
            p.add_argument('--deadline-utc', required=True)
            p.add_argument('--common-csv', type=Path)
            p.add_argument('--common-sha256')
            p.add_argument('--common-stage', type=Path)
        if command in {'prepare', 'execute', 'collect', 'step', 'run'}:
            p.add_argument('--host-root', type=Path)
            p.add_argument('--sdk-python', type=Path)
            p.add_argument('--owner-home', type=Path)
        if command == 'prepare':
            p.add_argument('--invoke', action='store_true', help='Explicitly run one native model episode; no scientific submission')
        if command in {'prepare', 'step', 'run'}:
            p.add_argument('--native-timeout', type=float)
        if command in {'execute', 'step', 'run'}:
            p.add_argument('--execute', action='store_true', help='Explicitly admit the requested scientific action')
            p.add_argument('--episode', type=int, default=1)
        if command == 'run':
            p.add_argument('--poll-seconds', type=float, default=30)
            p.add_argument('--max-wait-seconds', type=float, default=900)
    args = parser.parse_args(argv)
    if args.command == 'init':
        result = initialize(args)
    else:
        state, session = _load(args)
        if args.command == 'inspect':
            result = _status(session)
        elif args.command == 'prepare':
            result = _prepare(args, state, session)
        elif args.command == 'execute':
            result = _execute(args, state, session)
        elif args.command == 'collect':
            result = _collect(args, state, session)
        elif args.command == 'run':
            result = _run(args, state, session)
        else:
            result = _step(args, state, session)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return (130 if result.get('phase') == 'interrupted' else 2 if result.get('phase') == 'needs_attention' else 0) if args.command == 'run' else 0


if __name__ == '__main__':
    raise SystemExit(main())
