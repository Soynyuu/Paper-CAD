// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import * as Cesium from "cesium";
import type { PickedBuilding } from "./types";
import { calculateMeshCode, detectMeshLevel } from "./cesiumCoordinateUtils";

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
 * - Automatic mesh code calculation (6/8/9/10 digits)
 *
 * Usage:
 * ```typescript
 * const picker = new CesiumBuildingPicker(viewer);
 * const building = picker.pickBuilding(screenCoords, multiSelect);
 * const selected = picker.getSelectedBuildings();
 * ```
 */
export class CesiumBuildingPicker {
    private viewer: Cesium.Viewer;
    private selectedBuildings: Map<string, PickedBuilding> = new Map();
    private highlightedFeatures: Map<string, Cesium.Cesium3DTileFeature> = new Map();
    private originalColors: Map<string, Cesium.Color> = new Map();

    constructor(viewer: Cesium.Viewer) {
        this.viewer = viewer;
    }

    /**
     * Pick building at screen coordinates
     *
     * @param screenCoords - Screen coordinates {x, y}
     * @param multiSelect - If true, toggle selection; if false, replace selection
     * @returns Picked building or null if no building at coords
     * @throws Error if picked feature is not a building
     */
    pickBuilding(
        screenCoords: { x: number; y: number },
        multiSelect: boolean = false,
    ): PickedBuilding | null {
        // 1. Cesium pick at screen coords
        const pickedFeature = this.viewer.scene.pick(new Cesium.Cartesian2(screenCoords.x, screenCoords.y));

        if (!pickedFeature || !pickedFeature.getProperty) {
            // Nothing picked or not a 3D Tiles feature
            if (!multiSelect) {
                this.clearSelection();
            }
            return null;
        }

        // 2. Validate feature type
        const featureType = pickedFeature.getProperty("feature_type");
        if (featureType !== "bldg:Building") {
            throw new Error("Please select a building (non-building feature clicked)");
        }

        // 3. Extract gml_id
        const gmlId = pickedFeature.getProperty("gml_id");
        if (!gmlId) {
            throw new Error("Building has no gml_id property");
        }

        // 4. Get WGS84 position from picked location
        const cartesian = this.viewer.scene.pickPosition(
            new Cesium.Cartesian2(screenCoords.x, screenCoords.y),
        );
        if (!cartesian) {
            throw new Error("Failed to get 3D position for picked building");
        }

        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const height = cartographic.height;

        // 5. Calculate mesh code (detect level from tiles data)
        const tilesMeshCode = pickedFeature.getProperty("meshcode");
        const meshLevel = detectMeshLevel(tilesMeshCode);
        const meshCode = calculateMeshCode(lat, lon, meshLevel);

        // 6. Extract building metadata
        const building: PickedBuilding = {
            gmlId,
            meshCode,
            position: { latitude: lat, longitude: lon, height },
            properties: {
                name: pickedFeature.getProperty("gml:name") || undefined,
                usage: pickedFeature.getProperty("bldg:usage") || undefined,
                measuredHeight: pickedFeature.getProperty("bldg:measuredHeight") || undefined,
                cityName: pickedFeature.getProperty("city_name") || undefined,
                meshcode: tilesMeshCode || undefined,
                featureType,
            },
        };

        // 7. Multi-select handling
        if (multiSelect) {
            // Toggle selection
            if (this.selectedBuildings.has(gmlId)) {
                this.removeBuilding(gmlId);
            } else {
                this.addBuilding(building, pickedFeature);
            }
        } else {
            // Replace selection
            this.clearSelection();
            this.addBuilding(building, pickedFeature);
        }

        return building;
    }

    /**
     * Add building to selection
     *
     * @param building - Building to add
     * @param feature - Cesium 3D Tiles feature for highlighting
     */
    private addBuilding(building: PickedBuilding, feature: Cesium.Cesium3DTileFeature): void {
        this.selectedBuildings.set(building.gmlId, building);
        this.highlightBuilding(feature, building.gmlId);
    }

    /**
     * Remove building from selection by GML ID
     *
     * @param gmlId - GML ID of building to remove
     */
    removeBuilding(gmlId: string): void {
        this.selectedBuildings.delete(gmlId);
        this.removeHighlight(gmlId);
    }

    /**
     * Highlight building by changing its color
     *
     * @param feature - Cesium 3D Tiles feature
     * @param gmlId - GML ID for tracking
     */
    private highlightBuilding(feature: Cesium.Cesium3DTileFeature, gmlId: string): void {
        // Save original color if not already saved
        if (!this.originalColors.has(gmlId)) {
            this.originalColors.set(gmlId, feature.color.clone());
        }

        // Set highlight color (yellow with alpha)
        feature.color = Cesium.Color.YELLOW.withAlpha(0.7);

        // Track highlighted feature
        this.highlightedFeatures.set(gmlId, feature);
    }

    /**
     * Remove highlight from building
     *
     * @param gmlId - GML ID of building
     */
    private removeHighlight(gmlId: string): void {
        const feature = this.highlightedFeatures.get(gmlId);
        const originalColor = this.originalColors.get(gmlId);

        if (feature && originalColor) {
            feature.color = originalColor;
        }

        this.highlightedFeatures.delete(gmlId);
        this.originalColors.delete(gmlId);
    }

    /**
     * Get all selected buildings
     *
     * @returns Array of selected buildings
     */
    getSelectedBuildings(): PickedBuilding[] {
        return Array.from(this.selectedBuildings.values());
    }

    /**
     * Get number of selected buildings
     *
     * @returns Count of selected buildings
     */
    getSelectionCount(): number {
        return this.selectedBuildings.size;
    }

    /**
     * Check if building is selected
     *
     * @param gmlId - GML ID to check
     * @returns True if building is selected
     */
    isSelected(gmlId: string): boolean {
        return this.selectedBuildings.has(gmlId);
    }

    /**
     * Clear all selections and highlights
     */
    clearSelection(): void {
        // Restore all original colors
        for (const [gmlId, feature] of this.highlightedFeatures.entries()) {
            const originalColor = this.originalColors.get(gmlId);
            if (originalColor) {
                feature.color = originalColor;
            }
        }

        this.selectedBuildings.clear();
        this.highlightedFeatures.clear();
        this.originalColors.clear();
    }

    /**
     * Get building by GML ID from selection
     *
     * @param gmlId - GML ID to lookup
     * @returns Building or undefined if not selected
     */
    getBuilding(gmlId: string): PickedBuilding | undefined {
        return this.selectedBuildings.get(gmlId);
    }
}
