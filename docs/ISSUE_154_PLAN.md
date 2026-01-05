# Issue 154 Plan: 3D Building Picking UX (Cesium)

## Summary (What + Why)
Deliver a reliable, explicit building selection UX in Cesium that prevents mis-picks, disambiguates overlaps, and provides enough metadata to confirm correctness before import. The plan below is driven by issues observed in the current code paths.

## Goals
- Accurate building selection without accidental clicks during camera movement.
- Disambiguation when multiple buildings overlap under the cursor.
- Stable visual feedback (highlight/selection) under requestRenderMode.
- Consistent behavior across React and legacy dialogs.

## Constraints and Assumptions
- Cesium remains the renderer (no migration to other 3D engines).
- Default tilesets are LOD1 and are hosted remotely.
- `requestRenderMode` is enabled in `CesiumView`.
- Backend provides building metadata and conversion endpoints.
- **Legacy dialog is the priority** — React picker is unused and will be unified later.
- **Batch metadata endpoint is required for MVP** — 5+ selections cause noticeable latency.
- **GSI basemap** for Japanese map labels that match PLATEAU use case.

## Code-Based Diagnosis (Current Issues)
1. React picker is not used:
   - `frontend/packages/chili/src/commands/importCityGMLByCesium.ts` always uses `PlateauCesiumPickerDialog`.
   - `frontend/rspack.config.js` does not inject `useReactCesiumPicker` (type exists in `global.d.ts` but value is missing).
2. Two picking stacks behave differently:
   - React uses direct `Cesium3DTileset.fromUrl` with different settings.
   - Legacy uses `CesiumTilesetLoader` with LOD/preload tuned for picking.
3. React tileset loading removes all primitives:
   - `viewer.scene.primitives.removeAll()` in `PlateauCesiumPickerReact.tsx` can wipe overlays.
4. Click fires during drag:
   - No drag threshold or camera motion gating in either UI.
5. Single-hit pick only:
   - `CesiumBuildingPicker` uses `scene.pick` and a strict property check.
   - Overlaps are not disambiguated.
6. Depth picking failure is fatal:
   - `pickPosition` failure throws with no fallback.
7. requestRenderMode does not get forced:
   - After highlight, no explicit `scene.requestRender()` is called.
8. Hover/preview state is not implemented:
   - `highlightedBuildingIdsAtom` is unused.

## Non-Goals
- Replacing Cesium or introducing a new map renderer.
- LOD2/LOD3 streaming integration (future work).
- Full automation of building identity without user confirmation.

## Design Principles
- Prevent accidental selection via input gating (drag threshold).
- Provide multiple cues: highlight, tooltip, candidate list.
- Keep logic shared: one picker core used by both dialogs.
- Fail safe: fallback path if a Cesium API is unavailable.

## Plan (Prioritized by Impact and Independence)

### Phase 1: Input Gating and Render Timing (What)
1. Prevent selection on drag/camera motion.
2. Ensure highlights render immediately.

**Why first**: Independent of all other phases, high user impact, low risk.

### Phase 1: Implementation Details (How)
- Add pointer down/up tracking in `plateauCesiumPickerDialog.ts`:
  - Track `downPos` on `LEFT_DOWN`, compare to `LEFT_UP`.
  - Ignore selection if distance > 6 px.
- Gate on camera movement:
  - If `viewer.scene.screenSpaceCameraController` is rotating/zooming/tilting, ignore.
  - Optionally track `camera.changed` between down/up.
- In `cesiumBuildingPicker.ts`:
  - Call `viewer.scene.requestRender()` after `highlightBuilding` and `removeHighlight`.

### Phase 2: Robust Picking and Property Mapping (What)
1. Handle overlapping buildings and property variance.
2. Provide a safe fallback when depth picking fails.

**Why second**: Independent, fixes overlap/error issues that cause user frustration.

### Phase 2: Implementation Details (How)
- In `CesiumBuildingPicker`:
  - Add `drillPick` path and return candidates.
  - Introduce helper `getProperty(feature, keys)` to support variants:
    - `feature_type`, `featureType`, `type`
    - `gml_id`, `gmlId`, `gml:id`, `id`
  - If `feature_type` is missing but `gml_id` exists, treat as candidate.
- Use `scene.drillPick(pos, 10)`:
  - Filter to building candidates.
  - If single candidate, proceed.
  - If multiple, return list to UI for disambiguation.
- Fallback for `pickPosition`:
  - Try `scene.pickPosition`.
  - If null, use `camera.getPickRay` and `scene.globe.pick`.
  - If still null, return position without height.

