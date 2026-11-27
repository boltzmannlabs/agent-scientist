"""Chafa output is delivered by the CLI rather than captured as tool logs."""
import io
import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest


def png():
    output = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(output, format="PNG")
    return output.getvalue()


def test_cli_runs_chafa_child_and_preserves_packets_and_profile(tmp_path, monkeypatch):
    import cli
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
    from sci_cli.cli_render import print_assistant_image_previews
    from sci_constants import reset_sci_home_override, set_sci_home_override
    from sci_platform import resolver

    child = tmp_path / "renderer.py"
    child.write_text(
        "import json,os,sys\nfrom pathlib import Path\n"
        "data=sys.stdin.buffer.read()\n"
        "Path(os.environ['SCI_HOME'],'received.json').write_text(json.dumps({'args':sys.argv[1:],'size':len(data)}))\n"
        "sys.stdout.write('\\x1b_Ga=T;YWJj\\x1b\\\\\\n\\x1b[31mSymbols\\x1b[0m\\n')\n")
    monkeypatch.setattr(resolver, "locate_command", lambda *a, **k: SimpleNamespace(command=(sys.executable, str(child))))
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    output = []
    monkeypatch.setattr(cli, "_cprint", output.append)
    homes = [tmp_path / "a", tmp_path / "b"]
    data = png()
    for home in homes:
        home.mkdir()
        (home / "config.yaml").write_text("display:\n  image_renderer: chafa\n  image_protocol: kitty\nterminal:\n  backend: local\n")
        (home / "figure.png").write_bytes(data)
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            output.clear()
            print_assistant_image_previews("MEDIA:" + str(home / "figure.png"), 100)
            assert len(output) == 2
            assert to_formatted_text(cli._PT_ANSI(output[0])) == [("[ZeroWidthEscape]", "\x1b_Ga=T;YWJj\x1b\\")]
            assert "Symbols" in "".join(text for _, text in to_formatted_text(ANSI(output[1])))
            received = json.loads((home / "received.json").read_text())
            assert received["size"] == len(data)
            assert "--format=kitty" in received["args"]
            assert "--probe=off" in received["args"]
            assert "--size=98x72" in received["args"]
            assert received["args"][-1] == "-"
        finally:
            reset_sci_home_override(token)


@pytest.mark.parametrize("selection", ["builtin", "auto", "chafa"])
def test_configured_renderer_can_disable_chafa_and_missing_tool_falls_back(tmp_path, monkeypatch, selection):
    from sci_cli.chafa_images import chafa_preview
    from sci_constants import get_sci_home
    from sci_platform import resolver

    home = Path(get_sci_home())
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(f"display:\n  image_renderer: {selection}\n")
    calls = []

    def absent(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(command=())

    monkeypatch.setattr(resolver, "locate_command", absent)
    assert chafa_preview(png(), cols=80) is None
    assert bool(calls) == (selection != "builtin")


def test_chafa_failure_and_timeout_allow_builtin_fallback(tmp_path, monkeypatch):
    from sci_cli import chafa_images
    from sci_platform import resolver
    import subprocess

    child = tmp_path / "failed.py"
    child.write_text("raise SystemExit(7)\n")
    monkeypatch.setattr(resolver, "locate_command", lambda *a, **k: SimpleNamespace(command=(sys.executable, str(child))))
    assert chafa_images.chafa_preview(png(), cols=80) is None

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    assert chafa_images.chafa_preview(png(), cols=80) is None


def test_iterm_chafa_payload_uses_browser_decodable_png(tmp_path, monkeypatch):
    from sci_cli.chafa_images import chafa_preview
    from sci_cli.terminal_links import ImageANSI, TerminalANSI
    from prompt_toolkit.formatted_text import to_formatted_text
    from sci_platform import resolver

    # Exercise a real renderer child returning Chafa's TIFF-based wire format.
    child = tmp_path / "iterm_renderer.py"
    child.write_text("import sys\nsys.stdin.buffer.read()\nsys.stdout.write('\\x1b]1337;File=inline=1:SUkqAA==\\x07')\n")
    monkeypatch.setattr(resolver, "locate_command", lambda *a, **k: SimpleNamespace(command=(sys.executable, str(child))))
    rendered = chafa_preview(png(), cols=80)
    fragments = to_formatted_text(TerminalANSI(ImageANSI(rendered[0], history_text="test image")))
    assert len(fragments) == 1 and fragments[0][0] == "[ZeroWidthEscape]"
    packet = fragments[0][1]
    header, encoded = packet.split(":", 1)
    payload = base64.b64decode(encoded.removesuffix("\x07"), validate=True)
    assert f"size={len(payload)};" in header
    with Image.open(io.BytesIO(payload)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == (80, 40)
        assert decoded.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
