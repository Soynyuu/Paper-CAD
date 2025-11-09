"""
Coordinate recentering for numerical precision preservation (PHASE:0).

⚠️ CRITICAL: This module implements PHASE:0 coordinate recentering, which MUST be
executed BEFORE tolerance calculation. The recentering prevents OpenCASCADE precision
loss when coordinates are far from origin (e.g., PLATEAU data at ~40km causing
geometry collapse).

This is executed as the FIRST phase in the conversion pipeline, before any other
geometry processing.
"""

from typing import List, Tuple, Optional, Callable
import xml.etree.ElementTree as ET

from ..core.constants import NS, RECENTERING_DISTANCE_THRESHOLD
from ..core.types import CoordinateTransform3D
from ..parsers.coordinates import extract_polygon_xyz
from ..utils.logging import log


def compute_offset_and_wrap_transform(
    buildings: List[ET.Element],
    xyz_transform: Optional[CoordinateTransform3D],
    debug: bool = False
) -> Tuple[Optional[CoordinateTransform3D], Optional[Tuple[float, float, float]]]:
    """
    Compute coordinate offset and wrap transform to recenter geometry near origin.

    ⚠️ CRITICAL: This is PHASE:0 and MUST be executed before tolerance calculation.
    The offset shifts coordinates closer to the origin to prevent OpenCASCADE
    precision loss. Without this, buildings far from origin (e.g., 40km) will have
    collapsed or invalid geometry.

    Algorithm:
    1. Scan all polygon coordinates from all buildings
    2. Apply xyz_transform (if provided) to get planar coordinates in meters
    3. Calculate bounding box center of all coordinates
    4. Compute distance from origin
    5. If distance > threshold (1.0m):
       - Calculate offset = (-center_x, -center_y, -center_z)
       - Wrap xyz_transform with offset function
       - Return wrapped transform and offset
    6. Otherwise:
       - Return original transform and None offset

    Args:
        buildings: List of bldg:Building elements to scan
        xyz_transform: Existing 3D coordinate transformer (may be None)
        debug: Enable debug output

    Returns:
        Tuple of (wrapped_transform, offset) where:
        - wrapped_transform: Transform with offset applied (or original if no offset)
        - offset: Calculated offset tuple (x, y, z) or None if no offset needed

    Example:
        >>> # Buildings at ~40km from origin
        >>> wrapped_transform, offset = compute_offset_and_wrap_transform(
        ...     buildings, xyz_transform, debug=True
        ... )
        >>> # [PRESCAN] Distance from origin: 40123.456 m (40.123 km)
        >>> # [PRESCAN] ✓ Offset calculated: (-40000.0, -5000.0, -10.0) meters
        >>> offset
        (-40000.0, -5000.0, -10.0)

    Notes:
        - Uses RECENTERING_DISTANCE_THRESHOLD (1.0m) from constants
        - Always logs PHASE:0 header for debugging
        - Tests wrapped transform with sample coordinate if debug=True
        - Returns offset-only transform if no xyz_transform provided
    """
    # Always log PHASE:0 header (critical for debugging coordinate issues)
    log(f"\n{'='*80}")
    log(f"[PHASE:0] PRE-SCAN FOR COORDINATE RE-CENTERING")
    log(f"{'='*80}")

    # Scan all polygon coordinates from buildings
    raw_coords = []
    for b in buildings:
        for poly in b.findall(".//gml:Polygon", NS):
            ext, holes = extract_polygon_xyz(poly)
            raw_coords.extend(ext)
            for hole in holes:
                raw_coords.extend(hole)

    if not raw_coords:
        log(f"[PRESCAN] ⚠ No polygon coordinates found, skipping re-centering")
        return xyz_transform, None

    log(f"[PRESCAN] Scanned {len(raw_coords)} coordinates from {len(buildings)} buildings")

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

    if not (xs and ys and zs):
        log(f"[PRESCAN] ⚠ Invalid coordinates, skipping re-centering")
        return xyz_transform, None

    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0
    center_z = (min(zs) + max(zs)) / 2.0

    distance_from_origin = (center_x**2 + center_y**2 + center_z**2) ** 0.5

    # Always log bounding box info (critical for diagnosing precision issues)
    log(f"[PRESCAN] Bounding box center: ({center_x:.3f}, {center_y:.3f}, {center_z:.3f}) meters")
    log(f"[PRESCAN] Distance from origin: {distance_from_origin:.3f} m ({distance_from_origin/1000:.3f} km)")

    # Apply offset if significantly far from origin (> threshold)
    if distance_from_origin > RECENTERING_DISTANCE_THRESHOLD:
        coord_offset = (-center_x, -center_y, -center_z)

        log(f"[PRESCAN] ✓ Offset calculated: ({coord_offset[0]:.3f}, {coord_offset[1]:.3f}, {coord_offset[2]:.3f}) meters")
        log(f"[PRESCAN] This will re-center geometry to origin for numerical precision")

        # Wrap xyz_transform with offset
        if xyz_transform:
            original_transform = xyz_transform

            def wrapped_transform(x: float, y: float, z: float) -> Tuple[float, float, float]:
                tx, ty, tz = original_transform(x, y, z)
                return (tx + coord_offset[0], ty + coord_offset[1], tz + coord_offset[2])

            log(f"[PRESCAN] ✓ Wrapped xyz_transform with offset")

            # Test the wrapped transform with a sample coordinate
            if debug and raw_coords:
                test_x, test_y, test_z = raw_coords[0]
                orig_result = original_transform(test_x, test_y, test_z)
                wrapped_result = wrapped_transform(test_x, test_y, test_z)
                log(f"[PRESCAN] DEBUG: Sample coordinate ({test_x:.3f}, {test_y:.3f}, {test_z:.3f})")
                log(f"[PRESCAN] DEBUG: Original transform → ({orig_result[0]:.3f}, {orig_result[1]:.3f}, {orig_result[2]:.3f})")
                log(f"[PRESCAN] DEBUG: Wrapped transform → ({wrapped_result[0]:.3f}, {wrapped_result[1]:.3f}, {wrapped_result[2]:.3f})")

            return wrapped_transform, coord_offset
        else:
            # No xyz_transform, create offset-only transform
            def offset_transform(x: float, y: float, z: float) -> Tuple[float, float, float]:
                return (x + coord_offset[0], y + coord_offset[1], z + coord_offset[2])

            log(f"[PRESCAN] ✓ Created offset-only transform (no xyz_transform)")

            return offset_transform, coord_offset
    else:
        log(f"[PRESCAN] Coordinates already near origin, no offset needed")
        return xyz_transform, None
