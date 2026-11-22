#!/usr/bin/env python3
"""Verify a research/review return; performs no scientific metric calculation."""
import argparse
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / 'references/research-handoff.schema.json'


def artifact_path(root, raw, expected_hash):
    path = Path(raw)
    path = (path if path.is_absolute() else root / path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Artifact is not a regular file within this task root.')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected_hash:
        raise ValueError('Artifact bytes differ from the handoff: ' + str(path))
    return path


def verify(record, task_root, task_id, expected_run_id=None, expected_phase=None,
           require_operational=False, expected_workers=None, _ancestry=()):
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator(schema).validate(record)
    if record['task_id'] != task_id:
        raise ValueError('Handoff belongs to another task.')
    if expected_run_id is not None and record['run_id'] != expected_run_id:
        raise ValueError('Handoff belongs to another run.')
    if expected_phase is not None and record['phase'] != expected_phase:
        raise ValueError('Handoff belongs to another phase.')
    if require_operational and record['schema_version'] != '2.0':
        raise ValueError('Operational execution requires a v2 handoff, not a legacy record.')
    root = task_root.resolve(strict=True)
    for row in record['artifacts']:
        artifact_path(root, row['path'], row['sha256'])
    if record['status'] == 'blocked' and not record['blockers']:
        raise ValueError('A blocked return must identify the blocker and next owner.')
    findings = {}
    for finding in record['findings']:
        finding_id = finding.get('finding_id')
        if finding_id:
            if finding_id in findings:
                raise ValueError('Duplicate finding ID: ' + finding_id)
            findings[finding_id] = finding
    workers = {record['worker']}
    receipts = set()
    for child in record.get('child_returns', []):
        if child['native_run_id'] in receipts:
            raise ValueError('Duplicate child native receipt: ' + child['native_run_id'])
        receipts.add(child['native_run_id'])
        path = artifact_path(root, child['record_path'], child['sha256'])
        if path in _ancestry:
            raise ValueError('Cyclic child-return references are not permitted.')
        child_record = json.loads(path.read_text())
        checked = verify(child_record, root, task_id, record['run_id'],
                         require_operational=require_operational,
                         _ancestry=(*_ancestry, path))
        if child_record['worker'] != child['worker'] or child_record['status'] != child['status']:
            raise ValueError('Child receipt does not match its worker/status record.')
        if (record['schema_version'] == '2.0' and record['status'] == 'completed'
                and child_record['status'] != 'completed'):
            raise ValueError('A completed parent cannot conceal an incomplete or blocked child return.')
        if child_record.get('native_run_id', child['native_run_id']) != child['native_run_id']:
            raise ValueError('Child native run identity differs from its receipt.')
        workers.update(checked['workers_present'])
        if record['schema_version'] == '2.0':
            for item in child_record['findings']:
                finding_id = item.get('finding_id')
                if finding_id not in findings:
                    raise ValueError('Consolidation omitted child finding: ' + str(finding_id))
                if findings[finding_id] != item:
                    raise ValueError('Consolidation changed child finding: ' + str(finding_id))
    missing = sorted(set(expected_workers or ()) - workers)
    if missing:
        raise ValueError('Missing requested worker returns: ' + ', '.join(missing))
    return {'verified': True, 'task_id': task_id, 'artifact_count': len(record['artifacts']),
            'schema_version': record['schema_version'], 'workers_present': sorted(workers),
            'finding_count': len(findings), 'native_delivery_verified': False,
            'scientific_validity_established': False, 'native_frozen_artifacts_verification': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('record', type=Path)
    p.add_argument('--task-root', type=Path, required=True)
    p.add_argument('--task-id', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--phase', required=True)
    p.add_argument('--operational', action='store_true', help='Require v2 records and stable finding identities.')
    p.add_argument('--expected-workers', nargs='+', help='Exact role names required in this return tree.')
    a = p.parse_args()
    print(json.dumps(verify(json.loads(a.record.read_text()), a.task_root, a.task_id,
                            a.run_id, a.phase, a.operational, a.expected_workers)))


if __name__ == '__main__':
    main()
