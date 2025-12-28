// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState, useMemo } from "react";
import { useAtom } from "jotai";
import * as Cesium from "cesium";
import { DialogResult, I18n, PubSub } from "chili-core";
import {
    CesiumView,
    CesiumBuildingPicker,
    getAllCities,
    getCityConfig,
    type PickedBuilding,
    type CityConfig,
} from "chili-cesium";
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
 * PlateauCesiumPickerReact - React-based PLATEAU building picker
 *
 * Uses CesiumView (Web Components) wrapped in React for reliable Cesium integration.
 * This approach avoids the architectural mismatch between Cesium's imperative API
 * and React's declarative patterns that caused issues with resium.
 */
export function PlateauCesiumPickerReact({ onClose }: PlateauCesiumPickerReactProps) {
    const cesiumViewRef = useRef<CesiumView | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const tilesetRef = useRef<Cesium.Cesium3DTileset | null>(null);
    const handlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);
    const buildingPickerRef = useRef<CesiumBuildingPicker | null>(null);

    const [currentCity, setCurrentCity] = useAtom(currentCityAtom);
    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [tilesetUrl, setTilesetUrl] = useState<string>("");
    const [viewerReady, setViewerReady] = useState(false);

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

        // Use CesiumView.flyToCity instead of manual camera control
        if (cesiumViewRef.current) {
            console.log("[PlateauCesiumPickerReact] Flying to city:", currentCity);
            cesiumViewRef.current.flyToCity(cityConfig, 2.0);
        }

        // Loading will be cleared when tileset loads
    }, [currentCity, setSelectedBuildings, setLoading, setLoadingMessage]);

    // Setup click handler when viewer is ready
    useEffect(() => {
        if (!viewerReady || !buildingPickerRef.current) return;

        const viewer = cesiumViewRef.current?.getViewer();
        if (!viewer) return;

        const picker = buildingPickerRef.current;

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

    // Initialize CesiumView when container is ready
    useEffect(() => {
        if (!containerRef.current) return;

        console.log("[PlateauCesiumPickerReact] Initializing CesiumView");

        // Create and initialize CesiumView
        const cesiumView = new CesiumView(containerRef.current);
        cesiumView.initialize();
        cesiumViewRef.current = cesiumView;

        // Get viewer instance for building picker
        const viewer = cesiumView.getViewer();
        if (!viewer) {
            console.error("[PlateauCesiumPickerReact] Failed to get viewer from CesiumView");
            return;
        }

        // Initialize building picker
        buildingPickerRef.current = new CesiumBuildingPicker(viewer);
        setViewerReady(true);

        console.log("[PlateauCesiumPickerReact] CesiumView initialized successfully");

        // Cleanup on unmount
        return () => {
            console.log("[PlateauCesiumPickerReact] Disposing CesiumView");
            buildingPickerRef.current = null;
            cesiumViewRef.current?.dispose();
            cesiumViewRef.current = null;
            setViewerReady(false);
        };
    }, []); // Run once on mount

    // Load 3D Tiles tileset when URL changes
    useEffect(() => {
        if (!viewerReady || !tilesetUrl) return;

        const viewer = cesiumViewRef.current?.getViewer();
        if (!viewer) return;

        console.log("[PlateauCesiumPickerReact] Loading tileset:", tilesetUrl);

        // Remove existing tileset if any
        if (viewer.scene.primitives.length > 0) {
            viewer.scene.primitives.removeAll();
        }

        // Add new tileset using fromUrl (async)
        Cesium.Cesium3DTileset.fromUrl(tilesetUrl, {
            skipLevelOfDetail: false,
            maximumScreenSpaceError: 16,
        })
            .then((tileset) => {
                // Add to scene
                viewer.scene.primitives.add(tileset);
                tilesetRef.current = tileset;

                // Apply style
                tileset.style = new Cesium.Cesium3DTileStyle({
                    color: {
                        conditions: [
                            ["${feature_type} === 'bldg:Building'", "color('white', 0.9)"],
                            ["true", "color('lightgray', 0.8)"],
                        ],
                    },
                    show: "${feature_type} === 'bldg:Building'",
                });

                console.log("[PlateauCesiumPickerReact] Tileset loaded successfully");
                setLoading(false);
                setLoadingMessage("");
            })
            .catch((error: Error) => {
                console.error("[PlateauCesiumPickerReact] Failed to load tileset:", error);
                // Note: Toast notification removed due to missing i18n key
                setLoading(false);
                setLoadingMessage("");
            });

        // Cleanup on tileset change
        return () => {
            const currentTileset = tilesetRef.current;
            if (currentTileset && viewer.scene.primitives.contains(currentTileset)) {
                viewer.scene.primitives.remove(currentTileset);
                tilesetRef.current = null;
            }
        };
    }, [viewerReady, tilesetUrl, setLoading, setLoadingMessage]);

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
                    {/* Map container for CesiumView (Web Components) */}
                    <div
                        ref={containerRef}
                        style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            overflow: "hidden",
                        }}
                    />
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
