"""Profile-local saved specialists. Definitions are data; reading never executes code."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from sci_constants import get_sci_home, mkdir_under_sci_home
from utils import atomic_json_write

_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_MAX_BYTES = 256_000


@dataclass(frozen=True)
class Specialist:
    name: str
    purpose: str
    instructions: str = ""
    output: str = "A concise answer with evidence, limitations and output artifact paths."
    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    skill_files: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    children: tuple[str, ...] = ()
    automatic: bool = False
    enabled: bool = True
    needs_review: bool = False
    max_iterations: int = 30
    timeout_seconds: int = 900
    revision: str = field(default_factory=lambda: uuid4().hex)
    version: int = 1

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or set(raw) - set(cls.__dataclass_fields__):
            raise ValueError("Invalid specialist definition: unknown fields or non-object input.")
        data = dict(raw)
        for key in ("tools", "skills", "skill_files", "sources", "children"):
            values = data.get(key, [])
            if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"{key} must contain non-empty names/references.")
            data[key] = tuple(dict.fromkeys(values))
        try:
            item = cls(**data)
        except TypeError as exc:
            raise ValueError("A specialist needs a name and purpose.") from exc
        validate_name(item.name)
        for reference in item.skill_files:
            skill, sep, path = reference.partition("#")
            parts = path.replace("\\", "/").split("/")
            if not sep or skill not in item.skills or not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts) or ":" in path:
                raise ValueError("Skill modules must reference a selected skill and a safe relative file path.")
        if type(item.version) is not int or item.version != 1:
            raise ValueError("Unsupported specialist version; update SCI before editing it.")
        for key in ("purpose", "instructions", "output", "revision"):
            value = getattr(item, key)
            if not isinstance(value, str) or (key != "instructions" and not value.strip()):
                raise ValueError(f"{key} must be text and cannot be empty.")
        for key in ("automatic", "enabled", "needs_review"):
            if type(getattr(item, key)) is not bool:
                raise ValueError(f"{key} must be true or false.")
        for key in ("max_iterations", "timeout_seconds"):
            if type(getattr(item, key)) is not int or getattr(item, key) < 1:
                raise ValueError(f"{key} must be a positive whole number.")
        for child in item.children:
            validate_name(child)
            if child == item.name:
                raise ValueError("A specialist cannot delegate to itself.")
        if len(json.dumps(asdict(item)).encode()) > _MAX_BYTES:
            raise ValueError("Specialist definition exceeds 256 KB; use smaller instructions and references.")
        return item


def validate_name(name):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("Use 1–64 lowercase letters, numbers, hyphens or underscores for the name.")


def definition_dir(home=None):
    return Path(home if home is not None else get_sci_home()) / "subagents"


def _path(name, home=None):
    validate_name(name)
    directory = definition_dir(home)
    path = directory / f"{name}.json"
    if directory.is_symlink() or path.is_symlink():
        raise ValueError("Specialist definitions must not be symbolic links.")
    return path


def load(name, home=None):
    path = _path(name, home)
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError(f"{name}: definition exceeds 256 KB.")
    item = Specialist.parse(json.loads(path.read_text(encoding="utf-8-sig")))
    if item.name != name:
        raise ValueError(f"{name}: filename and saved name disagree.")
    return item


def inventory(home=None):
    directory = definition_dir(home)
    if directory.is_symlink():
        raise ValueError("Specialist directory must not be a symbolic link.")
    items, errors = {}, []
    for path in sorted(directory.glob("*.json")):
        try:
            item = load(path.stem, home)
            items[item.name] = item
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
    return items, errors


def save(item, home=None, *, expected_revision=None):
    """Create exclusively, or compare-and-swap a reviewed update. Never overwrite a conflict."""
    from sci_cli.auth import _file_lock
    item = Specialist.parse(asdict(item))
    path = _path(item.name, home)
    mkdir_under_sci_home(path.parent)
    with _file_lock(path.parent / ".definitions.lock", threading.local(), 10, "Specialist definitions are busy; retry."):
        if path.exists():
            current = load(item.name, home)
            if expected_revision is None:
                raise FileExistsError(f"{item.name} already exists. Choose another name or edit it explicitly.")
            if current.revision != expected_revision:
                raise ValueError("This specialist changed during review. Reopen it before saving.")
        elif expected_revision is not None:
            raise ValueError("This specialist was deleted during review; no replacement was saved.")
        item = replace(item, revision=uuid4().hex)
        atomic_json_write(path, asdict(item), mode=0o600)
    return item


def delete(name, home=None, *, expected_revision):
    from sci_cli.auth import _file_lock
    path = _path(name, home)
    with _file_lock(path.parent / ".definitions.lock", threading.local(), 10, "Specialist definitions are busy; retry."):
        if load(name, home).revision != expected_revision:
            raise ValueError("Specialist changed; review it again before deleting.")
        path.unlink()


def copy_to(item, destination_home, name=None):
    # Destination review resolves capabilities in THAT profile. Never copy private source grants or children.
    return save(replace(item, name=name or item.name, sources=(), children=(), automatic=False,
                        enabled=False, needs_review=True), destination_home)
