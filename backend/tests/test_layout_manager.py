import math

import pytest

from core.layout_manager import LayoutManager


def _rect(width: float, height: float):
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def _rotated_rect(width: float, height: float, angle_degrees: float):
    theta = math.radians(angle_degrees)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    return [
        (x * cos_theta - y * sin_theta, x * sin_theta + y * cos_theta)
        for x, y in _rect(width, height)
    ]


def _flatten_pages(paged_groups):
    return [group for page in paged_groups for group in page]


def test_layout_for_pages_warns_without_rescaling_oversized_groups():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(80.0, 40.0)], "tabs": []},
        {"polygons": [_rect(300.0, 240.0)], "tabs": []},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    all_groups = _flatten_pages(paged_groups)

    areas = sorted(group["bbox"]["width"] * group["bbox"]["height"] for group in all_groups)
    assert areas[0] == pytest.approx(80.0 * 40.0)
    assert areas[1] == pytest.approx(300.0 * 240.0)

    assert any(warning["type"] == "page_overflow" for warning in warnings)


def test_layout_for_pages_keeps_scale_when_groups_fit_width():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(120.0, 80.0)], "tabs": []},
        {"polygons": [_rect(90.0, 50.0)], "tabs": []},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    all_groups = _flatten_pages(paged_groups)

    areas = sorted(group["bbox"]["width"] * group["bbox"]["height"] for group in all_groups)
    assert areas == pytest.approx([90.0 * 50.0, 120.0 * 80.0])
    assert warnings == []


def test_layout_for_pages_rotates_group_when_that_makes_it_fit():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [{"polygons": [_rect(260.0, 100.0)], "tabs": []}]

    paged_groups, warnings = manager.layout_for_pages(groups)
    group = paged_groups[0][0]

    assert warnings == []
    assert group["layout_rotation"] == 90
    assert group["bbox"]["width"] == pytest.approx(100.0)
    assert group["bbox"]["height"] == pytest.approx(260.0)
    assert group["bbox"]["width"] <= manager.printable_width_mm
    assert group["bbox"]["height"] <= manager.printable_height_mm


def test_layout_for_pages_includes_tabs_in_fit_and_bbox():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {
            "polygons": [_rect(180.0, 60.0)],
            "tabs": [[(180.0, 0.0), (205.0, 0.0), (205.0, 20.0), (180.0, 20.0)]],
        }
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)
    group = paged_groups[0][0]

    assert warnings == []
    assert group["bbox"]["width"] <= manager.printable_width_mm
    assert group["bbox"]["height"] <= manager.printable_height_mm


def test_required_scale_to_fit_group_uses_oblique_rotation_candidates():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    group = {"polygons": [_rotated_rect(260.0, 100.0, 30.0)], "tabs": []}

    scale = manager.required_scale_to_fit_group(
        group, manager.printable_width_mm, manager.printable_height_mm
    )

    zero_ninety_scale = min(
        max(
            manager.calculate_group_bbox(group)["width"] / manager.printable_width_mm,
            manager.calculate_group_bbox(group)["height"] / manager.printable_height_mm,
        ),
        max(
            manager.calculate_group_bbox(manager._rotate_group(group, 90.0))["width"]
            / manager.printable_width_mm,
            manager.calculate_group_bbox(manager._rotate_group(group, 90.0))["height"]
            / manager.printable_height_mm,
        ),
    )
    assert scale < zero_ninety_scale


def test_can_pack_groups_on_single_page_requires_actual_packing_not_only_individual_fit():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    individually_fit_but_not_together = [
        {"polygons": [_rect(190.0, 190.0)], "tabs": []},
        {"polygons": [_rect(190.0, 190.0)], "tabs": []},
    ]
    scaled_to_pack = [
        {"polygons": [_rect(130.0, 130.0)], "tabs": []},
        {"polygons": [_rect(130.0, 130.0)], "tabs": []},
    ]

    assert not manager.can_pack_groups_on_single_page(individually_fit_but_not_together)
    assert manager.can_pack_groups_on_single_page(scaled_to_pack)
