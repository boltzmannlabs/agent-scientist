"""Bounded, inert package trees and ZIPs; checksums are integrity, not publisher trust."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json
import os
import stat
import tempfile
import zipfile

MAX_BYTES = 50 * 1024 * 1024
MAX_FILES = 1000
LOCK = 'files.lock.json'


def relative(name):
    from sci_cli.archive_safe import normalize_archive_parts
    if not isinstance(name, str):
        raise ValueError('Package paths must be strings.')
    parts = normalize_archive_parts(name)
    if '/'.join(parts) != name or '\\' in name or ':' in name:
        raise ValueError(f'Noncanonical package path: {name}')
    return name


def tree(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Select a regular package directory, not a symlink.')
    files, total = {}, 0
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in sorted([*dirs, *names]):
            path = Path(base) / name
            if path.is_symlink():
                raise ValueError(f'Package symlink rejected: {path}')
        for name in sorted(names):
            path = Path(base) / name
            key = relative(path.relative_to(root).as_posix())
            if not path.is_file():
                raise ValueError(f'Package must contain regular files: {key}')
            size = path.stat().st_size
            total += size
            if total > MAX_BYTES or len(files) >= MAX_FILES:
                raise ValueError('Package exceeds 50 MiB or 1,000 files; nothing was truncated.')
            files[key] = path.read_bytes()
    return files


def checksums(files):
    return {name: sha256(data).hexdigest() for name, data in sorted(files.items()) if name != LOCK}


def seal(root):
    from utils import atomic_json_write
    files = tree(root)
    atomic_json_write(Path(root) / LOCK, checksums(files), mode=0o644)


def verify(files):
    try:
        locked = json.loads(files[LOCK])
    except (KeyError, ValueError) as exc:
        raise ValueError('Missing/invalid release integrity lock. Maintainers must rebuild the reviewed release snapshot.') from exc
    if locked != checksums(files):
        raise ValueError('Package content differs from its release integrity lock; restore it or rebuild after review.')


@contextmanager
def open_package(source):
    source = Path(source).expanduser()
    if source.is_symlink():
        raise ValueError('Package source cannot be a symlink.')
    if source.is_dir():
        yield source.resolve()
        return
    if not source.is_file() or source.suffix.lower() != '.zip' or source.stat().st_size > MAX_BYTES:
        raise ValueError('Provide a package directory or ZIP of at most 50 MiB.')
    with tempfile.TemporaryDirectory(prefix='sci-package-review-') as temp:
        destination = Path(temp)
        with zipfile.ZipFile(source) as archive:
            seen, total = set(), 0
            if len(archive.infolist()) > MAX_FILES:
                raise ValueError('ZIP exceeds 1,000 entries.')
            for member in archive.infolist():
                name = member.filename.rstrip('/')
                relative(name)
                mode = member.external_attr >> 16
                if member.flag_bits & 1 or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ValueError('Encrypted ZIPs, links and special files are unsupported.')
                folded = name.casefold()
                if folded in seen:
                    raise ValueError('Duplicate/case-colliding ZIP entry.')
                seen.add(folded)
                total += member.file_size
                if total > MAX_BYTES:
                    raise ValueError('Expanded ZIP exceeds 50 MiB.')
                target = destination / name
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as stream:
                        data = stream.read(MAX_BYTES + 1)
                    if len(data) != member.file_size:
                        raise ValueError('ZIP size mismatch.')
                    target.write_bytes(data)
        yield destination


def digest(files):
    return sha256(json.dumps(checksums(files), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
