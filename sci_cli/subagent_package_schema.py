"""Strict portable package schema. Validation never imports contributed code or contacts services."""
import json
import re
from urllib.parse import urlsplit
from pathlib import PurePosixPath

from sci_cli.subagent_package_io import tree, relative, verify, digest, LOCK

TOKEN = re.compile(r'\{\{([^{}]+)\}\}')
_PRIVATE_PATH = re.compile(r'(?:/home/|/Users/|/root/|[A-Za-z]:[\\/]|\.sci/(?:profiles|subagent-data)/)')
_SECRET = re.compile(r'(?i)(?:-----BEGIN .*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})|'
                     r'(?:api[_-]?key|password|access[_-]?token|client[_-]?secret)\s*[:=]\s*["\']?(?!\$\{|\{\{|unknown\b|example\b|none\b)[A-Za-z0-9_+/=-]{16,})')


def obj(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError(f'Invalid fields; allowed={sorted(allowed)}, required={sorted(required)}')
    return value


def names(value):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value) or len(set(value)) != len(value):
        raise ValueError('Expected unique nonempty strings.')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value):
        raise ValueError('Identifiers use lowercase letters, numbers, hyphens and underscores.')
    return value


def https(value):
    if not isinstance(value, str):
        raise ValueError('URL must be text.')
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('Sources must be public HTTPS URLs without credentials, query or fragment.')


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('An exact SHA-256 digest is required.')


def dependency(dep):
    common = {'id', 'kind', 'optional'}
    fields = {
        'mcp': {'config', 'tools'}, 'plugin': {'source', 'revision', 'tools', 'skills'},
        'program': {'version', 'version_args', 'version_contains', 'artifacts'},
        'boltzmann': {'modules', 'contract_sha256'},
    }
    kind = dep.get('kind') if isinstance(dep, dict) else None
    if kind not in fields:
        raise ValueError('Dependency kind must be program, plugin, mcp or boltzmann.')
    obj(dep, common | fields[kind], {'id', 'kind'})
    identifier(dep['id'])
    if type(dep.get('optional', False)) is not bool:
        raise ValueError('optional must be boolean.')
    return {'mcp': _mcp_dependency, 'plugin': _plugin_dependency,
            'program': _program_dependency, 'boltzmann': _boltzmann_dependency}[kind](dep)


def _mcp_dependency(dep):
    cfg = dep.get('config')
    from sci_cli.mcp_security import validate_mcp_server_entry
    if not isinstance(cfg, dict) or validate_mcp_server_entry(dep['id'], cfg):
        raise ValueError('Invalid/unsafe MCP template.')
    names(dep.get('tools'))
    if not dep['tools'] or any(any(c in n for c in '*?[]') for n in dep['tools']):
        raise ValueError('MCP tools require a nonempty exact allowlist.')
    if cfg.get('url'):
        https(cfg['url'])
    if cfg.get('command') and ('/' in cfg['command'] or '\\' in cfg['command']) and not cfg['command'].startswith('{{program.'):
        raise ValueError('Local MCP executable paths must use a declared program token.')
    for section in ('headers', 'env'):
        for key, value in (cfg.get(section) or {}).items():
            secret = section == 'headers' and key.lower() not in {'accept', 'content-type', 'user-agent'}
            secret |= bool(re.search('(?i)key|token|secret|password|credential', key))
            if secret and (not isinstance(value, str) or not re.search(r'\$\{[A-Z_][A-Z0-9_]*\}', value)):
                raise ValueError('Credential values must be ${VARIABLE} references, never literals.')


def _plugin_dependency(dep):
    https(dep.get('source', ''))
    if not isinstance(dep.get('revision'), str) or not re.fullmatch('[a-fA-F0-9]{40}', dep['revision']):
        raise ValueError('Plugin sources require an exact 40-character commit SHA.')
    names(dep.get('tools', [])); names(dep.get('skills', []))


