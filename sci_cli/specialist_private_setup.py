"""Subagent-only setup adapters over existing skill import and MCP connection services."""
from dataclasses import replace
import json
from pathlib import Path
import shlex
from uuid import uuid4

from agent.specialist_extensions import extension_home, capability_scope
from sci_constants import get_sci_home


def prepare_home(item):
    from sci_cli.config import read_user_config_raw, atomic_config_replace
    item = replace(item, extension_id=item.extension_id or uuid4().hex)
    home = extension_home(item)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (home / 'config.yaml').exists():
        owner = read_user_config_raw()
        from sci_cli.plugins_discovery import collect_directory_manifests, resolve_manifest_winners
        manifests = resolve_manifest_winners(collect_directory_manifests())
        disabled_plugins = [key for key, manifest in manifests.items() if manifest.kind == 'standalone']
        # Reuse backend behavior, never copy credentials, plugins, sources or conversation state.
        terminal = dict(owner.get('terminal', {}))
        terminal['cwd'] = str(home / 'workspace')
        (home / 'workspace').mkdir(exist_ok=True)
        delegation = {k: v for k, v in owner.get('delegation', {}).items()
                      if k not in {'api_key', 'base_url', 'model', 'provider'}}
        atomic_config_replace(home / 'config.yaml', {
            'platform_toolsets': {'cli': ['skills']}, 'plugins': {'enabled': [], 'disabled': disabled_plugins},
            'mcp_servers': {}, 'terminal': terminal, 'delegation': delegation,
            'skills': {'disabled': [], 'external_dirs': [], 'inline_shell': False, 'template_vars': False}})
    return item, home


def import_skill(cli, ui, home):
    from sci_cli.skill_add_sources import load_source
    from sci_cli.skill_add import review
    source = ui.ask('Skill URL, identifier, or local SKILL.md/folder/ZIP path:').strip().strip('"\'')
    if source.startswith(('http://', 'https://')) or not Path(source).expanduser().exists():
        ui.show(f'Source: {source}. The existing guarded downloader will inspect it; no imported code runs.')
        ui.choose('Approve download for inspection?', ['Approve download', 'Cancel'])
    # Prevent ambiguity between inherited and private instructions with the same name.
    from tools.skills_tool import _find_all_skills
    inherited = {row['name'] for row in _find_all_skills(skip_disabled=True)}
    with capability_scope(home):
        loaded = load_source(source)
        if loaded.bundle is None:
            raise ValueError('This source is instructional material, not a prepared skill. Supply a reviewed SKILL.md bundle.')
        if loaded.bundle.name in inherited:
            raise ValueError('This skill name exists in the owning profile. Rename the external skill or select the existing one.')
        review(cli, ui, loaded.bundle, loaded, '')


def local_program(cli, ui, home):
    from sci_cli.skill_add import review
    from sci_cli.skill_add_sources import bundle_from_files, Source
    ui.show('This connects software already installed on this host by saving its invocation instructions. '
            'To install/connect a tool from a link or request, choose Add tool (link or request) instead.')
    name = ui.ask('Name this program integration (lowercase-hyphenated):')
    path = Path(ui.ask('Existing executable or script path on this host:').strip('"\'')).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Select an existing regular executable/script file.')
    interpreter = ui.ask('Interpreter path for a script, or none for an executable:')
    executable = [str(path)]
    if interpreter.lower() != 'none':
        runtime = Path(interpreter).expanduser().resolve(strict=True)
        if not runtime.is_file():
            raise ValueError('Interpreter must be an existing file.')
        executable = [str(runtime), str(path)]
    arguments = ui.ask('Documented arguments (shell quoting accepted; none for no arguments):')
    argv = executable + ([] if arguments.lower() == 'none' else shlex.split(arguments))
    working = Path(ui.ask('Working directory for this program:')).expanduser().resolve(strict=True)
    if not working.is_dir():
        raise ValueError('Working directory must be an existing folder.')
    purpose = ui.ask('Purpose and when to use this program:')
    inputs = ui.ask('Required inputs and formats; state unknown if uncertain:')
    outputs = ui.ask('Expected outputs and formats:')
    limitations = ui.ask('Prerequisites, limitations and required checks:')
    # Construct instructions only; neither inspect via --help nor execute during setup.
    content = ('---\nname: ' + json.dumps(name) + '\ndescription: ' + json.dumps(purpose) + '\n---\n'
               f'# {name}\n\n{purpose}\n\nSource: {path}\nWorking directory: {working}\n\nDocumented invocation:\n```sh\n{shlex.join(argv)}\n```\n'
               f'\nInputs: {inputs}\nOutputs: {outputs}\nPrerequisites and limitations: {limitations}\n'
               '\nRun only when requested and allowed by the execution environment. Ask for missing invocation '
               'details; do not invent parameters. Moving/removing the original software breaks this integration. '
               'Execution has not been tested.\n')
    bundle = bundle_from_files({'SKILL.md': content}, str(path))
    with capability_scope(home):
        review(cli, ui, bundle, Source(str(path), bundle=bundle), '')
        from sci_cli.config import read_user_config_raw, atomic_config_replace
        config = read_user_config_raw(home / 'config.yaml')
        config['platform_toolsets']['cli'] = list(dict.fromkeys([*config['platform_toolsets']['cli'], 'terminal']))
        atomic_config_replace(home / 'config.yaml', config)
    ui.show('Local program registered as private skill instructions, not a new model function. '
            'Private terminal/process access is included in the final specialist review. It can use the backend’s '
            'filesystem/network access; it is not restricted to this one executable. '
            'The original software was not installed, moved or executed.')


