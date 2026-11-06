"""Approved executable discovery/download and separate version probes; no shell bootstrap."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tarfile

from sci_cli.subagent_package_io import MAX_BYTES, MAX_FILES, relative, open_package


def platform_key():
    from sci_platform.host.facts import os_family, native_arch
    system = {'darwin': 'macos', 'win32': 'windows'}.get(os_family(), os_family())
    return system + '-' + native_arch()


def _extract(archive, destination, format):
    if format == 'zip':
        # open_package's archive checks are also suitable for inert binary artifacts.
        with open_package(archive) as root:
            shutil.copytree(root, destination, dirs_exist_ok=True)
    elif format == 'tar.gz':
        from sci_cli.archive_safe import normalize_archive_parts
        with tarfile.open(archive, 'r:gz') as stream:
            members = stream.getmembers()
            if len(members) > MAX_FILES or sum(m.size for m in members) > MAX_BYTES:
                raise ValueError('Program archive exceeds 50 MiB/1,000 files.')
            seen = set()
            for member in members:
                key = '/'.join(normalize_archive_parts(member.name))
                if key.casefold() in seen:
                    raise ValueError('Duplicate program archive entry.')
                seen.add(key.casefold())
                if not member.isfile() and not member.isdir():
                    raise ValueError('Program archive links/special entries rejected.')
                target = destination / key
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(member) as source:
                        target.write_bytes(source.read(MAX_BYTES + 1))


def prepare(dep, home, ui):
    artifacts = [a for a in dep.get('artifacts', []) if a['platform'] in {platform_key(), 'any'}]
    options = ['Use installed executable'] + (['Download verified artifact'] if artifacts else []) + ['Defer setup', 'Cancel']
    choice = ui.choose(f'Program {dep["id"]} {dep["version"]}; platform {platform_key()}', options)
    if choice == 'Defer setup':
        return None
    if choice == 'Use installed executable':
        executable = Path(ui.ask('Installed executable path on this CLI host:').strip('"\'')).expanduser().resolve(strict=True)
        if not executable.is_file():
            raise ValueError('Program must be an existing file.')
    else:
        artifact = artifacts[0]
        ui.show(f'Download: {artifact["url"]}\nSHA-256: {artifact["sha256"]}\n'
                f'Destination: {home / "tools" / dep["id"]}. This does not authorize execution.')
        ui.choose('Approve this software download?', ['Download', 'Cancel'])
        from tools.skills_hub import _guarded_http_stream
        directory = home / 'tools' / dep['id']
        directory.mkdir(parents=True, exist_ok=True)
        suffix = {'zip': '.zip', 'tar.gz': '.tar.gz', 'file': '.bin'}[artifact['format']]
        archive = directory / ('download' + suffix)
        with _guarded_http_stream(artifact['url'], timeout=30) as response:
            if response is None or response.status_code != 200:
                raise ValueError('Guarded program download failed.')
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError('Program download exceeds 50 MiB.')
        if sha256(data).hexdigest() != artifact['sha256']:
            raise ValueError('Downloaded program checksum mismatch; nothing was executed.')
        archive.write_bytes(data)
        payload = directory / 'payload'
        payload.mkdir()
        if artifact['format'] == 'file':
            executable = payload / relative(artifact['executable'])
            executable.parent.mkdir(parents=True, exist_ok=True)
            executable.write_bytes(data)
        else:
            _extract(archive, payload, artifact['format'])
            executable = payload / artifact['executable']
        if not executable.is_file() or executable.is_symlink():
            raise ValueError('Declared executable was not found in the verified archive.')
        executable.chmod(0o700)
    command = [str(executable), *dep['version_args']]
    ui.show('Version verification executes code: ' + repr(command) + f'\nWorking directory: {home / "workspace"}')
    decision = ui.choose('Approve this exact version check?', ['Run version check', 'Defer setup', 'Cancel'])
    if decision == 'Defer setup':
        return None
    # Defer is a real choice, not execution permission.
    # The chooser result is handled below rather than using any implicit approval.
    return verify_program(command, dep, home, ui)


def verify_program(command, dep, home, ui):
    from tools.environments.local import served_profile_child_env
    # Child environment construction uses the owning scoped secret/terminal bridge.
    env = served_profile_child_env()
    result = subprocess.run(command, cwd=home / 'workspace', env=env, capture_output=True, text=True, timeout=15)
    text = result.stdout + result.stderr
    if result.returncode or dep['version_contains'] not in text:
        raise ValueError('Program version check failed or did not match the declared version. No scientific job ran.')
    path = Path(command[0])
    return {'path': str(path), 'version': dep['version'], 'sha256': sha256(path.read_bytes()).hexdigest(),
            'verification': 'version check passed; scientific execution not tested'}
