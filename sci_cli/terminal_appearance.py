"""Own terminal defaults only for an interactive, explicitly surfaced skin."""

import atexit
import os
import re
import sys

_HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")


class TerminalAppearance:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.painted = False
        self.registered = False

    def apply(self, skin):
        if not self.stream.isatty() or os.environ.get("TERM") == "dumb" or "NO_COLOR" in os.environ:
            return
        background = skin.get_color("background")
        foreground = skin.get_color("banner_text")
        if not (_HEX.fullmatch(background) and _HEX.fullmatch(foreground)):
            self.restore()
            return
        try:
            # Default colors cover unpainted cells too, unlike SGR component fills.
            self.stream.write(f"\033]11;{background}\007\033]10;{foreground}\007")
            self.stream.flush()
        except (OSError, ValueError):
            return
        self.painted = True
        if not self.registered:
            atexit.register(self.restore)
            self.registered = True

    def restore(self):
        if not self.painted:
            return
        try:
            self.stream.write("\033]111\007\033]110\007")
            self.stream.flush()
        except (OSError, ValueError):
            return
        self.painted = False
