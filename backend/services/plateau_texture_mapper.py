"""
CityGML texture mapping helper for PLATEAU textured unfold (beta).

This module extracts app:ParameterizedTexture data from CityGML, resolves target
polygons for a specific building, and maps those textured polygons to STEP face
numbers used by the unfold pipeline.
"""

from __future__ import annotations

import base64
import hashlib
import math
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests

from services.citygml.core.constants import NS, RECENTERING_DISTANCE_THRESHOLD
from services.citygml.parsers.coordinates import extract_polygon_xyz
from services.citygml.transforms.crs_detection import detect_source_crs
from services.citygml.transforms.transformers import make_xyz_transformer
from services.citygml.utils.xlink_resolver import build_id_index, extract_polygon_with_xlink

try:
    from services.coordinate_utils import is_geographic_crs, recommend_projected_crs
except ImportError:
    from coordinate_utils import is_geographic_crs, recommend_projected_crs


def _is_local_demo() -> bool:
    return os.getenv("ENV", os.getenv("PYTHON_ENV", "development")) == "local_demo"


@dataclass
class TextureTarget:
    polygon_id: str
    uv_coords: List[Tuple[float, float]]


@dataclass
class TextureEntry:
    texture_id: str
    image_uri: str
    mime_type: Optional[str]
    targets: List[TextureTarget]


@dataclass
class PolygonFeature:
    polygon_id: str
    centroid: Tuple[float, float, float]
    normal: Optional[Tuple[float, float, float]]
    area: float


@dataclass
class StepFaceFeature:
    face_number: int
    centroid: Tuple[float, float, float]
    normal: Optional[Tuple[float, float, float]]
    area: float


def _as_float_tuple3(values: Sequence[Any], fallback: Tuple[float, float, float]) -> Tuple[float, float, float]:
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return fallback
    try:
        return (float(values[0]), float(values[1]), float(values[2]))
    except Exception:
        return fallback


def _vec_sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_norm(a: Tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, _vec_dot(a, a)))


