"""
Parallel building processing using ProcessPoolExecutor (Issue #192).

OpenCASCADE is NOT thread-safe, so we use process-based parallelism.
Each worker process gets its own OCCT instance and processes one building
at a time.

The worker receives serialized inputs (XML string, scalar parameters)
and returns a BREP string. The main process deserializes the result.

This module is only used when processing 3+ buildings to amortize
the process startup overhead.
"""

import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

from ..utils.logging import log


def _process_building_worker(
    building_xml_str: str,
    source_crs: str,
    target_crs: str,
    coord_offset: Optional[Tuple[float, float, float]],
    precision_mode: str,
    shape_fix_level: str,
    merge_building_parts: bool,
    debug: bool,
    target_lod: Optional[str] = None,
) -> Optional[bytes]:
    """
    Worker function for parallel building processing.

    Runs in a separate process. Receives serialized inputs, reconstructs
    all necessary objects, processes the building, and returns the result
    as a BREP byte string.

    Args:
        building_xml_str: Building element serialized as XML string
        source_crs: Source CRS (e.g., "EPSG:6697")
        target_crs: Target CRS (e.g., "EPSG:6677")
        coord_offset: Coordinate offset from recentering (x, y, z) or None
        precision_mode: Precision mode for tolerance computation
        shape_fix_level: Shape fix level for solid building
        merge_building_parts: Whether to merge BuildingParts
        debug: Enable debug logging
        target_lod: Target LOD level ("LOD1", "LOD2", "LOD3", or None for auto-fallback)

    Returns:
        BREP byte string of the resulting shape, or None if processing failed
    """
    try:
        # Reconstruct building element from XML string
        building_elem = ET.fromstring(building_xml_str)

        # Reconstruct coordinate transform
        from ..transforms.transformers import make_xyz_transformer

        xyz_transform = make_xyz_transformer(source_crs, target_crs)

        # Apply coordinate offset if provided
        if coord_offset is not None and xyz_transform is not None:
            original_transform = xyz_transform
            ox, oy, oz = coord_offset

            def wrapped_transform(x, y, z):
                tx, ty, tz = original_transform(x, y, z)
                return (tx + ox, ty + oy, tz + oz)

            xyz_transform = wrapped_transform
        elif coord_offset is not None:
            ox, oy, oz = coord_offset

            def offset_transform(x, y, z):
                return (x + ox, y + oy, z + oz)

            xyz_transform = offset_transform

        # Build local XLink index for this building
        from ..utils.xlink_resolver import build_id_index

        # Wrap in a dummy root for build_id_index
        dummy_root = ET.Element("root")
        dummy_root.append(building_elem)
        id_index = build_id_index(dummy_root)

        # Import extraction functions
        from ..lod.extractor import extract_building_geometry
        from ..geometry.solid_builder import make_solid_with_cavities
        from ..geometry.building_part_merger import (
            merge_building_parts as merge_parts_fn,
        )

        def extract_single_solid(bldg_elem, xyz_tx, id_idx, dbg, prec_mode, fix_level):
            result = extract_building_geometry(
                bldg_elem, xyz_tx, id_idx, dbg, precision_mode=prec_mode,
                target_lod=target_lod,
            )
            if not result.exterior_faces:
                return None
            return make_solid_with_cavities(
                result.exterior_faces,
                result.interior_shells,
                None,
                dbg,
                prec_mode,
                fix_level,
            )

        shp = merge_parts_fn(
            building_elem,
            extract_single_solid,
            xyz_transform,
            id_index,
            debug,
            precision_mode,
            shape_fix_level,
            merge_building_parts,
        )

        if shp is None or shp.IsNull():
            return None

        # Serialize shape to BREP via temp file
        from OCC.Core.BRepTools import breptools
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".brep", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            breptools.Write(shp, tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as e:
        # Worker exceptions are caught and returned as None
        if debug:
            import traceback

            traceback.print_exc()
        return None


def process_buildings_parallel(
    buildings_to_process: list,
    source_crs: str,
    target_crs: str,
    coord_offset: Optional[Tuple[float, float, float]],
    precision_mode: str,
    shape_fix_level: str,
    merge_building_parts: bool,
    debug: bool,
    max_workers: Optional[int] = None,
    target_lod: Optional[str] = None,
) -> list:
    """
    Process multiple buildings in parallel using ProcessPoolExecutor.

    Only beneficial for 3+ buildings (process startup overhead is ~0.5s).

    Args:
        buildings_to_process: List of (building_elem, id_index) tuples
        source_crs: Source CRS string
        target_crs: Target CRS string
        coord_offset: Recentering offset or None
        precision_mode: Precision mode
        shape_fix_level: Shape fix level
        merge_building_parts: Whether to merge parts
        debug: Enable debug logging
        max_workers: Max parallel workers (default: min(len(buildings), CPU count))
        target_lod: Target LOD level for extraction (None = auto-fallback)

    Returns:
        List of (building_id, TopoDS_Shape or None) tuples
    """
    if max_workers is None:
        max_workers = min(len(buildings_to_process), os.cpu_count() or 2)
    # Cap at 4 workers to avoid memory pressure from multiple OCCT instances
    max_workers = min(max_workers, 4)

    log(
        f"[PARALLEL] Starting parallel processing with {max_workers} workers for {len(buildings_to_process)} buildings"
    )

    # Serialize buildings to XML strings
    tasks = []
    for b, _ in buildings_to_process:
        building_id = b.get("{http://www.opengis.net/gml}id", "unknown")
        xml_str = ET.tostring(b, encoding="unicode")
        tasks.append((building_id, xml_str))

    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {}
        for building_id, xml_str in tasks:
            future = executor.submit(
                _process_building_worker,
                xml_str,
                source_crs,
                target_crs,
                coord_offset,
                precision_mode,
                shape_fix_level,
                merge_building_parts,
                debug,
                target_lod,
            )
            future_to_id[future] = building_id

        for future in as_completed(future_to_id):
            building_id = future_to_id[future]
            try:
                brep_bytes = future.result()
                if brep_bytes is not None:
                    # Deserialize BREP back to TopoDS_Shape via temp file
                    from OCC.Core.BRep import BRep_Builder
                    from OCC.Core.TopoDS import TopoDS_Shape
                    from OCC.Core.BRepTools import breptools
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        suffix=".brep", delete=False
                    ) as tmp:
                        tmp.write(brep_bytes)
                        tmp_path = tmp.name

                    try:
                        shape = TopoDS_Shape()
                        builder = BRep_Builder()
                        breptools.Read(shape, tmp_path, builder)
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass

                    if not shape.IsNull():
                        results.append((building_id, shape))
                        log(
                            f"[PARALLEL] ✓ {building_id[:40]}: Shape deserialized successfully"
                        )
                    else:
                        results.append((building_id, None))
                        log(
                            f"[PARALLEL] ✗ {building_id[:40]}: Deserialized shape is null"
                        )
                else:
                    results.append((building_id, None))
                    log(f"[PARALLEL] ✗ {building_id[:40]}: Worker returned None")

            except Exception as e:
                results.append((building_id, None))
                log(f"[PARALLEL] ✗ {building_id[:40]}: Exception: {e}")

    log(
        f"[PARALLEL] Completed: {sum(1 for _, s in results if s is not None)}/{len(results)} buildings successful"
    )
    return results
