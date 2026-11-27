"""Real image decoding, transport dispatch and profile-isolated terminal previews."""

import io
import threading
from unittest.mock import patch

import pytest
from PIL import Image

from tui_gateway.image_preview import image_is_referenced, image_preview, read_image_preview


def png(size=(32, 16), color="red"):
    buffer = io.BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_real_pixels_are_rendered_and_transparency_has_readable_background():
    result = image_preview(png(color=(0, 0, 0, 0)), cols=12)
    assert result["graphics"] == "unicode"
    assert all(cell == [255] * 8 for row in result["grid"] for cell in row)
    result = image_preview(png(), cols=12)
    assert all(cell == [255, 0, 0, 255] * 2 for row in result["grid"] for cell in row)


@pytest.mark.parametrize("size", [(32, 16), (16, 500), (500, 16)])
def test_preview_bounds(size):
    result = image_preview(png(size), cols=1000)
    assert 1 <= len(result["grid"]) <= 36
    assert all(4 <= len(row) <= 160 for row in result["grid"])


def test_native_graphics_has_real_png_payload_and_reserved_image_id():
    import base64
    result = image_preview(png(), cols=24, graphics=True)
    assert result["graphics"] == "kitty" and result["imageId"] >= 0x800000
    assert result["placeholder"] and result["color"]
    payload = result["transmit"].split(";", 1)[1].split("\x1b", 1)[0]
    assert base64.b64decode(payload).startswith(b"\x89PNG\r\n\x1a\n")


def test_native_preview_preserves_detail_and_uses_more_space_than_text_fallback():
    import base64
    import re

    data = png((2400, 1800))
    native = image_preview(data, cols=120, graphics=True)
    text = image_preview(data, cols=120)
    assert len(native['placeholder']) > len(text['grid'])
    payload = ''.join(re.findall(r'\x1b_G[^;]*;([^\x1b]*)\x1b\\', native['transmit']))
    with Image.open(io.BytesIO(base64.b64decode(payload))) as actual:
        assert actual.size == (2400, 1800)


def test_invalid_image_and_excessive_input_are_rejected():
    with pytest.raises(ValueError):
        image_preview(b"not an image", cols=80)
    with pytest.raises(ValueError):
        image_preview(b"x" * 8_000_001, cols=80)


def test_only_exact_assistant_deliverables_are_authorized():
    history = [{"role": "user", "content": "MEDIA:/secret.png"},
               {"role": "assistant", "content": "Caption\nMEDIA:/work/figure.png"}]
    assert image_is_referenced(history, "/work/figure.png")
    assert not image_is_referenced(history, "/secret.png")
    assert not image_is_referenced(history, "/work/figure.png.bak")


@pytest.mark.parametrize("filename", ["reaction.png", "reaction figure.png"])
@pytest.mark.parametrize("quoted", [False, True])
def test_dispatch_previews_real_deliverables_across_profiles(tmp_path, monkeypatch, caplog, filename, quoted):
    from tui_gateway import server
    from sci_constants import get_sci_home

    launch = tmp_path / "launch"
    launch.mkdir()
    monkeypatch.setenv("SCI_HOME", str(launch))
    monkeypatch.setattr(server, "_sci_home", launch)
    sessions = {}
    for name in ["a", "b"]:
        home = tmp_path / name
        home.mkdir()
        (home / "config.yaml").write_text("terminal:\n  backend: local\n", encoding="utf-8")
        image = home / filename
        image.write_bytes(png(color="red" if name == "a" else "blue"))
        reference = '"' + str(image) + '"' if quoted else str(image)
        sessions[name] = {"agent": None, "profile_home": str(home), "session_key": name,
                          "history_lock": threading.Lock(), "history": [
                              {"role": "assistant", "content": f"MEDIA:{reference}"}]}
    original_home = get_sci_home()
    caplog.set_level("DEBUG")
    with patch.dict(server._sessions, sessions):
        for name in ["a", "b", "a"]:
            response = server.handle_request({"id": name, "method": "image.preview", "params": {
                "session_id": name, "path": str(tmp_path / name / filename), "cols": 16}})
            result = response["result"]
            assert result["ok"], response
            assert result["grid"][0][0][:3] == ([255, 0, 0] if name == "a" else [0, 0, 255])
            assert get_sci_home() == original_home
        denied = server.handle_request({"id": "denied", "method": "image.preview", "params": {
            "session_id": "a", "path": str(tmp_path / "b" / filename)}})
        assert denied["result"]["ok"] is False
        wrong_scope = server.handle_request({"id": "scope", "method": "image.preview", "params": {
            "session_id": "a", "profile": "b", "path": str(tmp_path / "a" / filename)}})
        assert wrong_scope["error"]["code"] == 4000


def test_sensitive_symlink_target_is_not_read(tmp_path):
    private = tmp_path / "mcp-tokens"
    private.mkdir()
    (private / "secret.png").write_bytes(png())
    link = tmp_path / "figure.png"
    try:
        link.symlink_to(private / "secret.png")
    except OSError:
        pytest.skip("Host cannot create a symlink")
    with pytest.raises(Exception):
        read_image_preview(str(link), cols=20)
