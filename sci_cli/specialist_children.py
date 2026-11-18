"""Review profile-local child grants through the existing specialist editor."""
from dataclasses import replace

from agent.specialist_store import inventory
from sci_constants import get_sci_home


def hierarchy_depth(item, items=None):
    """Validate reachable definitions; main is depth zero, this specialist is one."""
    items = dict(inventory()[0] if items is None else items)
    items[item.name] = item
    depths = {}

    def visit(name, ancestors):
        if name in ancestors:
            raise ValueError('Child-specialist cycle: ' + ' → '.join((*ancestors, name)))
        if name in depths:
            return depths[name]
        child = items.get(name)
        if child is None or not child.enabled or child.needs_review:
            raise ValueError(f'Child specialist {name} is missing, disabled or awaiting review.')
        if child.package_info and child.package_info.get('state') != 'ready':
            raise ValueError(f'Child specialist {name} has incomplete setup.')
        depth = 1 + max((visit(n, (*ancestors, name)) for n in child.children), default=0)
        depths[name] = depth
        return depth

    return visit(item.name, ())


def select_children(ui, item):
    from sci_cli.specialist_wizard import pick
    items, _ = inventory()
    options = {name: child.purpose for name, child in items.items()
               if name != item.name and child.enabled and not child.needs_review
               and (not child.package_info or child.package_info.get('state') == 'ready')}
    selected = pick(ui, 'Approved child specialists (this profile only)', options, item.children)
    candidate = replace(item, children=tuple(selected))
    hierarchy_depth(candidate, items)
    return candidate


def review_limits(ui, item):
    if not item.children:
        return None
    required = hierarchy_depth(item)
    from tools.delegate_tool_config import _get_max_spawn_depth, _get_orchestrator_enabled
    current = _get_max_spawn_depth()
    if current >= required and _get_orchestrator_enabled():
        return None
    choice = ui.choose(
        f'This hierarchy needs depth {required} (main is 0). Enable nested delegation for this profile? '
        'Only reviewed child grants apply to saved specialists. Current conversations keep their tool snapshots.',
        ['Enable reviewed hierarchy', 'Back'])
    if choice == 'Back':
        raise ValueError('Delegation limits unchanged. Review approved children or enable the hierarchy before saving.')
    return max(current, required)


def apply_limits(depth):
    from sci_cli.config import atomic_config_write, read_user_config_raw
    path = get_sci_home() / 'config.yaml'
    cfg = read_user_config_raw(path)
    cfg.setdefault('delegation', {}).update(max_spawn_depth=depth, orchestrator_enabled=True)
    atomic_config_write(path, cfg)
