"""
BuildingPart merging module - fuses multiple BuildingParts into single solids.

This module handles the complex Boolean fusion logic for combining multiple
BuildingPart geometries into a single solid shape. It's a critical component
for CityGML buildings with complex part structures.

Extracted from original citygml_to_step.py lines 3222-3480 (Phase 2 refactoring).
"""

from typing import List, Optional, Any
import xml.etree.ElementTree as ET

from ..utils.logging import log

# Check OCCT availability
try:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Compound
    OCCT_AVAILABLE = True
except ImportError:
    OCCT_AVAILABLE = False
    TopoDS_Shape = Any


def extract_building_and_parts(
    building: ET.Element,
    extract_single_solid_fn,
    xyz_transform=None,
    id_index=None,
    debug: bool = False,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal"
) -> List[Any]:  # List[TopoDS_Shape]
    """
    Extract geometry from a Building and all its BuildingParts.

    This function recursively extracts:
    1. Geometry from the main Building element
    2. Geometry from all bldg:BuildingPart child elements

    Args:
        building: bldg:Building element
        extract_single_solid_fn: Function to extract solid from single building/part
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness

    Returns:
        List of TopoDS_Shape objects (one per Building/BuildingPart)

    Example:
        >>> shapes = extract_building_and_parts(
        ...     building_elem,
        ...     extract_lod_geometry,  # Function that extracts single building
        ...     xyz_transform,
        ...     id_index,
        ...     debug=True
        ... )
        >>> len(shapes)
        3  # Main building + 2 BuildingParts

    Notes:
        - Returns empty list if no geometry found
        - Each shape in the list represents one building/part
        - Caller is responsible for fusing or compounding the shapes
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE is required for building extraction")

    # Import namespace
    from ..core.constants import NS

    shapes: List[Any] = []  # List[TopoDS_Shape]

    # Extract from main Building
    main_shape = extract_single_solid_fn(
        building, xyz_transform, id_index, debug, precision_mode, shape_fix_level
    )
    if main_shape is not None:
        shapes.append(main_shape)
        if debug:
            log("[BUILDING] Extracted geometry from main Building element")

    # Extract from all BuildingParts
    building_parts = building.findall(".//bldg:BuildingPart", NS)
    if building_parts:
        if debug:
            log(f"[BUILDING] Found {len(building_parts)} BuildingPart(s)")

        for i, part in enumerate(building_parts):
            part_shape = extract_single_solid_fn(
                part, xyz_transform, id_index, debug, precision_mode, shape_fix_level
            )
            if part_shape is not None:
                shapes.append(part_shape)
                if debug:
                    part_id = part.get("{http://www.opengis.net/gml}id") or f"part_{i+1}"
                    log(f"[BUILDING] Extracted geometry from BuildingPart: {part_id}")

    return shapes


def fuse_shapes(shapes: List[Any], debug: bool = False) -> Optional[Any]:
    """
    Fuse multiple shapes into a single solid using Boolean union operations.

    This function iteratively fuses shapes using BRepAlgoAPI_Fuse. If fusion fails,
    it falls back to creating a compound.

    ⚠️ CRITICAL: This is a computationally expensive operation. Fusion can fail
    for complex geometries or shapes with topology errors. Always validate input
    shapes before calling this function.

    Args:
        shapes: List of TopoDS_Shape objects to fuse
        debug: Enable debug output

    Returns:
        Fused solid shape, or compound if fusion fails, or None if all shapes invalid

    Example:
        >>> part1 = make_solid_from_faces(faces1, ...)
        >>> part2 = make_solid_from_faces(faces2, ...)
        >>> fused = fuse_shapes([part1, part2], debug=True)
        >>> # [PHASE:6] BUILDINGPART FUSION (Boolean Union)
        >>> # [STEP 1/2] Using first BuildingPart as base
        >>> # [STEP 2/2] Fusing BuildingPart 2...
        >>> # [VALIDATION] ✓ Fused shape is valid
        >>> # ✓ Successfully fused all 2 BuildingParts

    Notes:
        - Performs iterative pairwise fusion (A ∪ B ∪ C = (A ∪ B) ∪ C)
        - Falls back to compound if any fusion operation fails
        - Validates topology after each fusion step
        - Returns None if all input shapes are invalid
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE is required for shape fusion")

    # Filter out None and null shapes
    valid_shapes = [s for s in shapes if s is not None and not s.IsNull()]

    if not valid_shapes:
        if debug:
            log("[FUSE] No valid shapes to fuse")
        return None

    if len(valid_shapes) == 1:
        if debug:
            log("[FUSE] Only one shape, returning as-is")
        return valid_shapes[0]

    log(f"\n{'='*80}")
    log(f"[PHASE:6] BUILDINGPART FUSION (Boolean Union)")
    log(f"{'='*80}")
    log(f"[INFO] Number of parts to fuse: {len(valid_shapes)}")
    log(f"")

    try:
        # Start with the first shape
        result = valid_shapes[0]
        log(f"[STEP 1/{len(valid_shapes)}] Using first BuildingPart as base")

        # Iteratively fuse with remaining shapes
        for i, shape in enumerate(valid_shapes[1:], start=2):
            log(f"\n[STEP {i}/{len(valid_shapes)}] Fusing BuildingPart {i}...")
            log(f"├─ [GEOMETRY] Attempting Boolean Fuse operation...")

            try:
                fuse_op = BRepAlgoAPI_Fuse(result, shape)

                if fuse_op.IsDone():
                    result = fuse_op.Shape()

                    # Validate fused result
                    analyzer = BRepCheck_Analyzer(result)
                    if analyzer.IsValid():
                        log(f"├─ [VALIDATION] ✓ Fused shape is valid")
                        log(f"└─ [RESULT] ✓ Fusion succeeded")
                    else:
                        log(f"├─ [VALIDATION] ⚠ Fused shape is invalid (but continuing)")
                        log(f"└─ [RESULT] ⚠ Fusion succeeded with invalid topology")
                else:
                    log(f"├─ [ERROR] ✗ BRepAlgoAPI_Fuse.IsDone() returned False")
                    log(f"├─ [DECISION] → Fusion operation failed, cannot continue")
                    log(f"└─ [FALLBACK] Creating compound instead of fused solid")
                    return create_compound(valid_shapes, debug)

            except Exception as e:
                log(f"├─ [ERROR] ✗ Exception during fusion")
                log(f"├─ [ERROR] Exception type: {type(e).__name__}")
                log(f"├─ [ERROR] Exception message: {str(e)}")
                if debug:
                    import traceback
                    log(f"├─ [ERROR] Traceback:")
                    for line in traceback.format_exc().split('\n'):
                        if line.strip():
                            log(f"│  {line}")
                log(f"└─ [FALLBACK] Creating compound instead of fused solid")
                return create_compound(valid_shapes, debug)

        log(f"\n{'='*80}")
        log(f"[PHASE:6] FUSION SUMMARY")
        log(f"{'='*80}")
        log(f"[RESULT] ✓ Successfully fused all {len(valid_shapes)} BuildingParts")

        # Final validation
        final_analyzer = BRepCheck_Analyzer(result)
        if final_analyzer.IsValid():
            log(f"[VALIDATION] ✓ Final fused solid is topologically valid")
        else:
            log(f"[VALIDATION] ⚠ Final fused solid has topology issues")
        log(f"")

        return result

    except Exception as e:
        log(f"\n[ERROR] ✗ Unexpected exception in fusion process")
        log(f"[ERROR] Exception type: {type(e).__name__}")
        log(f"[ERROR] Exception message: {str(e)}")
        if debug:
            import traceback
            log(f"[ERROR] Traceback:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    log(f"  {line}")
        log(f"[FALLBACK] Creating compound instead of fused solid")
        return create_compound(valid_shapes, debug)


def create_compound(shapes: List[Any], debug: bool = False) -> Optional[Any]:
    """
    Create a compound from multiple shapes.

    A compound is a collection of shapes that maintains their individual identities
    (unlike fusion which creates a single unified solid). This is useful when:
    - Fusion fails due to topology errors
    - Individual BuildingParts need to be preserved
    - Boolean operations are too expensive

    Args:
        shapes: List of TopoDS_Shape objects
        debug: Enable debug output

    Returns:
        Compound shape containing all valid input shapes, or None if no valid shapes

    Example:
        >>> shapes = [solid1, solid2, solid3]
        >>> compound = create_compound(shapes, debug=True)
        >>> # [COMPOUND] Created compound with 3 shapes

    Notes:
        - Filters out None and null shapes automatically
        - Returns single shape directly if only one valid shape
        - All shapes in compound maintain separate topology
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE is required for compound creation")

    # Filter out None and null shapes
    valid_shapes = [s for s in shapes if s is not None and not s.IsNull()]

    if not valid_shapes:
        if debug:
            log("[COMPOUND] No valid shapes to create compound")
        return None

    if len(valid_shapes) == 1:
        if debug:
            log("[COMPOUND] Only one shape, returning as-is")
        return valid_shapes[0]

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for shp in valid_shapes:
        builder.Add(compound, shp)

    if debug:
        log(f"[COMPOUND] Created compound with {len(valid_shapes)} shapes")

    return compound


def merge_building_parts(
    building: ET.Element,
    extract_single_solid_fn,
    xyz_transform=None,
    id_index=None,
    debug: bool = False,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal",
    merge_parts: bool = True
) -> Optional[Any]:
    """
    High-level function to extract and merge BuildingParts from a Building element.

    This orchestrates the complete BuildingPart extraction and merging pipeline:
    1. Extract geometry from main Building + all BuildingParts
    2. If multiple shapes: fuse into single solid OR create compound
    3. If single shape: return directly

    Args:
        building: bldg:Building element
        extract_single_solid_fn: Function to extract solid from single element
        xyz_transform: Optional coordinate transformation function
        id_index: Optional XLink resolution index
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness
        merge_parts: If True, fuse parts; if False, create compound

    Returns:
        Single TopoDS_Shape (fused solid, compound, or individual shape), or None

    Example:
        >>> shape = merge_building_parts(
        ...     building_elem,
        ...     extract_lod_geometry,
        ...     xyz_transform,
        ...     id_index,
        ...     debug=True,
        ...     merge_parts=True  # Fuse into single solid
        ... )
        >>> # [BUILDING] Found 2 BuildingPart(s)
        >>> # [PHASE:6] BUILDINGPART FUSION (Boolean Union)
        >>> # ✓ Successfully fused all 3 shapes

    Notes:
        - merge_parts=True: Use Boolean fusion (slower, single solid)
        - merge_parts=False: Use compound (faster, preserves parts)
        - Returns None if no geometry found
    """
    if not OCCT_AVAILABLE:
        raise RuntimeError("OpenCASCADE is required for BuildingPart merging")

    # Extract all shapes
    shapes = extract_building_and_parts(
        building,
        extract_single_solid_fn,
        xyz_transform,
        id_index,
        debug,
        precision_mode,
        shape_fix_level
    )

    if not shapes:
        return None

    # If only one shape, return it directly
    if len(shapes) == 1:
        return shapes[0]

    # Multiple shapes: fuse or create compound based on parameter
    if merge_parts:
        if debug:
            log(f"[BUILDING] Merging {len(shapes)} BuildingParts into single solid...")
        return fuse_shapes(shapes, debug)
    else:
        if debug:
            log(f"[BUILDING] Keeping {len(shapes)} BuildingParts as separate shapes in compound...")
        return create_compound(shapes, debug)
