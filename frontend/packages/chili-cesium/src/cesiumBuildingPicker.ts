// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import type { PickedBuilding } from "./types";

/**
 * CesiumBuildingPicker
 *
 * Handles building selection from Cesium 3D Tiles with multi-select support.
 *
 * Features:
 * - Click to select single building
 * - Ctrl+Click for multi-select
 * - Visual highlighting of selected buildings
 * - Validation of feature type (must be bldg:Building)
 * - Automatic mesh code calculation
 *
 * Usage:
 * ```typescript
 * const picker = new CesiumBuildingPicker(viewer);
 * const building = await picker.pickBuilding(screenCoords, multiSelect);
 * const selected = picker.getSelectedBuildings();
 * ```
 */

export class CesiumBuildingPicker {
    // TODO: Implement in Phase 2
    // - private selectedBuildings: Set<PickedBuilding>
    // - private highlightedFeatures: Map<string, Entity>
    // - pickBuilding(screenCoords, multiSelect): Promise<PickedBuilding | null>
    // - highlightBuilding(feature, gmlId): void
    // - removeHighlight(gmlId): void
    // - getSelectedBuildings(): PickedBuilding[]
    // - clearSelection(): void
}
