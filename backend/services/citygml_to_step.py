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
    "uro": "http://www.opengis.net/uro/1.0",
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


def _resolve_xlink(elem: ET.Element, id_index: dict[str, ET.Element]) -> Optional[ET.Element]:
    """Resolve an XLink reference (xlink:href) to the target element.

    Args:
        elem: Element that may contain an xlink:href attribute
        id_index: Index of gml:id -> element mappings

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
    return id_index.get(target_id)


def _extract_polygon_with_xlink(elem: ET.Element, id_index: dict[str, ET.Element]) -> Optional[ET.Element]:
    """Extract a gml:Polygon from an element, resolving XLink references if needed.

    Args:
        elem: Element that may contain a Polygon directly or via XLink
        id_index: Index for resolving XLink references

    Returns:
        gml:Polygon element or None
    """
    # Try to find Polygon directly
    poly = elem.find(".//gml:Polygon", NS)
    if poly is not None:
        return poly

    # Try to resolve XLink
    target = _resolve_xlink(elem, id_index)
    if target is not None:
        # Try to find Polygon in target
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


def _wire_from_coords_xyz(coords: List[Tuple[float, float, float]]) -> "TopoDS_Shape":
    poly = BRepBuilderAPI_MakePolygon()
    if coords and coords[0] == coords[-1]:
        pts = coords[:-1]
    else:
        pts = coords
    for x, y, z in pts:
        poly.Add(gp_Pnt(float(x), float(y), float(z)))
    poly.Close()
    return poly.Wire()


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


def _face_from_xyz_rings(ext: List[Tuple[float, float, float]], holes: List[List[Tuple[float, float, float]]]) -> Optional["TopoDS_Face"]:
    """Create a planar face from 3D polygon rings.

    Returns None if creation fails.
    """
    try:
        outer = _wire_from_coords_xyz(ext)
        face_maker = BRepBuilderAPI_MakeFace(outer, True)
        for hole in holes:
            if len(hole) >= 3:
                face_maker.Add(_wire_from_coords_xyz(hole))
        return face_maker.Face()
    except Exception:
        return None


def _compute_tolerance_from_coords(coords: List[Tuple[float, float, float]]) -> float:
    """Compute appropriate tolerance based on coordinate extent.

    The tolerance is set to approximately 0.1% of the bounding box extent.
    This ensures that tolerance scales appropriately with coordinate magnitude.

    Args:
        coords: List of (x, y, z) coordinate tuples

    Returns:
        Computed tolerance value (minimum 1e-6, maximum 10.0)
    """
    if not coords:
        return 0.01  # Default fallback

    # Compute bounding box
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]

    x_extent = max(xs) - min(xs) if xs else 0.0
    y_extent = max(ys) - min(ys) if ys else 0.0
    z_extent = max(zs) - min(zs) if zs else 0.0

    # Maximum extent across all dimensions
    extent = max(x_extent, y_extent, z_extent)

    # Tolerance as 0.1% of extent
    tolerance = extent * 0.001

    # Clamp to reasonable range
    tolerance = max(1e-6, min(tolerance, 10.0))

    return tolerance


def _compute_tolerance_from_face_list(faces: List["TopoDS_Face"]) -> float:
    """Compute tolerance from a list of faces by sampling their vertices.

    Args:
        faces: List of TopoDS_Face objects

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
        return _compute_tolerance_from_coords(coords)
    else:
        return 0.01  # Default fallback


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

    # Extract exterior shell polygons
    exterior_elem = solid_elem.find("./gml:exterior", NS)
    if exterior_elem is not None:
        # Support multiple GML surface patterns - find all surfaceMember elements
        for surf_member in exterior_elem.findall(".//gml:surfaceMember", NS):
            # Try to extract polygon (with XLink resolution)
            poly = _extract_polygon_with_xlink(surf_member, id_index) if id_index else surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                # Fallback: search directly
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
                        print(f"Exterior transform failed: {e}")
                    continue

            fc = _face_from_xyz_rings(ext, holes)
            if fc is not None and not fc.IsNull():
                exterior_faces.append(fc)

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

            fc = _face_from_xyz_rings(ext, holes)
            if fc is not None and not fc.IsNull():
                exterior_faces.append(fc)

    # Extract interior shells (cavities)
    for interior_elem in solid_elem.findall("./gml:interior", NS):
        interior_faces: List[TopoDS_Face] = []

        # Try surfaceMember pattern first
        for surf_member in interior_elem.findall(".//gml:surfaceMember", NS):
            poly = _extract_polygon_with_xlink(surf_member, id_index) if id_index else surf_member.find(".//gml:Polygon", NS)

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

            fc = _face_from_xyz_rings(ext, holes)
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

            fc = _face_from_xyz_rings(ext, holes)
            if fc is not None and not fc.IsNull():
                interior_faces.append(fc)

        if interior_faces:
            interior_shells.append(interior_faces)
            if debug:
                print(f"Found interior shell with {len(interior_faces)} faces (cavity)")

    return exterior_faces, interior_shells


