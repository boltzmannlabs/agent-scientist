"""Portable package relationships and their installed, profile-local bindings."""
from packaging.specifiers import SpecifierSet
from packaging.version import Version

# Dependency identifiers cannot contain '@'; this cannot collide with a service ID.
CHILDREN = '@children'


def child_requirements(manifest):
    from sci_cli.subagent_package_schema import identifier, obj
    children = manifest.get('children', [])
    if manifest.get('schema_version') == 1 and not children:
        return []
    if not isinstance(children, list):
        raise ValueError('children must be a list of role/package/version objects.')
    roles = set()
    for child in children:
        obj(child, {'role', 'package', 'version'}, {'role', 'package', 'version'})
        identifier(child['role']); identifier(child['package'])
        if child['role'] in roles:
            raise ValueError('Duplicate child role: ' + child['role'])
        roles.add(child['role'])
        if not isinstance(child['version'], str) or not child['version'].strip():
            raise ValueError('Child packages require a nonempty compatible version specifier.')
        SpecifierSet(child['version'])
    return children


def resolve_graph(rows, roots=None):
    """One reviewed catalog version per ID; dependencies first, no downloads or code execution."""
    order, done, active = [], set(), []

    def visit(key):
        if key in active:
            raise ValueError('Child package cycle: ' + ' -> '.join([*active, key]))
        if key in done:
            return
        if key not in rows:
            raise ValueError('Missing child package: ' + key)
        manifest = rows[key]['manifest']
        if manifest['id'] != key:
            raise ValueError('Child package identity differs from its catalog key: ' + key)
        active.append(key)
        for child in child_requirements(manifest):
            target = rows.get(child['package'])
            if target is None:
                raise ValueError(f"{key}/{child['role']}: missing child package {child['package']}")
            version = target['manifest']['version']
            if not SpecifierSet(child['version']).contains(Version(version), prereleases=None):
                raise ValueError(f"{key}/{child['role']}: {child['package']} {version} is incompatible with {child['version']}")
            visit(child['package'])
        active.pop()
        done.add(key)
        order.append(key)

    for key in sorted(rows) if roots is None else roots:
        visit(key)
    return order


def bindings(manifest, children):
    return {child['role']: {'name': children[child['role']].name, 'package': child['package'],
            'version': children[child['role']].package_info['version'],
            'digest': children[child['role']].package_info['digest'], 'requires': child['version']}
            for child in child_requirements(manifest)}


def installed_problem(item, *, owner=None, rows=None):
    """Check reviewed links locally. No credential probes or mutation of live snapshots."""
    from agent.specialist_store import load
    seen = set()

    def visit(parent, ancestors):
        if parent.name in ancestors:
            raise ValueError('Installed child-specialist cycle: ' + ' -> '.join([*ancestors, parent.name]))
        if parent.name in seen:
            return
        info = parent.package_info
        if rows is not None:
            expected = rows.get(info.get('id'))
            if (expected is None or info.get('version') != expected['manifest']['version'] or
                    info.get('digest') != expected['digest']):
                raise ValueError('Reviewed catalog version/content changed for ' + parent.name)
        resolved = info.get('resolved', {})
        linked = resolved.get(CHILDREN, {}) if isinstance(resolved, dict) else None
        if not isinstance(linked, dict):
            raise ValueError('Invalid installed child bindings for ' + parent.name)
        if rows is not None:
            expected_roles = {c['role'] for c in child_requirements(rows[info['id']]['manifest'])}
            if set(linked) != expected_roles:
                raise ValueError('Declared child roles changed for ' + parent.name)
        if linked and set(parent.children) != {c.get('name') for c in linked.values() if isinstance(c, dict)}:
            raise ValueError('Approved child grants differ from the installed package bindings for ' + parent.name)
        for role, child in linked.items():
            if not isinstance(child, dict) or set(child) != {'name', 'package', 'version', 'digest', 'requires'}:
                raise ValueError('Invalid child binding: ' + role)
            member = load(child['name'], owner)
            member_info = member.package_info
            if not member.enabled or member.needs_review or member_info.get('state') != 'ready':
                raise ValueError(f"Child {parent.name}/{role} ({member.name}) is disabled or needs setup/review")
            if (any(member_info.get(field) != child[field] for field in ('version', 'digest')) or
                    member_info.get('id') != child['package'] or
                    not SpecifierSet(child['requires']).contains(Version(member_info['version']), prereleases=None)):
                raise ValueError(f"Child {parent.name}/{role} changed package/version/content; review the hierarchy update")
            visit(member, (*ancestors, parent.name))
        seen.add(parent.name)

    try:
        visit(item, ())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return 'Package hierarchy needs setup: ' + str(exc)
    return None
