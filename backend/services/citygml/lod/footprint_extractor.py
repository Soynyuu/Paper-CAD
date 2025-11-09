"""
Footprint extrusion module - LOD0 footprint extraction and 3D extrusion.

This module handles the legacy footprint extrusion method for CityGML buildings
that don't have LOD1/LOD2/LOD3 solid geometry. It extracts 2D footprints and
extrudes them to a specified height to create simple building volumes.

Extracted from original citygml_to_step.py lines 396-667 (Phase 2 refactoring).
"""

from typing import List, Tuple, Optional, Callable, Any
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import math

from ..core.constants import NS
from ..parsers.coordinates import parse_poslist
from ..utils.logging import log

# Check OCCT availability
try:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCC.Core.gp import gp_Pnt, gp_Vec
    OCCT_AVAILABLE = True
except ImportError:
    OCCT_AVAILABLE = False


@dataclass
class Footprint:
    """Represents a 2D footprint with holes and height for extrusion."""
    exterior: List[Tuple[float, float]]  # Outer boundary (x, y) in meters
    holes: List[List[Tuple[float, float]]]  # Interior holes
    height: float  # Extrusion height in meters
    building_id: str  # Building identifier


def extract_polygon_xy(poly: ET.Element) -> Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]], List[float]]:
    """
    Extract exterior and interior rings as XY lists from a gml:Polygon.

    Also returns a list of all Z values found for height estimation.

    Args:
        poly: gml:Polygon element

    Returns:
        Tuple of (exterior_xy, holes_xy, all_z_values)
        - exterior_xy: List of (x, y) tuples for outer boundary
        - holes_xy: List of lists of (x, y) tuples for interior holes
        - all_z_values: All Z coordinates found (for height estimation)

    Example:
        >>> poly_elem = root.find(".//gml:Polygon", NS)
        >>> ext, holes, z_vals = extract_polygon_xy(poly_elem)
        >>> ext
        [(100.0, 200.0), (110.0, 200.0), (110.0, 210.0), (100.0, 210.0)]
        >>> z_vals
        [10.5, 10.5, 10.5, 10.5]
    """
    all_z: List[float] = []

    # Exterior
    ext_coords_xy: List[Tuple[float, float]] = []
    ext_poslist = poly.find(".//gml:exterior/gml:LinearRing/gml:posList", NS)
    if ext_poslist is not None:
        coords = parse_poslist(ext_poslist)
    else:
        # Fallback: multiple gml:pos elements
        pos_elems = poly.findall(".//gml:exterior//gml:pos", NS)
        coords = []
        for p in pos_elems:
            coords += parse_poslist(p)

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
            rcoords = parse_poslist(rl)
        else:
            rcoords = []
            for rp in ring.findall(".//gml:pos", NS):
                rcoords += parse_poslist(rp)
        for x, y, z in rcoords:
            ring_xy.append((x, y))
            if z is not None and not math.isnan(z):
                all_z.append(z)
        if ring_xy:
            holes_xy.append(ring_xy)

    return ext_coords_xy, holes_xy, all_z


def find_footprint_polygons(building: ET.Element) -> List[ET.Element]:
    """
    Return a list of gml:Polygon elements that likely represent footprints.

    Priority order:
      1) bldg:lod0FootPrint//gml:Polygon (explicit footprint)
      2) bldg:lod0RoofEdge//gml:Polygon (PLATEAU often uses this instead)
      3) bldg:boundedBy/bldg:GroundSurface//gml:Polygon (ground contact surfaces)

    Args:
        building: bldg:Building element

    Returns:
        List of gml:Polygon elements representing footprints

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> polys = find_footprint_polygons(building)
        >>> len(polys)
        1
        >>> polys[0].tag
        '{http://www.opengis.net/gml}Polygon'

    Notes:
        - Returns first available polygons from priority list
        - Empty list if no footprints found
        - PLATEAU datasets typically use lod0RoofEdge
    """
    polys: List[ET.Element] = []

    # 1) lod0FootPrint (explicit footprint definition)
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


def estimate_building_height(building: ET.Element, default_height: float) -> float:
    """
    Try to get building height from tags or coordinate Z range; fallback to default.

    Priority order:
      1) bldg:measuredHeight
      2) uro:measuredHeight (Urban Object extension)
      3) uro:buildingHeight
      4) Z coordinate range (max - min)
      5) default_height parameter

    Args:
        building: bldg:Building element
        default_height: Fallback height if no data found

    Returns:
        Building height in meters

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> height = estimate_building_height(building, 10.0)
        >>> height
        25.5  # From <bldg:measuredHeight>25.5</bldg:measuredHeight>

    Notes:
        - Returns default_height if no height data found
        - Validates height > 0 before returning
        - Z range calculation uses all gml:posList coordinates
    """
    # Helper to get first text content
    def _first_text(elem):
        if elem.text:
            return elem.text.strip()
        for child in elem:
            if child.text:
                return child.text.strip()
        return None

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
        coords = parse_poslist(poslist)
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
    """
    Parse a CityGML file and return footprint prism descriptions.

    This is the main entry point for footprint extraction. It:
    1. Parses the CityGML file
    2. Extracts footprint polygons for each building
    3. Estimates building heights
    4. Optionally transforms coordinates to target CRS
    5. Returns Footprint objects ready for extrusion

    Args:
        gml_path: Path to CityGML file
        default_height: Default height for buildings without height data (meters)
        limit: Maximum number of footprints to extract (None = unlimited)
        xy_transform: Optional function to transform (x, y) → (X, Y)

    Returns:
        List of Footprint objects with exterior, holes, height, building_id

    Example:
        >>> from pyproj import Transformer
        >>> transformer = Transformer.from_crs("EPSG:4326", "EPSG:6676")
        >>> def xy_tx(x, y):
        ...     return transformer.transform(x, y)
        >>> footprints = parse_citygml_footprints(
        ...     "city.gml",
        ...     default_height=10.0,
        ...     limit=100,
        ...     xy_transform=xy_tx
        ... )
        >>> footprints[0].height
        25.5
        >>> footprints[0].building_id
        'bldg_001'

    Notes:
        - Uses heuristic to find footprints (lod0FootPrint → lod0RoofEdge → GroundSurface)
        - Skips buildings with no footprint polygons
        - Skips buildings with < 3 exterior vertices
        - Coordinate transformation applied if xy_transform provided
    """
    tree = ET.parse(gml_path)
    root = tree.getroot()

    bldgs = root.findall(".//bldg:Building", NS)
    footprints: List[Footprint] = []
    for i, b in enumerate(bldgs):
        if limit is not None and len(footprints) >= limit:
            break

        bid = b.get("gml:id") or b.get("id") or f"building_{i+1}"
        polys = find_footprint_polygons(b)
        if not polys:
            # Skip if no reasonable polygon
            continue

        # Use first polygon as footprint (simple heuristic)
        ext, holes, z_all = extract_polygon_xy(polys[0])

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

        height = estimate_building_height(b, default_height)

        footprints.append(Footprint(exterior=ext, holes=holes, height=height, building_id=bid))

    return footprints


