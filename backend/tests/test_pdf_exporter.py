import math
import xml.etree.ElementTree as ET

import pytest

from core import pdf_exporter as pdf_module
from core.pdf_exporter import PDFExporter


SVG_NS = "http://www.w3.org/2000/svg"
PT_PER_MM = 72.0 / 25.4


def _stacked_svg(page_width_px=793.8, page_height_px=1122.66, page_gap=20.0):
    total_height = page_height_px * 2 + page_gap
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="{SVG_NS}" width="{page_width_px}px" height="{total_height}px" viewBox="0 0 {page_width_px} {total_height}">
  <style>
    .page-border {{ fill: white; stroke: #999999; }}
    .face-polygon {{ fill: none; stroke: #000000; }}
  </style>
  <rect x="0" y="0" width="{page_width_px}" height="{page_height_px}" class="page-border" />
  <polygon points="37.8,37.8 137.8,37.8 137.8,137.8 37.8,137.8" class="face-polygon" />
  <rect x="0" y="{page_height_px + page_gap}" width="{page_width_px}" height="{page_height_px}" class="page-border" />
  <polygon points="37.8,{page_height_px + page_gap + 37.8} 137.8,{page_height_px + page_gap + 37.8} 137.8,{page_height_px + page_gap + 137.8} 37.8,{page_height_px + page_gap + 137.8}" class="face-polygon" />
</svg>
"""


def _write_stacked_svg(tmp_path, **kwargs):
    svg_path = tmp_path / "stacked.svg"
    svg_path.write_text(_stacked_svg(**kwargs), encoding="utf-8")
    return str(svg_path)


def _parse_svg(svg_bytes):
    return ET.fromstring(svg_bytes)


@pytest.mark.parametrize(
    ("page_format", "orientation", "expected_width", "expected_height"),
    [
        ("A4", "portrait", "210mm", "297mm"),
        ("A4", "landscape", "297mm", "210mm"),
        ("A3", "portrait", "297mm", "420mm"),
        ("Letter", "portrait", "216mm", "279mm"),
    ],
)
def test_split_stacked_svg_uses_physical_page_size_and_preserves_viewbox(
    tmp_path, page_format, orientation, expected_width, expected_height
):
    svg_path = _write_stacked_svg(tmp_path)
    exporter = PDFExporter(page_format=page_format, page_orientation=orientation)

    pages = exporter._split_stacked_svg_by_page_border(svg_path)

    assert len(pages) == 2

    first = _parse_svg(pages[0])
    second = _parse_svg(pages[1])
    assert first.attrib["width"] == expected_width
    assert first.attrib["height"] == expected_height
    assert first.attrib["viewBox"] == "0 0 793.8 1122.66"
    assert second.attrib["width"] == expected_width
    assert second.attrib["height"] == expected_height
    assert second.attrib["viewBox"] == "0 1142.66 793.8 1122.66"


def test_export_stacked_svg_to_pdf_keeps_page_count_and_media_box(tmp_path):
    if not (pdf_module.CAIROSVG_AVAILABLE and pdf_module.PYPDF2_AVAILABLE):
        pytest.skip("PDF backend dependencies are not available")

    svg_path = _write_stacked_svg(tmp_path)
    pdf_path = tmp_path / "out.pdf"
    exporter = PDFExporter(page_format="A4", page_orientation="portrait")

    exporter.export_stacked_svg_to_pdf(svg_path, str(pdf_path))

    with open(pdf_path, "rb") as pdf_file:
        reader = pdf_module.PdfReader(pdf_file)
        assert len(reader.pages) == 2
        page = reader.pages[0]
        width_pt = float(page.mediabox.width)
        height_pt = float(page.mediabox.height)

    assert math.isclose(width_pt, 210 * PT_PER_MM, abs_tol=0.75)
    assert math.isclose(height_pt, 297 * PT_PER_MM, abs_tol=0.75)
