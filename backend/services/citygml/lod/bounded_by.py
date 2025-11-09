"""
BoundedBy surface extraction for CityGML buildings.

This module provides functions to extract geometry from CityGML boundedBy surfaces.
BoundedBy surfaces are thematic boundary surfaces that describe the semantic meaning
of building faces (walls, roofs, ground surfaces, etc.).

CityGML 2.0 defines 6 _BoundarySurface types, all supported here:
- WallSurface: vertical exterior walls (most common)
- RoofSurface: roof structures (most common)
- GroundSurface: ground contact surfaces (footprint)
- OuterCeilingSurface: exterior ceiling that is not a roof (rare)
- OuterFloorSurface: exterior upper floor that is not a roof (rare)
- ClosureSurface: virtual surfaces to close building volumes (PLATEAU uses these)
"""

from typing import List, Tuple, Optional, Any, Dict
import xml.etree.ElementTree as ET

from ..core.constants import NS, BOUNDARY_SURFACE_TYPES
from ..core.types import CoordinateTransform3D, IDIndex
from ..utils.logging import log
from ..parsers.coordinates import extract_polygon_xyz


def find_bounded_surfaces(elem: ET.Element) -> List[ET.Element]:
    """
    Find all boundedBy surfaces in a building element.

    Searches for all 6 CityGML 2.0 boundary surface types.

    Args:
        elem: bldg:Building or bldg:BuildingPart element

    Returns:
        List of boundary surface elements (all types combined)

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> surfaces = find_bounded_surfaces(building)
        >>> len(surfaces)
        42
    """
    bounded_surfaces = (
        elem.findall(".//bldg:boundedBy/bldg:WallSurface", NS) +
        elem.findall(".//bldg:boundedBy/bldg:RoofSurface", NS) +
        elem.findall(".//bldg:boundedBy/bldg:GroundSurface", NS) +
        elem.findall(".//bldg:boundedBy/bldg:OuterCeilingSurface", NS) +
        elem.findall(".//bldg:boundedBy/bldg:OuterFloorSurface", NS) +
        elem.findall(".//bldg:boundedBy/bldg:ClosureSurface", NS)
    )
    return bounded_surfaces


