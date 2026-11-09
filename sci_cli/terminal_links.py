"""File links for terminal output, without opening files or running a shell."""

from pathlib import PurePosixPath, PureWindowsPath
import re
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
from prompt_toolkit.formatted_text import ANSI
from rich.markdown import Markdown


_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_OSC = re.compile(r"\x1b\]([\s\S]*?)(?:\x07|\x1b\\|$)")
_CLOSE = "\x1b]8;;\x1b\\"


def file_link_uri(value: str) -> str | None:
    """Interpret path syntax independently of the host running the renderer."""
    if _CONTROLS.search(value):
        return None
    if value.lower().startswith("file:"):
        try:
            url = urlsplit(value)
        except ValueError:
            return None
        if url.query or url.fragment or url.username or url.password:
            return None
        path = unquote(url.path)
        if _CONTROLS.search(path) or _CONTROLS.search(unquote(url.netloc)):
            return None
        if url.netloc and url.netloc.lower() != "localhost":
            value = "\\\\" + url.netloc + path.replace("/", "\\")
        else:
            value = path[1:] if re.match(r"^/[A-Za-z]:/", path) else path
    if value.startswith(("\\\\?\\", "\\\\.\\")):
        return None  # Device namespaces are not ordinary file links.
    if _DRIVE.match(value) or value.startswith("\\\\"):
        path = PureWindowsPath(value)
        if not path.is_absolute():
            return None
        prefix = "file:" if path.drive.startswith("\\\\") else "file:///"
        return prefix + quote(path.as_posix(), safe="/:")
    if value.startswith("/"):
        return "file://" + quote(PurePosixPath(value).as_posix(), safe="/")
    return None


def safe_link_target(value: str) -> str | None:
    file_uri = file_link_uri(value)
    if file_uri:
        return file_uri
    if _CONTROLS.search(value) or _CONTROLS.search(unquote(value)):
        return None
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    if url.scheme.lower() in {"http", "https"} and url.hostname:
        return value
    if url.scheme.lower() == "mailto" and url.path:
        return value
    return None


def terminal_markdown(text: str) -> Markdown:
    parser = MarkdownIt().enable("strikethrough").enable("table")
    normalize = parser.normalizeLink
    validate = parser.validateLink
    parser.normalizeLink = lambda value: file_link_uri(value) or normalize(value)
    parser.validateLink = lambda value: bool(file_link_uri(value)) or validate(value)
    rendered = Markdown("")
    rendered.markup = text
    rendered.parsed = parser.parse(text)
    # Backticked paths and standalone path paragraphs are common result formats.
    # Do not linkify code blocks, arbitrary substrings or text inside authored links.
    for block in rendered.parsed:
        if not block.children:
            continue
        children = []
        in_link = False
        for token in block.children:
            if token.type == "link_open":
                in_link = True
            candidate = token.content
            # Slash commands such as /help are not output paths.
            is_path = _DRIVE.match(candidate) or candidate.startswith(("\\\\", "file:")) or candidate.count("/") > 1
            target = file_link_uri(candidate) if not in_link and is_path and token.type in {"text", "code_inline"} else None
            if target:
                children.append(Token("link_open", "a", 1, attrs={"href": target}))
            children.append(token)
            if target:
                children.append(Token("link_close", "a", -1))
            if token.type == "link_close":
                in_link = False
        block.children = children
    return rendered


def terminal_hyperlinks(text: str) -> str:
    """Keep only supported OSC 8 links; discard title/clipboard and other OSCs."""
    text = text.replace("\x01", "").replace("\x02", "")
    active = False

    def replace(match):
        nonlocal active
        parts = match[1].split(";", 2)
        if len(parts) != 3 or parts[0] != "8":
            return ""
        target = safe_link_target(parts[2]) if parts[2] else ""
        active = bool(target)
        return f"\x1b]8;;{target}\x1b\\" if target else _CLOSE

    result = _OSC.sub(replace, text)
    return result + _CLOSE if active else result


class TerminalANSI(ANSI):
    """Carry validated links through prompt_toolkit as zero-width escapes."""

    def __init__(self, value: str):
        value = terminal_hyperlinks(value)
        # ANSI normally discards OSC and may expose its payload as visible text.
        value = _OSC.sub(lambda match: "\x01" + match[0] + "\x02", value)
        # prompt_toolkit consumes the next character after a zero-width block;
        # adjacent controls must therefore share one block.
        value = value.replace("\x02\x01", "")
        super().__init__(value)
