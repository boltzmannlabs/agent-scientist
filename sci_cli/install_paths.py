"""Persistent shell PATH registration for source installers, after PM bootstrap."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import stat
import tempfile

_BEGIN = '# >>> Agent Scientist PATH >>>'
_END = '# <<< Agent Scientist PATH <<<'


def _write_shell_block(path: Path, block: str) -> None:
    # Follow a user's dotfile symlink instead of replacing the link itself.
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    start, end = original.find(_BEGIN), original.find(_END)
    if (start < 0) != (end < 0) or (start >= 0 and end < start):
        raise ValueError(f'Incomplete SCI PATH block in {path}; repair the marked block and retry.')
    if start >= 0:
        updated = original[:start] + block + original[end + len(_END):]
    else:
        updated = original + ('\n' if original and not original.endswith('\n') else '') + block + '\n'
    if updated == original:
        return
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix='.sci-path-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def register_shell_paths(bin_dir: Path, *, home: Path, shell: str,
                         zdotdir: Path | None = None, config_home: Path | None = None) -> list[Path]:
    """Register login and interactive shells without shadowing existing login files."""
    name = Path(shell).name
    quoted = shlex.quote(str(bin_dir.resolve()))
    if name == 'fish':
        paths = [(config_home or home / '.config') / 'fish/conf.d/agent-scientist.fish']
        body = f'if not contains -- {quoted} $PATH\n    set -gx PATH {quoted} $PATH\nend'
    elif name in {'bash', 'sh', 'dash', ''}:
        login = next((home / name for name in ('.bash_profile', '.bash_login', '.profile')
                      if (home / name).exists()), home / '.profile')
        paths = [home / '.bashrc', login] if name in {'bash', ''} else [home / '.profile']
        body = f'case ":$PATH:" in\n    *:{quoted}:*) ;;\n    *) export PATH={quoted}:"$PATH" ;;\nesac'
    elif name == 'zsh':
        root = zdotdir or home
        paths = [root / '.zprofile', root / '.zshrc']
        body = f'case ":$PATH:" in\n    *:{quoted}:*) ;;\n    *) export PATH={quoted}:"$PATH" ;;\nesac'
    else:
        raise ValueError(f'Automatic PATH setup does not support shell {shell!r}. '
                         f'Add {bin_dir} to your shell PATH, or select Bash, Zsh or Fish and rerun setup.')
    block = f'{_BEGIN}\n{body}\n{_END}'
    for path in paths:
        _write_shell_block(path, block)
    return paths


def register_user_path(bin_dir: Path) -> None:
    if os.name == 'nt':
        from sci_cli._launchers import _register_windows_user_path

        status = _register_windows_user_path(bin_dir)
        print(f'User PATH: {status} ({bin_dir})')
    else:
        paths = register_shell_paths(
            bin_dir, home=Path.home(), shell=os.environ.get('SHELL', ''),
            zdotdir=Path(os.environ['ZDOTDIR']) if os.environ.get('ZDOTDIR') else None,
            config_home=Path(os.environ['XDG_CONFIG_HOME']) if os.environ.get('XDG_CONFIG_HOME') else None,
        )
        print('PATH registered in: ' + ', '.join(map(str, paths)))
