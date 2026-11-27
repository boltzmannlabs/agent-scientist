"""Presentation exports preserve process values and separate drawing furniture."""
import xml.etree.ElementTree as ET

import pytest

from sci_cli.cheme_diagrams import focused_svg, SVG


def test_process_and_table_exports_preserve_content_in_separate_views():
    source = '''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="297" viewBox="0 0 420 297">
    <rect width="420" height="297" fill="white"/><g class="diagram">
    <g class="representation-group" id="M1"><text font-size="2.4">Mixer 400 kg/h</text></g>
    <g class="representation-group" id="S1"><path d="M 1 2 L 3 4"/><text font-size="2">S1</text></g>
    <g id="Drawing_Frame_Static"><path d="M 0 0 L 420 297"/></g>
    <g id="Drawing_StreamTable_Label"><text>25 mass% ethanol</text></g>
    <g id="Drawing_title"><text>Engineering sheet title</text></g></g></svg>'''
    diagram = ET.fromstring(focused_svg(source))
    table = ET.fromstring(focused_svg(source, table=True))
    assert [t.text for t in diagram.iter(SVG + "text")] == ["Mixer 400 kg/h", "S1"]
    assert [float(t.get("font-size")) for t in diagram.iter(SVG + "text")] == [4.2, 3.5]
    assert [t.text for t in table.iter(SVG + "text")] == ["25 mass% ethanol"]
    assert next(diagram.iter(SVG + "path")).get("d") == "M 1 2 L 3 4"
    assert not diagram.findall(SVG + "rect")
    # The engineering source is still reusable without presentation edits.
    assert ET.fromstring(source).find(SVG + "rect") is not None


def test_export_refuses_missing_process_geometry():
    with pytest.raises(ValueError, match="No process geometry"):
        focused_svg('<svg xmlns="http://www.w3.org/2000/svg"><g class="diagram"/></svg>')
