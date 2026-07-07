#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.local_demo import LOCAL_DEMO_TARGETS  # noqa: E402
from services.plateau_api_client import fetch_plateau_dataset_by_municipality  # noqa: E402
import services.plateau_fetcher as plateau_fetcher  # noqa: E402
from services.plateau_fetcher import (  # noqa: E402
    _get_wards_from_mesh,
    _load_gml_from_cache_with_metadata,
    find_nearest_building,
    parse_buildings_from_citygml,
)
from utils.mesh_utils import get_neighboring_meshes_3rd, latlon_to_mesh_3rd  # noqa: E402

DEFAULT_CACHE_DIR = BACKEND_DIR / "data" / "local_demo_cache"
PLATEAU_CITYGML_API = "https://api.plateauview.mlit.go.jp/datacatalog/citygml/m:{mesh_code}"
GSI_IMAGERY = {
    "gsi-standard": ("https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png", ".png"),
    "gsi-pale": ("https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png", ".png"),
    "gsi-photo": ("https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg", ".jpg"),
    "plateau-ortho-2023": (
        "https://tile.plateauview.mlit.go.jp/tiles/plateau-ortho-2023/{z}/{x}/{y}.png",
        ".png",
    ),
}
PLATEAU_TERRAIN_URL = "https://tile.plateauview.mlit.go.jp/terrain"


def request_json(url: str, timeout: int = 60) -> Any:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def download_file(url: str, destination: Path, timeout: int = 120) -> bool:
    if destination.exists() and destination.stat().st_size > 0:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with tmp.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                f.write(chunk)
    tmp.replace(destination)
    return True


def slippy_tile(lon: float, lat: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def bbox_for_point(lat: float, lon: float, radius_m: float) -> Tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lon_delta = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 0.1))
    return lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta


