"""Portable specialist definitions, copied as disabled data until destination review."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import os
from agent.specialist_store import Specialist, load, save, _MAX_BYTES


def export_definition(cli, ui, args):
    if len(args) != 2:
        raise ValueError('Usage: /subagent export <name> "<destination.json>"')
    item = load(args[0])
    path = Path(args[1]).expanduser().absolute()
    ui.show(f'Export to {path}. Instructions and capability names only; credentials, references, child grants and history are excluded. '
            'Review instructions for private content before sharing.')
    ui.choose('Export this definition?', ['Export', 'Cancel'])
    item = replace(item, sources=(), children=(), enabled=False, needs_review=True)
    # Exclusive creation: never overwrite a file or follow a destination symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(asdict(item), stream, indent=2, ensure_ascii=False)
    ui.show(f'Exported {item.name}: {path}. On another server use /subagent import "{path.name}" and review it.')


def import_definition(cli, ui, args):
    if len(args) not in (1, 2):
        raise ValueError('Usage: /subagent import "<definition.json>" [new-name]')
    path = Path(args[0]).expanduser().resolve(strict=True)
    with path.open('rb') as stream:
        payload = stream.read(_MAX_BYTES + 1)
    if len(payload) > _MAX_BYTES:
        raise ValueError('Definition exceeds 256 KB.')
    item = Specialist.parse(json.loads(payload))
    item = replace(item, name=args[1] if len(args) == 2 else item.name, sources=(), children=(),
                   enabled=False, needs_review=True)
    ui.show(f'Import {item.name} from {path} into the current profile as a disabled definition. '
            'No code runs and no credentials or source grants are imported.')
    ui.choose('Import for review?', ['Import', 'Cancel'])
    saved = save(item)
    ui.show(f'Imported {saved.name}, disabled pending /Update_subagent {saved.name}. Existing names are never overwritten.')
