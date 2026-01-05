# Issue 169 Plan: Assembly Interaction (Unfold ↔ 3D, QR)

## Summary (What + Why)
Create a clear assembly workflow that eliminates the “Which face is this?” problem by connecting 2D unfold faces to 3D surfaces, adding face classification, embedding QR/metadata in exports, and validating usability with focused tests.

## Goals
- Instant mapping between 2D face and 3D face (click, hover, or scan).
- Face classification that helps users orient parts during assembly.
- QR-based retrieval of face context for printed sheets.
- Metadata embedded in SVG/PDF to support external tools and future automation.

## Constraints and Assumptions
- Assembly mode uses a separate Three.js scene (`AssemblyPanel`).
- Backend already returns face numbers, but not rich metadata.
- SVG export is the primary artifact for unfold output.

## Code-Based Diagnosis (Current Issues)
1. Face classification logic exists but is not used:
   - `_assign_face_number_by_normal` is defined but unused.
   - Faces are numbered as `face_index + 1` only.
   - `backend/core/geometry_analyzer.py`
2. Backend returns only face number mappings:
   - `StepUnfoldGenerator.get_face_numbers` returns `{ faceIndex, faceNumber }`.
   - No surface type, normal, centroid, or orientation in the response.
   - `backend/services/step_processor.py`
3. SVG export embeds only face number:
   - `data-face-number` is added, but no additional metadata or QR payload.
   - `backend/core/svg_exporter.py`
4. 3D highlight is only number sprite:
   - `FaceNumberDisplay` highlights the number sprite, not the actual face.
   - `frontend/packages/chili-three/src/faceNumberDisplay.ts`
5. No QR generation or scanning:
   - No QR libraries or QR payloads in frontend/backend code.
6. Face numbering is assumed to be `face_index + 1` in texture flows:
   - `ApplyTextureCommand` derives face numbers from local indices and sends them to unfold.
   - Changing numbering without aligning this path will break texture mappings.
   - `frontend/packages/chili/src/commands/modify/applyTexture.ts`
7. SVG face index mapping is implicit:
   - `AssemblyPanel` assigns `data-face-index` based on DOM order, not backend mapping.
   - This is fragile if SVG element order differs from face index order.
   - `frontend/packages/chili-ui/src/assembly/assemblyPanel.ts`

## Non-Goals
- Replacing the assembly UI architecture.
- Changing the unfold algorithm itself.

## Design Principles
- Use shared metadata across 2D and 3D.
- Make QR optional but consistent and stable.
- Provide immediate visual confirmation in both views.

## Plan (Balanced What and How)

### Phase 0: Face Metadata Foundation (What)
Define and expose face metadata that enables classification, QR, and reliable mapping.

### Phase 0: Implementation Details (How)
- Backend (`backend/core/geometry_analyzer.py`):
  - Keep `face_number = face_index + 1` for compatibility.
  - Add `face_class` (front/back/left/right/top/bottom/other) derived from normals.
  - Reuse `_assign_face_number_by_normal` logic but return class only (no renumbering).
  - Store `centroid`, `normal_vector`, `surface_type` in `face_data`.
- Backend (`backend/services/step_processor.py`):
  - Return `face_metadata` list: `{ faceIndex, faceNumber, faceClass, centroid, normal, surfaceType }`.
- Backend (`backend/api/routers/step.py`):
  - Include `face_metadata` in JSON output when `return_face_numbers` is true.
- SVG export (`backend/core/svg_exporter.py`):
  - Embed `data-face-number`, `data-face-class`, `data-face-index`, `data-face-centroid`.
  - Ensure `data-face-index` matches backend faceIndex, not DOM order.

### Phase 1: 3D ↔ 2D Highlighting (What)
Make clicking or hovering a face in one view highlight the actual face in the other.

### Phase 1: Implementation Details (How)
- Assembly UI (`frontend/packages/chili-ui/src/assembly/assemblyPanel.ts`):
  - Cache `face_metadata` from the unfold response.
  - On 2D click, use `faceNumber` to resolve `faceIndex`.
  - Highlight actual face mesh (not just number sprites).
- Three.js highlighting:
  - Create a per-face highlight mesh using `IFace.mesh` for the selected face.
  - Use a single overlay mesh (replace on selection) to avoid per-triangle mapping.
  - Keep `FaceNumberDisplay` for labels.

### Phase 2: QR Embedding (What)
Embed QR codes in the SVG/PDF to allow scanning and cross-view highlighting.

### Phase 2: Implementation Details (How)
- Define QR payload schema:
  - Example: `paper-cad://assembly?model=<id>&face=<faceNumber>`
- Chosen: backend QR generation to keep SVG/PDF consistent.
  - Add a QR generator (e.g., `segno` or `qrcode`) in backend.
  - Generate QR as SVG paths to avoid raster blur in print.
  - Inject QR near each face number when face area is above a threshold.
  - For tiny faces, add QR to a per-page index panel instead of the face.
- Add `data-qr-payload` attributes on face elements for tooling.
- Ensure QR placement avoids tabs and fold lines (place in margin offset).

### Phase 3: QR Scan and Jump (What)
Allow scanning a QR code to highlight the corresponding face in 2D and 3D.

### Phase 3: Implementation Details (How)
- Add a “Scan QR” action in `AssemblyPanel`.
- Use `getUserMedia` to access camera and a JS QR decoder.
- On scan:
  - Parse payload, resolve face number.
  - Trigger the same highlight flow as manual selection.

### Phase 4: Face Classification UX (What)
Expose face class as visual cues to reduce confusion.

### Phase 4: Implementation Details (How)
- Add class badges in 2D:
  - Small icons or labels on each face (F/B/L/R/T/B).
- Add color palette per face class for quick recognition.
- Display class in tooltip or status bar on hover.

### Phase 5: UX Validation (What)
Validate the flow with a short usability test.

### Phase 5: Implementation Details (How)
- Define 3 tasks:
  1) Identify a face in 2D and locate in 3D.
  2) Scan QR and confirm highlight.
  3) Locate “top” or “front” face using classification cues.
- Measure error rate and time to correct face.

## File-Level Work Items
- `backend/core/geometry_analyzer.py`: use `_assign_face_number_by_normal`, add face metadata.
- `backend/services/step_processor.py`: return face metadata.
- `backend/api/routers/step.py`: include metadata in JSON.
- `backend/core/svg_exporter.py`: embed face metadata + QR SVG paths + index panel.
- `backend/services/step_processor.py`: pass QR config (size threshold, per-page panel).
- `frontend/packages/chili-ui/src/assembly/assemblyPanel.ts`: add metadata-driven highlight and QR scan.
- `frontend/packages/chili-three/src/faceNumberDisplay.ts`: keep labels; mesh highlight handled in `AssemblyPanel`.

## Risks and Mitigations
- Face index mapping mismatch:
  - Use `faceIndex` from backend response rather than index order in SVG elements.
- QR clutter:
  - Optionally put QR in a side panel or per-page index.
- Performance:
  - Limit highlights to a single active face and reuse materials.

## Open Decisions
- Decide default QR size threshold for per-face placement.
- Decide whether to include optional face-class icons in QR index panel.
