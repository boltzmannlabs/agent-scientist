"""Versioned approval fingerprints: diagnostic field names, never saved secret values."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

# Explicitly cosmetic/picker-cache fields only. Unknown settings stay protected;
# in particular display.personality, provider routes, permissions and mounts do.
_UNREVIEWED_FIELDS = {
    '_config_version': None,
    'display': frozenset({
        'skin', 'compact', 'show_reasoning', 'reasoning_full', 'timestamps',
        'timestamp_format', 'show_cost', 'battery', 'language', 'tool_progress',
        'bell_on_complete', 'bell_on_prompt', 'persistent_output',
        'persistent_output_max_lines', 'final_response_markdown',
    }),
    'model_catalog': frozenset({'ttl_minutes', 'ttl_hours'}),
}


def configuration_fields(config):
    filtered = deepcopy(config)
    for root, ignored in _UNREVIEWED_FIELDS.items():
        if ignored is None:
            filtered.pop(root, None)
        elif isinstance(filtered.get(root), dict):
            for key in ignored:
                filtered[root].pop(key, None)
            if not filtered[root]:
                filtered.pop(root)
    fields = {}

    def visit(value, path):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                visit(child, (*path, str(key)))
        else:
            # JSON pointers avoid collisions with dotted/custom provider names.
            pointer = '/' + '/'.join(k.replace('~', '~0').replace('/', '~1') for k in path)
            fields[pointer] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    for key, value in filtered.items():
        visit(value, (str(key),))
    return fields


def approval_record(config):
    return {'version': 1, 'fields': configuration_fields(config)}


def changed_fields(spec, config):
    """None means the old single digest cannot tell us which settings changed."""
    if not spec.config_review:
        from sci_cli.science_profiles import config_digest
        return [] if spec.config_digest and spec.config_digest == config_digest(config) else None
    record = spec.config_review
    if record.get('version') != 1 or not isinstance(record.get('fields'), dict):
        raise ValueError('Unsupported profile approval format. Update SCI before reviewing this profile.')
    before, after = record['fields'], configuration_fields(config)
    return ['.'.join(k.replace('~1', '/').replace('~0', '~') for k in p[1:].split('/'))
            for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]


def require_approval(home, spec, config):
    changes = changed_fields(spec, config)
    if changes is None or changes:
        detail = ('The older approval record cannot identify the changed fields.' if changes is None
                  else 'Changed fields: ' + ', '.join(changes) + '.')
        raise ValueError('Reviewed model/sandbox settings changed. ' + detail +
                         f' Run /Update_profile "{home.name}" to review and repair in place. '
                         'History and isolation are preserved; no recreation is required.')


def runtime_policy_id(spec, config):
    """Receipt upgrades alone must not invalidate a live cached conversation."""
    policy = asdict(spec)
    policy.pop('config_digest', None)
    policy.pop('config_review', None)
    data = {'policy': policy, 'configuration': configuration_fields(config)}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