def wire_from_coords_xy(coords: List[Tuple[float, float]]) -> Any:
    """
    Create a wire from 2D coordinates at Z=0.

    Args:
        coords: List of (x, y) tuples in meters

    Returns:
        TopoDS_Wire

    Example:
        >>> coords = [(0, 0), (10, 0), (10, 10), (0, 10)]
        >>> wire = wire_from_coords_xy(coords)
        >>> wire.IsNull()
        False

    Notes:
        - Automatically closes the wire
        - Removes duplicate closing point if present
        - All points placed at Z=0
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE is required for wire creation")

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


def extrude_footprint(fp: Footprint) -> Any:
    """
    Create a prism solid from a 2D footprint using vertical extrusion.

    This function:
    1. Creates a wire from the exterior boundary
    2. Creates a face from the wire
    3. Adds holes (interior boundaries) if any
    4. Extrudes the face vertically by the specified height

    Args:
        fp: Footprint with exterior, holes, and height

    Returns:
        TopoDS_Shape prism solid

    Example:
        >>> fp = Footprint(
        ...     exterior=[(0, 0), (10, 0), (10, 10), (0, 10)],
        ...     holes=[],
        ...     height=25.5,
        ...     building_id="bldg_001"
        ... )
        >>> solid = extrude_footprint(fp)
        >>> # Creates a 10m × 10m × 25.5m box

    Notes:
        - Extrusion is always vertical (along Z axis)
        - Handles interior holes (courtyards)
        - Returns TopoDS_Shape (usually TopoDS_Solid)
        - Requires valid footprint with ≥3 exterior points
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for extrusion")

    outer = wire_from_coords_xy(fp.exterior)
    face_maker = BRepBuilderAPI_MakeFace(outer, True)

    # Add interior holes if any
    for hole in fp.holes:
        if len(hole) >= 3:
            face_maker.Add(wire_from_coords_xy(hole))

    face = face_maker.Face()

    vec = gp_Vec(0.0, 0.0, float(fp.height))
    prism = BRepPrimAPI_MakePrism(face, vec, True).Shape()
    return prism


def extract_footprints_and_extrude(
    gml_path: str,
    default_height: float = 10.0,
    limit: Optional[int] = None,
    xy_transform: Optional[Callable[[float, float], Tuple[float, float]]] = None,
    debug: bool = False
) -> List[Any]:
    """
    High-level function to parse footprints and extrude them to 3D solids.

    This is a convenience function that combines:
    1. parse_citygml_footprints() to extract footprints
    2. extrude_footprint() to create 3D solids

    Args:
        gml_path: Path to CityGML file
        default_height: Default height for buildings without height data
        limit: Maximum number of buildings to process
        xy_transform: Optional coordinate transformation function
        debug: Enable debug output

    Returns:
        List of TopoDS_Shape solids (one per building)

    Example:
        >>> shapes = extract_footprints_and_extrude(
        ...     "city.gml",
        ...     default_height=10.0,
        ...     limit=100,
        ...     debug=True
        ... )
        >>> # Parsed buildings with footprints: 85
        >>> # Successfully extruded: 82
        >>> len(shapes)
        82

    Notes:
        - Skips buildings with extrusion failures
        - Returns empty list if no valid footprints found
        - Logs extraction progress if debug=True
    """
    if debug:
        log(f"[EXTRUDE] Parsing footprints from {gml_path}")
        log(f"[EXTRUDE] Default height: {default_height}m, limit: {limit}")

    fplist = parse_citygml_footprints(
        gml_path,
        default_height=default_height,
        limit=limit,
        xy_transform=xy_transform,
    )

    if debug:
        log(f"[EXTRUDE] Parsed {len(fplist)} buildings with footprints")

    shapes = []
    for i, fp in enumerate(fplist):
        try:
            shp = extrude_footprint(fp)
            shapes.append(shp)
            if debug:
                log(f"[EXTRUDE] {i+1}/{len(fplist)}: {fp.building_id} → height {fp.height}m")
        except Exception as e:
            if debug:
                log(f"[EXTRUDE] {i+1}/{len(fplist)}: {fp.building_id} FAILED: {e}")
            continue

    if debug:
        log(f"[EXTRUDE] Successfully extruded {len(shapes)}/{len(fplist)} buildings")

    return shapes
