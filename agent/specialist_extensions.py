"""Private specialist capability homes, using the existing scoped runtime infrastructure."""
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from sci_constants import get_sci_home


def extension_home(item, owner=None):
    if not item.extension_id:
        return None
    root = Path(owner or get_sci_home())
    home = root / 'subagent-data' / item.extension_id
    for path in (root / 'subagent-data', home):
        if path.is_symlink():
            raise ValueError('Private capability directories cannot be symbolic links.')
    if home.resolve().parent != (root / 'subagent-data').resolve():
        raise ValueError('Invalid private capability destination.')
    return home


@contextmanager
def capability_scope(home):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from sci_cli.native_profile_creation import profile_scope
    from tools.terminal_scope import install_and_reset_profile_terminal_scope
    token = set_multiplex_context(True)
    try:
        with profile_scope(Path(home)), install_and_reset_profile_terminal_scope(Path(home)):
            yield
    finally:
        reset_multiplex_context(token)


def fingerprint(home):
    """Detect changed private grants/credentials without publishing their contents."""
    digest = sha256()
    for name in ('config.yaml', '.env'):
        path = home / name
        if path.is_symlink():
            raise ValueError('Private configuration cannot be a symbolic link.')
        digest.update(name.encode())
        digest.update(path.read_bytes() if path.exists() else b'')
    for directory in ('skills', 'plugins'):
        for path in sorted((home / directory).rglob('*')):
            if set(path.relative_to(home / directory).parts) & {'.git', '__pycache__', 'node_modules', '.venv'}:
                continue
            if path.is_symlink():
                raise ValueError('Private capability source cannot contain symbolic links.')
            # These SCI-owned bookkeeping files change when skills are viewed,
            # used or locked. They do not grant capabilities. Keep exclusions
            # confined to their exact top-level skills locations; hidden files
            # in a skill or plugin can still contain executable instructions.
            relative = path.relative_to(home / directory)
            if directory == 'skills' and (
                relative.as_posix() in {'.usage.json', '.usage.json.lock',
                                        '.curator_ledger.jsonl', '.hub/audit.log'}
                or relative.parts[0] == '.locks'
            ):
                continue
            if path.is_file():
                digest.update(str(path.relative_to(home)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def without_private(item):
    return replace(item, extension_id='', extension_revision='', private_skills=(), private_tools=(), shared_tools=(), package_info={},
                   skills=tuple(n for n in item.skills if n not in item.private_skills),
                   tools=tuple(n for n in item.tools if n not in item.private_tools or n in item.shared_tools),
                   skill_files=tuple(r for r in item.skill_files if r.partition('#')[0] not in item.private_skills))


def private_definitions(item):
    """Discover approved private MCPs in their own registry scope, never the parent registry."""
    home = extension_home(item)
    if home is None:
        return []
    from tools.mcp_tool_discovery import discover_mcp_tools
    from sci_cli.config import read_user_config_raw
    import model_tools
    from tools.delegate_tool_results import _CHILD_CONSTRUCTION_LOCK
    with _CHILD_CONSTRUCTION_LOCK:
        previous = list(model_tools._last_resolved_tool_names)
        try:
            with capability_scope(home):
                cfg = read_user_config_raw(home / 'config.yaml')
                servers = cfg.get('mcp_servers', {})
                if servers:
                    discover_mcp_tools(allowed_mcp_names=list(servers))
                from sci_cli.plugins import get_plugin_manager
                get_plugin_manager().discover_and_load()
                return model_tools.get_tool_definitions(cfg.get('platform_toolsets', {}).get('cli', []), quiet_mode=True,
                                                       skip_tool_search_assembly=True)
        finally:
            model_tools._last_resolved_tool_names = previous


def install_parent_proxies(policy, entries):
    """Keep inherited service handlers bound to their original credentials and configuration."""
    from tools.registry import registry
    from agent.specialist_sources import DEFAULT_TOOLS
    for entry in entries:
        # File/code/process operations belong to the private execution backend. Service
        # integrations keep their owning profile's credentials through these proxies.
        if entry.name not in policy.tools or entry.name in policy.private_tools or entry.name in DEFAULT_TOOLS | {'skill_view', 'skills_list'}:
            continue
        def handler(args, _entry=entry, **kwargs):
            with capability_scope(policy.home):
                # Registry dispatch owns async bridging and signature filtering.
                return registry.dispatch(_entry.name, args, **kwargs)
        registry.register(name=entry.name, toolset=entry.toolset, schema=entry.schema,
                          handler=handler, scope=policy.execution_home,
                          check_fn=None)


@contextmanager
def execution_scope(policy):
    """Bind private capabilities only while constructing/running their owning child."""
    home = getattr(policy, 'execution_home', '')
    if home:
        with capability_scope(home):
            yield
    else:
        yield
