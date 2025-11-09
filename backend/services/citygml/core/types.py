"""
Type definitions for CityGML to STEP conversion pipeline.

This module provides the core data structures used throughout the conversion process.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Tuple, Any
import xml.etree.ElementTree as ET


@dataclass
class ConversionContext:
    """
    Conversion context shared across all pipeline phases.

    This context object encapsulates all parameters and runtime state for the
    CityGML→STEP conversion pipeline, enabling clean separation between phases
    while maintaining data flow.

    Attributes:
        # Input parameters (immutable)
        gml_path: Path to input CityGML file
        out_step: Path to output STEP file
        limit: Maximum number of buildings to process (None = no limit)
        debug: Enable debug logging
        method: Conversion strategy ("solid", "auto", "sew", "extrude")
        sew_tolerance: Manual sewing tolerance override (None = auto-compute)
        reproject_to: Target CRS (e.g., 'EPSG:6676')
        source_crs: Source CRS override (None = auto-detect)
        auto_reproject: Auto-select projection for geographic CRS
        precision_mode: Precision level ("standard", "high", "maximum", "ultra")
        shape_fix_level: Shape fixing aggressiveness ("minimal", "standard", "aggressive", "ultra")
        building_ids: List of building IDs to filter (None = no filtering)
        filter_attribute: Attribute to match building_ids against (default: "gml:id")
        merge_building_parts: Fuse BuildingParts into single solid via Boolean union
        target_latitude: Target latitude for coordinate filtering (WGS84)
        target_longitude: Target longitude for coordinate filtering (WGS84)
        radius_meters: Radius for coordinate filtering (default: 100m)

        # Runtime state (mutable, populated during pipeline execution)
        root: Parsed XML root element (populated in preprocessing)
        id_index: XLink ID→Element index (populated in PHASE:1, CRITICAL)
        xyz_transform: 3D coordinate transformer (populated in PHASE:2, wrapped in PHASE:0)
        xy_transform: 2D coordinate transformer (populated in PHASE:2)
        source_crs_detected: Auto-detected source CRS (populated in PHASE:2)
        target_crs_selected: Selected target CRS (populated in PHASE:2)
        coord_offset: Coordinate offset for recentering (populated in PHASE:0)
        building_elements: Filtered building elements (populated in PHASE:3)
    """

    # === Input parameters ===
    gml_path: str
    out_step: str
    limit: Optional[int] = None
    debug: bool = False
    method: str = "solid"
    sew_tolerance: Optional[float] = None
    reproject_to: Optional[str] = None
    source_crs: Optional[str] = None
    auto_reproject: bool = True
    precision_mode: str = "standard"
    shape_fix_level: str = "minimal"
    building_ids: Optional[List[str]] = None
    filter_attribute: str = "gml:id"
    merge_building_parts: bool = True
    target_latitude: Optional[float] = None
    target_longitude: Optional[float] = None
    radius_meters: float = 100.0

    # === Runtime state (populated during pipeline) ===
    root: Optional[ET.Element] = None
    id_index: Dict[str, ET.Element] = field(default_factory=dict)
    xyz_transform: Optional[Callable[[float, float, float], Tuple[float, float, float]]] = None
    xy_transform: Optional[Callable[[float, float], Tuple[float, float]]] = None
    source_crs_detected: Optional[str] = None
    target_crs_selected: Optional[str] = None
    coord_offset: Optional[Tuple[float, float, float]] = None
    building_elements: List[ET.Element] = field(default_factory=list)


@dataclass
class LODExtractionResult:
    """
    Intermediate result from LOD extraction strategies.

    This represents the faces extracted from a building element before shell/solid
    construction. Used by LOD1/LOD2/LOD3 strategies to return faces and metadata.

    Attributes:
        exterior_faces: List of TopoDS_Face objects forming the outer shell
        interior_shells: List of interior shell face lists (cavities, courtyards)
        lod_level: LOD level used for extraction ("LOD3", "LOD2", "LOD1")
        method: Extraction method used (e.g., "lod2Solid//gml:Solid", "boundedBy surfaces")
        prefer_bounded_by: Flag indicating if boundedBy was preferred over lod2Solid (Issue #48)
    """
    exterior_faces: List[Any]  # List[TopoDS_Face]
    interior_shells: List[List[Any]]  # List[List[TopoDS_Face]]
    lod_level: str
    method: str
    prefer_bounded_by: bool = False


@dataclass
class ExtractionResult:
    """
    Final result of building extraction with constructed shape.

    This represents the final output after shell/solid construction and validation.

    Attributes:
        shape: Extracted OpenCASCADE shape (TopoDS_Shape)
        building_id: Building gml:id
        building_name: Building name (if available)
        lod_level: LOD level used for extraction ("LOD3", "LOD2", "LOD1", "footprint")
        method: Extraction method used ("solid", "multisurface", "boundedBy", "sew", "extrude")
        num_faces: Number of faces in the shape
        is_valid: Whether the shape passed validation
    """
    shape: Any  # TopoDS_Shape (not imported here to avoid OpenCASCADE dependency)
    building_id: str
    building_name: Optional[str] = None
    lod_level: str = "unknown"
    method: str = "unknown"
    num_faces: int = 0
    is_valid: bool = False


# Type aliases for clarity
CoordinateTransform3D = Callable[[float, float, float], Tuple[float, float, float]]
CoordinateTransform2D = Callable[[float, float], Tuple[float, float]]
IDIndex = Dict[str, ET.Element]
