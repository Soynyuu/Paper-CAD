import xml.etree.ElementTree as ET

import pytest

from models.request_models import (
    PlateauBuildingIdWithMeshRequest,
    PlateauTexturedUnfoldRequest,
)
from services.citygml.core.types import LODExtractionResult
from services.citygml.lod import extractor
from services.citygml.pipeline.shape_cache import ShapeCache
from services.plateau_fetcher import _detect_lod_levels


def _empty_result(level: str) -> LODExtractionResult:
    return LODExtractionResult([], [], level, f"{level} unavailable")


@pytest.mark.parametrize(
    ("lod_target", "expected_order"),
    [
        ("auto", ["LOD3", "LOD2", "LOD1"]),
        ("LOD2", ["LOD2", "LOD1"]),
        ("LOD1", ["LOD1"]),
    ],
)
def test_lod_target_controls_extraction_order(monkeypatch, lod_target, expected_order):
    calls = []

    def strategy(level):
        def run(*args, **kwargs):
            calls.append(level)
            return _empty_result(level)

        return run

    monkeypatch.setattr(extractor, "compute_building_tolerance", lambda *args: 0.01)
    monkeypatch.setattr(extractor, "extract_lod3_geometry", strategy("LOD3"))
    monkeypatch.setattr(extractor, "extract_lod2_geometry", strategy("LOD2"))
    monkeypatch.setattr(extractor, "extract_lod1_geometry", strategy("LOD1"))

    extractor.extract_building_geometry(
        ET.Element("Building"), None, {}, lod_target=lod_target
    )

    assert calls == expected_order


def test_lod2_falls_back_to_lod1(monkeypatch):
    monkeypatch.setattr(extractor, "compute_building_tolerance", lambda *args: 0.01)
    monkeypatch.setattr(
        extractor, "extract_lod2_geometry", lambda *args, **kwargs: _empty_result("LOD2")
    )
    monkeypatch.setattr(
        extractor,
        "extract_lod1_geometry",
        lambda *args, **kwargs: LODExtractionResult([object()], [], "LOD1", "lod1Solid"),
    )

    result = extractor.extract_building_geometry(
        ET.Element("Building"), None, {}, lod_target="LOD2"
    )

    assert result.lod_level == "LOD1"


def test_detects_each_available_lod_level():
    building = ET.fromstring(
        """
        <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
          <bldg:lod1Solid />
          <bldg:lod2MultiSurface />
          <bldg:lod3Geometry />
        </bldg:Building>
        """
    )

    assert _detect_lod_levels(building) == (True, True, True)


def test_shape_cache_separates_lod_targets():
    cache = ShapeCache(max_size=3)
    auto_shape = object()
    lod2_shape = object()
    cache.put(("bldg_1", "ultra", "minimal", "auto"), auto_shape, "LOD3")
    cache.put(("bldg_1", "ultra", "minimal", "LOD2"), lod2_shape, "LOD2")

    assert cache.get(("bldg_1", "ultra", "minimal", "auto")).shape is auto_shape
    assert cache.get(("bldg_1", "ultra", "minimal", "LOD2")).shape is lod2_shape


def test_plateau_requests_default_to_auto_and_accept_explicit_lod():
    default_request = PlateauBuildingIdWithMeshRequest(
        building_id="bldg_test", mesh_code="53393586"
    )
    unfold_request = PlateauTexturedUnfoldRequest(
        building_id="bldg_test", mesh_code="53393586", lod_target="LOD1"
    )

    assert default_request.lod_target == "auto"
    assert unfold_request.lod_target == "LOD1"

