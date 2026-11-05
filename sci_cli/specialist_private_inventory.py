"""Reconcile retained private additions without downloads, imports, probes or execution."""
from dataclasses import replace

from agent.specialist_extensions import extension_home, fingerprint
from agent.specialist_sources import DEFAULT_TOOLS


def reconcile(item, *, plugin_tools=None, plugin_skills=None, warnings=None):
    home = extension_home(item)
    if home is None:
        return item
    from sci_cli.config import read_user_config_raw
    from sci_cli.skill_add_sources import _parse_frontmatter
    from agent.skill_utils import iter_skill_index_files
    from tools.mcp_tool_schema import mcp_prefixed_tool_name
    warnings = warnings if warnings is not None else []
    skills = set()
    for path in iter_skill_index_files(home / 'skills', 'SKILL.md'):
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(home.resolve() / 'skills'):
                raise ValueError('Skill source escapes its private directory.')
            if path.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('Skill instructions exceed 8 MiB.')
            name = _parse_frontmatter(path.read_text(encoding='utf-8-sig')).get('name')
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Skill has no valid name.')
            skills.add(name)
        except (OSError, ValueError, UnicodeError) as exc:
            warnings.append(f'Private skill not added: {path}: {exc}')
    config = read_user_config_raw(home / 'config.yaml')
    tools = {mcp_prefixed_tool_name(server, name)
             for server, cfg in config.get('mcp_servers', {}).items()
             if isinstance(cfg, dict) and cfg.get('enabled', True)
             for name in cfg.get('tools', {}).get('include', [])}
    if 'terminal' in config.get('platform_toolsets', {}).get('cli', []):
        tools |= {'terminal', 'process_manage'}
    # Keep reviewed plugin grants unless this attempt supplies a new explicit selection.
    skills |= set(plugin_skills if plugin_skills is not None else (n for n in item.private_skills if ':' in n))
    skills |= {n for n in item.private_skills if ':' not in n}
    tools |= set(plugin_tools if plugin_tools is not None else (
        n for n in item.private_tools if n not in DEFAULT_TOOLS and not n.startswith('mcp__')))
    inherited_skills = set(item.skills) - set(item.private_skills)
    inherited_tools = (set(item.tools) - set(item.private_tools)) | set(item.shared_tools)
    skill_conflicts = skills & inherited_skills
    tool_conflicts = tools & inherited_tools - DEFAULT_TOOLS
    for kind, names in (('skill', skill_conflicts), ('tool', tool_conflicts)):
        if names:
            warnings.append(f'Unresolved private/inherited {kind} name conflict: {", ".join(sorted(names))}. '
                            'Rename that integration; other additions remain in this review.')
    skills -= skill_conflicts
    tools -= tool_conflicts
    return replace(item, skills=tuple(sorted(inherited_skills | skills)),
                   private_skills=tuple(sorted(skills)), tools=tuple(sorted(inherited_tools | tools)),
                   private_tools=tuple(sorted(tools)), shared_tools=tuple(sorted(tools & inherited_tools & DEFAULT_TOOLS)),
                   extension_revision=fingerprint(home))


def retain(cli, ui, item, existing, **kwargs):
    """Preserve the candidate after partial setup; only the normal final save authorizes it."""
    from sci_cli.specialist_editor_state import remember
    warnings = []
    try:
        candidate = reconcile(item, warnings=warnings, **kwargs)
    except (OSError, ValueError, UnicodeError) as exc:
        candidate = item
        warnings.append(f'Private inventory could not be reconciled: {exc}. Files remain at {extension_home(item)}. '
                        'Use Review installed private additions after correcting the source.')
    remember(cli, candidate, existing)
    for message in warnings:
        ui.show(message)
    return candidate


def review_installed(cli, ui, item, existing):
    if not item.extension_id:
        ui.show('This specialist has no private setup directory yet.')
        return item
    home = extension_home(item)
    from sci_cli.config import read_user_config_raw
    enabled = read_user_config_raw(home / 'config.yaml').get('plugins', {}).get('enabled', [])
    kwargs = {}
    if any((home / 'plugins' / name).is_dir() for name in enabled):
        action = ui.choose('Installed plugin tools need code loading for discovery; this is separate from reading skill metadata.',
                           ['Review private plugin tools', 'Keep existing plugin grants', 'Cancel'])
        if action == 'Review private plugin tools':
            from sci_cli.specialist_tool_setup import plugin_inventory
            tools, skills = plugin_inventory(home, ui)
            kwargs = {'plugin_tools': tools, 'plugin_skills': skills}
    candidate = retain(cli, ui, item, existing, **kwargs)
    ui.show('Retained private additions are now in this draft for review. No download, installation, '
            'connection probe or tool execution occurred. Plugin code was loaded only if you approved discovery. '
            'Save and start /new to authorize them.\n'
            'Private skills: ' + (', '.join(candidate.private_skills) or 'none') + '\n'
            'Private tools: ' + (', '.join(candidate.private_tools) or 'none'))
    return candidate
