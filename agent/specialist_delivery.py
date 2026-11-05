"""Deliver saved-specialist reports without a second model rewriting them."""
import json
import logging
import re


class VerbatimReport(str):
    """Already-final specialist output; skip parent output rewriters."""


def reports_from_results(results):
    if not results or any(not isinstance(row, dict) or not row.get('specialist') for row in results):
        return None  # Ordinary/mixed delegation keeps its existing synthesis contract.
    from sci_constants import get_sci_home
    reports = []
    for row in results:
        run_id = str(row.get('run_id', ''))
        full = row
        if re.fullmatch(r'sa-[a-zA-Z0-9_-]+', run_id):
            path = get_sci_home() / 'subagent-runs' / f'{run_id}.json'
            if path.is_file() and not path.is_symlink():
                try:
                    saved = json.loads(path.read_text(encoding='utf-8-sig'))
                    if saved.get('specialist') == row['specialist']:
                        full = saved.get('result') or row
                except (ValueError, OSError) as exc:
                    logging.getLogger(__name__).warning('Could not recover full specialist report %s: %s', run_id, exc)
        text = full.get('summary')
        if full.get('status') != 'completed' or full.get('truncated') or full.get('summary_truncated'):
            text = (f"Specialist {row['specialist']}: {full.get('status', 'unknown')}. "
                    f"{full.get('error') or 'Full completed output is unavailable; this result may be incomplete.'}" +
                    (f'\n\nPartial output:\n{text}' if text else ''))
        elif not isinstance(text, str) or not text:
            return None
        if len(results) > 1:
            text = f"Specialist: {row['specialist']}\n\n{text}"
        reports.append(text)
    return '\n\n'.join(reports)


def report_from_event(event):
    if event.get('type') != 'async_delegation' or event.get('task_failure_notice'):
        return None
    return reports_from_results(event.get('results') or [])


def stage_sync(parent, results):
    # A pod lead must still finish its own assignment after receiving child results.
    if parent is None or getattr(parent, '_specialist_policy', None) is not None:
        return
    report = reports_from_results(results)
    if report:
        parent._specialist_pending_delivery = (getattr(parent, '_current_turn_id', None), report)


def stage_delivery(agent, state):
    """Use the normal turn finalizer/persistence; do not make a parent model request."""
    if agent._interrupt_requested:
        return False
    report = None
    pending = getattr(agent, '_specialist_pending_delivery', None)
    if pending is not None:
        agent._specialist_pending_delivery = None
        if pending[0] == state.turn_id:
            report = pending[1]
    if report is None and state.api_call_count == 0:
        # Compaction can replace the history and invalidate its absolute index. The current
        # request is the final user row in the loop's live message list.
        row = next((message for message in reversed(state.messages)
                    if isinstance(message, dict) and message.get('role') == 'user'), {})
        if row.get('display_kind') == 'async_delegation_complete':
            report = (row.get('display_metadata') or {}).get('specialist_report')
    if not isinstance(report, str) or not report:
        return False
    state.final_response = VerbatimReport(report)
    state._turn_exit_reason = 'completed'
    return True
