"""Interactive CLI displays real pixels while redirected output remains plain text."""
import io
import sys

import pytest
from PIL import Image


def test_interactive_cli_previews_once_and_keeps_missing_files_recoverable(tmp_path, monkeypatch):
    import cli
    from sci_cli import chafa_images
    from sci_cli.cli_render import print_assistant_image_previews

    path = tmp_path / 'figure.png'
    Image.new('RGB', (8, 8), 'red').save(path)
    output = []
    monkeypatch.setenv('TERM_PROGRAM', 'vscode')
    monkeypatch.setattr(chafa_images, 'chafa_preview', lambda *a, **k: None)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(cli, '_cprint', output.append)
    print_assistant_image_previews(f'MEDIA:{path}\nMEDIA:{path}', 20)
    assert output and all('▀' in row and '\033[38;2;255;0;0m' in row for row in output[:-1])
    assert str(path) in output[-1] and 'Full-resolution' in output[-1]
    first_length = len(output)
    print_assistant_image_previews(f'MEDIA:{tmp_path / "missing.png"}', 20)
    assert output[first_length:] == ['Image preview unavailable. Open the original file.']


def test_redirected_cli_does_not_decode_or_print_images(monkeypatch):
    from sci_cli.cli_render import print_assistant_image_previews
    output = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', output)
    print_assistant_image_previews('MEDIA:/unavailable.png', 80)
    assert output.getvalue() == ''


@pytest.mark.parametrize('mode', ['kitty', 'iterm', 'sixel'])
def test_interactive_cli_uses_native_protocol_without_losing_it_in_text_renderer(tmp_path, monkeypatch, mode):
    import cli
    from sci_cli import chafa_images
    from agent.pet import render
    from prompt_toolkit.formatted_text import to_formatted_text
    from sci_cli.cli_render import print_assistant_image_previews

    path = tmp_path / 'reaction.png'
    Image.new('RGB', (400, 200), 'white').save(path)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(chafa_images, 'chafa_preview', lambda *a, **k: None)
    monkeypatch.setattr(render, 'detect_terminal_graphics', lambda: mode)
    output = []
    monkeypatch.setattr(cli, '_cprint', output.append)
    print_assistant_image_previews(f'MEDIA:{path}', 100)
    assert len(output) == 1
    parts = to_formatted_text(cli._PT_ANSI(output[0]))
    assert parts[0][0] == '[ZeroWidthEscape]'
    assert {'kitty': '\x1b_G', 'iterm': '\x1b]1337;File=', 'sixel': '\x1bP'}[mode] in parts[0][1]


@pytest.mark.parametrize('mode', ['kitty', 'iterm'])
def test_native_payload_keeps_high_resolution_pixels_and_white_background(mode):
    import base64
    import re
    from sci_cli.terminal_images import native_preview

    output = io.BytesIO()
    Image.new('RGBA', (2400, 1800), (0, 0, 0, 0)).save(output, format='PNG')
    text = native_preview(output.getvalue(), cols=120, mode=mode)
    if mode == 'kitty':
        payload = ''.join(re.findall(r'\x1b_G[^;]*;([^\x1b]*)\x1b\\', text))
    else:
        payload = text.split(':', 1)[1].rstrip('\x07')
    with Image.open(io.BytesIO(base64.b64decode(payload))) as actual:
        assert actual.size == (2400, 1800)
        assert actual.getpixel((0, 0)) == (255, 255, 255, 255)
