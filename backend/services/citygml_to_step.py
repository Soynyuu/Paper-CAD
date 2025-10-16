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
    from OCC.Core.ShapeFix import ShapeFix_Shape

try:
    # Local exporter is optional; we avoid importing FastAPI-dependent config
    from core.step_exporter import STEPExporter  # type: ignore
except Exception:
    STEPExporter = None  # fallback to local writer


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
        print(f"      [XLink] Failed to resolve: {href}")
        print(f"      [XLink] Looking for ID: '{target_id}'")
        # Check for similar IDs
        similar_ids = [id for id in id_index.keys() if target_id in id or id in target_id]
        if similar_ids:
            print(f"      [XLink] Similar IDs found: {similar_ids[:3]}")
        else:
            print(f"      [XLink] No similar IDs found in index")

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
    poly = BRepBuilderAPI_MakePolygon()
    # Ensure closed polygon; avoid duplicate closing point
    if coords and coords[0] == coords[-1]:
        pts = coords[:-1]
    else:
        pts = coords
    for x, y in pts:
        poly.Add(gp_Pnt(float(x), float(y), 0.0))
    poly.Close()
    return poly.Wire()


def _wire_from_coords_xyz(coords: List[Tuple[float, float, float]], debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Create a wire from 3D coordinates.

    Args:
        coords: List of (x, y, z) tuples
        debug: Enable debug output

    Returns:
        TopoDS_Wire or None if creation fails
    """
    try:
        poly = BRepBuilderAPI_MakePolygon()
        if coords and coords[0] == coords[-1]:
            pts = coords[:-1]
        else:
            pts = coords

        if len(pts) < 2:
            if debug:
                print(f"Wire creation failed: insufficient points ({len(pts)} < 2)")
            return None

        for x, y, z in pts:
            poly.Add(gp_Pnt(float(x), float(y), float(z)))
        poly.Close()

        if not poly.IsDone():
            if debug:
                print(f"Wire creation failed: BRepBuilderAPI_MakePolygon.IsDone() = False")
            return None

        return poly.Wire()
    except Exception as e:
        if debug:
            print(f"Wire creation failed with exception: {e}")
        return None


def extrude_footprint(fp: Footprint) -> "TopoDS_Shape":
    """Create a prism solid from a 2D footprint using OCCT."""
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for extrusion")

    outer = _wire_from_coords_xy(fp.exterior)
    face_maker = BRepBuilderAPI_MakeFace(outer, True)
    # Add interior holes if any
    for hole in fp.holes:
        if len(hole) >= 3:
            face_maker.Add(_wire_from_coords_xy(hole))
    face = face_maker.Face()

    vec = gp_Vec(0.0, 0.0, float(fp.height))
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
                print(f"Face creation failed: outer wire creation failed ({len(ext)} points)")
            return None

        # Create face with planar_check control
        # planar_check=False allows non-planar faces (important for LOD2 complex geometry)
        face_maker = BRepBuilderAPI_MakeFace(outer, planar_check)

        if not face_maker.IsDone():
            if debug:
                print(f"Face creation failed: BRepBuilderAPI_MakeFace.IsDone() = False (planar_check={planar_check})")
            return None

        # Add holes if any
        for i, hole in enumerate(holes):
            if len(hole) >= 3:
                hole_wire = _wire_from_coords_xyz(hole, debug=debug)
                if hole_wire is not None:
                    face_maker.Add(hole_wire)
                elif debug:
                    print(f"Skipping hole {i}: wire creation failed")

        face = face_maker.Face()
        if face is None or face.IsNull():
            if debug:
                print(f"Face creation failed: resulting face is null")
            return None

        return face
    except Exception as e:
        if debug:
            print(f"Face creation failed with exception: {e}")
        return None


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
                    print(f"Transform failed for polygon: {e}")
                continue

        fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
        if fc is not None and not fc.IsNull():
            faces.append(fc)
            stats["face_creation_success"] += 1
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
                    print(f"Transform failed for polygon: {e}")
                continue

        fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
        if fc is not None and not fc.IsNull():
            faces.append(fc)
            stats["face_creation_success"] += 1
        else:
            stats["face_creation_failed"] += 1

    # Print statistics in debug mode
    if debug:
        print(f"  Face extraction statistics:")
        print(f"    - surfaceMembers found: {stats['surfaceMember_count']}")
        print(f"    - Polygons found: {stats['polygon_found']}")
        print(f"    - Polygons too small (<3 vertices): {stats['polygon_too_small']}")
        print(f"    - Transform failures: {stats['transform_failed']}")
        print(f"    - Face creation successes: {stats['face_creation_success']}")
        print(f"    - Face creation failures: {stats['face_creation_failed']}")
        print(f"    - Total faces returned: {len(faces)}")

    return faces


def _extract_solid_shells(solid_elem: ET.Element, xyz_transform: Optional[Callable] = None,
                          id_index: Optional[dict[str, ET.Element]] = None,
                          debug: bool = False) -> Tuple[List["TopoDS_Face"], List[List["TopoDS_Face"]]]:
    """Extract exterior and interior shells from a gml:Solid element.

    Now supports XLink reference resolution for polygons.

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
        print(f"  [Solid] Extracting shells from gml:Solid element")

        # Dump XML structure to temp file for debugging
        try:
            import tempfile
            import os
            xml_str = ET.tostring(solid_elem, encoding="unicode")
            dump_path = os.path.join(tempfile.gettempdir(), "plateau_solid_debug.xml")
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"  [Solid] XML structure dumped to: {dump_path}")
        except Exception as e:
            print(f"  [Solid] Failed to dump XML: {e}")

    # Extract exterior shell polygons
    exterior_elem = solid_elem.find("./gml:exterior", NS)
    if debug:
        if exterior_elem is not None:
            print(f"  [Solid] Found gml:exterior element")
        else:
            print(f"  [Solid] WARNING: No gml:exterior element found!")
    if exterior_elem is not None:
        # Support multiple GML surface patterns - find all surfaceMember elements
        surf_members = exterior_elem.findall(".//gml:surfaceMember", NS)
        if debug:
            print(f"  [Solid] Found {len(surf_members)} gml:surfaceMember elements in exterior")

        for i, surf_member in enumerate(surf_members):
            # Check for XLink reference
            href = surf_member.get("{http://www.w3.org/1999/xlink}href")
            if debug and href:
                print(f"  [Solid]   surfaceMember[{i}]: XLink reference: {href}")

                # For first surfaceMember, check if it exists in index
                if i == 0 and href.startswith("#"):
                    target_id = href[1:]
                    exists = target_id in id_index
                    print(f"  [Solid]   surfaceMember[{i}]: Target ID '{target_id}' in index: {exists}")
                    if not exists:
                        # Show some similar IDs
                        similar = [k for k in id_index.keys() if k.startswith("poly-")][:5]
                        print(f"  [Solid]   surfaceMember[{i}]: Sample polygon IDs in index: {similar}")

            # Try to extract polygon (with XLink resolution)
            # Force debug=True for first surfaceMember to see detailed XLink resolution
            xlink_debug = debug and i == 0
            poly = _extract_polygon_with_xlink(surf_member, id_index, debug=xlink_debug) if id_index else surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                # Fallback: search directly
                poly = surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                if debug:
                    print(f"  [Solid]   surfaceMember[{i}]: No Polygon found (XLink may have failed)")
                continue

            if debug:
                print(f"  [Solid]   surfaceMember[{i}]: Polygon found")

            ext, holes = _extract_polygon_xyz(poly)
            if debug:
                print(f"  [Solid]   surfaceMember[{i}]: Extracted {len(ext)} vertices, {len(holes)} holes")

            if len(ext) < 3:
                if debug:
                    print(f"  [Solid]   surfaceMember[{i}]: Insufficient vertices ({len(ext)} < 3), skipping")
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
                        print(f"  [Solid]   surfaceMember[{i}]: Transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes, debug=False, planar_check=False)
            if fc is not None and not fc.IsNull():
                exterior_faces.append(fc)
                if debug:
                    print(f"  [Solid]   surfaceMember[{i}]: ✓ Face created successfully")
            else:
                if debug:
                    print(f"  [Solid]   surfaceMember[{i}]: ✗ Face creation failed")

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
                        print(f"Exterior transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                exterior_faces.append(fc)

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
                        print(f"Interior transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                interior_faces.append(fc)

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
                        print(f"Interior transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                interior_faces.append(fc)

        if interior_faces:
            interior_shells.append(interior_faces)
            if debug:
                print(f"Found interior shell with {len(interior_faces)} faces (cavity)")

    if debug:
        print(f"  [Solid] Extraction complete: {len(exterior_faces)} exterior faces, {len(interior_shells)} interior shells")

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
                        print(f"Reversed face {i} orientation")
                except Exception as e:
                    if debug:
                        print(f"Failed to reverse face {i}: {e}")
                    normalized.append(face)
            else:
                normalized.append(face)

        return normalized
    except Exception as e:
        if debug:
            print(f"Face orientation normalization failed: {e}")
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
                        print(f"Cleaned face {i}")
                else:
                    cleaned.append(face)
            except Exception as e:
                if debug:
                    print(f"Failed to clean face {i}: {e}")
                cleaned.append(face)

        return cleaned
    except Exception as e:
        if debug:
            print(f"Vertex deduplication failed: {e}")
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
            print("Face invalid, attempting multi-stage fix...")

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
                    print("Face fixed in stage 1")
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
                                print("Face fixed in stage 2 (wire rebuild)")
                            return rebuilt
            except Exception as e:
                if debug:
                    print(f"Stage 2 wire fixing failed: {e}")

        # If all stages fail, return best attempt or None
        if fixed is not None and not fixed.IsNull():
            return fixed

        return None

    except Exception as e:
        if debug:
            print(f"Face validation/fixing failed: {e}")
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
        print(f"Building shell from {len(faces)} faces with tolerance {tolerance:.9f}")

    # Stage 1: Validate and fix each face individually
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            print("Stage 1: Validating and fixing individual faces...")

        validated_faces = []
        for i, face in enumerate(faces):
            fixed_face = _validate_and_fix_face(face, tolerance, debug)
            if fixed_face is not None:
                validated_faces.append(fixed_face)
            elif debug:
                print(f"Warning: Face {i} could not be fixed, skipping")

        if not validated_faces:
            if debug:
                print("Error: No valid faces after validation")
            return None

        faces = validated_faces
        if debug:
            print(f"Stage 1 complete: {len(faces)} valid faces")

    # Stage 2: Normalize face orientations
    if shape_fix_level in ("standard", "aggressive", "ultra"):
        if debug:
            print("Stage 2: Normalizing face orientations...")
        faces = _normalize_face_orientation(faces, debug)

    # Stage 3: Remove duplicate vertices
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            print("Stage 3: Removing duplicate vertices...")
        faces = _remove_duplicate_vertices(faces, tolerance, debug)

    # Stage 4: Multi-pass sewing for ultra mode
    if shape_fix_level == "ultra":
        if debug:
            print("Stage 4: Multi-pass sewing with progressively tighter tolerances...")

        # Try multiple sewing passes with different tolerances
        tolerances_to_try = [
            tolerance * 10.0,  # First pass: looser for connectivity
            tolerance * 5.0,   # Second pass: tighter
            tolerance,         # Final pass: target tolerance
        ]

        sewn_shape = None
        for i, tol in enumerate(tolerances_to_try):
            if debug:
                print(f"  Sewing pass {i+1} with tolerance {tol:.9f}")

            sewing = BRepBuilderAPI_Sewing(tol, True, True, True, False)
            for fc in faces:
                sewing.Add(fc)
            sewing.Perform()
            sewn_shape = sewing.SewedShape()

            # Check if sewing improved
            if sewn_shape is not None and not sewn_shape.IsNull():
                if debug:
                    print(f"  Pass {i+1} successful")
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
            print("Stage 4: Single-pass sewing...")

        sewing = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
        for fc in faces:
            sewing.Add(fc)
        sewing.Perform()
        sewn_shape = sewing.SewedShape()

    # Stage 5: Apply shape fixing based on level
    if shape_fix_level != "minimal":
        try:
            if debug:
                print(f"Stage 5: Applying shape fixing (level: {shape_fix_level})...")

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
                print(f"Shape fixing applied (level: {shape_fix_level})")
        except Exception as e:
            if debug:
                print(f"ShapeFix_Shape failed: {e}")

    # Stage 6: Extract and validate shell
    if debug:
        print("Stage 6: Extracting and validating shell...")

    exp = TopExp_Explorer(sewn_shape, TopAbs_SHELL)
    if exp.More():
        shell = topods.Shell(exp.Current())

        # Validate shell
        try:
            from OCC.Core.BRep import BRep_Tool
            analyzer = BRepCheck_Analyzer(shell)
            if not analyzer.IsValid():
                if debug:
                    print("Warning: Shell is not valid, attempting to fix...")

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
                                    print("Shell fixed successfully")
                                shell = fixed_shell
                            else:
                                if debug:
                                    print("Shell still invalid after fixing, using best attempt")
                    except Exception as e:
                        if debug:
                            print(f"ShapeFix_Shell failed: {e}")
                else:
                    # Standard shell fixing
                    try:
                        from OCC.Core.ShapeFix import ShapeFix_Shell
                        shell_fixer = ShapeFix_Shell(shell)
                        shell_fixer.Perform()
                        shell = shell_fixer.Shell()
                    except Exception as e:
                        if debug:
                            print(f"ShapeFix_Shell failed: {e}")
        except Exception as e:
            if debug:
                print(f"Shell validation failed: {e}")

        if debug:
            print("Shell construction complete")

        return shell

    if debug:
        print("Error: No shell found in sewn shape")

    return None


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
            print(f"Auto-computed tolerance: {tolerance:.6f} (precision_mode: {precision_mode})")

    # Build exterior shell
    if debug:
        print(f"Attempting to build exterior shell from {len(exterior_faces)} faces...")
    exterior_shell = _build_shell_from_faces(exterior_faces, tolerance, debug, shape_fix_level)
    if exterior_shell is None:
        if debug:
            print(f"ERROR: Failed to build exterior shell (sewing or shell extraction failed)")
        return None

    # Check if exterior shell is closed
    try:
        is_closed = BRep_Tool.IsClosed(exterior_shell)
        if not is_closed:
            if debug:
                print(f"WARNING: Exterior shell is not closed, returning shell instead of solid")
        else:
            if debug:
                print(f"Exterior shell is closed, will attempt to create solid")
    except Exception as e:
        if debug:
            print(f"Failed to check if shell is closed: {e}")
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
                        print(f"Added interior shell {i+1} (closed)")
                else:
                    if debug:
                        print(f"Interior shell {i+1} is not closed, skipping")
            except Exception as e:
                if debug:
                    print(f"Interior shell {i+1} check failed: {e}")

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
                        print(f"Failed to add interior shell: {e}")

            solid = mk_solid.Solid()

            # Validate solid
            analyzer = BRepCheck_Analyzer(solid)
            if analyzer.IsValid():
                if debug:
                    print(f"Created valid solid with {len(interior_shells)} cavities")
                return solid
            else:
                if debug:
                    print("Solid validation failed, returning shell")
                return exterior_shell
        except Exception as e:
            if debug:
                print(f"Solid creation failed: {e}, returning shell")
            return exterior_shell
    else:
        if debug:
            print("Exterior shell not closed, cannot create solid")
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

    # Always create log file for conversion tracking (not just in debug mode)
    log_file = None
    log_dir = os.path.join(os.path.dirname(__file__), "..", "debug_logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = elem_id.replace(":", "_").replace("/", "_")[:50]
    log_path = os.path.join(log_dir, f"conversion_{safe_id}_{timestamp}.log")
    try:
        log_file = open(log_path, "w", encoding="utf-8")
        log_file.write(f"CityGML to STEP Conversion Log\n")
        log_file.write(f"Building ID: {elem_id}\n")
        log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
        log_file.write(f"Precision mode: {precision_mode}\n")
        log_file.write(f"Shape fix level: {shape_fix_level}\n")
        log_file.write(f"Debug mode: Always enabled for detailed diagnostics\n")
        log_file.write(f"{'='*80}\n\n")
        print(f"[CONVERSION] Logging to: {log_path}")
    except Exception as e:
        print(f"[CONVERSION] Warning: Failed to create log file: {e}")
        log_file = None

    def log(message: str):
        """Helper function to log both to console and file"""
        print(message)
        if log_file:
            log_file.write(message + "\n")
            log_file.flush()

    # Log conversion start
    log(f"[CONVERSION DEBUG] ═══ Starting LOD extraction for building: {elem_id[:40]} ═══")
    log(f"[CONVERSION DEBUG] Precision mode: {precision_mode}, Shape fix level: {shape_fix_level}")

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
                # Build solid with cavities (adaptive tolerance)
                result = _make_solid_with_cavities(
                    exterior_faces_solid, interior_shells_faces, tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None:
                    log(f"[CONVERSION DEBUG]   ✓✓ LOD3 Strategy 1 SUCCEEDED - Returning detailed LOD3 model")
                    if debug:
                        log(f"[LOD3] Solid processing successful, returning shape")
                    if log_file:
                        log_file.close()
                    return result
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
            # Build solid from collected faces
            result = _make_solid_with_cavities(
                exterior_faces, [], tolerance=None, debug=debug,
                precision_mode=precision_mode, shape_fix_level=shape_fix_level
            )
            if result is not None:
                if debug:
                    log(f"[LOD3] MultiSurface processing successful, returning shape")
                if log_file:
                    log_file.close()
                return result
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
            result = _make_solid_with_cavities(
                exterior_faces, [], tolerance=None, debug=debug,
                precision_mode=precision_mode, shape_fix_level=shape_fix_level
            )
            if result is not None:
                if debug:
                    log(f"[LOD3] Geometry processing successful, returning shape")
                return result
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
                # Build solid with cavities (adaptive tolerance)
                result = _make_solid_with_cavities(
                    exterior_faces_solid, interior_shells_faces, tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None:
                    log(f"[CONVERSION DEBUG]   ✓ LOD2 Strategy 1 (lod2Solid) SUCCEEDED with {len(exterior_faces_solid)} faces")
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

                        # If boundedBy has significantly more faces (>20% more), prefer it for more detail
                        if bounded_faces_count > len(exterior_faces_solid) * 1.2:
                            log(f"[CONVERSION DEBUG]   ✓ boundedBy has {bounded_faces_count} vs lod2Solid's {len(exterior_faces_solid)} faces")
                            log(f"[CONVERSION DEBUG]   → Preferring boundedBy strategy for more detailed geometry")
                            # Don't return here - let it fall through to boundedBy strategy below
                        else:
                            log(f"[CONVERSION DEBUG]   → lod2Solid has sufficient detail ({len(exterior_faces_solid)} faces), using it")
                            if log_file:
                                log_file.close()
                            return result
                    else:
                        log(f"[CONVERSION DEBUG]   No boundedBy surfaces found, using lod2Solid result")
                        if log_file:
                            log_file.close()
                        return result
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
    lod2_multi = elem.find(".//bldg:lod2MultiSurface", NS)
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
            # Build solid from collected faces
            result = _make_solid_with_cavities(
                exterior_faces, [], tolerance=None, debug=debug,
                precision_mode=precision_mode, shape_fix_level=shape_fix_level
            )
            if result is not None:
                if debug:
                    log(f"[LOD2] MultiSurface processing successful, returning shape")
                return result
            else:
                if debug:
                    log(f"[LOD2] MultiSurface shell building failed, trying other strategies...")
                # Clear for next strategy
                exterior_faces = []

    # Strategy 3: LOD2 Geometry (generic geometry container)
    lod2_geom = elem.find(".//bldg:lod2Geometry", NS)
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
            result = _make_solid_with_cavities(
                exterior_faces, [], tolerance=None, debug=debug,
                precision_mode=precision_mode, shape_fix_level=shape_fix_level
            )
            if result is not None:
                if debug:
                    log(f"[LOD2] Geometry processing successful, returning shape")
                return result
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
            result = _make_solid_with_cavities(
                exterior_faces, [], tolerance=None, debug=debug,
                precision_mode=precision_mode, shape_fix_level=shape_fix_level
            )
            if result is not None:
                if debug:
                    log(f"[LOD2] boundedBy processing successful, returning shape")
                if log_file:
                    log(f"[CONVERSION DEBUG] ═══ Conversion successful via boundedBy strategy ═══")
                    log_file.close()
                return result
            else:
                if debug:
                    log(f"[LOD2] boundedBy shell building failed")

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
                # Build solid with cavities (adaptive tolerance)
                result = _make_solid_with_cavities(
                    exterior_faces_lod1, interior_shells_lod1, tolerance=None, debug=debug,
                    precision_mode=precision_mode, shape_fix_level=shape_fix_level
                )
                if result is not None:
                    if debug:
                        log(f"[LOD1] Processing successful, returning shape")
                    if log_file:
                        log_file.close()
                    return result

    if log_file:
        log(f"[CONVERSION DEBUG] ✗ All strategies failed - no geometry extracted")
        log_file.close()
    return None


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
            print("Extracted geometry from main Building")

    # Extract from all BuildingParts
    building_parts = building.findall(".//bldg:BuildingPart", NS)
    if building_parts:
        if debug:
            print(f"Found {len(building_parts)} BuildingPart(s)")

        for i, part in enumerate(building_parts):
            part_shape = _extract_single_solid(part, xyz_transform, id_index, debug,
                                               precision_mode, shape_fix_level)
            if part_shape is not None:
                shapes.append(part_shape)
                if debug:
                    part_id = part.get("{http://www.opengis.net/gml}id") or f"part_{i+1}"
                    print(f"Extracted geometry from BuildingPart: {part_id}")

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
            print(f"[BUILDING] Merging {len(shapes)} BuildingParts into single solid...")
        return _fuse_shapes(shapes, debug)
    else:
        if debug:
            print(f"[BUILDING] Keeping {len(shapes)} BuildingParts as separate shapes in compound...")
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
            print("[FUSE] No valid shapes to fuse")
        return None

    if len(valid_shapes) == 1:
        if debug:
            print("[FUSE] Only one shape, returning as-is")
        return valid_shapes[0]

    if debug:
        print(f"[FUSE] Attempting to fuse {len(valid_shapes)} shapes...")

    try:
        # Start with the first shape
        result = valid_shapes[0]

        # Iteratively fuse with remaining shapes
        for i, shape in enumerate(valid_shapes[1:], start=2):
            try:
                fuse_op = BRepAlgoAPI_Fuse(result, shape)
                if fuse_op.IsDone():
                    result = fuse_op.Shape()
                    if debug:
                        print(f"[FUSE] Successfully fused shape {i}/{len(valid_shapes)}")
                else:
                    if debug:
                        print(f"[FUSE] Fusion failed at shape {i}/{len(valid_shapes)}, falling back to compound")
                    # Fallback to compound
                    return _create_compound(valid_shapes, debug)
            except Exception as e:
                if debug:
                    print(f"[FUSE] Exception during fusion at shape {i}/{len(valid_shapes)}: {e}")
                # Fallback to compound
                return _create_compound(valid_shapes, debug)

        if debug:
            print(f"[FUSE] Successfully fused all {len(valid_shapes)} shapes into single solid")

        return result

    except Exception as e:
        if debug:
            print(f"[FUSE] Fusion failed with exception: {e}, falling back to compound")
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
            print("[COMPOUND] No valid shapes to create compound")
        return None

    if len(valid_shapes) == 1:
        if debug:
            print("[COMPOUND] Only one shape, returning as-is")
        return valid_shapes[0]

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for shp in valid_shapes:
        builder.Add(compound, shp)

    if debug:
        print(f"[COMPOUND] Created compound with {len(valid_shapes)} shapes")

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
                        print(f"Transform failed: {e}")
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
            print(f"Auto-computed sewing tolerance: {sew_tolerance:.6f} (precision_mode: {precision_mode})")

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
                print(f"Shape fixing applied to sewn shape (level: {shape_fix_level})")
        except Exception as e:
            if debug:
                print(f"ShapeFix_Shape failed: {e}")

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
                print(f"Shell to solid failed: {e}")
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
            print("STEP writer configured: AP214CD schema, MM units, 1e-6 precision")

    except Exception as e:
        if debug:
            print(f"Warning: STEP writer configuration failed: {e}")
        # Continue with default settings

    writer = STEPControl_Writer()
    tr = writer.Transfer(compound, STEPControl_AsIs)
    if tr != IFSelect_ReturnStatus.IFSelect_RetDone:
        return False, f"STEP transfer failed: {tr}"
    wr = writer.Write(out_step)
    if wr != IFSelect_ReturnStatus.IFSelect_RetDone:
        return False, f"STEP write failed: {wr}"

    if debug:
        print(f"STEP file written successfully: {out_step}")

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
        print(f"[COORD FILTER] Target: ({target_latitude}, {target_longitude})")
        print(f"[COORD FILTER] Radius: {radius_meters}m")

    for building in buildings:
        # Extract coordinates from building
        coords = _extract_building_coordinates_from_element(building)
        if not coords:
            if debug:
                gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
                print(f"[COORD FILTER] Skipping {gml_id}: No coordinates found")
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
                print(f"[COORD FILTER] ✓ {gml_id[:20]}: {dist_meters:.1f}m (within {radius_meters}m)")
        elif debug:
            gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
            print(f"[COORD FILTER] ✗ {gml_id[:20]}: {dist_meters:.1f}m (exceeds {radius_meters}m)")

    if debug:
        print(f"[COORD FILTER] Filtered: {len(buildings)} → {len(filtered)} buildings")

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
            print(f"[COORD FILTER] Result: {original_count} → {len(bldgs)} buildings within {radius_meters}m")

        if not bldgs:
            return False, f"No buildings found within {radius_meters}m of ({target_latitude}, {target_longitude})"

    # Apply building ID filtering if specified (only if coordinate filtering not used)
    elif building_ids:
        original_count = len(bldgs)
        bldgs = _filter_buildings(bldgs, building_ids, filter_attribute)
        if debug:
            print(f"Building ID filter: {original_count} → {len(bldgs)} buildings")
            print(f"Filter attribute: {filter_attribute}")
            print(f"Requested IDs: {building_ids}")

        if not bldgs:
            return False, f"No buildings found matching IDs: {building_ids} (filter_attribute: {filter_attribute})"

    # Build XLink resolution index
    id_index = _build_id_index(root)
    if debug and id_index:
        print(f"Built XLink index with {len(id_index)} gml:id entries")

        # Check for polygon IDs in the index
        poly_ids = [id for id in id_index.keys() if id.startswith("poly-")]
        if poly_ids:
            print(f"  Found {len(poly_ids)} polygon IDs in index (sample: {poly_ids[:5]})")
        else:
            print(f"  WARNING: No polygon IDs (starting with 'poly-') found in index!")
            # Show sample of what's actually in the index
            sample_ids = list(id_index.keys())[:10]
            print(f"  Sample of actual IDs in index: {sample_ids}")

    # Detect source CRS and sample coordinates
    detected_crs, sample_lat, sample_lon = _detect_source_crs(root)
    src = source_crs or detected_crs or "EPSG:6697"
    
    # Auto-select projection if needed
    if not reproject_to and auto_reproject:
        if is_geographic_crs(src):
            reproject_to = recommend_projected_crs(src, sample_lat, sample_lon)
            if debug and reproject_to:
                src_info = get_crs_info(src)
                tgt_info = get_crs_info(reproject_to)
                print(f"Auto-reprojection: Detected geographic CRS {src} ({src_info['name']})")
                print(f"  Sample coordinates: lat={sample_lat:.6f}, lon={sample_lon:.6f}" if sample_lat else "")
                print(f"  Auto-selected projection: {reproject_to} ({tgt_info['name']})")
                if 'regions' in tgt_info:
                    print(f"  Coverage area: {tgt_info['regions']}")
    
    # Build transformers if requested
    xy_transform = None
    xyz_transform = None
    if reproject_to:
        if debug:
            print(f"Reprojecting from {src} to {reproject_to}")
        try:
            xy_transform = _make_xy_transformer(src, reproject_to)
            xyz_transform = _make_xyz_transformer(src, reproject_to)
        except Exception as e:
            return False, f"Reprojection setup failed: {e}"

    shapes: List[TopoDS_Shape] = []
    tried_solid = False
    tried_sew = False

    # Try solid method first (for PLATEAU data with LOD1/LOD2 solids)
    if method in ("solid", "auto"):
        tried_solid = True
        count = 0
        for i, b in enumerate(bldgs):
            if limit is not None and count >= limit:
                break
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
                if shp is not None and not shp.IsNull():
                    shapes.append(shp)
                    count += 1
                    if debug:
                        print(f"Successfully extracted solid from building {i}")
            except Exception as e:
                if debug:
                    print(f"Solid extraction failed for building {i}: {e}")
                continue

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
                    print(f"Sewing failed for building {i}: {e}")
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
            print(f"Parsed buildings with footprints: {len(fplist)}")
        for fp in fplist:
            try:
                shp = extrude_footprint(fp)
                shapes.append(shp)
            except Exception as e:
                if debug:
                    print(f"Extrusion failed for {fp.building_id}: {e}")
                continue

    if not shapes:
        if method == "auto":
            return False, "No shapes created via solid extraction, sewing, or extrusion."
        elif method == "solid":
            return False, "Solid method produced no shapes (no LOD1/LOD2 solid data found)."
        elif method == "sew":
            return False, "Sew method produced no shapes (insufficient LOD2 surfaces)."
        else:
            return False, "No valid solids constructed from footprints."

    # Prefer core STEPExporter if importable, else fallback local
    if STEPExporter is not None:
        try:
            exporter = STEPExporter()
            res = exporter.export_compound(shapes, out_step)
            if not res.success:
                return False, f"STEP export failed: {res.error_message}"
            return True, out_step
        except Exception as e:
            if debug:
                print(f"STEPExporter failed, falling back to local writer: {e}")
            # continue to fallback

    return _export_step_compound_local(shapes, out_step, debug=debug)


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
        print("Warning: --default-height is deprecated and no longer used for LOD2/3 processing", file=sys.stderr)

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
        print(f"Wrote STEP: {msg}")
        return 0
    else:
        print(f"Error: {msg}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
