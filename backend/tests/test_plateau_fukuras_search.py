"""Regression tests for Shibuya Fukuras search handling."""

from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_fetcher import (  # noqa: E402
    BuildingInfo,
    CityGMLFetchResult,
    GeocodingResult,
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
    assert building.municipality_code == "13113"
    assert building.name == "渋谷フクラス"
    assert result["geocoding"].osm_type == "hardcoded"
    assert result["citygml_xml"] == "<CityModel />"


@patch("services.plateau_fetcher.fetch_citygml_from_plateau_with_metadata")
@patch("services.plateau_fetcher.geocode_address")
def test_search_buildings_by_address_sets_catalog_municipality_code(
    mock_geocode,
    mock_fetch_citygml,
):
    """Search results should keep the CityGML catalog cityCode even without building_id."""
    mock_geocode.return_value = GeocodingResult(
        query="芝浦工業大学 附属中学高等学校",
        latitude=35.6591,
        longitude=139.7958,
        display_name="芝浦工業大学 附属中学高等学校",
    )
    xml = """
    <core:CityModel
        xmlns:core="http://www.opengis.net/citygml/2.0"
        xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
        xmlns:gml="http://www.opengis.net/gml">
      <core:cityObjectMember>
        <bldg:Building gml:id="bldg_ecbbb177-9b09-49b8-8186-f65e82bd06c6">
          <gml:name>芝浦工業大学附属中学高等学校</gml:name>
          <bldg:lod0FootPrint>
            <gml:MultiSurface>
              <gml:surfaceMember>
                <gml:Polygon>
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>35.6591 139.7958 35.6592 139.7958 35.6592 139.7959</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod0FootPrint>
          <bldg:lod2Solid />
        </bldg:Building>
      </core:cityObjectMember>
    </core:CityModel>
    """
    mock_fetch_citygml.return_value = CityGMLFetchResult(
        xml_content=xml,
        municipality_by_gml_id={"bldg_ecbbb177-9b09-49b8-8186-f65e82bd06c6": "13108"},
    )

    result = search_buildings_by_address(
        "芝浦工業大学 附属中学高等学校",
        radius=0.001,
        limit=1,
        name_filter="芝浦工業大学 附属中学高等学校",
        search_mode="hybrid",
    )

    assert result["success"] is True
    assert result["buildings"][0].gml_id == "bldg_ecbbb177-9b09-49b8-8186-f65e82bd06c6"
    assert result["buildings"][0].building_id is None
    assert result["buildings"][0].municipality_code == "13108"
