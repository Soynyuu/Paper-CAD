"""
Tolerance computation for OpenCASCADE geometry operations.

This module provides functions to compute appropriate tolerance values based on
coordinate extent and precision mode. Tolerance is critical for OpenCASCADE operations
like sewing, shape fixing, and boolean operations.

The tolerance scales with geometry size and precision requirements:
- Larger geometries → larger tolerances
- Higher precision modes → smaller tolerances (more detail preservation)
"""

from typing import List, Tuple, Optional, Any

from ..core.constants import PRECISION_MODE_FACTORS


def compute_tolerance_from_coords(
    coords: List[Tuple[float, float, float]], precision_mode: str = "standard"
) -> float:
    """
    Compute appropriate tolerance based on coordinate extent and precision mode.

    The tolerance is calculated as a percentage of the maximum extent (X, Y, or Z range)
    of the input coordinates. The percentage depends on the precision mode.

    Args:
        coords: List of (x, y, z) coordinate tuples
        precision_mode: Precision level
            - "standard": 0.01% of extent (balanced, default)
            - "high": 0.001% of extent (preserves fine details)
            - "maximum": 0.0001% of extent (maximum detail preservation)
            - "ultra": 0.00001% of extent (ultra-precision for LOD2/LOD3)

    Returns:
        Computed tolerance value (clamped to reasonable range based on precision mode)

    Example:
        >>> # Building with 100m extent
        >>> coords = [(0, 0, 0), (100, 100, 50)]
        >>> compute_tolerance_from_coords(coords, "standard")
        0.01  # 0.01% of 100m = 0.01m = 1cm

        >>> compute_tolerance_from_coords(coords, "ultra")
        0.00001  # 0.00001% of 100m = 0.00001m = 10μm

    Notes:
        - Minimum tolerance: 1e-9 (ultra), 1e-8 (maximum), 1e-7 (high), 1e-6 (standard)
        - Maximum tolerance: 1.0 (ultra), 5.0 (maximum), 10.0 (high/standard)
        - If coords is empty, returns fallback value based on precision mode
    """
    if not coords:
        # Fallback values when no coordinates are provided
        fallback = {
            "ultra": 0.00001,
            "maximum": 0.0001,
            "high": 0.001,
            "standard": 0.01,
        }
        return fallback.get(precision_mode, 0.01)

    # Compute bounding box extents
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]

    x_extent = max(xs) - min(xs) if xs else 0.0
    y_extent = max(ys) - min(ys) if ys else 0.0
    z_extent = max(zs) - min(zs) if zs else 0.0

    # Use maximum extent across all dimensions
    extent = max(x_extent, y_extent, z_extent)

    # Get tolerance percentage from precision mode
    percentage = PRECISION_MODE_FACTORS.get(
        precision_mode, PRECISION_MODE_FACTORS["standard"]
    )

    tolerance = extent * percentage

    # Clamp to reasonable range based on precision mode
    # Tighter bounds for higher precision modes
    if precision_mode == "ultra":
        min_tol = 1e-9
        max_tol = 1.0
    elif precision_mode == "maximum":
        min_tol = 1e-8
        max_tol = 5.0
    elif precision_mode == "high":
        min_tol = 1e-7
        max_tol = 10.0
    else:  # standard or unknown
        min_tol = 1e-6
        max_tol = 10.0

    tolerance = max(min_tol, min(tolerance, max_tol))

    return tolerance


