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
    private scene: Cesium.Scene;
    private selectedBuildings: Map<string, PickedBuilding> = new Map();
    private highlightedFeatures: Map<string, Cesium.Cesium3DTileFeature> = new Map();
    private originalColors: Map<string, Cesium.Color> = new Map();
    private previewHighlight: {
        gmlId: string;
        feature: Cesium.Cesium3DTileFeature;
        originalColor: Cesium.Color;
    } | null = null;
    private lastCandidates: PickedBuilding[] = [];
    private lastScreenCoords: { x: number; y: number } | null = null;

    constructor(viewer: Cesium.Viewer) {
        this.viewer = viewer;
        this.scene = viewer.scene;
    }

    private normalizeBuildingId(value?: string): string | undefined {
        if (!value) return undefined;
        return value.trim().toLowerCase();
    }

    private stripNamespace(value: string): string {
        return value.replace(/^.*[:/]/, "");
    }

    private extractBuildingSegment(value: string): string {
        const index = value.indexOf("bldg_");
        return index >= 0 ? value.slice(index) : value;
    }

    private isMatchingBuildingId(featureId: string, targetId?: string): boolean {
        const normalizedFeature = this.normalizeBuildingId(featureId);
        const normalizedTarget = this.normalizeBuildingId(targetId);

        if (!normalizedFeature || !normalizedTarget) return false;
        if (normalizedFeature === normalizedTarget) return true;
        if (normalizedFeature.endsWith(normalizedTarget) || normalizedTarget.endsWith(normalizedFeature)) {
            return true;
        }

        const strippedFeature = this.stripNamespace(normalizedFeature);
        const strippedTarget = this.stripNamespace(normalizedTarget);
        if (strippedFeature === strippedTarget) return true;

        const featureSegment = this.extractBuildingSegment(strippedFeature);
        const targetSegment = this.extractBuildingSegment(strippedTarget);
        return featureSegment === targetSegment;
    }

    /**
     * Get property value trying multiple key variants (Phase 2.1)
     *
     * @param feature - Cesium 3D Tiles feature
     * @param keys - Array of property names to try (in order of preference)
     * @returns Property value or undefined if none found
     */
    private getPropertyFlexible(feature: any, keys: string[]): string | number | undefined {
        for (const key of keys) {
            const value = feature.getProperty(key);
            if (value !== undefined && value !== null) {
                return value;
            }
        }
        return undefined;
    }

    /**
     * Return GML ID if the feature looks like a building, otherwise undefined.
     */
    private extractBuildingGmlId(feature: any): string | undefined {
        if (!feature || !feature.getProperty) return undefined;

        const featureType = this.getPropertyFlexible(feature, ["feature_type", "featureType", "type"]) as
            | string
            | undefined;
        const gmlId = this.getPropertyFlexible(feature, ["gml_id", "gmlId", "gml:id", "id"]) as
            | string
            | undefined;
        if (!gmlId) return undefined;

        const hasTypeMatch = featureType === "bldg:Building";
        const hasBuildingProps =
            this.getPropertyFlexible(feature, ["bldg:usage", "usage"]) !== undefined ||
            this.getPropertyFlexible(feature, ["bldg:measuredHeight", "measuredHeight"]) !== undefined;

        return hasTypeMatch || hasBuildingProps ? gmlId : undefined;
    }

    /**
     * Extract 3D position from screen coordinates with fallback (Phase 2.2)
     *
     * @param screenCoords - Screen coordinates {x, y}
     * @returns WGS84 position {lat, lon, height} or null if failed
     */
    private extractPosition(screenCoords: {
        x: number;
        y: number;
    }): { latitude: number; longitude: number; height: number } | null {
        const screenPos = new Cesium.Cartesian2(screenCoords.x, screenCoords.y);

        // Method 1: Try pickPosition (depth-based, most accurate)
        let cartesian: Cesium.Cartesian3 | undefined = this.scene.pickPosition(screenPos);

        // Method 2: Fallback to camera ray + globe intersection
        if (!cartesian) {
            const ray = this.viewer.camera.getPickRay(screenPos);
            if (ray) {
                cartesian = this.scene.globe.pick(ray, this.scene);
            }
        }

        // Method 3: Last resort - use ellipsoid (0 height)
        if (!cartesian) {
            const ellipsoid = this.scene.globe.ellipsoid;
            cartesian = this.viewer.camera.pickEllipsoid(screenPos, ellipsoid);
        }

        if (!cartesian) {
            console.warn(
                "[CesiumBuildingPicker] Failed to extract position from screen coords:",
                screenCoords,
            );
            return null;
        }

        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        return {
            latitude: Cesium.Math.toDegrees(cartographic.latitude),
            longitude: Cesium.Math.toDegrees(cartographic.longitude),
            height: cartographic.height,
        };
    }

    /**
     * Pick all buildings at screen coordinates (for overlap disambiguation) (Phase 2.3)
     *
     * @param screenCoords - Screen coordinates {x, y}
     * @returns Array of candidate buildings (empty if none found)
     */
    private pickBuildingCandidates(screenCoords: { x: number; y: number }): PickedBuilding[] {
        const screenPos = new Cesium.Cartesian2(screenCoords.x, screenCoords.y);
        const picked = this.scene.drillPick(screenPos, 10); // Limit to 10 candidates

        if (!picked || picked.length === 0) {
            return [];
        }

        const candidates: PickedBuilding[] = [];

        for (const pickedObject of picked) {
            if (!pickedObject || !pickedObject.getProperty) {
                continue; // Skip non-3D Tiles features
            }

            // Use flexible property getter
            const featureType = this.getPropertyFlexible(pickedObject, [
                "feature_type",
                "featureType",
                "type",
            ]) as string | undefined;

            const gmlId = this.getPropertyFlexible(pickedObject, [
                "gml_id",
                "gmlId",
                "gml:id",
                "id",
            ]) as string;

            // Require gml_id, but be lenient on feature_type
            if (!gmlId) continue;

            // Treat as building if feature_type matches OR if it has building properties
            const hasTypeMatch = featureType === "bldg:Building";
            const hasBuildingProps =
                this.getPropertyFlexible(pickedObject, ["bldg:usage", "usage"]) !== undefined ||
                this.getPropertyFlexible(pickedObject, ["bldg:measuredHeight", "measuredHeight"]) !==
                    undefined;

            if (!hasTypeMatch && !hasBuildingProps) continue;

            // Extract position (use fallback)
            const position = this.extractPosition(screenCoords);
            if (!position) {
                console.warn(`[CesiumBuildingPicker] Skipping candidate ${gmlId} - no position`);
                continue;
            }

            // Extract metadata
            const tilesMeshCode = pickedObject.getProperty("meshcode");
            const meshLevel = detectMeshLevel(tilesMeshCode);
            const meshCode = calculateMeshCode(position.latitude, position.longitude, meshLevel);

            const building: PickedBuilding = {
                gmlId,
                meshCode,
                position,
                properties: {
                    name: this.getPropertyFlexible(pickedObject, ["gml:name", "name"]) as string | undefined,
                    usage: this.getPropertyFlexible(pickedObject, ["bldg:usage", "usage"]) as
                        | string
                        | undefined,
                    measuredHeight: this.getPropertyFlexible(pickedObject, [
                        "bldg:measuredHeight",
                        "measuredHeight",
                        "height",
                    ]) as number | undefined,
                    cityName: this.getPropertyFlexible(pickedObject, ["city_name", "cityName", "city"]) as
                        | string
                        | undefined,
                    meshcode: tilesMeshCode || undefined,
                    featureType: featureType as string | undefined,
                },
            };

            candidates.push(building);
        }

        return candidates;
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
        // 1. Try drill pick first (Phase 2.3)
        const candidates = this.pickBuildingCandidates(screenCoords);

        // Store candidates and screen coords for disambiguation UI (Phase 5.1)
        this.lastCandidates = candidates;
        this.lastScreenCoords = { x: screenCoords.x, y: screenCoords.y };

        if (candidates.length === 0) {
            // Nothing picked
            if (!multiSelect) {
                this.clearSelection();
            }
            return null;
        }

        // For now, auto-select first candidate (topmost)
        // Phase 5.2 will add disambiguation UI when candidates.length > 1
        const building = candidates[0];
        const gmlId = building.gmlId;

        // Re-pick to get feature reference for highlighting
        const pickedFeature = this.viewer.scene.pick(new Cesium.Cartesian2(screenCoords.x, screenCoords.y));

        if (!pickedFeature) {
            console.warn("[CesiumBuildingPicker] Could not re-pick feature for highlighting");
            // Still proceed with building from candidates
        }

        // 2. Multi-select handling
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
     * @param feature - Cesium 3D Tiles feature for highlighting (optional)
     */
    private addBuilding(building: PickedBuilding, feature?: Cesium.Cesium3DTileFeature): void {
        this.selectedBuildings.set(building.gmlId, building);
        if (feature) {
            this.highlightBuilding(feature, building.gmlId);
        }
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

        const originalColor = this.originalColors.get(gmlId);
        const originalAlpha = originalColor?.alpha ?? feature.color.alpha;
        // Set highlight color without changing opacity.
        feature.color = Cesium.Color.YELLOW.withAlpha(originalAlpha);

        if (this.previewHighlight?.gmlId === gmlId) {
            this.previewHighlight = null;
        }

        // Force render when requestRenderMode is enabled (Phase 1.3)
        if (this.scene.requestRenderMode) {
            this.scene.requestRender();
        }

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

            // Force render when requestRenderMode is enabled (Phase 1.3)
            if (this.scene.requestRenderMode) {
                this.scene.requestRender();
            }
        }

        this.highlightedFeatures.delete(gmlId);
        this.originalColors.delete(gmlId);
    }

    /**
     * Clear preview highlight that is independent from selected-building highlight.
     */
    clearPreviewHighlight(): void {
        if (!this.previewHighlight) return;

        const { gmlId, feature, originalColor } = this.previewHighlight;

        // Keep selected highlight intact.
        if (!this.isSelected(gmlId)) {
            feature.color = originalColor;
            if (this.scene.requestRenderMode) {
                this.scene.requestRender();
            }
        }

        this.previewHighlight = null;
    }

    /**
     * Get currently previewed GML ID.
     */
    getPreviewGmlId(): string | null {
        return this.previewHighlight?.gmlId ?? null;
    }

    private setPreviewHighlight(feature: Cesium.Cesium3DTileFeature, gmlId: string): void {
        if (this.previewHighlight?.gmlId === gmlId && this.previewHighlight.feature === feature) {
            return;
        }

        this.clearPreviewHighlight();

        // If already selected, keep selected highlight color untouched.
        if (this.isSelected(gmlId)) {
            return;
        }

        const originalColor = feature.color.clone();
        const alpha = originalColor.alpha;
        feature.color = Cesium.Color.fromCssColorString("#1ea7fd").withAlpha(alpha);

        if (this.scene.requestRenderMode) {
            this.scene.requestRender();
        }

        this.previewHighlight = { gmlId, feature, originalColor };
    }

    /**
     * Try to preview-highlight a building near the screen coordinates.
     *
     * @param screenCoords - Screen coordinates
     * @param targetGmlId - Optional GML ID to match exactly
     * @returns True if a feature was highlighted
     */
    previewBuildingAtScreen(screenCoords: { x: number; y: number }, targetGmlId?: string): boolean {
        const offsets: Array<{ x: number; y: number }> = [{ x: 0, y: 0 }];
        const radii = [6, 12, 20, 30, 44, 60, 80];
        const directions = 12;

        for (const radius of radii) {
            for (let i = 0; i < directions; i++) {
                const angle = (i / directions) * Math.PI * 2;
                offsets.push({
                    x: Math.round(Math.cos(angle) * radius),
                    y: Math.round(Math.sin(angle) * radius),
                });
            }
        }

        let fallback:
            | {
                  gmlId: string;
                  feature: Cesium.Cesium3DTileFeature;
              }
            | undefined;

        for (const offset of offsets) {
            const pickPosition = new Cesium.Cartesian2(screenCoords.x + offset.x, screenCoords.y + offset.y);
            const picked = this.scene.drillPick(pickPosition, 20);

            for (const pickedObject of picked) {
                const gmlId = this.extractBuildingGmlId(pickedObject);
                if (!gmlId) continue;

                if (targetGmlId && this.isMatchingBuildingId(gmlId, targetGmlId)) {
                    this.setPreviewHighlight(pickedObject, gmlId);
                    return true;
                }

                if (!fallback) {
                    fallback = { gmlId, feature: pickedObject };
                }
            }
        }

        if (!targetGmlId && fallback) {
            this.setPreviewHighlight(fallback.feature, fallback.gmlId);
            return true;
        }

        return false;
    }

    /**
     * Try to preview-highlight a building at world coordinates.
     *
     * @param longitude - WGS84 longitude
     * @param latitude - WGS84 latitude
     * @param targetGmlId - Optional GML ID to match exactly
     * @returns True if a feature was highlighted
     */
    previewBuildingAtCoordinates(longitude: number, latitude: number, targetGmlId?: string): boolean {
        const cartesian = Cesium.Cartesian3.fromDegrees(longitude, latitude, 20);
        const windowPos = Cesium.SceneTransforms.worldToWindowCoordinates(this.scene, cartesian);
        if (!windowPos) return false;

        return this.previewBuildingAtScreen({ x: windowPos.x, y: windowPos.y }, targetGmlId);
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
        this.clearPreviewHighlight();

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

    /**
     * Get last picked candidates (for disambiguation UI) (Phase 5.1)
     *
     * @returns Array of candidate buildings from last pick
     */
    getLastCandidates(): PickedBuilding[] {
        return this.lastCandidates;
    }

    /**
     * Select a specific candidate from last pick (Phase 5.1)
     *
     * Used by disambiguation UI to select a specific building from overlapping candidates.
     *
     * @param gmlId - GML ID of building to select
     * @param multiSelect - If true, toggle selection; if false, replace selection
     * @returns True if selection succeeded, false if candidate not found
     */
    selectCandidate(gmlId: string, multiSelect: boolean = false): boolean {
        const candidate = this.lastCandidates.find((c) => c.gmlId === gmlId);
        if (!candidate || !this.lastScreenCoords) {
            console.warn(
                `[CesiumBuildingPicker] Cannot select candidate ${gmlId} - not found in last candidates`,
            );
            return false;
        }

        // Re-pick to get feature reference for highlighting
        const pickedFeature = this.viewer.scene.pick(
            new Cesium.Cartesian2(this.lastScreenCoords.x, this.lastScreenCoords.y),
        );

        if (!pickedFeature) {
            console.warn("[CesiumBuildingPicker] Could not re-pick feature for highlighting");
            // Still proceed with building from candidates
        }

        // Handle multi-select
        if (multiSelect) {
            // Toggle selection
            if (this.selectedBuildings.has(gmlId)) {
                this.removeBuilding(gmlId);
            } else {
                this.addBuilding(candidate, pickedFeature);
            }
        } else {
            // Replace selection
            this.clearSelection();
            this.addBuilding(candidate, pickedFeature);
        }

        return true;
    }
}
