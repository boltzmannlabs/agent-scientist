"""Normalize native console keys that Windows does not give a control character."""


def install_ctrl_slash_alias():
    import ctypes
    from ctypes import wintypes
    from prompt_toolkit.input.win32 import ConsoleInputReader
    from prompt_toolkit.key_binding.key_processor import KeyPress
    from prompt_toolkit.keys import Keys

    original = ConsoleInputReader._event_to_key_presses
    if getattr(original, '_sci_ctrl_slash', False):
        return
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    user32.GetKeyboardLayout.restype = wintypes.HANDLE
    user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HANDLE]
    user32.MapVirtualKeyExW.restype = wintypes.UINT

    def normalized(reader, event):
        modifiers = event.ControlKeyState
        if (event.KeyDown and modifiers & 0xC and not modifiers & 0x13
                and event.uChar.UnicodeChar in ('\x00', '/')
                and user32.MapVirtualKeyExW(event.VirtualKeyCode, 2,
                                           user32.GetKeyboardLayout(0)) == ord('/')):
            return [KeyPress(Keys.ControlUnderscore, '\x1f')]
        return original(reader, event)

    normalized._sci_ctrl_slash = True
    ConsoleInputReader._event_to_key_presses = normalized
