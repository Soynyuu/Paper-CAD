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
    private loadedTilesets: Map<string, Cesium.Cesium3DTileset> = new Map();
    private meshLoadOrder: string[] = []; // LRU tracking
    // Keep the cache small for picker use to reduce memory pressure.
    private readonly MAX_LOADED_MESHES = 12;

    constructor(viewer: Cesium.Viewer) {
        this.viewer = viewer;
    }

    private getTilesetOptions() {
        return {
            // Enable debugging for development
            debugShowBoundingVolume: false,
            debugShowContentBoundingVolume: false,
            debugShowGeometricError: false,

            // Performance settings
            maximumScreenSpaceError: 128,
            cacheBytes: 48 * 1024 * 1024,
            maximumCacheOverflowBytes: 16 * 1024 * 1024,
            cullRequestsWhileMoving: true,
            cullRequestsWhileMovingMultiplier: 80,

            // Skip LOD levels for faster loading
            skipLevelOfDetail: true,
            baseScreenSpaceError: 2048,
            skipScreenSpaceErrorFactor: 64,
            skipLevels: 3,
            loadSiblings: false,

            // Avoid eager preloading to keep memory use down.
            preloadWhenHidden: false,
            preloadFlightDestinations: false,
            preferLeaves: false,

            // Enable dynamic screen space error for LOD
            dynamicScreenSpaceError: true,
            dynamicScreenSpaceErrorDensity: 0.00278,
            dynamicScreenSpaceErrorFactor: 64.0,
            dynamicScreenSpaceErrorHeightFalloff: 0.25,
            progressiveResolutionHeightFraction: 0.2,
            foveatedMinimumScreenSpaceErrorRelaxation: 4.0,
            foveatedConeSize: 0.2,
            foveatedTimeDelay: 0.4,
        };
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
            const tileset = await Cesium.Cesium3DTileset.fromUrl(url, this.getTilesetOptions());

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
            // Preserve original materials/textures; do not override color.
            show: "true",
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

    /**
     * Load multiple tilesets in parallel
     *
     * @param tilesets - Array of tileset info with meshCode and url
     * @returns Promise that resolves when all tilesets are loaded, with failed meshes
     *
     * @example
     * await loader.loadMultipleTilesets([
     *     { meshCode: "53394511", url: "https://..." },
     *     { meshCode: "53394512", url: "https://..." }
     * ]);
     */
    async loadMultipleTilesets(
        tilesets: Array<{ meshCode: string; url: string }>,
    ): Promise<{ failedMeshes: string[]; loadedTilesets: Cesium.Cesium3DTileset[] }> {
        const failedMeshes: string[] = [];
        const loadedTilesets: Cesium.Cesium3DTileset[] = [];
        const loadPromises = tilesets.map(async ({ meshCode, url }) => {
            // Skip if already loaded, but update access time
            if (this.loadedTilesets.has(meshCode)) {
                this.updateMeshAccessTime(meshCode);
                console.log(`[CesiumTilesetLoader] Mesh ${meshCode} already loaded, updating access time`);
                return;
            }

            // Check if we need to unload old meshes before loading new ones
            if (this.loadedTilesets.size >= this.MAX_LOADED_MESHES) {
                this.unloadOldestMesh();
                console.log(
                    `[CesiumTilesetLoader] Reached max meshes (${this.MAX_LOADED_MESHES}), unloaded oldest`,
                );
            }

            try {
                const tileset = await Cesium.Cesium3DTileset.fromUrl(url, this.getTilesetOptions());

                // Add to scene
                this.viewer.scene.primitives.add(tileset);
                this.loadedTilesets.set(meshCode, tileset);
                loadedTilesets.push(tileset);

                // Track in LRU order
                this.meshLoadOrder.push(meshCode);

                // Apply default styling
                this.setDefaultStyle(tileset);

                console.log(`[CesiumTilesetLoader] Loaded mesh ${meshCode}`);
            } catch (error) {
                console.warn(`[CesiumTilesetLoader] Failed to load mesh ${meshCode}:`, error);
                failedMeshes.push(meshCode);
            }
        });

        await Promise.all(loadPromises);

        console.log(`[CesiumTilesetLoader] Loaded ${this.loadedTilesets.size} tilesets total`);
        return { failedMeshes, loadedTilesets };
    }

    /**
     * Unload tileset for specific mesh code
     *
     * @param meshCode - Mesh code to unload
     */
    unloadTilesetByMesh(meshCode: string): void {
        const tileset = this.loadedTilesets.get(meshCode);
        if (tileset) {
            this.viewer.scene.primitives.remove(tileset);
            this.loadedTilesets.delete(meshCode);

            // Remove from LRU order
            const index = this.meshLoadOrder.indexOf(meshCode);
            if (index > -1) {
                this.meshLoadOrder.splice(index, 1);
            }

            console.log(`[CesiumTilesetLoader] Unloaded mesh ${meshCode}`);
        }
    }

    /**
     * Update mesh access time for LRU (move to end = most recently used)
     *
     * @param meshCode - Mesh code that was accessed
     */
    private updateMeshAccessTime(meshCode: string): void {
        const index = this.meshLoadOrder.indexOf(meshCode);
        if (index > -1) {
            // Remove from current position
            this.meshLoadOrder.splice(index, 1);
        }
        // Add to end (most recently used)
        this.meshLoadOrder.push(meshCode);
    }

    /**
     * Unload the oldest (least recently used) mesh to free memory
     */
    private unloadOldestMesh(): void {
        const oldestMesh = this.meshLoadOrder.shift();
        if (oldestMesh) {
            const tileset = this.loadedTilesets.get(oldestMesh);
            if (tileset) {
                this.viewer.scene.primitives.remove(tileset);
                this.loadedTilesets.delete(oldestMesh);
                console.log(`[CesiumTilesetLoader] Auto-unloaded old mesh: ${oldestMesh}`);
            }
        }
    }

    /**
     * Get list of loaded mesh codes
     *
     * @returns Array of loaded mesh codes
     */
    getLoadedMeshCodes(): string[] {
        return Array.from(this.loadedTilesets.keys());
    }

    /**
     * Keep only the specified mesh codes loaded, unloading the rest.
     *
     * @param meshCodes - Mesh codes to retain
     */
    retainMeshes(meshCodes: string[]): void {
        const keep = new Set(meshCodes);
        Array.from(this.loadedTilesets.keys()).forEach((meshCode) => {
            if (!keep.has(meshCode)) {
                this.unloadTilesetByMesh(meshCode);
            }
        });
    }

    /**
     * Clear all loaded tilesets
     */
    clearAll(): void {
        this.loadedTilesets.forEach((tileset) => {
            this.viewer.scene.primitives.remove(tileset);
        });
        this.loadedTilesets.clear();

        // Clear LRU tracking
        this.meshLoadOrder = [];

        // Also clear legacy currentTileset
        if (this.currentTileset) {
            this.viewer.scene.primitives.remove(this.currentTileset);
            this.currentTileset = null;
        }

        console.log(`[CesiumTilesetLoader] Cleared all tilesets`);
    }

    /**
     * Get total number of loaded tilesets
     *
     * @returns Number of loaded tilesets
     */
    getTilesetCount(): number {
        return this.loadedTilesets.size;
    }
}
