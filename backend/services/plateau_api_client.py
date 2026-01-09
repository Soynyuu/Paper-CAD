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
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)

# PLATEAU Data Catalog API endpoint
PLATEAU_API_URL = "https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets"

# Cache for dataset catalog (refreshed periodically)
_dataset_cache: Optional[List[Dict[str, Any]]] = None
_cache_timestamp: Optional[datetime] = None
_cache_duration = timedelta(hours=24)  # Refresh cache daily
_cache_lock = asyncio.Lock()

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

            # API returns array of datasets directly
            if not isinstance(data, list):
                raise ValueError(f"Expected list from PLATEAU API, got: {type(data)}")

            logger.info(f"Fetched {len(data)} datasets from PLATEAU catalog")
            return data


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

        # Check LOD if specified
        if lod is not None:
            dataset_lod = dataset.get("lod")
            if dataset_lod != lod:
                continue

        filtered.append(dataset)

    return filtered


async def fetch_plateau_dataset_by_mesh(mesh_code: str, lod: int = 1) -> Optional[Dict[str, Any]]:
    """
    PLATEAU Data Catalog APIからメッシュコードに対応するデータセットを取得

    Note: メッシュコードから直接市区町村を特定することは困難なため、
    このAPIは限定的なサポートのみを提供します。フロントエンドで住所検索を
    行い、座標から市区町村を特定してから`fetch_plateau_dataset_by_municipality`
    を使用することを推奨します。

    Args:
        mesh_code: 3次メッシュコード (8桁)
        lod: LODレベル (1, 2, 3)

    Returns:
        {
            "tileset_url": "https://...",
            "municipality_name": "千代田区",
            "municipality_code": "13101"
        }
        None if not found
    """
    if len(mesh_code) != 8:
        logger.warning(f"Invalid mesh code length: {mesh_code}")
        return None

    # メッシュコードから市区町村への直接マッピングは困難
    # 静的フォールバックを使用（東京エリアのみ）
    mesh_prefix = mesh_code[:4]
    mesh_2nd = mesh_code[4:6]

    # 簡易的な東京エリアマッピング（Phase 2の互換性のため）
    tokyo_mapping = {
        "5339": {
            "45": "13101",  # 千代田区
            "46": "13102",  # 中央区
            "55": "13103",  # 港区
            "47": "13104",  # 新宿区
            "57": "13113",  # 渋谷区
        }
    }

    municipality_code = None
    if mesh_prefix in tokyo_mapping:
        municipality_code = tokyo_mapping[mesh_prefix].get(mesh_2nd)

    if not municipality_code:
        logger.warning(
            f"Could not determine municipality from mesh code: {mesh_code}. "
            "Consider using address-based search instead."
        )
        return None

    # 市区町村コードが分かったので、それで検索
    return await fetch_plateau_dataset_by_municipality(municipality_code, lod)


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
    tilesets = []
    seen_municipalities = set()  # Avoid duplicate URLs for same municipality

    for mesh_code in mesh_codes:
        dataset = await fetch_plateau_dataset_by_mesh(mesh_code, lod)

        if dataset:
            # Only add if we haven't already added this municipality
            municipality_code = dataset.get("municipality_code")
            if municipality_code and municipality_code not in seen_municipalities:
                tilesets.append(
                    {
                        "mesh_code": mesh_code,
                        "tileset_url": dataset["tileset_url"],
                        "municipality_name": dataset["municipality_name"],
                        "municipality_code": municipality_code,
                    }
                )
                seen_municipalities.add(municipality_code)

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
