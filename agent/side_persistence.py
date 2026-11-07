"""Native saved branches for explicitly opened side conversations."""

from copy import deepcopy
import json
from pathlib import Path


class SidePersistenceError(RuntimeError):
    """The side conversation cannot safely claim to be saved."""


def capture_context(parent, history, db):
    # CLI history is replaced only at turn end. SQLite also contains the current
    # accepted request and tool activity committed before this snapshot.
    if db is not None:
        saved = db.get_messages_as_conversation(parent.session_id, repair_alternation=False)
        if saved:
            history = saved
    return deepcopy([m for m in (history or []) if m.get('role') != 'session_meta'])


def pending_context(messages):
    if not messages:
        return ''
    # Unfinished tool calls are evidence, not callable messages in the fork.
    visible = [{key: value for key, value in msg.items()
                if key in {'role', 'content', 'api_content', 'tool_calls', 'tool_call_id', 'name'}}
               for msg in messages]
    return ('\n\nMain activity captured at the fork boundary (incomplete; do not execute or '
            'assume pending calls succeeded):\n' + json.dumps(visible, ensure_ascii=False))


def attach_saved_branch(side, fork, question):
    """Save the immutable seed before any side model/tool request can start."""
    db = side.db
    if db is None:
        return
    from agent.session_persistence import _db_flush_row
    from agent.message_metadata import DB_ROW_SNAPSHOT
    from sci_cli.active_sessions import try_acquire_active_session
    from sci_cli.config import load_config

    side.lease, refusal = try_acquire_active_session(
        session_id=side.id, surface='side', config=load_config(), registry_home=Path(db.db_path).parent)
    if refusal:
        raise SidePersistenceError(str(refusal))

    parent_id = side.parent_id
    config = deepcopy(fork._session_init_model_config)
    config.update(provider=fork.provider, api_mode=fork.api_mode,
                  _branched_from=parent_id, _side_from=parent_id)
    # Copy only the existing durable runtime fields; never persist an API key.
    from sci_state import SessionDB
    runtime = SessionDB.session_gateway_runtime(db.get_session(parent_id) or {})
    route = {key: runtime.get(key) or getattr(fork, key, None)
             for key in ('provider', 'base_url', 'api_mode')}
    config.update(route)
    config['gateway_runtime'] = route
    rows = [_db_flush_row(fork, msg, False) for msg in side.history]
    for row in rows:
        # Rows belong to the new branch, never address the parent's row IDs.
        row.pop('_row_id', None)
        row.pop(DB_ROW_SNAPSHOT, None)
    try:
        db.create_session(side.id, 'cli', model=fork.model, model_config=config,
                          parent_session_id=parent_id if db.get_session(parent_id) else None,
                          system_prompt=side.prompt)
        db.append_messages_batch(side.id, rows)
        title = 'Side: ' + (' '.join(question.split())[:70] if isinstance(question, str) else 'conversation')
        db.set_session_title(side.id, db.get_next_title_in_lineage(title))
        side.history = db.get_messages_as_conversation(side.id, repair_alternation=False)
    except Exception as exc:
        # The partial branch stays recoverable; do not send an unsaved request.
        side.save_error = SidePersistenceError(f'Could not save side conversation {side.id}. No side request '
                                              'was sent. Check SCI storage, then close and reopen side to retry.')
        raise side.save_error from exc
    fork._session_db = db
    fork._owns_session_db = False
    fork._session_db_created = True
    fork._session_init_model_config = config
    fork._parent_session_id = parent_id
    fork._persist_disabled = False
    fork.compression_in_place = True
    side.saved = True


def flush_branch(side, result):
    if not side.saved:
        return
    messages = (result or {}).get('messages')
    if messages is not None and side._agent._flush_messages_to_session_db(messages) is False:
        side.save_error = SidePersistenceError(f'Side response received, but saving {side.id} failed. '
                                              'Keep this window open and check SCI storage; do not repeat external actions.')
        raise side.save_error
