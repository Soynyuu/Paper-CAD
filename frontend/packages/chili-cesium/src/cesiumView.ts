// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import * as Cesium from "cesium";
import type { CityConfig } from "./types";

/**
 * Basemap types supported by CesiumView
 */
export type BasemapType = "natural-earth" | "gsi-standard" | "gsi-pale" | "gsi-photo";

/**
 * Basemap configuration interface
 */
interface BasemapConfig {
    name: string;
    provider: () => Promise<Cesium.ImageryProvider>;
}

const GSI_CREDIT_HTML =
    '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>';
const createGsiCredit = () => new Cesium.Credit(GSI_CREDIT_HTML, true);

/**
 * Basemap registry with GSI (Geospatial Information Authority of Japan) layers
 */
const BASEMAPS: Record<BasemapType, BasemapConfig> = {
    "natural-earth": {
        name: "Natural Earth II",
        provider: async () => {
            return Cesium.TileMapServiceImageryProvider.fromUrl(
                Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"),
            );
        },
    },
    "gsi-standard": {
        name: "GSI Standard Map",
        provider: async () => {
            return new Cesium.UrlTemplateImageryProvider({
                url: "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png",
                maximumLevel: 18,
                credit: createGsiCredit(),
            });
        },
    },
    "gsi-pale": {
        name: "GSI Pale Map",
        provider: async () => {
            return new Cesium.UrlTemplateImageryProvider({
                url: "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
                maximumLevel: 18,
                credit: createGsiCredit(),
            });
        },
    },
    "gsi-photo": {
        name: "GSI Photo",
        provider: async () => {
            return new Cesium.UrlTemplateImageryProvider({
                url: "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg",
                maximumLevel: 18,
                credit: createGsiCredit(),
            });
        },
    },
};

// Load Cesium CSS dynamically
if (typeof document !== "undefined" && !document.getElementById("cesium-widget-css")) {
    const link = document.createElement("link");
    link.id = "cesium-widget-css";
    link.rel = "stylesheet";
    link.href = "/cesium/Widgets/CesiumWidget/CesiumWidget.css";
    document.head.appendChild(link);
}

/**
 * CesiumView
 *
 * Main wrapper for Cesium.Viewer with PLATEAU-specific configuration.
 *
 * Features:
 * - Initialize Cesium viewer with optimized settings
 * - Camera navigation controls
 * - Tileset management
 * - Event handling integration
 *
 * Usage:
 * ```typescript
 * const view = new CesiumView(container);
 * await view.initialize();
 * view.flyToCity(cityConfig);
 * ```
 */
export class CesiumView {
    private viewer: Cesium.Viewer | null = null;
    private container: HTMLElement;
    private currentBasemap: BasemapType = "gsi-pale";

    constructor(container: HTMLElement) {
        this.container = container;
    }

    /**
     * Initialize Cesium viewer with PLATEAU-optimized settings
     *
     * @param basemap - Initial basemap type (default: gsi-pale)
     */
    async initialize(basemap: BasemapType = "gsi-pale"): Promise<void> {
        // Set Cesium base URL from environment
        const cesiumBaseUrl = (window as any).__APP_CONFIG__?.cesiumBaseUrl || "/cesium/";
        (window as any).CESIUM_BASE_URL = cesiumBaseUrl;

        // Set Cesium Ion token if provided
        const ionToken = (window as any).__APP_CONFIG__?.cesiumIonToken;
        if (ionToken) {
            Cesium.Ion.defaultAccessToken = ionToken;
        }

        this.viewer = new Cesium.Viewer(this.container, {
            // Disable unnecessary UI elements
            animation: false,
            timeline: false,
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            sceneModePicker: false,
            navigationHelpButton: false,
            fullscreenButton: false,
            vrButton: false,
            infoBox: false,
            selectionIndicator: false,

            // Enable depth testing for 3D Tiles
            requestRenderMode: true,
            maximumRenderTimeChange: Infinity,

            // Use GSI basemap with Natural Earth fallback
            baseLayer: false, // Will be added manually after viewer creation
        });

        // Use PLATEAU terrain to align with Japan's geoid-based elevations
        await this.applyTerrainProvider();

        // Initialize basemap with fallback handling
        try {
            const basemapConfig = BASEMAPS[basemap];
            const provider = await basemapConfig.provider();
            this.viewer.imageryLayers.addImageryProvider(provider);
            this.currentBasemap = basemap;
        } catch (error) {
            console.warn(
                `[CesiumView] Failed to load ${basemap} basemap, falling back to Natural Earth:`,
                error,
            );
            // Fallback to Natural Earth
            const fallbackProvider = await BASEMAPS["natural-earth"].provider();
            this.viewer.imageryLayers.addImageryProvider(fallbackProvider);
            this.currentBasemap = "natural-earth";
        }

        // Configure scene for better 3D Tiles rendering
        if (this.viewer.scene) {
            this.viewer.scene.globe.depthTestAgainstTerrain = false;
            this.viewer.scene.globe.enableLighting = false;

            // High-quality rendering settings
            this.viewer.scene.highDynamicRange = false;
            this.viewer.scene.requestRenderMode = true;
            this.viewer.scene.maximumRenderTimeChange = 0.5;
        }

        // Configure camera
        if (this.viewer.camera) {
            this.viewer.camera.percentageChanged = 0.05;
        }

        // Disable default double-click zoom
        if (this.viewer.screenSpaceEventHandler) {
            this.viewer.screenSpaceEventHandler.removeInputAction(
                Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK,
            );
        }
    }

