import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import prepare_local_demo_cache as prepare  # noqa: E402
from services.plateau_fetcher import BuildingInfo  # noqa: E402


def _building(gml_id: str, latitude: float, longitude: float, name: str) -> BuildingInfo:
    return BuildingInfo(
        building_id=gml_id,
        gml_id=gml_id,
        latitude=latitude,
        longitude=longitude,
        distance_meters=0.0,
        name=name,
    )


def _target() -> dict:
    return {
        "key": "jp_tower",
        "name": "JPタワー",
        "latitude": 35.67989,
        "longitude": 139.76479,
        "municipality_code": "13101",
        "mesh_code": "53394611",
        "building_id": None,
        "cached_mesh_codes": ["53394611"],
    }


def test_resolve_target_building_ignores_higher_ranked_other_municipality(monkeypatch):
    wrong = _building("wrong", 35.67989, 139.76479, "JPタワー")
    correct = _building("correct", 35.67990, 139.76480, "JPタワー")
    cached = SimpleNamespace(
        xml_content="<CityModel />",
        municipality_by_gml_id={"wrong": "13102", "correct": "13101"},
    )
    monkeypatch.setattr(prepare, "_get_wards_from_mesh", lambda _mesh: ["13101", "13102"])
    monkeypatch.setattr(
        prepare, "_load_gml_from_cache_with_metadata", lambda _mesh, _codes: cached
    )
    monkeypatch.setattr(prepare, "parse_buildings_from_citygml", lambda _xml: [wrong, correct])

    resolved = prepare.resolve_target_building(_target(), Path("unused"))

    assert resolved["building_id"] == "correct"
    assert resolved["municipality_code"] == "13101"


def test_resolve_target_building_fails_without_expected_municipality_candidate(monkeypatch):
    wrong = _building("wrong", 35.67989, 139.76479, "JPタワー")
    cached = SimpleNamespace(
        xml_content="<CityModel />",
        municipality_by_gml_id={"wrong": "13102"},
    )
    monkeypatch.setattr(prepare, "_get_wards_from_mesh", lambda _mesh: ["13101", "13102"])
    monkeypatch.setattr(
        prepare, "_load_gml_from_cache_with_metadata", lambda _mesh, _codes: cached
    )
    monkeypatch.setattr(prepare, "parse_buildings_from_citygml", lambda _xml: [wrong])

    with pytest.raises(RuntimeError, match="JPタワー.*13101"):
        prepare.resolve_target_building(_target(), Path("unused"))


def test_resolve_target_building_rejects_weak_name_match(monkeypatch):
    unnamed = _building("unnamed", 35.67989, 139.76479, "別の建物")
    cached = SimpleNamespace(
        xml_content="<CityModel />",
        municipality_by_gml_id={"unnamed": "13101"},
    )
    monkeypatch.setattr(prepare, "_get_wards_from_mesh", lambda _mesh: ["13101"])
    monkeypatch.setattr(
        prepare, "_load_gml_from_cache_with_metadata", lambda _mesh, _codes: cached
    )
    monkeypatch.setattr(prepare, "parse_buildings_from_citygml", lambda _xml: [unnamed])

    with pytest.raises(RuntimeError, match="name does not match"):
        prepare.resolve_target_building(_target(), Path("unused"))


def test_manifest_audit_rejects_target_tileset_municipality_mismatch():
    manifest = {
        "targets": {
            target.key: {
                "building_id": target.building_id or f"bldg_{target.key}",
                "mesh_code": target.mesh_code or "mesh",
                "municipality_code": "13102" if target.key == "jp_tower" else target.municipality_code,
            }
            for target in prepare.LOCAL_DEMO_TARGETS
        },
        "tilesets": [{"municipality_code": "13102"}],
    }

    with pytest.raises(RuntimeError, match="jp_tower: expected municipality 13101"):
        prepare.validate_manifest_consistency(manifest)


def test_manifest_audit_requires_every_static_target():
    with pytest.raises(RuntimeError, match="missing target jp_tower"):
        prepare.validate_manifest_consistency({"targets": {}, "tilesets": []})
