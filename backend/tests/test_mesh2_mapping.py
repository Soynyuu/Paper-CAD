import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_api_client import _get_mesh2_mapping_path, _normalize_mesh2_mapping
from utils.mesh_utils import latlon_to_mesh_2nd


def _load_mapping() -> dict:
    path = _get_mesh2_mapping_path()
    if not Path(path).exists():
        pytest.skip(f"Mesh2 mapping file not found: {path}")
    with Path(path).open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return _normalize_mesh2_mapping(raw)


@pytest.mark.parametrize(
    ("name", "lat", "lon", "expected_code", "expected_prefix"),
    [
        ("shibuya", 35.658034, 139.701636, "13113", None),
        ("yokohama", 35.4437, 139.6380, None, "1410"),
        ("osaka", 34.6937, 135.5022, None, "2710"),
        ("sapporo", 43.0618, 141.3545, None, "0110"),
    ],
)
def test_mesh2_mapping_contains_municipality(
    name: str,
    lat: float,
    lon: float,
    expected_code: str | None,
    expected_prefix: str | None,
) -> None:
    mapping = _load_mapping()
    mesh2 = latlon_to_mesh_2nd(lat, lon)
    codes = mapping.get(mesh2)
    assert codes, f"mesh2 {mesh2} missing for {name}"
    if expected_code:
        assert expected_code in codes, f"{expected_code} missing in mesh2 {mesh2} for {name}"
    if expected_prefix:
        assert any(code.startswith(expected_prefix) for code in codes), (
            f"{expected_prefix}xx missing in mesh2 {mesh2} for {name}"
        )
