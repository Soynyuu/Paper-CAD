"""Regression tests for mesh-neighbor fallback in building ID search."""

from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_fetcher import search_building_by_id_and_mesh  # noqa: E402


@patch("services.plateau_fetcher._find_building_id_in_xml")
@patch("services.plateau_fetcher._fetch_citygml_by_mesh_code_with_sources")
def test_search_building_by_id_and_mesh_falls_back_to_neighbor_mesh(
    mock_fetch, mock_find
):
    """When the requested mesh misses, nearby meshes should be checked before failing."""
    target_id = "bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674"
    requested_mesh = "53393585"
    neighbor_mesh = "53393586"
    xml_by_mesh = {
        requested_mesh: "<CityModel id='requested' />",
        neighbor_mesh: "<CityModel id='neighbor' />",
    }

    def fake_fetch(mesh_code: str, timeout: int = 30):
        xml = xml_by_mesh.get(mesh_code)
        if xml is None:
            return None
        return xml, [f"https://example.invalid/{mesh_code}.gml"]

    def fake_find(xml_content: str, target_id_arg: str, debug: bool = False):
        """Return gml:id only when the neighbor XML contains the target building."""
        if xml_content == xml_by_mesh[neighbor_mesh]:
            return target_id
        return None

    mock_fetch.side_effect = fake_fetch
    mock_find.side_effect = fake_find

    result = search_building_by_id_and_mesh(target_id, requested_mesh)

    assert result["success"] is True
    assert result["matched_gml_id"] == target_id
    assert result["mesh_code"] == neighbor_mesh

    called_meshes = [call.args[0] for call in mock_fetch.call_args_list]
    assert requested_mesh in called_meshes
    assert neighbor_mesh in called_meshes
