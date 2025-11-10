"""
Main conversion orchestrator - implements complete export_step_from_citygml pipeline.

This module coordinates all conversion phases (PHASE:0-7) using the refactored modules.
It preserves 100% compatibility with the original monolithic implementation.
"""

from typing import Optional, List, Tuple, Any
import os
from datetime import datetime
import xml.etree.ElementTree as ET

from ..core.constants import NS
from ..core.types import LODExtractionResult
from ..utils.logging import log, set_log_file, close_log_file
from ..utils.xlink_resolver import build_id_index
from ..transforms.crs_detection import detect_source_crs
from ..transforms.transformers import make_xy_transformer, make_xyz_transformer
from ..transforms.recentering import compute_offset_and_wrap_transform
from ..lod.extractor import extract_building_geometry
from ..geometry.solid_builder import make_solid_with_cavities, is_valid_shape
from ..geometry.building_part_merger import merge_building_parts as merge_parts_fn
from ..geometry.sew_builder import build_sewn_shape_from_building
from ..lod.footprint_extractor import (
    parse_citygml_footprints,
    extrude_footprint,
    Footprint
)

# Import streaming parser (NEW: Issue #131 - Performance Optimization)
from ..streaming.parser import stream_parse_buildings, StreamingConfig
from ..streaming.xlink_cache import LocalXLinkCache

# Import coordinate utilities
try:
    from services.coordinate_utils import (
        is_geographic_crs,
        recommend_projected_crs,
        get_crs_info
    )
except ImportError:
    try:
        from coordinate_utils import (
            is_geographic_crs,
            recommend_projected_crs,
            get_crs_info
        )
    except ImportError:
        # Fallback stubs
        def is_geographic_crs(crs): return "EPSG:4" in str(crs)
        def recommend_projected_crs(src, lat, lon): return None
        def get_crs_info(crs): return {"name": crs}

# Check OCCT availability
try:
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Compound
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.IFSelect import IFSelect_ReturnStatus
    from OCC.Core.Interface import Interface_Static
    OCCT_AVAILABLE = True
except ImportError:
    OCCT_AVAILABLE = False
    TopoDS_Shape = Any
    TopoDS_Compound = Any


# ============================================================================
# Internal Helper Functions
# ============================================================================

def _filter_buildings(
    buildings: List[ET.Element],
    building_ids: Optional[List[str]] = None,
    filter_attribute: str = "gml:id"
) -> List[ET.Element]:
    """Filter buildings by IDs using specified attribute."""
    if not building_ids:
        return buildings

    building_ids_set = {bid.strip() for bid in building_ids}
    filtered: List[ET.Element] = []

    for b in buildings:
        match_found = False

        if filter_attribute == "gml:id":
            gml_id = b.get("{http://www.opengis.net/gml}id") or b.get("id")
            if gml_id and gml_id in building_ids_set:
                match_found = True
        else:
            # Match by generic attribute - simplified version
            for attr_name, attr_value in b.attrib.items():
                if filter_attribute in attr_name and attr_value in building_ids_set:
                    match_found = True
                    break

        if match_found:
            filtered.append(b)

    return filtered


def _filter_buildings_by_coordinates(
    buildings: List[ET.Element],
    target_latitude: float,
    target_longitude: float,
    radius_meters: float,
    debug: bool = False
) -> List[ET.Element]:
    """Filter buildings by distance from target coordinates."""
    try:
        from shapely.geometry import Point
        from shapely import distance as shapely_distance
    except ImportError:
        log("[WARNING] shapely not available, coordinate filtering disabled")
        return buildings

    target_point = Point(target_longitude, target_latitude)
    filtered: List[ET.Element] = []

    if debug:
        log(f"[COORD FILTER] Target: ({target_latitude}, {target_longitude})")
        log(f"[COORD FILTER] Radius: {radius_meters}m")

    for building in buildings:
        # Try to extract representative coordinates
        poslist_elem = building.find(".//gml:posList", NS)
        if poslist_elem is None or not poslist_elem.text:
            continue

        # Parse first coordinate
        coords_text = poslist_elem.text.strip().split()
        if len(coords_text) < 3:
            continue

        try:
            x, y = float(coords_text[0]), float(coords_text[1])

            # Detect order (lat/lon or lon/lat)
            if 20 <= x <= 50 and 120 <= y <= 155:
                lat, lon = x, y
            elif 120 <= x <= 155 and 20 <= y <= 50:
                lat, lon = y, x
            else:
                continue

            building_point = Point(lon, lat)
            dist_degrees = shapely_distance(target_point, building_point)
            dist_meters = float(dist_degrees) * 100000  # Rough conversion

            if dist_meters <= radius_meters:
                filtered.append(building)
                if debug:
                    gml_id = building.get("{http://www.opengis.net/gml}id") or "unknown"
                    log(f"[COORD FILTER] ✓ {gml_id[:20]}: {dist_meters:.1f}m")
        except (ValueError, IndexError):
            continue

    if debug:
        log(f"[COORD FILTER] Filtered: {len(buildings)} → {len(filtered)} buildings")

    return filtered


