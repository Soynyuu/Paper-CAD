"""
LOD1 extraction strategy for CityGML buildings.

LOD1 represents simple 3D block models:
- Building footprint extruded to a uniform height
- No roof differentiation (flat tops)
- Minimal detail, used when LOD2/LOD3 are unavailable

This is the final fallback in the LOD3→LOD2→LOD1 priority chain.
Common in early PLATEAU datasets or overview-level city models.
"""

from typing import Optional, Any
import xml.etree.ElementTree as ET

from ..core.constants import NS
from ..core.types import CoordinateTransform3D, IDIndex, LODExtractionResult
from ..utils.logging import log
from .surface_extractors import extract_solid_shells


def extract_lod1_geometry(
    elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    elem_id: str,
    debug: bool = False
) -> LODExtractionResult:
    """
    Extract LOD1 geometry from a building element.

    LOD1 extraction strategy:
    1. Find bldg:lod1Solid element
    2. Extract gml:Solid from within
    3. Extract exterior and interior shells
    4. Return faces for shell building

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        elem_id: Building ID for logging
        debug: Enable debug output

    Returns:
        LODExtractionResult with:
        - exterior_faces: List of faces from LOD1 solid
        - interior_shells: List of interior shell face lists (cavities)
        - lod_level: "LOD1"
        - method: Extraction method used

    Example:
        >>> result = extract_lod1_geometry(
        ...     building, xyz_transform, id_index, "bldg_123", debug=True
        ... )
        >>> # [LOD1] Found bldg:lod1Solid//gml:Solid in bldg_123
        >>> # [Solid] Extraction complete: 6 exterior faces, 0 interior shells
        >>> result.lod_level
        'LOD1'
        >>> len(result.exterior_faces)
        6

    Notes:
        - This is the simplest LOD extraction strategy
        - Returns empty result if no lod1Solid found
        - Coordinates are already re-centered by xyz_transform wrapper (PHASE:0)
        - Does not attempt to build solid - that's handled by the pipeline
    """
    lod1_solid = elem.find(".//bldg:lod1Solid", NS)
    if lod1_solid is None:
        # No LOD1 geometry found
        if debug:
            log(f"[LOD1] No lod1Solid found in {elem_id}")
        return LODExtractionResult(
            exterior_faces=[],
            interior_shells=[],
            lod_level="LOD1",
            method="lod1Solid (not found)"
        )

    solid_elem = lod1_solid.find(".//gml:Solid", NS)
    if solid_elem is None:
        # lod1Solid found but no gml:Solid child
        if debug:
            log(f"[LOD1] lod1Solid found but no gml:Solid child in {elem_id}")
        return LODExtractionResult(
            exterior_faces=[],
            interior_shells=[],
            lod_level="LOD1",
            method="lod1Solid (no gml:Solid)"
        )

    if debug:
        log(f"[LOD1] Found bldg:lod1Solid//gml:Solid in {elem_id}")

    # Extract exterior and interior shells
    exterior_faces, interior_shells = extract_solid_shells(
        solid_elem, xyz_transform, id_index, debug=debug
    )

    if debug:
        log(f"[LOD1] Extracted {len(exterior_faces)} exterior faces, {len(interior_shells)} interior shells")

    return LODExtractionResult(
        exterior_faces=exterior_faces,
        interior_shells=interior_shells,
        lod_level="LOD1",
        method="lod1Solid//gml:Solid"
    )
