"""
Coordinate parsing utilities for GML geometry elements.

This module provides functions to parse coordinate data from GML elements,
including gml:posList and gml:pos elements, and to extract polygon rings
(exterior and interior) in both 2D (XY) and 3D (XYZ) formats.
"""

import math
from typing import List, Tuple, Optional
import xml.etree.ElementTree as ET

from ..core.constants import NS


def parse_poslist(elem: ET.Element) -> List[Tuple[float, float, Optional[float]]]:
    """
    Parse a gml:posList or gml:pos element into a list of coordinates.

    This function automatically detects whether the coordinates are 2D or 3D
    based on whether the number of values is divisible by 2 or 3. It is robust
    to extra whitespace and unparsable tokens.

    Args:
        elem: gml:posList or gml:pos element

    Returns:
        List of (x, y, z) tuples where z may be None for 2D coordinates

    Examples:
        >>> # 3D coordinates
        >>> elem = ET.fromstring('<gml:posList>1.0 2.0 3.0 4.0 5.0 6.0</gml:posList>')
        >>> parse_poslist(elem)
        [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]

        >>> # 2D coordinates
        >>> elem = ET.fromstring('<gml:posList>1.0 2.0 3.0 4.0</gml:posList>')
        >>> parse_poslist(elem)
        [(1.0, 2.0, None), (3.0, 4.0, None)]

        >>> # Empty element
        >>> elem = ET.fromstring('<gml:posList></gml:posList>')
        >>> parse_poslist(elem)
        []

    Notes:
        - Dimension inference: 3D if divisible by 3, otherwise 2D if divisible by 2
        - Unparsable tokens are silently skipped
        - Extra whitespace is handled automatically
    """
    txt = (elem.text or "").strip()
    if not txt:
        return []

    # Split on whitespace and parse as floats
    parts = txt.split()
    vals: List[float] = []
    for p in parts:
        try:
            vals.append(float(p))
        except ValueError:
            # Skip unparsable tokens
            continue

    # Automatic dimension inference: 3D if divisible by 3; else 2D if by 2
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


def extract_polygon_xy(
    poly: ET.Element
) -> Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]], List[float]]:
    """
    Extract exterior and interior rings as 2D (XY) lists from a gml:Polygon.

    This function also collects all Z values found for height estimation purposes.

    Args:
        poly: gml:Polygon element

    Returns:
        Tuple of (exterior_xy, holes_xy, all_z_values) where:
        - exterior_xy: List of (x, y) coordinates for exterior ring
        - holes_xy: List of lists of (x, y) coordinates for interior rings (holes)
        - all_z_values: List of all Z values found (for height estimation)

    Example:
        >>> # Polygon with exterior ring and one hole
        >>> polygon = root.find(".//gml:Polygon", NS)
        >>> ext, holes, z_vals = extract_polygon_xy(polygon)
        >>> len(ext)
        5
        >>> len(holes)
        1
        >>> len(holes[0])
        4
        >>> min(z_vals), max(z_vals)
        (0.0, 25.5)

    Notes:
        - Handles both gml:posList (preferred) and multiple gml:pos elements (fallback)
        - NaN Z values are filtered out
        - Empty holes are excluded from the result
    """
    all_z: List[float] = []

    # Extract exterior ring
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

    # Extract interior rings (holes)
    holes_xy: List[List[Tuple[float, float]]] = []
    for ring in poly.findall(".//gml:interior/gml:LinearRing", NS):
        ring_xy: List[Tuple[float, float]] = []
        rl = ring.find("./gml:posList", NS)

        if rl is not None:
            rcoords = parse_poslist(rl)
        else:
            # Fallback: multiple gml:pos elements
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


def extract_polygon_xyz(
    poly: ET.Element
) -> Tuple[List[Tuple[float, float, float]], List[List[Tuple[float, float, float]]]]:
    """
    Extract exterior and interior rings as 3D (XYZ) lists from a gml:Polygon.

    If Z coordinate is missing, it is treated as 0.0.

    Args:
        poly: gml:Polygon element

    Returns:
        Tuple of (exterior_xyz, holes_xyz) where:
        - exterior_xyz: List of (x, y, z) coordinates for exterior ring
        - holes_xyz: List of lists of (x, y, z) coordinates for interior rings

    Example:
        >>> # 3D polygon (e.g., LOD2 wall or roof surface)
        >>> polygon = root.find(".//bldg:WallSurface//gml:Polygon", NS)
        >>> ext, holes = extract_polygon_xyz(polygon)
        >>> ext
        [(100.0, 200.0, 0.0), (110.0, 200.0, 0.0), (110.0, 210.0, 0.0), (100.0, 210.0, 15.0)]
        >>> holes
        [[(102.0, 202.0, 5.0), (108.0, 202.0, 5.0), (108.0, 208.0, 10.0), (102.0, 208.0, 10.0)]]

    Notes:
        - Handles both gml:posList (preferred) and multiple gml:pos elements (fallback)
        - Missing Z values default to 0.0
        - Empty holes are excluded from the result
    """
    # Extract exterior ring
    ext_xyz: List[Tuple[float, float, float]] = []
    ext_poslist = poly.find(".//gml:exterior/gml:LinearRing/gml:posList", NS)

    coords = []
    if ext_poslist is not None:
        coords = parse_poslist(ext_poslist)
    else:
        # Fallback: multiple gml:pos elements
        for p in poly.findall(".//gml:exterior//gml:pos", NS):
            coords += parse_poslist(p)

    for x, y, z in coords:
        ext_xyz.append((float(x), float(y), float(z if z is not None else 0.0)))

    # Extract interior rings (holes)
    holes_xyz: List[List[Tuple[float, float, float]]] = []
    for ring in poly.findall(".//gml:interior/gml:LinearRing", NS):
        ring_xyz: List[Tuple[float, float, float]] = []
        rl = ring.find("./gml:posList", NS)

        rcoords = parse_poslist(rl) if rl is not None else []
        if not rcoords:
            # Fallback: multiple gml:pos elements
            for rp in ring.findall(".//gml:pos", NS):
                rcoords += parse_poslist(rp)

        for x, y, z in rcoords:
            ring_xyz.append((float(x), float(y), float(z if z is not None else 0.0)))

        if ring_xyz:
            holes_xyz.append(ring_xyz)

    return ext_xyz, holes_xyz
