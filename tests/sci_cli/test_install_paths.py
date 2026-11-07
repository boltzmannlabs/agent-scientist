"""Source installers persist PATH for the user's actual shell without losing dotfiles."""
import os
from pathlib import Path
import subprocess

import pytest

from sci_cli.install_paths import register_shell_paths


@pytest.mark.platforms('posix')
@pytest.mark.parametrize('shell', ['bash', 'zsh', 'fish', 'sh'])
def test_shell_registration_preserves_files_and_is_idempotent(tmp_path, shell):
    home = tmp_path / 'home'
    home.mkdir()
    original = '# User settings\nexport USER_SETTING=preserved\n'
    (home / '.profile').write_text(original)
    bin_dir = home / "bin with 'quote and spaces"
    paths = register_shell_paths(bin_dir, home=home, shell='/bin/' + shell)
    before = {p: p.read_bytes() for p in paths}
    register_shell_paths(bin_dir, home=home, shell='/bin/' + shell)
    assert {p: p.read_bytes() for p in paths} == before
    assert (home / '.profile').read_text().startswith(original)
    assert not (home / '.bash_profile').exists()  # Do not hide the user's .profile.
    if shell in {'bash', 'sh'}:
        command = '. "$1"; . "$1"; printf "%s" "$PATH"'
        env = {**os.environ, 'HOME': str(home), 'PATH': '/usr/bin:/bin'}
        result = subprocess.run(['/bin/sh', '-c', command, 'sh', str(paths[0])],
                                env=env, text=True, capture_output=True, check=True)
        assert result.stdout.split(':').count(str(bin_dir)) == 1


@pytest.mark.platforms('posix')
def test_symlink_and_partial_block_are_preserved(tmp_path):
    target = tmp_path / 'managed-bashrc'
    target.write_text('# Keep me\n')
    link = tmp_path / '.bashrc'
    link.symlink_to(target)
    register_shell_paths(tmp_path / 'bin', home=tmp_path, shell='bash')
    assert link.is_symlink() and target.read_text().startswith('# Keep me\n')
    target.write_text('# >>> Agent Scientist PATH >>>\nincomplete\n')
    before = target.read_bytes()
    with pytest.raises(ValueError, match='Incomplete SCI PATH block'):
        register_shell_paths(tmp_path / 'bin', home=tmp_path, shell='bash')
    assert target.read_bytes() == before


@pytest.mark.platforms('posix')
@pytest.mark.parametrize('shell', ['zsh', 'fish'])
def test_custom_shell_configuration_directory(tmp_path, shell):
    custom = tmp_path / 'custom configuration'
    paths = register_shell_paths(tmp_path / 'bin', home=tmp_path / 'home', shell=shell,
                                 zdotdir=custom, config_home=custom)
    assert paths and all(path.is_relative_to(custom) for path in paths)
    assert not (tmp_path / 'home').exists()


@pytest.mark.platforms('windows')
def test_windows_registration_preserves_existing_path_and_value_type(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import sys
    from types import SimpleNamespace

    from sci_cli import _launchers
    from sci_cli.install_paths import register_user_path

    state = {'value': r'%USERPROFILE%\other-tools;C:\Existing', 'kind': 2, 'writes': 0}

    def set_value(key, name, reserved, kind, value):
        state.update(value=value, kind=kind, writes=state['writes'] + 1)

    registry = SimpleNamespace(
        HKEY_CURRENT_USER=object(), KEY_QUERY_VALUE=1, KEY_SET_VALUE=2,
        REG_SZ=1, REG_EXPAND_SZ=2,
        OpenKey=lambda *args: nullcontext(object()),
        QueryValueEx=lambda *args: (state['value'], state['kind']),
        SetValueEx=set_value,
    )
    monkeypatch.setitem(sys.modules, 'winreg', registry)
    monkeypatch.setattr(_launchers, '_broadcast_environment_change', lambda: None)
    directory = tmp_path / 'SCI commands'
    register_user_path(directory)
    register_user_path(directory)
    assert state['value'] == str(directory) + r';%USERPROFILE%\other-tools;C:\Existing'
    assert state['kind'] == registry.REG_EXPAND_SZ and state['writes'] == 1
