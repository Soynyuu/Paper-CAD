// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import * as Cesium from "cesium";

/**
 * LOD (Level of Detail) level type
 */
export type LodLevel = "LOD1" | "LOD2" | "LOD3";

/**
 * CesiumTilesetLoader
 *
 * Manages loading and unloading of PLATEAU 3D Tiles tilesets.
 *
 * Features:
 * - Load tileset from URL with automatic LOD3 → LOD2 → LOD1 fallback
 * - Unload tileset and cleanup
 * - Custom styling for highlighting
 * - Error handling for failed tile requests
 * - Performance optimization per LOD level
 * - Texture preservation for textured tilesets
 *
 * Usage:
 * ```typescript
 * const loader = new CesiumTilesetLoader(viewer);
 * const tileset = await loader.loadTileset(cityConfig.tilesetUrl);
 * const lodLevel = loader.getCurrentLodLevel(); // "LOD3", "LOD2", or "LOD1"
 * ```
 */
export class CesiumTilesetLoader {
    private viewer: Cesium.Viewer;
    private currentTileset: Cesium.Cesium3DTileset | null = null;
    private currentLodLevel: LodLevel | null = null;

    constructor(viewer: Cesium.Viewer) {
        this.viewer = viewer;
    }

    /**
     * Get the LOD level of the currently loaded tileset
     *
     * @returns Current LOD level or null if no tileset loaded
     */
    getCurrentLodLevel(): LodLevel | null {
        return this.currentLodLevel;
    }

    /**
     * Generate LOD variant URLs from a base URL
     *
     * @param baseUrl - Base tileset URL (usually LOD1)
     * @returns Object with lod1, lod2, and lod3 URLs
     */
    private generateLodUrls(baseUrl: string): { lod1: string; lod2: string; lod3: string } {
        // Replace _lod1, _lod2, or _lod3 in the URL
        const lod1 = baseUrl.replace(/_lod[123]/, "_lod1");
        const lod2 = baseUrl.replace(/_lod[123]/, "_lod2");
        const lod3 = baseUrl.replace(/_lod[123]/, "_lod3");

        return { lod1, lod2, lod3 };
    }

    /**
     * Get Cesium tileset options optimized for specific LOD level
     *
     * @param lodLevel - LOD level
     * @returns Cesium tileset constructor options
     */
    private getCesiumOptionsForLod(lodLevel: LodLevel): Cesium.Cesium3DTileset.ConstructorOptions {
        const baseOptions = {
            // Debugging (disabled for production)
            debugShowBoundingVolume: false,
            debugShowContentBoundingVolume: false,
            debugShowGeometricError: false,

            // Common settings
            baseScreenSpaceError: 1024,
            skipScreenSpaceErrorFactor: 16,
            preloadWhenHidden: true,
            preferLeaves: true,

            // Dynamic screen space error for LOD
            dynamicScreenSpaceError: true,
            dynamicScreenSpaceErrorDensity: 0.00278,
            dynamicScreenSpaceErrorFactor: 4.0,
            dynamicScreenSpaceErrorHeightFalloff: 0.25,
        };

        // LOD-specific optimizations
        switch (lodLevel) {
            case "LOD3":
                // Highest quality - load all detail
                return {
                    ...baseOptions,
                    maximumScreenSpaceError: 2,
                    skipLevelOfDetail: false,
                    skipLevels: 0,
                    preloadFlightDestinations: true,
                };

            case "LOD2":
                // Balanced quality and performance
                return {
                    ...baseOptions,
                    maximumScreenSpaceError: 8,
                    skipLevelOfDetail: false,
                    skipLevels: 0,
                    preloadFlightDestinations: false,
                };

            case "LOD1":
                // Performance optimized - skip intermediate levels
                return {
                    ...baseOptions,
                    maximumScreenSpaceError: 16,
                    skipLevelOfDetail: true,
                    skipLevels: 1,
                    preloadFlightDestinations: false,
                };
        }
    }

    /**
     * Try to load tileset from a specific LOD level
     *
     * @param url - Tileset URL
     * @param lodLevel - LOD level being attempted
     * @returns Result with success flag and tileset or error
     */
    private async tryLoadTileset(
        url: string,
        lodLevel: LodLevel,
    ): Promise<{ success: boolean; tileset?: Cesium.Cesium3DTileset; error?: Error }> {
        try {
            console.log(`[CesiumTilesetLoader] Attempting ${lodLevel}: ${url}`);

            const options = this.getCesiumOptionsForLod(lodLevel);
            const tileset = await Cesium.Cesium3DTileset.fromUrl(url, options);

            // Add to scene
            this.viewer.scene.primitives.add(tileset);
            this.currentTileset = tileset;
            this.currentLodLevel = lodLevel;

            // Apply default styling
            this.setDefaultStyle(tileset);

            // Fly to tileset bounds
            await this.viewer.zoomTo(tileset);

            console.log(`[CesiumTilesetLoader] ✓ ${lodLevel} loaded successfully`);
            return { success: true, tileset };
        } catch (error) {
            console.log(
                `[CesiumTilesetLoader] ✗ ${lodLevel} failed:`,
                error instanceof Error ? error.message : String(error),
            );
            return { success: false, error: error as Error };
        }
    }

    /**
     * Load 3D Tiles tileset from URL with automatic LOD3 → LOD2 → LOD1 fallback
     *
     * @param url - Tileset JSON URL (can be any LOD level)
     * @returns Promise that resolves to the loaded tileset
     */
    async loadTileset(url: string): Promise<Cesium.Cesium3DTileset> {
        // Unload existing tileset if any
        if (this.currentTileset) {
            this.unloadTileset();
        }

        // Generate LOD variant URLs
        const urls = this.generateLodUrls(url);

        // Try LOD3 first (highest detail)
        const lod3Result = await this.tryLoadTileset(urls.lod3, "LOD3");
        if (lod3Result.success) {
            return lod3Result.tileset!;
        }

        // Fallback to LOD2 (medium detail)
        const lod2Result = await this.tryLoadTileset(urls.lod2, "LOD2");
        if (lod2Result.success) {
            return lod2Result.tileset!;
        }

        // Fallback to LOD1 (basic detail)
        const lod1Result = await this.tryLoadTileset(urls.lod1, "LOD1");
        if (lod1Result.success) {
            return lod1Result.tileset!;
        }

        // All LOD levels failed
        console.error("[CesiumTilesetLoader] Failed to load tileset at all LOD levels");
        throw new Error(
            `Failed to load 3D Tiles at all LOD levels (LOD3, LOD2, LOD1). Last error: ${lod1Result.error?.message || "Unknown error"}`,
        );
    }

    /**
     * Unload current tileset and cleanup
     */
    unloadTileset(): void {
        if (this.currentTileset) {
            this.viewer.scene.primitives.remove(this.currentTileset);
            this.currentTileset = null;
            this.currentLodLevel = null;
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
     * Preserves textures if present in tileset while filtering for buildings only.
     *
     * @param tileset - Tileset to style
     */
    private setDefaultStyle(tileset: Cesium.Cesium3DTileset): void {
        tileset.style = new Cesium.Cesium3DTileStyle({
            // Only filter visibility - let textures show through
            // Color conditions removed to preserve textures from LOD2/LOD3 tilesets
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
