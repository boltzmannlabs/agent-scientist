"""Reviewed catalog discovery; installed choices and credentials are never synchronized implicitly."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import json

from sci_cli.subagent_package_schema import validate
from sci_cli.subagent_package_io import relative

CATALOG = Path(__file__).resolve().parent.parent / 'subagent-catalog'
SNAPSHOT = Path(__file__).parent / 'data' / 'subagent_catalog.json'


def catalog():
    if CATALOG.is_dir():
        rows = {}
        for folder in sorted(CATALOG.iterdir()):
            if folder.is_dir() and (folder / 'manifest.yaml').is_file():
                manifest, _, digest = validate(folder)
                if manifest['id'] in rows:
                    raise ValueError('Duplicate catalog ID: ' + manifest['id'])
                rows[manifest['id']] = {'manifest': manifest, 'digest': digest, 'path': str(folder)}
        from sci_cli.subagent_package_graph import resolve_graph
        resolve_graph(rows)
        return rows
    if not SNAPSHOT.exists():
        return {}
    data = json.loads(SNAPSHOT.read_text(encoding='utf-8-sig'))
    rows = {key: {'manifest': row['manifest'], 'digest': row['digest']} for key, row in data.items()}
    from sci_cli.subagent_package_graph import resolve_graph
    resolve_graph(rows)
    return rows


@contextmanager
def package(package_id, *, rows=None):
    rows = catalog() if rows is None else rows
    if package_id not in rows:
        raise ValueError('Package is not in this release catalog: ' + package_id)
    row = rows[package_id]
    if 'path' in row:
        root = Path(row['path'])
        manifest, _, digest = validate(root)
        if manifest != row['manifest'] or digest != row['digest']:
            raise ValueError('Package changed after hierarchy review: ' + package_id)
        yield root
        return
    data = json.loads(SNAPSHOT.read_text(encoding='utf-8-sig'))[package_id]
    from sci_cli.subagent_package_io import MAX_BYTES, MAX_FILES
    if len(data['files']) > MAX_FILES:
        raise ValueError('Embedded package exceeds file limit.')
    with TemporaryDirectory(prefix='sci-catalog-') as temp:
        root, size = Path(temp), 0
        for name, encoded in data['files'].items():
            relative(name)
            content = base64.b64decode(encoded, validate=True)
            size += len(content)
            if size > MAX_BYTES:
                raise ValueError('Embedded package exceeds size limit.')
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        manifest, _, digest = validate(root, require_lock=True)
        if manifest != row['manifest'] or digest != row['digest']:
            raise ValueError('Embedded catalog metadata/integrity mismatch.')
        yield root


def updates(ui):
    from agent.specialist_store import inventory
    from packaging.version import Version
    rows = catalog()
    for item in inventory()[0].values():
        info = item.package_info
        if not info:
            continue
        row = rows.get(info['id'])
        state = ('not in this release catalog' if row is None else
                 'update available: ' + row['manifest']['version'] if Version(row['manifest']['version']) > Version(info['version']) else
                 'up to date with this release catalog')
        from sci_cli.subagent_package_graph import installed_problem
        problem = installed_problem(item)
        if problem:
            state = problem
        elif row and row['manifest'].get('children') and installed_problem(item, rows=rows):
            state = 'hierarchy update available; installed definitions unchanged'
        ui.show(f'{item.name}: {info["id"]} {info["version"]}; {state}; {info["state"]}')
    ui.show('Read-only check of this installed release catalog. Update SCI first for a newer catalog; no services were queried.')
