#!/usr/bin/env python3
"""
Build mesh2 -> municipality code mapping from N03 GeoJSON.

Input requirements:
- GeoJSON in EPSG:4326 (lon/lat degrees)
- Municipality code property: N03_007 (default)

Output:
    backend/data/mesh2_municipality.json
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from shapely.geometry import box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

MESH2_LAT_STEP = 5.0 / 60.0
MESH2_LON_STEP = 7.5 / 60.0
MESH2_CELL_AREA = MESH2_LAT_STEP * MESH2_LON_STEP


def _mesh2_indices_from_lat(lat: float) -> int:
    return int(math.floor(lat * 60.0 / 5.0))


def _mesh2_indices_from_lon(lon: float) -> int:
    return int(math.floor((lon - 100.0) * 60.0 / 7.5))


def _mesh2_code_from_indices(lat_index: int, lon_index: int) -> str:
    p = lat_index // 8
    r = lat_index % 8
    q = lon_index // 8
    s = lon_index % 8
    return f"{p:02d}{q:02d}{r}{s}"


def _mesh2_bounds_from_code(mesh2_code: str) -> Tuple[float, float, float, float]:
    p = int(mesh2_code[0:2])
    q = int(mesh2_code[2:4])
    r = int(mesh2_code[4])
    s = int(mesh2_code[5])

    lat_min = (p * 40.0 + r * 5.0) / 60.0
    lon_min = 100.0 + (q * 60.0 + s * 7.5) / 60.0

    lat_max = lat_min + MESH2_LAT_STEP
    lon_max = lon_min + MESH2_LON_STEP

    return lon_min, lat_min, lon_max, lat_max


def _mesh2_codes_for_bounds(bounds: Tuple[float, float, float, float]) -> Iterable[str]:
    minx, miny, maxx, maxy = bounds

    lat_start = _mesh2_indices_from_lat(miny)
    lat_end = _mesh2_indices_from_lat(maxy)
    lon_start = _mesh2_indices_from_lon(minx)
    lon_end = _mesh2_indices_from_lon(maxx)

    for lat_index in range(lat_start, lat_end + 1):
        if lat_index < 0:
            continue
        for lon_index in range(lon_start, lon_end + 1):
            if lon_index < 0:
                continue
            yield _mesh2_code_from_indices(lat_index, lon_index)


def _load_features(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "features" in data:
        return data["features"]
    if isinstance(data, list):
        return data

    raise ValueError("Unsupported GeoJSON format: expected FeatureCollection or list")


def _extract_code(props: dict, code_keys: List[str]) -> str | None:
    for key in code_keys:
        if key in props and props[key] not in (None, ""):
            raw = str(props[key]).strip()
            if raw.isdigit() and len(raw) < 5:
                raw = raw.zfill(5)
            if raw.isdigit() and len(raw) == 5:
                # Skip prefecture-level codes (xx000)
                if raw.endswith("000"):
                    return None
                return raw
    return None


def build_mapping(
    features: List[dict], code_keys: List[str], min_overlap_ratio: float
) -> Dict[str, List[str]]:
    geoms_by_code: Dict[str, List] = {}
    for feature in features:
        props = feature.get("properties") or {}
        code = _extract_code(props, code_keys)
        if not code:
            continue

        geom = shape(feature.get("geometry"))
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        geoms_by_code.setdefault(code, []).append(geom)

    merged_by_code = {code: unary_union(geoms) for code, geoms in geoms_by_code.items()}

    mesh2_to_codes: Dict[str, set] = {}
    for code, geom in merged_by_code.items():
        if geom.is_empty:
            continue
        prepared = prep(geom)
        for mesh2_code in _mesh2_codes_for_bounds(geom.bounds):
            lon_min, lat_min, lon_max, lat_max = _mesh2_bounds_from_code(mesh2_code)
            cell = box(lon_min, lat_min, lon_max, lat_max)
            if not prepared.intersects(cell):
                continue
            if min_overlap_ratio > 0.0:
                overlap_ratio = geom.intersection(cell).area / MESH2_CELL_AREA
                if overlap_ratio < min_overlap_ratio:
                    continue
            mesh2_to_codes.setdefault(mesh2_code, set()).add(code)

    return {mesh2: sorted(codes) for mesh2, codes in mesh2_to_codes.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build mesh2 -> municipality mapping JSON.")
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="Path(s) to N03 GeoJSON (EPSG:4326).",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent.parent / "data" / "mesh2_municipality.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--code-keys",
        default="N03_007",
        help="Comma-separated property keys for municipality code.",
    )
    parser.add_argument(
        "--min-overlap-ratio",
        type=float,
        default=0.0,
        help="Minimum overlap ratio (0-1) to include a mesh2 cell.",
    )
    parser.add_argument(
        "--source-name",
        default="National Land Numerical Information (N03 Administrative Areas)",
        help="Source name for metadata.",
    )
    parser.add_argument(
        "--source-url",
        default="https://nlftp.mlit.go.jp/ksj/",
        help="Source URL for metadata.",
    )

    args = parser.parse_args()

    input_paths = [Path(p) for p in args.input]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features: List[dict] = []
    for input_path in input_paths:
        features.extend(_load_features(input_path))
    code_keys = [key.strip() for key in args.code_keys.split(",") if key.strip()]

    mapping = build_mapping(features, code_keys, args.min_overlap_ratio)

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_name": args.source_name,
            "source_url": args.source_url,
            "input_file": [str(p) for p in input_paths],
            "min_overlap_ratio": args.min_overlap_ratio,
        },
        "mesh2_to_municipalities": mapping,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)

    print(f"Saved {len(mapping)} mesh2 entries to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
