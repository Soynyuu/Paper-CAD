"""
PLATEAU Data Catalog API Client

This module provides functionality to interact with the PLATEAU Data Catalog API
to retrieve 3D Tiles URLs by mesh code or municipality code.

API Endpoint: https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets

Key Features:
- Query PLATEAU datasets by municipality code
- Support for LOD1/2/3 filtering
- In-memory caching for performance (dataset catalog is ~2MB)
- Fallback to static mapping for known cities

References:
- https://github.com/Project-PLATEAU/plateau-streaming-tutorial
- https://reearth.engineering/posts/plateau-mcp-en/
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

# PLATEAU Data Catalog API endpoint
PLATEAU_API_URL = "https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets"

# Cache for dataset catalog (refreshed periodically)
_dataset_cache: Optional[List[Dict[str, Any]]] = None
_cache_timestamp: Optional[datetime] = None
_cache_duration = timedelta(hours=24)  # Refresh cache daily
_cache_lock = asyncio.Lock()

# Cache for 2nd mesh code -> municipality code mapping
_mesh2_to_municipality_map: Dict[str, List[str]] = {}
_map_build_lock = asyncio.Lock()

# Default mesh2 mapping path (override with PLATEAU_MESH2_MAPPING_PATH)
_DEFAULT_MESH2_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "mesh2_municipality.json"
)
# Fallback for known cities (Phase 2 static mapping, kept for reliability)
KNOWN_CITY_TILESETS = {
    "13101": {  # 千代田区
        "name": "千代田区",
        "lod1": "https://assets.cms.plateau.reearth.io/assets/0e/e5948a-e95c-4e31-be85-1f8c066ed996/13101_chiyoda-ku_pref_2023_citygml_1_op_bldg_3dtiles_13101_chiyoda-ku_lod1/tileset.json",
    },
    "13102": {  # 中央区
        "name": "中央区",
        "lod1": "https://assets.cms.plateau.reearth.io/assets/72/d3e0b0-79bb-441c-9de4-9cf1be4d8e1d/13102_chuo-ku_pref_2023_citygml_1_op_bldg_3dtiles_13102_chuo-ku_lod1/tileset.json",
    },
    "13103": {  # 港区
        "name": "港区",
        "lod1": "https://assets.cms.plateau.reearth.io/assets/88/fc4ed4-d3e6-458a-bd6c-ec1063e43ebd/13103_minato-ku_pref_2023_citygml_1_op_bldg_3dtiles_13103_minato-ku_lod1/tileset.json",
    },
    "13104": {  # 新宿区
        "name": "新宿区",
        "lod1": "https://assets.cms.plateau.reearth.io/assets/5f/0f37a7-bf11-4df6-88e3-5ec71a0e1bfa/13104_shinjuku-ku_pref_2023_citygml_1_op_bldg_3dtiles_13104_shinjuku-ku_lod1/tileset.json",
    },
    "13113": {  # 渋谷区
        "name": "渋谷区",
        "lod1": "https://assets.cms.plateau.reearth.io/assets/d6/09251d-eaf4-4288-a68d-41c449edbe5d/13113_shibuya-ku_pref_2023_citygml_1_op_bldg_3dtiles_13113_shibuya-ku_lod1/tileset.json",
    },
}


async def _fetch_plateau_catalog() -> List[Dict[str, Any]]:
    """
    Fetch full PLATEAU dataset catalog from API

    Returns:
        List of dataset entries from PLATEAU API

    Raises:
        aiohttp.ClientError: If API request fails
    """
    logger.info(f"Fetching PLATEAU dataset catalog from {PLATEAU_API_URL}")

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(PLATEAU_API_URL) as response:
            response.raise_for_status()
            data = await response.json()

            # API returns {"datasets": [...]} structure
            if not isinstance(data, dict) or "datasets" not in data:
                raise ValueError(f"Unexpected PLATEAU API response format: {type(data)}")

            datasets = data["datasets"]
            if not isinstance(datasets, list):
                raise ValueError(f"Expected datasets to be a list, got: {type(datasets)}")

            logger.info(f"Fetched {len(datasets)} datasets from PLATEAU catalog")
            return datasets


async def _get_cached_catalog() -> List[Dict[str, Any]]:
    """
    Get dataset catalog from cache, or fetch if expired

    Returns:
        List of dataset entries
    """
    global _dataset_cache, _cache_timestamp

    async with _cache_lock:
        # Check if cache is valid
        if _dataset_cache is not None and _cache_timestamp is not None:
            age = datetime.now() - _cache_timestamp
            if age < _cache_duration:
                logger.debug(f"Using cached catalog (age: {age})")
                return _dataset_cache

        # Fetch new data
        try:
            _dataset_cache = await _fetch_plateau_catalog()
            _cache_timestamp = datetime.now()
            return _dataset_cache
        except Exception as e:
            logger.error(f"Failed to fetch PLATEAU catalog: {e}")

            # Return stale cache if available
            if _dataset_cache is not None:
                logger.warning("Using stale cache due to API failure")
                return _dataset_cache

            raise


def _get_mesh2_mapping_path() -> Path:
    """Resolve mesh2 mapping file path from env or default."""
    env_path = os.getenv("PLATEAU_MESH2_MAPPING_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_MESH2_MAPPING_PATH


def _normalize_mesh2_mapping(raw: Any) -> Dict[str, List[str]]:
    """Normalize mesh2 mapping JSON into Dict[str, List[str]]."""
    if isinstance(raw, dict) and "mesh2_to_municipalities" in raw:
        raw = raw["mesh2_to_municipalities"]

    if not isinstance(raw, dict):
        raise ValueError("mesh2 mapping JSON must be an object")

    normalized: Dict[str, List[str]] = {}
    for mesh2, codes in raw.items():
        mesh2_key = str(mesh2).strip()
        if len(mesh2_key) != 6 or not mesh2_key.isdigit():
            continue

        if isinstance(codes, str):
            codes = [codes]
        if not isinstance(codes, list):
            continue

        normalized_codes: List[str] = []
        for code in codes:
            code_str = str(code).strip()
            if len(code_str) == 5 and code_str.isdigit():
                normalized_codes.append(code_str)

        if normalized_codes:
            normalized[mesh2_key] = sorted(set(normalized_codes))

    if not normalized:
        raise ValueError("mesh2 mapping JSON has no usable entries")

    return normalized


def _load_mesh2_mapping(path: Path) -> Dict[str, List[str]]:
    """Load mesh2 mapping JSON from disk."""
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return _normalize_mesh2_mapping(raw)


async def _build_mesh2_to_municipality_map() -> Dict[str, List[str]]:
    """
    2次メッシュコード（6桁）→ 市区町村コード（5桁）マッピングを構築

    Strategy:
    1. 事前生成したJSON（mesh2_municipality.json）をロード
    2. メモリ内辞書として保持
    3. O(1)での高速検索を実現

    Returns:
        Dict[mesh2_code (6桁), List[municipality_code]]

    Example:
        >>> map = await _build_mesh2_to_municipality_map()
        >>> map["533935"]
        ["13113"]  # 渋谷区
    """
    mapping_path = _get_mesh2_mapping_path()

    if mapping_path.exists():
        mesh2_map = _load_mesh2_mapping(mapping_path)
        logger.info(
            "Loaded mesh2->municipality map from %s (%d entries)",
            mapping_path,
            len(mesh2_map),
        )
        logger.debug("Sample entries: %s", list(mesh2_map.items())[:5])
        return mesh2_map

    allow_fallback = os.getenv("PLATEAU_ALLOW_TOKYO_FALLBACK", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    if allow_fallback:
        from services.plateau_mesh_mapping import TOKYO_23_MESH2_MAPPING
        logger.warning(
            "Mesh2 mapping file not found at %s. Falling back to Tokyo-only map.",
            mapping_path,
        )
        return {mesh2: [code] for mesh2, code in TOKYO_23_MESH2_MAPPING.items()}

    raise FileNotFoundError(
        f"Mesh2 mapping file not found: {mapping_path}. "
        "Generate it via backend/scripts/build_mesh2_municipality_map.py."
    )


async def _get_cached_mesh2_map() -> Dict[str, List[str]]:
    """
    キャッシュされた2次メッシュマップを取得（起動時に一度だけ構築）

    Returns:
        Dict[mesh2_code, List[municipality_code]]

    Note:
        初回呼び出し時にマップを構築し、以降はキャッシュを返す
        サーバー再起動まで有効
    """
    global _mesh2_to_municipality_map

    async with _map_build_lock:
        if not _mesh2_to_municipality_map:
            _mesh2_to_municipality_map = await _build_mesh2_to_municipality_map()

        return _mesh2_to_municipality_map


def _filter_building_datasets(
    datasets: List[Dict[str, Any]], city_code: str, lod: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Filter datasets for building models (建築物モデル) in 3D Tiles format

    Args:
        datasets: Full catalog from PLATEAU API
        city_code: 5-digit municipality code (e.g., "13101")
        lod: Optional LOD filter (1, 2, or 3)

    Returns:
        Filtered list of matching datasets
    """
    filtered = []

    for dataset in datasets:
        # Check municipality code (city_code or ward_code)
        dataset_city = dataset.get("city_code") or dataset.get("ward_code")
        if dataset_city != city_code:
            continue

        # Check type (建築物モデル = Building Model)
        if dataset.get("type") != "建築物モデル":
            continue

        # Check format (3D Tiles)
        if dataset.get("format") != "3D Tiles":
            continue

        # Check LOD if specified (API returns LOD as string)
        if lod is not None:
            dataset_lod = dataset.get("lod")
            # Convert to int for comparison (API returns "1", "2", "3")
            try:
                dataset_lod_int = int(dataset_lod) if dataset_lod else None
                if dataset_lod_int != lod:
                    continue
            except (ValueError, TypeError):
                continue

        filtered.append(dataset)

    return filtered


