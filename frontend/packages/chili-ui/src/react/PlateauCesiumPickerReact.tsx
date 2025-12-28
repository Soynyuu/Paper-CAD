// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState, useMemo } from "react";
import { useAtom } from "jotai";
import { Viewer, Cesium3DTileset, CameraFlyTo } from "resium";
import * as Cesium from "cesium";
import { DialogResult, I18n, PubSub } from "chili-core";
import { CesiumBuildingPicker, getAllCities, getCityConfig, type PickedBuilding } from "chili-cesium";
import {
    currentCityAtom,
    selectedBuildingsAtom,
    loadingAtom,
    loadingMessageAtom,
} from "./atoms/cesiumState";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Instructions } from "./components/Instructions";
import { Loading } from "./components/Loading";
import styles from "./PlateauCesiumPickerReact.module.css";

const CESIUM_WIDGET_CSS_ID = "cesium-widget-css";

const ensureCesiumRuntime = () => {
    if (typeof document === "undefined") {
        return;
    }

    const runtime = globalThis as any;
    const rawBaseUrl = runtime.__APP_CONFIG__?.cesiumBaseUrl || "/cesium/";
    const baseUrl = rawBaseUrl.endsWith("/") ? rawBaseUrl : `${rawBaseUrl}/`;

    runtime.CESIUM_BASE_URL = baseUrl;

    const ionToken = runtime.__APP_CONFIG__?.cesiumIonToken;
    if (ionToken) {
        Cesium.Ion.defaultAccessToken = ionToken;
    }

    if (!document.getElementById(CESIUM_WIDGET_CSS_ID)) {
        const link = document.createElement("link");
        link.id = CESIUM_WIDGET_CSS_ID;
        link.rel = "stylesheet";
        link.href = `${baseUrl}Widgets/CesiumWidget/CesiumWidget.css`;
        document.head.appendChild(link);
    }
};

ensureCesiumRuntime();

export interface PlateauCesiumPickerReactProps {
    onClose: (result: DialogResult, data?: { selectedBuildings: PickedBuilding[] }) => void;
}

/**
 * PlateauCesiumPickerReact - React-based PLATEAU building picker using resium
 *
 * Uses resium (React bindings for Cesium) instead of @reearth/core for better compatibility.
 */
