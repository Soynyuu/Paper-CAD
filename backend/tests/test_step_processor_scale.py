import pytest
import math
import numpy as np

from models.request_models import BrepPapercraftRequest
from core.unfold_engine import UnfoldEngine
from services.step_processor import StepUnfoldGenerator


def _rect(width: float, height: float):
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


def test_unfold_engine_does_not_generate_tabs_by_default():
    engine = UnfoldEngine()
    engine.faces_data = [{"boundary_curves": [[(0.0, 0.0), (10.0, 0.0)]]}]

    assert engine._generate_tabs_for_group([0]) == []


def test_generator_reuses_analysis_within_same_loaded_model(monkeypatch):
    generator = StepUnfoldGenerator()
    generator.solid_shape = object()
    generator._file_hash = None
    analyze_calls = 0

    def fake_analyze(_shape):
        nonlocal analyze_calls
        analyze_calls += 1

    monkeypatch.setattr(
        generator.geometry_analyzer,
        "analyze_brep_topology",
        fake_analyze,
    )

    generator.analyze_brep_topology()
    generator.analyze_brep_topology()

    assert analyze_calls == 1


def _plane_face(boundary, face_number=1, origin=None, normal=None):
    return {
        "unfoldable": True,
        "surface_type": "plane",
        "plane_normal": normal or [0.0, 0.0, 1.0],
        "plane_origin": origin or [0.0, 0.0, 0.0],
        "boundary_curves": [boundary],
        "face_number": face_number,
    }


def _arc_wall_face(radius, start_deg, end_deg, height=12.0, face_number=1):
    start = math.radians(start_deg)
    end = math.radians(end_deg)
    mid = (start + end) / 2.0
    p0 = (radius * math.cos(start), radius * math.sin(start), 0.0)
    p1 = (radius * math.cos(end), radius * math.sin(end), 0.0)
    p2 = (radius * math.cos(end), radius * math.sin(end), height)
    p3 = (radius * math.cos(start), radius * math.sin(start), height)
    return {
        "unfoldable": True,
        "surface_type": "plane",
        "plane_normal": [math.cos(mid), math.sin(mid), 0.0],
        "plane_origin": p0,
        "boundary_curves": [[p0, p1, p2, p3]],
        "face_number": face_number,
    }


def test_default_unfold_groups_merge_adjacent_coplanar_faces():
    generator = StepUnfoldGenerator()
    generator.faces_data = [
        {
            "unfoldable": True,
            "surface_type": "plane",
            "plane_normal": [0.0, 0.0, 1.0],
            "plane_origin": [0.0, 0.0, 0.0],
        },
        {
            "unfoldable": True,
            "surface_type": "plane",
            "plane_normal": [0.0, 0.0, 1.0],
            "plane_origin": [1.0, 0.0, 0.0],
        },
    ]
    generator.edges_data = []
    generator.unfold_engine.set_geometry_data(
        generator.faces_data,
        generator.edges_data,
        {0: {1}, 1: {0}},
    )

    groups = generator.group_faces_for_unfolding()

    assert groups == [[0, 1]]


def test_coplanar_unfold_unions_split_triangles_into_single_outer_ring():
    engine = UnfoldEngine()
    engine.set_geometry_data(
        [
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                face_number=1,
            ),
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
                face_number=2,
            ),
        ],
        [],
        {0: {1}, 1: {0}},
    )

    groups = engine.group_faces_for_unfolding()
    unfolded = engine.unfold_face_groups()

    assert groups == [[0, 1]]
    assert len(unfolded) == 1
    assert len(unfolded[0]["polygons"]) == 1
    assert len(unfolded[0]["polygons"][0]) == 4
    assert set(unfolded[0]["face_numbers"]) == {1, 2}


def test_legacy_merge_mode_keeps_split_coplanar_polygons():
    engine = UnfoldEngine()
    engine.merge_mode = "legacy"
    engine.set_geometry_data(
        [
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                face_number=1,
            ),
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
                face_number=2,
            ),
        ],
        [],
        {0: {1}, 1: {0}},
    )

    engine.group_faces_for_unfolding()
    unfolded = engine.unfold_face_groups()

    assert len(unfolded) == 1
    assert len(unfolded[0]["polygons"]) == 2


