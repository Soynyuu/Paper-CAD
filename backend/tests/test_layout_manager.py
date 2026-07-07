import pytest

from core.layout_manager import LayoutManager


def _rect(width: float, height: float):
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def _flatten_pages(paged_groups):
    return [group for page in paged_groups for group in page]


def test_layout_for_pages_warns_without_rescaling_oversized_groups():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(80.0, 40.0)], "tabs": []},
        {"polygons": [_rect(240.0, 60.0)], "tabs": []},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    all_groups = _flatten_pages(paged_groups)

    widths = sorted(group["bbox"]["width"] for group in all_groups)
    assert widths[0] == pytest.approx(80.0)
    assert widths[1] == pytest.approx(240.0)

    assert any(warning["type"] == "page_overflow" for warning in warnings)


def test_layout_for_pages_keeps_scale_when_groups_fit_width():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(120.0, 80.0)], "tabs": []},
        {"polygons": [_rect(90.0, 50.0)], "tabs": []},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    all_groups = _flatten_pages(paged_groups)

    widths = sorted(group["bbox"]["width"] for group in all_groups)
    assert widths == pytest.approx([90.0, 120.0])
    assert warnings == []
