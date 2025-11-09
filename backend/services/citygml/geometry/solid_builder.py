"""
Solid construction with cavities and auto-escalating repair (PHASE:3-5).

This module handles:
- PHASE:3: Shell construction from faces
- PHASE:4: Solid validation
- PHASE:5: Automatic repair with progressive escalation

⚠️ CRITICAL: This implements the 4-level auto-escalation repair strategy:
minimal → standard → aggressive → ultra

The repair escalation ensures maximum conversion success rate while maintaining
quality when possible.
"""

from typing import List, Optional, Any, Dict

from ..utils.logging import log
from .tolerance import compute_tolerance_from_face_list
from .shell_builder import build_shell_from_faces


def diagnose_shape_errors(shape: Any, debug: bool = False) -> Dict:
    """
    Diagnose detailed errors in a shape using BRepCheck_Analyzer.

    Args:
        shape: TopoDS_Shape to diagnose
        debug: Enable debug logging

    Returns:
        Dictionary with error information:
        - is_valid: Whether the shape is valid
        - free_edges_count: Number of edges not fully connected
        - invalid_faces: List of invalid face indices
        - shell_closed: Whether the shell is closed
        - error_summary: Summary statistics
        - exception: Exception message if diagnosis failed

    Example:
        >>> errors = diagnose_shape_errors(solid, debug=True)
        >>> # [DIAGNOSTICS] Shape validation failed:
        >>> #   - Total edges: 156, Free edges: 12
        >>> #   - Total faces: 74, Invalid faces: 2
        >>> #   - Shell closed: False
        >>> errors['free_edges_count']
        12

    Notes:
        - Free edges indicate gaps in the shell
        - Invalid faces indicate topology problems
        - A closed shell is necessary for solid creation
    """
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRep import BRep_Tool

    errors = {
        'is_valid': False,
        'free_edges_count': 0,
        'invalid_faces': [],
        'shell_closed': None,
        'error_summary': {}
    }

    try:
        analyzer = BRepCheck_Analyzer(shape)
        errors['is_valid'] = analyzer.IsValid()

        if not errors['is_valid']:
            # Count free edges (edges not fully connected)
            edge_exp = TopExp_Explorer(shape, TopAbs_EDGE)
            edge_count = 0
            free_edge_count = 0
            while edge_exp.More():
                edge = topods.Edge(edge_exp.Current())
                # Free edges are not closed (not shared by 2 faces)
                try:
                    if not BRep_Tool.IsClosed(edge, shape):
                        free_edge_count += 1
                except:
                    pass
                edge_count += 1
                edge_exp.Next()
            errors['free_edges_count'] = free_edge_count

            # Check faces
            face_exp = TopExp_Explorer(shape, TopAbs_FACE)
            face_count = 0
            while face_exp.More():
                face = topods.Face(face_exp.Current())
                face_analyzer = BRepCheck_Analyzer(face)
                if not face_analyzer.IsValid():
                    errors['invalid_faces'].append(face_count)
                face_count += 1
                face_exp.Next()

            # Check shell closure
            shell_exp = TopExp_Explorer(shape, TopAbs_SHELL)
            if shell_exp.More():
                shell = topods.Shell(shell_exp.Current())
                errors['shell_closed'] = BRep_Tool.IsClosed(shell)

            errors['error_summary'] = {
                'total_edges': edge_count,
                'free_edges': free_edge_count,
                'total_faces': face_count,
                'invalid_faces_count': len(errors['invalid_faces']),
                'shell_closed': errors['shell_closed']
            }

            if debug:
                log(f"[DIAGNOSTICS] Shape validation failed:")
                log(f"  - Total edges: {edge_count}, Free edges: {free_edge_count}")
                log(f"  - Total faces: {face_count}, Invalid faces: {len(errors['invalid_faces'])}")
                log(f"  - Shell closed: {errors['shell_closed']}")
    except Exception as e:
        errors['exception'] = str(e)
        if debug:
            log(f"[DIAGNOSTICS] Exception during diagnosis: {e}")

    return errors


