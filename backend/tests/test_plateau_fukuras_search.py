"""Regression tests for Shibuya Fukuras search handling."""

from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_fetcher import (  # noqa: E402
    BuildingInfo,
    _is_shibuya_fukuras_query,
    search_buildings_by_address,
)


def test_is_shibuya_fukuras_query_variants():
    """The Fukuras detector should accept common notation variants."""
    assert _is_shibuya_fukuras_query("渋谷フクラス")
    assert _is_shibuya_fukuras_query("渋谷ふくらす")
    assert _is_shibuya_fukuras_query("渋谷ﾌｸﾗｽ")
    assert _is_shibuya_fukuras_query("Shibuya fukuras")
    assert not _is_shibuya_fukuras_query("渋谷スクランブルスクエア")


@patch("services.plateau_fetcher.search_building_by_id_and_mesh")
def test_search_buildings_by_address_hiragana_fukuras_sets_municipality_code(mock_search_by_id_and_mesh):
    """Hiragana query should use Fukuras fast-path and inject Shibuya code for UI tileset loading."""
    mock_search_by_id_and_mesh.return_value = {
        "success": True,
        "building": BuildingInfo(
            building_id=None,
            gml_id="bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674",
            latitude=35.65806,
            longitude=139.70028,
            distance_meters=0.0,
            height=35.0,
            usage="402",
        ),
        "citygml_xml": "<CityModel />",
    }

    result = search_buildings_by_address("渋谷ふくらす", radius=0.001, limit=1, search_mode="hybrid")

    assert result["success"] is True
    assert len(result["buildings"]) == 1
    building = result["buildings"][0]
    assert building.gml_id == "bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674"
    assert building.building_id == "13113-bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674"
    assert building.name == "渋谷フクラス"
    assert result["geocoding"].osm_type == "hardcoded"
    assert result["citygml_xml"] == "<CityModel />"
