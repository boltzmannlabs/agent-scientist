"""Preflight rejects unavailable prerequisites before touching the managed runtime."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / 'scripts/source-install-preflight.sh'


@pytest.mark.platforms('posix')
@pytest.mark.parametrize('approve', [False, True])
def test_missing_package_requires_consent_then_rechecks(tmp_path, approve):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    for tool in ('git', 'tar', 'awk', 'sha256sum', 'shasum', 'mkdir', 'mktemp', 'rm', 'df'):
        found = shutil.which(tool)
        if found:
            (binaries / tool).symlink_to(found)
    calls = tmp_path / 'packages'
    (binaries / 'id').write_text('#!/bin/sh\necho 0\n')
    (binaries / 'apt-get').write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$PACKAGE_LOG"\n'
        'if [ "$1" = install ]; then printf "#!/bin/sh\\nexit 0\\n" > "$BIN_DIR/curl"; /bin/chmod +x "$BIN_DIR/curl"; fi\n')
    for tool in ('id', 'apt-get'):
        (binaries / tool).chmod(0o755)
    home = tmp_path / 'home'
    home.mkdir()
    env = {**os.environ, 'PATH': str(binaries), 'HOME': str(home),
           'SCI_HOME': str(home / '.sci'), 'SCI_RUNTIME_DIR': str(home / 'runtime'),
           'BIN_DIR': str(binaries), 'PACKAGE_LOG': str(calls)}
    script = 'source "$1"; sci_install_prerequisites="$2"; SCRIPT_DIR="$3"; sci_source_preflight'
    result = subprocess.run(['/bin/bash', '-c', script, 'bash', str(HELPER),
                             str(approve).lower(), str(home)], env=env, text=True,
                            capture_output=True, timeout=20)
    if approve:
        assert result.returncode == 0, result.stdout + result.stderr
        assert calls.read_text().splitlines() == ['update', 'install -y curl']
        assert 'OS prerequisites passed' in result.stdout
    else:
        assert result.returncode != 0 and 'Missing prerequisites: curl' in result.stderr
        assert not calls.exists() and not (home / 'runtime').exists()


@pytest.mark.platforms('posix')
def test_low_disk_space_is_rejected_before_runtime_install(tmp_path):
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    (binaries / 'df').write_text('#!/bin/sh\nprintf "Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 999 990 9 99%% /\\n"\n')
    (binaries / 'df').chmod(0o755)
    env = {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH']}
    result = subprocess.run(['/bin/bash', '-c', 'source "$1"; sci_check_install_directory "$2"',
                             'bash', str(HELPER), str(tmp_path / 'destination')],
                            env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode != 0 and 'Insufficient disk space' in result.stderr
    assert not list((tmp_path / 'destination').glob('.sci-write-check-*'))
