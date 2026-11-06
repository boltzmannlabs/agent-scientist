"""Profile-aware package installation, explicit readiness and revision-checked managed updates."""
from dataclasses import asdict, replace
from contextlib import nullcontext
from agent.specialist_sources import DEFAULT_TOOLS
from hashlib import sha256
from pathlib import Path
import json
import threading

from agent.specialist_store import Specialist, inventory, save, validate_name
from agent.specialist_extensions import capability_scope, extension_home, fingerprint, private_definitions
from sci_cli.subagent_package_schema import validate, TOKEN


def definition_digest(item):
    data = asdict(item)
    data.pop('revision', None)
    data.pop('package_info', None)
    return sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _render(value, bindings):
    if isinstance(value, str):
        def token(match):
            if match[1] not in bindings:
                raise ValueError('Unresolved dependency/resource: ' + match[1])
            return bindings[match[1]]
        return TOKEN.sub(token, value)
    if isinstance(value, list):
        return [_render(v, bindings) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, bindings) for k, v in value.items()}
    return value



def _render_file(value, bindings):
    if isinstance(value, bytes):
        try:
            value = value.decode('utf-8')
        except UnicodeError:
            return value  # approved original supporting assets remain byte-identical
    return _render(value, bindings)


def _existing(ui, items, name, manifest, digest):
    from packaging.version import Version
    while name in items:
        current = items[name]
        info = current.package_info
        same = info.get('id') == manifest['id']
        modified = info.get('definition_digest') != definition_digest(current)
        choices = ['Rename', 'Cancel']
        resumable = same and not modified and info.get('digest') == digest and info.get('state') == 'setup_required'
        updatable = same and not modified and Version(manifest['version']) > Version(info['version'])
        if resumable:
            choices.insert(0, 'Resume setup')
        elif updatable:
            choices.insert(0, 'Review managed update')
        ui.show(f'{name} already exists. ' + ('Local edits are preserved; install under another name.' if modified else
                  f'Installed package: {info.get("id", "unmanaged")} {info.get("version", "")}.'))
        choice = ui.choose('Name/version conflict', choices)
        if choice == 'Rename':
            name = ui.ask('New local specialist name:')
            validate_name(name)
            continue
        if choice == 'Cancel':
            from sci_cli.skill_add import Cancelled
            raise Cancelled()
        return name, current, resumable
    return name, None, False


def install(root, owner, cli, ui, *, name=None, source='local package'):
    from sci_cli.native_profile_creation import profile_scope
    owner = Path(owner)
    if (owner / 'science-profile.json').exists():
        raise ValueError('Restricted legacy profile: reviewed migration is required; isolation was not changed.')
    from sci_cli.auth import _file_lock
    directory = owner / 'subagents'
    directory.mkdir(parents=True, exist_ok=True)
    with profile_scope(owner), _file_lock(directory / '.packages.lock', threading.local(), 10, 'Another package operation is running.'):
        return _install_locked(root, owner, cli, ui, name=name, source=source)