def _normalize(v: Optional[Tuple[float, float, float]]) -> Optional[Tuple[float, float, float]]:
    if v is None:
        return None
    n = _vec_norm(v)
    if n < 1e-12:
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def _distance(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return _vec_norm(_vec_sub(a, b))


def _remove_duplicate_closing(points: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    if len(points) >= 2 and _distance(points[0], points[-1]) < 1e-9:
        return points[:-1]
    return points


def _newell_normal(points: Sequence[Tuple[float, float, float]]) -> Optional[Tuple[float, float, float]]:
    if len(points) < 3:
        return None
    nx = 0.0
    ny = 0.0
    nz = 0.0
    for i in range(len(points)):
        x1, y1, z1 = points[i]
        x2, y2, z2 = points[(i + 1) % len(points)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return _normalize((nx, ny, nz))


def _fan_area_centroid(
    points: List[Tuple[float, float, float]],
    normal_hint: Optional[Tuple[float, float, float]] = None,
) -> Tuple[float, Tuple[float, float, float], Optional[Tuple[float, float, float]]]:
    points = _remove_duplicate_closing(points)
    if len(points) < 3:
        return 0.0, (0.0, 0.0, 0.0), None

    normal = _normalize(normal_hint) or _newell_normal(points)
    if normal is None:
        return 0.0, (0.0, 0.0, 0.0), None

    p0 = points[0]
    total_area = 0.0
    cx = 0.0
    cy = 0.0
    cz = 0.0
    for i in range(1, len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        cross = _vec_cross(_vec_sub(p1, p0), _vec_sub(p2, p0))
        tri_area = abs(_vec_dot(cross, normal)) * 0.5
        if tri_area <= 1e-12:
            continue
        tri_centroid = (
            (p0[0] + p1[0] + p2[0]) / 3.0,
            (p0[1] + p1[1] + p2[1]) / 3.0,
            (p0[2] + p1[2] + p2[2]) / 3.0,
        )
        total_area += tri_area
        cx += tri_centroid[0] * tri_area
        cy += tri_centroid[1] * tri_area
        cz += tri_centroid[2] * tri_area

    if total_area <= 1e-12:
        fallback = (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
            sum(p[2] for p in points) / len(points),
        )
        return 0.0, fallback, normal

    return total_area, (cx / total_area, cy / total_area, cz / total_area), normal


def _compute_polygon_feature(
    polygon_id: str,
    ext: List[Tuple[float, float, float]],
    holes: List[List[Tuple[float, float, float]]],
) -> Optional[PolygonFeature]:
    outer_area, outer_centroid, normal = _fan_area_centroid(ext)
    if outer_area <= 1e-12:
        return None

    hole_area_sum = 0.0
    hx = 0.0
    hy = 0.0
    hz = 0.0
    for hole in holes:
        area_h, centroid_h, _ = _fan_area_centroid(hole, normal_hint=normal)
        if area_h <= 1e-12:
            continue
        hole_area_sum += area_h
        hx += centroid_h[0] * area_h
        hy += centroid_h[1] * area_h
        hz += centroid_h[2] * area_h

    net_area = max(outer_area - hole_area_sum, 1e-9)
    if hole_area_sum > 1e-12:
        cx = (outer_centroid[0] * outer_area - hx) / net_area
        cy = (outer_centroid[1] * outer_area - hy) / net_area
        cz = (outer_centroid[2] * outer_area - hz) / net_area
        centroid = (cx, cy, cz)
    else:
        centroid = outer_centroid

    return PolygonFeature(
        polygon_id=polygon_id,
        centroid=centroid,
        normal=normal,
        area=net_area,
    )


def _build_transform(
    root: ET.Element,
    building_elem: ET.Element,
    auto_reproject: bool,
    source_crs: Optional[str],
    reproject_to: Optional[str],
) -> Tuple[Optional[Any], Dict[str, Any]]:
    detected_crs, sample_lat, sample_lon = detect_source_crs(root)
    src = source_crs or detected_crs or "EPSG:6697"
    dst = reproject_to
    if not dst and auto_reproject and is_geographic_crs(src):
        dst = recommend_projected_crs(src, sample_lat, sample_lon)

    xyz_transform = None
    if dst:
        try:
            xyz_transform = make_xyz_transformer(src, dst)
        except Exception:
            xyz_transform = None

    coords: List[Tuple[float, float, float]] = []
    for poly in building_elem.findall(".//gml:Polygon", NS):
        ext, holes = extract_polygon_xyz(poly)
        coords.extend(ext)
        for hole in holes:
            coords.extend(hole)

    offset = None
    if coords:
        transformed: List[Tuple[float, float, float]] = []
        if xyz_transform:
            for x, y, z in coords:
                try:
                    transformed.append(tuple(map(float, xyz_transform(x, y, z))))
                except Exception:
                    transformed.append((float(x), float(y), float(z)))
        else:
            transformed = [(float(x), float(y), float(z)) for x, y, z in coords]

        xs = [p[0] for p in transformed]
        ys = [p[1] for p in transformed]
        zs = [p[2] for p in transformed]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0
        dist = math.sqrt(cx * cx + cy * cy + cz * cz)
        if dist > RECENTERING_DISTANCE_THRESHOLD:
            offset = (-cx, -cy, -cz)

            if xyz_transform:
                original = xyz_transform

                def wrapped(x: float, y: float, z: float) -> Tuple[float, float, float]:
                    tx, ty, tz = original(x, y, z)
                    return (tx + offset[0], ty + offset[1], tz + offset[2])

                xyz_transform = wrapped
            else:

                def wrapped(x: float, y: float, z: float) -> Tuple[float, float, float]:
                    return (x + offset[0], y + offset[1], z + offset[2])

                xyz_transform = wrapped

    return xyz_transform, {
        "source_crs": src,
        "target_crs": dst,
        "recenter_offset": offset,
    }


def _apply_transform_ring(
    ring: List[Tuple[float, float, float]],
    xyz_transform: Optional[Any],
) -> List[Tuple[float, float, float]]:
    if not xyz_transform:
        return [(float(x), float(y), float(z)) for x, y, z in ring]
    out: List[Tuple[float, float, float]] = []
    for x, y, z in ring:
        try:
            tx, ty, tz = xyz_transform(x, y, z)
            out.append((float(tx), float(ty), float(tz)))
        except Exception:
            out.append((float(x), float(y), float(z)))
    return out


def _get_gml_id(elem: ET.Element) -> Optional[str]:
    return elem.get(f"{{{NS['gml']}}}id") or elem.get("id")


def _collect_building_polygons(
    building_elem: ET.Element,
    id_index: Dict[str, ET.Element],
) -> Dict[str, ET.Element]:
    polygons: Dict[str, ET.Element] = {}

    for poly in building_elem.findall(".//gml:Polygon", NS):
        poly_id = _get_gml_id(poly)
        if poly_id:
            polygons[poly_id] = poly

    for surf_member in building_elem.findall(".//gml:surfaceMember", NS):
        poly = extract_polygon_with_xlink(surf_member, id_index, debug=False)
        if poly is None:
            continue
        poly_id = _get_gml_id(poly)
        if poly_id:
            polygons[poly_id] = poly

    return polygons


def _resolve_target_id_to_polygon_id(
    target_id: str,
    id_index: Dict[str, ET.Element],
) -> Optional[str]:
    cleaned = (target_id or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]

    candidates = [cleaned]
    if "_" in cleaned:
        prefix, suffix = cleaned.rsplit("_", 1)
        if suffix.isdigit():
            candidates.append(prefix)

    visited: Set[str] = set()

    def resolve_one(elem_id: str) -> Optional[str]:
        if elem_id in visited:
            return None
        visited.add(elem_id)

        elem = id_index.get(elem_id)
        if elem is None:
            return None

        if elem.tag == f"{{{NS['gml']}}}Polygon":
            return elem_id

        poly = elem.find(".//gml:Polygon", NS)
        if poly is not None:
            poly_id = _get_gml_id(poly)
            if poly_id:
                return poly_id

        poly = extract_polygon_with_xlink(elem, id_index, debug=False)
        if poly is not None:
            poly_id = _get_gml_id(poly)
            if poly_id:
                return poly_id

        href = elem.get(f"{{{NS['xlink']}}}href")
        if href:
            return resolve_one(href.lstrip("#"))
        return None

    for candidate in candidates:
        resolved = resolve_one(candidate)
        if resolved:
            return resolved
    return None


def _parse_uv_pairs(target_elem: ET.Element) -> List[Tuple[float, float]]:
    uv_pairs: List[Tuple[float, float]] = []
    for coords_elem in target_elem.findall(".//app:textureCoordinates", NS):
        txt = (coords_elem.text or "").strip()
        if not txt:
            continue
        values: List[float] = []
        for token in txt.split():
            try:
                values.append(float(token))
            except ValueError:
                continue
        if len(values) < 2:
            continue
        for i in range(0, len(values) - 1, 2):
            uv_pairs.append((values[i], values[i + 1]))
    return uv_pairs


def _extract_parameterized_textures(
    root: ET.Element,
    id_index: Dict[str, ET.Element],
    building_polygon_ids: Set[str],
) -> List[TextureEntry]:
    textures: List[TextureEntry] = []
    for idx, tex in enumerate(root.findall(".//app:ParameterizedTexture", NS), 1):
        texture_id = _get_gml_id(tex) or f"texture_{idx}"
        image_uri = ((tex.findtext("./app:imageURI", "", NS) or "").strip())
        if not image_uri:
            continue
        mime_type = ((tex.findtext("./app:mimeType", "", NS) or "").strip()) or None

        per_polygon: Dict[str, List[Tuple[float, float]]] = {}
        for target_elem in tex.findall(".//app:target", NS):
            uri = target_elem.get("uri") or target_elem.get(f"{{{NS['xlink']}}}href")
            if not uri:
                continue
            polygon_id = _resolve_target_id_to_polygon_id(uri, id_index)
            if not polygon_id or polygon_id not in building_polygon_ids:
                continue
            uv = _parse_uv_pairs(target_elem)
            current = per_polygon.get(polygon_id)
            if current is None or len(uv) > len(current):
                per_polygon[polygon_id] = uv

        if not per_polygon:
            continue

        targets = [TextureTarget(polygon_id=pid, uv_coords=uv) for pid, uv in per_polygon.items()]
        textures.append(
            TextureEntry(
                texture_id=texture_id,
                image_uri=image_uri,
                mime_type=mime_type,
                targets=targets,
            )
        )
    return textures


def _estimate_tile_count(uv_pairs: List[Tuple[float, float]]) -> int:
    if len(uv_pairs) < 2:
        return 1
    us = [u for u, _ in uv_pairs]
    vs = [v for _, v in uv_pairs]
    span_u = max(us) - min(us)
    span_v = max(vs) - min(vs)
    span = max(span_u, span_v)
    if not math.isfinite(span) or span <= 0:
        return 1
    return max(1, min(8, int(round(span))))


def _resolve_image_data_uri(
    image_uri: str,
    mime_type: Optional[str],
    source_urls: Sequence[str],
    timeout: int = 15,
    max_bytes: int = 12 * 1024 * 1024,
) -> Tuple[Optional[str], Optional[str]]:
    cleaned = (image_uri or "").strip()
    if not cleaned:
        return None, None

    if cleaned.startswith("data:image"):
        return cleaned, "inline-data-uri"

    local_demo = _is_local_demo()
    parsed = urlparse(cleaned)
    candidates: List[str] = []
    if parsed.scheme in ("http", "https") and not local_demo:
        candidates.append(cleaned)

    for source_url in source_urls:
        source_parsed = urlparse(source_url)
        if source_parsed.scheme in ("http", "https") and not local_demo:
            candidates.append(urljoin(source_url, cleaned))
        elif source_parsed.scheme not in ("http", "https"):
            source_path = Path(source_url)
            source_dir = source_path.parent if source_path.is_file() else source_path
            candidates.append(str(source_dir / cleaned))

    # Local filesystem fallback (cache / local data runs)
    local_path = Path(cleaned)
    if local_path.exists():
        candidates.append(str(local_path))

    seen: Set[str] = set()
    dedup_candidates: List[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        dedup_candidates.append(candidate)

    for candidate in dedup_candidates:
        parsed_candidate = urlparse(candidate)
        raw_data: Optional[bytes] = None
        resolved_mime = mime_type

        try:
            if parsed_candidate.scheme in ("http", "https"):
                if local_demo:
                    continue
                response = requests.get(candidate, timeout=timeout)
                if response.status_code != 200:
                    continue
                content_len = response.headers.get("content-length")
                if content_len:
                    try:
                        if int(content_len) > max_bytes:
                            continue
                    except ValueError:
                        pass
                raw_data = response.content
                if len(raw_data) > max_bytes:
                    continue
                if not resolved_mime:
                    header_mime = response.headers.get("content-type", "").split(";")[0].strip()
                    if header_mime:
                        resolved_mime = header_mime
            else:
                candidate_path = Path(candidate)
                if not candidate_path.exists() or not candidate_path.is_file():
                    continue
                if candidate_path.stat().st_size > max_bytes:
                    continue
                raw_data = candidate_path.read_bytes()
                if not resolved_mime:
                    guessed, _ = mimetypes.guess_type(str(candidate_path))
                    resolved_mime = guessed
        except Exception:
            continue

        if not raw_data:
            continue
        resolved_mime = resolved_mime or "image/png"
        encoded = base64.b64encode(raw_data).decode("ascii")
        return f"data:{resolved_mime};base64,{encoded}", candidate

    return None, None


def _to_step_features(step_faces_data: Sequence[Dict[str, Any]]) -> List[StepFaceFeature]:
    features: List[StepFaceFeature] = []
    for i, face in enumerate(step_faces_data):
        face_number = int(face.get("face_number", i + 1))
        centroid = _as_float_tuple3(face.get("centroid", [0.0, 0.0, 0.0]), (0.0, 0.0, 0.0))
        normal_values = face.get("normal_vector")
        normal = None
        if isinstance(normal_values, (list, tuple)) and len(normal_values) >= 3:
            normal = _normalize(_as_float_tuple3(normal_values, (0.0, 0.0, 0.0)))
        try:
            area = float(face.get("area", 0.0) or 0.0)
        except Exception:
            area = 0.0
        features.append(
            StepFaceFeature(
                face_number=face_number,
                centroid=centroid,
                normal=normal,
                area=area,
            )
        )
    return features


def _point_cloud_diagonal(points: Iterable[Tuple[float, float, float]]) -> float:
    pts = list(points)
    if not pts:
        return 1.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    return max(1e-6, math.sqrt(dx * dx + dy * dy + dz * dz))


def _match_face(
    polygon: PolygonFeature,
    step_faces: Sequence[StepFaceFeature],
    used_faces: Set[int],
    distance_scale: float,
) -> Tuple[Optional[StepFaceFeature], float]:
    def _score_face_polygon(face: StepFaceFeature, polygon_feature: PolygonFeature) -> float:
        normal_score = 0.35
        if polygon_feature.normal and face.normal:
            normal_score = abs(_vec_dot(polygon_feature.normal, face.normal))
        elif polygon_feature.normal or face.normal:
            # One side has missing normal information; keep score moderate.
            normal_score = 0.45

        dist = _distance(polygon_feature.centroid, face.centroid)
        distance_score = math.exp(-(dist / max(distance_scale, 1e-6)))

        area_score = 0.5
        if polygon_feature.area > 1e-6 and face.area > 1e-6:
            area_score = min(polygon_feature.area, face.area) / max(polygon_feature.area, face.area)

        return (0.55 * normal_score) + (0.40 * distance_score) + (0.05 * area_score)

    best_face = None
    best_score = -1.0

    for face in step_faces:
        if face.face_number in used_faces:
            continue

        score = _score_face_polygon(face, polygon)
        if score > best_score:
            best_face = face
            best_score = score

    return best_face, best_score


def build_plateau_texture_mappings(
    citygml_xml: str,
    building_gml_id: str,
    step_faces_data: Sequence[Dict[str, Any]],
    source_urls: Optional[Sequence[str]] = None,
    auto_reproject: bool = True,
    source_crs: Optional[str] = None,
    reproject_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build unfold texture mappings from CityGML appearance data for one building.

    Returns:
        {
            "texture_mappings": [...],
            "warnings": [{"type": str, "message": str, "details": {...}}, ...],
            "stats": {...}
        }
    """
    source_urls = list(source_urls or [])
    warnings: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {
        "building_id": building_gml_id,
        "step_faces": len(step_faces_data),
        "parameterized_textures": 0,
        "texture_targets": 0,
        "mapped_faces": 0,
        "images_resolved": 0,
        "images_failed": 0,
    }

    try:
        root = ET.fromstring(citygml_xml)
    except ET.ParseError as e:
        warnings.append(
            {
                "type": "texture_mapping_error",
                "message": "CityGML XML parse failed. Generating unfold without textures.",
                "details": {"error": str(e)},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    id_index = build_id_index(root)

    building_elem = None
    for b in root.findall(".//bldg:Building", NS):
        if _get_gml_id(b) == building_gml_id:
            building_elem = b
            break

    if building_elem is None:
        warnings.append(
            {
                "type": "texture_mapping_warning",
                "message": "Target building not found in CityGML. Generating unfold without textures.",
                "details": {"building_id": building_gml_id},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    xyz_transform, transform_meta = _build_transform(
        root=root,
        building_elem=building_elem,
        auto_reproject=auto_reproject,
        source_crs=source_crs,
        reproject_to=reproject_to,
    )
    stats["transform"] = transform_meta

    building_polygons = _collect_building_polygons(building_elem, id_index)
    if not building_polygons:
        warnings.append(
            {
                "type": "texture_mapping_warning",
                "message": "No polygon geometry found for target building.",
                "details": {"building_id": building_gml_id},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    polygon_features: Dict[str, PolygonFeature] = {}
    for poly_id, poly in building_polygons.items():
        ext, holes = extract_polygon_xyz(poly)
        if not ext:
            continue
        ext_t = _apply_transform_ring(ext, xyz_transform)
        holes_t = [_apply_transform_ring(h, xyz_transform) for h in holes]
        feature = _compute_polygon_feature(poly_id, ext_t, holes_t)
        if feature is not None:
            polygon_features[poly_id] = feature

    if not polygon_features:
        warnings.append(
            {
                "type": "texture_mapping_warning",
                "message": "Polygon feature extraction failed for target building.",
                "details": {"building_id": building_gml_id},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    textures = _extract_parameterized_textures(
        root=root,
        id_index=id_index,
        building_polygon_ids=set(polygon_features.keys()),
    )
    stats["parameterized_textures"] = len(textures)
    stats["texture_targets"] = sum(len(t.targets) for t in textures)
    if not textures:
        warnings.append(
            {
                "type": "texture_mapping_info",
                "message": "No ParameterizedTexture found for this building.",
                "details": {"building_id": building_gml_id},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    step_features = _to_step_features(step_faces_data)
    if not step_features:
        warnings.append(
            {
                "type": "texture_mapping_warning",
                "message": "STEP face analysis is empty. Texture mapping skipped.",
                "details": {},
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    distance_scale = max(_point_cloud_diagonal([f.centroid for f in step_features]) * 0.5, 10.0)
    used_faces: Set[int] = set()
    texture_mappings_by_face: Dict[int, Dict[str, Any]] = {}
    image_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    pattern_cache: Dict[str, str] = {}
    resolved_targets: List[Dict[str, Any]] = []

    for texture in textures:
        image_key = texture.image_uri
        if image_key not in image_cache:
            image_cache[image_key] = _resolve_image_data_uri(
                image_uri=texture.image_uri,
                mime_type=texture.mime_type,
                source_urls=source_urls,
            )
        image_data_uri, resolved_image_ref = image_cache[image_key]

        if not image_data_uri:
            stats["images_failed"] += 1
            warnings.append(
                {
                    "type": "texture_image_fetch_failed",
                    "message": "Failed to resolve texture image. Target faces will be left untextured.",
                    "details": {"image_uri": texture.image_uri},
                }
            )
            continue
        stats["images_resolved"] += 1

        pattern_seed = resolved_image_ref or texture.image_uri
        if pattern_seed not in pattern_cache:
            digest = hashlib.sha1(pattern_seed.encode("utf-8")).hexdigest()[:12]
            pattern_cache[pattern_seed] = f"plateau_{digest}"
        pattern_id = pattern_cache[pattern_seed]

        for target in texture.targets:
            polygon = polygon_features.get(target.polygon_id)
            if polygon is None:
                continue
            resolved_targets.append(
                {
                    "texture_id": texture.texture_id,
                    "polygon_id": target.polygon_id,
                    "polygon": polygon,
                    "pattern_id": pattern_id,
                    "tile_count": _estimate_tile_count(target.uv_coords),
                    "image_data": image_data_uri,
                }
            )

    if not resolved_targets:
        warnings.append(
            {
                "type": "texture_mapping_info",
                "message": "Texture targets were found but no valid polygon references could be resolved.",
                "details": {
                    "parameterized_textures": stats["parameterized_textures"],
                    "texture_targets": stats["texture_targets"],
                },
            }
        )
        return {"texture_mappings": [], "warnings": warnings, "stats": stats}

    unmatched_target_count = 0
    for target in resolved_targets:
        polygon = target["polygon"]
        matched_face, score = _match_face(
            polygon=polygon,
            step_faces=step_features,
            used_faces=used_faces,
            distance_scale=distance_scale,
        )
        if matched_face is None or score < 0.28:
            unmatched_target_count += 1
            continue

        mapping = {
            "faceNumber": matched_face.face_number,
            "patternId": target["pattern_id"],
            "tileCount": target["tile_count"],
            "rotation": 0,
            "imageData": target["image_data"],
        }
        existing = texture_mappings_by_face.get(matched_face.face_number)
        if existing is None or score > existing["score"]:
            texture_mappings_by_face[matched_face.face_number] = {
                "score": score,
                "mapping": mapping,
                "source": "primary",
            }
        used_faces.add(matched_face.face_number)

    primary_count = len(texture_mappings_by_face)

    def _score_face_to_target(face: StepFaceFeature, target_item: Dict[str, Any]) -> float:
        polygon = target_item["polygon"]

        normal_score = 0.35
        if polygon.normal and face.normal:
            normal_score = abs(_vec_dot(polygon.normal, face.normal))
        elif polygon.normal or face.normal:
            normal_score = 0.45

        dist = _distance(polygon.centroid, face.centroid)
        distance_score = math.exp(-(dist / max(distance_scale, 1e-6)))

        area_score = 0.5
        if polygon.area > 1e-6 and face.area > 1e-6:
            area_score = min(polygon.area, face.area) / max(polygon.area, face.area)

        return (0.55 * normal_score) + (0.40 * distance_score) + (0.05 * area_score)

    fallback_count = 0
    remaining_faces = [f for f in step_features if f.face_number not in used_faces]
    for face in remaining_faces:
        best_target = None
        best_score = -1.0
        for target in resolved_targets:
            score = _score_face_to_target(face, target)
            if score > best_score:
                best_target = target
                best_score = score

        if best_target is None or best_score < 0.20:
            continue

        texture_mappings_by_face[face.face_number] = {
            "score": best_score,
            "mapping": {
                "faceNumber": face.face_number,
                "patternId": best_target["pattern_id"],
                "tileCount": best_target["tile_count"],
                "rotation": 0,
                "imageData": best_target["image_data"],
            },
            "source": "fallback",
        }
        used_faces.add(face.face_number)
        fallback_count += 1

    texture_mappings: List[Dict[str, Any]] = [
        item["mapping"] for _, item in sorted(texture_mappings_by_face.items(), key=lambda x: x[0])
    ]

    stats["mapped_faces"] = len(texture_mappings)
    stats["primary_mapped_faces"] = primary_count
    stats["fallback_mapped_faces"] = fallback_count
    stats["unmatched_texture_targets"] = unmatched_target_count

    if unmatched_target_count > 0 and texture_mappings:
        warnings.append(
            {
                "type": "texture_mapping_partial",
                "message": "Some texture targets could not be matched directly; fallback mapping was applied.",
                "details": {
                    "unmatched_targets": unmatched_target_count,
                    "primary_mapped_faces": primary_count,
                    "fallback_mapped_faces": fallback_count,
                },
            }
        )

    if not texture_mappings:
        warnings.append(
            {
                "type": "texture_mapping_info",
                "message": "No texture mappings could be generated. Unfold was generated without textures.",
                "details": {
                    "parameterized_textures": stats["parameterized_textures"],
                    "texture_targets": stats["texture_targets"],
                    "unmatched_targets": unmatched_target_count,
                },
            }
        )

    return {
        "texture_mappings": texture_mappings,
        "warnings": warnings,
        "stats": stats,
    }
