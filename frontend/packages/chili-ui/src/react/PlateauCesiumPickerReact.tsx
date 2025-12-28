// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState } from "react";
import { useAtom } from "jotai";
import { Viewer, Cesium3DTileset, CameraFlyTo } from "resium";
import * as Cesium from "cesium";
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
 * PlateauCesiumPickerReact - React-based PLATEAU building picker using resium
 *
 * Uses resium (React bindings for Cesium) instead of @reearth/core for better compatibility.
 */
export function PlateauCesiumPickerReact({ onClose }: PlateauCesiumPickerReactProps) {
    const viewerRef = useRef<Cesium.Viewer | null>(null);
    const tilesetRef = useRef<Cesium.Cesium3DTileset | null>(null);
    const handlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);
    const selectedFeatureIdsRef = useRef<Set<string>>(new Set());
    const selectedFeaturesRef = useRef<Map<string, any>>(new Map());

    const [currentCity, setCurrentCity] = useAtom(currentCityAtom);
    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [tilesetUrl, setTilesetUrl] = useState<string>("");
    const [cameraDestination, setCameraDestination] = useState<Cesium.Cartesian3 | undefined>();

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
        setSelectedBuildings([]);
        selectedFeatureIdsRef.current.clear();

        // Update tileset URL
        setTilesetUrl(cityConfig.tilesetUrl);

        // Set camera destination
        const destination = Cesium.Cartesian3.fromDegrees(
            cityConfig.initialView.longitude,
            cityConfig.initialView.latitude,
            cityConfig.initialView.height,
        );
        setCameraDestination(destination);

        // Loading will be cleared when tileset loads
    }, [currentCity, setSelectedBuildings, setLoading, setLoadingMessage]);

    // Setup click handler when viewer is ready
    useEffect(() => {
        const viewer = viewerRef.current;
        if (!viewer) return;

        // Clean up old handler
        if (handlerRef.current) {
            handlerRef.current.destroy();
        }

        // Create new handler
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
        handlerRef.current = handler;

        handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
            const pickedObject = viewer.scene.pick(click.position);
            if (!pickedObject || !pickedObject.content) return;

            const feature = pickedObject.content.getFeature(pickedObject.featureId);
            if (!feature) return;

            // Get feature properties
            const properties: Record<string, any> = {};
            const propertyIds = feature.getPropertyIds();
            propertyIds.forEach((id: string) => {
                properties[id] = feature.getProperty(id);
            });

            const featureType = properties["feature_type"];
            const gmlId = properties["gml:id"] || properties["gmlid"];

            // Only process building features
            if (featureType !== "bldg:Building" || !gmlId) return;

            // Check if Ctrl key was pressed (multi-select)
            const isMultiSelect =
                viewer.scene.screenSpaceCameraController.enableInputs &&
                (click as any).modifier === Cesium.KeyboardEventModifier.CTRL;

            // Toggle selection
            const isSelected = selectedFeatureIdsRef.current.has(gmlId);

            if (isSelected) {
                // Remove from selection
                selectedFeatureIdsRef.current.delete(gmlId);
                selectedFeaturesRef.current.delete(gmlId);
                setSelectedBuildings((prev) => prev.filter((b) => b.gmlId !== gmlId));
                feature.color = Cesium.Color.WHITE;
            } else {
                // Add to selection
                if (!isMultiSelect) {
                    // Single select: clear previous
                    selectedFeaturesRef.current.forEach((prevFeature) => {
                        prevFeature.color = Cesium.Color.WHITE;
                    });
                    selectedFeatureIdsRef.current.clear();
                    selectedFeaturesRef.current.clear();
                    setSelectedBuildings([]);
                }

                // Get building position from cartographic
                const cartographic = viewer.scene.globe.ellipsoid.cartesianToCartographic(
                    pickedObject.content.tile.boundingSphere.center,
                );

                const pickedBuilding: PickedBuilding = {
                    gmlId,
                    meshCode: properties["meshcode"] || "",
                    position: {
                        latitude: Cesium.Math.toDegrees(cartographic.latitude),
                        longitude: Cesium.Math.toDegrees(cartographic.longitude),
                        height: cartographic.height,
                    },
                    properties: {
                        name: properties["gml:name"] || undefined,
                        usage: properties["bldg:usage"] || undefined,
                        measuredHeight: properties["bldg:measuredHeight"] || 0,
                        cityName: getCityConfig(currentCity)?.name || "",
                        meshcode: properties["meshcode"] || "",
                        featureType: "bldg:Building",
                    },
                };

                selectedFeatureIdsRef.current.add(gmlId);
                selectedFeaturesRef.current.set(gmlId, feature);
                setSelectedBuildings((prev) => [...prev, pickedBuilding]);
                feature.color = Cesium.Color.YELLOW;
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        return () => {
            if (handlerRef.current) {
                handlerRef.current.destroy();
                handlerRef.current = null;
            }
        };
    }, [currentCity, setSelectedBuildings]);

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

            // Reset color using stored feature reference
            const feature = selectedFeaturesRef.current.get(gmlId);
            if (feature) {
                feature.color = Cesium.Color.WHITE;
            }
            selectedFeaturesRef.current.delete(gmlId);
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
        // Reset all colors using stored feature references
        selectedFeaturesRef.current.forEach((feature) => {
            feature.color = Cesium.Color.WHITE;
        });

        selectedFeatureIdsRef.current.clear();
        selectedFeaturesRef.current.clear();
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
            setLoading(false);
            setLoadingMessage("");
        },
        [setLoading, setLoadingMessage],
    );

    // Handle viewer ready
    const handleViewerReady = useCallback((ref: any) => {
        // resium refs contain the Cesium element in cesiumElement property
        if (ref && ref.cesiumElement) {
            viewerRef.current = ref.cesiumElement;
        }
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
                        baseLayerPicker={false}
                        geocoder={false}
                        homeButton={false}
                        navigationHelpButton={false}
                        sceneModePicker={false}
                        selectionIndicator={false}
                        infoBox={false}
                        style={{ width: "100%", height: "100%" }}
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
