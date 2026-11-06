"""Existing MCP/plugin/Boltzmann setup with package-owned scope and explicit consent."""
from hashlib import sha256


def mcp(dep, home, owner, cli, ui, render):
    from sci_cli.native_profile_services import setup_mcp
    from sci_cli.config import read_user_config_raw, atomic_config_replace, save_env_value_secure
    from tools.mcp_tool_schema import mcp_prefixed_tool_name
    from agent.specialist_extensions import capability_scope
    current = read_user_config_raw(owner / 'config.yaml').get('mcp_servers', {})
    candidates = [name for name, config in current.items() if isinstance(config, dict) and config.get('enabled', True)]
    options = (['Use an existing connection'] if candidates else []) + ['Create private connection', 'Defer setup', 'Cancel']
    choice = ui.choose(f'MCP dependency {dep["id"]}: {", ".join(dep["tools"])}', options)
    if choice == 'Defer setup':
        return None
    if choice == 'Use an existing connection':
        name = ui.choose('Choose the account/connection explicitly; no credential is displayed', [*candidates, 'Cancel'])
        raw = current[name]
        # Verify with the existing credential/probe path, but stage a separate private connection.
        ui.show('The selected template/credentials are offered for an approved private copy. '
                'Original connection permissions/configuration stay unchanged.')
    else:
        name, raw = dep['id'], render(dep['config'])
    service = setup_mcp(cli, ui, owner, name, raw, home, selected=dep['tools'])
    if service is None or not set(dep['tools']) <= set(service.tools):
        ui.show('Required MCP tools were not all discovered/selected; no usable dependency was granted.')
        return None
    # Narrow even an existing broader connection to this package's exact required tools.
    service.config['tools']['include'] = list(dep['tools'])
    with capability_scope(home):
        for key, secret in service.secrets.items():
            save_env_value_secure(key, secret)
        config = read_user_config_raw(home / 'config.yaml')
        config.setdefault('mcp_servers', {})[name] = service.config
        config['platform_toolsets']['cli'] = sorted(set(config['platform_toolsets']['cli']) | {'mcp-' + name})
        atomic_config_replace(home / 'config.yaml', config)
    return {'tools': {tool: mcp_prefixed_tool_name(name, tool) for tool in dep['tools']},
            'verification': 'handshake and explicit tool discovery passed; business execution not tested'}


def boltzmann(dep, home, owner, cli, ui, render):
    from sci_cli.native_profile_services import setup_boltzmann
    from sci_cli.config import read_user_config_raw, atomic_config_replace, save_env_value_secure
    from sci_cli.science_catalog_view import registry_path
    from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS
    from agent.specialist_extensions import capability_scope
    if dep.get('contract_sha256') and sha256(registry_path().read_bytes()).hexdigest() != dep['contract_sha256']:
        ui.show('Boltzmann contract revision differs from this package; review compatibility before installation.')
        return None
    choice = ui.choose('Boltzmann needs recipient authorization. Modules focus instructions; they do not restrict workflows.',
                       ['Configure private authorization', 'Defer setup', 'Cancel'])
    if choice == 'Defer setup':
        return None
    service = setup_boltzmann(cli, ui, owner, type('Manifest', (), {'source': 'bundled'})())
    if service is None:
        return None
    with capability_scope(home):
        for key, value in service.secrets.items():
            save_env_value_secure(key, value)
        from plugins.boltzmann.auth import authorize_saved_key
        authorize_saved_key()
        config = read_user_config_raw(home / 'config.yaml')
        plugins = config.setdefault('plugins', {})
        plugins['enabled'] = sorted(set(plugins.get('enabled', [])) | {'boltzmann'})
        plugins['disabled'] = [n for n in plugins.get('disabled', []) if n != 'boltzmann']
        config['platform_toolsets']['cli'] = sorted(set(config['platform_toolsets']['cli']) | {'boltzmann'})
        atomic_config_replace(home / 'config.yaml', config)
        root = registry_path().parent
        if any(not (root.parent / path).is_file() for path in dep.get('modules', [])):
            raise ValueError('A required maintained Boltzmann module is missing.')
    return {'tools': {n: n for n in BOLTZMANN_WORKFLOW_TOOLS}, 'skills': ['boltzmann:tools'],
            'skill_files': ['boltzmann:tools#' + p for p in dep.get('modules', [])],
            'verification': 'credential check and local authorization passed; scientific jobs not run'}