def _program_dependency(dep):
    if not isinstance(dep.get('version'), str) or not dep['version'].strip():
        raise ValueError('Program version is required.')
    names(dep.get('version_args'))
    if not dep['version_args'] or not isinstance(dep.get('version_contains'), str) or not dep['version_contains']:
        raise ValueError('Program verification needs version_args and expected version text.')
    artifacts = dep.get('artifacts', [])
    if not isinstance(artifacts, list):
        raise ValueError('artifacts must be a list.')
    seen_platforms = set()
    for artifact in artifacts:
        obj(artifact, {'platform', 'url', 'sha256', 'format', 'executable'}, {'platform', 'url', 'sha256', 'format', 'executable'})
        if not isinstance(artifact['platform'], str) or artifact['platform'] in seen_platforms:
            raise ValueError('Program artifacts need unique platform identifiers.')
        seen_platforms.add(artifact['platform'])
        https(artifact['url']); hash_value(artifact['sha256']); relative(artifact['executable'])
        if artifact['format'] not in {'file', 'zip', 'tar.gz'}:
            raise ValueError('Program artifact format must be file, zip or tar.gz.')


def _boltzmann_dependency(dep):
    names(dep.get('modules', []))
    for path in dep.get('modules', []):
        relative(path)
        if not path.startswith('references/modules/'):
            raise ValueError('Boltzmann modules must reference maintained module files.')
    if dep.get('contract_sha256'):
        hash_value(dep['contract_sha256'])