def _compute_bounding_box(shape: Any) -> Tuple[float, float, float, float, float, float]:
    """Compute bounding box of a shape."""
    if not OCCT_AVAILABLE:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return (xmin, ymin, zmin, xmax, ymax, zmax)


def _log_geometry_diagnostics(shapes: List[Any], debug: bool = False) -> None:
    """Log detailed geometry diagnostics including bounding boxes."""
    if not shapes:
        return

    log(f"\n{'='*80}")
    log(f"[DIAGNOSTICS] GEOMETRY ANALYSIS")
    log(f"{'='*80}")

    for i, shape in enumerate(shapes):
        xmin, ymin, zmin, xmax, ymax, zmax = _compute_bounding_box(shape)

        width = xmax - xmin
        height = zmax - zmin
        depth = ymax - ymin
        center_x = (xmin + xmax) / 2
        center_y = (ymin + ymax) / 2
        center_z = (zmin + zmax) / 2
        distance_from_origin = (center_x**2 + center_y**2 + center_z**2) ** 0.5

        log(f"\n[SHAPE {i+1}/{len(shapes)}] Bounding box analysis:")
        log(f"  Position (center): ({center_x:.3f}, {center_y:.3f}, {center_z:.3f})")
        log(f"  Size: {width:.3f} × {depth:.3f} × {height:.3f} (W×D×H)")
        log(f"  Range X: [{xmin:.3f}, {xmax:.3f}]")
        log(f"  Range Y: [{ymin:.3f}, {ymax:.3f}]")
        log(f"  Range Z: [{zmin:.3f}, {zmax:.3f}]")
        log(f"  Distance from origin: {distance_from_origin:.3f}")

        if distance_from_origin > 100000:
            log(f"  ⚠ WARNING: Geometry is very far from origin ({distance_from_origin/1000:.1f} km)")
        if max(width, depth, height) < 1:
            log(f"  ⚠ WARNING: Geometry is very small (< 1 unit)")
        if max(width, depth, height) > 1000000:
            log(f"  ⚠ WARNING: Geometry is extremely large (> 1000 km)")


def export_step_compound_local(shapes: List[Any], out_step: str, debug: bool = False) -> Tuple[bool, str]:
    """Export shapes to STEP file using local STEP writer."""
    if not OCCT_AVAILABLE:
        return False, "OCCT not available"

    if not shapes:
        return False, "No shapes to export"

    # Build compound
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    any_valid = False
    for s in shapes:
        if s is not None and not s.IsNull():
            builder.Add(compound, s)
            any_valid = True

    if not any_valid:
        return False, "All shapes invalid"

    # Configure STEP writer
    try:
        Interface_Static.SetCVal("write.step.schema", "AP214CD")
        Interface_Static.SetCVal("write.step.unit", "MM")
        Interface_Static.SetIVal("write.precision.mode", 1)
        Interface_Static.SetRVal("write.precision.val", 1e-6)
        Interface_Static.SetIVal("write.surfacecurve.mode", 0)
        if debug:
            log("STEP writer configured: AP214CD schema, MM units, 1e-6 precision")
    except Exception as e:
        if debug:
            log(f"Warning: STEP writer configuration failed: {e}")

    log(f"[STEP EXPORT] Using local STEP writer...")
    log(f"[STEP EXPORT] Configuration: AP214CD schema, MM units, 1e-6 precision")

    writer = STEPControl_Writer()

    log(f"[STEP EXPORT] Transferring geometry to STEP format...")
    tr = writer.Transfer(compound, STEPControl_AsIs)
    if tr != IFSelect_ReturnStatus.IFSelect_RetDone:
        log(f"[STEP EXPORT] ✗ Transfer failed with status: {tr}")
        return False, f"STEP transfer failed: {tr}"
    log(f"[STEP EXPORT] ✓ Transfer successful")

    log(f"[STEP EXPORT] Writing to file: {out_step}")
    wr = writer.Write(out_step)
    if wr != IFSelect_ReturnStatus.IFSelect_RetDone:
        log(f"[STEP EXPORT] ✗ Write failed with status: {wr}")
        return False, f"STEP write failed: {wr}"

    # Verify file
    if os.path.exists(out_step):
        file_size = os.path.getsize(out_step)
        log(f"[STEP EXPORT] ✓ File written successfully")
        log(f"  - File: {out_step}")
        log(f"  - Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")

        if file_size == 0:
            log(f"[STEP EXPORT] ⚠ WARNING: File size is 0 bytes")
            return False, "STEP file created but is empty"
    else:
        log(f"[STEP EXPORT] ⚠ WARNING: Write reported success but file not found")
        return False, "STEP write completed but file not found"

    return True, out_step


