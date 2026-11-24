"""Interactive CLI displays real pixels while redirected output remains plain text."""
import io
import sys

from PIL import Image


def test_interactive_cli_previews_once_and_keeps_missing_files_recoverable(tmp_path, monkeypatch):
    import cli
    from sci_cli.cli_render import print_assistant_image_previews

    path = tmp_path / 'figure.png'
    Image.new('RGB', (8, 8), 'red').save(path)
    output = []
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(cli, '_cprint', output.append)
    print_assistant_image_previews(f'MEDIA:{path}\nMEDIA:{path}', 20)
    assert output and all('▀' in row and '\033[38;2;255;0;0m' in row for row in output)
    first_length = len(output)
    print_assistant_image_previews(f'MEDIA:{tmp_path / "missing.png"}', 20)
    assert output[first_length:] == ['Image preview unavailable. Open the original file.']


def test_redirected_cli_does_not_decode_or_print_images(monkeypatch):
    from sci_cli.cli_render import print_assistant_image_previews
    output = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', output)
    print_assistant_image_previews('MEDIA:/unavailable.png', 80)
    assert output.getvalue() == ''
