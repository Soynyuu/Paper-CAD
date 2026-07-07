from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

LOCAL_DEMO_ROUTE_PREFIX = "/local-demo-cache"
DEFAULT_LOCAL_DEMO_CACHE_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "local_demo_cache"
)
DEFAULT_LOCAL_DEMO_MANIFEST_PATH = DEFAULT_LOCAL_DEMO_CACHE_DIR / "manifest.json"


@dataclass(frozen=True)
class LocalDemoTarget:
    key: str
    canonical_name: str
    aliases: tuple[str, ...]
    latitude: float
    longitude: float
    display_name: str
    municipality_code: Optional[str] = None
    mesh_code: Optional[str] = None
    building_id: Optional[str] = None


LOCAL_DEMO_TARGETS: tuple[LocalDemoTarget, ...] = (
    LocalDemoTarget(
        key="shibaura_fuzoku",
        canonical_name="芝浦工業大学附属中学高等学校",
        aliases=(
            "芝浦工業大学附属中学高等学校",
            "芝浦工大附属",
            "芝浦工業大学附属",
            "芝浦工大附属中高",
            "芝浦工大附属中学高等学校",
        ),
        latitude=35.64947,
        longitude=139.79413,
        display_name="芝浦工業大学附属中学高等学校, 豊洲, 江東区, 東京都",
        municipality_code="13108",
    ),
    LocalDemoTarget(
        key="jp_tower",
        canonical_name="JPタワー",
        aliases=("JPタワー", "ＪＰタワー", "jp tower", "jptower", "KITTE", "キッテ"),
        latitude=35.67989,
        longitude=139.76479,
        display_name="JPタワー, 丸の内, 千代田区, 東京都",
        municipality_code="13101",
    ),
    LocalDemoTarget(
        key="shibuya_fukuras",
        canonical_name="渋谷フクラス",
        aliases=("渋谷フクラス", "渋谷ふくらす", "フクラス", "ふくらす", "fukuras"),
        latitude=35.65806,
        longitude=139.70028,
        display_name="渋谷フクラス, 道玄坂, 渋谷区, 東京都",
        municipality_code="13113",
        mesh_code="53393586",
        building_id="bldg_3ad6aaeb-26f8-4716-a8ec-cb2504b94674",
    ),
)

_MANIFEST_CACHE: Optional[Dict[str, Any]] = None


def is_local_demo() -> bool:
    return os.getenv("ENV", os.getenv("PYTHON_ENV", "development")) == "local_demo"


def local_demo_cache_dir() -> Path:
    return Path(os.getenv("LOCAL_DEMO_CACHE_DIR", str(DEFAULT_LOCAL_DEMO_CACHE_DIR)))


def local_demo_manifest_path() -> Path:
    return Path(os.getenv("LOCAL_DEMO_MANIFEST_PATH", str(DEFAULT_LOCAL_DEMO_MANIFEST_PATH)))


def local_demo_public_base_url() -> str:
    return os.getenv(
        "LOCAL_DEMO_PUBLIC_BASE_URL",
        f"http://localhost:8001{LOCAL_DEMO_ROUTE_PREFIX}",
    )


def get_local_demo_static_dir() -> Path:
    return local_demo_cache_dir()


def _normalize_query(value: str) -> str:
    return value.strip().lower().replace("　", " ").replace(" ", "")


def get_static_target(query: str) -> Optional[LocalDemoTarget]:
    normalized = _normalize_query(query)
    if not normalized:
        return None

    for target in LOCAL_DEMO_TARGETS:
        values = (target.canonical_name, *target.aliases)
        if any(
            _normalize_query(value) in normalized
            or normalized in _normalize_query(value)
            for value in values
        ):
            return target
    return None


def load_manifest(force: bool = False) -> Dict[str, Any]:
    global _MANIFEST_CACHE

    if _MANIFEST_CACHE is not None and not force:
        return _MANIFEST_CACHE

    path = local_demo_manifest_path()
    if not path.exists():
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE

    try:
        with path.open("r", encoding="utf-8") as f:
            _MANIFEST_CACHE = json.load(f)
    except Exception as e:
        logger.error("[LOCAL_DEMO] Failed to load manifest %s: %s", path, e)
        _MANIFEST_CACHE = {}

    return _MANIFEST_CACHE


def get_manifest_target(query: str) -> Optional[Dict[str, Any]]:
    static_target = get_static_target(query)
    if not static_target:
        return None

    manifest = load_manifest()
    targets = manifest.get("targets", {})
    entry = targets.get(static_target.key, {}) if isinstance(targets, dict) else {}
    merged: Dict[str, Any] = {
        "key": static_target.key,
        "name": static_target.canonical_name,
        "aliases": list(static_target.aliases),
        "latitude": static_target.latitude,
        "longitude": static_target.longitude,
        "display_name": static_target.display_name,
        "municipality_code": static_target.municipality_code,
        "mesh_code": static_target.mesh_code,
        "building_id": static_target.building_id,
    }
    if isinstance(entry, dict):
        merged.update({k: v for k, v in entry.items() if v is not None})
    return merged


def rewrite_cache_path_to_url(cache_relative_path: str) -> str:
    relative = cache_relative_path.lstrip("/")
    return f"{local_demo_public_base_url().rstrip('/')}/{relative}"


def get_local_tilesets(
    mesh_codes: List[str],
    lod: int = 1,
    municipality_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    manifest = load_manifest()
    raw_tilesets = manifest.get("tilesets", [])
    if not isinstance(raw_tilesets, list):
        return []

    requested_meshes = set(mesh_codes)
    tilesets: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_tilesets:
        if not isinstance(item, dict):
            continue

        item_lod = int(item.get("lod") or lod)
        if item_lod != lod:
            continue

        item_municipality = item.get("municipality_code")
        if municipality_code and item_municipality != municipality_code:
            continue

        item_mesh_codes = item.get("mesh_codes") or []
        if isinstance(item_mesh_codes, str):
            item_mesh_codes = [item_mesh_codes]
        if (
            not municipality_code
            and requested_meshes
            and item_mesh_codes
            and not (requested_meshes & set(item_mesh_codes))
        ):
            continue

        local_path = item.get("local_path")
        if not local_path:
            continue

        mesh_code = next((m for m in item_mesh_codes if m in requested_meshes), None)
        if mesh_code is None:
            mesh_code = mesh_codes[0] if mesh_codes else str(item_municipality or "local")

        key = (str(mesh_code), str(item_municipality or local_path))
        if key in seen:
            continue
        seen.add(key)

        tilesets.append(
            {
                "mesh_code": str(mesh_code),
                "tileset_url": rewrite_cache_path_to_url(str(local_path)),
                "municipality_name": item.get("municipality_name"),
                "municipality_code": item_municipality,
                "lod": item_lod,
            }
        )

    return tilesets