def tile_range_for_bbox(bbox: Tuple[float, float, float, float], zoom: int) -> Iterable[Tuple[int, int]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    min_x, max_y = slippy_tile(min_lon, min_lat, zoom)
    max_x, min_y = slippy_tile(max_lon, max_lat, zoom)
    for x in range(min(min_x, max_x), max(min_x, max_x) + 1):
        for y in range(min(min_y, max_y), max(min_y, max_y) + 1):
            yield x, y


def merge_mesh_index(index_path: Path, mesh_to_codes: Dict[str, Set[str]]) -> None:
    data: Dict[str, Any] = {"version": "1.0.0", "created_at": datetime.now().isoformat(), "index": {}}
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("index", {})

    index = data["index"]
    for mesh_code, codes in mesh_to_codes.items():
        sorted_codes = sorted(codes)
        index[mesh_code] = sorted_codes[0] if len(sorted_codes) == 1 else sorted_codes

    data["updated_at"] = datetime.now().isoformat()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def download_citygml_for_mesh(mesh_code: str, citygml_cache_dir: Path) -> Set[str]:
    print(f"[CityGML] mesh {mesh_code}")
    catalog = request_json(PLATEAU_CITYGML_API.format(mesh_code=mesh_code))
    area_codes: Set[str] = set()

    for city in catalog.get("cities", []):
        city_code = str(city.get("cityCode") or "").strip()
        city_name = str(city.get("cityName") or city_code or "unknown").strip()
        if not city_code:
            continue

        files = city.get("files", {})
        for bldg_file in files.get("bldg", []):
            url = bldg_file.get("url")
            if not url:
                continue

            filename = Path(urlparse(url).path).name
            if not filename:
                continue

            ward_dir = citygml_cache_dir / f"{city_code}_{city_name}"
            destination = ward_dir / "udx" / "bldg" / filename
            changed = download_file(url, destination)
            print(f"  {'downloaded' if changed else 'cached'} {destination.relative_to(citygml_cache_dir)}")
            area_codes.add(city_code)

    return area_codes


def resolve_target_building(
    target: Dict[str, Any],
    _citygml_cache_dir: Path,
) -> Dict[str, Any]:
    if target.get("building_id") and target.get("mesh_code"):
        return target

    ranked_candidates: List[Tuple[Any, str, Dict[str, str]]] = []
    for mesh_code in target.get("cached_mesh_codes") or [target["mesh_code"]]:
        area_codes = _get_wards_from_mesh(str(mesh_code))
        if not area_codes:
            continue

        cached = _load_gml_from_cache_with_metadata(str(mesh_code), area_codes)
        if not cached:
            continue

        buildings = parse_buildings_from_citygml(cached.xml_content)
        ranked = find_nearest_building(
            buildings,
            float(target["latitude"]),
            float(target["longitude"]),
            name_query=str(target["name"]),
            search_mode="hybrid",
        )
        if ranked:
            ranked_candidates.append((ranked[0], str(mesh_code), cached.municipality_by_gml_id))

    if not ranked_candidates:
        raise RuntimeError(f"No buildings parsed for target {target['name']}")

    ranked_candidates.sort(
        key=lambda candidate: (
            -(candidate[0].relevance_score or 0),
            candidate[0].distance_meters,
        )
    )
    building, mesh_code, municipality_by_gml_id = ranked_candidates[0]
    target["building_id"] = building.gml_id
    target["mesh_code"] = mesh_code
    target["municipality_code"] = (
        municipality_by_gml_id.get(building.gml_id)
        or target.get("municipality_code")
    )
    return target


def local_tileset_path(cache_dir: Path, municipality_code: str, lod: int) -> Path:
    return cache_dir / "3dtiles" / municipality_code / f"lod{lod}" / "tileset.json"


def should_download_tileset_resource(path: str) -> bool:
    suffix = Path(urlparse(path).path).suffix.lower()
    return suffix in {".json", ".b3dm", ".i3dm", ".cmpt", ".pnts", ".glb", ".bin", ".png", ".jpg", ".jpeg", ".webp"}


def download_3dtiles_recursive(
    root_url: str,
    destination_tileset: Path,
    max_files: int,
) -> int:
    root_destination_dir = destination_tileset.parent
    root_destination_dir.mkdir(parents=True, exist_ok=True)
    queue: List[Tuple[str, Path]] = [(root_url, destination_tileset)]
    seen_urls: Set[str] = set()
    downloaded = 0

    while queue:
        url, destination = queue.pop(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if len(seen_urls) > max_files:
            raise RuntimeError(f"3D Tiles download exceeded --max-tileset-files={max_files}")

        download_file(url, destination)
        downloaded += 1

        if destination.suffix.lower() != ".json":
            continue

        with destination.open("r", encoding="utf-8") as f:
            data = json.load(f)

        child_uris: List[str] = []
        changed_json = False

        def collect(node: Dict[str, Any]) -> None:
            nonlocal changed_json
            content = node.get("content") or {}
            uri = content.get("uri") or content.get("url")
            if isinstance(uri, str):
                child_uris.append(uri)
                parsed_uri = urlparse(uri)
                if parsed_uri.scheme:
                    local_uri = Path(parsed_uri.path).name
                    if "uri" in content:
                        content["uri"] = local_uri
                    if "url" in content:
                        content["url"] = local_uri
                    changed_json = True
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    collect(child)

        root = data.get("root")
        if isinstance(root, dict):
            collect(root)

        if changed_json:
            with destination.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

        for uri in child_uris:
            if not should_download_tileset_resource(uri):
                continue
            child_url = urljoin(url, uri)
            parsed_child = urlparse(uri)
            if parsed_child.scheme:
                relative_name = Path(parsed_child.path).name
                child_destination = destination.parent / relative_name
            else:
                child_destination = (destination.parent / uri).resolve()
                try:
                    child_destination.relative_to(root_destination_dir.resolve())
                except ValueError:
                    child_destination = root_destination_dir / Path(uri).name
            queue.append((child_url, child_destination))

    return downloaded


async def fetch_tileset_dataset(municipality_code: str, lod: int) -> Dict[str, Any]:
    dataset = await fetch_plateau_dataset_by_municipality(municipality_code, lod, True)
    if not dataset:
        raise RuntimeError(f"No PLATEAU 3D Tiles dataset for municipality {municipality_code} LOD{lod}")
    return dataset


def download_imagery(cache_dir: Path, bboxes: List[Tuple[float, float, float, float]], zooms: List[int]) -> int:
    count = 0
    for layer, (template, extension) in GSI_IMAGERY.items():
        for zoom in zooms:
            tiles: Set[Tuple[int, int]] = set()
            for bbox in bboxes:
                tiles.update(tile_range_for_bbox(bbox, zoom))
            for x, y in tiles:
                url = template.format(z=zoom, x=x, y=y)
                destination = cache_dir / "imagery" / layer / str(zoom) / str(x) / f"{y}{extension}"
                try:
                    if download_file(url, destination, timeout=30):
                        count += 1
                except requests.RequestException as e:
                    print(f"[Imagery] skipped {url}: {e}")
    return count


def download_terrain(cache_dir: Path, bboxes: List[Tuple[float, float, float, float]], zooms: List[int]) -> int:
    terrain_dir = cache_dir / "terrain"
    terrain_dir.mkdir(parents=True, exist_ok=True)
    download_file(f"{PLATEAU_TERRAIN_URL}/layer.json", terrain_dir / "layer.json")
    count = 0
    for zoom in zooms:
        tiles: Set[Tuple[int, int]] = set()
        for bbox in bboxes:
            tiles.update(tile_range_for_bbox(bbox, zoom))
        for x, y in tiles:
            url = f"{PLATEAU_TERRAIN_URL}/{zoom}/{x}/{y}.terrain"
            destination = terrain_dir / str(zoom) / str(x) / f"{y}.terrain"
            try:
                if download_file(url, destination, timeout=30):
                    count += 1
            except requests.RequestException as e:
                print(f"[Terrain] skipped {url}: {e}")
    return count


def parse_zoom_range(value: str) -> List[int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def validate_manifest(cache_dir: Path) -> None:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    errors: List[str] = []
    for target_key, target in manifest.get("targets", {}).items():
        for field in ("name", "latitude", "longitude", "mesh_code", "municipality_code"):
            if not target.get(field):
                errors.append(f"{target_key}: missing {field}")

    for tileset in manifest.get("tilesets", []):
        local_path = cache_dir / tileset.get("local_path", "")
        if not local_path.exists():
            errors.append(f"missing tileset: {local_path}")

    if not (cache_dir / "terrain" / "layer.json").exists():
        errors.append("missing terrain/layer.json")

    if errors:
        raise RuntimeError("Local demo cache validation failed:\n" + "\n".join(errors))

    print("[Validate] local demo cache is usable")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare offline cache for Paper-CAD local demo.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--radius-m", type=float, default=900.0)
    parser.add_argument("--lod", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--imagery-zooms", default="14-18")
    parser.add_argument("--terrain-zooms", default="10-15")
    parser.add_argument("--max-tileset-files", type=int, default=20000)
    parser.add_argument("--skip-3dtiles", action="store_true")
    parser.add_argument("--skip-imagery", action="store_true")
    parser.add_argument("--skip-terrain", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    citygml_cache_dir = cache_dir / "citygml_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    citygml_cache_dir.mkdir(parents=True, exist_ok=True)

    os.environ["CITYGML_CACHE_ENABLED"] = "true"
    os.environ["CITYGML_CACHE_DIR"] = str(citygml_cache_dir)

    if args.validate:
        validate_manifest(cache_dir)
        return

    manifest: Dict[str, Any] = {
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "cache_dir": str(cache_dir),
        "targets": {},
        "tilesets": [],
    }
    mesh_to_codes: Dict[str, Set[str]] = {}
    bboxes: List[Tuple[float, float, float, float]] = []

    for static_target in LOCAL_DEMO_TARGETS:
        center_mesh = latlon_to_mesh_3rd(static_target.latitude, static_target.longitude)
        mesh_codes = get_neighboring_meshes_3rd(center_mesh)
        target = {
            "key": static_target.key,
            "name": static_target.canonical_name,
            "aliases": list(static_target.aliases),
            "latitude": static_target.latitude,
            "longitude": static_target.longitude,
            "display_name": static_target.display_name,
            "municipality_code": static_target.municipality_code,
            "mesh_code": static_target.mesh_code or center_mesh,
            "building_id": static_target.building_id,
            "cached_mesh_codes": mesh_codes,
        }

        print(f"\n[Target] {target['name']} center mesh={center_mesh}")
        for mesh_code in mesh_codes:
            area_codes = download_citygml_for_mesh(mesh_code, citygml_cache_dir)
            if area_codes:
                mesh_to_codes.setdefault(mesh_code, set()).update(area_codes)

        merge_mesh_index(citygml_cache_dir / "mesh_to_ward_index.json", mesh_to_codes)
        plateau_fetcher._MESH_INDEX_CACHE = None
        target = resolve_target_building(target, citygml_cache_dir)
        manifest["targets"][static_target.key] = target
        bboxes.append(bbox_for_point(static_target.latitude, static_target.longitude, args.radius_m))

    municipalities = sorted(
        {
            str(target.get("municipality_code"))
            for target in manifest["targets"].values()
            if target.get("municipality_code")
        }
    )

    if not args.skip_3dtiles:
        for municipality_code in municipalities:
            dataset = asyncio.run(fetch_tileset_dataset(municipality_code, args.lod))
            destination = local_tileset_path(cache_dir, municipality_code, args.lod)
            print(f"[3D Tiles] {municipality_code} -> {destination.relative_to(cache_dir)}")
            file_count = download_3dtiles_recursive(
                dataset["tileset_url"],
                destination,
                args.max_tileset_files,
            )
            mesh_codes = sorted(
                {
                    mesh
                    for target in manifest["targets"].values()
                    if target.get("municipality_code") == municipality_code
                    for mesh in target.get("cached_mesh_codes", [])
                }
            )
            manifest["tilesets"].append(
                {
                    "municipality_code": municipality_code,
                    "municipality_name": dataset.get("municipality_name"),
                    "lod": args.lod,
                    "remote_url": dataset["tileset_url"],
                    "local_path": str(destination.relative_to(cache_dir)),
                    "mesh_codes": mesh_codes,
                    "file_count": file_count,
                }
            )

    if not args.skip_imagery:
        count = download_imagery(cache_dir, bboxes, parse_zoom_range(args.imagery_zooms))
        print(f"[Imagery] downloaded {count} new tile(s)")

    if not args.skip_terrain:
        count = download_terrain(cache_dir, bboxes, parse_zoom_range(args.terrain_zooms))
        print(f"[Terrain] downloaded {count} new tile(s)")

    manifest_path = cache_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {manifest_path}")
    validate_manifest(cache_dir)


if __name__ == "__main__":
    main()
