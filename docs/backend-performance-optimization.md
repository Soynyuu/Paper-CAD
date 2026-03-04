# Backend Performance Optimization — Implementation Guide

## Overview
This document captures the complete implementation plan for backend performance
optimization. It serves as a reference for context window compression recovery.

## Bottlenecks Identified

### Phase 1: Event Loop Blocking (Quick Wins)
| ID | Issue | File | Lines |
|----|-------|------|-------|
| B1 | CPU-bound OCCT/numpy/scipy runs on async event loop | `api/routers/step.py` | 184, 215, 257, 261, 288, 395, 419, 420 |
| B2 | `time.sleep(1)` blocks event loop | `services/plateau_fetcher.py` | 628 |
| B3 | Sync `requests.get()` for textures | `services/plateau_texture_mapper.py` | 496 |

### Phase 2: Algorithm Improvements
| ID | Issue | File | Lines |
|----|-------|------|-------|
| B4 | O(F^2 * V1 * V2) face adjacency detection | `core/unfold_engine.py` | 1787-1840, 47-130, 368-482 |
| B5 | Brute-force 5mm grid layout (4800 cells * pairwise overlap) | `core/layout_manager.py` | 252-307 |
| B6 | No geometry analysis caching | `services/step_processor.py` | — |

---

## Implementation Details

### Phase 1-1: `api/routers/step.py` — run_in_executor

Wrap all sync CPU-bound calls in `asyncio.get_event_loop().run_in_executor(None, ...)`.
Use `functools.partial` for calls with keyword arguments.

**Calls to wrap:**
- `step_unfold_generator.load_from_file(in_path)` (L184)
- `step_unfold_generator.generate_brep_papercraft(request, output_path)` (L215)
- `step_unfold_generator.generate_brep_papercraft_pages(request)` (L257)
- `step_unfold_generator.export_to_svg_paged_files(...)` (L261)
- `_create_pdf_response_from_pages(...)` (L288)
- Same pattern in PDF endpoint (L395, L419, L420)

### Phase 1-2: plateau_fetcher / texture_mapper — run_in_executor at callers

Wrap calls from API routers (`api/routers/plateau.py`, `api/routers/citygml.py`)
to plateau_fetcher and texture_mapper functions in `run_in_executor`.
The `time.sleep(1)` and `requests.get()` calls become safe because they run in a
thread pool, not on the event loop.

### Phase 2-1: `core/geometry_analyzer.py` — OCCT Topology Adjacency Map

**New imports:**
```python
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCC.Core.TopExp import TopExp_Explorer, topexp
from OCC.Core.TopoDS import topods, TopoDS_Shape
```

**Changes to `analyze_brep_topology()`:**
1. Build face index map: `Dict[TopoDS_Face.HashCode, int]` mapping each face's hash to its index
2. Call `topexp.MapShapesAndAncestors(solid_shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)`
3. Iterate edge_face_map: for each edge, get the list of faces sharing it
4. Build `self.adjacency_map: Dict[int, Set[int]]` from face index pairs
5. Store `TopoDS_Face` reference in each `face_data["topo_face"]` via `topods.Face()`

**Key consideration:** pythonocc 7.9.0 uses `topexp.MapShapesAndAncestors()` (lowercase
module-level function). The `TopExp` class-level static method may not be directly
available — use the module-level function `topexp.MapShapesAndAncestors()`.

### Phase 2-2: `services/step_processor.py` — Pass Adjacency Map

After `analyze_brep_topology()`, pass the adjacency map to unfold_engine:
```python
self.unfold_engine.set_adjacency_map(self.geometry_analyzer.adjacency_map)
```

### Phase 2-3: `core/unfold_engine.py` — O(1) Adjacency + BFS Optimization

1. Add `set_adjacency_map(self, adjacency_map)` method
2. Rewrite `_are_faces_adjacent()`:
   - If adjacency_map exists: O(1) set lookup
   - Fallback: existing vertex-distance logic (renamed to `_are_faces_adjacent_by_vertices`)
3. Optimize BFS in `group_faces_for_unfolding()` (L47-130):
   - `queue.pop(0)` → `collections.deque.popleft()`
   - When adjacency_map exists, iterate only over `adjacency_map[current_face_idx]`
     instead of all unfoldable faces
4. Same optimization in `_unfold_spanning_tree()` (L368-482)
5. Same in `_expand_face_group()` (L1718-1749)

### Phase 2-4: `core/layout_manager.py` — STRtree + unary_union

**New imports:**
```python
from shapely import STRtree
from shapely import affinity
# unary_union is already imported but unused — activate it
```

**Changes:**

1. **`_find_non_overlapping_position_with_polygons()`:**
   - Pre-create Shapely polygons for the candidate group ONCE (not per grid cell)
   - Merge candidate group polygons via `unary_union` → single geometry
   - Maintain a running STRtree of all placed polygons (rebuilt after each placement)
   - For each grid cell: translate candidate with `affinity.translate()`, query STRtree
   - Replace `_areas_overlap()` linear scan with STRtree bbox query
   - Fix hardcoded grid bounds (300x400) → use `self.printable_width_mm`, `self.printable_height_mm`

2. **`_polygons_overlap()`:**
   - Use `unary_union` to merge each group's polygons → 1 intersection test instead of P1*P2
   - Cache merged geometries on placed groups

3. **`layout_for_pages()` → `_find_position_in_page()`:**
   - Apply same STRtree optimization

### Phase 2-5: `services/step_processor.py` — Geometry Analysis Cache

1. Compute SHA256 of uploaded file bytes in `load_from_file()` / `load_from_bytes()`
2. Class-level `_analysis_cache: Dict[str, CacheEntry]` (max 10 entries, LRU eviction)
3. `CacheEntry` = `(faces_data, edges_data, adjacency_map, stats)`
4. In `analyze_brep_topology()`: check cache first, skip OCCT analysis if hit
5. Deep copy cached data to avoid mutation across requests

---

## Data Flow (Current → After)

### Current
```
solid_shape → TopExp_Explorer(FACE) → face dict (numbers only) → unfold_engine
  └── _are_faces_adjacent: O(V1*V2) vertex comparison per call
  └── BFS: O(F^2) calls to _are_faces_adjacent
```

### After
```
solid_shape → TopExp_Explorer(FACE) + topexp.MapShapesAndAncestors(EDGE,FACE)
  └── adjacency_map: Dict[int, Set[int]]  (built once, O(E+F))
  └── unfold_engine receives adjacency_map
  └── _are_faces_adjacent: O(1) set lookup
  └── BFS: O(F + E) with neighbor-only iteration
```

---

## Files to Modify (Complete List)

| File | Changes |
|------|---------|
| `api/routers/step.py` | Add run_in_executor wrapping for all CPU-bound calls |
| `api/routers/plateau.py` | Add run_in_executor for plateau_fetcher calls |
| `api/routers/citygml.py` | Add run_in_executor for citygml/texture calls |
| `core/geometry_analyzer.py` | Build OCCT adjacency map, store TopoDS_Face refs |
| `services/step_processor.py` | Pass adjacency map, add SHA256 cache |
| `core/unfold_engine.py` | O(1) adjacency, deque BFS, neighbor-only iteration |
| `core/layout_manager.py` | STRtree spatial index, unary_union, fix grid bounds |

## Test Plan
- `pytest` all existing tests must pass
- New unit test: compare adjacency_map output with vertex-based adjacency for known STEP files
- Manual: upload STEP file, verify SVG output unchanged
