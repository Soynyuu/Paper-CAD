// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState } from "react";
import { useAtom } from "jotai";
import { CoreVisualizer, useVisualizer } from "@reearth/core";
import type { Layer, Camera, ComputedFeature } from "@reearth/core";
import { DialogResult, I18n, PubSub } from "chili-core";
import type { PickedBuilding } from "chili-cesium";
import { getAllCities, getCityConfig } from "chili-cesium";
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

export interface PlateauCesiumPickerReactProps {
    onClose: (result: DialogResult, data?: { selectedBuildings: PickedBuilding[] }) => void;
}

/**
 * PlateauCesiumPickerReactContent - Internal component with visualizer context
 *
 * Separated to use useVisualizer hook (must be inside CoreVisualizer context).
 */
function PlateauCesiumPickerReactContent({ onClose }: PlateauCesiumPickerReactProps) {
    const visualizer = useVisualizer();
    const [currentCity, setCurrentCity] = useAtom(currentCityAtom);
    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [camera, setCamera] = useState<Camera | undefined>();
    const [layers, setLayers] = useState<Layer[]>([]);
    const currentTilesetIdRef = useRef<string | null>(null);
    const selectedFeatureIdsRef = useRef<Set<string>>(new Set());

    // Initialize with first city
    useEffect(() => {
        const cities = getAllCities();
        if (cities.length > 0 && !currentCity) {
            setCurrentCity(cities[0].key);
        }
    }, [currentCity, setCurrentCity]);

    // Load city tileset when city changes
    useEffect(() => {
        if (!currentCity || !visualizer.current) return;

        const loadCityTileset = async () => {
            const cityConfig = getCityConfig(currentCity);
            if (!cityConfig) {
                PubSub.default.pub("showToast", "error.plateau.cityNotFound:{0}", currentCity);
                return;
            }

            try {
                setLoading(true);
                setLoadingMessage(I18n.translate("plateau.cesium.loading"));

                // Clear previous selections
                setSelectedBuildings([]);
                selectedFeatureIdsRef.current.clear();

                // Remove old tileset if exists
                if (currentTilesetIdRef.current && visualizer.current) {
                    visualizer.current.layers.deleteLayer(currentTilesetIdRef.current);
                }

                // Create new tileset layer
                const tilesetId = `plateau-tileset-${currentCity}`;
                const newLayer: Layer = {
                    type: "simple",
                    id: tilesetId,
                    title: cityConfig.name,
                    visible: true,
                    data: {
                        type: "3dtiles",
                        url: cityConfig.tilesetUrl,
                    },
                    "3dtiles": {
                        show: true,
                        color: "#ffffff",
                        selectedFeatureColor: "#ffeb3b",
                        shadows: "enabled",
                    },
                };

                if (!visualizer.current) {
                    throw new Error("Visualizer not initialized");
                }

                const addedLayer = visualizer.current.layers.add(newLayer);
                currentTilesetIdRef.current = tilesetId;

                // Update layers state
                setLayers([newLayer]);

                // Fly to city
                await visualizer.current.engine.flyTo(
                    {
                        lat: cityConfig.initialView.latitude,
                        lng: cityConfig.initialView.longitude,
                        height: cityConfig.initialView.height,
                        heading: 0,
                        pitch: -Math.PI / 4,
                        roll: 0,
                        fov: Math.PI / 3,
                    },
                    { duration: 2 },
                );

                setCamera({
                    lat: cityConfig.initialView.latitude,
                    lng: cityConfig.initialView.longitude,
                    height: cityConfig.initialView.height,
                    heading: 0,
                    pitch: -Math.PI / 4,
                    roll: 0,
                    fov: Math.PI / 3,
                });
            } catch (error) {
                console.error("[PlateauCesiumPickerReact] Failed to load city:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.cityLoadFailed:{0}:{1}",
                    cityConfig?.name || currentCity,
                    error instanceof Error ? error.message : String(error),
                );
            } finally {
                setLoading(false);
                setLoadingMessage("");
            }
        };

        loadCityTileset();
    }, [currentCity, visualizer, setSelectedBuildings, setLoading, setLoadingMessage]);

    // Handle layer selection (building picking)
    const handleLayerSelect = useCallback(
        async (
            layerId: string | undefined,
            layerGetter: (() => Promise<any>) | undefined,
            feature: ComputedFeature | undefined,
            reason: any,
        ) => {
            if (!feature || !layerId) return;

            // Get feature properties
            const properties = feature.properties || {};
            const featureType = properties.feature_type;
            const gmlId = properties["gml:id"] || properties.gmlid;

            // Only process building features
            if (featureType !== "bldg:Building" || !gmlId) return;

            // Check if Ctrl key was pressed (multi-select)
            const isMultiSelect = (reason as any)?.ctrlKey || false;

            // Toggle selection
            const isSelected = selectedFeatureIdsRef.current.has(gmlId);

            if (isSelected) {
                // Remove from selection
                selectedFeatureIdsRef.current.delete(gmlId);
                setSelectedBuildings((prev) => prev.filter((b) => b.gmlId !== gmlId));
            } else {
                // Add to selection
                if (!isMultiSelect) {
                    // Single select: clear previous
                    selectedFeatureIdsRef.current.clear();
                    setSelectedBuildings([]);
                }

                // Extract building data
                // Note: feature.geometry.coordinates type is complex (Position | Position[] | ...)
                // For Point geometry, it's [lng, lat, height] as Position type
                const coords = feature.geometry?.coordinates;
                const getCoordinate = (index: number): number => {
                    if (Array.isArray(coords) && typeof coords[index] === "number") {
                        return coords[index] as number;
                    }
                    return 0;
                };

                const pickedBuilding: PickedBuilding = {
                    gmlId,
                    meshCode: properties.meshcode || "",
                    position: {
                        latitude: getCoordinate(1),
                        longitude: getCoordinate(0),
                        height: getCoordinate(2),
                    },
                    properties: {
                        name: properties["gml:name"] || undefined,
                        usage: properties["bldg:usage"] || undefined,
                        measuredHeight: properties["bldg:measuredHeight"] || 0,
                        cityName: getCityConfig(currentCity)?.name || "",
                        meshcode: properties.meshcode || "",
                        featureType: "bldg:Building",
                    },
                };

                selectedFeatureIdsRef.current.add(gmlId);
                setSelectedBuildings((prev) => [...prev, pickedBuilding]);
            }
        },
        [currentCity, setSelectedBuildings],
    );

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
            selectedFeatureIdsRef.current.delete(gmlId);
            setSelectedBuildings((prev) => prev.filter((b) => b.gmlId !== gmlId));
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
        selectedFeatureIdsRef.current.clear();
        setSelectedBuildings([]);
    }, [setSelectedBuildings]);

    // Handle close
    const handleClose = useCallback(() => {
        onClose(DialogResult.cancel);
    }, [onClose]);

    return (
        <>
            <Header
                currentCity={currentCity}
                onCityChange={handleCityChange}
                onClose={handleClose}
                loading={loading}
            />
            <div className={styles.body}>
                <div className={styles.mapContainer}>
                    <CoreVisualizer
                        engine="cesium"
                        ready={true}
                        layers={layers}
                        camera={camera}
                        onLayerSelect={handleLayerSelect}
                        sceneProperty={{
                            tiles: [
                                {
                                    id: "default",
                                    tile_type: "default",
                                },
                            ],
                        }}
                        style={{ width: "100%", height: "100%" }}
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
        </>
    );
}

/**
 * PlateauCesiumPickerReact - React-based PLATEAU building picker using @reearth/core
 *
 * Main dialog component that provides visualizer context.
 */
export function PlateauCesiumPickerReact(props: PlateauCesiumPickerReactProps) {
    return (
        <div className={styles.dialog}>
            <PlateauCesiumPickerReactContent {...props} />
        </div>
    );
}