def validate(root, *, allow_draft=False, require_lock=False):
    from packaging.version import Version
    from packaging.specifiers import SpecifierSet
    import sci_yaml as yaml
    from pathlib import Path
    root = Path(root)
    files = tree(root)
    if require_lock or LOCK in files:
        verify(files)
    try:
        manifest = yaml.safe_load(files['manifest.yaml'].decode('utf-8-sig'))
    except (KeyError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        raise ValueError('Missing or invalid manifest.yaml.') from exc
    allowed = {'schema_version', 'id', 'name', 'version', 'authors', 'license', 'description', 'sci_requires',
               'instructions', 'output', 'tools', 'skills', 'skill_files', 'dependencies', 'references',
               'limits', 'platforms', 'fixtures', 'children', 'unresolved', 'automatic'}
    obj(manifest, allowed, allowed - {'children', 'unresolved', 'automatic', 'skill_files'})
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        raise ValueError('Unsupported package schema version.')
    identifier(manifest['id']); identifier(manifest['name'])
    if not isinstance(manifest['version'], str) or not isinstance(manifest['sci_requires'], str):
        raise ValueError('version and sci_requires must be strings.')
    Version(manifest['version']); SpecifierSet(manifest['sci_requires'])
    for field in ('license', 'description', 'output'):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f'{field} must be nonempty text.')
    if not names(manifest['authors']):
        raise ValueError('At least one author is required.')
    if type(manifest.get('automatic', True)) is not bool:
        raise ValueError('automatic must be boolean.')
    for field in ('skills', 'dependencies', 'references', 'fixtures'):
        if not isinstance(manifest[field], list) or any(not isinstance(v, dict) for v in manifest[field]):
            raise ValueError(f'{field} must be a list of objects.')
    names(manifest.get('unresolved', []))
    if manifest.get('unresolved') and not allow_draft:
        raise ValueError('Package is a draft with unresolved requirements: ' + '; '.join(names(manifest['unresolved'])))
    limits = obj(manifest['limits'], {'max_iterations', 'timeout_seconds'}, {'max_iterations', 'timeout_seconds'})
    if any(type(v) is not int or v < 1 for v in limits.values()):
        raise ValueError('Execution limits must be positive integers.')
    if not names(manifest['platforms']):
        raise ValueError('At least one supported platform is required.')
    for name in manifest['platforms']:
        if not re.fullmatch(r'(?:any|linux|macos|windows)(?:-[a-z0-9_]+)?', name):
            raise ValueError('Use platform keys such as any, linux-amd64, macos-arm64 or windows-amd64.')
    from agent.specialist_runtime import BLOCKED
    for tool in names(manifest['tools']):
        if tool in BLOCKED:
            raise ValueError('This tool cannot be granted to a specialist: ' + tool)
        if any(c in tool for c in '*?[]'):
            raise ValueError('Tool grants cannot contain wildcards.')
    def file(path):
        relative(path)
        if path not in files:
            raise ValueError(f'Required file is missing: {path}')
    file(manifest['instructions'])
    skill_ids = set()
    for skill in manifest['skills']:
        obj(skill, {'id', 'kind', 'path', 'sha256'}, {'id', 'kind'})
        if not isinstance(skill['id'], str) or not skill['id'].strip():
            raise ValueError('Skill identifiers must be nonempty strings.')
        if skill['id'] in skill_ids:
            raise ValueError('Duplicate skill requirement.')
        skill_ids.add(skill['id'])
        if skill['kind'] == 'package':
            if not isinstance(skill.get('path'), str):
                raise ValueError('Packaged skills need a relative path.')
            relative(skill['path']); file(skill['path'] + '/SKILL.md')
            from sci_cli.skill_add_sources import folder_bundle
            bundle = folder_bundle(root / skill['path'])
            if bundle.name != skill['id']:
                raise ValueError('Packaged skill name does not match its requirement.')
        elif skill['kind'] != 'existing':
            raise ValueError('Skill kind must be package or existing.')
        if skill.get('sha256'):
            hash_value(skill['sha256'])
    ids = set()
    kinds = {}
    for dep in manifest['dependencies']:
        dependency(dep)
        if dep['id'] in ids:
            raise ValueError('Duplicate dependency ID.')
        ids.add(dep['id'])
        kinds[dep['id']] = dep['kind']
    for ref in manifest['references']:
        obj(ref, {'path', 'url', 'label', 'license', 'required', 'mode'}, {'label', 'license'})
        if ('path' in ref) == ('url' in ref) or not ref['license']:
            raise ValueError('Reference requires one path/URL and redistribution/source license.')
        if 'path' in ref:
            file(ref['path'])
        else:
            https(ref['url'])
        if ref.get('mode', 'snapshot') not in {'snapshot', 'original'} or type(ref.get('required', False)) is not bool:
            raise ValueError('Reference mode is snapshot/original; required must be boolean.')
    if not isinstance(manifest['fixtures'], list) or not manifest['fixtures']:
        if not allow_draft:
            raise ValueError('At least one synthetic/approved fixture and expected JSON result are required.')
    for fixture in manifest['fixtures']:
        obj(fixture, {'input', 'expected', 'description'}, {'input', 'expected'})
        file(fixture['input']); file(fixture['expected'])
        if not isinstance(json.loads(files[fixture['expected']]), dict):
            raise ValueError('Expected fixture results must be a JSON object.')
    if manifest.get('children'):
        raise ValueError('Child-specialist packages are not installable in schema v1; do not publish an unsupported pipeline.')
    for reference in names(manifest.get('skill_files', [])):
        skill, separator, path = reference.partition('#')
        if not separator or skill not in skill_ids:
            raise ValueError('Skill files must reference a declared skill.')
        relative(path)
    folded = set()
    for name, data in files.items():
        if name.casefold() in folded:
            raise ValueError('Case-colliding package paths are not portable.')
        folded.add(name.casefold())
        if any(p.startswith('.') or p in {'__pycache__', 'node_modules', 'venv', 'logs', 'sessions'} for p in PurePosixPath(name).parts):
            raise ValueError(f'Runtime/hidden state cannot be distributed: {name}')
        if PurePosixPath(name).name in {'config.yaml', 'state.db', 'auth.json', 'authorization.json'}:
            raise ValueError(f'Runtime state cannot be distributed: {name}')
        try:
            text = data.decode('utf-8')
        except UnicodeError as exc:
            if name.startswith(('references/', 'tests/', 'skills/')) and PurePosixPath(name).suffix.lower() in {'.pdf', '.png', '.jpg', '.jpeg'}:
                continue  # Preserve approved original documents; never execute or unpickle them.
            raise ValueError('Executable/serialized binary payloads must be external declared dependencies.') from exc
        if re.search(r'https?://[^\s/]+:[^\s/@]+@', text) or re.search(r'(?i)[?&](?:api[_-]?key|token|signature|password|secret)=', text):
            raise ValueError(f'Credential-bearing URL in {name}.')
        if _SECRET.search(text):
            raise ValueError(f'Potential credential/private key in {name}; remove it and review manually.')
        if _PRIVATE_PATH.search(text):
            raise ValueError(f'Contributor-machine path in {name}; replace it with a declared resource/program token.')
        for token in TOKEN.findall(text):
            parts = token.split('.', 2)
            valid = (token == 'workspace' or
                     (parts[0] == 'program' and len(parts) in {2, 3} and kinds.get(parts[1]) == 'program' and (len(parts) == 2 or parts[2] == 'dir')) or
                     (parts[0] == 'tool' and len(parts) == 3 and kinds.get(parts[1]) in {'mcp', 'plugin', 'boltzmann'}) or
                     (token.startswith('resource.') and token[9:] in files))
            if not valid:
                raise ValueError(f'Unknown resource/dependency token {token} in {name}.')
    return manifest, files, digest(files)
