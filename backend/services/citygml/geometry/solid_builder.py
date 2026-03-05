"""
Solid construction with cavities and flat repair strategy (PHASE:3-5).

This module handles:
- PHASE:3: Shell construction from faces
- PHASE:4: Solid validation
- PHASE:5: Automatic repair with flat strategy list (no redundant escalation)

Repair strategies (each runs at most ONCE):
1. ShapeFix_Solid               — requires level >= minimal
2. ShapeUpgrade_UnifySameDomain — requires level >= standard
3. Rebuild with relaxed tolerance — requires level >= aggressive
4. ShapeFix_Shape               — requires level >= ultra

Performance optimization (Issue #192, Phase 6):
- Flat strategy list eliminates 12->4 OCCT operations (3x speedup)
- Diagnosis-based early exit skips repair for unrepairable shapes
- Timing instrumentation for all repair strategies
"""

import time
from typing import List, Optional, Any, Dict

from ..utils.logging import log
from .tolerance import compute_tolerance_from_face_list
from .shell_builder import build_shell_from_faces

# Level ordering for flat strategy gating
_LEVEL_RANK = {"minimal": 0, "standard": 1, "aggressive": 2, "ultra": 3}

# Early exit threshold: if free_edges / total_edges > this, skip repair
_UNREPAIRABLE_FREE_EDGE_RATIO = 0.2


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
        "is_valid": False,
        "free_edges_count": 0,
        "invalid_faces": [],
        "shell_closed": None,
        "error_summary": {},
    }

    try:
        analyzer = BRepCheck_Analyzer(shape)
        errors["is_valid"] = analyzer.IsValid()

        if not errors["is_valid"]:
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
            errors["free_edges_count"] = free_edge_count

            # Check faces
            face_exp = TopExp_Explorer(shape, TopAbs_FACE)
            face_count = 0
            while face_exp.More():
                face = topods.Face(face_exp.Current())
                face_analyzer = BRepCheck_Analyzer(face)
                if not face_analyzer.IsValid():
                    errors["invalid_faces"].append(face_count)
                face_count += 1
                face_exp.Next()

            # Check shell closure
            shell_exp = TopExp_Explorer(shape, TopAbs_SHELL)
            if shell_exp.More():
                shell = topods.Shell(shell_exp.Current())
                errors["shell_closed"] = BRep_Tool.IsClosed(shell)

            errors["error_summary"] = {
                "total_edges": edge_count,
                "free_edges": free_edge_count,
                "total_faces": face_count,
                "invalid_faces_count": len(errors["invalid_faces"]),
                "shell_closed": errors["shell_closed"],
            }

            if debug:
                log(f"[DIAGNOSTICS] Shape validation failed:")
                log(f"  - Total edges: {edge_count}, Free edges: {free_edge_count}")
                log(
                    f"  - Total faces: {face_count}, Invalid faces: {len(errors['invalid_faces'])}"
                )
                log(f"  - Shell closed: {errors['shell_closed']}")
    except Exception as e:
        errors["exception"] = str(e)
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


def _is_unrepairable(diag: Dict) -> bool:
    """
    Check if a shape is unrepairable based on diagnosis results.

    A shape is considered unrepairable if:
    - Shell is not closed AND
    - More than 20% of edges are free (not shared by 2 faces)

    Args:
        diag: Result from diagnose_shape_errors()

    Returns:
        True if shape should be skipped for repair
    """
    if "exception" in diag:
        return False  # Can't decide, let repair try

    summary = diag.get("error_summary", {})
    shell_closed = summary.get("shell_closed")
    total_edges = summary.get("total_edges", 0)
    free_edges = summary.get("free_edges", 0)

    if shell_closed is False and total_edges > 0:
        ratio = free_edges / total_edges
        if ratio > _UNREPAIRABLE_FREE_EDGE_RATIO:
            return True

    return False


