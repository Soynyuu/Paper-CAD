"""
LOD3 extraction strategy for CityGML buildings.

LOD3 represents architectural models with:
- Detailed wall and roof structures with surface textures
- Openings: windows (bldg:Window), doors (bldg:Door)
- BuildingInstallation elements (balconies, chimneys, etc.)

This is the highest priority LOD in the extraction hierarchy (LOD3→LOD2→LOD1).
"""

from typing import Optional, List, Any
import xml.etree.ElementTree as ET

from ..core.constants import NS
from ..core.types import CoordinateTransform3D, IDIndex, LODExtractionResult
from ..utils.logging import log
from .surface_extractors import extract_faces_from_surface_container, extract_solid_shells


def extract_lod3_geometry(
    elem: ET.Element,
    xyz_transform: Optional[CoordinateTransform3D],
    id_index: IDIndex,
    elem_id: str,
    debug: bool = False
) -> LODExtractionResult:
    """
    Extract LOD3 geometry from a building element using progressive fallback.

    LOD3 extraction strategies (in order):
    1. lod3Solid//gml:Solid - Most detailed solid structure
    2. lod3MultiSurface - Multiple independent detailed surfaces
    3. lod3Geometry - Generic LOD3 geometry container

    Args:
        elem: Building or BuildingPart element
        xyz_transform: Optional coordinate transformation function
        id_index: XLink resolution index (from build_id_index())
        elem_id: Building ID for logging
        debug: Enable debug output

    Returns:
        LODExtractionResult with:
        - exterior_faces: List of faces extracted
        - interior_shells: List of interior shell face lists (cavities, from lod3Solid only)
        - lod_level: "LOD3"
        - method: Extraction method used

    Example:
        >>> result = extract_lod3_geometry(
        ...     building, xyz_transform, id_index, "bldg_123", debug=True
        ... )
        >>> # [LOD3] Found bldg:lod3Solid//gml:Solid in bldg_123
        >>> # [Solid] Extraction complete: 156 exterior faces, 2 interior shells
        >>> result.lod_level
        'LOD3'
        >>> result.method
        'lod3Solid//gml:Solid'
        >>> len(result.exterior_faces)
        156

    Notes:
        - Falls back through strategies if earlier ones fail or extract 0 faces
        - Coordinates are already re-centered by xyz_transform wrapper (PHASE:0)
        - Returns empty result if all strategies fail
        - Interior shells only extracted from lod3Solid (not MultiSurface/Geometry)
    """
    exterior_faces: List[Any] = []  # List[TopoDS_Face]
    interior_shells: List[List[Any]] = []  # List[List[TopoDS_Face]]
    method_used = None

    # =========================================================================
    # Strategy 1: LOD3 Solid (most detailed solid structure)
    # =========================================================================
    lod3_solid = elem.find(".//bldg:lod3Solid", NS)
    if lod3_solid is not None:
        log(f"[CONVERSION DEBUG] Trying LOD3 Strategy 1: lod3Solid")
        solid_elem = lod3_solid.find(".//gml:Solid", NS)
        if solid_elem is not None:
            log(f"[CONVERSION DEBUG]   ✓ Found bldg:lod3Solid//gml:Solid")
            if debug:
                log(f"[LOD3] Found bldg:lod3Solid//gml:Solid in {elem_id}")

            # Extract exterior and interior shells
            exterior_faces_solid, interior_shells_faces = extract_solid_shells(
                solid_elem, xyz_transform, id_index, debug=debug
            )

            log(f"[CONVERSION DEBUG]   Extracted {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")
            if debug:
                log(f"[LOD3] Solid extraction: {len(exterior_faces_solid)} exterior faces, {len(interior_shells_faces)} interior shells")

            if exterior_faces_solid:
                return LODExtractionResult(
                    exterior_faces=exterior_faces_solid,
                    interior_shells=interior_shells_faces,
                    lod_level="LOD3",
                    method="lod3Solid//gml:Solid"
                )
            else:
                log(f"[CONVERSION DEBUG]   ✗ LOD3 Strategy 1 failed (0 faces), trying next strategy...")
                if debug:
                    log(f"[LOD3] Solid extracted 0 faces, trying other strategies...")
        else:
            log(f"[CONVERSION DEBUG]   ✗ lod3Solid found but no gml:Solid child")
    else:
        log(f"[CONVERSION DEBUG] LOD3 Strategy 1: lod3Solid not found")

    # =========================================================================
    # Strategy 2: LOD3 MultiSurface (multiple detailed surfaces)
    # =========================================================================
    lod3_multi = elem.find(".//bldg:lod3MultiSurface", NS)
    if lod3_multi is not None:
        log(f"[CONVERSION DEBUG] Trying LOD3 Strategy 2: lod3MultiSurface")
        if debug:
            log(f"[LOD3] Found bldg:lod3MultiSurface in {elem_id}")

        # Look for MultiSurface or CompositeSurface
        for surface_container in (
            lod3_multi.findall(".//gml:MultiSurface", NS) +
            lod3_multi.findall(".//gml:CompositeSurface", NS)
        ):
            faces_multi = extract_faces_from_surface_container(
                surface_container, xyz_transform, id_index, debug=debug
            )
            exterior_faces.extend(faces_multi)

        if debug:
            log(f"[LOD3] MultiSurface extraction: {len(exterior_faces)} faces")

        if exterior_faces:
            log(f"[CONVERSION DEBUG]   ✓ LOD3 Strategy 2 extracted {len(exterior_faces)} faces")
            return LODExtractionResult(
                exterior_faces=exterior_faces,
                interior_shells=[],  # MultiSurface doesn't have interior shells
                lod_level="LOD3",
                method="lod3MultiSurface"
            )
        else:
            log(f"[CONVERSION DEBUG]   ✗ LOD3 Strategy 2 failed (0 faces), trying next strategy...")
            if debug:
                log(f"[LOD3] MultiSurface extracted 0 faces, trying other strategies...")

    # =========================================================================
    # Strategy 3: LOD3 Geometry (generic LOD3 geometry container)
    # =========================================================================
    lod3_geom = elem.find(".//bldg:lod3Geometry", NS)
    if lod3_geom is not None:
        log(f"[CONVERSION DEBUG] Trying LOD3 Strategy 3: lod3Geometry")
        if debug:
            log(f"[LOD3] Found bldg:lod3Geometry in {elem_id}")

        # Reset faces for this strategy
        exterior_faces = []

        # Try to find any surface structures
        for surface_container in (
            lod3_geom.findall(".//gml:MultiSurface", NS) +
            lod3_geom.findall(".//gml:CompositeSurface", NS) +
            lod3_geom.findall(".//gml:Solid", NS)
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
            log(f"[LOD3] Geometry extraction: {len(exterior_faces)} faces")

        if exterior_faces:
            log(f"[CONVERSION DEBUG]   ✓ LOD3 Strategy 3 extracted {len(exterior_faces)} faces")
            return LODExtractionResult(
                exterior_faces=exterior_faces,
                interior_shells=interior_shells,
                lod_level="LOD3",
                method="lod3Geometry"
            )
        else:
            log(f"[CONVERSION DEBUG]   ✗ LOD3 Strategy 3 failed (0 faces)")
            if debug:
                log(f"[LOD3] Geometry extracted 0 faces")

    # All strategies failed
    if debug:
        log(f"[LOD3] No LOD3 geometry found, will fall back to LOD2 for {elem_id}")

    return LODExtractionResult(
        exterior_faces=[],
        interior_shells=[],
        lod_level="LOD3",
        method="No LOD3 geometry found"
    )
