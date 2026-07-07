import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.local_demo import get_local_tilesets, get_manifest_target, load_manifest
from services.plateau_fetcher import geocode_address


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