def compute_tolerance_from_face_list(
    faces: List[Any],  # List["TopoDS_Face"] but avoid import
    precision_mode: str = "standard",
) -> float:
    """
    Compute tolerance from a list of OpenCASCADE faces by sampling their vertices.

    This function extracts coordinates from face vertices (up to 100 samples)
    and computes tolerance using compute_tolerance_from_coords().

    Args:
        faces: List of TopoDS_Face objects
        precision_mode: Precision level ("standard", "high", "maximum", "ultra")

    Returns:
        Computed tolerance value

    Example:
        >>> from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        >>> # ... create some faces ...
        >>> tolerance = compute_tolerance_from_face_list(faces, "high")
        >>> tolerance
        0.001

    Notes:
        - Samples up to 100 vertices to avoid performance issues with large face lists
        - If no vertices can be extracted, returns fallback value
        - Requires OpenCASCADE (pythonOCC) to be available
    """
    # Import OpenCASCADE modules (only when this function is called)
    try:
        from OCC.Core.BRepTools import BRepTools_WireExplorer
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_WIRE
    except ImportError:
        # Fallback if OpenCASCADE is not available
        fallback = {
            "ultra": 0.00001,
            "maximum": 0.0001,
            "high": 0.001,
            "standard": 0.01,
        }
        return fallback.get(precision_mode, 0.01)

    # Sample up to 100 vertices from faces for tolerance computation
    coords: List[Tuple[float, float, float]] = []
    sample_limit = 100

    for face in faces:
        if len(coords) >= sample_limit:
            break

        # Explore wires in face
        wire_exp = TopExp_Explorer(face, TopAbs_WIRE)
        while wire_exp.More() and len(coords) < sample_limit:
            wire = wire_exp.Current()
            wire_explorer = BRepTools_WireExplorer(wire)

            # Extract vertices from wire
            while wire_explorer.More() and len(coords) < sample_limit:
                vertex = wire_explorer.CurrentVertex()
                pnt = BRep_Tool.Pnt(vertex)
                coords.append((pnt.X(), pnt.Y(), pnt.Z()))
                wire_explorer.Next()

            wire_exp.Next()

    if coords:
        return compute_tolerance_from_coords(coords, precision_mode)
    else:
        # Fallback if no coordinates could be extracted
        fallback = {
            "ultra": 0.00001,
            "maximum": 0.0001,
            "high": 0.001,
            "standard": 0.01,
        }
        return fallback.get(precision_mode, 0.01)


def compute_building_tolerance(
    building_elem: "ET.Element",
    xyz_transform: Optional[Any] = None,
    precision_mode: str = "standard",
    sample_limit: int = 50,
) -> float:
    """
    Precompute tolerance for an entire building by sampling polygon coordinates.

    This avoids calling compute_tolerance_from_coords() per-polygon during face
    extraction, which is a significant performance win for buildings with many faces.
    The bounding box extent of the entire building gives a better tolerance estimate
    than individual polygon extents anyway.

    Issue #192: Performance optimization - compute once per building, not per polygon.

    Args:
        building_elem: Building XML element to sample coordinates from
        xyz_transform: Optional coordinate transformation (applied before computing extent)
        precision_mode: Precision level ("standard", "high", "maximum", "ultra")
        sample_limit: Maximum number of polygons to sample (50 is sufficient for
            accurate bounding box estimation)

    Returns:
        Computed tolerance value based on building extent and precision mode
    """
    import xml.etree.ElementTree as ET
    from ..core.constants import NS
    from ..parsers.coordinates import extract_polygon_xyz

    sampled_coords: List[Tuple[float, float, float]] = []
    polygon_count = 0

    for poly in building_elem.iter(f"{{{NS['gml']}}}Polygon"):
        if polygon_count >= sample_limit:
            break
        ext, _ = extract_polygon_xyz(poly)
        if not ext:
            continue
        # Apply coordinate transform if provided
        if xyz_transform:
            try:
                ext = [tuple(map(float, xyz_transform(x, y, z))) for (x, y, z) in ext]
            except Exception:
                continue
        sampled_coords.extend(ext)
        polygon_count += 1

    return compute_tolerance_from_coords(sampled_coords, precision_mode)


def get_precision_mode_description(precision_mode: str) -> str:
    """
    Get a human-readable description of a precision mode.

    Args:
        precision_mode: Precision mode name

    Returns:
        Description string

    Example:
        >>> get_precision_mode_description("ultra")
        '0.00001% of extent (ultra-precision for LOD2/LOD3)'
    """
    descriptions = {
        "standard": "0.01% of extent (balanced, default)",
        "high": "0.001% of extent (preserves fine details)",
        "maximum": "0.0001% of extent (maximum detail preservation)",
        "ultra": "0.00001% of extent (ultra-precision for LOD2/LOD3)",
    }
    return descriptions.get(precision_mode, "Unknown precision mode")
