"""
Shell construction from faces with multi-stage sewing and progressive tolerance escalation.

⚠️ CRITICAL: This module implements a 4-stage tolerance escalation strategy that MUST
be preserved exactly. The progression (tolerance * 10.0 → 5.0 → 1.0) is essential for
handling varying geometry quality in PLATEAU data.

This is one of the most complex and critical parts of the conversion pipeline.
"""

from typing import List, Optional, Any

from ..core.constants import (
    ULTRA_MODE_TOLERANCE_MULTIPLIERS,
    INVALID_FACE_RATIO_THRESHOLD
)
from ..utils.logging import log
from .face_fixer import (
    validate_and_fix_face,
    normalize_face_orientation,
    remove_duplicate_vertices
)


def build_shell_from_faces(
    faces: List[Any],  # List[TopoDS_Face]
    tolerance: float = 0.1,
    debug: bool = False,
    shape_fix_level: str = "standard"
) -> Optional[Any]:  # Optional[TopoDS_Shell or TopoDS_Compound]
    """
    Build a shell from a list of faces using sewing and fixing.

    Enhanced with multi-stage processing for LOD2/LOD3 precision:
    1. Validate and fix each face individually
    2. Normalize face orientations
    3. Remove duplicate vertices
    4. Multi-pass sewing with progressively tighter tolerances
    5. Aggressive shell fixing
    6. Multi-shell handling with validation and unification

    ⚠️ CRITICAL: Stage 4 tolerance escalation sequence MUST be preserved exactly.
    The sequence (tolerance * 10.0 → 5.0 → 1.0) is essential for PLATEAU data.

    Args:
        faces: List of TopoDS_Face objects
        tolerance: Sewing tolerance
        debug: Enable debug output
        shape_fix_level: Shape fixing aggressiveness
            - "minimal": Skip shape fixing to preserve maximum detail
            - "standard": Standard shape fixing (default)
            - "aggressive": More aggressive shape fixing for robustness
            - "ultra": Maximum fixing for LOD2/LOD3 (multi-stage with validation)

    Returns:
        TopoDS_Shell, TopoDS_Compound (if multiple disconnected shells), or None

    Notes:
        - May return TopoDS_Compound for buildings with disconnected geometry
        - Ultra mode uses 3-pass sewing: looser → tighter → target tolerance
        - Multi-shell results are validated and potentially re-sewn for unification
    """
    # Import topods at function start to avoid scoping issues
    from OCC.Core.TopoDS import topods, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SHELL, TopAbs_FACE
    from OCC.Core.ShapeFix import ShapeFix_Shape, ShapeFix_Shell
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    if not faces:
        return None

    if debug:
        log(f"Building shell from {len(faces)} faces with tolerance {tolerance:.9f}")

    # ===== Stage 1: Validate and fix each face individually =====
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            log("Stage 1: Validating and fixing individual faces...")

        validated_faces = []
        for i, face in enumerate(faces):
            fixed_face = validate_and_fix_face(face, tolerance, debug)
            if fixed_face is not None:
                validated_faces.append(fixed_face)
            elif debug:
                log(f"Warning: Face {i} could not be fixed, skipping")

        if not validated_faces:
            if debug:
                log("Error: No valid faces after validation")
            return None

        faces = validated_faces
        if debug:
            log(f"Stage 1 complete: {len(faces)} valid faces")

    # ===== Stage 2: Normalize face orientations =====
    if shape_fix_level in ("standard", "aggressive", "ultra"):
        if debug:
            log("Stage 2: Normalizing face orientations...")
        faces = normalize_face_orientation(faces, debug)

    # ===== Stage 3: Remove duplicate vertices =====
    if shape_fix_level in ("aggressive", "ultra"):
        if debug:
            log("Stage 3: Removing duplicate vertices...")
        faces = remove_duplicate_vertices(faces, tolerance, debug)

    # ===== Stage 4: Multi-pass sewing with progressive tolerance escalation =====
    # ⚠️ CRITICAL: Tolerance progression MUST be exactly [10.0, 5.0, 1.0]
    if shape_fix_level == "ultra":
        if debug:
            log("Stage 4: Multi-pass sewing with progressively tighter tolerances...")

        # Progressive tolerance escalation (from constants)
        tolerances_to_try = [
            tolerance * mult for mult in ULTRA_MODE_TOLERANCE_MULTIPLIERS
        ]

        sewn_shape = None
        for i, tol in enumerate(tolerances_to_try):
            if debug:
                log(f"  Sewing pass {i+1} with tolerance {tol:.9f}")

            sewing = BRepBuilderAPI_Sewing(tol, True, True, True, False)
            for fc in faces:
                sewing.Add(fc)
            sewing.Perform()
            sewn_shape = sewing.SewedShape()

            # Check if sewing improved
            if sewn_shape is not None and not sewn_shape.IsNull():
                if debug:
                    log(f"  Pass {i+1} successful")

                # DEBUG: Check face count after this pass
                if debug:
                    face_exp_count = TopExp_Explorer(sewn_shape, TopAbs_FACE)
                    pass_face_count = 0
                    while face_exp_count.More():
                        pass_face_count += 1
                        face_exp_count.Next()
                    log(f"  [SEWING PASS {i+1}] {len(faces)} input → {pass_face_count} output faces")

                # Use this result as input for next pass
                # Extract faces from sewn shape for next iteration
                if i < len(tolerances_to_try) - 1:
                    face_exp = TopExp_Explorer(sewn_shape, TopAbs_FACE)
                    new_faces = []
                    while face_exp.More():
                        new_faces.append(topods.Face(face_exp.Current()))
                        face_exp.Next()
                    if new_faces:
                        faces = new_faces
    else:
        # Standard single-pass sewing
        if debug:
            log("Stage 4: Single-pass sewing...")

        sewing = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
        for fc in faces:
            sewing.Add(fc)
        sewing.Perform()
        sewn_shape = sewing.SewedShape()

    # DEBUG: Check how many faces survived sewing
    if debug:
        face_exp = TopExp_Explorer(sewn_shape, TopAbs_FACE)
        sewn_face_count = 0
        while face_exp.More():
            sewn_face_count += 1
            face_exp.Next()
        log(f"[SEWING DIAGNOSTIC] Input: {len(faces)} faces → Output: {sewn_face_count} faces in sewn shape")
        if sewn_face_count < len(faces):
            lost_faces = len(faces) - sewn_face_count
            loss_percentage = (lost_faces / len(faces)) * 100
            log(f"[SEWING DIAGNOSTIC] ⚠ WARNING: {lost_faces} faces lost ({loss_percentage:.1f}%)")

    # ===== Stage 5: Apply shape fixing based on level =====
    if shape_fix_level != "minimal":
        try:
            if debug:
                log(f"Stage 5: Applying shape fixing (level: {shape_fix_level})...")

            fixer = ShapeFix_Shape(sewn_shape)

            # Configure fixer based on level
            if shape_fix_level == "standard":
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 10.0)
            elif shape_fix_level == "aggressive":
                fixer.SetPrecision(tolerance * 10.0)
                fixer.SetMaxTolerance(tolerance * 100.0)
            elif shape_fix_level == "ultra":
                # Ultra mode: very tight precision with large tolerance range
                fixer.SetPrecision(tolerance)
                fixer.SetMaxTolerance(tolerance * 1000.0)

            fixer.Perform()
            sewn_shape = fixer.Shape()

            if debug:
                log(f"Shape fixing applied (level: {shape_fix_level})")
        except Exception as e:
            if debug:
                log(f"ShapeFix_Shape failed: {e}")

    # ===== Stage 6: Extract and validate shell =====
    if debug:
        log("Stage 6: Extracting and validating shell...")

    # First, count how many shells exist in sewn shape
    shell_count = 0
    shell_exp = TopExp_Explorer(sewn_shape, TopAbs_SHELL)
    shells = []
    while shell_exp.More():
        shells.append(topods.Shell(shell_exp.Current()))
        shell_count += 1
        shell_exp.Next()

    if debug:
        log(f"[SHELL DIAGNOSTIC] Found {shell_count} shell(s) in sewn shape")

    shell = None

    # Handle multiple shells: validate and potentially unify
    if shell_count > 1:
        if debug:
            log(f"[SHELL DIAGNOSTIC] Multiple disconnected shells detected, validating each shell...")

        # Validate each shell and count faces
        shell_info = []
        for i, sh in enumerate(shells):
            face_exp = TopExp_Explorer(sh, TopAbs_FACE)
            face_count = 0
            while face_exp.More():
                face_count += 1
                face_exp.Next()

            # Check shell validity and count invalid faces
            try:
                analyzer = BRepCheck_Analyzer(sh)
                is_valid = analyzer.IsValid()

                # If shell is invalid, count how many faces are invalid
                invalid_face_count = 0
                if not is_valid:
                    face_exp2 = TopExp_Explorer(sh, TopAbs_FACE)
                    while face_exp2.More():
                        face = topods.Face(face_exp2.Current())
                        face_analyzer = BRepCheck_Analyzer(face)
                        if not face_analyzer.IsValid():
                            invalid_face_count += 1
                        face_exp2.Next()

            except Exception as e:
                is_valid = False
                invalid_face_count = face_count  # Assume all invalid on error
                if debug:
                    log(f"  Shell {i+1} validation error: {e}")

            # Calculate invalid face ratio
            invalid_ratio = invalid_face_count / face_count if face_count > 0 else 1.0

            shell_info.append({
                'index': i + 1,
                'shell': sh,
                'face_count': face_count,
                'is_valid': is_valid,
                'invalid_face_count': invalid_face_count,
                'invalid_ratio': invalid_ratio
            })

            if debug:
                if is_valid:
                    status = "✓ valid"
                elif invalid_ratio < INVALID_FACE_RATIO_THRESHOLD:
                    status = f"⚠ mostly valid ({invalid_face_count}/{face_count} invalid, {invalid_ratio*100:.1f}%)"
                else:
                    status = f"✗ invalid ({invalid_face_count}/{face_count} invalid, {invalid_ratio*100:.1f}%)"
                log(f"  Shell {i+1}: {face_count} faces ({status})")

        # Find shells that are valid or mostly valid (< threshold invalid faces)
        acceptable_shells = [
            s for s in shell_info
            if s['is_valid'] or s['invalid_ratio'] < INVALID_FACE_RATIO_THRESHOLD
        ]

        if acceptable_shells:
            # Collect valid faces from ALL acceptable shells
            if debug:
                log(f"[SHELL DIAGNOSTIC] Found {len(acceptable_shells)} acceptable shell(s), collecting all valid faces...")

            all_valid_faces = []
            total_invalid_removed = 0

            for info in acceptable_shells:
                shell_idx = info['index']
                shell_obj = info['shell']
                shell_face_count = info['face_count']
                shell_is_valid = info['is_valid']
                shell_invalid_count = info['invalid_face_count']

                if debug:
                    status = "✓ valid" if shell_is_valid else f"⚠ mostly valid ({shell_invalid_count} invalid)"
                    log(f"  Processing Shell {shell_idx}: {shell_face_count} faces ({status})")

                # Extract valid faces from this shell
                face_exp = TopExp_Explorer(shell_obj, TopAbs_FACE)
                valid_count = 0
                invalid_count = 0

                while face_exp.More():
                    face = topods.Face(face_exp.Current())

                    # If shell is fully valid, skip validation check for efficiency
                    if shell_is_valid:
                        all_valid_faces.append(face)
                        valid_count += 1
                    else:
                        # Shell has some invalid faces - validate each face
                        face_analyzer = BRepCheck_Analyzer(face)
                        if face_analyzer.IsValid():
                            all_valid_faces.append(face)
                            valid_count += 1
                        else:
                            invalid_count += 1

                    face_exp.Next()

                if debug and invalid_count > 0:
                    log(f"    → Kept {valid_count} valid faces, removed {invalid_count} invalid faces")
                    total_invalid_removed += invalid_count

            if debug:
                log(f"[SHELL DIAGNOSTIC] Collected {len(all_valid_faces)} valid faces from {len(acceptable_shells)} shells")
                if total_invalid_removed > 0:
                    log(f"[SHELL DIAGNOSTIC] Removed {total_invalid_removed} invalid faces total")

            # Re-sew all collected valid faces into a unified shell
            if len(all_valid_faces) > 0:
                if debug:
                    log(f"[SHELL DIAGNOSTIC] Re-sewing {len(all_valid_faces)} faces into unified shell...")

                sewing_unified = BRepBuilderAPI_Sewing(tolerance, True, True, True, False)
                for fc in all_valid_faces:
                    sewing_unified.Add(fc)
                sewing_unified.Perform()
                unified_sewn = sewing_unified.SewedShape()

                # Extract all shells from unified result
                unified_exp = TopExp_Explorer(unified_sewn, TopAbs_SHELL)
                unified_shells = []
                while unified_exp.More():
                    unified_shells.append(topods.Shell(unified_exp.Current()))
                    unified_exp.Next()

                if debug:
                    log(f"[SHELL DIAGNOSTIC] Unified re-sewing produced {len(unified_shells)} shell(s)")

                if len(unified_shells) > 0:
                    # If multiple shells, create a Compound to preserve all geometry
                    if len(unified_shells) > 1:
                        if debug:
                            log(f"[SHELL DIAGNOSTIC] Multiple disconnected shells detected, creating Compound to preserve all geometry...")

                        # Log face counts for each shell
                        shell_face_counts = []
                        for i, sh in enumerate(unified_shells):
                            face_exp2 = TopExp_Explorer(sh, TopAbs_FACE)
                            face_count = 0
                            while face_exp2.More():
                                face_count += 1
                                face_exp2.Next()
                            shell_face_counts.append(face_count)

                            if debug:
                                log(f"  Unified shell {i+1}: {face_count} faces")

                        # Create Compound containing all shells
                        compound = TopoDS_Compound()
                        builder = BRep_Builder()
                        builder.MakeCompound(compound)

                        for sh in unified_shells:
                            builder.Add(compound, sh)

                        total_faces_in_compound = sum(shell_face_counts)

                        if debug:
                            log(f"[SHELL DIAGNOSTIC] Created Compound with {len(unified_shells)} shells ({total_faces_in_compound} total faces)")

                        # Return Compound instead of Shell
                        shell = compound
                    else:
                        shell = unified_shells[0]
                        if debug:
                            unified_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
                            unified_face_count = 0
                            while unified_face_exp.More():
                                unified_face_count += 1
                                unified_face_exp.Next()
                            log(f"[SHELL DIAGNOSTIC] Unified shell contains {unified_face_count} faces")
                else:
                    # Fallback: use largest acceptable shell if unification failed
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Unified re-sewing produced no shells, using largest acceptable shell as fallback")
                    largest_acceptable = max(acceptable_shells, key=lambda s: s['face_count'])
                    shell = largest_acceptable['shell']
            else:
                # No valid faces collected - fallback to largest acceptable shell
                largest_acceptable = max(acceptable_shells, key=lambda s: s['face_count'])
                shell = largest_acceptable['shell']

        else:
            # No valid shells found, try re-sewing approach as fallback
            if debug:
                log(f"[SHELL DIAGNOSTIC] No valid shells found, attempting re-sewing as fallback...")

            all_faces_from_shells = []
            for info in shell_info:
                sh = info['shell']
                face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                while face_exp.More():
                    all_faces_from_shells.append(topods.Face(face_exp.Current()))
                    face_exp.Next()

            if debug:
                log(f"[SHELL DIAGNOSTIC] Collected {len(all_faces_from_shells)} faces from all shells for re-sewing")

            # Build single shell from all collected faces
            if all_faces_from_shells:
                sewing_multi = BRepBuilderAPI_Sewing(tolerance * 10.0, True, True, True, False)
                for fc in all_faces_from_shells:
                    sewing_multi.Add(fc)
                sewing_multi.Perform()
                multi_sewn = sewing_multi.SewedShape()

                # Extract all shells from multi-sewn result
                multi_exp = TopExp_Explorer(multi_sewn, TopAbs_SHELL)
                resewn_shells = []
                while multi_exp.More():
                    resewn_shells.append(topods.Shell(multi_exp.Current()))
                    multi_exp.Next()

                if debug:
                    log(f"[SHELL DIAGNOSTIC] Re-sewing produced {len(resewn_shells)} shell(s)")

                # If re-sewing created multiple shells again, find the largest one
                if len(resewn_shells) > 1:
                    if debug:
                        log("[SHELL DIAGNOSTIC] Re-sewing still created multiple shells, selecting largest...")

                    largest_shell = None
                    largest_face_count = 0

                    for i, sh in enumerate(resewn_shells):
                        face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                        face_count = 0
                        while face_exp.More():
                            face_count += 1
                            face_exp.Next()

                        if debug:
                            log(f"  Re-sewn shell {i+1}: {face_count} faces")

                        if face_count > largest_face_count:
                            largest_face_count = face_count
                            largest_shell = sh

                    shell = largest_shell
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Selected largest re-sewn shell with {largest_face_count} faces")

                elif len(resewn_shells) == 1:
                    shell = resewn_shells[0]
                    if debug:
                        shell_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
                        shell_face_count = 0
                        while shell_face_exp.More():
                            shell_face_count += 1
                            shell_face_exp.Next()
                        log(f"[SHELL DIAGNOSTIC] Rebuilt shell contains {shell_face_count} faces")
                else:
                    # Fallback: use largest original shell if re-sewing failed completely
                    if debug:
                        log("[SHELL DIAGNOSTIC] Re-sewing failed, selecting largest original shell as fallback")

                    largest_shell = None
                    largest_face_count = 0

                    for i, sh in enumerate(shells):
                        face_exp = TopExp_Explorer(sh, TopAbs_FACE)
                        face_count = 0
                        while face_exp.More():
                            face_count += 1
                            face_exp.Next()

                        if face_count > largest_face_count:
                            largest_face_count = face_count
                            largest_shell = sh

                    shell = largest_shell
                    if debug:
                        log(f"[SHELL DIAGNOSTIC] Selected largest original shell with {largest_face_count} faces")
            else:
                # No faces collected, use first shell as fallback
                shell = shells[0]

    elif shell_count == 1:
        # Single shell - use it directly
        shell = shells[0]

        # DEBUG: Count faces in extracted shell
        if debug:
            shell_face_exp = TopExp_Explorer(shell, TopAbs_FACE)
            shell_face_count = 0
            while shell_face_exp.More():
                shell_face_count += 1
                shell_face_exp.Next()
            log(f"[SHELL DIAGNOSTIC] Extracted shell contains {shell_face_count} faces")
    else:
        # No shells found
        if debug:
            log("[SHELL DIAGNOSTIC] No shells found in sewn shape")
        return None

    # ===== Final validation and fixing =====
    if shell:
        # Validate shell
        try:
            analyzer = BRepCheck_Analyzer(shell)
            if not analyzer.IsValid():
                if debug:
                    log("Warning: Shell is not valid, attempting to fix...")

                # Try fixing based on shape_fix_level
                if shape_fix_level == "ultra":
                    # Ultra mode: try aggressive shell fixing
                    try:
                        shell_fixer = ShapeFix_Shell(shell)
                        shell_fixer.SetPrecision(tolerance)
                        shell_fixer.SetMaxTolerance(tolerance * 1000.0)
                        shell_fixer.Perform()
                        fixed_shell = shell_fixer.Shell()

                        # Validate fixed shell
                        if fixed_shell is not None and not fixed_shell.IsNull():
                            analyzer = BRepCheck_Analyzer(fixed_shell)
                            if analyzer.IsValid():
                                if debug:
                                    log("Shell fixed successfully")
                                shell = fixed_shell
                            else:
                                if debug:
                                    log("Shell still invalid after fixing, using best attempt")
                    except Exception as e:
                        if debug:
                            log(f"ShapeFix_Shell failed: {e}")
                else:
                    # Standard shell fixing
                    try:
                        shell_fixer = ShapeFix_Shell(shell)
                        shell_fixer.Perform()
                        shell = shell_fixer.Shell()
                    except Exception as e:
                        if debug:
                            log(f"ShapeFix_Shell failed: {e}")
        except Exception as e:
            if debug:
                log(f"Shell validation failed: {e}")

        if debug:
            log("Shell construction complete")

        return shell

    if debug:
        log("Error: No shell found in sewn shape")

    return None
