"""Bounded image previews for terminal chat, independent of vision providers."""

import hashlib
import io
import re
from pathlib import Path

MAX_IMAGE_BYTES = 8_000_000
MAX_IMAGE_PIXELS = 32_000_000


# Older reaction-draw replies identified the deliverable with a labelled file row.
_FIGURE_LINE = re.compile(
    r"^(?:[-*]\s+)?Figure:\s+(.+?\.(?:png|jpe?g|gif|bmp|webp))(?:\s+\(also [^()]*\))?$",
    re.IGNORECASE,
)


def media_references(text: str):
    for line in text.splitlines():
        line = line.strip().strip(chr(96) + "\"'")
        if line.startswith("MEDIA:"):
            yield line[6:].strip().strip(chr(96) + "\"'")
        elif match := _FIGURE_LINE.fullmatch(line):
            path = match.group(1)
            if Path(path).is_absolute():
                yield path


def image_is_referenced(history: list, path: str) -> bool:
    """Only preview explicit media from this conversation, never arbitrary client paths."""
    for message in history:
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        parts = [content] if isinstance(content, str) else [
            part.get("text", "") for part in (content or []) if isinstance(part, dict)
        ]
        for text in parts:
            if path in media_references(text):
                return True
    return False


def decode_image_preview(data: bytes, *, graphics: bool = False):
    from PIL import Image, UnidentifiedImageError

    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the preview size limit")
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image exceeds the preview pixel limit")
            source.thumbnail((4096, 4096) if graphics else (1920, 1152), Image.Resampling.LANCZOS)
            return source.convert("RGBA")
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("Unsupported image preview") from exc


def image_preview(data: bytes, *, cols: int, graphics: bool = False) -> dict:
    from PIL import Image
    from agent.pet.render import (
        _downscale_cells, _encode_kitty_virtual, kitty_color_hex, kitty_placeholder_rows,
    )

    frame = decode_image_preview(data, graphics=graphics)
    cols = max(4, min(cols, 160))
    # A terminal cell is approximately twice as tall as it is wide. Bound
    # portrait figures too, so a single image cannot consume the transcript.
    max_rows = 72 if graphics else 36
    cols = max(4, min(cols, int(2 * max_rows * frame.width / frame.height)))
    rows = max(1, min(max_rows, round(cols * frame.height / frame.width / 2)))
    if graphics:
        image_id = 0x800000 | (int.from_bytes(hashlib.sha256(data).digest()[:3]) & 0x7FFFFF)
        return {"ok": True, "graphics": "kitty", "imageId": image_id,
                "color": kitty_color_hex(image_id),
                "placeholder": kitty_placeholder_rows(cols, rows),
                "transmit": _encode_kitty_virtual(frame, image_id=image_id, cols=cols, rows=rows)}
    # Reuse the tested truecolor half-block representation, with alpha composited
    # against white so black chemical bonds remain visible on dark terminal themes.
    background = Image.new("RGBA", frame.size, "white")
    background.alpha_composite(frame)
    grid = _downscale_cells(background, target_cols=cols)
    return {"ok": True, "graphics": "unicode",
            "grid": [[list(top) + list(bottom) for top, bottom in row] for row in grid[:36]]}


def read_image_preview(path: str, *, cols: int, graphics: bool = False) -> dict:
    return image_preview(read_image_bytes(path), cols=cols, graphics=graphics)


def read_image_bytes(path: str) -> bytes:
    """Use the same profile-scoped local/remote filesystem policy as file downloads."""
    from sci_cli.web_routers.files import _fs_regular_file, _is_sensitive_path
    from sci_cli.config import load_config
    from sci_constants import get_sci_home
    from sci_cli.ssh_workspace_fs import get_ssh_workspace_fs
    from agent.secret_scope import get_secret

    if not Path(path).is_absolute() or _is_sensitive_path(Path(path)):
        raise ValueError("Image path is not available for preview")
    # The HTTP adapter's _fs_backend(None) re-enters the serving profile. This
    # RPC already owns a session scope, so resolve its config without re-scoping.
    terminal = dict(load_config().get("terminal") or {})
    kind = str(terminal.get("backend") or "local").lower()
    if kind not in {"local", "ssh"}:
        raise ValueError("This terminal backend has no image preview reader")
    if kind == "ssh":
        for key in ("host", "user", "port", "key"):
            name = "ssh_" + key
            if not terminal.get(name):
                terminal[name] = get_secret("TERMINAL_SSH_" + key.upper())
    backend = get_ssh_workspace_fs(str(get_sci_home()), terminal)
    if backend is not None:
        data, _size, target = backend.read_bytes(path, max_bytes=MAX_IMAGE_BYTES)
        if _is_sensitive_path(Path(target)):
            raise ValueError("Image path is not available for preview")
    else:
        target, stat = _fs_regular_file(Path(path))
        if stat.st_size > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds the preview size limit")
        with target.open("rb") as stream:
            data = stream.read(MAX_IMAGE_BYTES + 1)
    return data
