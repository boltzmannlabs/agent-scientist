"""Optional Chafa rendering through the classic CLI's owned paint path."""
import io
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

# Native graphics packets must bypass ANSI's text parser, while symbol-mode
# SGR and newlines remain ordinary, measurable transcript content.
_GRAPHICS_PACKET = re.compile(r"\x1b(?:_[\s\S]*?\x1b\\|P[\s\S]*?\x1b\\|\][\s\S]*?(?:\x07|\x1b\\))")


def chafa_preview(data: bytes, *, cols: int) -> list[str] | None:
    from PIL import Image
    from sci_cli.config import load_config
    from sci_platform.resolver import locate_command
    from sci_platform.resolver.known_dirs import homebrew_dirs, user_local_bin
    from tools.environments.local import served_profile_child_env
    from tui_gateway.image_preview import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS

    display = load_config().get("display") or {}
    if display.get("image_renderer", "auto") == "builtin":
        return None
    command = locate_command("chafa", known_dirs=(*homebrew_dirs(), *user_local_bin())).command
    if not command:
        return None
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the preview size limit")
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image exceeds the preview pixel limit")
    args = [*command, "--probe=off", "--polite=on", "--animate=off", "--duration=0",
            f"--size={max(4, min(cols, 160))}x72", "--bg=white", "--fg=black"]
    protocol = display.get("image_protocol", "auto")
    if protocol in {"kitty", "iterm", "sixels", "symbols"}:
        args.append("--format=" + protocol)
    args.append("-")
    try:
        # Probing would read keystrokes from the prompt's input stream. Chafa
        # uses terminal identity here; an explicit protocol handles ambiguous SSH.
        result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=served_profile_child_env(), timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Chafa unavailable: %s", exc)
        return None
    if result.returncode or not result.stdout:
        logger.debug("Chafa returned exit %s", result.returncode)
        return None
    text = result.stdout.decode("utf-8", errors="replace")
    if "\x1b]1337;File=" in text:
        # Chafa's iTerm payload is TIFF. Other terminals implementing that
        # protocol (including xterm.js) accept PNG but silently reject TIFF.
        from sci_cli.terminal_images import native_preview

        text = native_preview(data, cols=cols, mode="iterm")
    text = _GRAPHICS_PACKET.sub(lambda match: "\001" + match.group() + "\002", text)
    return text.rstrip("\n").split("\n")
