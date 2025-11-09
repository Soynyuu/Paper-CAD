"""
Polygon extraction utilities for CityGML building elements.

This module provides functions to find and extract polygon elements from
CityGML building geometries, including footprints, roofs, and ground surfaces.
"""

import math
from typing import List, Optional
import xml.etree.ElementTree as ET

from ..core.constants import NS, DEFAULT_BUILDING_HEIGHT
from ..utils.xml_parser import first_text
from .coordinates import parse_poslist


def find_footprint_polygons(building: ET.Element) -> List[ET.Element]:
    """
    Find polygon elements that represent a building's footprint.

    This function searches for footprint geometry in priority order:
    1. bldg:lod0FootPrint//gml:Polygon (standard CityGML footprint)
    2. bldg:lod0RoofEdge//gml:Polygon (PLATEAU often uses this instead)
    3. bldg:boundedBy/bldg:GroundSurface//gml:Polygon (ground surface fallback)

    Args:
        building: bldg:Building element

    Returns:
        List of gml:Polygon elements representing the footprint.
        Returns empty list if no footprint is found.

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> footprints = find_footprint_polygons(building)
        >>> len(footprints)
        1
        >>> footprints[0].tag
        '{http://www.opengis.net/gml}Polygon'

    Notes:
        - Returns immediately after finding polygons in the first available source
        - PLATEAU datasets often use lod0RoofEdge instead of lod0FootPrint
        - Ground surfaces are the lowest priority fallback
    """
    polys: List[ET.Element] = []

    # Priority 1: lod0FootPrint (standard CityGML)
    for node in building.findall(".//bldg:lod0FootPrint", NS):
        polys += node.findall(".//gml:Polygon", NS)
    if polys:
        return polys

    # Priority 2: lod0RoofEdge (PLATEAU often has this instead of footprint)
    for node in building.findall(".//bldg:lod0RoofEdge", NS):
        polys += node.findall(".//gml:Polygon", NS)
    if polys:
        return polys

    # Priority 3: GroundSurface under boundedBy
    for gs in building.findall(".//bldg:boundedBy/bldg:GroundSurface", NS):
        polys += gs.findall(".//gml:Polygon", NS)

    return polys


def estimate_building_height(
    building: ET.Element,
    default_height: float = DEFAULT_BUILDING_HEIGHT
) -> float:
    """
    Estimate building height from CityGML metadata or geometry.

    This function tries multiple strategies to determine building height:
    1. bldg:measuredHeight or uro:measuredHeight tags
    2. Z coordinate range across all geometry
    3. Default height (fallback)

    Args:
        building: bldg:Building element
        default_height: Default height to use if no height can be determined (meters)

    Returns:
        Estimated building height in meters

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> height = estimate_building_height(building, default_height=10.0)
        >>> height
        25.5

    Notes:
        - PLATEAU datasets typically have measuredHeight or uro:buildingHeight
        - Z range calculation considers all gml:posList elements in the building
        - Returns default height if no height information is available
    """
    # Strategy 1: Try common height tags
    tags = [
        ".//bldg:measuredHeight",
        ".//uro:measuredHeight",
        ".//uro:buildingHeight",
    ]
    for path in tags:
        node = building.find(path, NS)
        if node is not None:
            txt = first_text(node)
            if txt:
                try:
                    h = float(txt)
                    if h > 0:
                        return h
                except ValueError:
                    pass

    # Strategy 2: Calculate height from Z coordinate range
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

    # Strategy 3: Return default height
    return float(default_height)


def count_polygons_in_element(elem: ET.Element) -> int:
    """
    Count the number of gml:Polygon elements in an element's descendants.

    Args:
        elem: XML element to search

    Returns:
        Number of gml:Polygon elements found

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> count_polygons_in_element(building)
        42
    """
    return len(elem.findall(".//gml:Polygon", NS))


def find_building_parts(building: ET.Element) -> List[ET.Element]:
    """
    Find all BuildingPart elements within a building.

    Args:
        building: bldg:Building element

    Returns:
        List of bldg:BuildingPart elements (may be empty)

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> parts = find_building_parts(building)
        >>> len(parts)
        3
        >>> parts[0].tag
        '{http://www.opengis.net/citygml/building/2.0}BuildingPart'

    Notes:
        - BuildingParts represent components of a building (e.g., tower, annex)
        - Not all buildings have BuildingParts
        - Some PLATEAU buildings have multiple BuildingParts that need to be fused
    """
    return building.findall(".//bldg:consistsOfBuildingPart/bldg:BuildingPart", NS)
