"""Native classic-terminal images; the TUI owns its own placement protocol."""
import base64
import io


def native_preview(data: bytes, *, cols: int, mode: str) -> str:
    from PIL import Image
    from agent.pet.render import _encode_sixel, _kitty_apc
    from tui_gateway.image_preview import decode_image_preview

    frame = decode_image_preview(data, graphics=True)
    cols = max(4, min(cols, 160, int(144 * frame.width / frame.height)))
    rows = max(1, min(72, round(cols * frame.height / frame.width / 2)))
    # White backing keeps bonds and transparent labels legible on dark themes.
    background = Image.new("RGBA", frame.size, "white")
    background.alpha_composite(frame)
    if mode == "sixel":
        background.thumbnail((cols * 8, rows * 16), Image.Resampling.LANCZOS)
        return _encode_sixel(background)
    output = io.BytesIO()
    background.save(output, format="PNG")
    png = output.getvalue()
    payload = base64.b64encode(png).decode("ascii")
    if mode == "kitty":
        return _kitty_apc(f"f=100,a=T,q=2,c={cols},r={rows}", payload)
    if mode == "iterm":
        return (f"\x1b]1337;File=inline=1;size={len(png)};preserveAspectRatio=1;"
                f"width={cols};height={rows}:{payload}\x07")
    raise ValueError(f"Unsupported native image mode: {mode}")