def _build_shell_from_faces(faces: List["TopoDS_Face"], tolerance: float = 0.1,
                            debug: bool = False) -> Optional["TopoDS_Shell"]:
    """Build a shell from a list of faces using sewing and fixing.

    Args:
        faces: List of TopoDS_Face objects
        tolerance: Sewing tolerance
        debug: Enable debug output

    Returns:
        TopoDS_Shell or None if construction fails
    """
    if not faces:
        return None

    # Sew faces together
    sewing = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
    for fc in faces:
        sewing.Add(fc)
    sewing.Perform()
    sewn_shape = sewing.SewedShape()

    # Try to fix the shape
    try:
        fixer = ShapeFix_Shape(sewn_shape)
        fixer.Perform()
        sewn_shape = fixer.Shape()
    except Exception as e:
        if debug:
            print(f"ShapeFix_Shape failed: {e}")

    # Extract shell from sewn shape
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
                # Try to fix shell
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

        return shell

    return None


def _make_solid_with_cavities(exterior_faces: List["TopoDS_Face"],
                               interior_shells_faces: List[List["TopoDS_Face"]],
                               tolerance: Optional[float] = None,
                               debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Build a solid with cavities from exterior and interior shells.

    Args:
        exterior_faces: Faces forming the outer shell
        interior_shells_faces: List of face lists, each forming an interior shell (cavity)
        tolerance: Sewing tolerance (auto-computed if None)
        debug: Enable debug output

    Returns:
        TopoDS_Solid or TopoDS_Shape (if solid construction fails)
    """
    from OCC.Core.BRep import BRep_Tool

    # Auto-compute tolerance if not provided
    if tolerance is None:
        tolerance = _compute_tolerance_from_face_list(exterior_faces)
        if debug:
            print(f"Auto-computed tolerance: {tolerance:.6f}")

    # Build exterior shell
    exterior_shell = _build_shell_from_faces(exterior_faces, tolerance, debug)
    if exterior_shell is None:
        if debug:
            print("Failed to build exterior shell")
        return None

    # Check if exterior shell is closed
    try:
        is_closed = BRep_Tool.IsClosed(exterior_shell)
        if not is_closed:
            if debug:
                print("Warning: Exterior shell is not closed")
    except Exception as e:
        if debug:
            print(f"Failed to check if shell is closed: {e}")
        is_closed = False

    # Build interior shells
    interior_shells: List[TopoDS_Shell] = []
    for i, int_faces in enumerate(interior_shells_faces):
        int_shell = _build_shell_from_faces(int_faces, tolerance, debug)
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
                          debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Extract a single solid from a building or building part element.

    This is a helper function that extracts LOD1 or LOD2 solid from a single element.

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output

    Returns:
        TopoDS_Shape or None
    """
    # Try LOD2 solid first
    lod2_solid = elem.find(".//bldg:lod2Solid", NS)
    if lod2_solid is not None:
        solid_elem = lod2_solid.find(".//gml:Solid", NS)
        if solid_elem is not None:
            if debug:
                elem_id = elem.get("{http://www.opengis.net/gml}id") or "unknown"
                print(f"Found LOD2 Solid in {elem_id}")

            # Extract exterior and interior shells
            exterior_faces, interior_shells_faces = _extract_solid_shells(
                solid_elem, xyz_transform, id_index, debug
            )

            if exterior_faces:
                # Build solid with cavities (adaptive tolerance)
                result = _make_solid_with_cavities(
                    exterior_faces, interior_shells_faces, tolerance=None, debug=debug
                )
                if result is not None:
                    return result

    # Try LOD1 solid
    lod1_solid = elem.find(".//bldg:lod1Solid", NS)
    if lod1_solid is not None:
        solid_elem = lod1_solid.find(".//gml:Solid", NS)
        if solid_elem is not None:
            if debug:
                elem_id = elem.get("{http://www.opengis.net/gml}id") or "unknown"
                print(f"Found LOD1 Solid in {elem_id}")

            # Extract exterior and interior shells
            exterior_faces, interior_shells_faces = _extract_solid_shells(
                solid_elem, xyz_transform, id_index, debug
            )

            if exterior_faces:
                # Build solid with cavities (adaptive tolerance)
                result = _make_solid_with_cavities(
                    exterior_faces, interior_shells_faces, tolerance=None, debug=debug
                )
                if result is not None:
                    return result

    return None


def extract_building_and_parts(building: ET.Element, xyz_transform: Optional[Callable] = None,
                                id_index: Optional[dict[str, ET.Element]] = None,
                                debug: bool = False) -> List["TopoDS_Shape"]:
    """Extract geometry from a Building and all its BuildingParts.

    This function recursively extracts:
    1. Geometry from the main Building element
    2. Geometry from all bldg:BuildingPart child elements

    Args:
        building: bldg:Building element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output

    Returns:
        List of TopoDS_Shape objects (one per Building/BuildingPart)
    """
    shapes: List[TopoDS_Shape] = []

    # Extract from main Building
    main_shape = _extract_single_solid(building, xyz_transform, id_index, debug)
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
            part_shape = _extract_single_solid(part, xyz_transform, id_index, debug)
            if part_shape is not None:
                shapes.append(part_shape)
                if debug:
                    part_id = part.get("{http://www.opengis.net/gml}id") or f"part_{i+1}"
                    print(f"Extracted geometry from BuildingPart: {part_id}")

    return shapes


def extract_lod_solid_from_building(building: ET.Element, xyz_transform: Optional[Callable] = None,
                                    id_index: Optional[dict[str, ET.Element]] = None,
                                    debug: bool = False) -> Optional["TopoDS_Shape"]:
    """Extract LOD1 or LOD2 solid geometry from a building element.

    Now supports:
    - gml:Solid with exterior and interior shells (cavities)
    - bldg:BuildingPart extraction and merging
    - XLink reference resolution (xlink:href)
    - Proper distinction between exterior and interior geometry

    If the building has BuildingParts, all parts are extracted and merged into a Compound.

    Priority:
    1. LOD2 Solid (most detailed)
    2. LOD1 Solid (simplified)

    Returns the solid shape, compound of shapes, or None if not found.
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for solid extraction")

    # Extract from Building and all BuildingParts
    shapes = extract_building_and_parts(building, xyz_transform, id_index, debug)

    if not shapes:
        return None

    # If only one shape, return it directly
    if len(shapes) == 1:
        return shapes[0]

    # Multiple shapes: create a compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for shp in shapes:
        if shp is not None and not shp.IsNull():
            builder.Add(compound, shp)

    if debug:
        print(f"Created compound with {len(shapes)} shapes (Building + BuildingParts)")

    return compound


def build_sewn_shape_from_building(building: ET.Element, sew_tolerance: float = 1e-6, debug: bool = False, 
                                   xyz_transform: Optional[Callable] = None) -> Optional["TopoDS_Shape"]:
    """Build a sewn shape (and solids if possible) from LOD2 surfaces of a building.

    - Collect bldg:WallSurface, bldg:RoofSurface, bldg:GroundSurface polygons
    - Make faces with interior holes
    - Sew faces; try to close shells into solids
    - Return compound of solids if any; otherwise the sewn shell/compound
    - Optionally transform coordinates if xyz_transform is provided
    """
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
            
            fc = _face_from_xyz_rings(ext, holes)
            if fc is not None and not fc.IsNull():
                faces.append(fc)

    if not faces:
        return None

    sewing = BRepBuilderAPI_Sewing(sew_tolerance, True, True, True, False)
    for fc in faces:
        sewing.Add(fc)
    sewing.Perform()
    sewn = sewing.SewedShape()

    # Optional shape fix
    try:
        fixer = ShapeFix_Shape(sewn)
        fixer.Perform()
        sewn = fixer.Shape()
    except Exception:
        pass

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


def _export_step_compound_local(shapes: List["TopoDS_Shape"], out_step: str) -> Tuple[bool, str]:
    """Minimal STEP export avoiding config/FastAPI imports.

    Used as a fallback when importing core.step_exporter is not possible.
    """
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.IFSelect import IFSelect_ReturnStatus
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

    writer = STEPControl_Writer()
    tr = writer.Transfer(compound, STEPControl_AsIs)
    if tr != IFSelect_ReturnStatus.IFSelect_RetDone:
        return False, f"STEP transfer failed: {tr}"
    wr = writer.Write(out_step)
    if wr != IFSelect_ReturnStatus.IFSelect_RetDone:
        return False, f"STEP write failed: {wr}"
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


def export_step_from_citygml(
    gml_path: str,
    out_step: str,
    default_height: float = 10.0,
    limit: Optional[int] = None,
    debug: bool = False,
    method: str = "auto",
    sew_tolerance: float = 1e-6,
    reproject_to: Optional[str] = None,
    source_crs: Optional[str] = None,
    auto_reproject: bool = True,
) -> Tuple[bool, str]:
    """High-level pipeline: CityGML → STEP

    method:
      - "solid": LOD1/LOD2のSolidデータを直接使用（PLATEAUに最適）
      - "extrude": footprint+height extrusion (LOD0系)
      - "sew": LOD2の各サーフェスを縫合してソリッド化（可能なら）
      - "auto": solid→sew→extrudeの順でフォールバック
    auto_reproject:
      - If True and no reproject_to specified, automatically select appropriate projection
    Returns (success, message or output_path).
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

    # Build XLink resolution index
    id_index = _build_id_index(root)
    if debug and id_index:
        print(f"Built XLink index with {len(id_index)} gml:id entries")

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

    # Adjust sew tolerance based on reprojection
    # If reprojecting from geographic to projected coordinates, scale tolerance appropriately
    adjusted_tolerance = sew_tolerance
    if reproject_to and is_geographic_crs(src):
        # Scale tolerance for meter-based coordinates (typical projected systems)
        # Geographic coords are in degrees (~0.00001 degree), projected in meters (~1 meter)
        adjusted_tolerance = 0.1  # 10cm tolerance for meter-based coordinates
        if debug:
            print(f"Adjusted sew tolerance from {sew_tolerance} to {adjusted_tolerance} for projected coordinates")
    
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
                shp = extract_lod_solid_from_building(b, xyz_transform=xyz_transform, id_index=id_index, debug=debug)
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
                    sew_tolerance=adjusted_tolerance, 
                    debug=debug,
                    xyz_transform=xyz_transform
                )
                if shp is not None and not shp.IsNull():
                    shapes.append(shp)
                    count += 1
            except Exception as e:
                if debug:
                    print(f"Sewing failed for building {i}: {e}")
                continue

    # Fallback to extrusion from footprints
    if not shapes and method in ("extrude", "auto"):
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

    return _export_step_compound_local(shapes, out_step)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert CityGML (PLATEAU) to STEP (sew surfaces or extrude footprints)")
    parser.add_argument("input", help="Path to CityGML (*.gml) file")
    parser.add_argument("output", help="Path to output STEP (*.step) file")
    parser.add_argument("--default-height", type=float, default=10.0, help="Fallback height (m) if not available in data")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of buildings for quick tests")
    parser.add_argument("--debug", action="store_true", help="Enable debug prints")
    parser.add_argument("--method", choices=["auto", "sew", "extrude"], default="auto", help="Conversion strategy")
    parser.add_argument("--sew-tolerance", type=float, default=1e-6, help="Sewing tolerance for LOD2 surfaces")
    parser.add_argument("--reproject-to", type=str, default=None, help="Target CRS like 'EPSG:6676' (meters)")
    parser.add_argument("--source-crs", type=str, default=None, help="Override detected source CRS (e.g., 'EPSG:6697')")

    args = parser.parse_args(list(argv) if argv is not None else None)

    ok, msg = export_step_from_citygml(
        args.input,
        args.output,
        default_height=args.default_height,
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
