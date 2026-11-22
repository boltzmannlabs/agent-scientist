#!/usr/bin/env python3
"""MAIN assembles scoped child files without regenerating their full JSON in chat.

This checks supplied files, not native receipt authenticity or scientific validity.
It never accesses SCI state, changes child records or executes scientific tools.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from verify_handoff import artifact_path, verify


WORKERS = ('antigen-researcher-v2', 'antibody-tool-scout-v2',
           'antibody-workflow-scientist-v2', 'monoclonal-benchmark-analyst',
           'monoclonal-evidence-reviewer-v2')
METADATA_KEYS = {'child_returns', 'parent_findings', 'parent_artifacts',
                 'parent_blockers', 'next_action', 'native_run_id',
                 'parent_native_run_id'}


def scoped(root, value):
    p = Path(value)
    p = (p if p.is_absolute() else root / p).resolve()
    if not p.is_relative_to(root):
        raise ValueError('Path must remain within the authorized task root: ' + str(value))
    return p


def assemble(task_root, task_id, run_id, phase, worker, receipt_file, output):
    root = Path(task_root).resolve(strict=True)
    metadata_path = scoped(root, receipt_file)
    metadata_bytes = metadata_path.read_bytes()
    metadata = json.loads(metadata_bytes)
    if not isinstance(metadata, dict) or set(metadata) - METADATA_KEYS:
        raise ValueError('Receipt metadata must be an object with documented keys only.')
    receipts = metadata.get('child_returns')
    if not isinstance(receipts, list) or not receipts:
        raise ValueError('child_returns must contain actual observed native receipt metadata.')
    record = {'schema_version': '2.0', 'task_id': task_id, 'run_id': run_id,
              'phase': phase, 'worker': worker, 'status': 'completed',
              'scientific_execution_performed': False, 'findings': [],
              'artifacts': [], 'blockers': [], 'child_returns': receipts,
              'next_action': metadata.get('next_action') or
                             'MAIN reconciles native receipts, accounts for every finding and advances ready stages.'}
    for key in ('native_run_id', 'parent_native_run_id'):
        if key in metadata:
            record[key] = metadata[key]
    finding_ids = set()
    native_ids = set()
    artifacts = {}

    def add_finding(item):
        fid = item.get('finding_id') if isinstance(item, dict) else None
        if not isinstance(fid, str) or not fid:
            raise ValueError('Every operational finding needs its actual stable finding_id.')
        if fid in finding_ids:
            raise ValueError('Duplicate finding ID in consolidation: ' + fid)
        finding_ids.add(fid)
        record['findings'].append(item)

    def add_artifact(item):
        p = artifact_path(root, item['path'], item['sha256'])
        key = str(p)
        if key in artifacts and artifacts[key]['sha256'] != item['sha256']:
            raise ValueError('Conflicting artifact identities: ' + key)
        artifacts.setdefault(key, item)

    statuses = []
    for child in receipts:
        if not isinstance(child, dict) or not isinstance(child.get('native_run_id'), str) or not child['native_run_id'].strip():
            raise ValueError('Each child needs an actual observed native_run_id; none are generated.')
        if child['native_run_id'] in native_ids:
            raise ValueError('Duplicate native child receipt: ' + child['native_run_id'])
        native_ids.add(child['native_run_id'])
        path = artifact_path(root, child['record_path'], child['sha256'])
        child_record = json.loads(path.read_text())
        verify(child_record, root, task_id, run_id, require_operational=True)
        if child_record['worker'] != child['worker'] or child_record['status'] != child['status']:
            raise ValueError('Supplied child receipt worker/status differs from its record.')
        if child_record.get('native_run_id', child['native_run_id']) != child['native_run_id']:
            raise ValueError('Supplied child receipt native ID differs from its record.')
        for finding in child_record['findings']:
            add_finding(finding)
        for item in child_record['artifacts']:
            add_artifact(item)
        add_artifact({'path': child['record_path'], 'sha256': child['sha256']})
        record['blockers'].extend(child_record['blockers'])
        statuses.append(child_record['status'])
    for finding in metadata.get('parent_findings', []):
        add_finding(finding)
    for item in metadata.get('parent_artifacts', []):
        add_artifact(item)
    record['blockers'].extend(metadata.get('parent_blockers', []))
    add_artifact({'path': str(metadata_path),
                  'sha256': hashlib.sha256(metadata_bytes).hexdigest()})
    record['artifacts'] = list(artifacts.values())
    if 'blocked' in statuses:
        record['status'] = 'blocked'
    elif 'incomplete' in statuses:
        record['status'] = 'incomplete'
    # Full initial-team coverage is necessary for this helper's aggregate. A
    # missing child file/role is reported, never invented as a completed return.
    checked = verify(record, root, task_id, run_id, phase,
                     require_operational=True, expected_workers=WORKERS)
    target = scoped(root, output)
    encoded = (json.dumps(record, indent=2, ensure_ascii=False) + '\n').encode()
    if target.exists():
        if not target.is_file() or target.read_bytes() != encoded:
            raise ValueError('Refusing to overwrite a different existing handoff: ' + str(target))
        unchanged = True
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.handoff-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            # Same-directory link publishes complete bytes without replacing an
            # existing output, including a concurrent MAIN writer's result.
            os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        unchanged = False
    return {'written': str(target), 'sha256': hashlib.sha256(encoded).hexdigest(),
            'status': record['status'], 'finding_count': len(record['findings']),
            'child_count': len(receipts), 'workers_present': checked['workers_present'],
            'unchanged': unchanged, 'native_delivery_verified': False,
            'scientific_validity_established': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task-root', required=True, type=Path)
    p.add_argument('--task-id', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--phase', required=True,
                   choices=['research', 'preflight_review', 'result_analysis', 'result_review'])
    p.add_argument('--worker', required=True, help='Actual parent role; no native identity is inferred.')
    p.add_argument('--receipt-file', required=True, type=Path,
                   help='Scoped JSON with child_returns and optional parent_findings/artifacts/blockers.')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(assemble(a.task_root, a.task_id, a.run_id, a.phase,
                              a.worker, a.receipt_file, a.output)))


if __name__ == '__main__':
    main()