def extract_faces_from_bounded_surface(
    surf: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    extract_faces_from_surface_container: Any,  # Function
    debug: bool = False
) -> Tuple[List[Any], str, int]:  # List[TopoDS_Face], method_name, face_count
    """
    Extract faces from a single boundedBy surface using progressive fallback.

    Tries 3 methods in order:
    1. LOD-specific wrappers (lod3/lod2 MultiSurface/Geometry) - highest priority
    2. Direct MultiSurface/CompositeSurface children - fallback
    3. Direct Polygon children - last resort

    Args:
        surf: Boundary surface element (e.g., WallSurface, RoofSurface)
        xyz_transform: 3D coordinate transformer
        id_index: XLink ID index for reference resolution
        extract_faces_from_surface_container: Function to extract faces from containers
        debug: Enable debug output

    Returns:
        Tuple of (faces, method_used, face_count)

    Example:
        >>> wall_surface = building.find(".//bldg:WallSurface", NS)
        >>> faces, method, count = extract_faces_from_bounded_surface(
        ...     wall_surface, xyz_transform, id_index, extract_fn, debug=True
        ... )
        >>> # Method 1 (lod2MultiSurface): extracted 12 faces
        >>> method
        'Method 1 (lod2MultiSurface)'
        >>> count
        12

    Notes:
        - LOD3 has priority over LOD2 for more detailed geometry
        - Returns empty list if all methods fail
        - Automatically applies xyz_transform to extracted coordinates
    """
    from ..geometry.builders import face_from_xyz_rings

    faces = []
    found_geometry = False
    method_used = None

    # Get surface type for debugging
    surf_type = surf.tag.split("}")[-1] if "}" in surf.tag else surf.tag

    # ===== Method 1: LOD-specific wrappers (LOD3 has priority) =====
    # Fix for issue #48: Support LOD3 WallSurface extraction to prevent wall omissions
    for lod_tag in [".//bldg:lod3MultiSurface", ".//bldg:lod3Geometry",
                   ".//bldg:lod2MultiSurface", ".//bldg:lod2Geometry"]:
        surf_geom = surf.find(lod_tag, NS)
        if surf_geom is not None:
            faces_before = len(faces)

            # Look for MultiSurface or CompositeSurface containers
            for surface_container in (
                surf_geom.findall(".//gml:MultiSurface", NS) +
                surf_geom.findall(".//gml:CompositeSurface", NS)
            ):
                faces_extracted = extract_faces_from_surface_container(
                    surface_container, xyz_transform, id_index, debug
                )
                faces.extend(faces_extracted)

            # Only mark as found if we actually extracted faces
            if len(faces) > faces_before:
                found_geometry = True
                method_used = f"Method 1 ({lod_tag.split(':')[-1]})"
                if debug:
                    log(f"  [{surf_type}] {method_used}: extracted {len(faces) - faces_before} faces")
                break  # Successfully extracted, no need to try other LOD tags

    # ===== Method 2: Direct MultiSurface or CompositeSurface children =====
    # Some PLATEAU buildings have geometry directly without LOD-specific wrappers
    if not found_geometry:
        faces_before = len(faces)

        for direct_container in (
            surf.findall("./gml:MultiSurface", NS) +
            surf.findall("./gml:CompositeSurface", NS)
        ):
            faces_extracted = extract_faces_from_surface_container(
                direct_container, xyz_transform, id_index, debug
            )
            faces.extend(faces_extracted)

        if len(faces) > faces_before:
            found_geometry = True
            method_used = "Method 2 (direct MultiSurface)"
            if debug:
                log(f"  [{surf_type}] {method_used}: extracted {len(faces) - faces_before} faces")

    # ===== Method 3: Direct Polygon children =====
    if not found_geometry:
        faces_before = len(faces)

        for poly in surf.findall(".//gml:Polygon", NS):
            ext, holes = extract_polygon_xyz(poly)
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

            fc = face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                faces.append(fc)

        if len(faces) > faces_before:
            found_geometry = True
            method_used = "Method 3 (direct Polygon)"
            if debug:
                log(f"  [{surf_type}] {method_used}: extracted {len(faces) - faces_before} faces")

    # Log failure if no geometry found
    if not found_geometry and debug:
        log(f"  [{surf_type}] ✗ No geometry found - all 3 methods failed")

    return faces, method_used or "No method succeeded", len(faces)


