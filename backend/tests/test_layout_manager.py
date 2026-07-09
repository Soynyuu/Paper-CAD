import copy
import json
import math

import pytest

from core.layout_manager import LayoutManager, SHAPELY_AVAILABLE


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


def _l_shape(width: float, height: float, leg: float):
    return [
        (0.0, 0.0),
        (width, 0.0),
        (width, leg),
        (leg, leg),
        (leg, height),
        (0.0, height),
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


def test_layout_transforms_fold_lines_with_group():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    group = {
        "polygons": [_rect(260.0, 100.0)],
        "tabs": [],
        "fold_lines": [[(10.0, 0.0), (10.0, 100.0)]],
    }

    translated = manager._translate_group(group, 5.0, 7.0)
    rotated = manager._rotate_group(group, 90.0)

    assert translated["fold_lines"][0][0] == pytest.approx((15.0, 7.0))
    assert translated["fold_lines"][0][1] == pytest.approx((15.0, 107.0))
    assert rotated["fold_lines"][0][0] == pytest.approx((0.0, 10.0))
    assert rotated["fold_lines"][0][1] == pytest.approx((-100.0, 10.0))


def test_layout_for_pages_sorts_by_oriented_footprint_not_raw_bbox():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rotated_rect(200.0, 5.0, 45.0)], "tabs": [], "face_numbers": [1]},
        {"polygons": [_rect(120.0, 80.0)], "tabs": [], "face_numbers": [2]},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert paged_groups[0][0]["face_numbers"] == [2]


def test_layout_for_pages_fills_current_page_with_later_fitting_groups():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(190.0, 150.0)], "tabs": [], "face_numbers": [1]},
        {"polygons": [_rect(130.0, 130.0)], "tabs": [], "face_numbers": [2]},
        {"polygons": [_rect(60.0, 120.0)], "tabs": [], "face_numbers": [3]},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert [group["face_numbers"] for group in paged_groups[0]] == [[1], [3]]
    assert [group["face_numbers"] for group in paged_groups[1]] == [[2]]


def test_layout_for_pages_packs_four_medium_rectangles_on_one_page():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(90.0, 130.0)], "tabs": [], "face_numbers": [index]}
        for index in range(1, 5)
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert len(paged_groups) == 1
    assert len(paged_groups[0]) == 4
    assert all(group["layout_rotation"] == 0 for group in paged_groups[0])


def test_layout_for_pages_uses_free_rectangles_for_mixed_columns():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(120.0, 130.0)], "tabs": [], "face_numbers": [1]},
        {"polygons": [_rect(60.0, 130.0)], "tabs": [], "face_numbers": [2]},
        {"polygons": [_rect(120.0, 130.0)], "tabs": [], "face_numbers": [3]},
        {"polygons": [_rect(60.0, 130.0)], "tabs": [], "face_numbers": [4]},
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert len(paged_groups) == 1
    assert [group["face_numbers"] for group in paged_groups[0]] == [
        [1],
        [2],
        [3],
        [4],
    ]


def test_layout_for_pages_combines_rotation_and_ordering_to_reduce_page_count():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")

    groups = [
        {"polygons": [_rect(100.0, 85.0)], "tabs": [], "face_numbers": [1]},
        {"polygons": [_rect(75.0, 55.0)], "tabs": [], "face_numbers": [2]},
        {"polygons": [_rect(65.0, 155.0)], "tabs": [], "face_numbers": [3]},
        {"polygons": [_rect(85.0, 50.0)], "tabs": [], "face_numbers": [4]},
        {"polygons": [_rect(45.0, 95.0)], "tabs": [], "face_numbers": [5]},
    ]
    for group in groups:
        group["bbox"] = manager.calculate_group_bbox(group)

    orthogonal_manager = LayoutManager(page_format="A4", page_orientation="portrait")
    orthogonal_manager._packing_orientations = (
        lambda group: orthogonal_manager._layout_orientations(
            group, orthogonal_only=True
        )
    )
    area_ordered = sorted(groups, key=orthogonal_manager._layout_sort_key, reverse=True)
    area_only_pages = orthogonal_manager._pack_groups_in_order(
        area_ordered, margin=5, allow_overflow=False
    )
    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert area_only_pages is not None
    assert len(area_only_pages) == 2
    assert len(paged_groups) == 1
    assert len(paged_groups[0]) == 5


@pytest.mark.skipif(not SHAPELY_AVAILABLE, reason="polygon-aware packing requires shapely")
def test_layout_for_pages_interlocks_concave_polygons_with_overlapping_bboxes():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    groups = [
        {"polygons": [_l_shape(120.0, 120.0, 40.0)], "tabs": [], "face_numbers": [index]}
        for index in range(1, 4)
    ]

    bbox_only_manager = LayoutManager(page_format="A4", page_orientation="portrait")
    bbox_only_manager._should_use_polygon_fit = lambda group, bbox: False
    bbox_only_pages, bbox_only_warnings = bbox_only_manager.layout_for_pages(
        copy.deepcopy(groups)
    )
    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert bbox_only_warnings == []
    assert len(bbox_only_pages) == 2
    assert len(paged_groups) == 1
    assert len(paged_groups[0]) == 3
    assert any(group["layout_rotation"] == 180 for group in paged_groups[0])

    geometries = [
        manager._merge_group_polygons(manager._group_collision_polygons(group))
        for group in paged_groups[0]
    ]
    for index, geometry in enumerate(geometries):
        for other in geometries[index + 1 :]:
            assert geometry.intersection(other).area <= 1e-6


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


def test_large_layout_bounds_rotation_search_and_returns_serializable_groups(
    monkeypatch,
):
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    groups = [
        {"polygons": [_rect(20.0, 30.0)], "tabs": [], "face_numbers": [index]}
        for index in range(41)
    ]
    rotate_group = manager._rotate_group
    rotation_count = 0

    def counted_rotate(group, angle_degrees):
        nonlocal rotation_count
        rotation_count += 1
        return rotate_group(group, angle_degrees)

    monkeypatch.setattr(manager, "_rotate_group", counted_rotate)

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert warnings == []
    assert sum(len(page) for page in paged_groups) == len(groups)
    assert rotation_count <= len(groups) * 14
    assert all(
        "_layout_collision_geometry" not in group
        for page in paged_groups
        for group in page
    )
    json.dumps(paged_groups)


def test_layout_for_pages_skips_degenerate_groups_without_creating_empty_page():
    manager = LayoutManager(page_format="A4", page_orientation="portrait")
    groups = [
        {"polygons": [_rect(80.0, 60.0)], "tabs": [], "face_numbers": [1]},
        {
            "polygons": [[(0.0, 0.0), (40.0, 0.0), (80.0, 0.0)]],
            "tabs": [],
            "face_numbers": [2],
        },
    ]

    paged_groups, warnings = manager.layout_for_pages(groups)

    assert len(paged_groups) == 1
    assert [group["face_numbers"] for group in paged_groups[0]] == [[1]]
    assert warnings[-1]["type"] == "degenerate_groups_skipped"
    assert warnings[-1]["details"]["face_numbers"] == [2]