def is_valid_shape(shape: Any) -> bool:
    """
    Check if a shape is a valid solid, shell, or compound.

    This is used to validate results from make_solid_with_cavities(), which can return
    solids, shells, or compounds depending on the geometry. All three types are acceptable
    for STEP export.

    Args:
        shape: TopoDS_Shape to validate

    Returns:
        True if shape is a valid solid, shell, or compound, False otherwise

    Example:
        >>> solid = make_solid_with_cavities(faces, [], tolerance, debug, "ultra", "ultra")
        >>> is_valid_shape(solid)
        True

    Notes:
        - Accepts SOLID, SHELL, and COMPOUND types
        - Rejects lower-level types (FACE, EDGE, VERTEX, etc.)
        - Uses BRepCheck_Analyzer for topology validation
        - Compounds may contain multiple disconnected parts (valid for export)
    """
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_SHELL, TopAbs_COMPOUND

    if shape is None:
        return False

    try:
        shape_type = shape.ShapeType()

        # Accept SOLID, SHELL, and COMPOUND (but not face, edge, etc.)
        if shape_type not in (TopAbs_SOLID, TopAbs_SHELL, TopAbs_COMPOUND):
            return False

        # Check if the shape is topologically valid
        # Note: Compounds may contain multiple disconnected parts, which is valid
        analyzer = BRepCheck_Analyzer(shape)
        return analyzer.IsValid()
    except Exception:
        return False


