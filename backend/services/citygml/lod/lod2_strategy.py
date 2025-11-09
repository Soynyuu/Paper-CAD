"""
LOD2 extraction strategy for CityGML buildings.

LOD2 is PLATEAU's primary use case, representing:
- Buildings with differentiated roof structures (flat, gabled, hipped, etc.)
- Thematic boundary surfaces: WallSurface, RoofSurface, GroundSurface, etc.
- More detailed than LOD1 (simple blocks) but less than LOD3 (architectural models)

This is the most common LOD in PLATEAU datasets.

⚠️ CRITICAL: Contains Issue #48 fix for boundedBy vs lod2Solid comparison.
"""

from typing import Optional, List, Any
import xml.etree.ElementTree as ET

from ..core.constants import NS, BOUNDED_BY_PREFERENCE_THRESHOLD
from ..core.types import CoordinateTransform3D, IDIndex, LODExtractionResult
from ..utils.logging import log
from .surface_extractors import extract_faces_from_surface_container, extract_solid_shells
from .bounded_by import extract_faces_from_all_bounded_surfaces, count_bounded_by_faces


def extract_lod2_geometry(
    elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    elem_id: str,
    debug: bool = False
) -> LODExtractionResult:
    """
    Extract LOD2 geometry from a building element using progressive fallback.

    LOD2 extraction strategies (in order):
    1. lod2Solid//gml:Solid - Standard solid structure
       ⚠️ CRITICAL: Includes Issue #48 fix to compare with boundedBy
    2. lod2MultiSurface - Multiple independent surfaces (skipped if boundedBy preferred)
    3. lod2Geometry - Generic geometry container (skipped if boundedBy preferred)
    4. boundedBy surfaces - All 6 CityGML boundary surface types

    Issue #48 Fix:
    When lod2Solid is found, we check if boundedBy has more detail by comparing
    face counts. If boundedBy has >= lod2Solid faces (threshold 1.0, not 1.2),
    we prefer boundedBy for more detailed geometry and skip intermediate strategies.

    Previous threshold (1.2) caused wall omissions in tall buildings like JP Tower:
    - lod2Solid: 74 faces (simplified envelope)
    - boundedBy: 80 faces (detailed walls)
    - Old: 80 >= 74*1.2 (88.8) = False → chose lod2Solid (wrong!)
    - New: 80 >= 74*1.0 (74.0) = True → choose boundedBy (correct!)

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        elem_id: Building ID for logging
        debug: Enable debug output

    Returns:
        LODExtractionResult with:
        - exterior_faces: List of faces extracted
        - interior_shells: List of interior shell face lists (cavities)
        - lod_level: "LOD2"
        - method: Extraction method used
        - prefer_bounded_by: Flag indicating if boundedBy was preferred over lod2Solid

    Example:
        >>> result = extract_lod2_geometry(
        ...     building, xyz_transform, id_index, "bldg_123", debug=True
        ... )
        >>> # [LOD2] Found bldg:lod2Solid//gml:Solid in bldg_123
        >>> # [LOD2] boundedBy has 80 vs lod2Solid's 74 faces
        >>> # → Preferring boundedBy strategy for more detailed geometry
        >>> result.lod_level
        'LOD2'
        >>> result.method
        'boundedBy surfaces (6 types)'
        >>> result.prefer_bounded_by
        True

    Notes:
        - Falls back through strategies if earlier ones fail or extract 0 faces
        - Coordinates are already re-centered by xyz_transform wrapper (PHASE:0)
        - Returns empty result if all strategies fail
        - The prefer_bounded_by flag is used by the pipeline to skip intermediate strategies
    """
    exterior_faces: List[Any] = []  # List[TopoDS_Face]
    interior_shells: List[List[Any]] = []  # List[List[TopoDS_Face]]
    prefer_bounded_by = False  # Issue #48: Flag to skip intermediate strategies

    # =========================================================================
    # Strategy 1: LOD2 Solid (standard gml:Solid structure)
    # =========================================================================
    # ⚠️ CRITICAL: This strategy includes the Issue #48 fix for comparing
    # lod2Solid vs boundedBy face counts
    log(f"[CONVERSION DEBUG] Falling back to LOD2 (PLATEAU's most common LOD)")
    lod2_solid = elem.find(".//bldg:lod2Solid", NS)
    if lod2_solid is not None:
        log(f"[CONVERSION DEBUG] Trying LOD2 Strategy 1: lod2Solid")
        solid_elem = lod2_solid.find(".//gml:Solid", NS)
        if solid_elem is not None:
            log(f"[CONVERSION DEBUG]   ✓ Found bldg:lod2Solid//gml:Solid")
            if debug:
                log(f"[LOD2] Found bldg:lod2Solid//gml:Solid in {elem_id}")

            # Extract exterior and interior shells
            exterior_faces_solid, interior_shells_faces = extract_solid_shells(
                solid_elem, xyz_transform, id_index, debug=debug
            )

            log(f"[CONVERSION DEBUG]   Extracted {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")
            if debug:
                log(f"[LOD2] Solid extraction: {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")

            if exterior_faces_solid:
                # ===================================================================
                # ⚠️ CRITICAL: Issue #48 Fix - Compare lod2Solid vs boundedBy
                # ===================================================================
                # Many PLATEAU buildings (especially tall ones like JP Tower) have:
                # - lod2Solid: Simplified envelope (basic shape)
                # - boundedBy/WallSurface: Detailed wall geometry (architectural details)
                # We need to check both and use the more detailed one
                log(f"[CONVERSION DEBUG]   Checking if boundedBy has more detailed geometry...")

                # Quick count of boundedBy faces without full extraction
                bounded_faces_count = count_bounded_by_faces(elem)

                if bounded_faces_count > 0:
                    log(f"[CONVERSION DEBUG]   Found {bounded_faces_count} boundedBy faces")
                    log(f"[CONVERSION DEBUG]   Comparing lod2Solid ({len(exterior_faces_solid)} faces) vs boundedBy ({bounded_faces_count} faces)...")

                    # If boundedBy has same or more faces, prefer it for more detail
                    # Fix for Issue #48: Threshold is 1.0 (same or more), not 1.2 (20% more)
                    # This ensures we don't miss detailed wall geometry in tall buildings
                    threshold = BOUNDED_BY_PREFERENCE_THRESHOLD  # 1.0 from constants
                    if bounded_faces_count >= len(exterior_faces_solid) * threshold:
                        log(f"[CONVERSION DEBUG]   ✓ boundedBy has {bounded_faces_count} vs lod2Solid's {len(exterior_faces_solid)} faces")
                        log(f"[CONVERSION DEBUG]   → Preferring boundedBy strategy for more detailed geometry")
                        log(f"[CONVERSION DEBUG]   → Skipping MultiSurface/Geometry strategies, jumping to boundedBy")
                        prefer_bounded_by = True  # Skip intermediate strategies
                        # Don't return here - let it fall through to boundedBy strategy below
                    else:
                        log(f"[CONVERSION DEBUG]   → lod2Solid has more detail ({len(exterior_faces_solid)} vs {bounded_faces_count} faces), using it")
                        return LODExtractionResult(
                            exterior_faces=exterior_faces_solid,
                            interior_shells=interior_shells_faces,
                            lod_level="LOD2",
                            method="lod2Solid//gml:Solid",
                            prefer_bounded_by=False
                        )
                else:
                    log(f"[CONVERSION DEBUG]   No boundedBy surfaces found, using lod2Solid result")
                    return LODExtractionResult(
                        exterior_faces=exterior_faces_solid,
                        interior_shells=interior_shells_faces,
                        lod_level="LOD2",
                        method="lod2Solid//gml:Solid",
                        prefer_bounded_by=False
                    )
            else:
                log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 1 failed (0 faces), trying next strategy...")
                if debug:
                    log(f"[LOD2] Solid extracted 0 faces, trying other strategies...")
        else:
            log(f"[CONVERSION DEBUG]   ✗ lod2Solid found but no gml:Solid child")
    else:
        log(f"[CONVERSION DEBUG] LOD2 Strategy 1: lod2Solid not found")

    # =========================================================================
    # Strategy 2: LOD2 MultiSurface (multiple independent surfaces)
    # =========================================================================
    # ⚠️ Skip if boundedBy was preferred (Issue #48 fix)
    if not prefer_bounded_by:
        lod2_multi = elem.find(".//bldg:lod2MultiSurface", NS)
    else:
        lod2_multi = None  # Force skip

    if lod2_multi is not None:
        log(f"[CONVERSION DEBUG] Trying LOD2 Strategy 2: lod2MultiSurface")
        if debug:
            log(f"[LOD2] Found bldg:lod2MultiSurface in {elem_id}")

        # Look for MultiSurface or CompositeSurface
        for surface_container in (
            lod2_multi.findall(".//gml:MultiSurface", NS) +
            lod2_multi.findall(".//gml:CompositeSurface", NS)
        ):
            faces_multi = extract_faces_from_surface_container(
                surface_container, xyz_transform, id_index, debug=debug
            )
            exterior_faces.extend(faces_multi)

        if debug:
            log(f"[LOD2] MultiSurface extraction: {len(exterior_faces)} faces")

        if exterior_faces:
            log(f"[CONVERSION DEBUG]   ✓ LOD2 Strategy 2 extracted {len(exterior_faces)} faces")
            return LODExtractionResult(
                exterior_faces=exterior_faces,
                interior_shells=[],  # MultiSurface doesn't have interior shells
                lod_level="LOD2",
                method="lod2MultiSurface",
                prefer_bounded_by=False
            )
        else:
            log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 2 failed (0 faces), trying next strategy...")
            if debug:
                log(f"[LOD2] MultiSurface extracted 0 faces, trying other strategies...")
            # Clear for next strategy
            exterior_faces = []

    # =========================================================================
    # Strategy 3: LOD2 Geometry (generic geometry container)
    # =========================================================================
    # ⚠️ Skip if boundedBy was preferred (Issue #48 fix)
    if not prefer_bounded_by:
        lod2_geom = elem.find(".//bldg:lod2Geometry", NS)
    else:
        lod2_geom = None  # Force skip

    if lod2_geom is not None:
        log(f"[CONVERSION DEBUG] Trying LOD2 Strategy 3: lod2Geometry")
        if debug:
            log(f"[LOD2] Found bldg:lod2Geometry in {elem_id}")

        # Try to find any surface structures
        for surface_container in (
            lod2_geom.findall(".//gml:MultiSurface", NS) +
            lod2_geom.findall(".//gml:CompositeSurface", NS) +
            lod2_geom.findall(".//gml:Solid", NS)
        ):
            if surface_container.tag.endswith("Solid"):
                # Process as Solid
                faces_geom, interior_shells_geom = extract_solid_shells(
                    surface_container, xyz_transform, id_index, debug=debug
                )
                exterior_faces.extend(faces_geom)
                interior_shells.extend(interior_shells_geom)
            else:
                # Process as MultiSurface/CompositeSurface
                faces_geom = extract_faces_from_surface_container(
                    surface_container, xyz_transform, id_index, debug=debug
                )
                exterior_faces.extend(faces_geom)

        if debug:
            log(f"[LOD2] Geometry extraction: {len(exterior_faces)} faces")

        if exterior_faces:
            log(f"[CONVERSION DEBUG]   ✓ LOD2 Strategy 3 extracted {len(exterior_faces)} faces")
            return LODExtractionResult(
                exterior_faces=exterior_faces,
                interior_shells=interior_shells,
                lod_level="LOD2",
                method="lod2Geometry",
                prefer_bounded_by=False
            )
        else:
            log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 3 failed (0 faces), trying next strategy...")
            if debug:
                log(f"[LOD2] Geometry extracted 0 faces, trying other strategies...")
            exterior_faces = []

    # =========================================================================
    # Strategy 4: LOD2/LOD3 boundedBy surfaces (all CityGML 2.0 boundary surface types)
    # =========================================================================
    # This strategy works for both LOD2 and LOD3 when solid structures are unavailable
    # CityGML 2.0 defines 6 _BoundarySurface types (we support all of them):
    # - WallSurface: vertical exterior wall (most common)
    # - RoofSurface: roof structure (most common)
    # - GroundSurface: ground contact surface (footprint)
    # - OuterCeilingSurface: exterior ceiling that is not a roof (rare)
    # - OuterFloorSurface: exterior upper floor that is not a roof (rare)
    # - ClosureSurface: virtual surfaces to close building volumes (PLATEAU uses these)
    log(f"[CONVERSION DEBUG] Trying LOD2 Strategy 4: boundedBy surfaces")

    # Use the comprehensive boundedBy extraction from bounded_by.py
    exterior_faces = extract_faces_from_all_bounded_surfaces(
        elem, xyz_transform, id_index,
        extract_faces_from_surface_container,  # Pass helper function
        debug=debug
    )

    if exterior_faces:
        log(f"[CONVERSION DEBUG]   ✓ LOD2 Strategy 4 extracted {len(exterior_faces)} faces from boundedBy")
        if debug:
            log(f"[CONVERSION DEBUG] ═══ Conversion via boundedBy strategy ═══")
        return LODExtractionResult(
            exterior_faces=exterior_faces,
            interior_shells=[],  # boundedBy surfaces don't have interior shells
            lod_level="LOD2",
            method="boundedBy surfaces (6 types)",
            prefer_bounded_by=prefer_bounded_by
        )
    else:
        log(f"[CONVERSION DEBUG]   ✗ LOD2 Strategy 4 failed (0 faces)")
        if debug:
            log(f"[LOD2] boundedBy extracted 0 faces")

    # All strategies failed
    if debug:
        log(f"[LOD2] No LOD2 geometry found, will fall back to LOD1")

    return LODExtractionResult(
        exterior_faces=[],
        interior_shells=[],
        lod_level="LOD2",
        method="No LOD2 geometry found",
        prefer_bounded_by=prefer_bounded_by
    )
