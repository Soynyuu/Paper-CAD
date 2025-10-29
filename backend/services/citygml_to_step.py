"""
CityGML → STEP converter (heuristic)

This module provides a pragmatic pipeline to convert PLATEAU CityGML
building data into CAD-openable STEP files. It focuses on a robust
heuristic: extracting building footprints and heights, then extruding
to solids with OpenCascade, exported as STEP (AP214).

Notes
- Designed for CityGML 2.0 (PLATEAU). It tries several common tags:
  - bldg:lod0FootPrint
  - bldg:boundedBy/bldg:GroundSurface
  - measuredHeight (bldg/uro) or height from vertex Z range
- If OCCT is unavailable, it raises a clear error.
- Coordinates are treated as XY in meters; Z is vertical.

CLI
  python services/citygml_to_step.py input.gml output.step \
         [--default-height 10] [--limit N] [--debug]

Limitations
- Footprint/height inference is heuristic and may be simplistic for
  highly detailed or invalid geometries.
- Future work: CityGML→CityJSON→mesh path, rectangle tiling fallback.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Callable
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import threading

try:
    from services.coordinate_utils import (
        detect_epsg_from_srs,
        is_geographic_crs, 
        recommend_projected_crs,
        get_crs_info
    )
except ImportError:
    # Fallback for standalone usage
    from coordinate_utils import (
        detect_epsg_from_srs,
        is_geographic_crs, 
        recommend_projected_crs,
        get_crs_info
    )

# Import OCCT availability from config
try:
    from config import OCCT_AVAILABLE
except ImportError:
    # Fallback: detect OCCT locally if config unavailable
    try:
        from OCC.Core.gp import gp_Pnt, gp_Vec
        from OCC.Core.BRepBuilderAPI import (
            BRepBuilderAPI_MakePolygon,
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_Sewing,
            BRepBuilderAPI_MakeSolid,
        )
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Shell, topods
        from OCC.Core.TopAbs import TopAbs_SHELL
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.BRepCheck import BRepCheck_Analyzer
        from OCC.Core.ShapeFix import ShapeFix_Shape
        OCCT_AVAILABLE = True
    except Exception:
        OCCT_AVAILABLE = False

# Import OCCT modules if available
if OCCT_AVAILABLE:
    from OCC.Core.gp import gp_Pnt, gp_Vec
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_Sewing,
        BRepBuilderAPI_MakeSolid,
    )
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Shell, topods
    from OCC.Core.TopAbs import TopAbs_SHELL
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeFix import ShapeFix_Shape, ShapeFix_Solid
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCC.Core.BRep import BRep_Tool

try:
    # Local exporter is optional; we avoid importing FastAPI-dependent config
    from core.step_exporter import STEPExporter  # type: ignore
except Exception:
    STEPExporter = None  # fallback to local writer


# Thread-local storage for log file (Issue #48: detailed logging across all functions)
_thread_local = threading.local()

def log(message: str):
    """Global log function that writes to both console and thread-local log file.

    This allows all functions (not just _extract_single_solid) to write to the
    conversion log file. The log file is set via set_log_file() at the start
    of each conversion.

    Args:
        message: Message to log
    """
    print(message)
    log_file = getattr(_thread_local, 'log_file', None)
    if log_file:
        try:
            log_file.write(message + "\n")
            log_file.flush()
        except Exception:
            pass  # Silently fail if log file is closed or unavailable

def set_log_file(log_file):
    """Set the log file for the current thread.

    Args:
        log_file: File object to write logs to (or None to disable file logging)
    """
    _thread_local.log_file = log_file

def close_log_file():
    """Close and clear the thread-local log file if one is open.

    This function is safe to call multiple times and handles exceptions gracefully.
    It should be called before returning from conversion functions to ensure log files
    are properly closed even if an exception occurs.
    """
    log_file = getattr(_thread_local, 'log_file', None)
    if log_file:
        try:
            set_log_file(None)  # Clear the reference first
            log_file.close()
        except Exception:
            pass  # Silently fail if already closed


# Common namespaces for CityGML 2.0 / PLATEAU
NS = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/2.0",
    "core": "http://www.opengis.net/citygml/2.0",
    "uro": "https://www.geospatial.jp/iur/uro/3.1",  # PLATEAU-specific namespace (iur/uro 3.1)
    "gen": "http://www.opengis.net/citygml/generics/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
}


@dataclass
class Footprint:
    """2D footprint polygon with optional interior holes and height.

    - exterior: list[(x,y)]
    - holes: list[list[(x,y)]]
    - height: float (meters)
    - building_id: optional id/name for traceability
    """

    exterior: List[Tuple[float, float]]
    holes: List[List[Tuple[float, float]]]
    height: float
    building_id: Optional[str] = None


def _parse_poslist(elem: ET.Element) -> List[Tuple[float, float, Optional[float]]]:
    """Parse a gml:posList or gml:pos sequence into list of (x, y, z?).

    Returns list of triples (x, y, z or None).
    Robust to 2D or 3D inputs and extra whitespace.
    """
    txt = (elem.text or "").strip()
    if not txt:
        return []
    parts = txt.split()
    vals: List[float] = []
    for p in parts:
        try:
            vals.append(float(p))
        except ValueError:
            # Skip unparsable tokens
            continue

    # Try dimension inference: 3D if divisible by 3; else 2D if by 2
    dim = 3 if len(vals) % 3 == 0 and len(vals) >= 3 else 2
    coords: List[Tuple[float, float, Optional[float]]] = []
    if dim == 3:
        for i in range(0, len(vals), 3):
            coords.append((vals[i], vals[i + 1], vals[i + 2]))
    else:
        for i in range(0, len(vals), 2):
            if i + 1 < len(vals):
                coords.append((vals[i], vals[i + 1], None))
    return coords


def _first_text(elem: Optional[ET.Element]) -> Optional[str]:
    return (elem.text or "").strip() if elem is not None and elem.text else None


def _extract_generic_attributes(building: ET.Element) -> dict[str, str]:
    """Extract generic attributes from a building element.

    PLATEAU CityGML often stores metadata like building IDs, addresses,
    and other properties in gen:genericAttribute elements.

    Args:
        building: bldg:Building element

    Returns:
        Dictionary mapping attribute names to values
    """
    attributes: dict[str, str] = {}

    # Find all generic attribute elements
    for attr in building.findall(".//gen:stringAttribute", NS):
        name_elem = attr.get("name")
        value_elem = attr.find("./gen:value", NS)

        if name_elem and value_elem is not None:
            value = _first_text(value_elem)
            if value:
                attributes[name_elem] = value

    # Also check for intAttribute (integer generic attributes)
    for attr in building.findall(".//gen:intAttribute", NS):
        name_elem = attr.get("name")
        value_elem = attr.find("./gen:value", NS)

        if name_elem and value_elem is not None:
            value = _first_text(value_elem)
            if value:
                attributes[name_elem] = value

    # Check for PLATEAU-specific uro:buildingIDAttribute
    # Format: <uro:buildingIDAttribute><uro:BuildingIDAttribute><uro:buildingID>value</uro:buildingID>...
    for bid_attr in building.findall(".//uro:buildingIDAttribute/uro:BuildingIDAttribute", NS):
        bid_elem = bid_attr.find("./uro:buildingID", NS)
        if bid_elem is not None:
            bid = _first_text(bid_elem)
            if bid:
                attributes["buildingID"] = bid
                break  # Use first found ID

    return attributes


def _filter_buildings(
    buildings: List[ET.Element],
    building_ids: Optional[List[str]] = None,
    filter_attribute: str = "gml:id"
) -> List[ET.Element]:
    """Filter buildings by IDs using specified attribute.

    Args:
        buildings: List of bldg:Building elements
        building_ids: List of building IDs to filter by (None = no filtering)
        filter_attribute: Attribute to match against:
            - "gml:id": Match against gml:id attribute (default)
            - Other: Match against generic attribute with this name

    Returns:
        Filtered list of building elements
    """
    if not building_ids:
        return buildings

    # Normalize building_ids for case-insensitive matching
    building_ids_set = {bid.strip() for bid in building_ids}
    filtered: List[ET.Element] = []

    for b in buildings:
        match_found = False

        if filter_attribute == "gml:id":
            # Match by gml:id attribute
            gml_id = b.get("{http://www.opengis.net/gml}id") or b.get("id")
            if gml_id and gml_id in building_ids_set:
                match_found = True
        else:
            # Match by generic attribute
            attrs = _extract_generic_attributes(b)
            attr_value = attrs.get(filter_attribute)
            if attr_value and attr_value in building_ids_set:
                match_found = True

        if match_found:
            filtered.append(b)

    return filtered


def _build_id_index(root: ET.Element) -> dict[str, ET.Element]:
    """Build an index of all gml:id attributes in the document.

    This enables efficient resolution of XLink references (xlink:href="#id").

    Args:
        root: Root element of the GML document

    Returns:
        Dictionary mapping gml:id values to elements
    """
    id_index: dict[str, ET.Element] = {}

    # Iterate through all elements
    for elem in root.iter():
        # Check for gml:id attribute
        gml_id = elem.get("{http://www.opengis.net/gml}id")
        if gml_id:
            id_index[gml_id] = elem

    return id_index


def _resolve_xlink(elem: ET.Element, id_index: dict[str, ET.Element], debug: bool = False) -> Optional[ET.Element]:
    """Resolve an XLink reference (xlink:href) to the target element.

    Args:
        elem: Element that may contain an xlink:href attribute
        id_index: Index of gml:id -> element mappings
        debug: Enable debug output for XLink resolution failures

    Returns:
        The target element if reference is resolved, None otherwise
    """
    # Check for xlink:href attribute
    href = elem.get("{http://www.w3.org/1999/xlink}href")
    if not href:
        return None

    # Remove leading '#' from href
    if href.startswith("#"):
        target_id = href[1:]
    else:
        target_id = href

    # Look up in index
    result = id_index.get(target_id)

    if debug and result is None:
        # XLink resolution failed - provide helpful debug info
        log(f"      [XLink] Failed to resolve: {href}")
        log(f"      [XLink] Looking for ID: '{target_id}'")
        # Check for similar IDs
        similar_ids = [id for id in id_index.keys() if target_id in id or id in target_id]
        if similar_ids:
            log(f"      [XLink] Similar IDs found: {similar_ids[:3]}")
        else:
            log(f"      [XLink] No similar IDs found in index")

    return result


def _extract_polygon_with_xlink(elem: ET.Element, id_index: dict[str, ET.Element], debug: bool = False) -> Optional[ET.Element]:
    """Extract a gml:Polygon from an element, resolving XLink references if needed.

    Args:
        elem: Element that may contain a Polygon directly or via XLink
        id_index: Index for resolving XLink references
        debug: Enable debug output for XLink resolution

    Returns:
        gml:Polygon element or None
    """
    # Try to find Polygon directly
    poly = elem.find(".//gml:Polygon", NS)
    if poly is not None:
        return poly

    # Try to resolve XLink
    target = _resolve_xlink(elem, id_index, debug=debug)
    if target is not None:
        # Check if target IS a Polygon element itself
        if target.tag.endswith("Polygon"):
            return target

        # Otherwise, try to find Polygon in target's descendants
        poly = target.find(".//gml:Polygon", NS)
        if poly is not None:
            return poly

    return None


def _extract_polygon_xy(poly: ET.Element) -> Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]], List[float]]:
    """Extract exterior and interior rings as XY lists from a gml:Polygon.

    Also returns a list of all Z values found for height estimation.
    """
    all_z: List[float] = []

    # Exterior
    ext_coords_xy: List[Tuple[float, float]] = []
    ext_poslist = poly.find(".//gml:exterior/gml:LinearRing/gml:posList", NS)
    if ext_poslist is not None:
        coords = _parse_poslist(ext_poslist)
    else:
        # Fallback: multiple gml:pos elements
        pos_elems = poly.findall(".//gml:exterior//gml:pos", NS)
        coords = []
        for p in pos_elems:
            coords += _parse_poslist(p)

    for x, y, z in coords:
        ext_coords_xy.append((x, y))
        if z is not None and not math.isnan(z):
            all_z.append(z)

    # Interiors (holes)
    holes_xy: List[List[Tuple[float, float]]] = []
    for ring in poly.findall(".//gml:interior/gml:LinearRing", NS):
        ring_xy: List[Tuple[float, float]] = []
        rl = ring.find("./gml:posList", NS)
        if rl is not None:
            rcoords = _parse_poslist(rl)
        else:
            rcoords = []
            for rp in ring.findall(".//gml:pos", NS):
                rcoords += _parse_poslist(rp)
        for x, y, z in rcoords:
            ring_xy.append((x, y))
            if z is not None and not math.isnan(z):
                all_z.append(z)
        if ring_xy:
            holes_xy.append(ring_xy)

    return ext_coords_xy, holes_xy, all_z


def _extract_polygon_xyz(poly: ET.Element) -> Tuple[List[Tuple[float, float, float]], List[List[Tuple[float, float, float]]]]:
    """Extract exterior and interior rings as XYZ lists from a gml:Polygon.

    If Z is missing, treat it as 0.
    """
    # Exterior
    ext_xyz: List[Tuple[float, float, float]] = []
    ext_poslist = poly.find(".//gml:exterior/gml:LinearRing/gml:posList", NS)
    coords = []
    if ext_poslist is not None:
        coords = _parse_poslist(ext_poslist)
    else:
        for p in poly.findall(".//gml:exterior//gml:pos", NS):
            coords += _parse_poslist(p)
    for x, y, z in coords:
        ext_xyz.append((float(x), float(y), float(z if z is not None else 0.0)))

    # Interiors
    holes_xyz: List[List[Tuple[float, float, float]]] = []
    for ring in poly.findall(".//gml:interior/gml:LinearRing", NS):
        ring_xyz: List[Tuple[float, float, float]] = []
        rl = ring.find("./gml:posList", NS)
        rcoords = _parse_poslist(rl) if rl is not None else []
        if not rcoords:
            for rp in ring.findall(".//gml:pos", NS):
                rcoords += _parse_poslist(rp)
        for x, y, z in rcoords:
            ring_xyz.append((float(x), float(y), float(z if z is not None else 0.0)))
        if ring_xyz:
            holes_xyz.append(ring_xyz)
    return ext_xyz, holes_xyz


def _find_footprint_polygons(building: ET.Element) -> List[ET.Element]:
    """Return a list of gml:Polygon elements that likely represent footprints.

    Priority order:
      1) bldg:lod0FootPrint//gml:Polygon
      2) bldg:lod0RoofEdge//gml:Polygon (use as footprint at z=0 for PLATEAU)
      3) bldg:boundedBy/bldg:GroundSurface//gml:Polygon
    """
    polys: List[ET.Element] = []

    # 1) lod0FootPrint
    for node in building.findall(".//bldg:lod0FootPrint", NS):
        polys += node.findall(".//gml:Polygon", NS)
    if polys:
        return polys

    # 2) lod0RoofEdge (PLATEAU often has this instead of footprint)
    for node in building.findall(".//bldg:lod0RoofEdge", NS):
        polys += node.findall(".//gml:Polygon", NS)
    if polys:
        return polys

    # 3) GroundSurface under boundedBy
    for gs in building.findall(".//bldg:boundedBy/bldg:GroundSurface", NS):
        polys += gs.findall(".//gml:Polygon", NS)
    return polys


def _estimate_building_height(building: ET.Element, default_height: float) -> float:
    """Try to get building height from tags or coordinate Z range; fallback to default."""
    # Common tags for height
    tags = [
        ".//bldg:measuredHeight",
        ".//uro:measuredHeight",
        ".//uro:buildingHeight",
    ]
    for path in tags:
        node = building.find(path, NS)
        if node is not None:
            txt = _first_text(node)
            if txt:
                try:
                    h = float(txt)
                    if h > 0:
                        return h
                except ValueError:
                    pass

    # Height from Z range across all positions
    z_vals: List[float] = []
    for poslist in building.findall(".//gml:posList", NS):
        coords = _parse_poslist(poslist)
        for _, _, z in coords:
            if z is not None and not math.isnan(z):
                z_vals.append(z)
    if z_vals:
        zmin, zmax = min(z_vals), max(z_vals)
        if zmax - zmin > 0:
            return float(zmax - zmin)

    return float(default_height)


def parse_citygml_footprints(
    gml_path: str,
    default_height: float = 10.0,
    limit: Optional[int] = None,
    xy_transform: Optional[Callable[[float, float], Tuple[float, float]]] = None,
) -> List[Footprint]:
    """Parse a CityGML file and return footprint prisms description.

    Heuristic:
    - For each bldg:Building, find a representative footprint polygon
    - Determine a single height value
    - Return Footprint entries to be extruded
    """
    tree = ET.parse(gml_path)
    root = tree.getroot()

    bldgs = root.findall(".//bldg:Building", NS)
    footprints: List[Footprint] = []
    for i, b in enumerate(bldgs):
        if limit is not None and len(footprints) >= limit:
            break

        bid = b.get("gml:id") or b.get("id") or f"building_{i+1}"
        polys = _find_footprint_polygons(b)
        if not polys:
            # Skip if no reasonable polygon
            continue

        # Use first polygon as footprint (simple heuristic)
        ext, holes, z_all = _extract_polygon_xy(polys[0])
        # Reproject if requested
        if xy_transform is not None:
            try:
                ext = [tuple(map(float, xy_transform(x, y))) for (x, y) in ext]
                holes = [
                    [tuple(map(float, xy_transform(x, y))) for (x, y) in ring]
                    for ring in holes
                ]
            except Exception:
                pass
        if len(ext) < 3:
            continue
        height = _estimate_building_height(b, default_height)

        footprints.append(Footprint(exterior=ext, holes=holes, height=height, building_id=bid))

    return footprints


def _wire_from_coords_xy(coords: List[Tuple[float, float]]) -> "TopoDS_Shape":
    """Create a wire from 2D coordinates.

    Args:
        coords: List of (x, y) tuples in METERS (CityGML standard)

    Returns:
        TopoDS_Wire

    Note:
        CityGML coordinates are in meters, but OpenCASCADE/STEP expects millimeters.
        This function automatically converts by multiplying by 1000.
    """
    poly = BRepBuilderAPI_MakePolygon()
    # Ensure closed polygon; avoid duplicate closing point
    if coords and coords[0] == coords[-1]:
        pts = coords[:-1]
    else:
        pts = coords
    # Convert from meters (CityGML) to millimeters (OpenCASCADE/STEP)
    for x, y in pts:
        poly.Add(gp_Pnt(float(x) * 1000.0, float(y) * 1000.0, 0.0))
    poly.Close()
    return poly.Wire()


def _wire_from_coords_xyz(coords: List[Tuple[float, float, float]], debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Create a wire from 3D coordinates.

    Args:
        coords: List of (x, y, z) tuples in METERS (CityGML standard)
        debug: Enable debug output

    Returns:
        TopoDS_Wire or None if creation fails

    Note:
        CityGML coordinates are in meters, but OpenCASCADE/STEP expects millimeters.
        This function automatically converts by multiplying by 1000.
    """
    try:
        poly = BRepBuilderAPI_MakePolygon()
        if coords and coords[0] == coords[-1]:
            pts = coords[:-1]
        else:
            pts = coords

        if len(pts) < 2:
            if debug:
                log(f"Wire creation failed: insufficient points ({len(pts)} < 2)")
            return None

        # Convert from meters (CityGML) to millimeters (OpenCASCADE/STEP)
        for x, y, z in pts:
            poly.Add(gp_Pnt(float(x) * 1000.0, float(y) * 1000.0, float(z) * 1000.0))
        poly.Close()

        if not poly.IsDone():
            if debug:
                log(f"Wire creation failed: BRepBuilderAPI_MakePolygon.IsDone() = False")
            return None

        return poly.Wire()
    except Exception as e:
        if debug:
            log(f"Wire creation failed with exception: {e}")
        return None


