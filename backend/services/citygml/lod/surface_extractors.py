"""
Surface and solid extraction helpers for LOD processing.

This module provides common face extraction functions used across multiple LOD strategies:
- extract_faces_from_surface_container: Extracts from MultiSurface/CompositeSurface
- extract_solid_shells: Extracts from gml:Solid elements (exterior + interior shells)

These functions are used by LOD1, LOD2, and LOD3 strategies.
"""

from typing import List, Tuple, Optional, Dict, Any
import xml.etree.ElementTree as ET

from ..core.constants import NS
from ..core.types import CoordinateTransform3D, IDIndex
from ..utils.logging import log
from ..utils.xlink_resolver import extract_polygon_with_xlink
from ..parsers.coordinates import extract_polygon_xyz
from ..geometry.tolerance import compute_tolerance_from_coords
from ..geometry.face_fixer import create_face_with_progressive_fallback


def extract_faces_from_surface_container(
    container: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    tolerance: Optional[float] = None,
    debug: bool = False
) -> List[Any]:  # List[TopoDS_Face]
    """
    Extract faces from various GML surface container structures.

    Supports:
    - gml:MultiSurface (multiple independent surfaces)
    - gml:CompositeSurface (connected surface patches)
    - Direct gml:Polygon children

    Extraction Strategies:
    1. Strategy 1: surfaceMember elements (common in MultiSurface/CompositeSurface)
       - Uses XLink resolution for polygon references
       - Applies coordinate transformation
       - Uses progressive fallback for face creation
    2. Strategy 2: Direct Polygon children
       - Fallback for direct polygon children not in surfaceMember

    Args:
        container: Element containing surface geometry (MultiSurface, CompositeSurface, etc.)
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        tolerance: Geometric tolerance (computed from coords if None)
        debug: Enable debug output

    Returns:
        List of TopoDS_Face objects extracted from the container

    Example:
        >>> multi_surface = building.find(".//gml:MultiSurface", NS)
        >>> faces = extract_faces_from_surface_container(
        ...     multi_surface, xyz_transform, id_index, debug=True
        ... )
        >>> # Face extraction statistics:
        >>> #   - surfaceMembers found: 24
        >>> #   - Polygons found: 24
        >>> #   - Face creation successes: 24
        >>> len(faces)
        24

    Notes:
        - Automatically handles XLink references for shared geometry
        - Applies xyz_transform to all coordinates if provided
        - Computes tolerance per-polygon if not provided globally
        - Uses 4-stage progressive fallback for robust face creation
        - Tracks detailed statistics for debugging
    """
    faces: List[Any] = []  # List[TopoDS_Face]

    # Statistics tracking
    stats = {
        "surfaceMember_count": 0,
        "polygon_found": 0,
        "polygon_too_small": 0,
        "transform_failed": 0,
        "face_creation_success": 0,
        "face_creation_failed": 0,
    }

    # ===== Strategy 1: surfaceMember elements =====
    # Common in MultiSurface/CompositeSurface containers
    for surf_member in container.findall(".//gml:surfaceMember", NS):
        stats["surfaceMember_count"] += 1

        # Extract polygon with XLink resolution
        poly = extract_polygon_with_xlink(surf_member, id_index, debug=debug)

        if poly is None:
            # Fallback: search directly without XLink
            poly = surf_member.find(".//gml:Polygon", NS)

        if poly is None:
            continue

        stats["polygon_found"] += 1

        # Extract coordinates
        ext, holes = extract_polygon_xyz(poly)
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
            tol = compute_tolerance_from_coords(ext, precision_mode="standard")
        else:
            tol = tolerance

        # Use progressive fallback strategy for robust face creation
        face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
        if face_list:
            faces.extend(face_list)
            stats["face_creation_success"] += len(face_list)
        else:
            stats["face_creation_failed"] += 1

    # ===== Strategy 2: Direct Polygon children =====
    # Fallback for polygons not in surfaceMember elements
    for poly in container.findall(".//gml:Polygon", NS):
        # Skip if already processed via surfaceMember
        parent = poly.find("..")
        if parent is not None and parent.tag.endswith("surfaceMember"):
            continue

        stats["polygon_found"] += 1

        # Extract coordinates
        ext, holes = extract_polygon_xyz(poly)
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
            tol = compute_tolerance_from_coords(ext, precision_mode="standard")
        else:
            tol = tolerance

        # Use progressive fallback strategy for robust face creation
        face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
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