def test_curved_wall_strip_unfolds_to_smooth_exact_rectangle():
    engine = UnfoldEngine()
    faces = [
        _arc_wall_face(20.0, angle, angle + 10.0, face_number=index + 1)
        for index, angle in enumerate([0.0, 10.0, 20.0, 30.0, 40.0])
    ]
    adjacency = {
        0: {1},
        1: {0, 2},
        2: {1, 3},
        3: {2, 4},
        4: {3},
    }
    engine.set_geometry_data(faces, [], adjacency)

    engine.group_faces_for_unfolding()
    unfolded = engine.unfold_face_groups()

    assert len(unfolded) == 1
    group = unfolded[0]
    assert group["unfold_method"] == "reconstructed_cylinder_unwrap"
    assert len(group["polygons"]) == 1
    assert group["fold_lines"] == []
    assert group["polygons"][0][0] == pytest.approx((0.0, 0.0))
    assert group["polygons"][0][2][1] == pytest.approx(12.0)
    assert group["polygons"][0][1][0] == pytest.approx(20.0 * math.radians(50.0))


def test_faceted_curved_wall_generates_tolerance_based_fold_lines():
    engine = UnfoldEngine()
    engine.curve_mode = "faceted"
    engine.curve_tolerance = 0.5
    faces = [
        _arc_wall_face(20.0, angle, angle + 10.0, face_number=index + 1)
        for index, angle in enumerate([0.0, 10.0, 20.0, 30.0, 40.0])
    ]
    engine.set_geometry_data(
        faces, [], {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
    )

    result = engine._try_unfold_curved_wall_strip(0, [0, 1, 2, 3, 4])

    assert result is not None
    assert result["unfold_method"] == "reconstructed_cylinder_unwrap"
    assert len(result["fold_lines"]) > 0


def test_closed_cylinder_keeps_full_circumference_across_angle_seam():
    engine = UnfoldEngine()
    faces = [
        _arc_wall_face(20.0, angle, angle + 10.0, face_number=index + 1)
        for index, angle in enumerate(range(0, 360, 10))
    ]
    adjacency = {
        index: {(index - 1) % len(faces), (index + 1) % len(faces)}
        for index in range(len(faces))
    }
    engine.set_geometry_data(faces, [], adjacency)

    result = engine._try_unfold_curved_wall_strip(0, list(range(len(faces))))

    assert result is not None
    assert result["polygons"][0][1][0] == pytest.approx(2.0 * math.pi * 20.0)


def test_split_conical_wall_reconstructs_to_annular_sector():
    engine = UnfoldEngine()
    faces = []
    for index, start_degrees in enumerate([0.0, 10.0, 20.0, 30.0, 40.0]):
        start = math.radians(start_degrees)
        end = math.radians(start_degrees + 10.0)
        middle = (start + end) / 2.0
        points = [
            (20.0 * math.cos(start), 20.0 * math.sin(start), 0.0),
            (20.0 * math.cos(end), 20.0 * math.sin(end), 0.0),
            (30.0 * math.cos(end), 30.0 * math.sin(end), 10.0),
            (30.0 * math.cos(start), 30.0 * math.sin(start), 10.0),
        ]
        normal = np.array([math.cos(middle), math.sin(middle), -1.0])
        normal /= np.linalg.norm(normal)
        faces.append(_plane_face(points, face_number=index + 1, normal=normal.tolist()))
    engine.set_geometry_data(
        faces, [], {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
    )

    result = engine._try_unfold_curved_wall_strip(0, [0, 1, 2, 3, 4])

    assert result is not None
    assert result["unfold_method"] == "reconstructed_cone_unwrap"
    assert len(result["polygons"][0]) > 8


def test_curved_wall_strip_is_disabled_in_legacy_mode():
    engine = UnfoldEngine()
    engine.merge_mode = "legacy"
    faces = [
        _arc_wall_face(20.0, angle, angle + 10.0, face_number=index + 1)
        for index, angle in enumerate([0.0, 10.0, 20.0, 30.0, 40.0])
    ]
    engine.set_geometry_data(
        faces,
        [],
        {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}},
    )

    engine.group_faces_for_unfolding()
    unfolded = engine.unfold_face_groups()

    assert not str(unfolded[0].get("unfold_method", "")).startswith("reconstructed_")


def test_straight_wall_strip_does_not_use_curved_unwrap():
    engine = UnfoldEngine()
    faces = [
        {
            "unfoldable": True,
            "surface_type": "plane",
            "plane_normal": [0.0, -1.0, 0.0],
            "plane_origin": [index * 10.0, 0.0, 0.0],
            "boundary_curves": [
                [
                    (index * 10.0, 0.0, 0.0),
                    ((index + 1) * 10.0, 0.0, 0.0),
                    ((index + 1) * 10.0, 0.0, 12.0),
                    (index * 10.0, 0.0, 12.0),
                ]
            ],
            "face_number": index + 1,
        }
        for index in range(5)
    ]
    engine.set_geometry_data(
        faces,
        [],
        {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}},
    )

    result = engine._try_unfold_curved_wall_strip(0, [0, 1, 2, 3, 4])

    assert result is None