def make_solid_with_cavities(
    exterior_faces: List[Any],  # List[TopoDS_Face]
    interior_shells_faces: List[List[Any]],  # List[List[TopoDS_Face]]
    tolerance: Optional[float] = None,
    debug: bool = False,
    precision_mode: str = "auto",
    shape_fix_level: str = "standard"
) -> Optional[Any]:  # Optional[TopoDS_Shape]
    """
    Build a solid with cavities from exterior and interior shells.

    This function implements PHASE:3-5 of the conversion pipeline:
    - PHASE:3: Shell construction from faces
    - PHASE:4: Solid validation
    - PHASE:5: Automatic repair with auto-escalation

    ⚠️ CRITICAL: The auto-escalation repair strategy tries progressively more
    aggressive repair levels: minimal → standard → aggressive → ultra

    Args:
        exterior_faces: Faces forming the outer shell
        interior_shells_faces: List of face lists, each forming an interior shell (cavity)
        tolerance: Sewing tolerance (auto-computed if None)
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness (starting level for escalation)

    Returns:
        TopoDS_Solid or TopoDS_Shell (if solid construction fails) or None (if shell fails)

    Example:
        >>> solid = make_solid_with_cavities(
        ...     faces, interior_shells, None, True, "ultra", "standard"
        ... )
        >>> # [PHASE:3] Attempting to build exterior shell from 74 faces...
        >>> # [PHASE:4] SOLID VALIDATION
        >>> # [VALIDATION] ✓ Initial solid validation succeeded
        >>> is_valid_shape(solid)
        True

    Notes:
        - Auto-computes tolerance from face list if not provided
        - Builds exterior shell using build_shell_from_faces()
        - Attempts to create solid with BRepBuilderAPI_MakeSolid
        - Validates solid with BRepCheck_Analyzer
        - If validation fails, tries 4-level escalation repair
        - Returns shell if solid creation fails
        - Interior shells (cavities) are only added if they're closed
    """
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeFix import ShapeFix_Solid, ShapeFix_Shape
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    # Auto-compute tolerance if not provided
    if tolerance is None:
        tolerance = compute_tolerance_from_face_list(exterior_faces, precision_mode)
        if debug:
            log(f"Auto-computed tolerance: {tolerance:.6f} (precision_mode: {precision_mode})")

    # Build exterior shell
    if debug:
        log(f"Attempting to build exterior shell from {len(exterior_faces)} faces...")
    exterior_shell = build_shell_from_faces(exterior_faces, tolerance, debug, shape_fix_level)
    if exterior_shell is None:
        if debug:
            log(f"ERROR: Failed to build exterior shell (sewing or shell extraction failed)")
        return None

    # Check if exterior shell is closed
    try:
        is_closed = BRep_Tool.IsClosed(exterior_shell)
        if not is_closed:
            if debug:
                log(f"WARNING: Exterior shell is not closed, returning shell instead of solid")
        else:
            if debug:
                log(f"Exterior shell is closed, will attempt to create solid")
    except Exception as e:
        if debug:
            log(f"Failed to check if shell is closed: {e}")
        is_closed = False

    # Build interior shells
    interior_shells: List[Any] = []  # List[TopoDS_Shell]
    for i, int_faces in enumerate(interior_shells_faces):
        int_shell = build_shell_from_faces(int_faces, tolerance, debug, shape_fix_level)
        if int_shell is not None:
            try:
                if BRep_Tool.IsClosed(int_shell):
                    interior_shells.append(int_shell)
                    if debug:
                        log(f"Added interior shell {i+1} (closed)")
                else:
                    if debug:
                        log(f"Interior shell {i+1} is not closed, skipping")
            except Exception as e:
                if debug:
                    log(f"Interior shell {i+1} check failed: {e}")

    # Try to create solid
    if is_closed:
        try:
            mk_solid = BRepBuilderAPI_MakeSolid(exterior_shell)

            # Add interior shells (cavities)
            for int_shell in interior_shells:
                try:
                    mk_solid.Add(int_shell)
                except Exception as e:
                    if debug:
                        log(f"Failed to add interior shell: {e}")

            solid = mk_solid.Solid()

            # Validate solid
            log(f"\n[PHASE:4] SOLID VALIDATION")
            analyzer = BRepCheck_Analyzer(solid)
            if analyzer.IsValid():
                log(f"[VALIDATION] ✓ Initial solid validation succeeded")
                if debug:
                    log(f"[INFO] Created valid solid with {len(interior_shells)} cavities")
                return solid
            else:
                log(f"[VALIDATION] ✗ Initial solid validation failed")

                # Diagnose the specific errors
                if debug:
                    log(f"\n[PHASE:4.5] ERROR DIAGNOSIS")
                    diag = diagnose_shape_errors(solid, debug=True)
                    if 'exception' not in diag:
                        log(f"[DIAGNOSIS] Root cause analysis:")
                        summary = diag.get('error_summary', {})
                        if summary.get('free_edges', 0) > 0:
                            log(f"  ⚠ {summary['free_edges']}/{summary['total_edges']} edges are not fully connected (FREE EDGES)")
                            log(f"     → This means some faces don't share edges properly")
                        if summary.get('invalid_faces_count', 0) > 0:
                            log(f"  ⚠ {summary['invalid_faces_count']}/{summary['total_faces']} faces are invalid")
                        if summary.get('shell_closed') == False:
                            log(f"  ⚠ Shell is not closed (has gaps or holes)")
                        log(f"[DIAGNOSIS] This geometry has fundamental topology issues that may not be repairable")

                log(f"\n[PHASE:5] AUTOMATIC REPAIR WITH AUTO-ESCALATION")

                # Define escalation levels (minimal → standard → aggressive → ultra)
                escalation_map = {
                    'minimal': ['minimal', 'standard', 'aggressive', 'ultra'],
                    'standard': ['standard', 'aggressive', 'ultra'],
                    'aggressive': ['aggressive', 'ultra'],
                    'ultra': ['ultra']
                }

                levels_to_try = escalation_map.get(shape_fix_level, ['minimal', 'standard', 'aggressive', 'ultra'])
                log(f"[INFO] Auto-escalation enabled: will try levels {' → '.join(levels_to_try)}")
                log(f"[INFO] Starting from: {shape_fix_level}")
                log(f"")

                # Try each escalation level
                for current_level_idx, current_level in enumerate(levels_to_try):
                    if current_level_idx > 0:
                        log(f"\n{'='*80}")
                        log(f"[ESCALATION] Previous level failed, escalating to: {current_level}")
                        log(f"{'='*80}")

                    log(f"\n[REPAIR LEVEL: {current_level.upper()}]")

                    # Repair Strategy 1: ShapeFix_Solid (always try)
                    log(f"\n[STEP 1/4] Trying ShapeFix_Solid...")
                    try:
                        fixer = ShapeFix_Solid(solid)
                        fixer.SetPrecision(tolerance)
                        fixer.SetMaxTolerance(tolerance * 10)
                        fixer.Perform()
                        repaired_solid = fixer.Solid()

                        analyzer_repaired = BRepCheck_Analyzer(repaired_solid)
                        if analyzer_repaired.IsValid():
                            log(f"[REPAIR] ✓ ShapeFix_Solid succeeded at level '{current_level}'!")
                            log(f"[INFO] Repaired solid is now valid")
                            if current_level_idx > 0:
                                log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                            return repaired_solid
                        else:
                            log(f"[REPAIR] ✗ ShapeFix_Solid did not fix all issues")
                            solid = repaired_solid  # Use partially repaired version for next attempts
                    except Exception as e:
                        log(f"[REPAIR] ✗ ShapeFix_Solid raised exception: {type(e).__name__}: {str(e)}")

                    # Repair Strategy 2: ShapeUpgrade_UnifySameDomain (standard+)
                    if current_level in ['standard', 'aggressive', 'ultra']:
                        log(f"\n[STEP 2/4] Trying ShapeUpgrade_UnifySameDomain (topology simplification)...")
                        try:
                            unifier = ShapeUpgrade_UnifySameDomain(solid, True, True, True)
                            unifier.Build()
                            unified_shape = unifier.Shape()

                            analyzer_unified = BRepCheck_Analyzer(unified_shape)
                            if analyzer_unified.IsValid():
                                log(f"[REPAIR] ✓ ShapeUpgrade_UnifySameDomain succeeded at level '{current_level}'!")
                                log(f"[INFO] Unified shape is now valid")
                                if current_level_idx > 0:
                                    log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                                return unified_shape
                            else:
                                log(f"[REPAIR] ✗ Topology simplification did not create valid solid")
                        except Exception as e:
                            log(f"[REPAIR] ✗ ShapeUpgrade_UnifySameDomain raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 2/4] Skipped (requires level standard+)")

                    # Repair Strategy 3: Rebuild with relaxed tolerance (aggressive+)
                    if current_level in ['aggressive', 'ultra']:
                        log(f"\n[STEP 3/4] Trying rebuild with relaxed tolerance (2x)...")
                        try:
                            relaxed_tolerance = tolerance * 2.0
                            log(f"[INFO] Original tolerance: {tolerance:.6f}")
                            log(f"[INFO] Relaxed tolerance: {relaxed_tolerance:.6f}")

                            # Rebuild shell with relaxed tolerance
                            relaxed_shell = build_shell_from_faces(exterior_faces, relaxed_tolerance, debug, current_level)
                            if relaxed_shell is not None and BRep_Tool.IsClosed(relaxed_shell):
                                mk_solid_relaxed = BRepBuilderAPI_MakeSolid(relaxed_shell)
                                for int_shell in interior_shells:
                                    try:
                                        mk_solid_relaxed.Add(int_shell)
                                    except Exception:
                                        pass

                                relaxed_solid = mk_solid_relaxed.Solid()
                                analyzer_relaxed = BRepCheck_Analyzer(relaxed_solid)
                                if analyzer_relaxed.IsValid():
                                    log(f"[REPAIR] ✓ Rebuild with relaxed tolerance succeeded at level '{current_level}'!")
                                    if current_level_idx > 0:
                                        log(f"[INFO] Success after escalation from '{shape_fix_level}' to '{current_level}'")
                                    return relaxed_solid
                                else:
                                    log(f"[REPAIR] ✗ Relaxed tolerance rebuild did not create valid solid")
                            else:
                                log(f"[REPAIR] ✗ Could not rebuild closed shell with relaxed tolerance")
                        except Exception as e:
                            log(f"[REPAIR] ✗ Relaxed tolerance rebuild raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 3/4] Skipped (requires level aggressive+)")

                    # Repair Strategy 4: ShapeFix_Shape (ultra only)
                    if current_level == 'ultra':
                        log(f"\n[STEP 4/4] Trying ShapeFix_Shape (most aggressive)...")
                        try:
                            shape_fixer = ShapeFix_Shape(solid)
                            shape_fixer.SetPrecision(tolerance)
                            shape_fixer.SetMaxTolerance(tolerance * 100)
                            shape_fixer.Perform()
                            fixed_shape = shape_fixer.Shape()

                            analyzer_fixed = BRepCheck_Analyzer(fixed_shape)
                            if analyzer_fixed.IsValid():
                                log(f"[REPAIR] ✓ ShapeFix_Shape succeeded at level 'ultra'!")
                                if current_level_idx > 0:
                                    log(f"[INFO] Success after escalation from '{shape_fix_level}' to 'ultra'")
                                return fixed_shape
                            else:
                                log(f"[REPAIR] ✗ ShapeFix_Shape did not create valid solid")
                        except Exception as e:
                            log(f"[REPAIR] ✗ ShapeFix_Shape raised exception: {type(e).__name__}: {str(e)}")
                    else:
                        log(f"[STEP 4/4] Skipped (requires level ultra)")

                    log(f"\n[REPAIR LEVEL: {current_level.upper()}] ✗ All strategies failed at this level")

                # All escalation levels exhausted
                log(f"\n{'='*80}")
                log(f"[REPAIR] ✗ All repair attempts exhausted across all escalation levels")
                log(f"[INFO] Tried levels: {' → '.join(levels_to_try)}")
                log(f"[DECISION] → Returning shell instead of solid (may cause issues in merging/export)")
                log(f"⚠ WARNING: This shape may fail in BuildingPart fusion or STEP export")
                log(f"⚠ WARNING: The building geometry has fundamental topology issues")
                return exterior_shell
        except Exception as e:
            if debug:
                log(f"Solid creation failed: {e}, returning shell")
            return exterior_shell
    else:
        if debug:
            log("Exterior shell not closed, cannot create solid")
        return exterior_shell