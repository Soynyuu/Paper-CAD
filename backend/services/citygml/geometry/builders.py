"""
Basic Wire and Face construction utilities using OpenCASCADE.

This module provides low-level functions to create OpenCASCADE geometric
primitives (wires and faces) from coordinate lists. These are the building
blocks for more complex geometry operations.
"""

from typing import List, Tuple, Optional, Any

from ..utils.logging import log


def wire_from_coords_xy(coords: List[Tuple[float, float]]) -> Any:  # TopoDS_Wire
    """
    Create a closed wire from 2D coordinates (z=0).

    Args:
        coords: List of (x, y) tuples in meters

    Returns:
        TopoDS_Wire (closed polygon)

    Example:
        >>> coords = [(0, 0), (100, 0), (100, 100), (0, 100)]
        >>> wire = wire_from_coords_xy(coords)

    Notes:
        - Automatically removes duplicate closing point if present
        - All points are placed at z=0
        - Wire is automatically closed
    """
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.gp import gp_Pnt

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


def wire_from_coords_xyz(
    coords: List[Tuple[float, float, float]],
    debug: bool = False
) -> Optional[Any]:  # Optional[TopoDS_Wire]
    """
    Create a closed wire from 3D coordinates.

    Args:
        coords: List of (x, y, z) tuples in meters
        debug: Enable debug output

    Returns:
        TopoDS_Wire (closed polygon) or None if creation fails

    Example:
        >>> coords = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 10)]
        >>> wire = wire_from_coords_xyz(coords, debug=True)

    Notes:
        - Automatically removes duplicate closing point if present
        - Wire is automatically closed
        - Returns None if creation fails (e.g., insufficient points)
    """
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCC.Core.gp import gp_Pnt

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

        for x, y, z in pts:
            poly.Add(gp_Pnt(float(x), float(y), float(z)))

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


def face_from_xyz_rings(
    ext: List[Tuple[float, float, float]],
    holes: List[List[Tuple[float, float, float]]],
    debug: bool = False,
    planar_check: bool = False
) -> Optional[Any]:  # Optional[TopoDS_Face]
    """
    Create a face from 3D polygon rings (exterior + optional holes).

    Args:
        ext: Exterior ring coordinates
        holes: List of interior ring (hole) coordinates
        debug: Enable debug output
        planar_check: Enforce strict planarity check
            - False: Allow non-planar faces (more permissive, recommended for LOD2)
            - True: Reject non-planar faces (stricter, may fail for complex geometry)

    Returns:
        TopoDS_Face or None if creation fails

    Example:
        >>> ext = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
        >>> hole = [(20, 20, 0), (80, 20, 0), (80, 80, 0), (20, 80, 0)]
        >>> face = face_from_xyz_rings(ext, [hole], debug=True)

    Notes:
        - planar_check=False is important for LOD2 complex geometry with slight non-planarity
        - Failed hole creation is logged but does not fail the entire face
        - Outer wire creation failure causes face creation to fail
    """
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    try:
        # Create outer wire
        outer = wire_from_coords_xyz(ext, debug=debug)
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
                hole_wire = wire_from_coords_xyz(hole, debug=debug)
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


def triangulate_polygon_fan(
    vertices: List[Tuple[float, float, float]]
) -> List[List[Tuple[float, float, float]]]:
    """
    Triangulate a polygon using fan triangulation.

    Fan triangulation uses the first vertex as a pivot and creates triangles
    by connecting it to consecutive pairs of remaining vertices. This is simple,
    robust, and works well for convex polygons and most concave polygons.

    Args:
        vertices: List of polygon vertices (at least 3)

    Returns:
        List of triangles, each triangle is a list of 3 vertices

    Example:
        >>> vertices = [(0,0,0), (1,0,0), (1,1,0), (0.5,1.5,0), (0,1,0)]
        >>> triangles = triangulate_polygon_fan(vertices)
        >>> len(triangles)
        3
        >>> triangles[0]
        [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        >>> triangles[1]
        [(0, 0, 0), (1, 1, 0), (0.5, 1.5, 0)]
        >>> triangles[2]
        [(0, 0, 0), (0.5, 1.5, 0), (0, 1, 0)]

    Algorithm:
        For 7 vertices → 5 triangles:
        - Triangle 0: [v0, v1, v2]
        - Triangle 1: [v0, v2, v3]
        - Triangle 2: [v0, v3, v4]
        - Triangle 3: [v0, v4, v5]
        - Triangle 4: [v0, v5, v6]

    Notes:
        - Returns empty list if fewer than 3 vertices
        - Returns [vertices] if exactly 3 vertices (already a triangle)
        - For n vertices, creates n-2 triangles
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


def project_to_best_fit_plane(
    vertices: List[Tuple[float, float, float]],
    tolerance: float
) -> Tuple[List[Tuple[float, float, float]], Tuple[float, float, float]]:
    """
    Project polygon vertices onto their best-fit plane.

    This computes the optimal plane that minimizes the distance to all vertices,
    then projects each vertex onto that plane. This corrects minor non-planarity
    while preserving the original shape as much as possible.

    Args:
        vertices: List of polygon vertices
        tolerance: Geometric tolerance (kept for API consistency, not directly used)

    Returns:
        Tuple of:
        - List of projected vertices (guaranteed to be coplanar)
        - Plane normal vector (nx, ny, nz)

    Example:
        >>> # Slightly non-planar polygon
        >>> vertices = [(0,0,0), (100,0,0.1), (100,100,-0.1), (0,100,0)]
        >>> projected, normal = project_to_best_fit_plane(vertices, tolerance=0.01)
        >>> normal
        (0.0, 0.0, 1.0)
        >>> # All projected vertices now lie on the same plane

    Raises:
        Exception if plane fitting fails

    Notes:
        - Uses OpenCASCADE's GeomPlate_BuildAveragePlane for robust plane fitting
        - Automatically falls back to original vertex if projection fails
        - Preserves vertex order
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
