// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import * as Cesium from "cesium";
import type { CityConfig } from "./types";

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

    constructor(container: HTMLElement) {
        this.container = container;
    }

    /**
     * Initialize Cesium viewer with PLATEAU-optimized settings
     */
    initialize(): void {
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

            // Use default imagery (no Ion token required)
            baseLayer: Cesium.ImageryLayer.fromProviderAsync(
                Cesium.TileMapServiceImageryProvider.fromUrl(
                    Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"),
                ),
            ),
        });

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
     * Dispose viewer and cleanup resources
     */
    dispose(): void {
        if (this.viewer) {
            this.viewer.destroy();
            this.viewer = null;
        }
    }
}