    private async applyTerrainProvider(): Promise<void> {
        if (!this.viewer) return;

        const assetId = __APP_CONFIG__.cesiumTerrainAssetId;
        if (!Number.isFinite(assetId) || assetId <= 0) {
            return;
        }

        try {
            const terrainProvider = await Cesium.CesiumTerrainProvider.fromIonAssetId(assetId);
            this.viewer.terrainProvider = terrainProvider;
        } catch (error) {
            console.warn("[CesiumView] Failed to load PLATEAU terrain, using default terrain.", error);
        }
    }

    /**
     * Fly camera to city location
     *
     * @param cityConfig - City configuration with initial view
     * @param duration - Flight duration in seconds (default: 2.0)
     */
    flyToCity(cityConfig: CityConfig, duration: number = 2.0): void {
        if (!this.viewer) {
            throw new Error("Viewer not initialized. Call initialize() first.");
        }

        this.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(
                cityConfig.initialView.longitude,
                cityConfig.initialView.latitude,
                cityConfig.initialView.height,
            ),
            duration,
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-45),
                roll: 0,
            },
        });
    }

    /**
     * Get Cesium.Viewer instance
     *
     * @returns Cesium.Viewer or null if not initialized
     */
    getViewer(): Cesium.Viewer | null {
        return this.viewer;
    }

    /**
     * Switch to a different basemap
     *
     * @param basemapType - Target basemap type
     * @throws Error if viewer is not initialized
     */
    async switchBasemap(basemapType: BasemapType): Promise<void> {
        if (!this.viewer) {
            throw new Error("Viewer not initialized. Call initialize() first.");
        }

        if (basemapType === this.currentBasemap) {
            return; // Already using this basemap
        }

        try {
            // Remove current basemap layer (index 0)
            const currentLayer = this.viewer.imageryLayers.get(0);
            if (currentLayer) {
                this.viewer.imageryLayers.remove(currentLayer);
            }

            // Add new basemap
            const basemapConfig = BASEMAPS[basemapType];
            const provider = await basemapConfig.provider();
            this.viewer.imageryLayers.addImageryProvider(provider, 0); // Insert at index 0
            this.currentBasemap = basemapType;

            console.log(`[CesiumView] Switched to basemap: ${basemapConfig.name}`);
        } catch (error) {
            console.error(`[CesiumView] Failed to switch to ${basemapType} basemap:`, error);
            throw error;
        }
    }

    /**
     * Get currently active basemap type
     *
     * @returns Current basemap type
     */
    getCurrentBasemap(): BasemapType {
        return this.currentBasemap;
    }

    /**
     * Get list of available basemap types
     *
     * @returns Array of basemap types
     */
    getAvailableBasemaps(): BasemapType[] {
        return Object.keys(BASEMAPS) as BasemapType[];
    }

    /**
     * Dispose viewer and cleanup resources
     */
    dispose(): void {
        if (this.viewer) {
            this.viewer.destroy();
            this.viewer = null;
        }
    }
}
