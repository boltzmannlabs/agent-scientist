"""Readable chat exports derived from the package's engineering SVGs."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def focused_svg(source: str, *, table: bool = False) -> str:
    """Separate process geometry or the stream table from the engineering frame."""
    root = ET.fromstring(source)
    diagram = next((g for g in root if g.tag == SVG + "g" and g.get("class") == "diagram"), None)
    if diagram is None:
        raise ValueError("The generated SVG has no diagram group")
    for child in list(root):
        if child.tag == SVG + "rect":
            root.remove(child)  # The renderer's full-page white backing prevents tight bounds.
    for child in list(diagram):
        keep = (child.get("id", "").startswith("Drawing_StreamTable_") if table
                else child.get("class") == "representation-group")
        if not keep:
            diagram.remove(child)
    if not len(diagram):
        raise ValueError("No stream table" if table else "No process geometry")
    for text in diagram.iter(SVG + "text"):
        text.set("font-family", "DejaVu Sans, Liberation Sans, Arial, sans-serif")
        # The source engineering geometry and values stay untouched. This
        # separate presentation export modestly enlarges labels within their bands.
        if not table:
            text.set("font-size", str(float(text.get("font-size", "3")) * 1.75))
    if not table:
        for group in diagram.iter(SVG + "g"):
            if group.get("class") != "representation-group":
                continue
            static = next((g for g in group if g.get("class") == "static"), None)
            label = next((g for g in group if g.get("class") == "label"), None)
            if static is None or label is None:
                continue
            xs = []
            for line in static.iter(SVG + "polyline"):
                points = [float(n) for n in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line.get("points", ""))]
                xs.extend(points[::2])
            if not xs or max(xs) == min(xs):
                continue
            for text in label.iter(SVG + "text"):
                if text.get("text-anchor") == "middle" and text.text:
                    # Reserve space inside terminal symbols so a long name does
                    # not collide with the connected stream after enlargement.
                    fit = (max(xs) - min(xs)) * 0.8 / (len(text.text) * 0.62)
                    text.set("font-size", str(min(float(text.get("font-size")), fit)))
    return ET.tostring(root, encoding="unicode")


def _raster(python: Path, environment: dict, source: Path, output: Path, scale: float):
    code = ("import sys; from pathlib import Path; "
            "from chemeascode.domains.piping.render import svg_to_png; "
            "Path(sys.argv[2]).write_bytes(svg_to_png(Path(sys.argv[1]).read_text(encoding='utf-8-sig'),float(sys.argv[3])))")
    subprocess.run([str(python), "-c", code, str(source), str(output), str(scale)],
                   env=environment, check=True, timeout=120)


def export_diagrams(project: Path, python: Path, environment: dict) -> list[Path]:
    from PIL import Image, ImageChops

    outputs = []
    build = project / "build"
    build.mkdir(exist_ok=True)
    for name in ("BFD", "PFD"):
        xml = project / "process" / (name + ".xml")
        if not xml.is_file():
            continue
        with tempfile.TemporaryDirectory(prefix="cheme-chat-") as temporary:
            stage = Path(temporary)
            original = stage / "sheet.svg"
            subprocess.run([str(python), "-c", "from chemeascode.interfaces.cli import app; app()",
                            "render", str(xml), "-o", str(original)], cwd=project,
                           env=environment, check=True, timeout=120, stdout=subprocess.DEVNULL)
            for table in (False, True):
                try:
                    svg = focused_svg(original.read_text(encoding="utf-8-sig"), table=table)
                except ValueError:
                    if table:
                        continue
                    raise
                working = stage / "focus.svg"
                working.write_text(svg, encoding="utf-8")
                measure = stage / "bounds.png"
                _raster(python, environment, working, measure, 2)
                with Image.open(measure) as image:
                    rgb = image.convert("RGB")
                    box = ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).getbbox()
                if box is None:
                    raise ValueError("Generated diagram is empty")
                root = ET.fromstring(svg)
                vx, vy, _, _ = map(float, root.get("viewBox").split())
                margin = 4.0
                x0, y0 = vx + box[0] / 2 - margin, vy + box[1] / 2 - margin
                width, height = (box[2] - box[0]) / 2 + 2 * margin, (box[3] - box[1]) / 2 + 2 * margin
                root.set("viewBox", f"{x0} {y0} {width} {height}")
                root.set("width", str(width))
                root.set("height", str(height))
                background = ET.Element(SVG + "rect", {"x": str(x0), "y": str(y0), "width": str(width),
                                                       "height": str(height), "fill": "white"})
                root.insert(0, background)
                suffix = "streams" if table else "chat"
                target = build / f"{name}-{suffix}.svg"
                target.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
                # Export from vector data at up to 3200 x 4000 pixels. No bitmap upscaling.
                scale = min(3200 / width, 4000 / height, 40)
                png = target.with_suffix(".png")
                _raster(python, environment, target, png, scale)
                outputs.extend([target, png])
    if not outputs:
        raise ValueError("No process diagrams found. Run process build first.")
    return outputs
