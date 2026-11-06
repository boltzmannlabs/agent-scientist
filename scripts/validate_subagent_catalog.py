#!/usr/bin/env python3
"""Inert package validation/snapshot build. Never execute contributor fixtures or contact services."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None):
    from sci_cli.subagent_package_schema import validate
    from sci_cli.subagent_package_catalog import CATALOG, SNAPSHOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-snapshot', action='store_true')
    parser.add_argument('--promotion', action='store_true', help='Check integrated dev evidence for changed packages before main')
    parser.add_argument('--check-snapshot', action='store_true', help='Require release snapshot freshness (main promotion/release)')
    parser.add_argument('--base', help='Reviewed base Git commit (full SHA) for immutable-version checks')
    args = parser.parse_args(argv)
    if args.write_snapshot and args.check_snapshot:
        parser.error('Choose --write-snapshot or --check-snapshot.')
    if args.promotion and not args.base:
        parser.error('--promotion requires --base.')
    if args.base:
        import re
        if not re.fullmatch('[0-9a-f]{40}', args.base):
            raise ValueError('--base must be a full Git commit SHA.')
        subprocess.run(['git', 'cat-file', '-e', args.base + '^{commit}'], cwd=ROOT, check=True, capture_output=True)
    snapshot = {}
    for folder in sorted(CATALOG.iterdir()):
        if not folder.is_dir():
            continue
        manifest, files, digest = validate(folder)
        key = manifest['id']
        if folder.name != key or key in snapshot:
            raise ValueError('Catalog directory must match unique package ID: ' + key)
        changed = True
        if args.base:
            from packaging.version import Version
            import sci_yaml as yaml
            relative = folder.relative_to(ROOT).as_posix()
            old = subprocess.run(['git', 'show', args.base + ':' + relative + '/manifest.yaml'], capture_output=True, cwd=ROOT)
            diff = subprocess.run(['git', 'diff', '--exit-code', args.base, '--', relative], capture_output=True, cwd=ROOT)
            if diff.returncode not in (0, 1):
                raise ValueError('Cannot compare package with the PR base: ' + key)
            changed = bool(diff.returncode)
            if old.returncode == 0:
                previous = yaml.safe_load(old.stdout)
                runtime_diff = subprocess.run(['git', 'diff', '--exit-code', args.base, '--', relative,
                    ':(exclude)' + relative + '/tests/validation.json', ':(exclude)' + relative + '/files.lock.json'], capture_output=True, cwd=ROOT)
                if runtime_diff.returncode not in (0, 1):
                    raise ValueError('Cannot compare package contents: ' + key)
                if Version(manifest['version']) < Version(previous['version']) or (runtime_diff.returncode and manifest['version'] == previous['version']):
                    raise ValueError('Changed published packages require a higher version: ' + key)
        from sci_cli.subagent_package_review import evidence
        if changed:
            evidence(folder, manifest, repo=ROOT if args.promotion else None)
        from sci_cli.subagent_package_io import LOCK, checksums
        files[LOCK] = (json.dumps(checksums(files), sort_keys=True, indent=2) + '\n').encode()
        snapshot[key] = {'manifest': manifest, 'digest': digest,
                         'files': {name: base64.b64encode(data).decode() for name, data in sorted(files.items())}}
        print(f'VALID {key} {manifest["version"]}: {len(files)} files; no code executed')
    content = json.dumps(snapshot, sort_keys=True, indent=2) + '\n'
    if args.write_snapshot:
        SNAPSHOT.write_text(content, encoding='utf-8')
    elif args.check_snapshot and (not SNAPSHOT.exists() or SNAPSHOT.read_text(encoding='utf-8') != content):
        raise ValueError('Packaged catalog snapshot is stale. Run with --write-snapshot after review.')
    print('Source packages validated. ' + ('Release snapshot checked/generated. ' if args.check_snapshot or args.write_snapshot else 'Snapshot generation belongs to maintainer promotion. ') + 'Fixtures require separate reviewed execution tests.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
