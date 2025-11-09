"""
CityGML to STEP conversion module (refactored).

Public API preserving exact compatibility with original citygml_to_step.py.

Phase 2 COMPLETE: Now uses fully refactored implementation with all methods:
- Solid extraction (LOD1/LOD2/LOD3 with BuildingPart merging)
- Surface sewing (LOD2 BoundarySurfaces)
- Footprint extrusion (LOD0 fallback)
- Auto method (solid → sew → extrude fallback chain)
"""

# Use fully refactored implementation (Phase 2)
from .pipeline.orchestrator import export_step_from_citygml

__all__ = ["export_step_from_citygml"]