def plugin(dep, home, owner, cli, ui, render):
    from agent.specialist_extensions import capability_scope
    from sci_cli import plugins_cmd as pc
    from sci_cli.plugin_capabilities import record_consent
    ui.show(f'Plugin source: {dep["source"]}\nExact revision: {dep["revision"]}\nDestination: {home / "plugins"}\n'
            'Plugin code has whole-plugin host access. Tool selection is not code isolation.')
    if ui.choose('Prepare this pinned plugin?', ['Install pinned plugin', 'Defer setup', 'Cancel']) == 'Defer setup':
        return None
    with capability_scope(home):
        from sci_cli.plugins_cmd_catalog import raise_if_removed
        git_url = pc._resolve_git_url(dep['source'])[0]
        raise_if_removed(dep['source'], git_url)
        target, manifest, name = pc._install_plugin_core(dep['source'], force=False, ref=dep['revision'],
            scan_decision_cb=lambda scan: ui.choose(f'Scan: {scan.verdict}; review findings: {scan.findings}',
                                                  ['Accept scan warnings', 'Cancel']) == 'Accept scan warnings')
        from pm.plugin_declarations import read_python_declaration
        declaration = read_python_declaration(target)
        ui.show('Declared Python dependencies: ' + repr(declaration.install_requirements))
        if (target / 'package.json').exists():
            ui.show('Node sidecar preparation can execute dependency install scripts.')
            ui.choose('Approve managed Node sidecar installation?', ['Prepare Node dependencies', 'Cancel'])
            from pm.workspace import install_node_sidecar
            if error := install_node_sidecar(target, explicit=True):
                raise ValueError(str(error))
        declared = pc._declared_capabilities_from_manifest(manifest, name)
        ui.show('Whole-plugin host capability declarations: ' + repr(declared))
        ui.choose('Approve dependency admission, declared capabilities and plugin-code loading?', ['Approve plugin access', 'Cancel'])
        record_consent(name, declared, declared)
        from sci_cli.native_profile_services import credential
        from sci_cli.config import save_env_value_secure
        from agent.secret_scope import build_profile_secret_scope
        existing = build_profile_secret_scope(owner)
        for spec in manifest.get('requires_env', []):
            key = spec if isinstance(spec, str) else spec['name']
            value, _ = credential(cli, ui, key, existing.get(key, ''))
            if value is None:
                return None
            save_env_value_secure(key, value)
        enabled, disabled = pc._get_enabled_set(), pc._get_disabled_set()
        pc._apply_activation(enabled, disabled, name, (), enable=True)
        pc._admit_and_save_plugin_sets(enabled, disabled, action='Package plugin dependency', plugin=name)
        from sci_cli.plugins import get_plugin_manager
        from sci_cli.config import atomic_config_replace, read_user_config_raw
        from tools.registry import registry
        manager = get_plugin_manager()
        manager.discover_and_load(force=True)
        loaded = manager._plugins.get(name)
        if loaded is None or loaded.error or not set(dep.get('tools', [])) <= set(loaded.tools_registered):
            raise ValueError('Plugin did not load its declared required tools; software may remain installed.')
        sets = {registry.get_entry(n).toolset for n in dep.get('tools', [])}
        config = read_user_config_raw(home / 'config.yaml')
        config['platform_toolsets']['cli'] = sorted(set(config['platform_toolsets']['cli']) | sets)
        atomic_config_replace(home / 'config.yaml', config)
    return {'tools': {n: n for n in dep.get('tools', [])}, 'skills': dep.get('skills', []),
            'verification': 'pinned scan, dependency admission and module/tool registration passed; service execution not tested'}
