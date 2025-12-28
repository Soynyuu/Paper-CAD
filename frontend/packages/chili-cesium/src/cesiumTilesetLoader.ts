// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import * as Cesium from "cesium";

/**
 * CesiumTilesetLoader
 *
 * Manages loading and unloading of PLATEAU 3D Tiles tilesets.
 *
 * Features:
 * - Load tileset from URL
 * - Unload tileset and cleanup
 * - Custom styling for highlighting
 * - Error handling for failed tile requests
 *
 * Usage:
 * ```typescript
 * const loader = new CesiumTilesetLoader(viewer);
 * const tileset = await loader.loadTileset(cityConfig.tilesetUrl);
 * ```
 */
export class CesiumTilesetLoader {
    private viewer: Cesium.Viewer;
    private currentTileset: Cesium.Cesium3DTileset | null = null;

    constructor(viewer: Cesium.Viewer) {
        this.viewer = viewer;
    }

    /**
     * Load 3D Tiles tileset from URL
     *
     * @param url - Tileset JSON URL
     * @returns Promise that resolves to the loaded tileset
     */
    async loadTileset(url: string): Promise<Cesium.Cesium3DTileset> {
        // Unload existing tileset if any
        if (this.currentTileset) {
            this.unloadTileset();
        }

        try {
            const tileset = await Cesium.Cesium3DTileset.fromUrl(url, {
                // Enable debugging for development
                debugShowBoundingVolume: false,
                debugShowContentBoundingVolume: false,
                debugShowGeometricError: false,

                // Performance settings
                maximumScreenSpaceError: 16,
                // maximumMemoryUsage removed - not a valid Cesium property

                // Skip LOD levels for faster loading
                skipLevelOfDetail: true,
                baseScreenSpaceError: 1024,
                skipScreenSpaceErrorFactor: 16,
                skipLevels: 1,

                // Preload ancestors for better picking
                preloadWhenHidden: true,
                preloadFlightDestinations: false,
                preferLeaves: true,

                // Enable dynamic screen space error for LOD
                dynamicScreenSpaceError: true,
                dynamicScreenSpaceErrorDensity: 0.00278,
                dynamicScreenSpaceErrorFactor: 4.0,
                dynamicScreenSpaceErrorHeightFalloff: 0.25,
            });

            // Add to scene
            this.viewer.scene.primitives.add(tileset);
            this.currentTileset = tileset;

            // Tileset is already ready from fromUrl() - no need to await readyPromise

            // Apply default styling
            this.setDefaultStyle(tileset);

            // Fly to tileset bounds
            await this.viewer.zoomTo(tileset);

            return tileset;
        } catch (error) {
            console.error("[CesiumTilesetLoader] Failed to load tileset:", error);
            throw new Error(
                `Failed to load 3D Tiles: ${error instanceof Error ? error.message : String(error)}`,
            );
        }
    }

    /**
     * Unload current tileset and cleanup
     */
    unloadTileset(): void {
        if (this.currentTileset) {
            this.viewer.scene.primitives.remove(this.currentTileset);
            this.currentTileset = null;
        }
    }

    /**
     * Get current loaded tileset
     *
     * @returns Current tileset or null
     */
    getCurrentTileset(): Cesium.Cesium3DTileset | null {
        return this.currentTileset;
    }

    /**
     * Set default style for PLATEAU buildings
     *
     * @param tileset - Tileset to style
     */
    private setDefaultStyle(tileset: Cesium.Cesium3DTileset): void {
        tileset.style = new Cesium.Cesium3DTileStyle({
            color: {
                conditions: [
                    ["${feature_type} === 'bldg:Building'", "color('white', 0.9)"],
                    ["true", "color('lightgray', 0.8)"],
                ],
            },
            show: "${feature_type} === 'bldg:Building'", // Only show buildings
        });
    }

    /**
     * Set custom style for tileset
     *
     * @param style - Cesium3DTileStyle or style JSON
     */
    setTilesetStyle(style: Cesium.Cesium3DTileStyle | any): void {
        if (this.currentTileset) {
            this.currentTileset.style =
                style instanceof Cesium.Cesium3DTileStyle ? style : new Cesium.Cesium3DTileStyle(style);
        }
    }

    /**
     * Reset to default style
     */
    resetStyle(): void {
        if (this.currentTileset) {
            this.setDefaultStyle(this.currentTileset);
        }
    }
}