def extract_faces_from_all_bounded_surfaces(
    elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    extract_faces_from_surface_container: Any,  # Function
    debug: bool = False
) -> List[Any]:  # List[TopoDS_Face]
    """
    Extract faces from all boundedBy surfaces in a building element.

    This is the main entry point for boundedBy extraction. It:
    1. Finds all boundary surfaces (all 6 types)
    2. Extracts faces from each surface using progressive fallback
    3. Collects statistics for debugging
    4. Returns all extracted faces

    Args:
        elem: bldg:Building or bldg:BuildingPart element
        xyz_transform: 3D coordinate transformer
        id_index: XLink ID index for reference resolution
        extract_faces_from_surface_container: Function to extract faces from containers
        debug: Enable detailed logging with statistics

    Returns:
        List of TopoDS_Face objects extracted from all boundary surfaces

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> faces = extract_faces_from_all_bounded_surfaces(
        ...     building, xyz_transform, id_index, extract_fn, debug=True
        ... )
        >>> # [LOD2] boundedBy extraction summary:
        >>> #   - Total surfaces: 42 (Wall: 24, Roof: 12, Ground: 4, ...)
        >>> #   - Total faces extracted: 156 (Wall: 96, Roof: 48, Ground: 12, ...)
        >>> len(faces)
        156

    Notes:
        - Coordinates are already re-centered by xyz_transform wrapper (PHASE:0)
        - Returns empty list if no surfaces found or all extraction fails
        - Detailed statistics logged when debug=True
    """
    bounded_surfaces = find_bounded_surfaces(elem)

    if not bounded_surfaces:
        return []

    if debug:
        elem_id = elem.get(f"{{{NS['gml']}}}id") or "unknown"
        log(f"[LOD2/LOD3] Found {len(bounded_surfaces)} boundedBy surfaces in {elem_id}")

    # Initialize statistics tracking
    surface_stats: Dict[str, int] = {surf_type: 0 for surf_type in BOUNDARY_SURFACE_TYPES}
    faces_by_type: Dict[str, int] = {surf_type: 0 for surf_type in BOUNDARY_SURFACE_TYPES}

    all_faces = []

    # Extract faces from each surface
    for surf in bounded_surfaces:
        # Get surface type
        surf_type = surf.tag.split("}")[-1] if "}" in surf.tag else surf.tag

        if debug:
            surface_stats[surf_type] = surface_stats.get(surf_type, 0) + 1

        # Extract faces from this surface
        faces, method, face_count = extract_faces_from_bounded_surface(
            surf, xyz_transform, id_index, extract_faces_from_surface_container, debug
        )

        all_faces.extend(faces)

        if debug:
            faces_by_type[surf_type] = faces_by_type.get(surf_type, 0) + face_count
            if face_count > 0:
                log(f"  - {surf_type}: extracted {face_count} faces")

    # Log summary statistics
    if debug:
        log(f"[LOD2] boundedBy extraction summary:")
        log(f"  - Total surfaces: {len(bounded_surfaces)} "
            f"(Wall: {surface_stats.get('WallSurface', 0)}, "
            f"Roof: {surface_stats.get('RoofSurface', 0)}, "
            f"Ground: {surface_stats.get('GroundSurface', 0)}, "
            f"OuterCeiling: {surface_stats.get('OuterCeilingSurface', 0)}, "
            f"OuterFloor: {surface_stats.get('OuterFloorSurface', 0)}, "
            f"Closure: {surface_stats.get('ClosureSurface', 0)})")
        log(f"  - Total faces extracted: {len(all_faces)} "
            f"(Wall: {faces_by_type.get('WallSurface', 0)}, "
            f"Roof: {faces_by_type.get('RoofSurface', 0)}, "
            f"Ground: {faces_by_type.get('GroundSurface', 0)}, "
            f"OuterCeiling: {faces_by_type.get('OuterCeilingSurface', 0)}, "
            f"OuterFloor: {faces_by_type.get('OuterFloorSurface', 0)}, "
            f"Closure: {faces_by_type.get('ClosureSurface', 0)})")

    return all_faces


def count_bounded_by_faces(elem: ET.Element) -> int:
    """
    Quickly count the approximate number of faces in boundedBy surfaces.

    This is used for Issue #48 comparison logic to determine if boundedBy
    has more detail than lod2Solid.

    Args:
        elem: bldg:Building or bldg:BuildingPart element

    Returns:
        Approximate number of faces (polygon count)

    Example:
        >>> building = root.find(".//bldg:Building", NS)
        >>> count = count_bounded_by_faces(building)
        >>> count
        80

    Notes:
        - This is a quick count, not exact face extraction
        - Used for comparison purposes only
        - Does not create actual TopoDS_Face objects
    """
    bounded_surfaces = find_bounded_surfaces(elem)

    if not bounded_surfaces:
        return 0

    total_count = 0

    for surf in bounded_surfaces:
        surf_count = 0

        # Try all 3 methods like in full extraction
        # Method 1: LOD-specific wrappers
        for lod_tag in [".//bldg:lod3MultiSurface", ".//bldg:lod3Geometry",
                       ".//bldg:lod2MultiSurface", ".//bldg:lod2Geometry"]:
            surf_geom = surf.find(lod_tag, NS)
            if surf_geom is not None:
                for container in (
                    surf_geom.findall(".//gml:MultiSurface", NS) +
                    surf_geom.findall(".//gml:CompositeSurface", NS)
                ):
                    polys = container.findall(".//gml:Polygon", NS)
                    surf_count += len(polys)
                if surf_count > 0:
                    break

        # Method 2: Direct containers
        if surf_count == 0:
            for container in (
                surf.findall("./gml:MultiSurface", NS) +
                surf.findall("./gml:CompositeSurface", NS)
            ):
                polys = container.findall(".//gml:Polygon", NS)
                surf_count += len(polys)

        # Method 3: Direct polygons
        if surf_count == 0:
            polys = surf.findall(".//gml:Polygon", NS)
            surf_count += len(polys)

        total_count += surf_count

    return total_count