def connect_mcp(cli, ui, home, owner):
    from sci_cli.native_profile_services import setup_mcp
    from sci_cli.config import read_user_config_raw, atomic_config_replace, save_env_value_secure
    value = ui.ask('Public MCP endpoint URL or local JSON/YAML configuration path:').strip('"\'')
    if value.startswith(('https://', 'http://')):
        name = ui.ask('Connection name (unique within this specialist):')
        raw = {'url': value}
        auth = ui.choose('Authentication', ['None', 'Bearer/API key or custom headers', 'OAuth', 'Cancel'])
        if auth == 'Bearer/API key or custom headers':
            header = ui.ask('Header name, for example Authorization or X-API-Key:')
            variable = ui.ask('Credential variable name, for example SERVICE_API_KEY (not its value):')
            raw['headers'] = {header: ('Bearer ' if header.lower() == 'authorization' else '') + '${' + variable + '}'}
        elif auth == 'OAuth':
            raw['auth'] = 'oauth'
    else:
        path = Path(value).expanduser().resolve(strict=True)
        ui.show(f'Configuration source: {path}')
        if path.stat().st_size > 1_000_000:
            raise ValueError('Configuration exceeds 1 MiB.')
        import sci_yaml as yaml
        data = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        mapping = data.get('mcpServers', data.get('mcp_servers', {})) if isinstance(data, dict) else {}
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError('Provide an mcpServers or mcp_servers mapping.')
        name = ui.choose('Choose one MCP connection to add', [*mapping, 'Cancel'])
        raw = mapping[name]
    with capability_scope(home):
        config = read_user_config_raw(home / 'config.yaml')
    import re
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name):
        raise ValueError('Connection names use letters, numbers, hyphens and underscores.')
    if name in config.get('mcp_servers', {}):
        raise ValueError('That connection already exists. Choose another name; nothing overwritten.')
    service = setup_mcp(cli, ui, owner, name, raw, home)
    if service is None:
        return
    ui.choose('Save this connection for this subagent only?', ['Save private connection', 'Cancel'])
    with capability_scope(home):
        for key, secret in service.secrets.items():
            save_env_value_secure(key, secret)
        config.setdefault('mcp_servers', {})[name] = service.config
        config['platform_toolsets']['cli'] = list(dict.fromkeys([*config['platform_toolsets']['cli'], 'mcp-' + name]))
        atomic_config_replace(home / 'config.yaml', config)
    ui.show(f'Saved {name} for this specialist only. {len(service.tools)} tools allowed. '
            'Discovery passed; no business tool executed. OAuth grants/package downloads, if approved, may remain after cancellation.')


def setup(cli, ui, item):
    """Return the draft with explicit private grants; final specialist save remains separate."""
    from sci_cli.specialist_editor_state import remember, drafts
    owner = get_sci_home()
    action = ui.choose('Add for this subagent only', ['Add tool (link or request)', 'External skill', 'MCP service',
                                                    'Use an already-installed program', 'Back', 'Cancel'])
    if action == 'Back':
        return item
    item, home = prepare_home(item)
    existing = drafts(cli).get(item.name, (None, None))[1]
    remember(cli, item, existing)
    ui.show(f'Private destination for {item.name}: {home}. Main and other specialists do not receive these capabilities. '
            'Saved setup files stay private even if you cancel the specialist draft.')
    plugin_tools = plugin_skills = None
    try:
        from sci_cli.specialist_tool_setup import add_tool
        {'External skill': lambda: import_skill(cli, ui, home),
         'MCP service': lambda: connect_mcp(cli, ui, home, owner),
         'Use an already-installed program': lambda: local_program(cli, ui, home),
         'Add tool (link or request)': lambda: add_tool(cli, ui, home)}[action]()
        if action == 'Add tool (link or request)':
            from sci_cli.specialist_tool_setup import plugin_inventory
            plugin_tools, plugin_skills = plugin_inventory(home, ui)
    finally:
        from sci_cli.specialist_private_inventory import retain
        item = retain(cli, ui, item, existing, plugin_tools=plugin_tools, plugin_skills=plugin_skills)
    if not item.private_skills and not item.private_tools:
        ui.show('No usable private integration was discovered. Review remaining setup; private files may remain.')
    return item
