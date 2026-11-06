"""Install only the local main-entry plugin, skills and native saved specialist.

Use the existing SDK interpreter. No model, platform request, repository change,
dependency installation or credential copying is performed.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


BUNDLE = Path(__file__).resolve().parents[1]


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def copy_owned_tree(source, target):
    if target.is_symlink():
        raise ValueError('Do not replace a linked destination')
    if target.exists():
        expected = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
        actual = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        if actual != expected:
            raise ValueError('Existing destination differs; no user files were overwritten: ' + str(target))
        return
    shutil.copytree(source, target)


def install(args):
    home = args.owner_home.expanduser().absolute()
    if any(p.is_symlink() for p in (home, *home.parents)) or not home.is_dir():
        raise ValueError('An existing nonsymlink owning profile is required')
    root = args.host_root.resolve()
    state = args.state_root.expanduser().absolute()
    if any(p.is_symlink() for p in (state, *state.parents)) or state.is_relative_to(home) or state.is_relative_to(BUNDLE.parent):
        raise ValueError('Use a private nonsymlink state root outside the profile and checkout')
    if not (root / 'run_agent.py').is_file():
        raise ValueError('Existing SDK checkout required')
    if not (args.environment_source / 'leadopt_env/core.py').is_file():
        raise ValueError('Existing leadopt_env src directory required')
    if not args.scoring_python.is_file():
        raise ValueError('Qualified scoring interpreter required')
    sys.path.insert(0, str(root))
    from sci_constants import set_sci_home_override, reset_sci_home_override
    from sci_cli.config import get_config_path, read_user_config_raw, atomic_config_write, load_config
    from sci_cli.tools_config import _get_platform_tools
    from agent.specialist_store import Specialist, load, save
    from agent.skill_utils import parse_config_string_list
    token = set_sci_home_override(home)
    try:
        source = json.loads((BUNDLE / 'integration/definition.json').read_text())
        item = Specialist.parse(source)
        plugin = home / 'plugins/smallmol-optimization'
        skill = home / 'skills/smallmol-optimization'
        marker = state / 'installations' / (hashlib.sha256(str(home).encode()).hexdigest()[:16] + '.json')
        existing = json.loads(marker.read_text()) if marker.is_file() else None
        definition_path = home / 'subagents' / (item.name + '.json')
        if definition_path.exists() and (not existing or load(item.name).revision != existing['specialist_revision']):
            raise ValueError('An unrelated saved specialist already exists; it was not replaced')
        if plugin.exists() and not existing:
            raise ValueError('An existing plugin was not installed by this installer; it was not replaced')
        config = read_user_config_raw()
        if 'smallmol-optimization' in parse_config_string_list(config.get('plugins', {}).get('disabled')):
            raise ValueError('The user disabled this plugin; its setting was not overridden')
        if 'smallmol_optimization' in parse_config_string_list(config.get('agent', {}).get('disabled_toolsets')):
            raise ValueError('The user disabled this toolset; its setting was not overridden')
        platforms = config.get('platform_toolsets', {})
        selected = parse_config_string_list(platforms.get('cli')) if 'cli' in platforms else sorted(_get_platform_tools(load_config(), 'cli'))
        enabled = parse_config_string_list(config.get('plugins', {}).get('enabled'))
        plugin.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ('__init__.py', 'plugin.yaml'):
            destination = plugin / name
            if destination.is_symlink():
                raise ValueError('Linked plugin destination is unsupported')
            data = (BUNDLE / 'integration/plugin' / name).read_bytes()
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError('Installed plugin source changed; explicit review required')
            if not destination.exists():
                destination.write_bytes(data); destination.chmod(0o600)
        copy_owned_tree(BUNDLE / 'specialist/optimization-v1/skills/smallmol-optimization', skill)
        saved = load(item.name) if existing else save(replace(item, enabled=True, needs_review=False))
        runtime = {'bundle_root': str(BUNDLE), 'host_root': str(root),
                   'sdk_python': str(Path(sys.executable).absolute()),
                   'scoring_python': str(args.scoring_python.absolute()),
                   'environment_source': str(args.environment_source.resolve()),
                   'owner_home': str(home), 'state_root': str(state),
                   'specialist_revision': saved.revision}
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        private_json(plugin / 'runtime.json', runtime)
        config.setdefault('plugins', {})['enabled'] = list(dict.fromkeys([*enabled, 'smallmol-optimization']))
        config.setdefault('platform_toolsets', {})['cli'] = list(dict.fromkeys([*selected, 'smallmol_optimization', 'delegation', 'skills']))
        atomic_config_write(get_config_path(), config)
        receipt = {'schema_version': 1, 'owner_home': str(home), 'plugin': str(plugin),
                   'specialist': saved.name, 'specialist_revision': saved.revision,
                   'installed_skills': [str(skill)], 'source_definition_sha256': hashlib.sha256((BUNDLE / 'integration/definition.json').read_bytes()).hexdigest(),
                   'next_step': 'Start a new main-agent conversation in this owning profile',
                   'scientific_jobs_submitted': 0, 'credentials_copied': False}
        private_json(marker, receipt)
        return receipt
    finally:
        reset_sci_home_override(token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-home', type=Path, required=True)
    parser.add_argument('--host-root', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--scoring-python', type=Path, required=True)
    parser.add_argument('--environment-source', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(install(args), sort_keys=True))


if __name__ == '__main__':
    main()
