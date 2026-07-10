import asyncio
import json
import sys
from pathlib import Path

import pytest
from starlette.exceptions import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.local_demo import (
    LocalDemoStaticFiles,
    get_local_tilesets,
    get_manifest_target,
    load_manifest,
)
import services.plateau_fetcher as plateau_fetcher
from services.plateau_fetcher import BuildingInfo, geocode_address


def test_local_demo_static_files_prefers_cached_imagery(tmp_path):
    tile = tmp_path / "imagery" / "plateau-ortho-2023" / "18" / "1" / "2.png"
    tile.parent.mkdir(parents=True)
    tile.write_bytes(b"cached-ortho")
    static_files = LocalDemoStaticFiles(directory=tmp_path)

    response = asyncio.run(
        static_files.get_response(
            "imagery/plateau-ortho-2023/18/1/2.png",
            {"method": "GET", "headers": []},
        )
    )

    assert response.status_code == 200
    assert Path(response.path) == tile


def test_local_demo_static_files_falls_back_only_for_missing_imagery(tmp_path):
    static_files = LocalDemoStaticFiles(directory=tmp_path)
    scope = {"method": "GET", "headers": []}

    imagery_response = asyncio.run(
        static_files.get_response(
            "imagery/plateau-ortho-2023/18/1/missing.png",
            scope,
        )
    )
    assert imagery_response.status_code == 200
    assert imagery_response.headers["content-type"] == "image/png"
    with pytest.raises(HTTPException) as error:
        asyncio.run(static_files.get_response("3dtiles/missing.json", scope))
    assert error.value.status_code == 404


def test_local_demo_manifest_target_merges_static_and_generated_data(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "targets": {
                    "jp_tower": {
                        "mesh_code": "53394611",
                        "building_id": "bldg_test",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("LOCAL_DEMO_MANIFEST_PATH", str(manifest_path))
    load_manifest(force=True)

    target = get_manifest_target("JPタワー")

    assert target is not None
    assert target["key"] == "jp_tower"
    assert target["mesh_code"] == "53394611"
    assert target["building_id"] == "bldg_test"
    assert target["municipality_code"] == "13101"


def test_local_demo_tilesets_are_rewritten_to_local_urls(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tilesets": [
                    {
                        "municipality_code": "13113",
                        "municipality_name": "渋谷区",
                        "lod": 1,
                        "local_path": "3dtiles/13113/lod1/tileset.json",
                        "mesh_codes": ["53393586"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("LOCAL_DEMO_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("LOCAL_DEMO_PUBLIC_BASE_URL", "http://localhost:8001/local-demo-cache")
    load_manifest(force=True)

    tilesets = get_local_tilesets(["53393586"], lod=1, municipality_code="13113")

    assert len(tilesets) == 1
    assert tilesets[0]["tileset_url"] == (
        "http://localhost:8001/local-demo-cache/3dtiles/13113/lod1/tileset.json"
    )


def test_local_demo_geocode_uses_static_target_without_network(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"targets": {}}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setenv("ENV", "local_demo")
    monkeypatch.setenv("LOCAL_DEMO_MANIFEST_PATH", str(manifest_path))
    load_manifest(force=True)

    result = geocode_address("渋谷フクラス")

    assert result is not None
    assert result.osm_type == "local_demo"
    assert result.latitude == 35.65806


def test_local_demo_cache_config_defaults_to_bundled_cache(monkeypatch):
    monkeypatch.setenv("ENV", "local_demo")
    monkeypatch.delenv("CITYGML_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("CITYGML_CACHE_DIR", raising=False)

    config = plateau_fetcher._get_cache_config()

    assert config["enabled"] is True
    assert config["cache_dir"].name == "citygml_cache"
    assert config["cache_dir"].parent.name == "local_demo_cache"


def test_local_demo_search_uses_manifest_building_and_mesh(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "targets": {
                    "jp_tower": {
                        "mesh_code": "53394611",
                        "building_id": "bldg_manifest",
                        "municipality_code": "13102",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV", "local_demo")
    monkeypatch.setenv("LOCAL_DEMO_MANIFEST_PATH", str(manifest_path))
    load_manifest(force=True)

    calls = []

    def fake_search_building_by_id_and_mesh(building_id, mesh_code, **kwargs):
        calls.append((building_id, mesh_code, kwargs))
        return {
            "success": True,
            "building": BuildingInfo(
                building_id=None,
                gml_id="bldg_manifest",
                latitude=35.67989,
                longitude=139.76479,
                distance_meters=12.3,
            ),
            "citygml_xml": "<CityModel />",
        }

    monkeypatch.setattr(
        plateau_fetcher,
        "search_building_by_id_and_mesh",
        fake_search_building_by_id_and_mesh,
    )

    result = plateau_fetcher.search_buildings_by_address("JPタワー", limit=20)

    assert result["success"] is True
    assert calls == [
        (
            "bldg_manifest",
            "53394611",
            {"debug": False, "include_building_info": True},
        )
    ]
    building = result["buildings"][0]
    assert building.gml_id == "bldg_manifest"
    assert building.name == "JPタワー"
    assert building.municipality_code == "13102"
    assert building.match_reason == "local_demo"
