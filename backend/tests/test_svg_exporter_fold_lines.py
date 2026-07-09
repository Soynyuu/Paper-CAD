import xml.etree.ElementTree as ET

from core.layout_manager import LayoutManager
from core.svg_exporter import SVGExporter


def test_svg_exporter_draws_fold_lines(tmp_path):
    exporter = SVGExporter(show_fold_lines=True)
    output_path = tmp_path / "fold-lines.svg"

    exporter.export_to_svg(
        [
            {
                "polygons": [[(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)]],
                "tabs": [],
                "fold_lines": [[(10.0, 0.0), (10.0, 20.0)]],
                "face_numbers": [1],
            }
        ],
        str(output_path),
    )

    svg = output_path.read_text()
    assert 'class="fold-line"' in svg


def test_svg_exporter_hides_fold_lines_when_disabled(tmp_path):
    exporter = SVGExporter(show_fold_lines=False)
    output_path = tmp_path / "no-fold-lines.svg"

    exporter.export_to_svg(
        [
            {
                "polygons": [[(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)]],
                "tabs": [],
                "fold_lines": [[(10.0, 0.0), (10.0, 20.0)]],
                "face_numbers": [1],
            }
        ],
        str(output_path),
    )

    svg = output_path.read_text()
    assert 'class="fold-line"' not in svg


def test_large_layout_exports_as_paged_svg(tmp_path):
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    groups = [
        {
            "polygons": [[(0.0, 0.0), (45.0, 0.0), (45.0, 55.0), (0.0, 55.0)]],
            "tabs": [],
            "face_numbers": [index],
        }
        for index in range(1, 46)
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    output_path = tmp_path / "large-paged-layout.svg"
    exporter = SVGExporter(
        page_format="A4",
        page_orientation="portrait",
        layout_mode="paged",
    )
    exporter.export_to_svg_paged_single_file(paged_groups, str(output_path))

    svg = output_path.read_text()
    root = ET.fromstring(svg)
    face_shapes = [
        element
        for element in root.iter()
        if element.attrib.get("class") == "face-polygon"
        and "data-face-number" in element.attrib
    ]
    assert warnings == []
    assert output_path.stat().st_size > 0
    assert f"Page {len(paged_groups)} / {len(paged_groups)}" in svg
    assert len(face_shapes) == len(groups)
