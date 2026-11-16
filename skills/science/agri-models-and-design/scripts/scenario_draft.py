"""Metadata-only scenario drafts; never invokes a simulator or edits saved results."""
from copy import deepcopy
from contextlib import contextmanager
import argparse
import errno
import json
import os
from pathlib import Path
import re
import tempfile
import sys
import time

ACTIONS = ['Add scenario', 'Delete scenario', 'Edit scenario', 'Run scenarios']


def validate_scenarios(items):
    if not isinstance(items, list):
        raise ValueError('scenarios must be a list')
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Each scenario must be an object')
        sid = item.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'S[1-9][0-9]*', sid) or sid in seen:
            raise ValueError('Scenario IDs must be unique S1, S2, ... labels')
        seen.add(sid)
        for key in ('name', 'model'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError('Every scenario needs ' + key)
        if not isinstance(item.get('recipe_ids'), list) or not item['recipe_ids'] or any(not isinstance(r, str) or not r for r in item['recipe_ids']):
            raise ValueError('Every scenario needs saved recipe_ids')
    return items


def create(payload):
    if not isinstance(payload.get('project_id'), str) or not payload['project_id']:
        raise ValueError('project_id is required')
    if payload.get('mode') not in ('design', 'ai_physics'):
        raise ValueError('mode must be design or ai_physics')
    rows = deepcopy(validate_scenarios(payload.get('scenarios', [])))
    for row in rows:
        row['status'] = 'review_required'
    return {'schema_version': 1, 'revision': 1, 'project_id': payload['project_id'],
            'mode': payload['mode'], 'scenarios': rows, 'last_deleted': [], 'last_deleted_positions': [],
            'next_scenario_number': max([int(r['id'][1:]) for r in rows] + [0]) + 1}


def apply(state, action, payload):
    if type(payload.get('expected_revision')) is not int or payload['expected_revision'] != state['revision']:
        raise ValueError('Draft changed; list it again before editing')
    updated = deepcopy(state)
    validate_scenarios(updated['scenarios'])
    if action == 'delete':
        ids = payload.get('scenario_ids')
        available = {r['id'] for r in updated['scenarios']}
        if ids == 'all':
            if payload.get('confirm_all') is not True:
                raise ValueError('Delete All requires a separate explicit confirmation; draft unchanged')
            ids = list(available)
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise ValueError('Choose scenario IDs to delete')
        if set(ids) - available:
            raise ValueError('Selected scenario is not in this draft')
        if len(available) > 1 and set(ids) == available and payload.get('confirm_all') is not True:
            raise ValueError('Deleting every scenario requires a separate explicit confirmation; draft unchanged')
        updated['last_deleted'] = [r for r in updated['scenarios'] if r['id'] in ids]
        updated['last_deleted_positions'] = [i for i, r in enumerate(updated['scenarios']) if r['id'] in ids]
        updated['scenarios'] = [r for r in updated['scenarios'] if r['id'] not in ids]
    elif action == 'undo':
        if not updated.get('last_deleted'):
            raise ValueError('There is no deletion to undo')
        positions = updated.get('last_deleted_positions', [])
        if len(positions) == len(updated['last_deleted']):
            for position, row in zip(positions, updated['last_deleted']):
                updated['scenarios'].insert(position, row)
        else:
            # Older drafts did not retain positions; stable numeric IDs recover
            # their display order without discarding any intervening edits.
            updated['scenarios'].extend(updated['last_deleted'])
            updated['scenarios'].sort(key=lambda r: int(r['id'][1:]))
        validate_scenarios(updated['scenarios'])
        updated['last_deleted'] = []
        updated['last_deleted_positions'] = []
    elif action == 'upsert':
        row = deepcopy(payload.get('scenario'))
        if not isinstance(row, dict):
            raise ValueError('scenario must be an object')
        if 'id' not in row:
            row['id'] = 'S' + str(updated['next_scenario_number'])
            updated['next_scenario_number'] += 1
        if not isinstance(row['id'], str) or not re.fullmatch(r'S[1-9][0-9]*', row['id']):
            raise ValueError('Scenario ID must be an S-number')
        ids = {r['id'] for r in updated['scenarios']}
        if row['id'] not in ids and int(row['id'][1:]) < state['next_scenario_number']:
            raise ValueError('Do not reuse a deleted scenario ID')
        if row['id'] in ids:
            updated['scenarios'] = [row if r['id'] == row['id'] else r for r in updated['scenarios']]
        else:
            updated['scenarios'].append(row)
        validate_scenarios(updated['scenarios'])
        updated['next_scenario_number'] = max(updated['next_scenario_number'], int(row['id'][1:]) + 1)
    else:
        raise ValueError('Unknown draft action')
    updated['revision'] += 1
    return updated


def view(state):
    rows = state['scenarios']
    selector = None
    if rows:
        if len(rows) <= 2:
            choices = [*[r['id'] + ' — ' + r['name'] for r in rows], 'All scenarios', 'Previous']
        elif len(rows) == 3:
            choices = [*[r['id'] + ' — ' + r['name'] for r in rows], 'More options']
        else:
            choices = ['Choose a scenario', 'Choose multiple scenarios', 'All scenarios', 'Previous']
        selector = {'question': 'Which scenario(s) should be deleted?',
                    'choices': choices, 'multi_select': False}
    return {'revision': state['revision'], 'project_id': state['project_id'],
            'mode': state['mode'], 'scenarios': state['scenarios'],
            'delete_selector': selector,
            'delete_more_selector': {
                'question': 'How would you like to select scenarios?',
                'choices': ['Choose multiple scenarios', 'All scenarios', 'Previous'], 'multi_select': False},
            'delete_id_selector': {
                'question': 'Enter the scenario ID(s) to delete, such as S1 or S1, S3. Type Previous to go back.',
                'multi_select': False},
            'bulk_delete_confirmation': {
                'question': f'Delete all {len(rows)} draft scenarios? Saved scientific results will remain.',
                'choices': ['Keep scenarios', f'Delete all {len(rows)} scenarios'], 'multi_select': False},
            'actions': ACTIONS, 'can_run': bool(state['scenarios']) and all(r.get('status') == 'ready' for r in state['scenarios'])}


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.scenario-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def draft_lock(path, timeout=10):
    """Serialize read/check/write across sessions; OS releases on process exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the lock inode: unlinking it would allow two independent locks.
    with path.with_name('.' + path.name + '.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'\0')
            stream.flush()
        if os.name == 'nt':
            import msvcrt
            def acquire():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise OSError('Draft is busy; try listing it again') from exc
                time.sleep(.02)
        try:
            yield
        finally:
            release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'list', 'delete', 'undo', 'upsert'])
    parser.add_argument('--draft', type=Path, required=True)
    parser.add_argument('--request-file', type=Path,
                        help='Read mutation payload as UTF-8 JSON data from this file')
    args = parser.parse_args()
    try:
        if args.action == 'list':
            payload = {}
        elif args.request_file is not None:
            payload = json.loads(args.request_file.read_text(encoding='utf-8'))
        else:
            payload = json.load(sys.stdin)  # Compatibility with older clients.
        if not isinstance(payload, dict):
            raise ValueError('Command payload must be a JSON object')
        if args.action == 'list':
            state = json.loads(args.draft.read_text())
        else:
            with draft_lock(args.draft):
                if args.action == 'create':
                    if args.draft.exists():
                        raise ValueError('Draft already exists; list it or choose a new draft name')
                    state = create(payload)
                else:
                    state = apply(json.loads(args.draft.read_text()), args.action, payload)
                save(args.draft, state)
        print(json.dumps({'status': 'ok', **view(state)}, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
