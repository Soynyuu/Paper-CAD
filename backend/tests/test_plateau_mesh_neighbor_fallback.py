"""Regression tests for mesh-neighbor fallback in building ID search."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import sys

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_fetcher import search_building_by_id_and_mesh  # noqa: E402
from services.plateau_fetcher import _query_plateau_catalog_api  # noqa: E402


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


@patch("services.plateau_fetcher._find_building_id_in_xml")
@patch("services.plateau_fetcher._fetch_citygml_by_mesh_code_with_sources")
def test_fetch_failure_triggers_neighbor_fallback(mock_fetch, mock_find):
    """When the primary mesh fetch returns None (e.g., API 404 after retries),
    neighboring meshes should be tried before returning an error.

    This is the Step 3 neighbor fallback — distinct from Step 5 which only
    triggers when the fetch succeeds but the building ID isn't found.
    Regression test for GitHub issue #207.
    """
    target_id = "bldg_f0028aa3-e666-4608-8b70-4e981a45d6b5"
    primary_mesh = "53394611"
    neighbor_xml = "<CityModel id='neighbor_data' />"

    def fake_fetch(mesh_code: str, timeout: int = 30):
        # Primary mesh: API 404 (returns None)
        if mesh_code == primary_mesh:
            return None
        # One of the neighbors has data
        return neighbor_xml, [f"https://example.invalid/{mesh_code}.gml"]

    def fake_find(xml_content: str, target_id_arg: str, debug: bool = False):
        # Building is found in the neighbor's data
        if xml_content == neighbor_xml:
            return target_id
        return None

    mock_fetch.side_effect = fake_fetch
    mock_find.side_effect = fake_find

    result = search_building_by_id_and_mesh(target_id, primary_mesh)

    assert result["success"] is True
    assert result["matched_gml_id"] == target_id

    # The primary mesh should have been tried first
    called_meshes = [call.args[0] for call in mock_fetch.call_args_list]
    assert called_meshes[0] == primary_mesh
    # At least one neighbor was tried after primary failed
    assert len(called_meshes) > 1


@patch("services.plateau_fetcher._find_building_id_in_xml")
@patch("services.plateau_fetcher._fetch_citygml_by_mesh_code_with_sources")
def test_all_fetches_fail_returns_error_with_neighbor_details(mock_fetch, mock_find):
    """When primary AND all neighbor fetches fail, the error message should
    indicate that neighbors were also tried."""
    target_id = "bldg_f0028aa3-e666-4608-8b70-4e981a45d6b5"
    primary_mesh = "53394611"

    # Everything fails
    mock_fetch.return_value = None

    result = search_building_by_id_and_mesh(target_id, primary_mesh)

    assert result["success"] is False
    assert "also tried neighboring meshes" in result["error_details"]


@patch("services.plateau_fetcher.requests.get")
@patch("services.plateau_fetcher.time.sleep")
def test_query_plateau_catalog_api_retries_on_failure(mock_sleep, mock_get):
    """_query_plateau_catalog_api should retry up to max_retries times on
    HTTP errors before returning None."""
    # First 2 attempts fail with 404, third succeeds
    mock_response_fail = MagicMock()
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 Client Error: Not Found"
    )
    mock_response_ok = MagicMock()
    mock_response_ok.raise_for_status.return_value = None
    mock_response_ok.json.return_value = {"cities": []}

    mock_get.side_effect = [mock_response_fail, mock_response_fail, mock_response_ok]

    result = _query_plateau_catalog_api("53394611", timeout=10, max_retries=2)

    assert result == {"cities": []}
    assert mock_get.call_count == 3
    # Sleep was called before retry 1 and retry 2
    assert mock_sleep.call_count == 2


@patch("services.plateau_fetcher.requests.get")
@patch("services.plateau_fetcher.time.sleep")
def test_query_plateau_catalog_api_returns_none_after_exhausting_retries(
    mock_sleep, mock_get
):
    """When all retries are exhausted, _query_plateau_catalog_api returns None."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 Client Error: Not Found"
    )
    mock_get.return_value = mock_response

    result = _query_plateau_catalog_api("53394611", timeout=10, max_retries=2)

    assert result is None
    assert mock_get.call_count == 3  # 1 initial + 2 retries