### Phase 3: Visual Feedback (What)
1. Increase geographic context to reduce mis-picks.
2. Improve visual identification of selection.

**Why third**: Low complexity, improves UX without changing core logic.

### Phase 3: Implementation Details (How)
- Add basemap switcher in `CesiumView`:
  - NaturalEarth (default) + GSI (for Japan).
  - Gate external base layers behind config if needed.
- Add selection outline:
  - Use `feature.color` for fill.
  - Optionally add a silhouette post-process stage.
- Add crosshair overlay and "Zoom to selection" action.

### Phase 4: React Picker Unification (What)
1. Make React picker reachable with a feature flag.
2. Ensure both dialogs use the same tileset loader settings.

**Why fourth**: React picker is currently unused. Unify after core UX is stable.

### Phase 4: Implementation Details (How)
- `frontend/rspack.config.js`:
  - Add `useReactCesiumPicker: process.env.USE_REACT_CESIUM_PICKER === "true"` to `__APP_CONFIG__`.
  - Note: `global.d.ts` already has the type definition.
- `frontend/packages/chili/src/commands/importCityGMLByCesium.ts`:
  - If `__APP_CONFIG__.useReactCesiumPicker` is true, open React dialog via `renderReactDialog`.
  - Otherwise keep `PlateauCesiumPickerDialog` as fallback.
- `frontend/packages/chili-ui/src/react/PlateauCesiumPickerReact.tsx`:
  - Replace direct `Cesium3DTileset.fromUrl` with `CesiumTilesetLoader`.
  - Remove `viewer.scene.primitives.removeAll()`; manage only the active tileset.

### Phase 5: Disambiguation UI (What)
1. Provide a candidate list when multiple buildings overlap.

**Why fifth**: Only needed if Phase 2's drillPick returns multiple candidates frequently.

### Phase 5: Implementation Details (How)
- UI state machine:
  - `idle` -> `preview` -> `selected`
  - `preview` -> `selected` only on explicit "Add".
- Click behavior:
  - If one candidate: select directly (current behavior).
  - If multiple: open a candidate list near the cursor.
  - Selecting a candidate from list adds it to selection.
- Store candidate metadata in memory:
  - Use temporary data from tileset properties.

### Phase 6: Metadata Enrichment (What)
1. Provide reliable name/height/usage from backend.
2. Avoid repeated fetches.

**Why sixth**: Nice-to-have, depends on Phase 5 UI being in place.

### Phase 6: Implementation Details (How)
- On confirm:
  - Call `CityGMLService.searchByBuildingIdAndMesh(gmlId, meshCode)`.
  - Merge response into `PickedBuilding.properties`.
- Cache results in a `Map<gmlId, BuildingInfo>` for the dialog session.
- Backend:
  - Add batch endpoint `POST /api/plateau/buildings/batch` for multi-select.

### Phase 7: QA and Acceptance (What)
Manual checks:
- Dragging the map never selects a building.
- Overlapping buildings show disambiguation list (if Phase 5 shipped).
- Highlight appears immediately after click.
- Multi-select works with Ctrl and Meta.
- Import succeeds for single and multiple buildings.

## File-Level Work Items
| File | Changes |
|------|---------|
| `frontend/packages/chili-cesium/src/cesiumBuildingPicker.ts` | drillPick, property mapping, pickPosition fallback, requestRender |
| `frontend/packages/chili-ui/src/plateauCesiumPickerDialog.ts` | drag threshold (LEFT_DOWN/UP tracking) |
| `frontend/packages/chili-cesium/src/cesiumView.ts` | basemap switcher (GSI) |
| `frontend/rspack.config.js` | inject `useReactCesiumPicker` |
| `frontend/packages/chili/src/commands/importCityGMLByCesium.ts` | conditional React/Legacy dialog |
| `frontend/packages/chili-ui/src/react/PlateauCesiumPickerReact.tsx` | use CesiumTilesetLoader, remove primitives.removeAll() |
| `frontend/packages/chili-core/src/services/citygmlService.ts` | metadata cache, batch endpoint support |
| `backend/api/routers/plateau.py` | batch metadata endpoint |

## Risks and Mitigations
- Low LOD accuracy:
  - Add a "precision mode" toggle by lowering `maximumScreenSpaceError`.
- UI complexity:
  - Ship Phase 1-3 first, evaluate if Phase 5 disambiguation is needed.
- Render timing issues:
  - Always call `scene.requestRender()` after highlight.
