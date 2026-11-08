"""Terminal ownership for the persistent-chat viewer; no input threads survive detach."""

import os
import select
import signal
import sys


class PosixConsole:
    def __init__(self, outcome):
        self.outcome = outcome
        self.stopped = False
        self.resized = False
        self.previous = {}

    def __enter__(self):
        import termios
        import tty
        self.saved = termios.tcgetattr(sys.stdin.fileno())
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):  # windows-footgun: ok — PosixConsole is selected only on POSIX
            self.previous[sig] = signal.signal(sig, self.stop)
        self.previous[signal.SIGWINCH] = signal.signal(signal.SIGWINCH, self.resize)
        self.previous[signal.SIGTSTP] = signal.signal(signal.SIGTSTP, self.suspend)
        tty.setraw(sys.stdin.fileno(), when=termios.TCSANOW)
        return self

    def stop(self, *_):
        self.stopped = True

    def resize(self, *_):
        self.resized = True

    def suspend(self, *_):
        self.outcome['suspend'] = True
        self.stopped = True

    def poll(self, sock, *, timeout=None):
        readable, _, _ = select.select([sock, sys.stdin], [], [], 0.2 if timeout is None else timeout)
        return sock in readable, os.read(sys.stdin.fileno(), 8192) if sys.stdin in readable else None

    def __exit__(self, *_):
        import termios
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, self.saved)
        except termios.error:
            pass  # The terminal may have been closed by its owner.


class WindowsConsole:
    def __init__(self, outcome):
        self.stopped = False
        self.resized = False
        self.previous = {}
        self.saved = []
        self.pending_surrogate = ''
        self.reader = None

    def __enter__(self):
        import ctypes
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetStdHandle.restype = wintypes.HANDLE
        self.kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        try:
            for identifier in (-10, -11):
                handle = self.kernel.GetStdHandle(identifier)
                mode = wintypes.DWORD()
                if not self.kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    raise ctypes.WinError(ctypes.get_last_error())
                self.saved.append((handle, mode.value))
                # Raw Ctrl+C is delivered as input to the worker, never a console-wide signal.
                new = ((mode.value & ~(1 | 2 | 4 | 64 | 0x200)) | 0x98) if identifier == -10 else mode.value | 4
                if not self.kernel.SetConsoleMode(handle, new):
                    raise ctypes.WinError(ctypes.get_last_error())
            self.size = os.get_terminal_size()
            from sci_cli.windows_console_input import install_ctrl_slash_alias
            install_ctrl_slash_alias()
            from prompt_toolkit.input.win32 import ConsoleInputReader
            self.reader = ConsoleInputReader(recognize_paste=False)
            self.previous[signal.SIGINT] = signal.signal(signal.SIGINT, lambda *_: None)
            self.previous[signal.SIGTERM] = signal.signal(signal.SIGTERM, self.stop)
            return self
        except BaseException:
            self.__exit__()
            raise

    def stop(self, *_):
        self.stopped = True

    def poll(self, sock, *, timeout=None):
        readable = bool(select.select([sock], [], [], 0.05 if timeout is None else timeout)[0])
        size = os.get_terminal_size()
        if size != self.size:
            self.resized, self.size = True, size
        keys = list(self.reader.read())
        if not keys:
            return readable, None
        text = self.pending_surrogate + ''.join(self.key_data(key) for key in keys)
        self.pending_surrogate = ''
        if text and 0xD800 <= ord(text[-1]) <= 0xDBFF:
            text, self.pending_surrogate = text[:-1], text[-1]
        data = text.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace').encode('utf-8')
        return readable, data if data else None

    @staticmethod
    def key_data(key):
        from prompt_toolkit.keys import Keys
        if key.key != Keys.WindowsMouseEvent:
            return key.data
        button, event, x, y = key.data.split(';')
        code = {'LEFT': 0, 'MIDDLE': 1, 'RIGHT': 2, 'NONE': 3}[button]
        code = {'SCROLL_UP': 64, 'SCROLL_DOWN': 65}.get(event, code)
        if event == 'MOUSE_MOVE':
            code |= 32
        suffix = 'm' if event == 'MOUSE_UP' else 'M'
        return f'\x1b[<{code};{int(x) + 1};{int(y) + 1}{suffix}'

    def __exit__(self, *_):
        if self.reader is not None:
            self.reader.close()
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)
        for handle, mode in reversed(self.saved):
            self.kernel.SetConsoleMode(handle, mode)


def terminal_console(outcome):
    return WindowsConsole(outcome) if os.name == 'nt' else PosixConsole(outcome)
