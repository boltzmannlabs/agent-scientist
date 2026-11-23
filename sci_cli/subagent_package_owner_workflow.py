"""Explicit admission of the route-proposer's companion into Main's profile."""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from sci_cli.config import atomic_config_replace, read_user_config_raw

KEY = 'retrosynthesis_specialists'


def available(owner):
    directory = owner / 'plugins'
    target = directory / KEY
    metadata = directory / '.install-metadata.json'
    cfg = read_user_config_raw(owner / 'config.yaml').get('plugins', {})
    if (directory.is_symlink() or target.exists() or target.is_symlink() or metadata.is_symlink() or
            (metadata.exists() and KEY in json.loads(metadata.read_text())) or
            KEY in cfg.get('entries', {}) or KEY in cfg.get('disabled', ()) or KEY in cfg.get('enabled', ())):
        raise ValueError('Existing owner workflow configuration or installation; use a fresh profile. Nothing overwritten.')


def review(owner, name, ui):
    available(owner)
    ui.show(f'Combined workflow: install the pinned supporting plugin into {owner / "plugins" / KEY} for Main, '
            f'bind its delegation to {name}, and enable its tools, instructions and pre-tool hook. '
            'This is owner-level code execution, including literature access, submitting REBOLT jobs '
            'and using the active provider. The specialist retains only its reviewed leaf tools.')
    if ui.choose('Approve owner plugin, dependencies and routing?', ['Install combined workflow in Main', 'Cancel']) != 'Install combined workflow in Main':
        raise ValueError('Owner workflow installation declined.')


def backend_python():
    from pm.environments import project_python
    for python in dict.fromkeys((project_python(Path(__file__).resolve().parents[1]), Path(sys.executable))):
        if python.is_file() and subprocess.run([str(python), '-I', '-c', 'import jsonschema, mcp, rdkit.Chem'],
                capture_output=True, timeout=30).returncode == 0:
            return str(python)
    raise ValueError('Combined workflow requires an admitted Python environment with RDKit, jsonschema and MCP.')


def configure_private(home):
    from agent.specialist_extensions import capability_scope
    with capability_scope(home):
        python = backend_python()
    path = home / 'config.yaml'
    config = read_user_config_raw(path)
    config.setdefault('plugins', {}).setdefault('entries', {}).setdefault(KEY, {}).setdefault('settings', {}).update(
        enabled=True, backend_python=python)
    config.setdefault('tools', {})['tool_search'] = {'enabled': 'off'}
    atomic_config_replace(path, config)


@contextmanager
def activate(owner, private, name, dependency):
    from sci_cli import plugins_cmd as pc
    from sci_cli.plugins_transaction import publish_plugin
    from sci_cli.tools_config import _get_platform_tools
    from sci_cli.plugins_manifest import parse_manifest_file
    available(owner)
    source = private / 'plugins' / KEY
    manifest = parse_manifest_file(source / 'plugin.yaml', source, 'user', '')
    if manifest is None or manifest.name != KEY or manifest.key != KEY:
        raise ValueError('Reviewed owner plugin identity does not match the workflow.')
    if ('workflow_specialist_name' not in manifest.config_schema or
            not {'start_retrosynthesis_workflow', 'retrosynthesis_workflow_status'} <= set(manifest.provides_tools)):
        raise ValueError('Pinned plugin does not support portable owner workflow installation.')
    metadata = json.loads((private / 'plugins/.install-metadata.json').read_text())[KEY]
    if metadata.get('pinned') is not True or any(metadata.get(k) != dependency[k] for k in ('revision', 'source')):
        raise ValueError('Reviewed owner plugin provenance mismatch.')
    directory = owner / 'plugins'
    directory.mkdir(exist_ok=True)
    target = directory / KEY
    path = owner / 'config.yaml'
    old_cfg = read_user_config_raw(path)
    old_meta = pc._read_install_metadata()
    if KEY in old_meta:
        raise ValueError('Concurrent owner workflow installation; no overwrite.')
    old_enabled, old_disabled = pc._get_enabled_set(), pc._get_disabled_set()
    expected = pc._plugin_selection_version()
    explicit_tools = old_cfg.get('platform_toolsets', {}).get('cli')
    old_tools = explicit_tools if isinstance(explicit_tools, list) else _get_platform_tools(
        old_cfg, 'cli', include_default_mcp_servers=False)
    with tempfile.TemporaryDirectory(dir=owner) as scratch:
        staged = Path(scratch) / KEY
        shutil.copytree(source, staged, symlinks=True)
        publish_plugin(staged, target, old_meta, {**old_meta, KEY:metadata}, new_only=True)
    activated = False
    try:
        enabled, disabled = pc._get_enabled_set(), pc._get_disabled_set()
        pc._apply_activation(enabled, disabled, KEY, (), enable=True)
        pc._admit_and_save_plugin_sets(enabled, disabled, action='Reviewed owner workflow', plugin=KEY, expected_config=expected)
        activated = True
        config = read_user_config_raw(path)
        config.setdefault('plugins', {}).setdefault('entries', {})[KEY] = {'settings': {
            'enabled': True, 'backend_python': backend_python(), 'workflow_specialist_name': name}}
        config.setdefault('platform_toolsets', {})['cli'] = sorted(set(old_tools) | {KEY, 'delegation'})
        atomic_config_replace(path, config)
        yield
    except BaseException:
        if activated:
            pc._admit_and_save_plugin_sets(old_enabled, old_disabled | {KEY}, action='Undo incomplete owner workflow',
                                          expected_config=pc._plugin_selection_version())
            atomic_config_replace(path, old_cfg)
        shutil.rmtree(target)
        from sci_cli.plugins_cmd_git import _update_install_record
        _update_install_record(KEY, lambda current: None if current == metadata else current)
        raise