def _install_locked(root, owner, cli, ui, *, name, source):
    from packaging.specifiers import SpecifierSet
    from sci_cli.plugins_manifest import running_sci_version
    from sci_cli.subagent_package_programs import platform_key
    from sci_cli.specialist_private_setup import prepare_home
    from sci_cli.config import read_user_config_raw
    manifest, files, digest = validate(root)
    if not SpecifierSet(manifest['sci_requires']).contains(running_sci_version(), prereleases=True):
        raise ValueError('Package SCI compatibility requirement does not match this installation.')
    platform = platform_key()
    if not set(manifest['platforms']) & {'any', platform, platform.split('-')[0]}:
        raise ValueError(f'Package does not support this CLI host: {platform}. No installation started.')
    name = name or manifest['name']
    validate_name(name)
    name, previous, resume = _existing(ui, inventory()[0], name, manifest, digest)
    ui.show(f'Package: {manifest["id"]} {manifest["version"]}\nAuthors: {", ".join(manifest["authors"])}\n'
            f'License: {manifest["license"]}\nDestination profile: {owner}\n'
            f'Requested tools: {", ".join(manifest["tools"]) or "none"}\n'
            f'Dependencies: {json.dumps(manifest["dependencies"], indent=2)}\n'
            'Catalog membership/checksums do not establish scientific correctness. '
            'Executable setup and service authentication need their separate approvals. Current conversation stays unchanged.')
    if previous and previous.extension_id:
        old_manifest, _, _ = validate(extension_home(previous) / 'package', require_lock=True)
        old_tools, new_tools = set(old_manifest['tools']), set(manifest['tools'])
        old_dependencies = {d['id']: d for d in old_manifest['dependencies']}
        new_dependencies = {d['id']: d for d in manifest['dependencies']}
        changed = sorted(key for key in old_dependencies.keys() | new_dependencies.keys()
                         if old_dependencies.get(key) != new_dependencies.get(key))
        ui.show('Reviewed package changes: tools added=' + ', '.join(sorted(new_tools - old_tools)) +
                '; tools removed=' + ', '.join(sorted(old_tools - new_tools)) +
                '; dependencies changed=' + ', '.join(changed) +
                f'; content {previous.package_info["digest"]} -> {digest}. All new declarations above require review.')
    ui.choose('Prepare this package?', ['Prepare package', 'Cancel'])
    if previous and previous.extension_id:
        old = extension_home(previous)
        if fingerprint(old) != previous.extension_revision:
            raise ValueError('Installed private setup was modified. Preserve it and install under a new name, or review its changes first.')
    initial = Specialist(name, manifest['description'], automatic=manifest.get('automatic', True),
                         max_iterations=manifest['limits']['max_iterations'], timeout_seconds=manifest['limits']['timeout_seconds'])
    if resume:
        initial = replace(initial, extension_id=previous.extension_id)
    item, home = prepare_home(initial)
    ui.show(f'[Package] Private staging destination: {home}. Partial downloads, installed software or credentials '
            'may remain here after cancellation/failure; existing specialists are published only at final save.')
    package_root = home / 'package'
    if package_root.exists():
        _, _, retained_digest = validate(package_root, require_lock=True)
        if retained_digest != digest:
            raise ValueError('Retained package content conflicts with this resume; nothing overwritten.')
    else:
        package_root.mkdir()
        for relative, data in files.items():
            target = package_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    from sci_cli.subagent_package_io import seal
    seal(package_root)  # Locally reviewed bytes, not a contributor-generated artifact.
    bindings = {'workspace': str(home / 'workspace')}
    bindings.update({'resource.' + path: str(package_root / path) for path in files})
    missing, resolved, private_tools, private_skills, module_files = [], {}, set(), set(), []
    from sci_cli.subagent_package_programs import prepare as program
    from sci_cli.subagent_package_integrations import mcp, plugin, boltzmann
    handlers = {'mcp': mcp, 'plugin': plugin, 'boltzmann': boltzmann}
    dependencies = sorted(manifest['dependencies'], key=lambda dep: dep['kind'] != 'program')
    old_resolved = previous.package_info.get('resolved', {}) if resume else {}
    credential_source = extension_home(previous) if previous and previous.extension_id else owner
    for dep in dependencies:
        try:
            if dep['id'] in old_resolved:
                result = old_resolved[dep['id']]
                if dep['kind'] == 'program' and (not Path(result['path']).is_file() or
                        sha256(Path(result['path']).read_bytes()).hexdigest() != result['sha256']):
                    raise ValueError('Retained program is missing or changed; re-review its installation.')
                ui.show('Reusing retained verified setup: ' + dep['id'])
            elif dep['kind'] == 'program':
                backend = read_user_config_raw(home / 'config.yaml').get('terminal', {}).get('backend', 'local')
                if backend != 'local':
                    raise ValueError('Host program dependencies currently require a local backend; no host fallback is allowed.')
                with capability_scope(home):
                    result = program(dep, home, ui)
            else:
                result = handlers[dep['kind']](dep, home, credential_source, cli, ui, lambda value: _render(value, bindings))
            if result is None:
                if not dep.get('optional', False):
                    missing.append('Required dependency not prepared: ' + dep['id'])
                continue
            resolved[dep['id']] = result
            if dep['kind'] == 'program':
                bindings['program.' + dep['id']] = result['path']
                bindings['program.' + dep['id'] + '.dir'] = str(Path(result['path']).parent)
                private_tools |= {'terminal', 'process_manage'}
                from sci_cli.config import atomic_config_replace
                cfg = read_user_config_raw(home / 'config.yaml')
                cfg['platform_toolsets']['cli'] = sorted(set(cfg['platform_toolsets']['cli']) | {'terminal'})
                atomic_config_replace(home / 'config.yaml', cfg)
            else:
                private_tools.update(result.get('tools', {}).values())
                private_skills.update(result.get('skills', []))
                module_files += result.get('skill_files', [])
                for raw, actual in result.get('tools', {}).items():
                    bindings[f'tool.{dep["id"]}.{raw}'] = actual
        except (ValueError, OSError, RuntimeError) as exc:
            from sci_cli.mcp_config import redact_mcp_probe_text
            message = redact_mcp_probe_text(str(exc))
            ui.show(f'[Package] {dep["id"]}: setup failed: {message}. Retained side effects are at {home}.')
            if not dep.get('optional', False):
                missing.append(dep['id'] + ': ' + message)
    skills = set()
    from tools.skills_tool import skill_view
    for spec in manifest['skills']:
        if spec['kind'] == 'package':
            try:
                from sci_cli.skill_add_sources import folder_bundle, bundle_from_files
                from sci_cli.skill_add_store import scanned_bundle, save_reviewed
                bundle = folder_bundle(package_root / spec['path'])
                contents = {p: _render_file(v, bindings) for p, v in bundle.files.items()}
                bundle = bundle_from_files(contents, source)
                with capability_scope(home):
                    target = home / 'skills' / bundle.name
                    if not target.exists():
                        with scanned_bundle(bundle) as (staged, scan):
                            ui.show(f'Skill {bundle.name}: scan {scan.verdict}. Security scanning is not scientific validation.')
                            if scan.verdict == 'dangerous':
                                raise ValueError('Security scanner blocked the skill.')
                            if scan.findings:
                                ui.show(str(scan.findings))
                                ui.choose('Accept these skill findings?', ['Accept findings', 'Cancel'])
                            _, state = save_reviewed(bundle, staged, scan)
                            if not state.startswith('Enabled.'):
                                raise ValueError(state)
                    elif {p: v.encode() if isinstance(v, str) else v for p, v in folder_bundle(target).files.items()} != {p: v.encode() if isinstance(v, str) else v for p, v in bundle.files.items()}:
                        raise ValueError('A retained skill differs from this prepared package; no overwrite.')
                private_skills.add(bundle.name)
                skills.add(bundle.name)
            except (ValueError, OSError, UnicodeError) as exc:
                missing.append('Skill ' + spec['id'] + ': ' + str(exc))
        else:
            with capability_scope(home) if spec['id'] in private_skills else nullcontext():
                value = json.loads(skill_view(spec['id'], preprocess=False, allow_setup=False))
            if not value.get('success'):
                missing.append('Existing skill unavailable: ' + spec['id'])
            elif spec.get('sha256') and sha256(value.get('content', '').encode()).hexdigest() != spec['sha256']:
                missing.append('Existing skill revision mismatch: ' + spec['id'])
            else:
                skills.add(spec['id'])
    for skill_name in tuple(private_skills):
        with capability_scope(home):
            found = json.loads(skill_view(skill_name, preprocess=False, allow_setup=False))
        if not found.get('success'):
            private_skills.remove(skill_name)
            skills.discard(skill_name)
            missing.append('Private dependency skill unavailable: ' + skill_name)
    from sci_cli.tools_config import _get_platform_tools
    import model_tools
    from tools.delegate_tool_results import _CHILD_CONSTRUCTION_LOCK
    owner_cfg = read_user_config_raw(owner / 'config.yaml')
    with _CHILD_CONSTRUCTION_LOCK:
        previous_names = list(model_tools._last_resolved_tool_names)
        try:
            owner_names = {t['function']['name'] for t in model_tools.get_tool_definitions(
                sorted(_get_platform_tools(owner_cfg, 'cli', include_default_mcp_servers=False)),
                disabled_toolsets=owner_cfg.get('agent', {}).get('disabled_toolsets', []), quiet_mode=True, skip_tool_search_assembly=True)}
        finally:
            model_tools._last_resolved_tool_names = previous_names
    ready_private = {t['function']['name'] for t in private_definitions(item)}
    missing.extend('Private dependency tool unavailable/not authorized: ' + tool for tool in sorted(private_tools - ready_private))
    tools = set(private_tools) & ready_private
    for name_ref in manifest['tools']:
        if name_ref.startswith('mcp:'):
            alias, _, raw = name_ref[4:].partition('/')
            actual = bindings.get(f'tool.{alias}.{raw}')
        else:
            actual = name_ref
        if actual and (actual in owner_names or actual in tools):
            tools.add(actual)
        else:
            missing.append('Required tool unavailable/not authorized: ' + name_ref)
    try:
        instructions = _render(files[manifest['instructions']].decode(), bindings)
    except ValueError as exc:
        instructions = 'Setup required. The retained package contains unresolved requirements.'
        missing.append(str(exc))
    item = replace(item, instructions=instructions, output=manifest['output'], skills=tuple(sorted(skills | private_skills)),
                   private_skills=tuple(sorted(private_skills)), tools=tuple(sorted(tools)), private_tools=tuple(sorted(tools & private_tools)),
                   shared_tools=tuple(sorted(tools & private_tools & owner_names & DEFAULT_TOOLS)),
                   skill_files=tuple(sorted(ref for ref in set(manifest.get('skill_files', [])) | set(module_files)
                                            if ref.partition('#')[0] in skills | private_skills)))
    for reference in manifest['references']:
        source_path = str(package_root / reference['path']) if 'path' in reference else reference['url']
        ui.show(f'Reference: {reference["label"]}; license/source permission: {reference["license"]}; location: {source_path}')
        choice = ui.choose('Allow this resource to be read and relevant contents sent to the selected model?', ['Approve resource', 'Skip resource', 'Cancel'])
        if choice != 'Approve resource':
            if reference.get('required'):
                missing.append('Required reference not approved: ' + reference['label'])
            continue
        if reference.get('mode') == 'original':
            doc = {'source': source_path, 'label': reference['label'], 'text': 'Approved original resource at ' + source_path + '; contents not preloaded.'}
            item = replace(item, sources=(*item.sources, source_path), source_documents=(*item.source_documents, doc))
        else:
            from agent.specialist_sources import load_reference
            try:
                docs = load_reference(source_path)
                item = replace(item, sources=(*item.sources, source_path), source_documents=(*item.source_documents, *docs))
            except (ValueError, OSError) as exc:
                missing.append('Reference unavailable: ' + str(exc))
    if sum(len(doc['text']) for doc in item.source_documents) > 40_000 or len(item.source_documents) > 20:
        from agent.specialist_source_library import store_library
        item = replace(item, source_manifest=store_library(item.source_documents), source_documents=())
    state = 'setup_required' if missing else 'ready'
    info = {'id': manifest['id'], 'version': manifest['version'], 'digest': digest, 'source': source,
            'state': state, 'resolved': resolved, 'missing': missing}
    item = replace(item, enabled=not missing, needs_review=bool(missing), package_info=info,
                   extension_revision=fingerprint(home))
    item.package_info['definition_digest'] = definition_digest(item)
    ui.show(f'[Package] {state}: {item.name}\nSkills: {", ".join(item.skills)}\nTools: {", ".join(item.tools)}\n'
            + ('Missing: ' + '; '.join(missing) if missing else 'Required local setup/permission checks passed; scientific correctness is not certified.'))
    final = 'Save disabled; setup required' if missing else 'Save and enable for the next conversation'
    ui.choose('Publish this reviewed local definition?', [final, 'Cancel'])
    saved = save(item, expected_revision=previous.revision if previous else None)
    ui.show(f'Installed {saved.name}: {owner / "subagents" / (saved.name + ".json")}. '
            + ('Disabled. Setup required; retry package installation to finish.' if missing else 'Enabled. Available in your next conversation; use /new.'))
    return saved
