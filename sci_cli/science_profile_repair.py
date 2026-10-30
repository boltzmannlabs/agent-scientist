"""Explicit in-place review for restricted profiles; never converts their isolation."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile

from sci_cli.science_profiles import MANIFEST, config_digest, read_spec
from sci_cli.science_profile_approval import approval_record, changed_fields
from sci_cli.science_profiles_sandbox import validate_sandbox
from sci_cli.skill_add import Cancelled


def repair_candidate(home, spec, config):
    """Relocate only the recorded private workspace/copied sources, with review."""
    config = deepcopy(config)
    changes = []
    volumes = config.get('terminal', {}).get('docker_volumes', [])
    workspace = f'{home / "workspace"}:/workspace:rw'
    old_home = None
    if volumes and volumes[0] != workspace:
        suffix = ':/workspace:rw'
        if not isinstance(volumes[0], str) or not volumes[0].endswith(suffix):
            raise ValueError('Unexpected workspace mount; repair cannot infer a replacement.')
        old_workspace = Path(volumes[0][:-len(suffix)])
        if old_workspace.name != 'workspace' or old_workspace.parent.name != spec.name:
            raise ValueError('Workspace does not belong to the recorded profile; review its configuration manually.')
        old_home = old_workspace.parent
        old_mount = volumes[0]
        config['terminal']['docker_volumes'][0] = workspace
        changes.append(f'Workspace mount: {old_mount} → {workspace}')
    if spec.name != home.name:
        changes.append(f'Profile identity: {spec.name} → {home.name}')
        spec = replace(spec, name=home.name)
    sources = list(spec.sources)
    if old_home:
        for i, source in enumerate(sources):
            if source.location.startswith('https://'):
                continue
            path = Path(source.location)
            if not path.is_relative_to(old_home / 'sources'):
                continue
            target = home / path.relative_to(old_home)
            if not target.exists() or target.is_symlink() or target.resolve() != target.absolute():
                raise ValueError('A copied source is missing or linked after relocation; restore it before repair.')
            sources[i] = replace(source, location=str(target))
            old_mount, new_mount = f'{path}:/sources/{i}:ro', f'{target}:/sources/{i}:ro'
            config['terminal']['docker_volumes'] = [new_mount if v == old_mount else v for v in
                                                    config['terminal']['docker_volumes']]
            changes.append(f'Copied source: {path} → {target}')
    spec = replace(spec, sources=sources)
    validate_sandbox(home, spec, config, check_image=False)
    return spec, config, changes


def _masked_config(value):
    """Mask named secret containers before applying the shared text redactor."""
    if isinstance(value, dict):
        return {key: ('[hidden]' if any(word in str(key).lower() for word in
                     ('key', 'token', 'secret', 'password', 'authorization', 'header', 'credential', 'env'))
                     else _masked_config(child)) for key, child in value.items()}
    if isinstance(value, list):
        return [_masked_config(item) for item in value]
    return value


def save_repair(home, original_config, original_manifest, config, spec, *, cancelled):
    from sci_cli.config import atomic_config_replace, read_user_config_raw, _CONFIG_LOCK
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.plugins_state import _locked_plugin_state
    from utils import atomic_json_write
    path = home / 'config.yaml'
    manifest = home / MANIFEST
    with profile_scope(home), _locked_plugin_state(path), _CONFIG_LOCK:
        if cancelled():
            raise Cancelled()
        if path.read_bytes() != original_config or manifest.read_bytes() != original_manifest:
            raise ValueError('Profile settings changed during review. Nothing overwritten; review again.')
        # A review never exempts a missing image, changed mount or expanded grant.
        validate_sandbox(home, spec, config)
        if cancelled():
            raise Cancelled()
        if path.read_bytes() != original_config or manifest.read_bytes() != original_manifest:
            raise ValueError('Profile settings changed during review. Nothing overwritten; review again.')
        backups = home / 'backups'
        if backups.is_symlink():
            raise ValueError('Profile backup directory is a symlink; no settings saved.')
        backups.mkdir(mode=0o700, exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix='profile-compatibility-', dir=backups))
        for name, data in (('config.yaml', original_config), (MANIFEST, original_manifest)):
            # The directory is private from creation; preserve the exact original bytes.
            with (backup / name).open('xb') as output:
                output.write(data)
            (backup / name).chmod(0o600)
        payload = json.loads(original_manifest)
        payload.update(name=spec.name, sources=[{'location': s.location, 'mode': s.mode} for s in spec.sources],
                       config_digest=config_digest(config), config_review=approval_record(config))
        if read_user_config_raw(path) != config:
            atomic_config_replace(path, config)
        written_config = path.read_bytes()
        try:
            atomic_json_write(manifest, payload, mode=0o600)
        except OSError as exc:
            state = 'Configuration may remain changed.'
            if path.read_bytes() == written_config and manifest.read_bytes() == original_manifest:
                try:
                    if written_config != original_config:
                        atomic_config_replace(path, read_user_config_raw(backup / 'config.yaml'))
                    state = 'Original configuration settings retained.'
                except OSError:
                    state = 'Configuration restore also failed.'
            raise RuntimeError(f'Approval could not be saved. {state} No new approval was recorded. '
                               f'Original files are in {backup}.') from exc
    return backup


def review_repair(cli, home, ui):
    from sci_cli.config import read_user_config_raw
    from sci_cli.native_profile_services import progress
    from agent.redact import redact_sensitive_text
    if getattr(cli, '_agent_running', False):
        raise ValueError('Finish or cancel the current turn before reviewing this profile.')
    original_config = (home / 'config.yaml').read_bytes()
    original_manifest = (home / MANIFEST).read_bytes()
    original_spec = read_spec(home)
    original = read_user_config_raw(home / 'config.yaml')
    changes = changed_fields(original_spec, original)
    spec, config, relocation = repair_candidate(home, original_spec, original)
    if not original_spec.config_review:
        reason = ('This profile has an older whole-configuration approval. Prior field values are unavailable; '
                  'review the current configuration once to upgrade its approval record.')
    else:
        reason = 'Changed protected fields: ' + (', '.join(changes) or 'none') + '.'
    ui.show(f'Review restricted profile {home.name}\n{reason}\n' + '\n'.join(relocation) +
            '\nCurrent configuration (credentials hidden):\n' +
            redact_sensitive_text(json.dumps(_masked_config(config), indent=2), force=True) +
            '\nThis keeps the same profile, history, memory, persona, credentials, skills and access restrictions. '
            'Only reviewed relocation paths and the approval record are saved. '
            'Local execution remains unavailable while setup is pending. '
            'No model request, download, service probe or scientific job is performed. '
            'For prepared profiles, saving checks the existing Docker image without starting a container. '
            'Changed settings require a fresh conversation after restarting SCI.')
    if ui.choose('Save reviewed settings and repair this profile?',
                 ['Approve profile repair', 'Cancel']) != 'Approve profile repair':
        raise Cancelled()
    cancel = lambda: bool(getattr(cli, '_science_cancel', None) and cli._science_cancel.is_set())
    with progress(ui, 'Validating and saving profile approval'):
        backup = save_repair(home, original_config, original_manifest, config, spec, cancelled=cancel)
    ui.show(f'Saved profile {home.name}. Backup: {backup}. '
            'Restart SCI and start a new conversation to use changed settings. '
            'The current conversation is unchanged; tool and sandbox restrictions are retained.')