export function PlateauCesiumPickerReact({ onClose }: PlateauCesiumPickerReactProps) {
    const viewerRef = useRef<Cesium.Viewer | null>(null);
    const tilesetRef = useRef<Cesium.Cesium3DTileset | null>(null);
    const handlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);
    const buildingPickerRef = useRef<CesiumBuildingPicker | null>(null);
    const basemapInitializedRef = useRef(false);
    const basemapFallbackRef = useRef(false);

    const [currentCity, setCurrentCity] = useAtom(currentCityAtom);
    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [tilesetUrl, setTilesetUrl] = useState<string>("");
    const [cameraDestination, setCameraDestination] = useState<Cesium.Cartesian3 | undefined>();
    const [viewerReady, setViewerReady] = useState(false);
    const baseLayer = useMemo(() => {
        if (typeof window === "undefined") {
            return undefined;
        }

        // GSI tiles (Japan) - return ImageryProvider directly for resium
        return new Cesium.UrlTemplateImageryProvider({
            url: "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
            credit: "GSI Tiles",
            maximumLevel: 18,
        });
    }, []);

    // Initialize with first city
    useEffect(() => {
        const cities = getAllCities();
        if (cities.length > 0 && !currentCity) {
            setCurrentCity(cities[0].key);
        }
    }, [currentCity, setCurrentCity]);

    // Load city tileset when city changes
    useEffect(() => {
        if (!currentCity) return;

        const cityConfig = getCityConfig(currentCity);
        if (!cityConfig) {
            PubSub.default.pub("showToast", "error.plateau.cityNotFound:{0}", currentCity);
            return;
        }

        setLoading(true);
        setLoadingMessage(I18n.translate("plateau.cesium.loading"));

        // Clear previous selections
        if (buildingPickerRef.current) {
            buildingPickerRef.current.clearSelection();
        }
        setSelectedBuildings([]);

        // Update tileset URL
        setTilesetUrl(cityConfig.tilesetUrl);

        // Set camera destination
        const destination = Cesium.Cartesian3.fromDegrees(
            cityConfig.initialView.longitude,
            cityConfig.initialView.latitude,
            cityConfig.initialView.height,
        );
        setCameraDestination(destination);

        // Set camera position directly if viewer is ready (avoids race condition)
        if (viewerRef.current) {
            console.log("[PlateauCesiumPickerReact] Setting camera position for city:", currentCity);
            viewerRef.current.camera.setView({
                destination,
                orientation: {
                    heading: 0,
                    pitch: Cesium.Math.toRadians(-45),
                    roll: 0,
                },
            });
        }

        // Loading will be cleared when tileset loads
    }, [currentCity, setSelectedBuildings, setLoading, setLoadingMessage]);

    // Setup click handler when viewer is ready
    useEffect(() => {
        const viewer = viewerRef.current;
        const picker = buildingPickerRef.current;
        if (!viewer || !picker) return;

        // Clean up old handler
        if (handlerRef.current) {
            handlerRef.current.destroy();
        }

        // Create new handler
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
        handlerRef.current = handler;

        handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
            if (!click.position) return;

            const isMultiSelect = (click as any).modifier === Cesium.KeyboardEventModifier.CTRL;

            try {
                picker.pickBuilding({ x: click.position.x, y: click.position.y }, isMultiSelect);
                setSelectedBuildings(picker.getSelectedBuildings());
            } catch (error) {
                if (error instanceof Error) {
                    PubSub.default.pub("showToast", "error.plateau.selectionFailed:{0}", error.message);
                }
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        return () => {
            if (handlerRef.current) {
                handlerRef.current.destroy();
                handlerRef.current = null;
            }
        };
    }, [setSelectedBuildings, viewerReady]);

    // Setup base map once the viewer is ready (FALLBACK ONLY)
    useEffect(() => {
        if (!viewerReady || basemapInitializedRef.current) return;

        const viewer = viewerRef.current;
        if (!viewer) return;

        basemapInitializedRef.current = true;

        // Check if base layer already exists (from baseLayer prop)
        if (viewer.imageryLayers.length > 0) {
            console.log("[PlateauCesiumPickerReact] Base layer already initialized via prop");
            return;
        }

        // Fallback: Add basemap manually if baseLayer prop failed
        console.warn("[PlateauCesiumPickerReact] Base layer missing; adding manually");

        const gsiProvider = new Cesium.UrlTemplateImageryProvider({
            url: "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
            credit: "GSI Tiles",
            maximumLevel: 18,
        });

        viewer.imageryLayers.add(new Cesium.ImageryLayer(gsiProvider));

        // OSM fallback on error
        const fallbackToOsm = () => {
            if (basemapFallbackRef.current) return;
            basemapFallbackRef.current = true;
            viewer.imageryLayers.removeAll();
            const osmProvider = new Cesium.OpenStreetMapImageryProvider({
                url: "https://tile.openstreetmap.org/",
            });
            viewer.imageryLayers.add(new Cesium.ImageryLayer(osmProvider));
            console.warn("[PlateauCesiumPickerReact] GSI tiles failed; falling back to OSM.");
        };

        const onError = () => fallbackToOsm();
        gsiProvider.errorEvent.addEventListener(onError);

        return () => {
            gsiProvider.errorEvent.removeEventListener(onError);
        };
    }, [viewerReady]);

    // Configure scene for optimal 3D Tiles rendering (mirror CesiumView.initialize)
    useEffect(() => {
        if (!viewerReady) return;

        const viewer = viewerRef.current;
        if (!viewer) return;

        console.log("[PlateauCesiumPickerReact] Configuring scene for 3D Tiles");

        // Scene configuration (from cesiumView.ts lines 83-96)
        if (viewer.scene) {
            viewer.scene.globe.depthTestAgainstTerrain = false;
            viewer.scene.globe.enableLighting = false;
            viewer.scene.highDynamicRange = false;
            viewer.scene.requestRenderMode = true;
            viewer.scene.maximumRenderTimeChange = 0.5;
        }

        // Camera configuration
        if (viewer.camera) {
            viewer.camera.percentageChanged = 0.05;
        }

        // Disable default double-click zoom
        if (viewer.screenSpaceEventHandler) {
            viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
        }
    }, [viewerReady]);

    // Handle city change
    const handleCityChange = useCallback(
        (cityKey: string) => {
            setCurrentCity(cityKey);
        },
        [setCurrentCity],
    );

    // Handle remove building
    const handleRemoveBuilding = useCallback(
        (gmlId: string) => {
            const picker = buildingPickerRef.current;
            if (!picker) {
                setSelectedBuildings((prev) => prev.filter((b) => b.gmlId !== gmlId));
                return;
            }

            picker.removeBuilding(gmlId);
            setSelectedBuildings(picker.getSelectedBuildings());
        },
        [setSelectedBuildings],
    );

    // Handle import
    const handleImport = useCallback(() => {
        if (selectedBuildings.length === 0) {
            PubSub.default.pub("showToast", "error.plateau.selectAtLeastOne");
            return;
        }
        onClose(DialogResult.ok, { selectedBuildings });
    }, [selectedBuildings, onClose]);

    // Handle clear
    const handleClear = useCallback(() => {
        const picker = buildingPickerRef.current;
        if (picker) {
            picker.clearSelection();
        }
        setSelectedBuildings([]);
    }, [setSelectedBuildings]);

    // Handle close
    const handleClose = useCallback(() => {
        onClose(DialogResult.cancel);
    }, [onClose]);

    // Handle tileset ready
    const handleTilesetReady = useCallback(
        (tileset: Cesium.Cesium3DTileset) => {
            tilesetRef.current = tileset;
            tileset.style = new Cesium.Cesium3DTileStyle({
                color: {
                    conditions: [
                        ["${feature_type} === 'bldg:Building'", "color('white', 0.9)"],
                        ["true", "color('lightgray', 0.8)"],
                    ],
                },
                show: "${feature_type} === 'bldg:Building'",
            });
            setLoading(false);
            setLoadingMessage("");
        },
        [setLoading, setLoadingMessage],
    );

    // Handle viewer ready
    const handleViewerReady = useCallback((ref: any) => {
        // resium refs contain the Cesium element in cesiumElement property
        if (!ref || !ref.cesiumElement) {
            return;
        }

        // Only initialize once - prevent multiple initializations
        if (viewerRef.current) {
            console.log("[PlateauCesiumPickerReact] Viewer already initialized, skipping");
            return;
        }

        console.log("[PlateauCesiumPickerReact] Viewer ready callback fired");
        viewerRef.current = ref.cesiumElement;
        buildingPickerRef.current = new CesiumBuildingPicker(ref.cesiumElement);

        // Validate canvas dimensions
        if (!ref.cesiumElement.canvas) {
            console.error("[PlateauCesiumPickerReact] Viewer canvas is missing!");
            return;
        }

        if (ref.cesiumElement.canvas.width === 0 || ref.cesiumElement.canvas.height === 0) {
            console.warn("[PlateauCesiumPickerReact] Canvas has zero dimensions, forcing resize");
            ref.cesiumElement.resize();
        }

        setViewerReady(true);
        console.log("[PlateauCesiumPickerReact] Viewer ready");
    }, []);

    return (
        <div className={styles.dialog}>
            <Header
                currentCity={currentCity}
                onCityChange={handleCityChange}
                onClose={handleClose}
                loading={loading}
            />
            <div className={styles.body}>
                <div className={styles.mapContainer}>
                    <Viewer
                        full
                        ref={handleViewerReady}
                        timeline={false}
                        animation={false}
                        baseLayer={baseLayer}
                        baseLayerPicker={false}
                        geocoder={false}
                        homeButton={false}
                        navigationHelpButton={false}
                        sceneModePicker={false}
                        selectionIndicator={false}
                        infoBox={false}
                    >
                        {tilesetUrl && (
                            <>
                                <Cesium3DTileset url={tilesetUrl} onReady={handleTilesetReady} />
                                {cameraDestination && (
                                    <CameraFlyTo
                                        destination={cameraDestination}
                                        duration={2}
                                        orientation={{
                                            heading: 0,
                                            pitch: Cesium.Math.toRadians(-45),
                                            roll: 0,
                                        }}
                                    />
                                )}
                            </>
                        )}
                    </Viewer>
                    <Instructions />
                    {loading && <Loading message={loadingMessage} />}
                </div>
                <Sidebar
                    selectedBuildings={selectedBuildings}
                    onRemove={handleRemoveBuilding}
                    onImport={handleImport}
                    onClear={handleClear}
                />
            </div>
        </div>
    );
}
