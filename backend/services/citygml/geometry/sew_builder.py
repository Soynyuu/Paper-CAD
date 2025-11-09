"""
Surface sewing module - builds solids from individual LOD2 surfaces.

This module implements the "sew" conversion method which:
1. Extracts individual BoundarySurface polygons (Wall, Roof, Ground)
2. Creates faces from polygons
3. Sews faces together using BRepBuilderAPI_Sewing
4. Attempts to create solids from closed shells
5. Returns compound of solids or sewn shape

This is a fallback method when LOD solid data is not available or incomplete.

Extracted from original citygml_to_step.py lines 3483-3603 (Phase 2 refactoring).
"""

from typing import List, Optional, Callable, Any
import xml.etree.ElementTree as ET

from ..core.constants import NS
from ..utils.logging import log
from ..parsers.coordinates import extract_polygon_xyz
from ..geometry.builders import face_from_xyz_rings
from ..geometry.tolerance import compute_tolerance_from_face_list

# Check OCCT availability
try:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeFix import ShapeFix_Shape
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SHELL
    from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    OCCT_AVAILABLE = True
except ImportError:
    OCCT_AVAILABLE = False
    TopoDS_Face = Any
    TopoDS_Shape = Any


def build_sewn_shape_from_building(
    building: ET.Element,
    sew_tolerance: Optional[float] = None,
    debug: bool = False,
    xyz_transform: Optional[Callable] = None,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal"
) -> Optional[Any]:  # Optional[TopoDS_Shape]
    """
    Build a sewn shape (and solids if possible) from LOD2 surfaces of a building.

    This function implements the "sew" conversion method:
    1. Collects bldg:WallSurface, bldg:RoofSurface, bldg:GroundSurface polygons
    2. Creates faces with interior holes
    3. Sews faces together using tolerance-based edge matching
    4. Attempts to close shells into solids
    5. Returns compound of solids (if successful) or sewn shell

    ⚠️ CRITICAL: This method requires high-quality LOD2 BoundarySurface data.
    It may fail if surfaces have gaps or topology issues. Consider using
    the "solid" method (LOD2Solid extraction) as the primary approach.

    Args:
        building: bldg:Building element
        sew_tolerance: Sewing tolerance in meters (auto-computed if None)
        debug: Enable debug output
        xyz_transform: Optional coordinate transformation function (x,y,z)→(X,Y,Z)
        precision_mode: Precision level for auto-tolerance computation
        shape_fix_level: Shape fixing aggressiveness

    Returns:
        TopoDS_Shape (compound of solids or sewn shell), or None if no faces

    Example:
        >>> from pyproj import Transformer
        >>> transformer = Transformer.from_crs("EPSG:4326", "EPSG:6676")
        >>> def xyz_tx(x, y, z):
        ...     X, Y = transformer.transform(x, y)
        ...     return X, Y, z
        >>> shape = build_sewn_shape_from_building(
        ...     building_elem,
        ...     sew_tolerance=None,  # Auto-compute
        ...     debug=True,
        ...     xyz_transform=xyz_tx,
        ...     precision_mode="high",
        ...     shape_fix_level="standard"
        ... )
        >>> # Auto-computed sewing tolerance: 0.015000 (precision_mode: high)
        >>> # Shape fixing applied to sewn shape (level: standard)
        >>> # Created 1 solid from shells

    Notes:
        - Collects surfaces from WallSurface, RoofSurface, GroundSurface
        - Auto-computes tolerance based on face extents if not provided
        - Applies shape fixing based on shape_fix_level (minimal/standard/aggressive)
        - Returns None if no faces can be created
        - May return sewn shell instead of solid if shells cannot be closed
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE (pythonocc-core) is required for surface sewing")

    # Collect all boundary surfaces
    surfaces = []
    for surf_tag in ["bldg:WallSurface", "bldg:RoofSurface", "bldg:GroundSurface"]:
        surfaces += building.findall(f".//{surf_tag}", NS)

    if debug:
        log(f"[SEW] Found {len(surfaces)} boundary surfaces (Wall/Roof/Ground)")

    # Create faces from surfaces
    faces: List[Any] = []  # List[TopoDS_Face]
    skipped = 0

    for s in surfaces:
        for poly in s.findall(".//gml:Polygon", NS):
            ext, holes = extract_polygon_xyz(poly)
            if len(ext) < 3:
                skipped += 1
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
                        log(f"[SEW] Transform failed for polygon: {e}")
                    skipped += 1
                    continue

            # Create face (planar_check=False for complex LOD2 geometry)
            fc = face_from_xyz_rings(ext, holes, debug=debug, planar_check=False)
            if fc is not None and not fc.IsNull():
                faces.append(fc)
            else:
                skipped += 1

    if not faces:
        if debug:
            log(f"[SEW] No valid faces created from {len(surfaces)} surfaces")
        return None

    if debug:
        log(f"[SEW] Created {len(faces)} faces ({skipped} skipped)")

    # Auto-compute tolerance if not provided
    if sew_tolerance is None:
        sew_tolerance = compute_tolerance_from_face_list(faces, precision_mode)
        if debug:
            log(f"[SEW] Auto-computed sewing tolerance: {sew_tolerance:.6f} (precision_mode: {precision_mode})")

    # Sew faces together
    if debug:
        log(f"[SEW] Sewing {len(faces)} faces with tolerance {sew_tolerance:.6f}...")

    sewing = BRepBuilderAPI_Sewing(sew_tolerance, True, True, True, False)
    for fc in faces:
        sewing.Add(fc)
    sewing.Perform()
    sewn = sewing.SewedShape()

    if debug:
        log(f"[SEW] Sewing complete")

    # Apply shape fixing based on level
    if shape_fix_level != "minimal":
        try:
            if debug:
                log(f"[SEW] Applying shape fixing (level: {shape_fix_level})...")

            fixer = ShapeFix_Shape(sewn)

            # Configure fixer based on level
            if shape_fix_level == "standard":
                fixer.SetPrecision(sew_tolerance)
                fixer.SetMaxTolerance(sew_tolerance * 10.0)
            elif shape_fix_level == "aggressive":
                fixer.SetPrecision(sew_tolerance * 10.0)
                fixer.SetMaxTolerance(sew_tolerance * 100.0)
            elif shape_fix_level == "ultra":
                fixer.SetPrecision(sew_tolerance * 100.0)
                fixer.SetMaxTolerance(sew_tolerance * 1000.0)

            fixer.Perform()
            sewn = fixer.Shape()

            if debug:
                log(f"[SEW] Shape fixing applied")
        except Exception as e:
            if debug:
                log(f"[SEW] ShapeFix_Shape failed: {e}")

    # Try to make solids from shells
    solids: List[Any] = []  # List[TopoDS_Shape]
    exp = TopExp_Explorer(sewn, TopAbs_SHELL)

    shell_count = 0
    while exp.More():
        shell_count += 1
        # Downcast shape -> shell
        shell = topods.Shell(exp.Current())
        try:
            analyzer = BRepCheck_Analyzer(shell)
            if analyzer.IsValid():
                mk = BRepBuilderAPI_MakeSolid()
                mk.Add(shell)
                solid = mk.Solid()
                if solid is not None and not solid.IsNull():
                    solids.append(solid)
                    if debug:
                        log(f"[SEW] Shell {shell_count} → solid (valid)")
                else:
                    if debug:
                        log(f"[SEW] Shell {shell_count} → solid creation failed (null)")
            else:
                if debug:
                    log(f"[SEW] Shell {shell_count} is invalid, cannot create solid")
        except Exception as e:
            if debug:
                log(f"[SEW] Shell {shell_count} → solid failed: {e}")
        exp.Next()

    if solids:
        if debug:
            log(f"[SEW] Created {len(solids)} solid(s) from {shell_count} shell(s)")

        # Return compound of solids
        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)
        for s in solids:
            builder.Add(compound, s)
        return compound
    else:
        if debug:
            log(f"[SEW] No solids created, returning sewn shape (shell/compound)")
        return sewn


def build_sewn_shapes_from_buildings(
    buildings: List[ET.Element],
    sew_tolerance: Optional[float] = None,
    debug: bool = False,
    xyz_transform: Optional[Callable] = None,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal",
    limit: Optional[int] = None
) -> List[Any]:  # List[TopoDS_Shape]
    """
    Convenience function to sew multiple buildings.

    Args:
        buildings: List of bldg:Building elements
        sew_tolerance: Sewing tolerance (auto-computed per building if None)
        debug: Enable debug output
        xyz_transform: Optional coordinate transformation function
        precision_mode: Precision level for auto-tolerance computation
        shape_fix_level: Shape fixing aggressiveness
        limit: Maximum number of buildings to process (None = unlimited)

    Returns:
        List of TopoDS_Shape objects (one per building)

    Example:
        >>> buildings = root.findall(".//bldg:Building", NS)
        >>> shapes = build_sewn_shapes_from_buildings(
        ...     buildings,
        ...     debug=True,
        ...     limit=100
        ... )
        >>> len(shapes)
        85  # Some buildings failed

    Notes:
        - Skips buildings where sewing fails
        - Each building gets independent tolerance computation
        - Returns only successfully sewn shapes
    """
    shapes = []
    count = 0

    for i, building in enumerate(buildings):
        if limit is not None and count >= limit:
            if debug:
                log(f"[SEW] Reached limit of {limit} buildings")
            break

        if debug:
            building_id = building.get("{http://www.opengis.net/gml}id") or f"building_{i}"
            log(f"\n[SEW] Processing building {i+1}/{len(buildings)}: {building_id}")

        try:
            shape = build_sewn_shape_from_building(
                building,
                sew_tolerance,
                debug,
                xyz_transform,
                precision_mode,
                shape_fix_level
            )

            if shape is not None and not shape.IsNull():
                shapes.append(shape)
                count += 1
                if debug:
                    log(f"[SEW] Success: {count} shapes created")
            else:
                if debug:
                    log(f"[SEW] Skipped: no valid shape created")

        except Exception as e:
            if debug:
                log(f"[SEW] Exception: {type(e).__name__}: {e}")
            continue

    if debug:
        log(f"\n[SEW] Total: {count} shapes created from {len(buildings)} buildings")

    return shapes
