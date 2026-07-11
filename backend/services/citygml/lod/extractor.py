"""
LOD extraction orchestrator - coordinates LOD3→LOD2→LOD1 fallback chain.

This module implements the main LOD extraction pipeline that tries each LOD level
in order of priority (LOD3 → LOD2 → LOD1) and returns the first successful extraction.

⚠️ CRITICAL: This orchestrator preserves the exact LOD priority order from the
original implementation. Do NOT change the order without careful consideration.
"""

from typing import Optional
import xml.etree.ElementTree as ET

from ..core.types import CoordinateTransform3D, IDIndex, LODExtractionResult
from ..utils.logging import log
from ..geometry.tolerance import compute_building_tolerance
from .lod3_strategy import extract_lod3_geometry
from .lod2_strategy import extract_lod2_geometry
from .lod1_strategy import extract_lod1_geometry


def extract_building_geometry(
    elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    debug: bool = False,
    precision_mode: str = "standard",
    lod_target: str = "auto",
) -> LODExtractionResult:
    """
    Extract building geometry using LOD3→LOD2→LOD1 fallback chain.

    This is the main entry point for LOD extraction. It orchestrates the progressive
    fallback through LOD levels, trying each strategy in order until one succeeds.

    LOD Priority Order (⚠️ CRITICAL - DO NOT CHANGE):
    1. LOD3 (highest detail - architectural models)
    2. LOD2 (PLATEAU's primary use case - differentiated roofs)
    3. LOD1 (simple block models - last resort)

    Each LOD strategy may have multiple extraction methods internally (e.g., LOD2
    has lod2Solid, lod2MultiSurface, lod2Geometry, boundedBy). The strategy
    functions handle those internal fallbacks.

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        debug: Enable debug output
        precision_mode: Precision level ("standard", "high", "maximum", "ultra").
            Used to precompute tolerance once per building instead of per polygon.
            Issue #192: Performance optimization.

    Returns:
        LODExtractionResult with extracted faces and metadata.
        Always returns a result (may have empty faces if all strategies fail).

    Example:
        >>> result = extract_building_geometry(
        ...     building, xyz_transform, id_index, debug=True
        ... )
        >>> # [PHASE:1] LOD STRATEGY SELECTION
        >>> # [LOD3] No LOD3 geometry found
        >>> # [LOD2] Found bldg:lod2Solid//gml:Solid
        >>> # [LOD2] boundedBy has 80 vs lod2Solid's 74 faces
        >>> # → Preferring boundedBy strategy for more detailed geometry
        >>> result.lod_level
        'LOD2'
        >>> result.method
        'boundedBy surfaces (6 types)'
        >>> len(result.exterior_faces)
        80

    Notes:
        - Coordinates are already re-centered by xyz_transform wrapper (PHASE:0)
        - Returns first successful extraction (non-empty faces)
        - If all LOD strategies fail, returns empty result with LOD1 level
        - The calling pipeline is responsible for building solids from faces
        - Debug logging provides detailed extraction progress
    """
    # Get building ID for logging
    elem_id = (
        elem.get(f"{{{id_index.get('gml', 'http://www.opengis.net/gml')}}}id")
        if id_index
        else "unknown"
    )
    if not elem_id or elem_id == "unknown":
        # Try alternative ID lookup
        elem_id = elem.get("gml:id", "unknown")

    # =========================================================================
    # Precompute tolerance once per building (Issue #192 optimization)
    # =========================================================================
    # Instead of calling compute_tolerance_from_coords() per polygon inside
    # surface_extractors.py, we compute a single tolerance from the building's
    # bounding box. This is both faster and more accurate.
    building_tolerance = compute_building_tolerance(elem, xyz_transform, precision_mode)

    normalized_lod_target = lod_target or "auto"
    if normalized_lod_target not in {"auto", "LOD2", "LOD1"}:
        raise ValueError(
            f"lod_target must be one of auto/LOD2/LOD1, got: {normalized_lod_target}"
        )

    # Log extraction start
    if debug:
        log(f"\n{'=' * 80}")
        log(f"[PHASE:1] LOD STRATEGY SELECTION")
        log(f"{'=' * 80}")
        log(f"[INFO] Building ID: {elem_id}")
        strategy_labels = {
            "auto": "LOD3 → LOD2 → LOD1",
            "LOD2": "LOD2 → LOD1",
            "LOD1": "LOD1 only",
        }
        log(
            f"[INFO] Strategy: {strategy_labels[normalized_lod_target]} "
            "(with strategy-internal fallbacks)"
        )
        log(
            f"[INFO] Precomputed tolerance: {building_tolerance:.2e} (precision_mode={precision_mode})"
        )
        log(f"")

    strategies = {
        "LOD3": extract_lod3_geometry,
        "LOD2": extract_lod2_geometry,
        "LOD1": extract_lod1_geometry,
    }
    strategy_orders = {
        "auto": ("LOD3", "LOD2", "LOD1"),
        "LOD2": ("LOD2", "LOD1"),
        "LOD1": ("LOD1",),
    }
    levels = strategy_orders[normalized_lod_target]

    for index, level in enumerate(levels):
        result = strategies[level](
            elem,
            xyz_transform,
            id_index,
            elem_id,
            tolerance=building_tolerance,
            debug=debug,
        )
        if result.exterior_faces:
            if debug:
                log(
                    f"[PHASE:1] ✓ {level} extraction succeeded with "
                    f"{len(result.exterior_faces)} faces"
                )
                log(f"[PHASE:1] Method: {result.method}")
                if level == "LOD2" and result.prefer_bounded_by:
                    log(
                        "[PHASE:1] Note: boundedBy was preferred over "
                        "lod2Solid (Issue #48 fix)"
                    )
            return result

        if debug and index + 1 < len(levels):
            log(
                f"[PHASE:1] {level} extraction failed, "
                f"falling back to {levels[index + 1]}"
            )

    # All strategies failed
    if debug:
        log(f"[PHASE:1] ✗ All LOD extraction strategies failed for {elem_id}")
        log(
            f"[PHASE:1] No geometry found for target {normalized_lod_target} "
            f"(tried: {', '.join(levels)})"
        )

    # Return empty result
    return LODExtractionResult(
        exterior_faces=[],
        interior_shells=[],
        lod_level=levels[-1],
        method=f"All requested strategies failed ({' → '.join(levels)})",
    )