def make_solid_with_cavities(
    exterior_faces: List[Any],  # List[TopoDS_Face]
    interior_shells_faces: List[List[Any]],  # List[List[TopoDS_Face]]
    tolerance: Optional[float] = None,
    debug: bool = False,
    precision_mode: str = "auto",
    shape_fix_level: str = "standard",
) -> Optional[Any]:  # Optional[TopoDS_Shape]
    """
    Build a solid with cavities from exterior and interior shells.

    This function implements PHASE:3-5 of the conversion pipeline:
    - PHASE:3: Shell construction from faces
    - PHASE:4: Solid validation
    - PHASE:5: Automatic repair with flat strategy list

    Issue #192 Phase 6 optimization:
    - Flat strategy list: each strategy runs at most once (was 12 ops, now max 4)
    - Diagnosis-based early exit for unrepairable shapes
    - Timing instrumentation for performance profiling

    Args:
        exterior_faces: Faces forming the outer shell
        interior_shells_faces: List of face lists, each forming an interior shell (cavity)
        tolerance: Sewing tolerance (auto-computed if None)
        debug: Enable debug output
        precision_mode: Precision level for tolerance computation
        shape_fix_level: Shape fixing aggressiveness (controls which strategies are enabled)
            - "minimal": Strategy 1 only (ShapeFix_Solid)
            - "standard": Strategies 1-2 (+ UnifySameDomain)
            - "aggressive": Strategies 1-3 (+ rebuild with relaxed tolerance)
            - "ultra": Strategies 1-4 (+ ShapeFix_Shape)

    Returns:
        TopoDS_Solid or TopoDS_Shell (if solid construction fails) or None (if shell fails)

    Example:
        >>> solid = make_solid_with_cavities(
        ...     faces, interior_shells, None, True, "ultra", "standard"
        ... )
        >>> # [PHASE:3] Attempting to build exterior shell from 74 faces...
        >>> # [PHASE:4] SOLID VALIDATION
        >>> # [VALIDATION] Solid validation succeeded
        >>> is_valid_shape(solid)
        True

    Notes:
        - Auto-computes tolerance from face list if not provided
        - Builds exterior shell using build_shell_from_faces()
        - Attempts to create solid with BRepBuilderAPI_MakeSolid
        - Validates solid with BRepCheck_Analyzer
        - If validation fails, runs flat repair strategy list (max 4 ops)
        - Returns shell if solid creation fails
        - Interior shells (cavities) are only added if they're closed
    """
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.ShapeFix import ShapeFix_Solid, ShapeFix_Shape
    from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    t_total_start = time.time()

    # Auto-compute tolerance if not provided
    if tolerance is None:
        tolerance = compute_tolerance_from_face_list(exterior_faces, precision_mode)
        if debug:
            log(
                f"Auto-computed tolerance: {tolerance:.6f} (precision_mode: {precision_mode})"
            )

    # Build exterior shell
    if debug:
        log(f"Attempting to build exterior shell from {len(exterior_faces)} faces...")

    t_shell = time.time()
    exterior_shell = build_shell_from_faces(
        exterior_faces, tolerance, debug, shape_fix_level
    )
    shell_ms = (time.time() - t_shell) * 1000
    log(f"[TIMING] Shell construction: {shell_ms:.0f}ms")

    if exterior_shell is None:
        if debug:
            log(
                f"ERROR: Failed to build exterior shell (sewing or shell extraction failed)"
            )
        return None

    # Check if exterior shell is closed
    try:
        is_closed = BRep_Tool.IsClosed(exterior_shell)
        if not is_closed:
            if debug:
                log(
                    f"WARNING: Exterior shell is not closed, returning shell instead of solid"
                )
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
                        log(f"Added interior shell {i + 1} (closed)")
                else:
                    if debug:
                        log(f"Interior shell {i + 1} is not closed, skipping")
            except Exception as e:
                if debug:
                    log(f"Interior shell {i + 1} check failed: {e}")

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
            t_validate = time.time()
            analyzer = BRepCheck_Analyzer(solid)
            is_valid = analyzer.IsValid()
            validate_ms = (time.time() - t_validate) * 1000
            log(f"[TIMING] Solid validation: {validate_ms:.0f}ms")

            if is_valid:
                log(f"[VALIDATION] ✓ Initial solid validation succeeded")
                if debug:
                    log(
                        f"[INFO] Created valid solid with {len(interior_shells)} cavities"
                    )
                total_ms = (time.time() - t_total_start) * 1000
                log(f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms")
                return solid
            else:
                log(f"[VALIDATION] ✗ Initial solid validation failed")

                # ============================================================
                # PHASE:4.5 - Diagnosis (always run for early exit decision)
                # ============================================================
                log(f"\n[PHASE:4.5] ERROR DIAGNOSIS")
                t_diag = time.time()
                diag = diagnose_shape_errors(solid, debug=debug)
                diag_ms = (time.time() - t_diag) * 1000
                log(f"[TIMING] Diagnosis: {diag_ms:.0f}ms")

                if "exception" not in diag:
                    summary = diag.get("error_summary", {})
                    log(f"[DIAGNOSIS] Root cause analysis:")
                    if summary.get("free_edges", 0) > 0:
                        log(
                            f"  - {summary['free_edges']}/{summary['total_edges']} edges are not fully connected (FREE EDGES)"
                        )
                    if summary.get("invalid_faces_count", 0) > 0:
                        log(
                            f"  - {summary['invalid_faces_count']}/{summary['total_faces']} faces are invalid"
                        )
                    if summary.get("shell_closed") is False:
                        log(f"  - Shell is not closed (has gaps or holes)")

                    # 6B: Diagnosis-based early exit
                    if _is_unrepairable(diag):
                        total_edges = summary.get("total_edges", 0)
                        free_edges = summary.get("free_edges", 0)
                        ratio = free_edges / total_edges if total_edges > 0 else 0
                        log(
                            f"\n[EARLY EXIT] Shell not closed + {free_edges}/{total_edges} free edges "
                            f"({ratio * 100:.1f}%) > {_UNREPAIRABLE_FREE_EDGE_RATIO * 100:.0f}% threshold"
                        )
                        log(
                            f"[DECISION] -> Skipping repair, returning shell (unrepairable topology)"
                        )
                        total_ms = (time.time() - t_total_start) * 1000
                        log(
                            f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms (early exit)"
                        )
                        return exterior_shell

                # ============================================================
                # PHASE:5 - Flat repair strategy list (Issue #192 Phase 6A)
                # ============================================================
                log(f"\n[PHASE:5] AUTOMATIC REPAIR (FLAT STRATEGY LIST)")

                current_rank = _LEVEL_RANK.get(shape_fix_level, 0)
                max_strategies = (
                    current_rank + 1
                )  # minimal=1, standard=2, aggressive=3, ultra=4
                log(
                    f"[INFO] shape_fix_level='{shape_fix_level}' -> up to {max_strategies} strategy(ies)"
                )
                log(f"[INFO] Each strategy runs at most ONCE (no redundant escalation)")

                # ----------------------------------------------------------
                # Strategy 1: ShapeFix_Solid (level >= minimal)
                # ----------------------------------------------------------
                if current_rank >= _LEVEL_RANK["minimal"]:
                    log(f"\n[STRATEGY 1/{max_strategies}] ShapeFix_Solid")
                    t_s1 = time.time()
                    try:
                        fixer = ShapeFix_Solid(solid)
                        fixer.SetPrecision(tolerance)
                        fixer.SetMaxTolerance(tolerance * 10)
                        fixer.Perform()
                        repaired_solid = fixer.Solid()

                        analyzer_repaired = BRepCheck_Analyzer(repaired_solid)
                        s1_ms = (time.time() - t_s1) * 1000
                        if analyzer_repaired.IsValid():
                            log(f"[REPAIR] ✓ ShapeFix_Solid succeeded")
                            log(f"[TIMING] ShapeFix_Solid: {s1_ms:.0f}ms")
                            total_ms = (time.time() - t_total_start) * 1000
                            log(
                                f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms"
                            )
                            return repaired_solid
                        else:
                            log(f"[REPAIR] ✗ ShapeFix_Solid did not fix all issues")
                            log(f"[TIMING] ShapeFix_Solid: {s1_ms:.0f}ms")
                            solid = repaired_solid  # Use partially repaired version
                    except Exception as e:
                        s1_ms = (time.time() - t_s1) * 1000
                        log(
                            f"[REPAIR] ✗ ShapeFix_Solid raised exception: {type(e).__name__}: {str(e)}"
                        )
                        log(f"[TIMING] ShapeFix_Solid: {s1_ms:.0f}ms")

                # ----------------------------------------------------------
                # Strategy 2: ShapeUpgrade_UnifySameDomain (level >= standard)
                # ----------------------------------------------------------
                if current_rank >= _LEVEL_RANK["standard"]:
                    log(
                        f"\n[STRATEGY 2/{max_strategies}] ShapeUpgrade_UnifySameDomain (topology simplification)"
                    )
                    t_s2 = time.time()
                    try:
                        unifier = ShapeUpgrade_UnifySameDomain(solid, True, True, True)
                        unifier.Build()
                        unified_shape = unifier.Shape()

                        analyzer_unified = BRepCheck_Analyzer(unified_shape)
                        s2_ms = (time.time() - t_s2) * 1000
                        if analyzer_unified.IsValid():
                            log(f"[REPAIR] ✓ ShapeUpgrade_UnifySameDomain succeeded")
                            log(f"[TIMING] UnifySameDomain: {s2_ms:.0f}ms")
                            total_ms = (time.time() - t_total_start) * 1000
                            log(
                                f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms"
                            )
                            return unified_shape
                        else:
                            log(
                                f"[REPAIR] ✗ Topology simplification did not create valid solid"
                            )
                            log(f"[TIMING] UnifySameDomain: {s2_ms:.0f}ms")
                    except Exception as e:
                        s2_ms = (time.time() - t_s2) * 1000
                        log(
                            f"[REPAIR] ✗ ShapeUpgrade_UnifySameDomain raised exception: {type(e).__name__}: {str(e)}"
                        )
                        log(f"[TIMING] UnifySameDomain: {s2_ms:.0f}ms")

                # ----------------------------------------------------------
                # Strategy 3: Rebuild with relaxed tolerance (level >= aggressive)
                # ----------------------------------------------------------
                if current_rank >= _LEVEL_RANK["aggressive"]:
                    log(
                        f"\n[STRATEGY 3/{max_strategies}] Rebuild with relaxed tolerance (2x)"
                    )
                    t_s3 = time.time()
                    try:
                        relaxed_tolerance = tolerance * 2.0
                        log(f"[INFO] Original tolerance: {tolerance:.6f}")
                        log(f"[INFO] Relaxed tolerance: {relaxed_tolerance:.6f}")

                        # Rebuild shell with relaxed tolerance
                        # Use 'aggressive' level for face validation in rebuild
                        relaxed_shell = build_shell_from_faces(
                            exterior_faces, relaxed_tolerance, debug, "aggressive"
                        )
                        if relaxed_shell is not None and BRep_Tool.IsClosed(
                            relaxed_shell
                        ):
                            mk_solid_relaxed = BRepBuilderAPI_MakeSolid(relaxed_shell)
                            for int_shell in interior_shells:
                                try:
                                    mk_solid_relaxed.Add(int_shell)
                                except Exception:
                                    pass

                            relaxed_solid = mk_solid_relaxed.Solid()
                            analyzer_relaxed = BRepCheck_Analyzer(relaxed_solid)
                            s3_ms = (time.time() - t_s3) * 1000
                            if analyzer_relaxed.IsValid():
                                log(
                                    f"[REPAIR] ✓ Rebuild with relaxed tolerance succeeded"
                                )
                                log(f"[TIMING] Rebuild relaxed: {s3_ms:.0f}ms")
                                total_ms = (time.time() - t_total_start) * 1000
                                log(
                                    f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms"
                                )
                                return relaxed_solid
                            else:
                                log(
                                    f"[REPAIR] ✗ Relaxed tolerance rebuild did not create valid solid"
                                )
                                log(f"[TIMING] Rebuild relaxed: {s3_ms:.0f}ms")
                        else:
                            s3_ms = (time.time() - t_s3) * 1000
                            log(
                                f"[REPAIR] ✗ Could not rebuild closed shell with relaxed tolerance"
                            )
                            log(f"[TIMING] Rebuild relaxed: {s3_ms:.0f}ms")
                    except Exception as e:
                        s3_ms = (time.time() - t_s3) * 1000
                        log(
                            f"[REPAIR] ✗ Relaxed tolerance rebuild raised exception: {type(e).__name__}: {str(e)}"
                        )
                        log(f"[TIMING] Rebuild relaxed: {s3_ms:.0f}ms")

                # ----------------------------------------------------------
                # Strategy 4: ShapeFix_Shape (level >= ultra)
                # ----------------------------------------------------------
                if current_rank >= _LEVEL_RANK["ultra"]:
                    log(
                        f"\n[STRATEGY 4/{max_strategies}] ShapeFix_Shape (most aggressive)"
                    )
                    t_s4 = time.time()
                    try:
                        shape_fixer = ShapeFix_Shape(solid)
                        shape_fixer.SetPrecision(tolerance)
                        shape_fixer.SetMaxTolerance(tolerance * 100)
                        shape_fixer.Perform()
                        fixed_shape = shape_fixer.Shape()

                        analyzer_fixed = BRepCheck_Analyzer(fixed_shape)
                        s4_ms = (time.time() - t_s4) * 1000
                        if analyzer_fixed.IsValid():
                            log(f"[REPAIR] ✓ ShapeFix_Shape succeeded")
                            log(f"[TIMING] ShapeFix_Shape: {s4_ms:.0f}ms")
                            total_ms = (time.time() - t_total_start) * 1000
                            log(
                                f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms"
                            )
                            return fixed_shape
                        else:
                            log(f"[REPAIR] ✗ ShapeFix_Shape did not create valid solid")
                            log(f"[TIMING] ShapeFix_Shape: {s4_ms:.0f}ms")
                    except Exception as e:
                        s4_ms = (time.time() - t_s4) * 1000
                        log(
                            f"[REPAIR] ✗ ShapeFix_Shape raised exception: {type(e).__name__}: {str(e)}"
                        )
                        log(f"[TIMING] ShapeFix_Shape: {s4_ms:.0f}ms")

                # All strategies exhausted
                log(f"\n{'=' * 80}")
                log(f"[REPAIR] ✗ All {max_strategies} repair strategy(ies) exhausted")
                log(
                    f"[DECISION] -> Returning shell instead of solid (may cause issues in merging/export)"
                )
                log(
                    f"WARNING: This shape may fail in BuildingPart fusion or STEP export"
                )
                log(f"WARNING: The building geometry has fundamental topology issues")
                total_ms = (time.time() - t_total_start) * 1000
                log(
                    f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms (all strategies failed)"
                )
                return exterior_shell
        except Exception as e:
            if debug:
                log(f"Solid creation failed: {e}, returning shell")
            total_ms = (time.time() - t_total_start) * 1000
            log(
                f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms (exception)"
            )
            return exterior_shell
    else:
        if debug:
            log("Exterior shell not closed, cannot create solid")
        total_ms = (time.time() - t_total_start) * 1000
        log(
            f"[TIMING] Total make_solid_with_cavities: {total_ms:.0f}ms (shell not closed)"
        )
        return exterior_shell