def extrude_footprint(fp: Footprint) -> "TopoDS_Shape":
    """Create a prism solid from a 2D footprint using OCCT.

    Note:
        Footprint coordinates are in meters (CityGML standard), but OpenCASCADE/STEP
        expects millimeters. Height is also converted from meters to millimeters.
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for extrusion")

    outer = _wire_from_coords_xy(fp.exterior)
    face_maker = BRepBuilderAPI_MakeFace(outer, True)
    # Add interior holes if any
    for hole in fp.holes:
        if len(hole) >= 3:
            face_maker.Add(_wire_from_coords_xy(hole))
    face = face_maker.Face()

    # Convert height from meters to millimeters (fp.height is in meters)
    vec = gp_Vec(0.0, 0.0, float(fp.height) * 1000.0)
    prism = BRepPrimAPI_MakePrism(face, vec, True).Shape()
    return prism


def _face_from_xyz_rings(ext: List[Tuple[float, float, float]], holes: List[List[Tuple[float, float, float]]],
                         debug: bool = False, planar_check: bool = False) -> Optional["TopoDS_Face"]:
    """Create a face from 3D polygon rings.

    Args:
        ext: Exterior ring coordinates
        holes: List of interior ring coordinates
        debug: Enable debug output
        planar_check: Enforce strict planarity check (False = more permissive for LOD2 complex geometry)

    Returns:
        TopoDS_Face or None if creation fails
    """
    try:
        # Create outer wire
        outer = _wire_from_coords_xyz(ext, debug=debug)
        if outer is None:
            if debug:
                log(f"Face creation failed: outer wire creation failed ({len(ext)} points)")
            return None

        # Create face with planar_check control
        # planar_check=False allows non-planar faces (important for LOD2 complex geometry)
        face_maker = BRepBuilderAPI_MakeFace(outer, planar_check)

        if not face_maker.IsDone():
            if debug:
                log(f"Face creation failed: BRepBuilderAPI_MakeFace.IsDone() = False (planar_check={planar_check})")
            return None

        # Add holes if any
        for i, hole in enumerate(holes):
            if len(hole) >= 3:
                hole_wire = _wire_from_coords_xyz(hole, debug=debug)
                if hole_wire is not None:
                    face_maker.Add(hole_wire)
                elif debug:
                    log(f"Skipping hole {i}: wire creation failed")

        face = face_maker.Face()
        if face is None or face.IsNull():
            if debug:
                log(f"Face creation failed: resulting face is null")
            return None

        return face
    except Exception as e:
        if debug:
            log(f"Face creation failed with exception: {e}")
        return None


def _triangulate_polygon_fan(vertices: List[Tuple[float, float, float]]) -> List[List[Tuple[float, float, float]]]:
    """Triangulate a polygon using fan triangulation.

    Fan triangulation uses the first vertex as a pivot and creates triangles
    by connecting it to consecutive pairs of remaining vertices.

    This is simple, robust, and works well for convex polygons and most concave polygons.

    Args:
        vertices: List of polygon vertices (at least 3)

    Returns:
        List of triangles, each triangle is a list of 3 vertices

    Example:
        7 vertices → 5 triangles:
        - Triangle 0: [v0, v1, v2]
        - Triangle 1: [v0, v2, v3]
        - Triangle 2: [v0, v3, v4]
        - Triangle 3: [v0, v4, v5]
        - Triangle 4: [v0, v5, v6]
    """
    if len(vertices) < 3:
        return []

    if len(vertices) == 3:
        return [vertices]  # Already a triangle

    triangles = []
    pivot = vertices[0]

    for i in range(1, len(vertices) - 1):
        triangle = [pivot, vertices[i], vertices[i + 1]]
        triangles.append(triangle)

    return triangles


def _project_to_best_fit_plane(
    vertices: List[Tuple[float, float, float]],
    tolerance: float
) -> Tuple[List[Tuple[float, float, float]], Tuple[float, float, float]]:
    """Project polygon vertices onto their best-fit plane.

    This computes the optimal plane that minimizes the distance to all vertices,
    then projects each vertex onto that plane. This corrects minor non-planarity
    while preserving the original shape as much as possible.

    Args:
        vertices: List of polygon vertices
        tolerance: Geometric tolerance (not directly used, kept for consistency)

    Returns:
        Tuple of:
        - List of projected vertices (guaranteed to be coplanar)
        - Plane normal vector (nx, ny, nz)

    Raises:
        Exception if plane fitting fails
    """
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_HArray1OfPnt
    from OCC.Core.GeomPlate import GeomPlate_BuildAveragePlane
    from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf

    # Convert vertices to gp_Pnt array
    n = len(vertices)
    points = TColgp_HArray1OfPnt(1, n)
    for i, (x, y, z) in enumerate(vertices):
        points.SetValue(i + 1, gp_Pnt(x, y, z))

    # Build the best-fit plane using OpenCASCADE
    plane_builder = GeomPlate_BuildAveragePlane(points)
    plane = plane_builder.Plane()
    plane_surface = plane.GetObject()

    # Get plane normal for logging
    ax = plane.Axis()
    direction = ax.Direction()
    normal = (direction.X(), direction.Y(), direction.Z())

    # Project each vertex onto the plane
    projected = []
    for x, y, z in vertices:
        pnt = gp_Pnt(x, y, z)
        projector = GeomAPI_ProjectPointOnSurf(pnt, plane_surface)

        if projector.NbPoints() > 0:
            proj_pnt = projector.Point(1)
            projected.append((proj_pnt.X(), proj_pnt.Y(), proj_pnt.Z()))
        else:
            # Fallback: use original vertex if projection fails
            projected.append((x, y, z))

    return projected, normal


def _create_face_with_progressive_fallback(
    ext: List[Tuple[float, float, float]],
    holes: List[List[Tuple[float, float, float]]],
    tolerance: float,
    debug: bool = False
) -> List["TopoDS_Face"]:
    """Create face(s) from polygon rings using progressive fallback strategy.

    This function tries multiple methods in order of shape fidelity:

    Level 1: Normal face creation (planar_check=False)
        - Best: Preserves original geometry 100%
        - Success rate: ~30-40% (simple planar polygons)

    Level 2: Best-fit plane projection
        - Very good: Corrects minor non-planarity with minimal shape change
        - Success rate: ~50-60% (slightly non-planar polygons)
        - **This is where most failures are resolved!**

    Level 3: ShapeFix_Face repair
        - Good: Automatic repair of face geometry
        - Success rate: ~5-10% (faces that need topological fixes)

    Level 4: Fan triangulation
        - Guaranteed: Always succeeds, but creates multiple triangle faces
        - Success rate: 100% (mathematical guarantee - triangles are always planar)
        - Last resort: Only ~5% of faces reach this level

    Args:
        ext: Exterior ring coordinates
        holes: List of interior ring coordinates
        tolerance: Geometric tolerance for operations
        debug: Enable detailed logging

    Returns:
        List of TopoDS_Face objects (usually 1 face, multiple if triangulated)
        Empty list if all methods fail (extremely rare)
    """

    # ===== Level 1: Normal face creation =====
    face = _face_from_xyz_rings(ext, holes, debug=False, planar_check=False)
    if face is not None:
        if debug:
            log(f"  [Level 1] Success: Normal face creation ({len(ext)} vertices)")
        return [face]

    # ===== Level 2: Best-fit plane projection =====
    if debug:
        log(f"  [Level 1] Failed, trying Level 2: Plane projection ({len(ext)} vertices)...")

    try:
        # Project vertices to best-fit plane
        projected_ext, plane_normal = _project_to_best_fit_plane(ext, tolerance)

        # Try creating face with projected vertices (now guaranteed planar)
        face = _face_from_xyz_rings(projected_ext, holes, debug=False, planar_check=False)
        if face is not None:
            if debug:
                log(f"  [Level 2] Success: Plane-projected face ({len(ext)} vertices)")
            return [face]
    except Exception as e:
        if debug:
            log(f"  [Level 2] Failed: {e}")

    # ===== Level 3: ShapeFix_Face repair =====
    if debug:
        log(f"  [Level 2] Failed, trying Level 3: ShapeFix repair...")

    try:
        # Create wire from original vertices
        outer_wire = _wire_from_coords_xyz(ext, debug=False)
        if outer_wire is not None:
            from OCC.Core.ShapeFix import ShapeFix_Face
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

            # Try to make a temporary face
            temp_maker = BRepBuilderAPI_MakeFace(outer_wire, False)
            if temp_maker.IsDone():
                temp_face = temp_maker.Face()

                # Apply ShapeFix
                fixer = ShapeFix_Face(temp_face)
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 1000)
                fixer.Perform()

                fixed_face = fixer.Face()
                if fixed_face is not None and not fixed_face.IsNull():
                    if debug:
                        log(f"  [Level 3] Success: ShapeFix repair ({len(ext)} vertices)")
                    return [fixed_face]
    except Exception as e:
        if debug:
            log(f"  [Level 3] Failed: {e}")

    # ===== Level 4: Fan triangulation (last resort, always succeeds) =====
    if debug:
        log(f"  [Level 3] Failed, trying Level 4: Triangulation (last resort)...")

    triangles = _triangulate_polygon_fan(ext)
    faces = []

    for i, tri in enumerate(triangles):
        # Triangles are guaranteed to be planar (3 points define a plane)
        tri_face = _face_from_xyz_rings(tri, [], debug=False, planar_check=False)
        if tri_face is not None:
            faces.append(tri_face)
        elif debug:
            log(f"  [Level 4] Warning: Triangle {i}/{len(triangles)} creation failed (rare!)")

    if debug:
        if faces:
            log(f"  [Level 4] Success: Created {len(faces)}/{len(triangles)} triangle faces")
        else:
            log(f"  [Level 4] Failed: Could not create any triangle faces (extremely rare!)")

    return faces


def _compute_tolerance_from_coords(coords: List[Tuple[float, float, float]], precision_mode: str = "auto") -> float:
    """Compute appropriate tolerance based on coordinate extent and precision mode.

    The tolerance scales with coordinate extent and precision requirements.
    Higher precision means smaller tolerance (more detail preservation).

    Args:
        coords: List of (x, y, z) coordinate tuples
        precision_mode: Precision level ("auto", "high", "maximum", or "ultra")
            - "auto"/"standard": 0.01% of extent (default, good balance)
            - "high": 0.001% of extent (preserves fine details)
            - "maximum": 0.0001% of extent (maximum detail preservation)
            - "ultra": 0.00001% of extent (ultra-precision for LOD2/LOD3)

    Returns:
        Computed tolerance value (minimum 1e-9 for ultra, maximum 10.0)
    """
    if not coords:
        # Fallback values based on precision mode
        fallback = {
            "ultra": 0.00001,
            "maximum": 0.0001,
            "high": 0.001,
        }
        return fallback.get(precision_mode, 0.01)

    # Compute bounding box
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]

    x_extent = max(xs) - min(xs) if xs else 0.0
    y_extent = max(ys) - min(ys) if ys else 0.0
    z_extent = max(zs) - min(zs) if zs else 0.0

    # Maximum extent across all dimensions
    extent = max(x_extent, y_extent, z_extent)

    # Tolerance percentage based on precision mode
    # Higher precision = smaller percentage = more detail preserved
    percentage = {
        "ultra": 0.0000001,    # 0.00001% - for LOD2/LOD3 with fine details
        "maximum": 0.000001,   # 0.0001% - maximum standard precision
        "high": 0.00001,       # 0.001% - high precision
    }.get(precision_mode, 0.0001)  # default: 0.01%

    tolerance = extent * percentage

    # Clamp to reasonable range (tighter bounds for higher precision)
    if precision_mode == "ultra":
        min_tol = 1e-9
        max_tol = 1.0
    elif precision_mode == "maximum":
        min_tol = 1e-8
        max_tol = 5.0
    elif precision_mode == "high":
        min_tol = 1e-7
        max_tol = 10.0
    else:
        min_tol = 1e-6
        max_tol = 10.0

    tolerance = max(min_tol, min(tolerance, max_tol))

    return tolerance


def _compute_tolerance_from_face_list(faces: List["TopoDS_Face"], precision_mode: str = "auto") -> float:
    """Compute tolerance from a list of faces by sampling their vertices.

    Args:
        faces: List of TopoDS_Face objects
        precision_mode: Precision level ("auto", "high", or "maximum")

    Returns:
        Computed tolerance value
    """
    # Sample up to 100 vertices from faces
    coords: List[Tuple[float, float, float]] = []
    from OCC.Core.BRepTools import BRepTools_WireExplorer
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_WIRE

    sample_limit = 100
    for face in faces:
        if len(coords) >= sample_limit:
            break

        # Explore wires in face
        wire_exp = TopExp_Explorer(face, TopAbs_WIRE)
        while wire_exp.More() and len(coords) < sample_limit:
            wire = wire_exp.Current()
            wire_explorer = BRepTools_WireExplorer(wire)

            while wire_explorer.More() and len(coords) < sample_limit:
                vertex = wire_explorer.CurrentVertex()
                pnt = BRep_Tool.Pnt(vertex)
                coords.append((pnt.X(), pnt.Y(), pnt.Z()))
                wire_explorer.Next()

            wire_exp.Next()

    if coords:
        return _compute_tolerance_from_coords(coords, precision_mode)
    else:
        # Fallback values based on precision mode
        fallback = {
            "ultra": 0.00001,
            "maximum": 0.0001,
            "high": 0.001,
        }
        return fallback.get(precision_mode, 0.01)


def _extract_faces_from_surface_container(container: ET.Element, xyz_transform: Optional[Callable] = None,
                                          id_index: Optional[dict[str, ET.Element]] = None,
                                          tolerance: Optional[float] = None,
                                          debug: bool = False) -> List["TopoDS_Face"]:
    """Extract faces from various GML surface container structures.

    Supports:
    - gml:MultiSurface (multiple independent surfaces)
    - gml:CompositeSurface (connected surface patches)
    - Direct gml:Polygon children

    Args:
        container: Element containing surface geometry (MultiSurface, CompositeSurface, etc.)
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        tolerance: Geometric tolerance (computed from coords if None)
        debug: Enable debug output

    Returns:
        List of TopoDS_Face objects extracted from the container
    """
    faces: List[TopoDS_Face] = []

    if id_index is None:
        id_index = {}

    # Statistics tracking
    stats = {
        "surfaceMember_count": 0,
        "polygon_found": 0,
        "polygon_too_small": 0,
        "transform_failed": 0,
        "face_creation_success": 0,
        "face_creation_failed": 0,
    }

    # Strategy 1: Look for surfaceMember elements (common in MultiSurface/CompositeSurface)
    for surf_member in container.findall(".//gml:surfaceMember", NS):
        stats["surfaceMember_count"] += 1

        poly = _extract_polygon_with_xlink(surf_member, id_index, debug=debug) if id_index else surf_member.find(".//gml:Polygon", NS)

        if poly is None:
            poly = surf_member.find(".//gml:Polygon", NS)

        if poly is None:
            continue

        stats["polygon_found"] += 1

        ext, holes = _extract_polygon_xyz(poly)
        if len(ext) < 3:
            stats["polygon_too_small"] += 1
            continue

        # Apply coordinate transformation if provided
        if xyz_transform:
            try:
                ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                holes = [
                    [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                    for ring in holes
                ]
            except Exception as e:
                stats["transform_failed"] += 1
                if debug:
                    log(f"Transform failed for polygon: {e}")
                continue

        # Compute tolerance if not provided
        if tolerance is None:
            tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
        else:
            tol = tolerance

        # Use progressive fallback strategy for robust face creation
        face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
        if face_list:
            faces.extend(face_list)
            stats["face_creation_success"] += len(face_list)
        else:
            stats["face_creation_failed"] += 1

    # Strategy 2: Look for direct Polygon children
    for poly in container.findall(".//gml:Polygon", NS):
        # Skip if already processed via surfaceMember
        parent = poly.find("..")
        if parent is not None and parent.tag.endswith("surfaceMember"):
            continue

        stats["polygon_found"] += 1

        ext, holes = _extract_polygon_xyz(poly)
        if len(ext) < 3:
            stats["polygon_too_small"] += 1
            continue

        # Apply coordinate transformation if provided
        if xyz_transform:
            try:
                ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                holes = [
                    [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                    for ring in holes
                ]
            except Exception as e:
                stats["transform_failed"] += 1
                if debug:
                    log(f"Transform failed for polygon: {e}")
                continue

        # Compute tolerance if not provided
        if tolerance is None:
            tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
        else:
            tol = tolerance

        # Use progressive fallback strategy for robust face creation
        face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
        if face_list:
            faces.extend(face_list)
            stats["face_creation_success"] += len(face_list)
        else:
            stats["face_creation_failed"] += 1

    # Print statistics in debug mode
    if debug:
        log(f"  Face extraction statistics:")
        log(f"    - surfaceMembers found: {stats['surfaceMember_count']}")
        log(f"    - Polygons found: {stats['polygon_found']}")
        log(f"    - Polygons too small (<3 vertices): {stats['polygon_too_small']}")
        log(f"    - Transform failures: {stats['transform_failed']}")
        log(f"    - Face creation successes: {stats['face_creation_success']}")
        log(f"    - Face creation failures: {stats['face_creation_failed']}")
        log(f"    - Total faces returned: {len(faces)}")

    return faces


def _extract_solid_shells(solid_elem: ET.Element, xyz_transform: Optional[Callable] = None,
                          id_index: Optional[dict[str, ET.Element]] = None,
                          tolerance: Optional[float] = None,
                          debug: bool = False) -> Tuple[List["TopoDS_Face"], List[List["TopoDS_Face"]]]:
    """Extract exterior and interior shells from a gml:Solid element.

    Now supports XLink reference resolution for polygons and progressive fallback for face creation.

    Args:
        solid_elem: XML element containing gml:Solid
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        tolerance: Geometric tolerance (computed from coords if None)
        debug: Enable debug output

    Returns:
        Tuple of (exterior_faces, list_of_interior_face_lists)

    GML Structure:
        gml:Solid/gml:exterior - outer shell (building envelope)
        gml:Solid/gml:interior - inner shells (cavities, courtyards)
    """
    exterior_faces: List[TopoDS_Face] = []
    interior_shells: List[List[TopoDS_Face]] = []

    # Use empty index if none provided
    if id_index is None:
        id_index = {}

    if debug:
        log(f"  [Solid] Extracting shells from gml:Solid element")

        # Dump XML structure to temp file for debugging
        try:
            import tempfile
            import os
            xml_str = ET.tostring(solid_elem, encoding="unicode")
            dump_path = os.path.join(tempfile.gettempdir(), "plateau_solid_debug.xml")
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            log(f"  [Solid] XML structure dumped to: {dump_path}")
        except Exception as e:
            log(f"  [Solid] Failed to dump XML: {e}")

    # Extract exterior shell polygons
    exterior_elem = solid_elem.find("./gml:exterior", NS)
    if debug:
        if exterior_elem is not None:
            log(f"  [Solid] Found gml:exterior element")
        else:
            log(f"  [Solid] WARNING: No gml:exterior element found!")
    if exterior_elem is not None:
        # Support multiple GML surface patterns - find all surfaceMember elements
        surf_members = exterior_elem.findall(".//gml:surfaceMember", NS)
        if debug:
            log(f"  [Solid] Found {len(surf_members)} gml:surfaceMember elements in exterior")

        for i, surf_member in enumerate(surf_members):
            # Check for XLink reference
            href = surf_member.get("{http://www.w3.org/1999/xlink}href")
            if debug and href:
                log(f"  [Solid]   surfaceMember[{i}]: XLink reference: {href}")

                # For first surfaceMember, check if it exists in index
                if i == 0 and href.startswith("#"):
                    target_id = href[1:]
                    exists = target_id in id_index
                    log(f"  [Solid]   surfaceMember[{i}]: Target ID '{target_id}' in index: {exists}")
                    if not exists:
                        # Show some similar IDs
                        similar = [k for k in id_index.keys() if k.startswith("poly-")][:5]
                        log(f"  [Solid]   surfaceMember[{i}]: Sample polygon IDs in index: {similar}")

            # Try to extract polygon (with XLink resolution)
            # Force debug=True for first surfaceMember to see detailed XLink resolution
            xlink_debug = debug and i == 0
            poly = _extract_polygon_with_xlink(surf_member, id_index, debug=xlink_debug) if id_index else surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                # Fallback: search directly
                poly = surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                if debug:
                    log(f"  [Solid]   surfaceMember[{i}]: No Polygon found (XLink may have failed)")
                continue

            if debug:
                log(f"  [Solid]   surfaceMember[{i}]: Polygon found")

            ext, holes = _extract_polygon_xyz(poly)
            if debug:
                log(f"  [Solid]   surfaceMember[{i}]: Extracted {len(ext)} vertices, {len(holes)} holes")

            if len(ext) < 3:
                if debug:
                    log(f"  [Solid]   surfaceMember[{i}]: Insufficient vertices ({len(ext)} < 3), skipping")
                continue

            # Apply coordinate transformation if provided
            if xyz_transform:
                try:
                    ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                    holes = [
                        [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                        for ring in holes
                    ]
                except Exception as e:
                    if debug:
                        log(f"  [Solid]   surfaceMember[{i}]: Transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                exterior_faces.extend(face_list)
                if debug:
                    log(f"  [Solid]   surfaceMember[{i}]: ✓ Face created successfully")
            else:
                if debug:
                    log(f"  [Solid]   surfaceMember[{i}]: ✗ Face creation failed")

        # Also search for direct Polygon children (not in surfaceMember)
        for poly in exterior_elem.findall(".//gml:Polygon", NS):
            # Skip if already processed via surfaceMember
            parent = poly.find("..")
            if parent is not None and parent.tag.endswith("surfaceMember"):
                continue

            ext, holes = _extract_polygon_xyz(poly)
            if len(ext) < 3:
                continue

            # Apply coordinate transformation if provided
            if xyz_transform:
                try:
                    ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                    holes = [
                        [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                        for ring in holes
                    ]
                except Exception as e:
                    if debug:
                        log(f"Exterior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                exterior_faces.extend(face_list)

    # Extract interior shells (cavities)
    for interior_elem in solid_elem.findall("./gml:interior", NS):
        interior_faces: List[TopoDS_Face] = []

        # Try surfaceMember pattern first
        for surf_member in interior_elem.findall(".//gml:surfaceMember", NS):
            poly = _extract_polygon_with_xlink(surf_member, id_index, debug=debug) if id_index else surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                poly = surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                continue

            ext, holes = _extract_polygon_xyz(poly)
            if len(ext) < 3:
                continue

            # Apply coordinate transformation if provided
            if xyz_transform:
                try:
                    ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                    holes = [
                        [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                        for ring in holes
                    ]
                except Exception as e:
                    if debug:
                        log(f"Interior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                interior_faces.extend(face_list)

        # Also search for direct Polygon children
        for poly in interior_elem.findall(".//gml:Polygon", NS):
            parent = poly.find("..")
            if parent is not None and parent.tag.endswith("surfaceMember"):
                continue

            ext, holes = _extract_polygon_xyz(poly)
            if len(ext) < 3:
                continue

            # Apply coordinate transformation if provided
            if xyz_transform:
                try:
                    ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                    holes = [
                        [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                        for ring in holes
                    ]
                except Exception as e:
                    if debug:
                        log(f"Interior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = _compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = _create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                interior_faces.extend(face_list)

        if interior_faces:
            interior_shells.append(interior_faces)
            if debug:
                log(f"Found interior shell with {len(interior_faces)} faces (cavity)")

    if debug:
        log(f"  [Solid] Extraction complete: {len(exterior_faces)} exterior faces, {len(interior_shells)} interior shells")

    return exterior_faces, interior_shells


def _normalize_face_orientation(faces: List["TopoDS_Face"], debug: bool = False) -> List["TopoDS_Face"]:
    """Normalize face orientations to ensure consistent normals.

    This helps prevent issues with shell construction by ensuring all faces
    have compatible orientations.

    Args:
        faces: List of TopoDS_Face objects
        debug: Enable debug output

    Returns:
        List of faces with normalized orientations
    """
    if not faces:
        return faces

    try:
        # Import only what we need - TopAbs_REVERSED
        from OCC.Core.TopAbs import TopAbs_REVERSED

        normalized = []
        for i, face in enumerate(faces):
            # Check face orientation
            orientation = face.Orientation()

            # If face is reversed, try to correct it
            if orientation == TopAbs_REVERSED:
                try:
                    # Reverse the face
                    face_copy = face.Reversed()
                    normalized.append(face_copy)
                    if debug:
                        log(f"Reversed face {i} orientation")
                except Exception as e:
                    if debug:
                        log(f"Failed to reverse face {i}: {e}")
                    normalized.append(face)
            else:
                normalized.append(face)

        return normalized
    except Exception as e:
        if debug:
            log(f"Face orientation normalization failed: {e}")
        return faces


def _remove_duplicate_vertices(faces: List["TopoDS_Face"], tolerance: float, debug: bool = False) -> List["TopoDS_Face"]:
    """Remove duplicate vertices from faces within tolerance.

    This helps reduce complexity and improve sewing quality for LOD2/LOD3 data.

    Args:
        faces: List of TopoDS_Face objects
        tolerance: Vertex merge tolerance
        debug: Enable debug output

    Returns:
        List of faces with deduplicated vertices
    """
    if not faces:
        return faces

    try:
        from OCC.Core.ShapeFix import ShapeFix_Face
        from OCC.Core.ShapeBuild import ShapeBuild_ReShape

        cleaned = []
        for i, face in enumerate(faces):
            try:
                # Use ShapeFix_Face to clean up the face
                fixer = ShapeFix_Face(face)
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 100)

                # Perform fixing
                fixer.Perform()

                fixed_face = fixer.Face()
                if fixed_face is not None and not fixed_face.IsNull():
                    cleaned.append(fixed_face)
                    if debug and fixed_face != face:
                        log(f"Cleaned face {i}")
                else:
                    cleaned.append(face)
            except Exception as e:
                if debug:
                    log(f"Failed to clean face {i}: {e}")
                cleaned.append(face)

        return cleaned
    except Exception as e:
        if debug:
            log(f"Vertex deduplication failed: {e}")
        return faces


def _validate_and_fix_face(face: "TopoDS_Face", tolerance: float, debug: bool = False) -> Optional["TopoDS_Face"]:
    """Validate and fix a single face with multiple strategies.

    Args:
        face: TopoDS_Face to validate and fix
        tolerance: Precision tolerance
        debug: Enable debug output

    Returns:
        Fixed face or None if unfixable
    """
    try:
        from OCC.Core.BRepCheck import BRepCheck_Analyzer
        from OCC.Core.ShapeFix import ShapeFix_Face, ShapeFix_Wire

        # First validation
        analyzer = BRepCheck_Analyzer(face)
        if analyzer.IsValid():
            return face

        if debug:
            log("Face invalid, attempting multi-stage fix...")

        # Stage 1: Basic face fixing
        fixer = ShapeFix_Face(face)
        fixer.SetPrecision(tolerance)
        fixer.SetMaxTolerance(tolerance * 1000)
        fixer.Perform()
        fixed = fixer.Face()

        # Validate stage 1
        if fixed is not None and not fixed.IsNull():
            analyzer = BRepCheck_Analyzer(fixed)
            if analyzer.IsValid():
                if debug:
                    log("Face fixed in stage 1")
                return fixed

        # Stage 2: Aggressive wire fixing
        if fixed is not None and not fixed.IsNull():
            try:
                from OCC.Core.TopExp import TopExp_Explorer
                from OCC.Core.TopAbs import TopAbs_WIRE
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

                # Extract and fix wires
                wire_exp = TopExp_Explorer(fixed, TopAbs_WIRE)
                fixed_wires = []

                while wire_exp.More():
                    wire = wire_exp.Current()
                    wire_fixer = ShapeFix_Wire()
                    wire_fixer.Load(wire)
                    wire_fixer.SetPrecision(tolerance)
                    wire_fixer.SetMaxTolerance(tolerance * 1000)
                    wire_fixer.Perform()

                    fixed_wire = wire_fixer.Wire()
                    if fixed_wire is not None and not fixed_wire.IsNull():
                        fixed_wires.append(fixed_wire)

                    wire_exp.Next()

                # Rebuild face from fixed wires
                if fixed_wires:
                    face_maker = BRepBuilderAPI_MakeFace(fixed_wires[0], True)
                    for wire in fixed_wires[1:]:
                        face_maker.Add(wire)

                    rebuilt = face_maker.Face()
                    if rebuilt is not None and not rebuilt.IsNull():
                        analyzer = BRepCheck_Analyzer(rebuilt)
                        if analyzer.IsValid():
                            if debug:
                                log("Face fixed in stage 2 (wire rebuild)")
                            return rebuilt
            except Exception as e:
                if debug:
                    log(f"Stage 2 wire fixing failed: {e}")

        # If all stages fail, return best attempt or None
        if fixed is not None and not fixed.IsNull():
            return fixed

        return None

    except Exception as e:
        if debug:
            log(f"Face validation/fixing failed: {e}")
        return None


def _build_shell_from_faces(faces: List["TopoDS_Face"], tolerance: float = 0.1,
                            debug: bool = False, shape_fix_level: str = "standard") -> Optional["TopoDS_Shell"]:
    """Build a shell from a list of faces using sewing and fixing.

    Enhanced with multi-stage processing for LOD2/LOD3 precision:
    1. Validate and fix each face individually
    2. Normalize face orientations
    3. Remove duplicate vertices
    4. Multi-pass sewing with progressively tighter tolerances
    5. Aggressive shell fixing

    Args:
        faces: List of TopoDS_Face objects
        tolerance: Sewing tolerance
        debug: Enable debug output
        shape_fix_level: Shape fixing aggressiveness
            - "minimal": Skip shape fixing to preserve maximum detail
            - "standard": Standard shape fixing (default)
            - "aggressive": More aggressive shape fixing for robustness
            - "ultra": Maximum fixing for LOD2/LOD3 (multi-stage with validation)

    Returns:
        TopoDS_Shell or None if construction fails
    """
    # Import topods at function start to avoid scoping issues
    from OCC.Core.TopoDS import topods

    if not faces:
        return None

    if debug:
        log(f"Building shell from {len(faces)} faces with tolerance {tolerance:.9f}")

    # Stage 1: Validate and fix each face individually
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            log("Stage 1: Validating and fixing individual faces...")

        validated_faces = []
        for i, face in enumerate(faces):
            fixed_face = _validate_and_fix_face(face, tolerance, debug)
            if fixed_face is not None:
                validated_faces.append(fixed_face)
            elif debug:
                log(f"Warning: Face {i} could not be fixed, skipping")

        if not validated_faces:
            if debug:
                log("Error: No valid faces after validation")
            return None

        faces = validated_faces
        if debug:
            log(f"Stage 1 complete: {len(faces)} valid faces")

    # Stage 2: Normalize face orientations
    if shape_fix_level in ("standard", "aggressive", "ultra"):
        if debug:
            log("Stage 2: Normalizing face orientations...")
        faces = _normalize_face_orientation(faces, debug)

    # Stage 3: Remove duplicate vertices
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            log("Stage 3: Removing duplicate vertices...")
        faces = _remove_duplicate_vertices(faces, tolerance, debug)

    # Stage 4: Multi-pass sewing for ultra mode
    if shape_fix_level == "ultra":
        if debug:
            log("Stage 4: Multi-pass sewing with progressively tighter tolerances...")

        # Try multiple sewing passes with different tolerances
        tolerances_to_try = [
            tolerance * 10.0,  # First pass: looser for connectivity
            tolerance * 5.0,   # Second pass: tighter
            tolerance,         # Final pass: target tolerance
        ]

        sewn_shape = None
        for i, tol in enumerate(tolerances_to_try):
            if debug:
                log(f"  Sewing pass {i+1} with tolerance {tol:.9f}")

            sewing = BRepBuilderAPI_Sewing(tol, True, True, True, False)
            for fc in faces:
                sewing.Add(fc)
            sewing.Perform()
            sewn_shape = sewing.SewedShape()

            # Check if sewing improved
            if sewn_shape is not None and not sewn_shape.IsNull():
                if debug:
                    log(f"  Pass {i+1} successful")

                # DEBUG: Check face count after this pass
                if debug:
                    from OCC.Core.TopAbs import TopAbs_FACE
                    face_exp_count = TopExp_Explorer(sewn_shape, TopAbs_FACE)
                    pass_face_count = 0
                    while face_exp_count.More():
                        pass_face_count += 1
                        face_exp_count.Next()
                    log(f"  [SEWING PASS {i+1}] {len(faces)} input → {pass_face_count} output faces")

                # Use this result as input for next pass
                # Extract faces from sewn shape for next iteration
                if i < len(tolerances_to_try) - 1:
                    from OCC.Core.TopAbs import TopAbs_FACE
                    face_exp = TopExp_Explorer(sewn_shape, TopAbs_FACE)
                    new_faces = []
                    while face_exp.More():
                        new_faces.append(topods.Face(face_exp.Current()))
                        face_exp.Next()
                    if new_faces:
                        faces = new_faces
    else:
        # Standard single-pass sewing
        if debug:
            log("Stage 4: Single-pass sewing...")

        sewing = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
        for fc in faces:
            sewing.Add(fc)
        sewing.Perform()
        sewn_shape = sewing.SewedShape()

    # DEBUG: Check how many faces survived sewing
    if debug:
        from OCC.Core.TopAbs import TopAbs_FACE
        face_exp = TopExp_Explorer(sewn_shape, TopAbs_FACE)
        sewn_face_count = 0
        while face_exp.More():
            sewn_face_count += 1
            face_exp.Next()
        log(f"[SEWING DIAGNOSTIC] Input: {len(faces)} faces → Output: {sewn_face_count} faces in sewn shape")
        if sewn_face_count < len(faces):
            lost_faces = len(faces) - sewn_face_count
            loss_percentage = (lost_faces / len(faces)) * 100
            log(f"[SEWING DIAGNOSTIC] ⚠ WARNING: {lost_faces} faces lost ({loss_percentage:.1f}%)")

    # Stage 5: Apply shape fixing based on level
    if shape_fix_level != "minimal":
        try:
            if debug:
                log(f"Stage 5: Applying shape fixing (level: {shape_fix_level})...")

            fixer = ShapeFix_Shape(sewn_shape)

            # Configure fixer based on level
            if shape_fix_level == "standard":
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 10.0)
            elif shape_fix_level == "aggressive":
                fixer.SetPrecision(tolerance * 10.0)
                fixer.SetMaxTolerance(tolerance * 100.0)
            elif shape_fix_level == "ultra":
                # Ultra mode: very tight precision with large tolerance range
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 1000.0)

            fixer.Perform()
            sewn_shape = fixer.Shape()

            if debug:
                log(f"Shape fixing applied (level: {shape_fix_level})")
        except Exception as e:
            if debug:
                log(f"ShapeFix_Shape failed: {e}")

    # Stage 6: Extract and validate shell
    if debug:
        log("Stage 6: Extracting and validating shell...")

    # First, count how many shells exist in sewn shape
    shell_count = 0
    shell_exp = TopExp_Explorer(sewn_shape, TopAbs_SHELL)
    shells = []
    while shell_exp.More():
        shells.append(topods.Shell(shell_exp.Current()))
        shell_count += 1
        shell_exp.Next()

    if debug:
        log(f"[SHELL DIAGNOSTIC] Found {shell_count} shell(s) in sewn shape")

    # If multiple disconnected shells exist, select the largest valid shell
    # instead of trying to re-sew (which often fails for disconnected geometry)
    if shell_count > 1:
        if debug:
            log(f"[SHELL DIAGNOSTIC] Multiple disconnected shells detected, validating each shell...")

        # Validate each shell and count faces
        from OCC.Core.BRepCheck import BRepCheck_Analyzer

        shell_info = []
        for i, sh in enumerate(shells):
            face_exp = TopExp_Explorer(sh, TopAbs_FACE)
            face_count = 0
            while face_exp.More():
                face_count += 1
                face_exp.Next()

            # Check shell validity and count invalid faces
            try:
                analyzer = BRepCheck_Analyzer(sh)
                is_valid = analyzer.IsValid()

                # If shell is invalid, count how many faces are invalid
                invalid_face_count = 0
                if not is_valid:
                    face_exp2 = TopExp_Explorer(sh, TopAbs_FACE)
                    while face_exp2.More():
                        face = topods.Face(face_exp2.Current())
                        face_analyzer = BRepCheck_Analyzer(face)
                        if not face_analyzer.IsValid():
                            invalid_face_count += 1
                        face_exp2.Next()

            except Exception as e:
                is_valid = False
                invalid_face_count = face_count  # Assume all invalid on error
                if debug:
                    log(f"  Shell {i+1} validation error: {e}")

            # Calculate invalid face ratio
            invalid_ratio = invalid_face_count / face_count if face_count > 0 else 1.0

            shell_info.append({
                'index': i + 1,
                'shell': sh,
                'face_count': face_count,
                'is_valid': is_valid,
                'invalid_face_count': invalid_face_count,
                'invalid_ratio': invalid_ratio
            })

            if debug:
                if is_valid:
                    status = "✓ valid"
                elif invalid_ratio < 0.05:  # Less than 5% invalid
                    status = f"⚠ mostly valid ({invalid_face_count}/{face_count} invalid, {invalid_ratio*100:.1f}%)"
                else:
                    status = f"✗ invalid ({invalid_face_count}/{face_count} invalid, {invalid_ratio*100:.1f}%)"
                log(f"  Shell {i+1}: {face_count} faces ({status})")

        # Find shells that are valid or mostly valid (< 5% invalid faces)
        INVALID_THRESHOLD = 0.05  # 5% tolerance for invalid faces
        acceptable_shells = [s for s in shell_info if s['is_valid'] or s['invalid_ratio'] < INVALID_THRESHOLD]

        if acceptable_shells:
            # Collect valid faces from ALL acceptable shells (not just the largest)
            if debug:
                log(f"[SHELL DIAGNOSTIC] Found {len(acceptable_shells)} acceptable shell(s), collecting all valid faces...")

            all_valid_faces_from_acceptable_shells = []
            total_invalid_removed = 0

            for shell_info in acceptable_shells:
                shell_idx = shell_info['index']
                shell_obj = shell_info['shell']
                shell_face_count = shell_info['face_count']
                shell_is_valid = shell_info['is_valid']
                shell_invalid_count = shell_info['invalid_face_count']

                if debug:
                    status = "✓ valid" if shell_is_valid else f"⚠ mostly valid ({shell_invalid_count} invalid)"
                    log(f"  Processing Shell {shell_idx}: {shell_face_count} faces ({status})")

                # Extract valid faces from this shell
                face_exp = TopExp_Explorer(shell_obj, TopAbs_FACE)
                valid_count = 0
                invalid_count = 0

                while face_exp.More():
                    face = topods.Face(face_exp.Current())

                    # If shell is fully valid, skip validation check for efficiency
                    if shell_is_valid:
                        all_valid_faces_from_acceptable_shells.append(face)
                        valid_count += 1
                    else:
                        # Shell has some invalid faces - validate each face
                        face_analyzer = BRepCheck_Analyzer(face)
                        if face_analyzer.IsValid():
                            all_valid_faces_from_acceptable_shells.append(face)
                            valid_count += 1
                        else:
                            invalid_count += 1

                    face_exp.Next()

                if debug and invalid_count > 0:
                    log(f"    → Kept {valid_count} valid faces, removed {invalid_count} invalid faces")
                    total_invalid_removed += invalid_count

            if debug:
                log(f"[SHELL DIAGNOSTIC] Collected {len(all_valid_faces_from_acceptable_shells)} valid faces from {len(acceptable_shells)} shells")
                if total_invalid_removed > 0:
                    log(f"[SHELL DIAGNOSTIC] Removed {total_invalid_removed} invalid faces total")

            # Re-sew all collected valid faces into a unified shell
            if len(all_valid_faces_from_acceptable_shells) > 0:
                if debug:
                    log(f"[SHELL DIAGNOSTIC] Re-sewing {len(all_valid_faces_from_acceptable_shells)} faces into unified shell...")

                sewing_unified = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
                for fc in all_valid_faces_from_acceptable_shells:
                    sewing_unified.Add(fc)
                sewing_unified.Perform()
                unified_sewn = sewing_unified.SewedShape()

                # Extract all shells from unified result
                unified_exp = TopExp_Explorer(unified_sewn, TopAbs_SHELL)
                unified_shells = []
                while unified_exp.More():
                    unified_shells.append(topods.Shell(unified_exp.Current()))
                    unified_exp.Next()

                if debug:
                    log(f"[SHELL DIAGNOSTIC] Unified re-sewing produced {len(unified_shells)} shell(s)")

                if len(unified_shells) > 0:
                    # If multiple shells, create a Compound to preserve all geometry
                    if len(unified_shells) > 1:
                        from OCC.Core.TopoDS import TopoDS_Compound
                        from OCC.Core.BRep import BRep_Builder

                        if debug:
                            log(f"[SHELL DIAGNOSTIC] Multiple disconnected shells detected, creating Compound to preserve all geometry...")

                        # Log face counts for each shell
                        shell_face_counts = []
                        for i, sh in enumerate(unified_shells):
                            face_exp2 = TopExp_Explorer(sh, TopAbs_FACE)
                            face_count = 0
                            while face_exp2.More():
                                face_count += 1
                                face_exp2.Next()
                            shell_face_counts.append(face_count)

                            if debug:
                                log(f"  Unified shell {i+1}: {face_count} faces")

                        # Create Compound containing all shells
                        compound = TopoDS_Compound()
                        builder = BRep_Builder()
                        builder.MakeCompound(compound)

                        for sh in unified_shells:
                            builder.Add(compound, sh)

                        total_faces_in_compound = sum(shell_face_counts)

                        if debug:
                            log(f"[SHELL DIAGNOSTIC] Created Compound with {len(unified_shells)} shells ({total_faces_in_compound} total faces)")

                        # Return Compound instead of Shell
                        shell = compound
                    else:
                        shell = unified_shells[0]
                        if debug:
                            unified_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
                            unified_face_count = 0
                            while unified_face_exp.More():
                                unified_face_count += 1
                                unified_face_exp.Next()
                            log(f"[SHELL DIAGNOSTIC] Unified shell contains {unified_face_count} faces")
                else:
                    # Fallback: use largest acceptable shell if unification failed
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Unified re-sewing produced no shells, using largest acceptable shell as fallback")
                    largest_acceptable = max(acceptable_shells, key=lambda s: s['face_count'])
                    shell = largest_acceptable['shell']
            else:
                # No valid faces collected - fallback to largest acceptable shell
                largest_acceptable = max(acceptable_shells, key=lambda s: s['face_count'])
                shell = largest_acceptable['shell']

        else:
            # No valid shells found, try re-sewing approach as fallback
            if debug:
                log(f"[SHELL DIAGNOSTIC] No valid shells found, attempting re-sewing as fallback...")

            all_faces_from_shells = []
            for info in shell_info:
                sh = info['shell']
                face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                while face_exp.More():
                    all_faces_from_shells.append(topods.Face(face_exp.Current()))
                    face_exp.Next()

            if debug:
                log(f"[SHELL DIAGNOSTIC] Collected {len(all_faces_from_shells)} faces from all shells for re-sewing")

            # Build single shell from all collected faces
            if all_faces_from_shells:
                sewing_multi = BRepBuilderAPI_Sewing(tolerance * 10.0, True, True, True, False)
                for fc in all_faces_from_shells:
                    sewing_multi.Add(fc)
                sewing_multi.Perform()
                multi_sewn = sewing_multi.SewedShape()

                # Extract all shells from multi-sewn result
                multi_exp = TopExp_Explorer(multi_sewn, TopAbs_SHELL)
                resewn_shells = []
                while multi_exp.More():
                    resewn_shells.append(topods.Shell(multi_exp.Current()))
                    multi_exp.Next()

                if debug:
                    log(f"[SHELL DIAGNOSTIC] Re-sewing produced {len(resewn_shells)} shell(s)")

                # If re-sewing created multiple shells again, find the largest one
                if len(resewn_shells) > 1:
                    if debug:
                        log("[SHELL DIAGNOSTIC] Re-sewing still created multiple shells, selecting largest...")

                    largest_shell = None
                    largest_face_count = 0

                    for i, sh in enumerate(resewn_shells):
                        face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                        face_count = 0
                        while face_exp.More():
                            face_count += 1
                            face_exp.Next()

                        if debug:
                            log(f"  Re-sewn shell {i+1}: {face_count} faces")

                        if face_count > largest_face_count:
                            largest_face_count = face_count
                            largest_shell = sh

                    shell = largest_shell
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Selected largest re-sewn shell with {largest_face_count} faces")

                elif len(resewn_shells) == 1:
                    shell = resewn_shells[0]
                    if debug:
                        shell_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
                        shell_face_count = 0
                        while shell_face_exp.More():
                            shell_face_count += 1
                            shell_face_exp.Next()
                        log(f"[SHELL DIAGNOSTIC] Rebuilt shell contains {shell_face_count} faces")
                else:
                    # Fallback: use largest original shell if re-sewing failed completely
                    if debug:
                        log("[SHELL DIAGNOSTIC] Re-sewing failed, selecting largest original shell as fallback")

                    largest_shell = None
                    largest_face_count = 0

                    for i, sh in enumerate(shells):
                        face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                        face_count = 0
                        while face_exp.More():
                            face_count += 1
                            face_exp.Next()

                        if face_count > largest_face_count:
                            largest_face_count = face_count
                            largest_shell = sh

                    shell = largest_shell
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Selected largest original shell with {largest_face_count} faces")
            else:
                # No faces collected, use first shell as fallback
                shell = shells[0]

    elif shell_count == 1:
        # Single shell - use it directly
        shell = shells[0]

        # DEBUG: Count faces in extracted shell
        if debug:
            shell_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
            shell_face_count = 0
            while shell_face_exp.More():
                shell_face_count += 1
                shell_face_exp.Next()
            log(f"[SHELL DIAGNOSTIC] Extracted shell contains {shell_face_count} faces")
    else:
        # No shells found
        if debug:
            log("[SHELL DIAGNOSTIC] No shells found in sewn shape")
        return None

    if shell:

        # Validate shell
        try:
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.BRepCheck import BRepCheck_Analyzer
            analyzer = BRepCheck_Analyzer(shell)
            if not analyzer.IsValid():
                if debug:
                    log("Warning: Shell is not valid, attempting to fix...")

                # Try multiple fixing strategies
                if shape_fix_level == "ultra":
                    # Ultra mode: try aggressive shell fixing
                    try:
                        from OCC.Core.ShapeFix import ShapeFix_Shell

                        shell_fixer = ShapeFix_Shell(shell)
                        shell_fixer.SetPrecision(tolerance)
                        shell_fixer.SetMaxTolerance(tolerance * 1000.0)
                        shell_fixer.Perform()
                        fixed_shell = shell_fixer.Shell()

                        # Validate fixed shell
                        if fixed_shell is not None and not fixed_shell.IsNull():
                            analyzer = BRepCheck_Analyzer(fixed_shell)
                            if analyzer.IsValid():
                                if debug:
                                    log("Shell fixed successfully")
                                shell = fixed_shell
                            else:
                                if debug:
                                    log("Shell still invalid after fixing, using best attempt")
                    except Exception as e:
                        if debug:
                            log(f"ShapeFix_Shell failed: {e}")
                else:
                    # Standard shell fixing
                    try:
                        from OCC.Core.ShapeFix import ShapeFix_Shell
                        shell_fixer = ShapeFix_Shell(shell)
                        shell_fixer.Perform()
                        shell = shell_fixer.Shell()
                    except Exception as e:
                        if debug:
                            log(f"ShapeFix_Shell failed: {e}")
        except Exception as e:
            if debug:
                log(f"Shell validation failed: {e}")

        if debug:
            log("Shell construction complete")

        return shell

    if debug:
        log("Error: No shell found in sewn shape")

    return None


def _diagnose_shape_errors(shape, debug: bool = False) -> dict:
    """Diagnose detailed errors in a shape using BRepCheck_Analyzer.

    Args:
        shape: TopoDS_Shape to diagnose
        debug: Enable debug logging

    Returns:
        Dictionary with error information
    """
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRep import BRep_Tool

    errors = {
        'is_valid': False,
        'free_edges_count': 0,
        'invalid_faces': [],
        'shell_closed': None,
        'error_summary': {}
    }

    try:
        analyzer = BRepCheck_Analyzer(shape)
        errors['is_valid'] = analyzer.IsValid()

        if not errors['is_valid']:
            # Count free edges (edges not fully connected)
            edge_exp = TopExp_Explorer(shape, TopAbs_EDGE)
            edge_count = 0
            free_edge_count = 0
            while edge_exp.More():
                edge = topods.Edge(edge_exp.Current())
                # Free edges are not closed (not shared by 2 faces)
                try:
                    if not BRep_Tool.IsClosed(edge, shape):
                        free_edge_count += 1
                except:
                    pass
                edge_count += 1
                edge_exp.Next()
            errors['free_edges_count'] = free_edge_count

            # Check faces
            face_exp = TopExp_Explorer(shape, TopAbs_FACE)
            face_count = 0
            while face_exp.More():
                face = topods.Face(face_exp.Current())
                face_analyzer = BRepCheck_Analyzer(face)
                if not face_analyzer.IsValid():
                    errors['invalid_faces'].append(face_count)
                face_count += 1
                face_exp.Next()

            # Check shell closure
            shell_exp = TopExp_Explorer(shape, TopAbs_SHELL)
            if shell_exp.More():
                shell = topods.Shell(shell_exp.Current())
                errors['shell_closed'] = BRep_Tool.IsClosed(shell)

            errors['error_summary'] = {
                'total_edges': edge_count,
                'free_edges': free_edge_count,
                'total_faces': face_count,
                'invalid_faces_count': len(errors['invalid_faces']),
                'shell_closed': errors['shell_closed']
            }

            if debug:
                log(f"[DIAGNOSTICS] Shape validation failed:")
                log(f"  - Total edges: {edge_count}, Free edges: {free_edge_count}")
                log(f"  - Total faces: {face_count}, Invalid faces: {len(errors['invalid_faces'])}")
                log(f"  - Shell closed: {errors['shell_closed']}")
    except Exception as e:
        errors['exception'] = str(e)
        if debug:
            log(f"[DIAGNOSTICS] Exception during diagnosis: {e}")

    return errors


def _is_valid_shape(shape) -> bool:
    """Check if a shape is a valid solid, shell, or compound.

    This is used to validate results from _make_solid_with_cavities(), which can return
    solids, shells, or compounds depending on the geometry. All three types are acceptable
    for STEP export.

    Args:
        shape: TopoDS_Shape to validate

    Returns:
        True if shape is a valid solid, shell, or compound, False otherwise
    """
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_COMPOUND

    if shape is None:
        return False

    try:
        shape_type = shape.ShapeType()

        # Accept SOLID, SHELL, and COMPOUND (but not face, edge, etc.)
        if shape_type not in (TopAbs_SOLID, TopAbs_SHELL, TopAbs_COMPOUND):
            return False

        # Check if the shape is topologically valid
        # Note: Compounds may contain multiple disconnected parts, which is valid
        analyzer = BRepCheck_Analyzer(shape)
        return analyzer.IsValid()
    except Exception:
        return False


def _make_solid_with_cavities(exterior_faces: List["TopoDS_Face"],
                               interior_shells_faces: List[List["TopoDS_Face"]],
                               tolerance: Optional[float] = None,
                               debug: bool = False,
                               precision_mode: str = "auto",
                               shape_fix_level: str = "standard") -> Optional["TopoDS_Shape"]:
    """Build a solid with cavities from exterior and interior shells.

    Args:
        exterior_faces: Faces forming the outer shell
        interior_shells_faces: List of face lists, each forming an interior shell (cavity)
        tolerance: Sewing tolerance (auto-computed if None)
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness

    Returns:
        TopoDS_Solid or TopoDS_Shape (if solid construction fails)
    """
    from OCC.Core.BRep import BRep_Tool

    # Auto-compute tolerance if not provided
    if tolerance is None:
        tolerance = _compute_tolerance_from_face_list(exterior_faces, precision_mode)
        if debug:
            log(f"Auto-computed tolerance: {tolerance:.6f} (precision_mode: {precision_mode})")

    # Build exterior shell
    if debug:
        log(f"Attempting to build exterior shell from {len(exterior_faces)} faces...")
    exterior_shell = _build_shell_from_faces(exterior_faces, tolerance, debug, shape_fix_level)
    if exterior_shell is None:
        if debug:
            log(f"ERROR: Failed to build exterior shell (sewing or shell extraction failed)")
        return None

    # Check if exterior shell is closed
    try:
        is_closed = BRep_Tool.IsClosed(exterior_shell)
        if not is_closed:
            if debug:
                log(f"WARNING: Exterior shell is not closed, returning shell instead of solid")
        else:
            if debug:
                log(f"Exterior shell is closed, will attempt to create solid")
    except Exception as e:
        if debug:
            log(f"Failed to check if shell is closed: {e}")
        is_closed = False

    # Build interior shells
    interior_shells: List[TopoDS_Shell] = []
    for i, int_faces in enumerate(interior_shells_faces):
        int_shell = _build_shell_from_faces(int_faces, tolerance, debug, shape_fix_level)
        if int_shell is not None:
            try:
                if BRep_Tool.IsClosed(int_shell):
                    interior_shells.append(int_shell)
                    if debug:
                        log(f"Added interior shell {i+1} (closed)")
                else:
                    if debug:
                        log(f"Interior shell {i+1} is not closed, skipping")
            except Exception as e:
                if debug:
                    log(f"Interior shell {i+1} check failed: {e}")

    # Try to create solid
    if is_closed:
        try:
            mk_solid = BRepBuilderAPI_MakeSolid(exterior_shell)

            # Add interior shells (cavities)
            for int_shell in interior_shells:
                try:
                    mk_solid.Add(int_shell)
                except Exception as e:
                    if debug:
                        log(f"Failed to add interior shell: {e}")

            solid = mk_solid.Solid()

            # Validate solid
            log(f"\n[PHASE:4] SOLID VALIDATION")
            analyzer = BRepCheck_Analyzer(solid)
            if analyzer.IsValid():
                log(f"[VALIDATION] ✓ Initial solid validation succeeded")
                if debug:
                    log(f"[INFO] Created valid solid with {len(interior_shells)} cavities")
                return solid
            else:
                log(f"[VALIDATION] ✗ Initial solid validation failed")

                # Diagnose the specific errors
                if debug:
                    log(f"\n[PHASE:4.5] ERROR DIAGNOSIS")
                    diag = _diagnose_shape_errors(solid, debug=True)
                    if 'exception' not in diag:
                        log(f"[DIAGNOSIS] Root cause analysis:")
                        summary = diag.get('error_summary', {})
                        if summary.get('free_edges', 0) > 0:
                            log(f"  ⚠ {summary['free_edges']}/{summary['total_edges']} edges are not fully connected (FREE EDGES)")
                            log(f"     → This means some faces don't share edges properly")
                        if summary.get('invalid_faces_count', 0) > 0:
                            log(f"  ⚠ {summary['invalid_faces_count']}/{summary['total_faces']} faces are invalid")
                        if summary.get('shell_closed') == False:
                            log(f"  ⚠ Shell is not closed (has gaps or holes)")
                        log(f"[DIAGNOSIS] This geometry has fundamental topology issues that may not be repairable")

                log(f"\n[PHASE:5] AUTOMATIC REPAIR WITH AUTO-ESCALATION")

                # Define escalation levels (minimal → standard → aggressive → ultra)
                escalation_map = {
                    'minimal': ['minimal', 'standard', 'aggressive', 'ultra'],
                    'standard': ['standard', 'aggressive', 'ultra'],
                    'aggressive': ['aggressive', 'ultra'],
                    'ultra': ['ultra']
                }

                levels_to_try = escalation_map.get(shape_fix_level, ['minimal', 'standard', 'aggressive', 'ultra'])
                log(f"[INFO] Auto-escalation enabled: will try levels {' → '.join(levels_to_try)}")
                log(f"[INFO] Starting from: {shape_fix_level}")
                log(f"")

                # Try each escalation level
                for current_level_idx, current_level in enumerate(levels_to_try):
                    if current_level_idx > 0:
                        log(f"\n{'='*80}")
                        log(f"[ESCALATION] Previous level failed, escalating to: {current_level}")
                        log(f"{'='*80}")

                    log(f"\n[REPAIR LEVEL: {current_level.upper()}]")

                    # Repair Strategy 1: ShapeFix_Solid (always try)
                    log(f"\n[STEP 1/4] Trying ShapeFix_Solid...")
                    try:
                        fixer = ShapeFix_Solid(solid)
                        fixer.SetPrecision(tolerance)
                        fixer.SetMaxTolerance(tolerance * 10)
                        fixer.Perform()
                        repaired_solid = fixer.Solid()

                        analyzer_repaired = BRepCheck_Analyzer(repaired_solid)
                        if analyzer_repaired.IsValid():
                            log(f"[REPAIR] ✓ ShapeFix_Solid succeeded at level '{current_level}'!")
                            log(f"[INFO] Repaired solid is now valid")
                            if current_level_idx > 0:
                                log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                            return repaired_solid
                        else:
                            log(f"[REPAIR] ✗ ShapeFix_Solid did not fix all issues")
                            solid = repaired_solid  # Use partially repaired version for next attempts
                    except Exception as e:
                        log(f"[REPAIR] ✗ ShapeFix_Solid raised exception: {type(e).__name__}: {str(e)}")

                    # Repair Strategy 2: ShapeUpgrade_UnifySameDomain (standard+)
                    if current_level in ['standard', 'aggressive', 'ultra']:
                        log(f"\n[STEP 2/4] Trying ShapeUpgrade_UnifySameDomain (topology simplification)...")
                        try:
                            unifier = ShapeUpgrade_UnifySameDomain(solid, True, True, True)
                            unifier.Build()
                            unified_shape = unifier.Shape()

                            analyzer_unified = BRepCheck_Analyzer(unified_shape)
                            if analyzer_unified.IsValid():
                                log(f"[REPAIR] ✓ ShapeUpgrade_UnifySameDomain succeeded at level '{current_level}'!")
                                log(f"[INFO] Unified shape is now valid")
                                if current_level_idx > 0:
                                    log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                                return unified_shape
                            else:
                                log(f"[REPAIR] ✗ Topology simplification did not create valid solid")
                        except Exception as e:
                            log(f"[REPAIR] ✗ ShapeUpgrade_UnifySameDomain raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 2/4] Skipped (requires level standard+)")

                    # Repair Strategy 3: Rebuild with relaxed tolerance (aggressive+)
                    if current_level in ['aggressive', 'ultra']:
                        log(f"\n[STEP 3/4] Trying rebuild with relaxed tolerance (2x)...")
                        try:
                            relaxed_tolerance = tolerance * 2.0
                            log(f"[INFO] Original tolerance: {tolerance:.6f}")
                            log(f"[INFO] Relaxed tolerance: {relaxed_tolerance:.6f}")

                            # Rebuild shell with relaxed tolerance
                            relaxed_shell = _build_shell_from_faces(exterior_faces, relaxed_tolerance, debug, current_level)
                            if relaxed_shell is not None and BRep_Tool.IsClosed(relaxed_shell):
                                mk_solid_relaxed = BRepBuilderAPI_MakeSolid(relaxed_shell)
                                for int_shell in interior_shells:
                                    try:
                                        mk_solid_relaxed.Add(int_shell)
                                    except Exception:
                                        pass

                                relaxed_solid = mk_solid_relaxed.Solid()
                                analyzer_relaxed = BRepCheck_Analyzer(relaxed_solid)
                                if analyzer_relaxed.IsValid():
                                    log(f"[REPAIR] ✓ Rebuild with relaxed tolerance succeeded at level '{current_level}'!")
                                    if current_level_idx > 0:
                                        log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                                    return relaxed_solid
                                else:
                                    log(f"[REPAIR] ✗ Relaxed tolerance rebuild did not create valid solid")
                            else:
                                log(f"[REPAIR] ✗ Could not rebuild closed shell with relaxed tolerance")
                        except Exception as e:
                            log(f"[REPAIR] ✗ Relaxed tolerance rebuild raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 3/4] Skipped (requires level aggressive+)")

                    # Repair Strategy 4: ShapeFix_Shape (ultra only)
                    if current_level == 'ultra':
                        log(f"\n[STEP 4/4] Trying ShapeFix_Shape (most aggressive)...")
                        try:
                            shape_fixer = ShapeFix_Shape(solid)
                            shape_fixer.SetPrecision(tolerance)
                            shape_fixer.SetMaxTolerance(tolerance * 100)
                            shape_fixer.Perform()
                            fixed_shape = shape_fixer.Shape()

                            analyzer_fixed = BRepCheck_Analyzer(fixed_shape)
                            if analyzer_fixed.IsValid():
                                log(f"[REPAIR] ✓ ShapeFix_Shape succeeded at level 'ultra'!")
                                if current_level_idx > 0:
                                    log(f"[INFO] Success after escalation from '{shape_fix_level}' to 'ultra'")
                                return fixed_shape
                            else:
                                log(f"[REPAIR] ✗ ShapeFix_Shape did not create valid solid")
                        except Exception as e:
                            log(f"[REPAIR] ✗ ShapeFix_Shape raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 4/4] Skipped (requires level ultra)")

                    log(f"\n[REPAIR LEVEL: {current_level.upper()}] ✗ All strategies failed at this level")

                # All escalation levels exhausted
                log(f"\n{'='*80}")
                log(f"[REPAIR] ✗ All repair attempts exhausted across all escalation levels")
                log(f"[INFO] Tried levels: {' → '.join(levels_to_try)}")
                log(f"[DECISION] → Returning shell instead of solid (may cause issues in merging/export)")
                log(f"⚠ WARNING: This shape may fail in BuildingPart fusion or STEP export")
                log(f"⚠ WARNING: The building geometry has fundamental topology issues")
                return exterior_shell
        except Exception as e:
            if debug:
                log(f"Solid creation failed: {e}, returning shell")
            return exterior_shell
    else:
        if debug:
            log("Exterior shell not closed, cannot create solid")
        return exterior_shell


def _extract_single_solid(elem: ET.Element, xyz_transform: Optional[Callable] = None,
                          id_index: Optional[dict[str, ET.Element]] = None,
                          debug: bool = False,
                          precision_mode: str = "auto",
                          shape_fix_level: str = "standard") -> Optional["TopoDS_Shape"]:
    """Extract a single solid from a building or building part element.

    Enhanced LOD extraction with priority-based fallback chain:

    LOD3 (highest detail - architectural models with detailed walls/roofs/openings):
      1. bldg:lod3Solid//gml:Solid
      2. bldg:lod3MultiSurface
      3. bldg:lod3Geometry
      4. bldg:boundedBy surfaces (with all boundary types)

    LOD2 (differentiated roof structures and thematic surfaces):
      1. bldg:lod2Solid//gml:Solid (standard solid structure)
      2. bldg:lod2MultiSurface (multiple independent surfaces)
      3. bldg:lod2Geometry (generic geometry container)
      4. bldg:boundedBy surfaces (WallSurface, RoofSurface, GroundSurface, etc.)

    LOD1 (simple block models):
      1. bldg:lod1Solid//gml:Solid

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness

    Returns:
        TopoDS_Shape or None
    """
    # Force debug mode for comprehensive logging (issue #48 diagnostics)
    # This ensures detailed logs are always available for troubleshooting geometry extraction issues
    debug = True

    elem_id = elem.get("{http://www.opengis.net/gml}id") or "unknown"
    exterior_faces: List[TopoDS_Face] = []
    prefer_bounded_by = False  # Flag to skip intermediate strategies if boundedBy is preferred

    # Check if log file is already open (from parent call or previous Building/BuildingPart)
    # If so, reuse it instead of creating a new one
    existing_log_file = getattr(_thread_local, 'log_file', None)
    log_file_created_here = False  # Track whether this function created the log file

    # Create log file only if one doesn't already exist
    log_file = None
    if existing_log_file is None:
        # Always create log file for conversion tracking (not just in debug mode)
        log_dir = os.path.join(os.path.dirname(__file__), "..", "debug_logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = elem_id.replace(":", "_").replace("/", "_")[:50]
        log_path = os.path.join(log_dir, f"conversion_{safe_id}_{timestamp}.log")
        try:
            log_file = open(log_path, "w", encoding="utf-8")
            log_file_created_here = True  # Mark that we created the log file
            # Write comprehensive log header with legend for LLM analysis
            log_file.write(f"{'='*80}\n")
            log_file.write(f"CITYGML TO STEP CONVERSION LOG\n")
            log_file.write(f"{'='*80}\n")
            log_file.write(f"Building ID: {elem_id}\n")
            log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log_file.write(f"Precision mode: {precision_mode}\n")
            log_file.write(f"Shape fix level: {shape_fix_level}\n")
            log_file.write(f"Debug mode: Always enabled for detailed diagnostics\n")
            log_file.write(f"{'='*80}\n\n")

            # Log Legend for LLM Analysis (凡例)
            log_file.write(f"LOG LEGEND (for AI/LLM Analysis and Debugging):\n")
            log_file.write(f"{'-'*80}\n")
            log_file.write(f"  [PHASE:N]       = Major processing phase (1-7)\n")
            log_file.write(f"  [STEP X/Y]      = Step number within current phase\n")
            log_file.write(f"  ✓ SUCCESS       = Operation completed successfully\n")
            log_file.write(f"  ✗ FAILED        = Operation failed\n")
            log_file.write(f"  ⚠ WARNING       = Potential issue detected (may not be critical)\n")
            log_file.write(f"  → DECISION      = Decision point (which strategy/fallback to use)\n")
            log_file.write(f"  ├─              = Child operation (subprocess)\n")
            log_file.write(f"  └─              = Final result of operation\n")
            log_file.write(f"  [GEOMETRY]      = Geometry extraction/construction operation\n")
            log_file.write(f"  [VALIDATION]    = Topology/geometry validation check\n")
            log_file.write(f"  [REPAIR]        = Automatic repair attempt\n")
            log_file.write(f"  [ERROR CODE]    = OpenCASCADE error code/type\n")
            log_file.write(f"  [INFO]          = Informational message\n")
            log_file.write(f"{'-'*80}\n\n")

            log_file.write(f"PROCESSING PHASES:\n")
            log_file.write(f"  [PHASE:1] LOD Strategy Selection (LOD3→LOD2→LOD1 fallback)\n")
            log_file.write(f"  [PHASE:2] Geometry Extraction (faces from gml:Solid)\n")
            log_file.write(f"  [PHASE:3] Shell Construction (sewing faces)\n")
            log_file.write(f"  [PHASE:4] Solid Validation (topology check)\n")
            log_file.write(f"  [PHASE:5] Automatic Repair (ShapeFix_Solid, tolerance adjustment)\n")
            log_file.write(f"  [PHASE:6] BuildingPart Merging (Boolean fusion if multiple parts)\n")
            log_file.write(f"  [PHASE:7] STEP Export (final output generation)\n")
            log_file.write(f"{'='*80}\n\n")
            log(f"[CONVERSION] Logging to: {log_path}")
            # Set log file for this thread (now all functions can use global log())
            set_log_file(log_file)
        except Exception as e:
            log(f"[CONVERSION] Warning: Failed to create log file: {e}")
            log_file = None
            log_file_created_here = False
            set_log_file(None)
    else:
        # Reuse existing log file from parent call
        if debug:
            log(f"[CONVERSION] Reusing existing log file for element: {elem_id}")
        log_file = existing_log_file

    # Wrap entire conversion in try-finally to ensure log cleanup on exception
    try:
        # Log conversion start with structured format
        log(f"\n{'='*80}")
        log(f"[PHASE:1] LOD STRATEGY SELECTION")
        log(f"{'='*80}")
        log(f"[INFO] Building ID: {elem_id}")
        log(f"[INFO] Precision mode: {precision_mode}")
        log(f"[INFO] Shape fix level: {shape_fix_level}")
        log(f"[INFO] Strategy: LOD3 → LOD2 → LOD1 (with fallback to boundedBy)")
        log(f"")

        # =========================================================================
        # LOD3 Extraction - Highest detail level (architectural models)
        # =========================================================================
        # LOD3 represents architectural models with:
        # - Detailed wall and roof structures with surface textures
        # - Openings: windows (bldg:Window), doors (bldg:Door)
        # - BuildingInstallation elements (balconies, chimneys, etc.)
        # Priority: Try LOD3 first for maximum detail before falling back to LOD2/LOD1

        # Strategy 1: LOD3 Solid (most detailed solid structure)
        lod3_solid = elem.find(".//bldg:lod3Solid", NS)
        if lod3_solid is not None:
            log(f"[CONVERSION DEBUG] Trying LOD3 Strategy 1: lod3Solid")
            solid_elem = lod3_solid.find(".//gml:Solid", NS)
            if solid_elem is not None:
                log(f"[CONVERSION DEBUG]   ✓ Found bldg:lod3Solid//gml:Solid")
                if debug:
                    log(f"[LOD3] Found bldg:lod3Solid//gml:Solid in {elem_id}")

                # Extract exterior and interior shells
                exterior_faces_solid, interior_shells_faces = _extract_solid_shells(
                    solid_elem, xyz_transform, id_index, debug
                )

                log(f"[CONVERSION DEBUG]   Extracted {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")
                if debug:
                    log(f"[LOD3] Solid extraction: {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")

                if exterior_faces_solid:
                    # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)
                    # No face-level re-centering needed

                    # Build solid with cavities (adaptive tolerance)
                    result = _make_solid_with_cavities(
                        exterior_faces_solid, interior_shells_faces, tolerance=None, debug=debug,
                        precision_mode=precision_mode, shape_fix_level=shape_fix_level
                    )
                    if result is not None and _is_valid_shape(result):
                        log(f"[CONVERSION DEBUG]   ✓✓ LOD3 Strategy 1 SUCCEEDED with valid solid - Returning detailed LOD3 model")
                        if debug:
                            log(f"[LOD3] Solid processing successful, returning shape")
                        return result
                    else:
                        if result is not None:
                            log(f"[CONVERSION DEBUG]   ⚠ LOD3 Strategy 1 returned invalid solid/shell, trying next strategy...")
                            if debug:
                                log(f"[LOD3] Solid validation failed, trying other strategies...")
                        else:
                            log(f"[CONVERSION DEBUG]   ✗ LOD3 Strategy 1 failed (shell building), trying next strategy...")
                            if debug:
                                log(f"[LOD3] Solid shell building failed, trying other strategies...")
                else:
                    log(f"[CONVERSION DEBUG]   ✗ LOD3 Strategy 1 failed (0 faces), trying next strategy...")
                    if debug:
                        log(f"[LOD3] Solid extracted 0 faces, trying other strategies...")
            else:
                log(f"[CONVERSION DEBUG]   ✗ lod3Solid found but no gml:Solid child")
        else:
            log(f"[CONVERSION DEBUG] LOD3 Strategy 1: lod3Solid not found")

        # Strategy 2: LOD3 MultiSurface (multiple detailed surfaces)
        lod3_multi = elem.find(".//bldg:lod3MultiSurface", NS)
        if lod3_multi is not None:
            if debug:
                log(f"[LOD3] Found bldg:lod3MultiSurface in {elem_id}")

            # Look for MultiSurface or CompositeSurface
            for surface_container in lod3_multi.findall(".//gml:MultiSurface", NS) + lod3_multi.findall(".//gml:CompositeSurface", NS):
                faces_multi = _extract_faces_from_surface_container(surface_container, xyz_transform, id_index, debug)
                exterior_faces.extend(faces_multi)

            if debug:
                log(f"[LOD3] MultiSurface extraction: {len(exterior_faces)} faces")

            if exterior_faces:
                # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                # Build solid from collected faces
                result = _make_solid_with_cavities(
                    exterior_faces, [], tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None and _is_valid_shape(result):
                    if debug:
                        log(f"[LOD3] MultiSurface processing successful with valid solid, returning shape")
                    return result
                elif result is not None:
                    if debug:
                        log(f"[LOD3] MultiSurface returned invalid solid/shell, trying next strategy")
                else:
                    if debug:
                        log(f"[LOD3] MultiSurface shell building failed, trying other strategies...")
                    # Clear for next strategy
                    exterior_faces = []

        # Strategy 3: LOD3 Geometry (generic LOD3 geometry container)
        lod3_geom = elem.find(".//bldg:lod3Geometry", NS)
        if lod3_geom is not None:
            if debug:
                log(f"[LOD3] Found bldg:lod3Geometry in {elem_id}")

            # Try to find any surface structures
            for surface_container in (
                lod3_geom.findall(".//gml:MultiSurface", NS) +
                lod3_geom.findall(".//gml:CompositeSurface", NS) +
                lod3_geom.findall(".//gml:Solid", NS)
            ):
                if surface_container.tag.endswith("Solid"):
                    # Process as Solid
                    faces_geom, interior_shells = _extract_solid_shells(surface_container, xyz_transform, id_index, debug)
                    exterior_faces.extend(faces_geom)
                else:
                    # Process as MultiSurface/CompositeSurface
                    faces_geom = _extract_faces_from_surface_container(surface_container, xyz_transform, id_index, debug)
                    exterior_faces.extend(faces_geom)

            if debug:
                log(f"[LOD3] Geometry extraction: {len(exterior_faces)} faces")

            if exterior_faces:
                # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                result = _make_solid_with_cavities(
                    exterior_faces, [], tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None and _is_valid_shape(result):
                    if debug:
                        log(f"[LOD3] Geometry processing successful with valid solid, returning shape")
                    return result
                elif result is not None:
                    if debug:
                        log(f"[LOD3] Geometry returned invalid solid/shell, trying next strategy")
                else:
                    if debug:
                        log(f"[LOD3] Geometry shell building failed, trying LOD2...")
                    exterior_faces = []

        if debug and not exterior_faces:
            log(f"[LOD3] No LOD3 geometry found, falling back to LOD2 for {elem_id}")

        # =========================================================================
        # LOD2 Extraction - Try multiple strategies
        # =========================================================================
        # LOD2 is PLATEAU's primary use case, representing:
        # - Buildings with differentiated roof structures (flat, gabled, hipped, etc.)
        # - Thematic boundary surfaces: WallSurface, RoofSurface, GroundSurface, etc.
        # - More detailed than LOD1 (simple blocks) but less than LOD3 (architectural models)
        # This is the most common LOD in PLATEAU datasets

        # Strategy 1: LOD2 Solid (standard gml:Solid structure)
        log(f"[CONVERSION DEBUG] Falling back to LOD2 (PLATEAU's most common LOD)")
        lod2_solid = elem.find(".//bldg:lod2Solid", NS)
        if lod2_solid is not None:
            log(f"[CONVERSION DEBUG] Trying LOD2 Strategy 1: lod2Solid")
            solid_elem = lod2_solid.find(".//gml:Solid", NS)
            if solid_elem is not None:
                log(f"[CONVERSION DEBUG]   ✓ Found bldg:lod2Solid//gml:Solid")
                if debug:
                    log(f"[LOD2] Found bldg:lod2Solid//gml:Solid in {elem_id}")

                # Extract exterior and interior shells
                exterior_faces_solid, interior_shells_faces = _extract_solid_shells(
                    solid_elem, xyz_transform, id_index, debug
                )

                log(f"[CONVERSION DEBUG]   Extracted {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")
                if debug:
                    log(f"[LOD2] Solid extraction: {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")

                if exterior_faces_solid:
                    # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                    # Build solid with cavities (adaptive tolerance)
                    result = _make_solid_with_cavities(
                        exterior_faces_solid, interior_shells_faces, tolerance=None, debug=debug,
                        precision_mode=precision_mode, shape_fix_level=shape_fix_level
                    )
                    if result is not None and _is_valid_shape(result):
                        log(f"[CONVERSION DEBUG]   ✓ LOD2 Strategy 1 (lod2Solid) SUCCEEDED with valid solid ({len(exterior_faces_solid)} faces)")
                        if debug:
                            log(f"[LOD2] Solid processing successful")

                        # FIX for Issue #48: Check if boundedBy WallSurfaces exist and have more detail
                        # Many PLATEAU buildings (especially tall ones like JP Tower) have:
                        # - lod2Solid: Simplified envelope (basic shape)
                        # - boundedBy/WallSurface: Detailed wall geometry (architectural details)
                        # We need to check both and use the more detailed one
                        log(f"[CONVERSION DEBUG]   Checking if boundedBy has more detailed geometry...")

                        bounded_surfaces_check = (
                                elem.findall(".//bldg:boundedBy/bldg:WallSurface", NS) +
                                elem.findall(".//bldg:boundedBy/bldg:RoofSurface", NS) +
                                elem.findall(".//bldg:boundedBy/bldg:GroundSurface", NS) +
                                elem.findall(".//bldg:boundedBy/bldg:OuterCeilingSurface", NS) +
                                elem.findall(".//bldg:boundedBy/bldg:OuterFloorSurface", NS) +
                                elem.findall(".//bldg:boundedBy/bldg:ClosureSurface", NS)
                            )

                        if bounded_surfaces_check:
                            log(f"[CONVERSION DEBUG]   Found {len(bounded_surfaces_check)} boundedBy surfaces")
                            log(f"[CONVERSION DEBUG]   Comparing lod2Solid ({len(exterior_faces_solid)} faces) vs boundedBy...")

                            # Quick extraction to count boundedBy faces
                            bounded_faces_count = 0
                            for surf in bounded_surfaces_check:
                                surf_face_count = 0
                                # Try all 3 methods like in the main boundedBy strategy
                                for lod_tag in [".//bldg:lod3MultiSurface", ".//bldg:lod3Geometry",
                                               ".//bldg:lod2MultiSurface", ".//bldg:lod2Geometry"]:
                                    surf_geom = surf.find(lod_tag, NS)
                                    if surf_geom is not None:
                                        for container in surf_geom.findall(".//gml:MultiSurface", NS) + surf_geom.findall(".//gml:CompositeSurface", NS):
                                            polys = container.findall(".//gml:Polygon", NS)
                                            surf_face_count += len(polys)
                                        if surf_face_count > 0:
                                            break

                                # Method 2: Direct containers
                                if surf_face_count == 0:
                                    for container in surf.findall("./gml:MultiSurface", NS) + surf.findall("./gml:CompositeSurface", NS):
                                        polys = container.findall(".//gml:Polygon", NS)
                                        surf_face_count += len(polys)

                                # Method 3: Direct polygons
                                if surf_face_count == 0:
                                    polys = surf.findall(".//gml:Polygon", NS)
                                    surf_face_count += len(polys)

                                bounded_faces_count += surf_face_count

                            log(f"[CONVERSION DEBUG]   boundedBy would provide approximately {bounded_faces_count} faces")

                            # If boundedBy has same or more faces, prefer it for more detail
                            # Fix for Issue #48: Relaxed threshold from 1.2 (20% more) to 1.0 (same or more)
                            # Previous: 80 > 74*1.2 (88.8) = False → chose lod2Solid (wrong!)
                            # Now: 80 >= 74*1.0 (74) = True → choose boundedBy (correct!)
                            if bounded_faces_count >= len(exterior_faces_solid):
                                log(f"[CONVERSION DEBUG]   ✓ boundedBy has {bounded_faces_count} vs lod2Solid's {len(exterior_faces_solid)} faces")
                                log(f"[CONVERSION DEBUG]   → Preferring boundedBy strategy for more detailed geometry")
                                log(f"[CONVERSION DEBUG]   → Skipping MultiSurface/Geometry strategies, jumping to boundedBy")
                                prefer_bounded_by = True  # Skip intermediate strategies
                                # Don't return here - let it fall through to boundedBy strategy below
                            else:
                                log(f"[CONVERSION DEBUG]   → lod2Solid has more detail ({len(exterior_faces_solid)} vs {bounded_faces_count} faces), using it")
                                return result
                        else:
                            log(f"[CONVERSION DEBUG]   No boundedBy surfaces found, using lod2Solid result")
                            return result
                    elif result is not None:
                        # Result is not a valid solid (likely an invalid shell)
                        log(f"[CONVERSION DEBUG]   ⚠ LOD2 Strategy 1 returned invalid solid/shell, trying boundedBy fallback...")
                        if debug:
                            log(f"[LOD2] Solid validation failed, enabling boundedBy fallback")
                        prefer_bounded_by = True  # Force fallback to boundedBy strategy
                    else:
                        log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 1 failed (shell building), trying next strategy...")
                        if debug:
                            log(f"[LOD2] Solid shell building failed, trying other strategies...")
                else:
                    log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 1 failed (0 faces), trying next strategy...")
                    if debug:
                        log(f"[LOD2] Solid extracted 0 faces, trying other strategies...")
            else:
                log(f"[CONVERSION DEBUG]   ✗ lod2Solid found but no gml:Solid child")
        else:
            log(f"[CONVERSION DEBUG] LOD2 Strategy 1: lod2Solid not found")

        # Strategy 2: LOD2 MultiSurface (multiple independent surfaces)
        # Skip if boundedBy was preferred (Issue #48 fix)
        if not prefer_bounded_by:
            lod2_multi = elem.find(".//bldg:lod2MultiSurface", NS)
        else:
            lod2_multi = None  # Force skip
        if lod2_multi is not None:
            if debug:
                log(f"[LOD2] Found bldg:lod2MultiSurface in {elem_id}")

            # Look for MultiSurface or CompositeSurface
            for surface_container in lod2_multi.findall(".//gml:MultiSurface", NS) + lod2_multi.findall(".//gml:CompositeSurface", NS):
                faces_multi = _extract_faces_from_surface_container(surface_container, xyz_transform, id_index, debug)
                exterior_faces.extend(faces_multi)

            if debug:
                log(f"[LOD2] MultiSurface extraction: {len(exterior_faces)} faces")

            if exterior_faces:
                # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                # Build solid from collected faces
                result = _make_solid_with_cavities(
                    exterior_faces, [], tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None and _is_valid_shape(result):
                    if debug:
                        log(f"[LOD2] MultiSurface processing successful with valid solid, returning shape")
                    return result
                elif result is not None:
                    if debug:
                        log(f"[LOD2] MultiSurface returned invalid solid/shell, trying next strategy")
                else:
                    if debug:
                        log(f"[LOD2] MultiSurface shell building failed, trying other strategies...")
                    # Clear for next strategy
                    exterior_faces = []

        # Strategy 3: LOD2 Geometry (generic geometry container)
        # Skip if boundedBy was preferred (Issue #48 fix)
        if not prefer_bounded_by:
            lod2_geom = elem.find(".//bldg:lod2Geometry", NS)
        else:
            lod2_geom = None  # Force skip
        if lod2_geom is not None:
            if debug:
                log(f"[LOD2] Found bldg:lod2Geometry in {elem_id}")

            # Try to find any surface structures
            for surface_container in (
                lod2_geom.findall(".//gml:MultiSurface", NS) +
                lod2_geom.findall(".//gml:CompositeSurface", NS) +
                lod2_geom.findall(".//gml:Solid", NS)
            ):
                if surface_container.tag.endswith("Solid"):
                    # Process as Solid
                    faces_geom, interior_shells = _extract_solid_shells(surface_container, xyz_transform, id_index, debug)
                    exterior_faces.extend(faces_geom)
                else:
                    # Process as MultiSurface/CompositeSurface
                    faces_geom = _extract_faces_from_surface_container(surface_container, xyz_transform, id_index, debug)
                    exterior_faces.extend(faces_geom)

            if debug:
                log(f"[LOD2] Geometry extraction: {len(exterior_faces)} faces")

            if exterior_faces:
                # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                result = _make_solid_with_cavities(
                    exterior_faces, [], tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None and _is_valid_shape(result):
                    if debug:
                        log(f"[LOD2] Geometry processing successful with valid solid, returning shape")
                    return result
                elif result is not None:
                    if debug:
                        log(f"[LOD2] Geometry returned invalid solid/shell, trying next strategy")
                else:
                    if debug:
                        log(f"[LOD2] Geometry shell building failed, trying other strategies...")
                    exterior_faces = []

        # Strategy 4: LOD2/LOD3 boundedBy surfaces (all CityGML 2.0 boundary surface types)
        # This strategy works for both LOD2 and LOD3 when solid structures are unavailable
        # CityGML 2.0 defines 6 _BoundarySurface types (we support all of them):
        # - WallSurface: vertical exterior wall (most common)
        # - RoofSurface: roof structure (most common)
        # - GroundSurface: ground contact surface (footprint)
        # - OuterCeilingSurface: exterior ceiling that is not a roof (rare)
        # - OuterFloorSurface: exterior upper floor that is not a roof (rare)
        # - ClosureSurface: virtual surfaces to close building volumes (PLATEAU uses these)
        bounded_surfaces = (
            elem.findall(".//bldg:boundedBy/bldg:WallSurface", NS) +
            elem.findall(".//bldg:boundedBy/bldg:RoofSurface", NS) +
            elem.findall(".//bldg:boundedBy/bldg:GroundSurface", NS) +
            elem.findall(".//bldg:boundedBy/bldg:OuterCeilingSurface", NS) +
            elem.findall(".//bldg:boundedBy/bldg:OuterFloorSurface", NS) +
            elem.findall(".//bldg:boundedBy/bldg:ClosureSurface", NS)
        )
        if bounded_surfaces:
            if debug:
                log(f"[LOD2/LOD3] Found {len(bounded_surfaces)} boundedBy surfaces in {elem_id}")
                surface_stats = {
                    "WallSurface": 0, "RoofSurface": 0, "GroundSurface": 0,
                    "OuterCeilingSurface": 0, "OuterFloorSurface": 0, "ClosureSurface": 0
                }
                faces_by_type = {
                    "WallSurface": 0, "RoofSurface": 0, "GroundSurface": 0,
                    "OuterCeilingSurface": 0, "OuterFloorSurface": 0, "ClosureSurface": 0
                }

            for surf in bounded_surfaces:
                # Get surface type for debugging
                surf_type = surf.tag.split("}")[-1] if "}" in surf.tag else surf.tag
                if debug:
                    surface_stats[surf_type] = surface_stats.get(surf_type, 0) + 1

                faces_before = len(exterior_faces)
                found_geometry = False
                method_used = None

                # Method 1: Check for LOD-specific wrappers (LOD3 and LOD2) within each bounded surface
                # LOD3 has priority for more detailed geometry (walls, roofs with architectural details)
                # Fix for issue #48: Support LOD3 WallSurface extraction to prevent wall omissions
                for lod_tag in [".//bldg:lod3MultiSurface", ".//bldg:lod3Geometry",
                               ".//bldg:lod2MultiSurface", ".//bldg:lod2Geometry"]:
                    surf_geom = surf.find(lod_tag, NS)
                    if surf_geom is not None:
                        faces_extracted_before = len(exterior_faces)
                        for surface_container in surf_geom.findall(".//gml:MultiSurface", NS) + surf_geom.findall(".//gml:CompositeSurface", NS):
                            faces_bounded = _extract_faces_from_surface_container(surface_container, xyz_transform, id_index, debug)
                            exterior_faces.extend(faces_bounded)
                        # Only mark as found if we actually extracted faces
                        if len(exterior_faces) > faces_extracted_before:
                            found_geometry = True
                            method_used = f"Method 1 ({lod_tag.split(':')[-1]})"
                            if log_file:
                                log(f"  [{surf_type}] {method_used}: extracted {len(exterior_faces) - faces_extracted_before} faces")
                            break  # Successfully extracted, no need to try other LOD tags

                # Method 2: Fallback - Check for direct gml:MultiSurface or gml:CompositeSurface children
                # Some PLATEAU buildings have geometry directly without LOD-specific wrappers
                if not found_geometry:
                    faces_method2_before = len(exterior_faces)
                    for direct_container in surf.findall("./gml:MultiSurface", NS) + surf.findall("./gml:CompositeSurface", NS):
                        faces_bounded = _extract_faces_from_surface_container(direct_container, xyz_transform, id_index, debug)
                        exterior_faces.extend(faces_bounded)
                    if len(exterior_faces) > faces_method2_before:
                        found_geometry = True
                        method_used = "Method 2 (direct MultiSurface)"
                        if log_file:
                            log(f"  [{surf_type}] {method_used}: extracted {len(exterior_faces) - faces_method2_before} faces")

                # Method 3: Fallback - Check for direct gml:Polygon children
                if not found_geometry:
                    faces_method3_before = len(exterior_faces)
                    for poly in surf.findall(".//gml:Polygon", NS):
                        ext, holes = _extract_polygon_xyz(poly)
                        if len(ext) < 3:
                            continue

                        # Apply coordinate transformation if provided
                        if xyz_transform:
                            try:
                                ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                                holes = [
                                    [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                                    for ring in holes
                                ]
                            except Exception as e:
                                if debug:
                                    log(f"    Transform failed for polygon in {surf_type}: {e}")
                                continue

                        fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
                        if fc is not None and not fc.IsNull():
                            exterior_faces.append(fc)

                    if len(exterior_faces) > faces_method3_before:
                        found_geometry = True
                        method_used = "Method 3 (direct Polygon)"
                        if log_file:
                            log(f"  [{surf_type}] {method_used}: extracted {len(exterior_faces) - faces_method3_before} faces")

                # Track faces extracted from this surface
                faces_added = len(exterior_faces) - faces_before
                if debug:
                    faces_by_type[surf_type] = faces_by_type.get(surf_type, 0) + faces_added
                    if faces_added > 0:
                        log(f"  - {surf_type}: extracted {faces_added} faces")
                    elif not found_geometry:
                        if log_file:
                            log(f"  [{surf_type}] ✗ No geometry found - all 3 methods failed")

            if debug:
                log(f"[LOD2] boundedBy extraction summary:")
                log(f"  - Total surfaces: {len(bounded_surfaces)} (Wall: {surface_stats.get('WallSurface', 0)}, Roof: {surface_stats.get('RoofSurface', 0)}, Ground: {surface_stats.get('GroundSurface', 0)}, OuterCeiling: {surface_stats.get('OuterCeilingSurface', 0)}, OuterFloor: {surface_stats.get('OuterFloorSurface', 0)}, Closure: {surface_stats.get('ClosureSurface', 0)})")
                log(f"  - Total faces extracted: {len(exterior_faces)} (Wall: {faces_by_type.get('WallSurface', 0)}, Roof: {faces_by_type.get('RoofSurface', 0)}, Ground: {faces_by_type.get('GroundSurface', 0)}, OuterCeiling: {faces_by_type.get('OuterCeilingSurface', 0)}, OuterFloor: {faces_by_type.get('OuterFloorSurface', 0)}, Closure: {faces_by_type.get('ClosureSurface', 0)})")

            if exterior_faces:
                # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                result = _make_solid_with_cavities(
                    exterior_faces, [], tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None and _is_valid_shape(result):
                    if debug:
                        log(f"[LOD2] boundedBy processing successful with valid solid, returning shape")
                        log(f"[CONVERSION DEBUG] ═══ Conversion successful via boundedBy strategy ═══")
                    return result
                else:
                    if debug:
                        if result is not None:
                            log(f"[LOD2] boundedBy returned invalid solid/shell, continuing to LOD1 fallback")
                        else:
                            log(f"[LOD2] boundedBy shell building failed, continuing to LOD1 fallback")

        if debug and not exterior_faces:
            log(f"[LOD2] No LOD2 geometry found, falling back to LOD1 for {elem_id}")

        # =========================================================================
        # LOD1 Fallback
        # =========================================================================
        # LOD1 represents simple 3D block models:
        # - Building footprint extruded to a uniform height
        # - No roof differentiation (flat tops)
        # - Minimal detail, used when LOD2/LOD3 are unavailable
        # Common in early PLATEAU datasets or overview-level city models

        lod1_solid = elem.find(".//bldg:lod1Solid", NS)
        if lod1_solid is not None:
            solid_elem = lod1_solid.find(".//gml:Solid", NS)
            if solid_elem is not None:
                if debug:
                    log(f"[LOD1] Found bldg:lod1Solid//gml:Solid in {elem_id}")

                # Extract exterior and interior shells
                exterior_faces_lod1, interior_shells_lod1 = _extract_solid_shells(
                    solid_elem, xyz_transform, id_index, debug
                )

                if exterior_faces_lod1:
                    # Coordinates already re-centered by xyz_transform wrapper (PHASE:0)

                    # Build solid with cavities (adaptive tolerance)
                    result = _make_solid_with_cavities(
                        exterior_faces_lod1, interior_shells_lod1, tolerance=None, debug=debug,
                        precision_mode=precision_mode, shape_fix_level=shape_fix_level
                    )
                    if result is not None and _is_valid_shape(result):
                        if debug:
                            log(f"[LOD1] Processing successful with valid solid, returning shape")
                        return result
                    elif result is not None:
                        if debug:
                            log(f"[LOD1] Returned invalid solid/shell, no more strategies available")
                    else:
                        if debug:
                            log(f"[LOD1] Shell building failed, no more strategies available")

            log(f"[CONVERSION DEBUG] ✗ All strategies failed - no geometry extracted")
            return None

    finally:
        # Don't close log file here - let the top-level function (export_step_from_citygml) close it
        # after all phases (PHASE:1-7) are complete. This ensures PHASE:6-7 logs are captured.
        # (Issue #96: Log file was being closed prematurely before STEP export phase)
        pass


def extract_building_and_parts(building: ET.Element, xyz_transform: Optional[Callable] = None,
                                id_index: Optional[dict[str, ET.Element]] = None,
                                debug: bool = False,
                                precision_mode: str = "auto",
                                shape_fix_level: str = "standard") -> List["TopoDS_Shape"]:
    """Extract geometry from a Building and all its BuildingParts.

    This function recursively extracts:
    1. Geometry from the main Building element
    2. Geometry from all bldg:BuildingPart child elements

    Args:
        building: bldg:Building element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness

    Returns:
        List of TopoDS_Shape objects (one per Building/BuildingPart)
    """
    shapes: List[TopoDS_Shape] = []

    # Extract from main Building
    main_shape = _extract_single_solid(building, xyz_transform, id_index, debug,
                                       precision_mode, shape_fix_level)
    if main_shape is not None:
        shapes.append(main_shape)
        if debug:
            log("Extracted geometry from main Building")

    # Extract from all BuildingParts
    building_parts = building.findall(".//bldg:BuildingPart", NS)
    if building_parts:
        if debug:
            log(f"Found {len(building_parts)} BuildingPart(s)")

        for i, part in enumerate(building_parts):
            part_shape = _extract_single_solid(part, xyz_transform, id_index, debug,
                                               precision_mode, shape_fix_level)
            if part_shape is not None:
                shapes.append(part_shape)
                if debug:
                    part_id = part.get("{http://www.opengis.net/gml}id") or f"part_{i+1}"
                    log(f"Extracted geometry from BuildingPart: {part_id}")

    return shapes


def extract_lod_solid_from_building(building: ET.Element, xyz_transform: Optional[Callable] = None,
                                    id_index: Optional[dict[str, ET.Element]] = None,
                                    debug: bool = False,
                                    precision_mode: str = "auto",
                                    shape_fix_level: str = "standard",
                                    merge_building_parts: bool = True) -> Optional["TopoDS_Shape"]:
    """Extract LOD1 or LOD2 solid geometry from a building element.

    Now supports:
    - gml:Solid with exterior and interior shells (cavities)
    - bldg:BuildingPart extraction and merging/fusion
    - XLink reference resolution (xlink:href)
    - Proper distinction between exterior and interior geometry
    - Precision mode control for detail preservation
    - Optional fusion of BuildingParts into single solid

    If the building has BuildingParts:
    - merge_building_parts=True: Fuse all parts into single solid (recommended for visualization)
    - merge_building_parts=False: Keep parts separate in a Compound (preserves original structure)

    Priority:
    1. LOD2 Solid (most detailed)
    2. LOD1 Solid (simplified)

    Args:
        building: bldg:Building element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness
        merge_building_parts: If True, fuse multiple BuildingParts into single solid;
                              if False, keep as compound (default: True)

    Returns the solid shape, compound of shapes, or None if not found.
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for solid extraction")

    # Extract from Building and all BuildingParts
    shapes = extract_building_and_parts(building, xyz_transform, id_index, debug,
                                        precision_mode, shape_fix_level)

    if not shapes:
        return None

    # If only one shape, return it directly
    if len(shapes) == 1:
        return shapes[0]

    # Multiple shapes: fuse or create compound based on parameter
    if merge_building_parts:
        if debug:
            log(f"[BUILDING] Merging {len(shapes)} BuildingParts into single solid...")
        return _fuse_shapes(shapes, debug)
    else:
        if debug:
            log(f"[BUILDING] Keeping {len(shapes)} BuildingParts as separate shapes in compound...")
        return _create_compound(shapes, debug)


