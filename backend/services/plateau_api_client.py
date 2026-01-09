"""
PLATEAU Data Catalog API Client

This module provides functionality to interact with the PLATEAU Data Catalog API
to retrieve 3D Tiles URLs by mesh code.

API Reference:
https://github.com/Project-PLATEAU/plateau-streaming-tutorial

Key Features:
- Convert mesh codes to 3D Tiles tileset URLs
- Query PLATEAU datasets by mesh code
- Support for LOD1/2/3 filtering
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional, List
from pathlib import Path

# Known PLATEAU 3D Tiles URLs (fallback for Phase 2 implementation)
# TODO: Replace with actual PLATEAU Data Catalog API calls
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

# Mesh code to municipality code mapping (1st 4 digits of mesh code)
# This is a simplified mapping for Tokyo area
# Format: {mesh_prefix: municipality_code}
MESH_TO_MUNICIPALITY = {
    "5339": {  # Tokyo area
        "45": "13101",  # 千代田区
        "46": "13102",  # 中央区
        "55": "13103",  # 港区
        "47": "13104",  # 新宿区
        "57": "13113",  # 渋谷区
    }
}


async def fetch_plateau_dataset_by_mesh(
    mesh_code: str,
    lod: int = 1
) -> Optional[Dict[str, Any]]:
    """
    PLATEAU Data Catalog APIからメッシュコードに対応するデータセットを取得

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

    Note:
        Phase 2 implementation uses known city tilesets.
        TODO: Implement actual PLATEAU Data Catalog API calls.
    """
    if len(mesh_code) != 8:
        return None

    # Extract mesh prefix (first 4 digits) and 2nd mesh indices (5th-6th digits)
    mesh_prefix = mesh_code[:4]
    mesh_2nd = mesh_code[4:6]

    # Look up municipality code
    municipality_code = None
    if mesh_prefix in MESH_TO_MUNICIPALITY:
        municipality_map = MESH_TO_MUNICIPALITY[mesh_prefix]
        if mesh_2nd in municipality_map:
            municipality_code = municipality_map[mesh_2nd]

    if not municipality_code:
        # Municipality not found in our known mapping
        return None

    # Get tileset URL from known city data
    if municipality_code not in KNOWN_CITY_TILESETS:
        return None

    city_data = KNOWN_CITY_TILESETS[municipality_code]
    lod_key = f"lod{lod}"

    if lod_key not in city_data:
        # Fallback to LOD1 if requested LOD not available
        lod_key = "lod1"

    tileset_url = city_data.get(lod_key)
    if not tileset_url:
        return None

    return {
        "tileset_url": tileset_url,
        "municipality_name": city_data["name"],
        "municipality_code": municipality_code,
    }


async def fetch_tilesets_for_meshes(
    mesh_codes: List[str],
    lod: int = 1
) -> List[Dict[str, Any]]:
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
                tilesets.append({
                    "mesh_code": mesh_code,
                    "tileset_url": dataset["tileset_url"],
                    "municipality_name": dataset["municipality_name"],
                    "municipality_code": municipality_code,
                })
                seen_municipalities.add(municipality_code)

    return tilesets


# TODO: Future implementation with actual PLATEAU Data Catalog API
"""
async def fetch_plateau_dataset_by_mesh_api(
    mesh_code: str,
    lod: int = 1
) -> Optional[Dict[str, Any]]:
    '''
    Actual PLATEAU Data Catalog API implementation

    API Endpoint: https://api.plateau.reearth.io/v1/datasets
    Query Parameters:
        - mesh_code: 53394511
        - type: bldg (building)
        - lod: 1/2/3
    '''
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.plateau.reearth.io/v1/datasets",
            params={
                "mesh_code": mesh_code,
                "type": "bldg",
                "lod": lod,
            },
            timeout=10.0
        )

        if response.status_code != 200:
            return None

        data = response.json()

        # Parse response and extract tileset URL
        # (API response structure needs to be confirmed)
        if "datasets" in data and len(data["datasets"]) > 0:
            dataset = data["datasets"][0]
            return {
                "tileset_url": dataset.get("tileset_url"),
                "municipality_name": dataset.get("municipality_name"),
                "municipality_code": dataset.get("municipality_code"),
            }

    return None
"""
