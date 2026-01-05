# Issue 162 Plan: LOD-Based Assembly Level Split (Beginner vs Expert)

## Summary (What + Why)
Introduce explicit LOD-based flows so beginners get simpler, more reliable LOD2 models and templates, while experts can choose LOD3 with higher detail and richer textures. This needs UI branching, backend control of LOD extraction, and template/preset design for the unfold output.

## Goals
- Clear user-facing choice between LOD2 (beginner) and LOD3 (expert).
- Backend respects user-selected LOD target instead of always taking highest available.
- Templates/presets optimized for each LOD.
- Texture/data management UI that scales with LOD complexity.

## Constraints and Assumptions
- Backend currently uses LOD3 → LOD2 → LOD1 fallback automatically.
- Frontend selection dialogs already show LOD availability flags.
- STEP unfold pipeline operates on the resulting STEP data.

## Code-Based Diagnosis (Current Issues)
1. No explicit LOD selection in UI:
   - `PlateauBuildingSelectionDialog` shows LOD badges but does not change conversion flow.
   - `frontend/packages/chili-ui/src/plateauBuildingSelectionDialog.ts`
2. Backend always takes highest LOD available:
   - `lod/extractor.py` uses LOD3 → LOD2 → LOD1 fallback without user control.
   - `backend/services/citygml/lod/extractor.py`
3. CityGML API lacks LOD target parameter:
   - `/api/citygml/to-step` exposes precision/method options, but no LOD selection.
   - `backend/api/routers/citygml.py`
4. Frontend services do not send LOD intent:
   - `CityGMLService.fetchAndConvertByBuildingIdAndMesh` and related methods.
   - `frontend/packages/chili-core/src/services/citygmlService.ts`
5. No LOD-specific unfold presets:
   - `StepUnfoldPanel` has options but no LOD templates or presets.
   - `frontend/packages/chili-ui/src/stepUnfold/stepUnfoldPanel.ts`
6. Cesium flow lacks LOD availability data:
   - Cesium pick returns `gmlId` + `meshCode` but no `has_lod2/has_lod3`.
   - LOD profile UI cannot be accurate without a metadata fetch.
   - `frontend/packages/chili-ui/src/react/PlateauCesiumPickerReact.tsx`

## Non-Goals
- Full refactor of CityGML pipeline.
- LOD streaming of 3D tiles for Cesium.

## Design Principles
- Beginners get predictable, lightweight output (LOD2).
- Experts can opt into higher detail with explicit tradeoffs.
- LOD choice flows through all stages (import → unfold → assembly).

## Plan (Balanced What and How)

### Phase 0: Define LOD Profiles (What)
Create a shared representation of “Beginner (LOD2)” and “Expert (LOD3)” profiles.

### Phase 0: Implementation Details (How)
- Add a `LodProfile` type in frontend:
  - `{ key, label, targetLod, defaultUnfoldOptions, textureMode }`.
- Provide default presets:
  - Beginner: LOD2, simpler unfold, fewer pages.
  - Expert: LOD3, higher detail, optional textures.

### Phase 1: UI Flow Branching (What)
Expose LOD choice during building selection and import.

### Phase 1: Implementation Details (How)
- Add profile selection in:
  - `frontend/packages/chili/src/commands/importCityGMLByAddress.ts`
  - `frontend/packages/chili/src/commands/importCityGMLByCesium.ts`
- Cesium flow:
  - On selection, call `searchByBuildingIdAndMesh` to fetch `has_lod2/has_lod3`.
  - Disable Expert option when LOD3 is unavailable.
- When building has no LOD3:
  - Disable Expert option or show fallback warning.
- Persist user preference for future sessions (local storage).

### Phase 2: Backend LOD Target Support (What)
Allow the backend to honor explicit LOD targets instead of always choosing highest.

### Phase 2: Implementation Details (How)
- Add `lod_target` parameter to:
  - `/api/citygml/to-step`
  - `/api/plateau/fetch-by-id-and-mesh`
  - `/api/plateau/fetch-and-convert`
- Update `backend/services/citygml/lod/extractor.py`:
  - Keep default order unchanged unless `lod_target` is provided.
  - If `lod_target=LOD2`, try LOD2 then LOD1 (skip LOD3).
  - If `lod_target=LOD3`, try LOD3 then LOD2 then LOD1 (current default).
- Include `lod_used` in response headers or JSON for UI feedback.

### Phase 3: Frontend Service Integration (What)
Pass LOD target through API calls and surface the final LOD used.

### Phase 3: Implementation Details (How)
- Extend `CityGMLService` methods:
  - `fetchAndConvertByBuildingIdAndMesh` to accept `lodTarget`.
  - `fetchAndConvertByAddress` to accept `lodTarget`.
- For file responses, use headers:
  - `X-LOD-Used` and `X-LOD-Target` for UI feedback.
- Update UI results to show:
  - Selected profile, actual `lod_used`, and fallback if any.

### Phase 4: LOD-Specific Unfold Templates (What)
Provide template presets to optimize unfold output for each LOD.

### Phase 4: Implementation Details (How)
- Add presets to `StepUnfoldPanel`:
  - Beginner: larger scale, fewer faces per page, bigger labels.
  - Expert: smaller scale, more pages, optional texture mappings.
- Store presets in local storage and allow custom tweaks.
- Apply template automatically based on selected LOD profile.
- Persist selected profile in document metadata or app storage to reuse in unfold/assembly.

### Phase 5: Texture and Data Management UI (What)
Enable texture sets and data management that scale with LOD complexity.

### Phase 5: Implementation Details (How)
- Extend `FaceTextureService`:
  - Support multiple texture sets keyed by `lod_profile`.
  - Add serialization per profile.
- Add a “Texture Set” selector in `StepUnfoldPanel`.
- For Expert flow:
  - Encourage texture usage and previews.

### Phase 6: QA and Acceptance (What)
Manual checks:
- LOD selection visibly changes backend behavior (`lod_used`).
- Expert flow uses LOD3 when available.
- Beginner flow never uses LOD3.
- Templates switch based on profile.
- Texture sets persist per profile.

## File-Level Work Items
- `frontend/packages/chili-ui/src/plateauBuildingSelectionDialog.ts`: surface LOD profile choice.
- `frontend/packages/chili/src/commands/importCityGMLByAddress.ts`: pass `lodTarget`.
- `frontend/packages/chili/src/commands/importCityGMLByCesium.ts`: pass `lodTarget`.
- `frontend/packages/chili-core/src/services/citygmlService.ts`: add `lodTarget` support.
- `backend/api/routers/citygml.py`: accept `lod_target`.
- `backend/services/citygml/lod/extractor.py`: honor LOD target.
- `frontend/packages/chili-ui/src/stepUnfold/stepUnfoldPanel.ts`: LOD presets and template handling.
- `frontend/packages/chili-core/src/services/faceTextureService.ts`: per-profile texture sets.

## Risks and Mitigations
- LOD3 models are heavy:
  - Default to LOD2 for beginners and warn on expert selection.
- Inconsistent LOD availability:
  - Show per-building LOD status and fallback messaging.
- Increased UI complexity:
  - Hide advanced options behind “Expert” mode.

## Open Decisions
- Whether to allow explicit LOD1/LOD0 fallback in Beginner mode.
- How to surface `lod_used` in UI (toast vs panel).
- Whether to support LOD profile switching after import.