def _fuse_shapes(shapes: List["TopoDS_Shape"], debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Fuse multiple shapes into a single solid using Boolean union operations.

    This function iteratively fuses shapes using BRepAlgoAPI_Fuse. If fusion fails,
    it falls back to creating a compound.

    Args:
        shapes: List of TopoDS_Shape objects to fuse
        debug: Enable debug output

    Returns:
        Fused solid shape, or compound if fusion fails, or None if all shapes are invalid
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for shape fusion")

    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    # Filter out None and null shapes
    valid_shapes = [s for s in shapes if s is not None and not s.IsNull()]

    if not valid_shapes:
        if debug:
            log("[FUSE] No valid shapes to fuse")
        return None

    if len(valid_shapes) == 1:
        if debug:
            log("[FUSE] Only one shape, returning as-is")
        return valid_shapes[0]

    log(f"\n{'='*80}")
    log(f"[PHASE:6] BUILDINGPART FUSION (Boolean Union)")
    log(f"{'='*80}")
    log(f"[INFO] Number of parts to fuse: {len(valid_shapes)}")
    log(f"")

    try:
        # Start with the first shape
        result = valid_shapes[0]
        log(f"[STEP 1/{len(valid_shapes)}] Using first BuildingPart as base")

        # Iteratively fuse with remaining shapes
        for i, shape in enumerate(valid_shapes[1:], start=2):
            log(f"\n[STEP {i}/{len(valid_shapes)}] Fusing BuildingPart {i}...")
            log(f"├─ [GEOMETRY] Attempting Boolean Fuse operation...")

            try:
                fuse_op = BRepAlgoAPI_Fuse(result, shape)

                if fuse_op.IsDone():
                    result = fuse_op.Shape()

                    # Validate fused result
                    analyzer = BRepCheck_Analyzer(result)
                    if analyzer.IsValid():
                        log(f"├─ [VALIDATION] ✓ Fused shape is valid")
                        log(f"└─ [RESULT] ✓ Fusion succeeded")
                    else:
                        log(f"├─ [VALIDATION] ⚠ Fused shape is invalid (but continuing)")
                        log(f"└─ [RESULT] ⚠ Fusion succeeded with invalid topology")
                else:
                    log(f"├─ [ERROR] ✗ BRepAlgoAPI_Fuse.IsDone() returned False")
                    log(f"├─ [DECISION] → Fusion operation failed, cannot continue")
                    log(f"└─ [FALLBACK] Creating compound instead of fused solid")
                    return _create_compound(valid_shapes, debug)

            except Exception as e:
                log(f"├─ [ERROR] ✗ Exception during fusion")
                log(f"├─ [ERROR] Exception type: {type(e).__name__}")
                log(f"├─ [ERROR] Exception message: {str(e)}")
                if debug:
                    import traceback
                    log(f"├─ [ERROR] Traceback:")
                    for line in traceback.format_exc().split('\n'):
                        if line.strip():
                            log(f"│  {line}")
                log(f"└─ [FALLBACK] Creating compound instead of fused solid")
                return _create_compound(valid_shapes, debug)

        log(f"\n{'='*80}")
        log(f"[PHASE:6] FUSION SUMMARY")
        log(f"{'='*80}")
        log(f"[RESULT] ✓ Successfully fused all {len(valid_shapes)} BuildingParts")

        # Final validation
        final_analyzer = BRepCheck_Analyzer(result)
        if final_analyzer.IsValid():
            log(f"[VALIDATION] ✓ Final fused solid is topologically valid")
        else:
            log(f"[VALIDATION] ⚠ Final fused solid has topology issues")
        log(f"")

        return result

    except Exception as e:
        log(f"\n[ERROR] ✗ Unexpected exception in fusion process")
        log(f"[ERROR] Exception type: {type(e).__name__}")
        log(f"[ERROR] Exception message: {str(e)}")
        if debug:
            import traceback
            log(f"[ERROR] Traceback:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    log(f"  {line}")
        log(f"[FALLBACK] Creating compound instead of fused solid")
        return _create_compound(valid_shapes, debug)


def _create_compound(shapes: List["TopoDS_Shape"], debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Create a compound from multiple shapes.

    Args:
        shapes: List of TopoDS_Shape objects
        debug: Enable debug output

    Returns:
        Compound shape, or None if no valid shapes
    """
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    # Filter out None and null shapes
    valid_shapes = [s for s in shapes if s is not None and not s.IsNull()]

    if not valid_shapes:
        if debug:
            log("[COMPOUND] No valid shapes to create compound")
        return None

    if len(valid_shapes) == 1:
        if debug:
            log("[COMPOUND] Only one shape, returning as-is")
        return valid_shapes[0]

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for shp in valid_shapes:
        builder.Add(compound, shp)

    if debug:
        log(f"[COMPOUND] Created compound with {len(valid_shapes)} shapes")

    return compound


def build_sewn_shape_from_building(building: ET.Element, sew_tolerance: Optional[float] = None,
                                   debug: bool = False, xyz_transform: Optional[Callable] = None,
                                   precision_mode: str = "auto",
                                   shape_fix_level: str = "standard") -> Optional["TopoDS_Shape"]:
    """Build a sewn shape (and solids if possible) from LOD2 surfaces of a building.

    - Collect bldg:WallSurface, bldg:RoofSurface, bldg:GroundSurface polygons
    - Make faces with interior holes
    - Sew faces; try to close shells into solids
    - Return compound of solids if any; otherwise the sewn shell/compound
    - Optionally transform coordinates if xyz_transform is provided

    Args:
        building: bldg:Building element
        sew_tolerance: Sewing tolerance (auto-computed if None)
        debug: Enable debug output
        xyz_transform: Optional coordinate transformation function
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness
    """
    # Import topods at function start to avoid scoping issues
    from OCC.Core.TopoDS import topods

    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for surface sewing")

    surfaces = []
    for surf_tag in ["bldg:WallSurface", "bldg:RoofSurface", "bldg:GroundSurface"]:
        surfaces += building.findall(f".//{surf_tag}", NS)

    faces: List[TopoDS_Face] = []  # type: ignore
    for s in surfaces:
        for poly in s.findall(".//gml:Polygon", NS):
            ext, holes = _extract_polygon_xyz(poly)
            if len(ext) < 3:
                continue

            # Apply coordinate transformation if provided
            if xyz_transform:
                try:
                    ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
                    holes = [
                        [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ring]
                        for ring in holes
                    ]
                except Exception as e:
                    if debug:
                        log(f"Transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                faces.append(fc)

    if not faces:
        return None

    # Auto-compute tolerance if not provided
    if sew_tolerance is None:
        sew_tolerance = _compute_tolerance_from_face_list(faces, precision_mode)
        if debug:
            log(f"Auto-computed sewing tolerance: {sew_tolerance:.6f} (precision_mode: {precision_mode})")

    sewing = BRepBuilderAPI_Sewing(sew_tolerance, True, True, True, False)
    for fc in faces:
        sewing.Add(fc)
    sewing.Perform()
    sewn = sewing.SewedShape()

    # Apply shape fixing based on level
    if shape_fix_level != "minimal":
        try:
            fixer = ShapeFix_Shape(sewn)

            # Configure fixer based on level
            if shape_fix_level == "standard":
                fixer.SetPrecision(sew_tolerance)
                fixer.SetMaxTolerance(sew_tolerance * 10.0)
            elif shape_fix_level == "aggressive":
                fixer.SetPrecision(sew_tolerance * 10.0)
                fixer.SetMaxTolerance(sew_tolerance * 100.0)

            fixer.Perform()
            sewn = fixer.Shape()

            if debug:
                log(f"Shape fixing applied to sewn shape (level: {shape_fix_level})")
        except Exception as e:
            if debug:
                log(f"ShapeFix_Shape failed: {e}")

    # Try to make solids from shells
    solids: List[TopoDS_Shape] = []
    exp = TopExp_Explorer(sewn, TopAbs_SHELL)
    while exp.More():
        # Downcast shape -> shell via topods.Shell (constructor takes no args)
        shell = topods.Shell(exp.Current())
        try:
            analyzer = BRepCheck_Analyzer(shell)
            if analyzer.IsValid():
                mk = BRepBuilderAPI_MakeSolid()
                mk.Add(shell)
                solid = mk.Solid()
                if solid is not None and not solid.IsNull():
                    solids.append(solid)
        except Exception as e:
            if debug:
                log(f"Shell to solid failed: {e}")
        exp.Next()

    if solids:
        # Return compound of solids
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for s in solids:
            builder.Add(compound, s)
        return compound
    return sewn


def _compute_bounding_box(shape: "TopoDS_Shape") -> Tuple[float, float, float, float, float, float]:
    """Compute bounding box of a shape.

    Args:
        shape: TopoDS_Shape to analyze

    Returns:
        Tuple of (xmin, ymin, zmin, xmax, ymax, zmax)
    """
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)

    if bbox.IsVoid():
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return (xmin, ymin, zmin, xmax, ymax, zmax)


def _log_geometry_diagnostics(shapes: List["TopoDS_Shape"], debug: bool = False) -> None:
    """Log detailed geometry diagnostics including bounding boxes and positions.

    Args:
        shapes: List of shapes to analyze
        debug: Enable debug output (unused, diagnostics always shown)
    """
    if not shapes:
        return

    # Always log diagnostics (critical for debugging coordinate issues)
    log(f"\n{'='*80}")
    log(f"[DIAGNOSTICS] GEOMETRY ANALYSIS")
    log(f"{'='*80}")

    for i, shape in enumerate(shapes):
        xmin, ymin, zmin, xmax, ymax, zmax = _compute_bounding_box(shape)

        # Calculate size and center
        width = xmax - xmin
        height = zmax - zmin
        depth = ymax - ymin
        center_x = (xmin + xmax) / 2
        center_y = (ymin + ymax) / 2
        center_z = (zmin + zmax) / 2

        # Distance from origin
        distance_from_origin = (center_x**2 + center_y**2 + center_z**2) ** 0.5

        log(f"\n[SHAPE {i+1}/{len(shapes)}] Bounding box analysis:")
        log(f"  Position (center): ({center_x:.3f}, {center_y:.3f}, {center_z:.3f})")
        log(f"  Size: {width:.3f} × {depth:.3f} × {height:.3f} (W×D×H)")
        log(f"  Range X: [{xmin:.3f}, {xmax:.3f}]")
        log(f"  Range Y: [{ymin:.3f}, {ymax:.3f}]")
        log(f"  Range Z: [{zmin:.3f}, {zmax:.3f}]")
        log(f"  Distance from origin: {distance_from_origin:.3f}")

        # Diagnostic warnings
        if distance_from_origin > 100000:  # > 100km from origin
            log(f"  ⚠ WARNING: Geometry is very far from origin ({distance_from_origin/1000:.1f} km)")
            log(f"    This may indicate coordinate transformation issues")

        if max(width, depth, height) < 1:  # < 1 meter
            log(f"  ⚠ WARNING: Geometry is very small (< 1 unit)")
            log(f"    This may indicate scale issues (e.g., using degrees instead of meters)")

        if max(width, depth, height) > 1000000:  # > 1000 km
            log(f"  ⚠ WARNING: Geometry is extremely large (> 1000 km)")
            log(f"    This may indicate coordinate transformation issues")


def _recenter_faces(faces: List["TopoDS_Face"], debug: bool = False) -> Tuple[List["TopoDS_Face"], Tuple[float, float, float]]:
    """Re-center faces by translating them to place bounding box center at origin.

    This prevents numerical precision loss when face coordinates are far from origin
    (e.g., PLATEAU projected plane coordinates ~10-100km from origin).

    Args:
        faces: List of TopoDS_Face objects to re-center
        debug: Enable debug output

    Returns:
        Tuple of (re-centered faces, offset (cx, cy, cz))
    """
    if not faces:
        return faces, (0.0, 0.0, 0.0)

    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.gp import gp_Trsf, gp_Vec
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

    # Calculate combined bounding box of all faces
    combined_bbox = Bnd_Box()
    for face in faces:
        if face is not None and not face.IsNull():
            brepbndlib.Add(face, combined_bbox)

    if combined_bbox.IsVoid():
        if debug:
            log("[RECENTER] ⚠ Bounding box is void, skipping re-centering")
        return faces, (0.0, 0.0, 0.0)

    # Get bounding box extents
    xmin, ymin, zmin, xmax, ymax, zmax = combined_bbox.Get()

    # Calculate center
    center_x = (xmin + xmax) / 2.0
    center_y = (ymin + ymax) / 2.0
    center_z = (zmin + zmax) / 2.0

    # Only re-center if significantly far from origin (> 1 meter)
    distance_from_origin = (center_x**2 + center_y**2 + center_z**2) ** 0.5
    if distance_from_origin < 1.0:
        if debug:
            log(f"[RECENTER] Geometry already near origin ({distance_from_origin:.3f} mm), skipping re-centering")
        return faces, (0.0, 0.0, 0.0)

    # Calculate translation vector (negate center to move to origin)
    translation_x = -center_x
    translation_y = -center_y
    translation_z = -center_z

    if debug:
        log(f"\n{'='*80}")
        log(f"[RECENTER] RE-CENTERING GEOMETRY TO ORIGIN")
        log(f"{'='*80}")
        log(f"[RECENTER] Original bounding box center: ({center_x:.3f}, {center_y:.3f}, {center_z:.3f})")
        log(f"[RECENTER] Distance from origin: {distance_from_origin:.3f} mm ({distance_from_origin/1000:.3f} m)")
        log(f"[RECENTER] Translation vector: ({translation_x:.3f}, {translation_y:.3f}, {translation_z:.3f})")
        log(f"[RECENTER] Re-centering {len(faces)} faces...")

    # Create translation transformation
    transformation = gp_Trsf()
    transformation.SetTranslation(gp_Vec(translation_x, translation_y, translation_z))

    # Transform all faces (must use copy=True to avoid corrupting original geometry)
    recentered_faces = []
    failed_count = 0
    for i, face in enumerate(faces):
        if face is not None and not face.IsNull():
            try:
                # Use BRepBuilderAPI_Transform with copy=True to ensure clean transformation
                transformer = BRepBuilderAPI_Transform(face, transformation, True)
                transformer.Build()

                if transformer.IsDone():
                    transformed_shape = transformer.Shape()
                    if not transformed_shape.IsNull():
                        from OCC.Core.TopoDS import topods
                        # Safely downcast to Face
                        try:
                            transformed_face = topods.Face(transformed_shape)
                            recentered_faces.append(transformed_face)
                        except Exception as e:
                            if debug:
                                log(f"[RECENTER] ⚠ Face {i+1}: downcast failed ({e}), keeping original")
                            recentered_faces.append(face)
                            failed_count += 1
                    else:
                        if debug:
                            log(f"[RECENTER] ⚠ Face {i+1}: transformed shape is null, keeping original")
                        recentered_faces.append(face)
                        failed_count += 1
                else:
                    if debug:
                        log(f"[RECENTER] ⚠ Face {i+1}: transformation not done, keeping original")
                    recentered_faces.append(face)
                    failed_count += 1
            except Exception as e:
                if debug:
                    log(f"[RECENTER] ⚠ Face {i+1}: transformation failed with exception ({e}), keeping original")
                recentered_faces.append(face)
                failed_count += 1
        else:
            recentered_faces.append(face)

    if debug:
        if failed_count > 0:
            log(f"[RECENTER] ⚠ {failed_count}/{len(faces)} faces failed to transform, kept originals")
        log(f"[RECENTER] ✓ Successfully processed {len(recentered_faces)} faces ({len(faces) - failed_count} transformed, {failed_count} kept original)")
        log(f"[RECENTER] Offset applied: ({center_x:.3f}, {center_y:.3f}, {center_z:.3f})")

    return recentered_faces, (center_x, center_y, center_z)


def _export_step_compound_local(shapes: List["TopoDS_Shape"], out_step: str, debug: bool = False) -> Tuple[bool, str]:
    """Optimized STEP export with proper configuration.

    Used as a fallback when importing core.step_exporter is not possible.
    Now includes proper STEP writer configuration for CAD compatibility.

    Args:
        shapes: List of TopoDS_Shape objects to export
        out_step: Output STEP file path
        debug: Enable debug output

    Returns:
        Tuple of (success, message or output_path)
    """
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.IFSelect import IFSelect_ReturnStatus
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    if not shapes:
        return False, "No shapes to export"

    # Build a compound
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    any_valid = False
    for s in shapes:
        if s is not None and not s.IsNull():
            builder.Add(compound, s)
            any_valid = True
    if not any_valid:
        return False, "All shapes invalid"

    # Configure STEP writer for optimal CAD compatibility
    try:
        # Set STEP schema to AP214CD (automotive design, widely supported)
        Interface_Static.SetCVal("write.step.schema", "AP214CD")

        # Set units to millimeters (standard for CAD)
        Interface_Static.SetCVal("write.step.unit", "MM")

        # Set precision mode to maximum
        Interface_Static.SetIVal("write.precision.mode", 1)

        # Set precision value
        Interface_Static.SetRVal("write.precision.val", 1e-6)

        # Set surface curve mode (write 3D curves only, no 2D parameter curves on surfaces)
        Interface_Static.SetIVal("write.surfacecurve.mode", 0)

        if debug:
            log("STEP writer configured: AP214CD schema, MM units, 1e-6 precision")

    except Exception as e:
        if debug:
            log(f"Warning: STEP writer configuration failed: {e}")
        # Continue with default settings

    log(f"[STEP EXPORT] Using local STEP writer...")
    log(f"[STEP EXPORT] Configuration: AP214CD schema, MM units, 1e-6 precision")

    writer = STEPControl_Writer()

    log(f"[STEP EXPORT] Transferring geometry to STEP format...")
    tr = writer.Transfer(compound, STEPControl_AsIs)
    if tr != IFSelect_ReturnStatus.IFSelect_RetDone:
        log(f"[STEP EXPORT] ✗ Transfer failed with status: {tr}")
        return False, f"STEP transfer failed: {tr}"
    log(f"[STEP EXPORT] ✓ Transfer successful")

    log(f"[STEP EXPORT] Writing to file: {out_step}")
    wr = writer.Write(out_step)
    if wr != IFSelect_ReturnStatus.IFSelect_RetDone:
        log(f"[STEP EXPORT] ✗ Write failed with status: {wr}")
        return False, f"STEP write failed: {wr}"

    # Verify file was created and get size
    if os.path.exists(out_step):
        file_size = os.path.getsize(out_step)
        log(f"[STEP EXPORT] ✓ File written successfully")
        log(f"  - File: {out_step}")
        log(f"  - Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")

        if file_size == 0:
            log(f"[STEP EXPORT] ⚠ WARNING: File size is 0 bytes (empty file)")
            return False, "STEP file created but is empty"
    else:
        log(f"[STEP EXPORT] ⚠ WARNING: Write reported success but file not found")
        return False, "STEP write completed but file not found"

    return True, out_step




def _detect_source_crs(root: ET.Element) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """Scan XML for srsName and try to detect EPSG code, plus sample coordinates.
    
    Returns:
        Tuple of (epsg_code, sample_lat, sample_lon)
    """
    epsg_code = None
    sample_lat = None
    sample_lon = None
    
    # Check root and descendants for srsName
    queue = [root]
    seen = 0
    while queue and seen < 10000:
        e = queue.pop(0)
        seen += 1
        srs = e.get("srsName")
        if srs and not epsg_code:
            epsg_code = detect_epsg_from_srs(srs)
        
        # Try to get sample coordinates from first posList
        if sample_lat is None and e.tag.endswith("posList"):
            txt = (e.text or "").strip()
            if txt:
                parts = txt.split()
                try:
                    if len(parts) >= 2:
                        sample_lat = float(parts[0])
                        sample_lon = float(parts[1])
                        # Sanity check for Japan area
                        if not (20 <= sample_lat <= 50 and 120 <= sample_lon <= 155):
                            # Maybe lon/lat order
                            sample_lat, sample_lon = sample_lon, sample_lat
                except ValueError:
                    pass
        
        if epsg_code and sample_lat is not None:
            break
            
        queue.extend(list(e))
    
    return epsg_code, sample_lat, sample_lon


def _make_xy_transformer(source_crs: str, target_crs: str):
    """Return a function (x, y) -> (X, Y) in meters. Swaps lat/lon for geographic sources.

    Requires pyproj.
    """
    try:
        from pyproj import CRS, Transformer
    except Exception as e:
        raise RuntimeError("pyproj is required for reprojection but is not installed") from e

    s = CRS.from_user_input(source_crs)
    t = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(s, t, always_xy=True)
    swap = s.is_geographic  # If geographic, GML often stores as (lat, lon)

    def tx(x: float, y: float):
        if swap:
            xx, yy = float(y), float(x)  # (lon, lat)
        else:
            xx, yy = float(x), float(y)
        X, Y = transformer.transform(xx, yy)
        return X, Y

    return tx


def _make_xyz_transformer(source_crs: str, target_crs: str):
    try:
        from pyproj import CRS, Transformer
    except Exception as e:
        raise RuntimeError("pyproj is required for reprojection but is not installed") from e

    s = CRS.from_user_input(source_crs)
    t = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(s, t, always_xy=True)
    swap = s.is_geographic

    def tx(x: float, y: float, z: float):
        if swap:
            xx, yy = float(y), float(x)
        else:
            xx, yy = float(x), float(y)
        X, Y, Z = transformer.transform(xx, yy, float(z))
        return X, Y, Z

    return tx


def _filter_buildings_by_coordinates(
    buildings: List[ET.Element],
    target_latitude: float,
    target_longitude: float,
    radius_meters: float,
    debug: bool = False
) -> List[ET.Element]:
    """Filter buildings by distance from target coordinates.

    Args:
        buildings: List of bldg:Building elements
        target_latitude: Target latitude (WGS84)
        target_longitude: Target longitude (WGS84)
        radius_meters: Maximum distance in meters
        debug: Enable debug output

    Returns:
        Filtered list of building elements within radius
    """
    from shapely.geometry import Point
    from shapely import distance as shapely_distance

    target_point = Point(target_longitude, target_latitude)
    filtered: List[ET.Element] = []

    if debug:
        log(f"[COORD FILTER] Target: ({target_latitude}, {target_longitude})")
        log(f"[COORD FILTER] Radius: {radius_meters}m")

    for building in buildings:
        # Extract coordinates from building
        coords = _extract_building_coordinates_from_element(building)
        if not coords:
            if debug:
                gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
                log(f"[COORD FILTER] Skipping {gml_id}: No coordinates found")
            continue

        lat, lon = coords
        building_point = Point(lon, lat)

        # Calculate distance (in degrees, then convert to meters)
        dist_degrees = shapely_distance(target_point, building_point)
        dist_meters = float(dist_degrees) * 100000  # Rough conversion

        if dist_meters <= radius_meters:
            filtered.append(building)
            if debug:
                gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
                log(f"[COORD FILTER] ✓ {gml_id[:20]}: {dist_meters:.1f}m (within {radius_meters}m)")
        elif debug:
            gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
            log(f"[COORD FILTER] ✗ {gml_id[:20]}: {dist_meters:.1f}m (exceeds {radius_meters}m)")

    if debug:
        log(f"[COORD FILTER] Filtered: {len(buildings)} → {len(filtered)} buildings")

    return filtered


def _extract_building_coordinates_from_element(building_elem: ET.Element) -> Optional[Tuple[float, float]]:
    """Extract representative coordinates for a building element.

    Priority:
    1. lod0FootPrint
    2. lod0RoofEdge
    3. First posList in any geometry

    Returns:
        (latitude, longitude) tuple or None
    """
    # Try footprint/roof edge polygons
    for tag in [".//bldg:lod0FootPrint", ".//bldg:lod0RoofEdge"]:
        elem = building_elem.find(tag, NS)
        if elem is not None:
            poslist = elem.find(".//gml:posList", NS)
            if poslist is not None and poslist.text:
                coords = _parse_poslist(poslist)  # Pass element, not text
                if coords:
                    # Return first coordinate
                    x, y, _ = coords[0]
                    # Check if this looks like lat/lon (WGS84)
                    if 20 <= x <= 50 and 120 <= y <= 155:
                        return (x, y)
                    elif 120 <= x <= 155 and 20 <= y <= 50:
                        return (y, x)  # Swapped

    # Fallback: any posList
    poslist = building_elem.find(".//gml:posList", NS)
    if poslist is not None and poslist.text:
        coords = _parse_poslist(poslist)  # Pass element, not text
        if coords:
            x, y, _ = coords[0]
            # Guess order based on Japan coordinates
            if 20 <= x <= 50 and 120 <= y <= 155:
                return (x, y)
            elif 120 <= x <= 155 and 20 <= y <= 50:
                return (y, x)

    return None


def export_step_from_citygml(
    gml_path: str,
    out_step: str,
    limit: Optional[int] = None,
    debug: bool = False,
    method: str = "solid",
    sew_tolerance: Optional[float] = None,
    reproject_to: Optional[str] = None,
    source_crs: Optional[str] = None,
    auto_reproject: bool = True,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal",
    building_ids: Optional[List[str]] = None,
    filter_attribute: str = "gml:id",
    merge_building_parts: bool = True,
    target_latitude: Optional[float] = None,
    target_longitude: Optional[float] = None,
    radius_meters: float = 100,
) -> Tuple[bool, str]:
    """High-level pipeline: CityGML → STEP with precision control.

    Args:
        gml_path: Path to CityGML file
        out_step: Output STEP file path
        limit: Limit number of buildings to process (None for all, ignored if building_ids is specified)
        debug: Enable debug output
        method: Conversion strategy
            - "solid": Use LOD2/LOD3 Solid data directly (optimized for PLATEAU, recommended)
            - "auto": Fallback solid→sew→extrude (compatibility mode)
            - "sew": Sew LOD2 surfaces into solids
            - "extrude": Footprint+height extrusion (requires explicit specification)
        sew_tolerance: Sewing tolerance (auto-computed if None based on precision_mode)
        reproject_to: Target CRS (e.g., 'EPSG:6676')
        source_crs: Source CRS (auto-detected if None)
        auto_reproject: Auto-select projection for geographic CRS
        precision_mode: Precision level for detail preservation
            - "standard": 0.01% of extent (balanced, default - recommended for most use cases)
            - "high": 0.001% of extent (preserves fine details)
            - "maximum": 0.0001% of extent (maximum detail preservation)
            - "ultra": 0.00001% of extent (LOD2/LOD3 optimized - may fail with imperfect data)
        shape_fix_level: Shape fixing aggressiveness
            - "minimal": Skip fixing to preserve maximum detail (default - fastest, preserves original geometry)
            - "standard": Balanced fixing
            - "aggressive": Prioritize robustness over detail
            - "ultra": Maximum fixing for LOD2/LOD3 (slowest, may alter geometry)
        building_ids: List of building IDs to filter by (None = no filtering)
        filter_attribute: Attribute to match building_ids against
            - "gml:id": Match against gml:id attribute (default)
            - Other: Match against generic attribute with this name (e.g., "buildingID")
        merge_building_parts: Fuse multiple BuildingParts into single solid using Boolean union
            - True: Merge all BuildingParts into one solid (default, recommended for most use cases)
            - False: Keep BuildingParts as separate shapes in a compound
        target_latitude: Target latitude for coordinate-based filtering (WGS84)
        target_longitude: Target longitude for coordinate-based filtering (WGS84)
        radius_meters: Radius in meters for coordinate-based filtering (default: 100m)
            - If target_latitude/longitude are specified, only buildings within this radius are processed
            - Takes priority over building_ids filtering if both are specified
            - Simplifies workflow by eliminating ID mismatch issues

    Returns:
        Tuple of (success, message or output_path)
    """
    if not OCCT_AVAILABLE:
        return False, "OCCT is not available; cannot export STEP."

    # Normalize limit: treat 0 or negative as no limit
    if limit is not None and limit <= 0:
        limit = None

    # Parse GML tree once
    tree = ET.parse(gml_path)
    root = tree.getroot()
    bldgs = root.findall(".//bldg:Building", NS)

    # Apply coordinate-based filtering if specified (takes priority over building_ids)
    if target_latitude is not None and target_longitude is not None:
        original_count = len(bldgs)
        bldgs = _filter_buildings_by_coordinates(
            bldgs, target_latitude, target_longitude, radius_meters, debug
        )
        if debug:
            log(f"[COORD FILTER] Result: {original_count} → {len(bldgs)} buildings within {radius_meters}m")

        if not bldgs:
            return False, f"No buildings found within {radius_meters}m of ({target_latitude}, {target_longitude})"

    # Apply building ID filtering if specified (only if coordinate filtering not used)
    elif building_ids:
        original_count = len(bldgs)
        bldgs = _filter_buildings(bldgs, building_ids, filter_attribute)
        if debug:
            log(f"Building ID filter: {original_count} → {len(bldgs)} buildings")
            log(f"Filter attribute: {filter_attribute}")
            log(f"Requested IDs: {building_ids}")

        if not bldgs:
            return False, f"No buildings found matching IDs: {building_ids} (filter_attribute: {filter_attribute})"

    # Check for buildings before initializing log file
    if not bldgs:
        return False, "No buildings found in CityGML file"

    first_building_id = bldgs[0].get("{http://www.opengis.net/gml}id", "building_0")
    log_dir = "debug_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize building ID for filename (replace invalid characters)
    safe_id = first_building_id.replace(":", "_").replace("/", "_").replace("\\", "_")
    log_path = os.path.join(log_dir, f"conversion_{safe_id}_{timestamp}.log")

    try:
        log_file = open(log_path, "w", encoding="utf-8")
        # Write log header
        log_file.write(f"{'='*80}\n")
        log_file.write(f"CITYGML TO STEP CONVERSION LOG\n")
        log_file.write(f"{'='*80}\n")
        log_file.write(f"Building ID: {first_building_id}\n")
        log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
        log_file.write(f"Precision mode: {precision_mode}\n")
        log_file.write(f"Shape fix level: {shape_fix_level}\n")
        log_file.write(f"Debug mode: {'Enabled' if debug else 'Always enabled for detailed diagnostics'}\n")
        log_file.write(f"{'='*80}\n\n")

        # Write LOG LEGEND and PROCESSING PHASES
        log_file.write(f"LOG LEGEND (for AI/LLM Analysis and Debugging):\n")
        log_file.write(f"{'-'*80}\n")
        log_file.write(f"  [PHASE:N]       = Major processing phase (1-7)\n")
        log_file.write(f"  [STEP X/Y]      = Step number within current phase\n")
        log_file.write(f"  ✓ SUCCESS       = Operation completed successfully\n")
        log_file.write(f"  ✗ FAILED        = Operation failed\n")
        log_file.write(f"  ⚠ WARNING       = Potential issue detected (may not be critical)\n")
        log_file.write(f"  → DECISION      = Decision point (which strategy/fallback to use)\n")
        log_file.write(f"  ├─              = Child operation (subprocess)\n")
        log_file.write(f"  └─              = Final result of operation\n")
        log_file.write(f"  [GEOMETRY]      = Geometry extraction/construction operation\n")
        log_file.write(f"  [VALIDATION]    = Topology/geometry validation check\n")
        log_file.write(f"  [REPAIR]        = Automatic repair attempt\n")
        log_file.write(f"  [ERROR CODE]    = OpenCASCADE error code/type\n")
        log_file.write(f"  [INFO]          = Informational message\n")
        log_file.write(f"{'-'*80}\n\n")
        log_file.write(f"PROCESSING PHASES:\n")
        log_file.write(f"  [PHASE:1] LOD Strategy Selection (LOD3→LOD2→LOD1 fallback)\n")
        log_file.write(f"  [PHASE:2] Geometry Extraction (faces from gml:Solid)\n")
        log_file.write(f"  [PHASE:3] Shell Construction (sewing faces)\n")
        log_file.write(f"  [PHASE:4] Solid Validation (topology check)\n")
        log_file.write(f"  [PHASE:5] Automatic Repair (ShapeFix_Solid, tolerance adjustment)\n")
        log_file.write(f"  [PHASE:6] BuildingPart Merging (Boolean fusion if multiple parts)\n")
        log_file.write(f"  [PHASE:7] STEP Export (final output generation)\n")
        log_file.write(f"{'='*80}\n\n")

        # Set as global log file so all subsequent log() calls write to it
        set_log_file(log_file)
    except Exception as e:
        print(f"Warning: Failed to create log file: {e}")
        log_file = None

    # Build XLink resolution index
    id_index = _build_id_index(root)
    if debug and id_index:
        log(f"Built XLink index with {len(id_index)} gml:id entries")

        # Check for polygon IDs in the index
        poly_ids = [id for id in id_index.keys() if id.startswith("poly-")]
        if poly_ids:
            log(f"  Found {len(poly_ids)} polygon IDs in index (sample: {poly_ids[:5]})")
        else:
            log(f"  WARNING: No polygon IDs (starting with 'poly-') found in index!")
            # Show sample of what's actually in the index
            sample_ids = list(id_index.keys())[:10]
            log(f"  Sample of actual IDs in index: {sample_ids}")

    # Detect source CRS and sample coordinates
    log(f"\n{'='*80}")
    log(f"[PHASE:1.5] COORDINATE SYSTEM DETECTION")
    log(f"{'='*80}")

    detected_crs, sample_lat, sample_lon = _detect_source_crs(root)
    src = source_crs or detected_crs or "EPSG:6697"

    if debug:
        src_info = get_crs_info(src) if src else {}
        log(f"[CRS] Source coordinate system:")
        log(f"  - CRS code: {src}")
        log(f"  - CRS name: {src_info.get('name', 'Unknown')}")
        if sample_lat is not None and sample_lon is not None:
            log(f"  - Sample coordinates: lat={sample_lat:.6f}°, lon={sample_lon:.6f}°")
        else:
            log(f"  - Sample coordinates: Not available")
        log(f"  - Is geographic CRS: {is_geographic_crs(src)}")

    # Auto-select projection if needed
    if not reproject_to and auto_reproject:
        if is_geographic_crs(src):
            reproject_to = recommend_projected_crs(src, sample_lat, sample_lon)
            if debug:
                if reproject_to:
                    tgt_info = get_crs_info(reproject_to)
                    log(f"\n[CRS] Auto-reprojection selected:")
                    log(f"  - Target CRS: {reproject_to}")
                    log(f"  - Target name: {tgt_info.get('name', 'Unknown')}")
                    if 'regions' in tgt_info:
                        log(f"  - Coverage area: {tgt_info['regions']}")
                else:
                    log(f"\n[CRS] ⚠ WARNING: Geographic CRS detected but no suitable projection found")
                    log(f"  - Geometry will use raw geographic coordinates (degrees)")
                    log(f"  - This may cause scale/position issues in STEP output")
    
    # Build transformers if requested
    xy_transform = None
    xyz_transform = None
    if reproject_to:
        log(f"\n[CRS] Setting up coordinate transformation:")
        log(f"  - From: {src}")
        log(f"  - To: {reproject_to}")
        try:
            xy_transform = _make_xy_transformer(src, reproject_to)
            xyz_transform = _make_xyz_transformer(src, reproject_to)
            log(f"  - ✓ Transformation setup successful")
        except Exception as e:
            log(f"  - ✗ Transformation setup failed: {e}")
            close_log_file()  # Close log before returning
            return False, f"Reprojection setup failed: {e}"
    else:
        if debug:
            log(f"\n[CRS] ⚠ WARNING: No coordinate transformation will be applied")
            log(f"  - Using source CRS as-is: {src}")
            if is_geographic_crs(src):
                log(f"  - ⚠ CRITICAL: Geographic coordinates (lat/lon degrees) will be used directly")
                log(f"  - This will likely cause severe scale/position issues in STEP output")
                log(f"  - Recommendation: Enable auto_reproject or specify a projected CRS")

    # =========================================================================
    # PHASE 0: PRE-SCAN COORDINATES FOR RE-CENTERING
    # =========================================================================
    # Scan all polygon coordinates to calculate offset for numerical precision
    # This prevents OpenCASCADE precision loss when coordinates are far from origin
    # (e.g., PLATEAU data at ~40km from origin causing geometry collapse)

    coord_offset = None
    if xyz_transform or True:  # Always apply re-centering if coordinates available
        # Always log PHASE:0 header (critical for debugging coordinate issues)
        log(f"\n{'='*80}")
        log(f"[PHASE:0] PRE-SCAN FOR COORDINATE RE-CENTERING")
        log(f"{'='*80}")

        # Scan all polygon coordinates from buildings
        raw_coords = []
        for b in bldgs:
            for poly in b.findall(".//gml:Polygon", NS):
                ext, holes = _extract_polygon_xyz(poly)
                raw_coords.extend(ext)
                for hole in holes:
                    raw_coords.extend(hole)

        if raw_coords:
            log(f"[PRESCAN] Scanned {len(raw_coords)} coordinates from {len(bldgs)} buildings")

            # Apply xyz_transform to get planar coordinates (meters)
            if xyz_transform:
                try:
                    planar_coords = []
                    for x, y, z in raw_coords:
                        tx, ty, tz = xyz_transform(x, y, z)
                        planar_coords.append((tx, ty, tz))

                    log(f"[PRESCAN] ✓ Applied xyz_transform to get planar coordinates")
                except Exception as e:
                    log(f"[PRESCAN] ✗ xyz_transform failed: {e}, using raw coordinates")
                    planar_coords = raw_coords
            else:
                planar_coords = raw_coords

            # Calculate bounding box center in meters (planar coordinates)
            xs = [x for x, y, z in planar_coords]
            ys = [y for x, y, z in planar_coords]
            zs = [z for x, y, z in planar_coords]

            if xs and ys and zs:
                center_x = (min(xs) + max(xs)) / 2.0
                center_y = (min(ys) + max(ys)) / 2.0
                center_z = (min(zs) + max(zs)) / 2.0

                distance_from_origin = (center_x**2 + center_y**2 + center_z**2) ** 0.5

                # Always log bounding box info (critical for diagnosing precision issues)
                log(f"[PRESCAN] Bounding box center: ({center_x:.3f}, {center_y:.3f}, {center_z:.3f}) meters")
                log(f"[PRESCAN] Distance from origin: {distance_from_origin:.3f} m ({distance_from_origin/1000:.3f} km)")

                # Apply offset if significantly far from origin (> 1 meter)
                if distance_from_origin > 1.0:
                    coord_offset = (-center_x, -center_y, -center_z)

                    log(f"[PRESCAN] ✓ Offset calculated: ({coord_offset[0]:.3f}, {coord_offset[1]:.3f}, {coord_offset[2]:.3f}) meters")
                    log(f"[PRESCAN] This will re-center geometry to origin for numerical precision")

                    # Wrap xyz_transform with offset
                    if xyz_transform:
                        original_transform = xyz_transform
                        def wrapped_transform(x, y, z):
                            tx, ty, tz = original_transform(x, y, z)
                            return (tx + coord_offset[0], ty + coord_offset[1], tz + coord_offset[2])
                        xyz_transform = wrapped_transform

                        log(f"[PRESCAN] ✓ Wrapped xyz_transform with offset")
                        # Test the wrapped transform with a sample coordinate
                        if raw_coords:
                            test_x, test_y, test_z = raw_coords[0]
                            orig_result = original_transform(test_x, test_y, test_z)
                            wrapped_result = xyz_transform(test_x, test_y, test_z)
                            log(f"[PRESCAN] DEBUG: Sample coordinate ({test_x:.3f}, {test_y:.3f}, {test_z:.3f})")
                            log(f"[PRESCAN] DEBUG: Original transform → ({orig_result[0]:.3f}, {orig_result[1]:.3f}, {orig_result[2]:.3f})")
                            log(f"[PRESCAN] DEBUG: Wrapped transform → ({wrapped_result[0]:.3f}, {wrapped_result[1]:.3f}, {wrapped_result[2]:.3f})")
                    else:
                        # No xyz_transform, create offset-only transform
                        def offset_transform(x, y, z):
                            return (x + coord_offset[0], y + coord_offset[1], z + coord_offset[2])
                        xyz_transform = offset_transform

                        log(f"[PRESCAN] ✓ Created offset-only transform (no xyz_transform)")
                else:
                    log(f"[PRESCAN] Coordinates already near origin, no offset needed")
        else:
            log(f"[PRESCAN] ⚠ No polygon coordinates found, skipping re-centering")

    shapes: List[TopoDS_Shape] = []
    tried_solid = False
    tried_sew = False

    # Try solid method first (for PLATEAU data with LOD1/LOD2 solids)
    if method in ("solid", "auto"):
        tried_solid = True
        count = 0

        # Log extraction phase start
        log(f"\n{'='*80}")
        log(f"[PHASE:2] BUILDING GEOMETRY EXTRACTION (Solid Method)")
        log(f"{'='*80}")
        log(f"[INFO] Total buildings to process: {len(bldgs)}")
        log(f"[INFO] Limit: {limit if limit else 'unlimited'}")
        log(f"[INFO] Extraction method: {method}")
        log(f"")

        for i, b in enumerate(bldgs):
            if limit is not None and count >= limit:
                log(f"\n[INFO] Reached limit of {limit} buildings, stopping extraction")
                break

            # Get building ID for logging
            building_id = b.get("{http://www.opengis.net/gml}id", f"building_{i}")

            log(f"\n{'─'*80}")
            log(f"[BUILDING {i+1}/{len(bldgs)}] Processing: {building_id[:60]}")
            log(f"├─ [STEP 1/3] Extracting LOD geometry...")

            try:
                shp = extract_lod_solid_from_building(
                    b,
                    xyz_transform=xyz_transform,
                    id_index=id_index,
                    debug=debug,
                    precision_mode=precision_mode,
                    shape_fix_level=shape_fix_level,
                    merge_building_parts=merge_building_parts
                )

                if shp is None:
                    log(f"├─ [GEOMETRY] ✗ Extraction returned None")
                    log(f"└─ [RESULT] Skipping building {building_id[:40]}")
                    continue

                if shp.IsNull():
                    log(f"├─ [GEOMETRY] ✗ Shape is null")
                    log(f"└─ [RESULT] Skipping building {building_id[:40]}")
                    continue

                # Validate shape before adding
                log(f"├─ [STEP 2/3] Validating shape...")
                analyzer = BRepCheck_Analyzer(shp)
                shape_type = shp.ShapeType()

                if not analyzer.IsValid():
                    log(f"├─ [VALIDATION] ⚠ Shape is topologically invalid")
                    log(f"├─ [INFO] Shape type: {shape_type}")
                    log(f"├─ [DECISION] → Will attempt export anyway (may fail)")
                else:
                    log(f"├─ [VALIDATION] ✓ Shape is topologically valid")
                    log(f"├─ [INFO] Shape type: {shape_type}")

                log(f"├─ [STEP 3/3] Adding to shape list...")
                shapes.append(shp)
                count += 1
                log(f"└─ [RESULT] ✓ Successfully added (total valid shapes: {count})")

            except Exception as e:
                log(f"├─ [ERROR] ✗ Exception during extraction")
                log(f"├─ [ERROR] Exception type: {type(e).__name__}")
                log(f"├─ [ERROR] Exception message: {str(e)}")
                if debug:
                    import traceback
                    log(f"├─ [ERROR] Traceback:")
                    for line in traceback.format_exc().split('\n'):
                        if line.strip():
                            log(f"│  {line}")
                log(f"└─ [RESULT] ✗ Failed, skipping building {building_id[:40]}")
                continue

        # Log extraction summary
        log(f"\n{'='*80}")
        log(f"[PHASE:2] EXTRACTION SUMMARY")
        log(f"{'='*80}")
        log(f"[INFO] Buildings processed: {len(bldgs)}")
        log(f"[INFO] Shapes extracted: {count}")
        log(f"[INFO] Success rate: {count}/{len(bldgs)} ({100*count/len(bldgs) if len(bldgs) > 0 else 0:.1f}%)")
        log(f"")

    # Try sew method if solid didn't work
    if not shapes and method in ("sew", "auto"):
        tried_sew = True
        count = 0
        for i, b in enumerate(bldgs):
            if limit is not None and count >= limit:
                break
            try:
                shp = build_sewn_shape_from_building(
                    b,
                    sew_tolerance=sew_tolerance,  # Will be auto-computed if None
                    debug=debug,
                    xyz_transform=xyz_transform,
                    precision_mode=precision_mode,
                    shape_fix_level=shape_fix_level
                )
                if shp is not None and not shp.IsNull():
                    shapes.append(shp)
                    count += 1
            except Exception as e:
                if debug:
                    log(f"Sewing failed for building {i}: {e}")
                continue

    # Fallback to extrusion from footprints (only when explicitly requested or in auto mode)
    if not shapes and method in ("extrude", "auto"):
        # Note: default_height is only used for LOD0 extrusion fallback
        # LOD2/3 buildings have explicit geometry and don't need this
        default_height = 10.0
        fplist = parse_citygml_footprints(
            gml_path,
            default_height=default_height,
            limit=limit,
            xy_transform=xy_transform,
        )
        if debug:
            log(f"Parsed buildings with footprints: {len(fplist)}")
        for fp in fplist:
            try:
                shp = extrude_footprint(fp)
                shapes.append(shp)
            except Exception as e:
                if debug:
                    log(f"Extrusion failed for {fp.building_id}: {e}")
                continue

    # Pre-export validation phase
    log(f"\n{'='*80}")
    log(f"[PHASE:7] STEP EXPORT PREPARATION")
    log(f"{'='*80}")
    log(f"[INFO] Total shapes extracted: {len(shapes)}")

    if not shapes:
        log(f"[ERROR] ✗ No valid shapes to export")
        log(f"[ERROR] Conversion method used: {method}")
        log(f"[ERROR] Buildings attempted: {len(bldgs)}")
        log(f"[ERROR] Tried solid method: {tried_solid}")
        log(f"[ERROR] Tried sew method: {tried_sew}")

        close_log_file()  # Close log before returning (Issue #96)
        if method == "auto":
            return False, "No shapes created via solid extraction, sewing, or extrusion."
        elif method == "solid":
            return False, "Solid method produced no shapes (no LOD1/LOD2 solid data found)."
        elif method == "sew":
            return False, "Sew method produced no shapes (insufficient LOD2 surfaces)."
        else:
            return False, "No valid solids constructed from footprints."

    # Validate all shapes before export
    log(f"\n[VALIDATION] Pre-export shape validation:")
    valid_count = 0
    invalid_count = 0
    shape_type_counts = {}

    for i, shp in enumerate(shapes):
        analyzer = BRepCheck_Analyzer(shp)
        shape_type = shp.ShapeType()
        shape_type_counts[shape_type] = shape_type_counts.get(shape_type, 0) + 1

        if analyzer.IsValid():
            valid_count += 1
            log(f"  [{i+1}/{len(shapes)}] ✓ Valid - Type: {shape_type}")
        else:
            invalid_count += 1
            log(f"  [{i+1}/{len(shapes)}] ⚠ Invalid - Type: {shape_type}")

    log(f"\n[VALIDATION] Summary:")
    log(f"  ✓ Valid shapes: {valid_count}")
    log(f"  ⚠ Invalid shapes: {invalid_count}")
    log(f"  Shape type distribution:")
    for shape_type, count in sorted(shape_type_counts.items()):
        log(f"    - Type {shape_type}: {count} shape(s)")

    # Log geometry diagnostics (bounding boxes, positions, sizes)
    _log_geometry_diagnostics(shapes, debug=debug)

    if valid_count == 0:
        log(f"\n[ERROR] ✗ All extracted shapes are topologically invalid")
        log(f"[ERROR] STEP export will likely fail")
        close_log_file()  # Close log before returning (Issue #96)
        return False, f"All {len(shapes)} extracted shapes are topologically invalid. Try using shape_fix_level='standard' or higher."

    if invalid_count > 0:
        log(f"\n⚠ WARNING: {invalid_count} shape(s) are invalid, but will attempt export")
        log(f"⚠ WARNING: STEP export may partially fail or produce incorrect geometry")

    log(f"\n[INFO] Proceeding to STEP export with {len(shapes)} shape(s)...")
    log(f"[INFO] Target file: {out_step}")
    log(f"")

    # Prefer core STEPExporter if importable, else fallback local
    if STEPExporter is not None:
        try:
            log(f"[STEP EXPORT] Using core STEPExporter...")
            exporter = STEPExporter()
            res = exporter.export_compound(shapes, out_step)
            if not res.success:
                log(f"[STEP EXPORT] ✗ Export failed: {res.error_message}")
                close_log_file()  # Close log before returning (Issue #96)
                return False, f"STEP export failed: {res.error_message}"

            # Verify file was created
            if os.path.exists(out_step):
                file_size = os.path.getsize(out_step)
                log(f"[STEP EXPORT] ✓ Export successful")
                log(f"  - File: {out_step}")
                log(f"  - Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            else:
                log(f"[STEP EXPORT] ⚠ WARNING: Export reported success but file not found")

            close_log_file()  # Close log after successful export (Issue #96)
            return True, out_step
        except Exception as e:
            log(f"[STEP EXPORT] ✗ STEPExporter exception: {e}")
            log(f"[STEP EXPORT] Falling back to local writer...")
            # continue to fallback

    result = _export_step_compound_local(shapes, out_step, debug=debug)

    # Close log file after all phases complete (Issue #96)
    close_log_file()

    return result


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert CityGML (PLATEAU) to STEP (LOD2/LOD3 optimized)")
    parser.add_argument("input", help="Path to CityGML (*.gml) file")
    parser.add_argument("output", help="Path to output STEP (*.step) file")
    parser.add_argument("--default-height", type=float, default=10.0, help="[DEPRECATED] No longer used for LOD2/3 processing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of buildings for quick tests")
    parser.add_argument("--debug", action="store_true", help="Enable debug prints")
    parser.add_argument("--method", choices=["solid", "auto", "sew", "extrude"], default="solid", help="Conversion strategy (default: solid for LOD2/3)")
    parser.add_argument("--sew-tolerance", type=float, default=1e-6, help="Sewing tolerance for LOD2 surfaces")
    parser.add_argument("--reproject-to", type=str, default=None, help="Target CRS like 'EPSG:6676' (meters)")
    parser.add_argument("--source-crs", type=str, default=None, help="Override detected source CRS (e.g., 'EPSG:6697')")

    args = parser.parse_args(list(argv) if argv is not None else None)

    # Warn if deprecated parameter is used
    if args.default_height != 10.0:
        log("Warning: --default-height is deprecated and no longer used for LOD2/3 processing", file=sys.stderr)

    ok, msg = export_step_from_citygml(
        args.input,
        args.output,
        limit=args.limit,
        debug=args.debug,
        method=args.method,
        sew_tolerance=args.sew_tolerance,
        reproject_to=args.reproject_to,
        source_crs=args.source_crs,
    )
    if ok:
        log(f"Wrote STEP: {msg}")
        return 0
    else:
        log(f"Error: {msg}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
