"""Connect scientific effects to the existing specialist run evidence."""
from agent.specialist_assignment import check_arguments, current_assignment, record_effect
import json
import hashlib
from agent.specialist_assignment import evidence
from agent.specialist_policy import current_policy
from types import SimpleNamespace
import time
from .receipt_store import ReceiptStorageError


def check(tool, arguments):
    assignment = current_assignment()
    if assignment is not None:
        contract = json.loads(assignment.contract)
        if tool in {'boltzmann_submit', 'boltzmann_upload'}:
            job = arguments.get('job_name')
            rules = contract['tool_arguments'].get('boltzmann_submit', [])
            rules = [rules] if isinstance(rules, dict) else rules
            covered = any(rule.get('job_name') == job and isinstance(rule.get('experiment_data'), dict)
                          and rule['experiment_data'] for rule in rules)
            if job not in contract['max_submissions'] or not covered:
                return {'error': 'The parent must freeze this job\'s required experiment_data and max_submissions '
                        'in delegate_task.assignment before scientific execution. Return the prepared specification '
                        'to the parent; no upload or job started.', 'status': 'not_started', 'submitted': False,
                        **({'uploaded': False} if tool == 'boltzmann_upload' else {})}
        if tool == 'boltzmann_upload' and not contract['inputs'] and not any(row.get('kind') == 'artifact' for row in effects()):
            return {'error': 'Prepare the exact input file, then have the parent pin it in delegate_task.assignment.inputs '
                    'before uploading. No upload started.', 'status': 'not_started', 'uploaded': False}
    mismatch = check_arguments(tool, arguments)
    if mismatch:
        return {'error': mismatch, 'status': 'not_started', 'submitted': False, 'safe_to_retry': False}
    return None


def stopped():
    from tools.interrupt import is_interrupted
    policy = current_policy()
    return is_interrupted() or (policy is not None and time.monotonic() >= policy.deadline)


def save(attempt, *, required=False, **facts):
    if not attempt or current_assignment() is None:
        return None
    try:
        record_effect(attempt, attempt_id=attempt, **facts)
    except (OSError, ValueError, RuntimeError) as exc:
        message = ('Assignment evidence could not be saved (' + type(exc).__name__ + '). '
                   'Reconcile the reserved receipt and any returned job ID; do not resubmit.')
        if required:
            raise ReceiptStorageError(message) from exc
        return message
    return None


def effects():
    row = evidence(SimpleNamespace(_specialist_policy=current_policy()))
    if row.get('evidence_error'):
        raise ReceiptStorageError('Assignment evidence is unreadable. Preserve existing jobs and reconcile it before continuing.')
    return row.get('recorded_effects', [])


def tracked_job(job, doc):
    assignment = current_assignment()
    if assignment is None or not json.loads(assignment.contract)['max_submissions']:
        return True  # Informational reconciliation may inspect previously submitted jobs.
    return any(row.get('job_name') == job and row.get('doc_id') == doc for row in effects())


def artifact_key(url):
    return hashlib.sha256(url.encode()).hexdigest()


def observe_outputs(job, doc, result):
    if current_assignment() is None or not isinstance(result, dict):
        return None
    references = set()

    def visit(value):
        if isinstance(value, str) and value.startswith(('https://', 'http://')):
            references.add(artifact_key(value))
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    for row in effects():
        if row.get('job_name') == job and row.get('doc_id') == doc:
            return save(row['attempt_id'], artifact_refs=sorted(references))
    return None


def download_origin(url):
    assignment = current_assignment()
    if assignment is None or not json.loads(assignment.contract)['max_submissions']:
        return {}
    for row in effects():
        if artifact_key(url) in row.get('artifact_refs', []):
            return {'job_name': row['job_name'], 'doc_id': row['doc_id']}
    raise ReceiptStorageError('Download is not an output of a job recorded for this assignment. '
                              'Poll the accepted job and use its exact returned artifact reference; no download started.')
