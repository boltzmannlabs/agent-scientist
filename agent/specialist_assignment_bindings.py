"""Resolve future file arguments from adapter-validated input evidence."""
import hashlib
import json
from pathlib import Path

from agent.specialist_assignment import current_assignment, record_effect


def value_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _effects():
    from agent.specialist_assignment import evidence
    from agent.specialist_policy import current_policy
    from types import SimpleNamespace
    return evidence(SimpleNamespace(_specialist_policy=current_policy())).get('recorded_effects', [])


def _input_hashes(contract, effects):
    derived = {}
    if any(row.get('terminal_confirmed') is True for row in effects):
        derived = {row['path']: row['sha256'] for row in effects if row.get('kind') == 'artifact'}
    return {**derived, **contract['inputs']}


def record_input_binding(tool, path, value, *, sha256, selectors):
    """Called by the uploading adapter only after validation and receipt persistence.

    Store a digest rather than a potentially credential-bearing remote reference.
    The binding grants no new inputs, parameters, tools or submission allowance.
    """
    assignment = current_assignment()
    if assignment is None:
        return
    pinned = _input_hashes(json.loads(assignment.contract), _effects())
    if sha256 not in pinned.values():
        return
    facts = dict(kind='input_binding', tool=tool, argument_path=list(path),
                 value_sha256=value_digest(value), input_sha256=sha256, selectors=selectors)
    record_effect('binding:' + value_digest(facts), **facts)


def needs_input_binding(tool, path, *, sha256, selectors):
    """Older assignments may have an upload receipt but no binding journal entry."""
    assignment = current_assignment()
    if assignment is None:
        return False
    contract = json.loads(assignment.contract)
    rules = contract['tool_arguments'].get(tool, [])
    rules = [rules] if isinstance(rules, dict) else rules
    pending = False
    for rule in rules:
        if not all(rule.get(key) == value for key, value in selectors.items()):
            continue
        marker = rule
        for key in path:
            marker = marker.get(key) if isinstance(marker, dict) else None
        if (isinstance(marker, dict) and set(marker) == {'$input'}
                or isinstance(marker, str) and marker.startswith('<') and marker.endswith('>')):
            pending = True
    if not pending:
        return False
    rows = _effects()
    return not any(row.get('kind') == 'input_binding' and row.get('tool') == tool
                   and row.get('argument_path') == list(path) and row.get('input_sha256') == sha256
                   and row.get('selectors') == selectors for row in rows)


def bound_argument(expected, actual, *, tool, path, arguments, contract, effects):
    inputs = _input_hashes(contract, effects)
    hashes = set(inputs.values())
    if isinstance(expected, dict):
        source = expected.get('$input')
        if not isinstance(source, str):
            return False
        pinned = inputs.get(str(Path(source).expanduser().resolve()))
        hashes = {pinned} if pinned else set()
    elif not (isinstance(expected, str) and expected.startswith('<') and expected.endswith('>')):
        return False
    return any(row.get('kind') == 'input_binding' and row.get('tool') == tool
               and row.get('argument_path') == list(path)
               and row.get('value_sha256') == value_digest(actual)
               and row.get('input_sha256') in hashes
               and all(arguments.get(key) == value for key, value in row.get('selectors', {}).items())
               for row in effects)