async def fetch_plateau_datasets_by_mesh(mesh_code: str, lod: int = 1) -> List[Dict[str, Any]]:
    """
    高速版：メッシュコード → 市区町村コード → PLATEAU 3D Tiles (複数対応)

    Implementation Strategy:
    1. 3次メッシュコード（8桁）→ 2次メッシュコード（6桁）抽出
    2. 2次メッシュ → 市区町村コード辞書検索（O(1)）
    3. 市区町村コード → PLATEAU 3D Tiles取得

    Performance:
    - OLD: 9メッシュ × 1秒 = 9秒（Nominatim API）❌
    - NEW: 9メッシュ × 1ms = 9ms（辞書検索）✅

    Args:
        mesh_code: 3次メッシュコード (8桁, 例: "53393575")
        lod: LODレベル (1, 2, 3)

    Returns:
        List of dataset dicts (may be empty if not found)

    Note:
        - No external API calls
        - No rate limiting
        - No network latency
        - Requires offline mesh2 mapping JSON for nationwide support

    Example:
        >>> results = await fetch_plateau_datasets_by_mesh("53393575", lod=1)
        >>> results[0]["municipality_code"]
        "13113"  # 渋谷区
    """
    if len(mesh_code) != 8:
        logger.warning(f"Invalid mesh code length: {mesh_code} (expected 8 digits)")
        return []

    # Extract 2nd mesh code (6 digits) from 3rd mesh code (8 digits)
    # Example: "53393575" -> "533935"
    mesh2 = mesh_code[:6]

    # O(1) dictionary lookup for municipality code
    mesh2_map = await _get_cached_mesh2_map()
    municipality_codes = mesh2_map.get(mesh2, [])

    if not municipality_codes:
        logger.warning(
            f"No municipality found for mesh2: {mesh2} (from mesh: {mesh_code}). "
            f"This area may not be covered by PLATEAU data."
        )
        return []

    logger.info(f"Mesh {mesh_code} -> Mesh2 {mesh2} -> Municipalities {municipality_codes}")

    # Fetch datasets for all municipalities (parallel)
    tasks = [fetch_plateau_dataset_by_municipality(code, lod) for code in municipality_codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    datasets: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Error fetching dataset by municipality: {result}")
            continue
        if result:
            datasets.append(result)

    return datasets


async def fetch_plateau_dataset_by_mesh(mesh_code: str, lod: int = 1) -> Optional[Dict[str, Any]]:
    """
    Backward-compatible single-result helper.
    """
    results = await fetch_plateau_datasets_by_mesh(mesh_code, lod)
    return results[0] if results else None


async def fetch_plateau_dataset_by_municipality(
    municipality_code: str, lod: int = 1
) -> Optional[Dict[str, Any]]:
    """
    市区町村コードからPLATEAU 3D Tilesデータセットを取得

    Args:
        municipality_code: 5桁の市区町村コード (例: "13101" for 千代田区)
        lod: LODレベル (1, 2, 3)

    Returns:
        {
            "tileset_url": "https://...",
            "municipality_name": "千代田区",
            "municipality_code": "13101",
            "lod": 1
        }
        None if not found
    """
    try:
        # Get catalog
        catalog = await _get_cached_catalog()

        # Filter for this municipality and LOD
        datasets = _filter_building_datasets(catalog, municipality_code, lod)

        if datasets:
            # Return first matching dataset
            dataset = datasets[0]
            return {
                "tileset_url": dataset["url"],
                "municipality_name": dataset.get("name", "Unknown"),
                "municipality_code": municipality_code,
                "lod": dataset.get("lod", lod),
            }

        # If no match for specific LOD, try LOD1 as fallback
        if lod != 1:
            logger.info(f"LOD{lod} not found for {municipality_code}, trying LOD1")
            datasets = _filter_building_datasets(catalog, municipality_code, 1)
            if datasets:
                dataset = datasets[0]
                return {
                    "tileset_url": dataset["url"],
                    "municipality_name": dataset.get("name", "Unknown"),
                    "municipality_code": municipality_code,
                    "lod": 1,
                }

    except Exception as e:
        logger.error(f"Error fetching from PLATEAU API: {e}")

        # Fallback to static mapping
        if municipality_code in KNOWN_CITY_TILESETS:
            logger.info(f"Using fallback tileset for {municipality_code}")
            city_data = KNOWN_CITY_TILESETS[municipality_code]
            lod_key = f"lod{lod}" if f"lod{lod}" in city_data else "lod1"
            return {
                "tileset_url": city_data[lod_key],
                "municipality_name": city_data["name"],
                "municipality_code": municipality_code,
                "lod": lod,
            }

    logger.warning(f"No tileset found for municipality {municipality_code} LOD{lod}")
    return None


async def fetch_tilesets_for_meshes(mesh_codes: List[str], lod: int = 1) -> List[Dict[str, Any]]:
    """
    複数のメッシュコードに対して3D Tiles URLを取得

    Args:
        mesh_codes: メッシュコードのリスト
        lod: LODレベル

    Returns:
        List of {
            "mesh_code": "53394511",
            "tileset_url": "https://...",
            "municipality_name": "千代田区",
            "municipality_code": "13101"
        }
    """
    tilesets: List[Dict[str, Any]] = []
    seen_municipalities = set()  # Avoid duplicate URLs for same municipality

    mesh2_map = await _get_cached_mesh2_map()
    mesh_to_codes: Dict[str, List[str]] = {}
    unique_codes: List[str] = []
    unique_code_set = set()

    for mesh_code in mesh_codes:
        if len(mesh_code) != 8 or not mesh_code.isdigit():
            logger.warning(f"Invalid mesh code format: {mesh_code}")
            continue

        mesh2 = mesh_code[:6]
        codes = mesh2_map.get(mesh2, [])
        mesh_to_codes[mesh_code] = codes
        for code in codes:
            if code not in unique_code_set:
                unique_codes.append(code)
                unique_code_set.add(code)

    if not unique_codes:
        return tilesets

    concurrency = int(os.getenv("PLATEAU_DATASET_FETCH_CONCURRENCY", "8"))
    semaphore = asyncio.Semaphore(concurrency)

    async def _fetch_dataset(code: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        async with semaphore:
            dataset = await fetch_plateau_dataset_by_municipality(code, lod)
            return code, dataset

    dataset_results = await asyncio.gather(
        *[_fetch_dataset(code) for code in unique_codes], return_exceptions=True
    )

    datasets_by_code: Dict[str, Dict[str, Any]] = {}
    for result in dataset_results:
        if isinstance(result, Exception):
            logger.warning(f"Dataset fetch error: {result}")
            continue
        code, dataset = result
        if dataset:
            datasets_by_code[code] = dataset

    for mesh_code, codes in mesh_to_codes.items():
        for code in codes:
            if code in seen_municipalities:
                continue
            dataset = datasets_by_code.get(code)
            if not dataset:
                continue
            tilesets.append(
                {
                    "mesh_code": mesh_code,
                    "tileset_url": dataset["tileset_url"],
                    "municipality_name": dataset["municipality_name"],
                    "municipality_code": code,
                }
            )
            seen_municipalities.add(code)

    return tilesets


# Utility function for manual cache refresh
async def refresh_catalog_cache() -> None:
    """
    Manually refresh the PLATEAU dataset catalog cache

    Useful for:
    - Initial server startup
    - Periodic background refresh
    - After detecting stale data
    """
    global _dataset_cache, _cache_timestamp

    async with _cache_lock:
        _dataset_cache = await _fetch_plateau_catalog()
        _cache_timestamp = datetime.now()
        logger.info("PLATEAU catalog cache refreshed successfully")