def extract_solid_shells(
    solid_elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    tolerance: Optional[float] = None,
    debug: bool = False
) -> Tuple[List[Any], List[List[Any]]]:  # Tuple[List[TopoDS_Face], List[List[TopoDS_Face]]]
    """
    Extract exterior and interior shells from a gml:Solid element.

    This function extracts all faces from the solid's exterior shell and any interior
    shells (cavities, courtyards). It supports XLink reference resolution for polygons
    and uses progressive fallback for robust face creation.

    GML Structure:
        gml:Solid/gml:exterior - outer shell (building envelope)
        gml:Solid/gml:interior - inner shells (cavities, courtyards)

    Extraction Process:
    1. Find gml:exterior element
    2. Extract all surfaceMember polygons (with XLink resolution)
    3. Also extract direct Polygon children (fallback)
    4. Repeat for all gml:interior elements
    5. Apply coordinate transformation to all polygons
    6. Use progressive fallback for face creation

    Args:
        solid_elem: XML element containing gml:Solid
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        tolerance: Geometric tolerance (computed from coords if None)
        debug: Enable debug output with XML structure dumping

    Returns:
        Tuple of (exterior_faces, list_of_interior_face_lists)
        - exterior_faces: Faces forming the outer shell
        - list_of_interior_face_lists: Each interior shell as a separate face list

    Example:
        >>> solid = building.find(".//gml:Solid", NS)
        >>> exterior, interiors = extract_solid_shells(
        ...     solid, xyz_transform, id_index, debug=True
        ... )
        >>> # [Solid] Found gml:exterior element
        >>> # [Solid] Found 24 gml:surfaceMember elements in exterior
        >>> # [Solid] Extraction complete: 24 exterior faces, 1 interior shells
        >>> len(exterior)
        24
        >>> len(interiors)
        1

    Notes:
        - Automatically resolves XLink references for shared polygons
        - Dumps XML structure to temp file in debug mode
        - Applies xyz_transform to all coordinates
        - Computes tolerance per-polygon if not provided globally
        - Uses 4-stage progressive fallback for face creation
        - Logs detailed extraction progress for debugging
    """
    exterior_faces: List[Any] = []  # List[TopoDS_Face]
    interior_shells: List[List[Any]] = []  # List[List[TopoDS_Face]]

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

    # ===== Extract exterior shell polygons =====
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
            poly = extract_polygon_with_xlink(surf_member, id_index, debug=xlink_debug)

            if poly is None:
                # Fallback: search directly
                poly = surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                if debug:
                    log(f"  [Solid]   surfaceMember[{i}]: No Polygon found (XLink may have failed)")
                continue

            if debug:
                log(f"  [Solid]   surfaceMember[{i}]: Polygon found")

            ext, holes = extract_polygon_xyz(poly)
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
                tol = compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
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
                        log(f"Exterior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                exterior_faces.extend(face_list)

    # ===== Extract interior shells (cavities) =====
    for interior_elem in solid_elem.findall("./gml:interior", NS):
        interior_faces: List[Any] = []  # List[TopoDS_Face]

        # Try surfaceMember pattern first
        for surf_member in interior_elem.findall(".//gml:surfaceMember", NS):
            poly = extract_polygon_with_xlink(surf_member, id_index, debug=debug)

            if poly is None:
                poly = surf_member.find(".//gml:Polygon", NS)

            if poly is None:
                continue

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
                        log(f"Interior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                interior_faces.extend(face_list)

        # Also search for direct Polygon children
        for poly in interior_elem.findall(".//gml:Polygon", NS):
            parent = poly.find("..")
            if parent is not None and parent.tag.endswith("surfaceMember"):
                continue

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
                        log(f"Interior transform failed: {e}")
                    continue

            # Compute tolerance if not provided
            if tolerance is None:
                tol = compute_tolerance_from_coords(ext, precision_mode="standard")
            else:
                tol = tolerance

            # Use progressive fallback strategy for robust face creation
            face_list = create_face_with_progressive_fallback(ext, holes, tol, debug=debug)
            if face_list:
                interior_faces.extend(face_list)

        if interior_faces:
            interior_shells.append(interior_faces)
            if debug:
                log(f"Found interior shell with {len(interior_faces)} faces (cavity)")

    if debug:
        log(f"  [Solid] Extraction complete: {len(exterior_faces)} exterior faces, {len(interior_shells)} interior shells")

    return exterior_faces, interior_shells