def test_curved_wall_strip_rejects_mismatched_heights():
    engine = UnfoldEngine()
    faces = [
        _arc_wall_face(20.0, 0.0, 10.0, height=12.0, face_number=1),
        _arc_wall_face(20.0, 10.0, 20.0, height=12.0, face_number=2),
        _arc_wall_face(20.0, 20.0, 30.0, height=30.0, face_number=3),
    ]
    engine.set_geometry_data(faces, [], {0: {1}, 1: {0, 2}, 2: {1}})

    result = engine._try_unfold_curved_wall_strip(0, [0, 1, 2])

    assert result is None


def test_coplanar_union_preserves_holes():
    engine = UnfoldEngine()
    outer = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    hole = [(3.0, 3.0), (7.0, 3.0), (7.0, 7.0), (3.0, 7.0)]

    merged = engine._merge_coplanar_polygon_sets([[outer, hole]])

    assert len(merged) == 2
    assert sorted(len(ring) for ring in merged) == [4, 4]


def test_same_direction_adjacent_faces_on_different_planes_merge():
    engine = UnfoldEngine()
    engine.set_geometry_data(
        [
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                face_number=1,
                origin=[0.0, 0.0, 0.0],
            ),
            _plane_face(
                [(0.0, 0.0, 1.0), (10.0, 0.0, 1.0), (10.0, 10.0, 1.0)],
                face_number=2,
                origin=[0.0, 0.0, 1.0],
            ),
        ],
        [],
        {0: {1}, 1: {0}},
    )

    assert engine.group_faces_for_unfolding() == [[0, 1]]


def test_same_direction_non_adjacent_faces_on_different_planes_do_not_merge():
    engine = UnfoldEngine()
    engine.set_geometry_data(
        [
            _plane_face(
                [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
                face_number=1,
                origin=[0.0, 0.0, 0.0],
            ),
            _plane_face(
                [(0.0, 0.0, 1.0), (10.0, 0.0, 1.0), (10.0, 10.0, 1.0)],
                face_number=2,
                origin=[0.0, 0.0, 1.0],
            ),
        ],
        [],
        {0: set(), 1: set()},
    )

    assert engine.group_faces_for_unfolding() == [[0], [1]]


def test_fixed_scale_converts_unfolded_groups_to_paper_dimensions():
    generator = StepUnfoldGenerator()
    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fixed",
        )
    )

    groups, warnings = generator._prepare_groups_for_layout(
        [
            {
                "polygons": [_rect(15000.0, 3000.0)],
                "tabs": [_rect(1500.0, 300.0)],
                "fold_lines": [[(1500.0, 0.0), (1500.0, 3000.0)]],
            }
        ]
    )

    bbox = groups[0]["bbox"]
    assert bbox["width"] == pytest.approx(100.0)
    assert bbox["height"] == pytest.approx(20.0)
    assert groups[0]["tabs"][0][1][0] == pytest.approx(10.0)
    assert groups[0]["fold_lines"][0][0][0] == pytest.approx(10.0)
    assert warnings == []
    assert generator.stats["scale_mode"] == "fixed"
    assert generator.stats["applied_scale_factor"] == pytest.approx(150.0)
    assert generator.stats["source_units"] == "mm"


def test_fixed_scale_converts_meter_inputs_to_paper_millimeters():
    generator = StepUnfoldGenerator()
    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fixed",
            units="m",
        )
    )

    groups, warnings = generator._prepare_groups_for_layout(
        [{"polygons": [_rect(15.0, 3.0)], "tabs": [_rect(1.5, 0.3)]}]
    )

    bbox = groups[0]["bbox"]
    assert bbox["width"] == pytest.approx(100.0)
    assert bbox["height"] == pytest.approx(20.0)
    assert groups[0]["tabs"][0][1][0] == pytest.approx(10.0)
    assert warnings == []
    assert generator.stats["source_units"] == "m"
    assert generator.stats["unit_to_mm_factor"] == pytest.approx(1000.0)