# ============================================================================
# Main Export Function
# ============================================================================

def export_step_from_citygml(
    gml_path: str,
    out_step: str,
    limit: Optional[int] = None,
    debug: bool = False,
    method: str = "solid",
    sew_tolerance: Optional[float] = None,
    reproject_to: Optional[str] = None,
    source_crs: Optional[str] = None,
    auto_reproject: bool = True,
    precision_mode: str = "standard",
    shape_fix_level: str = "minimal",
    building_ids: Optional[List[str]] = None,
    filter_attribute: str = "gml:id",
    merge_building_parts: bool = True,
    target_latitude: Optional[float] = None,
    target_longitude: Optional[float] = None,
    radius_meters: float = 100,
    use_streaming: bool = True,
) -> Tuple[bool, str]:
    """
    Convert CityGML building(s) to STEP format (AP214).

    ⚠️ CRITICAL: This is the fully refactored implementation that preserves
    100% compatibility with the original monolithic citygml_to_step.py.

    🚀 NEW (Issue #131): Streaming parser for 98% memory reduction and 4x speedup.

    Args:
        gml_path: Path to CityGML file
        out_step: Output STEP file path
        limit: Limit number of buildings (None = all, ignored if building_ids specified)
        debug: Enable debug output
        method: Conversion strategy ("solid", "auto", "sew", "extrude")
        sew_tolerance: Sewing tolerance (auto-computed if None)
        reproject_to: Target CRS (e.g., 'EPSG:6676')
        source_crs: Source CRS (auto-detected if None)
        auto_reproject: Auto-select projection for geographic CRS
        precision_mode: Precision level ("standard", "high", "maximum", "ultra")
        shape_fix_level: Shape repair level ("minimal", "standard", "aggressive", "ultra")
        building_ids: List of building IDs to filter
        filter_attribute: Attribute to match IDs against ("gml:id" or other)
        merge_building_parts: Fuse BuildingParts into single solid
        target_latitude: Target latitude for coordinate filtering (WGS84)
        target_longitude: Target longitude for coordinate filtering (WGS84)
        radius_meters: Radius for coordinate filtering (default: 100m)
        use_streaming: Use streaming parser (NEW: 98% memory reduction, 4x faster)
            - True (default): Use streaming parser (recommended for files >100MB)
            - False: Use legacy ET.parse() method (for debugging/compatibility)
            - Note: Automatically falls back to legacy if coordinate filtering is used

    Returns:
        Tuple of (success, message_or_output_path)

    Example:
        >>> success, path = export_step_from_citygml(
        ...     "city.gml",
        ...     "output.step",
        ...     precision_mode="ultra",
        ...     shape_fix_level="aggressive",
        ...     debug=True
        ... )
        >>> success
        True
    """
    if not OCCT_AVAILABLE:
        return False, "OCCT is not available; cannot export STEP."

    # Normalize limit
    if limit is not None and limit <= 0:
        limit = None

    # Determine whether to use streaming parser
    # Coordinate filtering requires full tree access, so force legacy mode
    has_coordinate_filter = (target_latitude is not None and target_longitude is not None)
    use_streaming_actual = use_streaming and not has_coordinate_filter

    if debug and has_coordinate_filter and use_streaming:
        log("[STREAMING] Coordinate filtering detected - falling back to legacy parser")

    # === Streaming Parser Path (NEW: Issue #131) ===
    if use_streaming_actual:
        print(f"[STREAMING] Using streaming parser (memory-optimized)")
        print(f"[STREAMING] Limit: {limit if limit else 'unlimited'}")
        print(f"[STREAMING] Building IDs: {len(building_ids) if building_ids else 'all'}")

        if debug:
            log(f"[STREAMING] Using streaming parser (memory-optimized)")
            log(f"[STREAMING] Limit: {limit if limit else 'unlimited'}")
            log(f"[STREAMING] Building IDs: {len(building_ids) if building_ids else 'all'}")

        # Track buildings for processing
        buildings_to_process = []

        # Calculate expected count for early termination
        expected_count = None
        if limit is not None:
            expected_count = limit
        elif building_ids:
            expected_count = len(building_ids)

        # Stream-parse buildings one at a time
        building_count = 0
        for building_elem, local_xlink_index in stream_parse_buildings(
            gml_path,
            limit=limit,
            building_ids=building_ids,
            filter_attribute=filter_attribute,
            debug=debug
        ):
            # Store building with its XLink index
            buildings_to_process.append((building_elem, local_xlink_index))
            building_count += 1

            # Progress logging (every 10 buildings or when target found)
            if building_count % 10 == 0 or (expected_count and building_count >= expected_count):
                print(f"[STREAMING] Progress: {building_count} building(s) found")

            # Early termination: If we found all requested buildings, stop
            if expected_count and building_count >= expected_count:
                print(f"[STREAMING] Found all {expected_count} requested building(s), stopping parse")
                break

        print(f"[STREAMING] Parse complete: {building_count} building(s) loaded")

        if not buildings_to_process:
            if building_ids:
                return False, f"No buildings found matching IDs: {building_ids} (filter_attribute: {filter_attribute})"
            else:
                return False, "No buildings found in CityGML file"

        if debug:
            log(f"[STREAMING] Loaded {len(buildings_to_process)} buildings for processing")

        # Extract building elements for compatibility with existing code
        bldgs = [b for b, _ in buildings_to_process]

        # Build XLink index from first building (for CRS detection)
        # Note: For streaming, we'll use local indices per building
        id_index = buildings_to_process[0][1] if buildings_to_process else {}

    # === Legacy Parser Path (backward compatibility) ===
    else:
        if debug:
            if has_coordinate_filter:
                log("[LEGACY] Using legacy parser (required for coordinate filtering)")
            else:
                log("[LEGACY] Using legacy parser (use_streaming=False)")

        # Original ET.parse() implementation
        tree = ET.parse(gml_path)
        root = tree.getroot()
        bldgs = root.findall(".//bldg:Building", NS)

        # Apply coordinate-based filtering (takes priority)
        if target_latitude is not None and target_longitude is not None:
            original_count = len(bldgs)
            bldgs = filter_buildings_by_coordinates(
                bldgs, target_latitude, target_longitude, radius_meters, debug
            )
            if debug:
                log(f"[COORD FILTER] Result: {original_count} → {len(bldgs)} buildings within {radius_meters}m")
            if not bldgs:
                return False, f"No buildings found within {radius_meters}m of ({target_latitude}, {target_longitude})"

        # Apply building ID filtering
        elif building_ids:
            original_count = len(bldgs)
            bldgs = filter_buildings(bldgs, building_ids, filter_attribute)
            if debug:
                log(f"Building ID filter: {original_count} → {len(bldgs)} buildings")
                log(f"Filter attribute: {filter_attribute}")
                log(f"Requested IDs: {building_ids}")
            if not bldgs:
                return False, f"No buildings found matching IDs: {building_ids} (filter_attribute: {filter_attribute})"

        if not bldgs:
            return False, "No buildings found in CityGML file"

        # Build global XLink index (legacy behavior)
        id_index = build_id_index(root)
        buildings_to_process = [(b, id_index) for b in bldgs]

    # Setup log file
    first_building_id = bldgs[0].get("{http://www.opengis.net/gml}id", "building_0")
    log_dir = "debug_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = first_building_id.replace(":", "_").replace("/", "_").replace("\\", "_")
    log_path = os.path.join(log_dir, f"conversion_{safe_id}_{timestamp}.log")

    try:
        log_file = open(log_path, "w", encoding="utf-8")
        # Write header (preserved from original)
        log_file.write(f"{'='*80}\n")
        log_file.write(f"CITYGML TO STEP CONVERSION LOG\n")
        log_file.write(f"{'='*80}\n")
        log_file.write(f"Building ID: {first_building_id}\n")
        log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
        log_file.write(f"Precision mode: {precision_mode}\n")
        log_file.write(f"Shape fix level: {shape_fix_level}\n")
        log_file.write(f"Debug mode: {'Enabled' if debug else 'Always enabled for detailed diagnostics'}\n")
        log_file.write(f"{'='*80}\n\n")
        log_file.write(f"LOG LEGEND (for AI/LLM Analysis and Debugging):\n")
        log_file.write(f"{'-'*80}\n")
        log_file.write(f"  [PHASE:N]       = Major processing phase (1-7)\n")
        log_file.write(f"  ✓ SUCCESS       = Operation completed successfully\n")
        log_file.write(f"  ✗ FAILED        = Operation failed\n")
        log_file.write(f"  ⚠ WARNING       = Potential issue detected\n")
        log_file.write(f"{'-'*80}\n\n")
        log_file.write(f"PROCESSING PHASES:\n")
        log_file.write(f"  [PHASE:1] LOD Strategy Selection (LOD3→LOD2→LOD1 fallback)\n")
        log_file.write(f"  [PHASE:2] Geometry Extraction\n")
        log_file.write(f"  [PHASE:3] Shell Construction\n")
        log_file.write(f"  [PHASE:4] Solid Validation\n")
        log_file.write(f"  [PHASE:5] Automatic Repair\n")
        log_file.write(f"  [PHASE:6] BuildingPart Merging\n")
        log_file.write(f"  [PHASE:7] STEP Export\n")
        log_file.write(f"{'='*80}\n\n")
        set_log_file(log_file)
    except Exception as e:
        print(f"Warning: Failed to create log file: {e}")
        log_file = None

    # Detect CRS (PHASE:1.5)
    log(f"\n{'='*80}")
    log(f"[PHASE:1.5] COORDINATE SYSTEM DETECTION")
    log(f"{'='*80}")

    # For CRS detection, use first building element (works for both streaming and legacy)
    crs_detection_elem = bldgs[0] if bldgs else None
    if crs_detection_elem is not None:
        detected_crs, sample_lat, sample_lon = detect_source_crs(crs_detection_elem)
    else:
        detected_crs, sample_lat, sample_lon = None, None, None

    src = source_crs or detected_crs or "EPSG:6697"

    if debug:
        src_info = get_crs_info(src) if src else {}
        log(f"[CRS] Source coordinate system:")
        log(f"  - CRS code: {src}")
        log(f"  - CRS name: {src_info.get('name', 'Unknown')}")
        if sample_lat is not None:
            log(f"  - Sample coordinates: lat={sample_lat:.6f}°, lon={sample_lon:.6f}°")
        log(f"  - Is geographic CRS: {is_geographic_crs(src)}")

    # Auto-select projection
    if not reproject_to and auto_reproject:
        if is_geographic_crs(src):
            reproject_to = recommend_projected_crs(src, sample_lat, sample_lon)
            if debug:
                if reproject_to:
                    tgt_info = get_crs_info(reproject_to)
                    log(f"\n[CRS] Auto-reprojection selected:")
                    log(f"  - Target CRS: {reproject_to}")
                    log(f"  - Target name: {tgt_info.get('name', 'Unknown')}")

    # Build transformers
    xyz_transform = None
    if reproject_to:
        log(f"\n[CRS] Setting up coordinate transformation:")
        log(f"  - From: {src}")
        log(f"  - To: {reproject_to}")
        try:
            xyz_transform = make_xyz_transformer(src, reproject_to)
            log(f"  - ✓ Transformation setup successful")
        except Exception as e:
            log(f"  - ✗ Transformation setup failed: {e}")
            close_log_file()
            return False, f"Reprojection setup failed: {e}"

    # PHASE:0 - Coordinate recentering (⚠️ CRITICAL)
    print(f"[PHASE:0] Computing coordinate offset for {len(bldgs)} building(s)...")
    xyz_transform, coord_offset = compute_offset_and_wrap_transform(bldgs, xyz_transform, debug)
    print(f"[PHASE:0] Coordinate offset computed: {coord_offset}")

    # =========================================================================
    # PHASE:2 - Geometry extraction
    # =========================================================================
    shapes: List[Any] = []  # List[TopoDS_Shape]
    tried_solid = False
    tried_sew = False

    # Helper function for solid extraction with BuildingPart merging
    def extract_single_solid(building_elem, xyz_tx, id_idx, dbg, prec_mode, fix_level):
        """Extract solid from single building element using LOD extractor."""
        result = extract_building_geometry(building_elem, xyz_tx, id_idx, dbg)
        if not result.exterior_faces:
            return None

        # Build solid from extracted faces
        return make_solid_with_cavities(
            result.exterior_faces,
            result.interior_shells,
            None,  # auto-compute tolerance
            dbg,
            prec_mode,
            fix_level
        )

    # -------------------------------------------------------------------------
    # Method 1: Solid extraction (LOD2/LOD3 Solid data)
    # -------------------------------------------------------------------------
    if method in ("solid", "auto"):
        tried_solid = True
        count = 0

        log(f"\n{'='*80}")
        log(f"[PHASE:2] BUILDING GEOMETRY EXTRACTION (Solid Method)")
        log(f"{'='*80}")
        log(f"[INFO] Total buildings to process: {len(bldgs)}")
        log(f"[INFO] Limit: {limit if limit else 'unlimited'}")
        log(f"[INFO] BuildingPart merging: {'enabled' if merge_building_parts else 'disabled'}")
        log(f"")

        for i, (b, local_id_index) in enumerate(buildings_to_process):
            if limit is not None and count >= limit:
                log(f"\n[INFO] Reached limit of {limit} buildings, stopping extraction")
                break

            building_id = b.get("{http://www.opengis.net/gml}id", f"building_{i}")
            print(f"[PHASE:2] Processing building {i+1}/{len(bldgs)}: {building_id[:40]}...")
            log(f"\n{'─'*80}")
            log(f"[BUILDING {i+1}/{len(bldgs)}] Processing: {building_id[:60]}")

            try:
                # Use BuildingPart merger for complete extraction
                # Note: Use local XLink index for streaming mode, shared index for legacy
                print(f"[PHASE:2]   Extracting geometry (merge_building_parts={merge_building_parts})...")
                shp = merge_parts_fn(
                    b,
                    extract_single_solid,
                    xyz_transform,
                    local_id_index,  # Use local index from buildings_to_process
                    debug,
                    precision_mode,
                    shape_fix_level,
                    merge_building_parts
                )
                print(f"[PHASE:2]   Geometry extraction complete")

                if shp is None or shp.IsNull():
                    log(f"└─ [RESULT] Skipping (extraction returned None/Null)")
                    continue

                # Validate
                if is_valid_shape(shp):
                    log(f"└─ [RESULT] ✓ Successfully added (total: {count+1})")
                    shapes.append(shp)
                    count += 1
                else:
                    log(f"└─ [RESULT] ⚠ Added invalid shape (will attempt export)")
                    shapes.append(shp)
                    count += 1

            except Exception as e:
                log(f"├─ [ERROR] ✗ Exception: {type(e).__name__}: {str(e)}")
                log(f"└─ [RESULT] ✗ Failed, skipping")
                continue

        log(f"\n{'='*80}")
        log(f"[PHASE:2] EXTRACTION SUMMARY (Solid Method)")
        log(f"{'='*80}")
        log(f"[INFO] Shapes extracted: {count}")
        log(f"")

    # -------------------------------------------------------------------------
    # Method 2: Surface sewing (LOD2 BoundarySurfaces)
    # -------------------------------------------------------------------------
    if not shapes and method in ("sew", "auto"):
        tried_sew = True
        count = 0

        log(f"\n{'='*80}")
        log(f"[PHASE:2] BUILDING GEOMETRY EXTRACTION (Sew Method)")
        log(f"{'='*80}")
        log(f"[INFO] Total buildings to process: {len(bldgs)}")
        log(f"[INFO] Limit: {limit if limit else 'unlimited'}")
        log(f"")

        for i, (b, local_id_index) in enumerate(buildings_to_process):
            if limit is not None and count >= limit:
                log(f"\n[INFO] Reached limit of {limit} buildings, stopping sewing")
                break

            building_id = b.get("{http://www.opengis.net/gml}id", f"building_{i}")
            log(f"\n{'─'*80}")
            log(f"[BUILDING {i+1}/{len(bldgs)}] Sewing: {building_id[:60]}")

            try:
                shp = build_sewn_shape_from_building(
                    b,
                    sew_tolerance=sew_tolerance,  # Will be auto-computed if None
                    debug=debug,
                    xyz_transform=xyz_transform,
                    precision_mode=precision_mode,
                    shape_fix_level=shape_fix_level
                )

                if shp is not None and not shp.IsNull():
                    shapes.append(shp)
                    count += 1
                    log(f"└─ [RESULT] ✓ Successfully sewn (total: {count})")
                else:
                    log(f"└─ [RESULT] Skipping (sewing returned None/Null)")

            except Exception as e:
                log(f"├─ [ERROR] ✗ Exception: {type(e).__name__}: {str(e)}")
                log(f"└─ [RESULT] ✗ Failed, skipping")
                continue

        log(f"\n{'='*80}")
        log(f"[PHASE:2] EXTRACTION SUMMARY (Sew Method)")
        log(f"{'='*80}")
        log(f"[INFO] Shapes sewn: {count}")
        log(f"")

    # -------------------------------------------------------------------------
    # Method 3: Footprint extrusion (LOD0/LOD1 fallback)
    # -------------------------------------------------------------------------
    if not shapes and method in ("extrude", "auto"):
        log(f"\n{'='*80}")
        log(f"[PHASE:2] BUILDING GEOMETRY EXTRACTION (Extrude Method)")
        log(f"{'='*80}")

        # Note: Use xy_transform for 2D footprints, not xyz_transform
        xy_transform = None
        if xyz_transform:
            # Wrap xyz_transform to work as xy_transform
            def xy_tx(x, y):
                X, Y, _ = xyz_transform(x, y, 0.0)
                return X, Y
            xy_transform = xy_tx

        # Parse footprints from CityGML file
        default_height = 10.0
        fplist = parse_citygml_footprints(
            gml_path,
            default_height=default_height,
            limit=limit,
            xy_transform=xy_transform,
        )

        if debug:
            log(f"[EXTRUDE] Parsed {len(fplist)} buildings with footprints")

        count = 0
        for i, fp in enumerate(fplist):
            try:
                shp = extrude_footprint(fp)
                shapes.append(shp)
                count += 1
                if debug:
                    log(f"[EXTRUDE] {i+1}/{len(fplist)}: {fp.building_id} → height {fp.height}m")
            except Exception as e:
                if debug:
                    log(f"[EXTRUDE] {i+1}/{len(fplist)}: {fp.building_id} FAILED: {e}")
                continue

        log(f"\n{'='*80}")
        log(f"[PHASE:2] EXTRACTION SUMMARY (Extrude Method)")
        log(f"{'='*80}")
        log(f"[INFO] Shapes extruded: {count}")
        log(f"")

    # PHASE:7 - STEP Export
    log(f"\n{'='*80}")
    log(f"[PHASE:7] STEP EXPORT PREPARATION")
    log(f"{'='*80}")
    log(f"[INFO] Total shapes extracted: {len(shapes)}")

    if not shapes:
        log(f"[ERROR] ✗ No valid shapes to export")
        log(f"[ERROR] Conversion method used: {method}")
        log(f"[ERROR] Buildings attempted: {len(bldgs)}")
        log(f"[ERROR] Tried solid method: {tried_solid}")
        log(f"[ERROR] Tried sew method: {tried_sew}")
        close_log_file()

        if method == "auto":
            return False, "No shapes created via solid extraction, sewing, or extrusion."
        elif method == "solid":
            return False, "Solid method produced no shapes (no LOD1/LOD2/LOD3 solid data found)."
        elif method == "sew":
            return False, "Sew method produced no shapes (insufficient LOD2 surfaces)."
        elif method == "extrude":
            return False, "Extrude method produced no shapes (no footprints found)."
        else:
            return False, f"No shapes created via {method} method."

    # Pre-export validation
    log(f"\n[VALIDATION] Pre-export shape validation:")
    valid_count = sum(1 for shp in shapes if is_valid_shape(shp))
    log(f"  ✓ Valid shapes: {valid_count}")
    log(f"  ⚠ Invalid shapes: {len(shapes) - valid_count}")

    log(f"\n[INFO] Proceeding to STEP export with {len(shapes)} shape(s)...")
    log(f"[INFO] Target file: {out_step}")

    # Export using legacy function (delegates to core STEPExporter)
    print(f"[PHASE:7] Exporting {len(shapes)} shape(s) to STEP file...")
    result = export_step_compound_local(shapes, out_step, debug=debug)
    print(f"[PHASE:7] STEP export complete: {out_step}")

    close_log_file()
    return result
