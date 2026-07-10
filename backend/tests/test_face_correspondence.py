from services.step_processor import StepUnfoldGenerator, match_source_face_descriptors
from core.geometry_analyzer import GeometryAnalyzer
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods


def _face(center, area=4.0, normal=(0.0, 0.0, 1.0)):
    return {
        "match_centroid": list(center),
        "centroid": list(center),
        "area": area,
        "normal_vector": list(normal),
    }


def _source(node, index, number, center, area=4.0, normal=(0.0, 0.0, 1.0)):
    return {
        "nodeIndex": node,
        "faceIndex": index,
        "faceNumber": number,
        "centroid": list(center),
        "area": area,
        "normal": list(normal),
        "bounds": {
            "min": [center[0] - 2.0, center[1] - 2.0, center[2] - 0.01],
            "max": [center[0] + 2.0, center[1] + 2.0, center[2] + 0.01],
        },
        "meshPositions": [
            center[0] - 2.0, center[1] - 2.0, center[2],
            center[0] + 2.0, center[1] - 2.0, center[2],
            center[0], center[1] + 2.0, center[2],
        ],
        "meshIndices": [0, 1, 2],
    }


def test_matches_faces_after_step_reorders_them():
    faces = [_face((10.0, 0.0, 0.0)), _face((0.0, 0.0, 0.0))]
    sources = [
        _source(0, 0, 1, (0.0, 0.0, 0.0)),
        _source(0, 1, 2, (10.0, 0.0, 0.0)),
    ]

    matches, unmatched = match_source_face_descriptors(faces, sources)

    assert sorted(matches) == [(0, 1), (1, 0)]
    assert unmatched == []


def test_deterministically_matches_coincident_faces_by_source_order():
    faces = [_face((0.0, 0.0, 0.0)), _face((0.0, 0.0, 0.0))]
    sources = [
        _source(0, 0, 1, (0.0, 0.0, 0.0)),
        _source(1, 0, 2, (0.0, 0.0, 0.0)),
    ]

    matches, unmatched = match_source_face_descriptors(faces, sources)

    assert matches == [(0, 0), (1, 1)]
    assert unmatched == []


def test_multiple_step_fragments_share_one_source_face_number():
    faces = [
        _face((-0.5, -0.5, 0.0), area=1.0),
        _face((0.5, -0.5, 0.0), area=1.0),
    ]
    sources = [_source(0, 4, 9, (0.0, 0.0, 0.0), area=4.0)]

    matches, unmatched = match_source_face_descriptors(faces, sources)

    assert matches == [(0, 0), (1, 0)]
    assert unmatched == []

    generator = StepUnfoldGenerator()
    generator.faces_data = faces
    generator._source_face_descriptors = sources
    generator._match_source_face_descriptors()
    assert generator.get_face_numbers() == [
        {"faceIndex": 4, "faceNumber": 9, "nodeIndex": 0},
        {"faceIndex": 4, "faceNumber": 9, "nodeIndex": 0},
    ]


def test_rejects_face_outside_matching_tolerance():
    faces = [_face((100.0, 0.0, 0.0))]
    sources = [_source(0, 0, 1, (0.0, 0.0, 0.0))]

    matches, unmatched = match_source_face_descriptors(faces, sources)

    assert matches == []
    assert unmatched == [0]


def test_generator_returns_original_node_and_face_indices():
    generator = StepUnfoldGenerator()
    generator.faces_data = [_face((10.0, 0.0, 0.0)), _face((0.0, 0.0, 0.0))]
    generator._source_face_descriptors = [
        _source(3, 7, 1, (0.0, 0.0, 0.0)),
        _source(4, 2, 2, (10.0, 0.0, 0.0)),
    ]

    generator._match_source_face_descriptors()

    assert generator.get_face_numbers() == [
        {"faceIndex": 2, "faceNumber": 2, "nodeIndex": 4},
        {"faceIndex": 7, "faceNumber": 1, "nodeIndex": 3},
    ]


def test_generator_does_not_create_synthetic_number_for_unmatched_step_face():
    generator = StepUnfoldGenerator()
    generator.faces_data = [_face((100.0, 0.0, 0.0))]
    generator._source_face_descriptors = [_source(0, 0, 1, (0.0, 0.0, 0.0))]

    generator._match_source_face_descriptors()

    assert generator.faces_data[0]["face_number"] is None
    assert generator.get_face_numbers() == []


def test_generator_returns_only_numbers_present_in_exported_groups():
    generator = StepUnfoldGenerator()
    generator.faces_data = [
        {"face_number": 10, "source_face_index": 2, "source_node_index": 0},
        {"face_number": 20, "source_face_index": 3, "source_node_index": 0},
    ]

    generator._remember_exported_face_numbers(
        [{"polygons": [[(0, 0), (1, 0), (0, 1)]], "face_numbers": [20]}]
    )

    assert generator.get_face_numbers() == [
        {"faceIndex": 3, "faceNumber": 20, "nodeIndex": 0}
    ]


def test_geometry_analyzer_uses_real_surface_area_and_center_of_mass():
    box = BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    face = topods.Face(explorer.Current())

    analyzed = GeometryAnalyzer()._analyze_face_geometry(face, 0)

    assert analyzed["area"] in {6.0, 8.0, 12.0}
    assert all(abs(value) < 10.0 for value in analyzed["centroid"])
