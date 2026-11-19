"""Prepare package graphs with the existing installer; publish parents after their children."""
from contextlib import ExitStack
from pathlib import Path

from agent.specialist_store import inventory, load, save, validate_name
from sci_cli.subagent_package_graph import CHILDREN, bindings, child_requirements, installed_problem, resolve_graph
from sci_cli.subagent_package_schema import validate


def _sources(root, source):
    """Resolve only declared sibling packages or the current reviewed catalog."""
    from sci_cli.subagent_package_catalog import catalog
    root = Path(root)
    manifest, files, digest = validate(root)
    rows = {manifest['id']: {'manifest': manifest, 'digest': digest, 'path': str(root), 'files': files}}
    pending, release = [manifest['id']], None
    while pending:
        key = pending.pop()
        for child in child_requirements(rows[key]['manifest']):
            package_id = child['package']
            if package_id in rows:
                continue
            sibling = root.parent / package_id
            if not source.startswith('catalog:') and (sibling / 'manifest.yaml').exists():
                value, _, digest = validate(sibling)
                rows[package_id] = {'manifest': value, 'digest': digest, 'path': str(sibling)}
            else:
                release = catalog() if release is None else release
                if package_id not in release:
                    raise ValueError(f"{key}/{child['role']}: missing child package {package_id}; provide its sibling folder or release catalog entry")
                rows[package_id] = release[package_id]
            pending.append(package_id)
    return manifest['id'], rows


def _unused_name(base, occupied):
    base = base[:64]
    name, number = base, 2
    while name in occupied:
        suffix = '-' + str(number)
        name = base[:64 - len(suffix)] + suffix
        number += 1
    return name


def _candidate(items, row, children, owner):
    from agent.specialist_extensions import extension_home, fingerprint
    from sci_cli.subagent_package_install import definition_digest
    expected = bindings(row['manifest'], children)
    for item in items.values():
        info = item.package_info
        if (info.get('id') != row['manifest']['id'] or info.get('version') != row['manifest']['version'] or
                info.get('digest') != row['digest'] or info.get('definition_digest') != definition_digest(item)):
            continue
        if info.get('resolved', {}).get(CHILDREN, {}) != expected:
            continue
        home = extension_home(item, owner=owner)
        if home is None or fingerprint(home) != item.extension_revision:
            continue
        if item.enabled and not item.needs_review and info.get('state') == 'ready':
            return item, False
        if info.get('state') == 'setup_required':
            return item, True
    return None, False


def _unchanged_parent(item, row, owner):
    from agent.specialist_extensions import extension_home
    from sci_cli.subagent_package_io import execution_digest
    info = item.package_info
    if info.get('id') != row['manifest']['id'] or info.get('version') != row['manifest']['version']:
        return False
    if info.get('digest') == row['digest']:
        return True
    private = extension_home(item, owner=owner)
    if private is None:
        return False
    _, files, _ = validate(private / 'package', require_lock=True)
    return execution_digest(files) == execution_digest(row['files'])


def install_hierarchy(root, owner, cli, ui, *, name, source):
    from sci_cli.subagent_package_catalog import package
    from sci_cli.subagent_package_install import _existing, _install_locked, check_compatibility
    from sci_cli.specialist_children import apply_limits, review_limits
    package_id, rows = _sources(root, source)
    order = resolve_graph(rows, [package_id])
    for row in rows.values():
        check_compatibility(row['manifest'])
    items = inventory()[0]
    name = name or rows[package_id]['manifest']['name']
    validate_name(name)
    current = items.get(name)
    changed = bool(current and _unchanged_parent(current, rows[package_id], owner) and
                   installed_problem(current, owner=owner, rows=rows))
    selection = _existing(ui, items, name, rows[package_id]['manifest'], rows[package_id]['digest'],
                          hierarchy_changed=changed)
    name, previous, _ = selection
    ui.show('Package hierarchy (children first):\n' + '\n'.join(
        f"  {key} {rows[key]['manifest']['version']} — {rows[key]['digest']}" + ''.join(
            f"\n    {c['role']} -> {c['package']} ({c['version']})" for c in child_requirements(rows[key]['manifest'])) for key in order) +
        '\nEach package retains its own capability scope. Existing definitions stay unchanged during preparation; '
        'cancellation may leave reviewed downloads/private setup, but does not publish a partial hierarchy.')
    selected, staged, occupied = {}, [], set(items) | {name}
    # Keep all extracted catalog resources alive until preparation and publication finish.
    with ExitStack() as stack:
        paths = {key: stack.enter_context(package(key, rows=rows)) for key in order}
        for key in order:
            row = rows[key]
            child_bindings = {c['role']: selected[c['package']] for c in child_requirements(row['manifest'])}
            if key == package_id:
                choice = selection
            else:
                candidate, resume = _candidate(items, row, child_bindings, owner)
                if candidate and not resume:
                    selected[key] = candidate
                    ui.show(f'Reusing reviewed child: {key} -> {candidate.name}')
                    continue
                local = candidate.name if candidate else _unused_name(name + '-' + row['manifest']['name'], occupied)
                choice = (local, candidate, resume)
            child_source = 'catalog:' + key if 'path' not in row or source.startswith('catalog:') else str(Path(row['path']).absolute())
            item = _install_locked(paths[key], owner, cli, ui, name=choice[0], source=source if key == package_id else child_source,
                                   selection=choice, child_bindings=child_bindings, publish=False, expected_digest=row['digest'])
            selected[key] = item
            occupied.add(item.name)
            staged.append((item, choice[1]))
        lead = selected[package_id]
        if previous and previous.enabled and previous.package_info.get('state') == 'ready' and not lead.enabled:
            raise ValueError('New hierarchy setup is incomplete. The existing working hierarchy was preserved; '
                             'prepared private destinations are retained for inspection and retry.')
        prepared = {**items, **{item.name: item for item, _ in staged}}
        depth = review_limits(ui, lead, items=prepared) if lead.enabled else None
        staged_names = {item.name for item, _ in staged}
        for item in selected.values():
            if item.name not in staged_names and load(item.name, owner).revision != item.revision:
                raise ValueError('Child specialist changed during hierarchy review: ' + item.name + '; existing hierarchy preserved.')
        if depth is not None:
            apply_limits(depth)
        published = {}
        for item, original in staged:
            published[item.name] = save(item, expected_revision=original.revision if original else None)
        lead = published[lead.name]
        ui.show(f'Installed hierarchy {lead.name}: ' + ('ready; use /new.' if lead.enabled else
                'disabled; finish the reported child/setup requirements and retry installation.') +
                '\nChildren: ' + ', '.join(lead.children))
        return lead