def test_fit_page_scale_uses_selected_page_orientation():
    generator = StepUnfoldGenerator()
    groups = [{"polygons": [_rect(3000.0, 1000.0)], "tabs": []}]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    portrait_groups, portrait_warnings = generator._prepare_groups_for_layout(groups)
    portrait_scale = generator.applied_scale_factor
    portrait_printable_height = generator.layout_manager.printable_height_mm

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="landscape",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    landscape_groups, landscape_warnings = generator._prepare_groups_for_layout(groups)
    landscape_scale = generator.applied_scale_factor
    landscape_printable_width = generator.layout_manager.printable_width_mm

    assert portrait_groups[0]["bbox"]["width"] == pytest.approx(portrait_printable_height)
    assert landscape_groups[0]["bbox"]["width"] == pytest.approx(landscape_printable_width)
    assert portrait_warnings[0]["type"] == "fit_page_scale_applied"
    assert landscape_warnings[0]["type"] == "fit_page_scale_applied"
    assert portrait_scale < 3000.0 / generator.layout_manager.page_sizes_mm["A4"]["width"]
    assert landscape_scale == pytest.approx(portrait_scale)


def test_fit_page_scale_respects_meter_units():
    generator = StepUnfoldGenerator()
    groups = [{"polygons": [_rect(30.0, 10.0)], "tabs": []}]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
            units="m",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert paper_groups[0]["bbox"]["width"] == pytest.approx(
        generator.layout_manager.printable_height_mm
    )
    assert warnings[0]["type"] == "fit_page_scale_applied"
    assert generator.stats["applied_scale_factor"] == pytest.approx(
        30000.0 / generator.layout_manager.printable_height_mm
    )


def test_fit_page_scale_can_enlarge_small_models_beyond_one_to_one():
    generator = StepUnfoldGenerator()
    groups = [{"polygons": [_rect(30.0, 10.0)], "tabs": []}]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
            units="mm",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert generator.applied_scale_factor < 1.0
    assert paper_groups[0]["bbox"]["width"] == pytest.approx(
        generator.layout_manager.printable_height_mm
    )
    assert warnings[0]["type"] == "fit_page_scale_applied"


def test_fit_page_splits_extreme_multi_ring_groups_before_scaling():
    generator = StepUnfoldGenerator()
    groups = [
        {
            "polygons": [
                [(0.0, 0.0), (100.0, 0.0), (100.0, 1.0), (0.0, 1.0)],
                [(500.0, 0.0), (600.0, 0.0), (600.0, 1.0), (500.0, 1.0)],
            ],
            "tabs": [],
            "face_indices": [0, 1],
            "face_numbers": [10, 11],
        }
    ]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
            units="m",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert len(paper_groups) == 2
    assert generator.applied_scale_factor < (
        600000.0 / generator.layout_manager.printable_height_mm
    )
    assert generator.applied_scale_factor > 0
    assert warnings[0]["type"] == "fit_page_scale_applied"


def test_legacy_merge_mode_keeps_extreme_multi_ring_group_for_scaling():
    generator = StepUnfoldGenerator()
    groups = [
        {
            "polygons": [
                [(0.0, 0.0), (100.0, 0.0), (100.0, 1.0), (0.0, 1.0)],
                [(500.0, 0.0), (600.0, 0.0), (600.0, 1.0), (500.0, 1.0)],
            ],
            "tabs": [],
            "face_indices": [0, 1],
            "face_numbers": [10, 11],
        }
    ]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
            units="m",
            merge_mode="legacy",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert len(paper_groups) == 1
    assert generator.applied_scale_factor > 1000
    assert warnings[0]["type"] == "fit_page_scale_applied"


def test_fit_page_scale_includes_tabs_in_largest_part():
    generator = StepUnfoldGenerator()
    groups = [
        {
            "polygons": [_rect(180.0, 260.0)],
            "tabs": [[(180.0, 0.0), (205.0, 0.0), (205.0, 20.0), (180.0, 20.0)]],
        }
    ]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    assert generator.applied_scale_factor > 1.0
    assert warnings[0]["type"] == "fit_page_scale_applied"
    assert generator.layout_manager.can_pack_groups_on_single_page(paper_groups)


def test_fit_page_scale_uses_largest_single_group_not_single_page_packing():
    generator = StepUnfoldGenerator()
    groups = [
        {"polygons": [_rect(1000.0, 1000.0)], "tabs": []},
        {"polygons": [_rect(1000.0, 1000.0)], "tabs": []},
    ]

    generator.apply_request_settings(
        BrepPapercraftRequest(
            layout_mode="paged",
            page_format="A4",
            page_orientation="portrait",
            scale_factor=150.0,
            scale_mode="fit_page",
        )
    )
    paper_groups, warnings = generator._prepare_groups_for_layout(groups)

    individual_only_scale = 1000.0 / generator.layout_manager.printable_width_mm
    assert generator.applied_scale_factor == pytest.approx(individual_only_scale)
    assert not generator.layout_manager.can_pack_groups_on_single_page(paper_groups)
    assert warnings[0]["type"] == "fit_page_scale_applied"
