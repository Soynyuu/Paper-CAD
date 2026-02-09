// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState } from "react";
import { useAtom } from "jotai";
import * as Cesium from "cesium";
import { DialogResult, I18n, PubSub } from "chili-core";
import {
    CesiumView,
    CesiumBuildingPicker,
    CesiumTilesetLoader,
    resolveMeshCodesFromCoordinates,
    type PickedBuilding,
} from "chili-cesium";
import { selectedBuildingsAtom, loadingAtom, loadingMessageAtom } from "./atoms/cesiumState";
import { Sidebar } from "./components/Sidebar";
import { Instructions } from "./components/Instructions";
import { Loading } from "./components/Loading";
import { PlateauSearchLoading } from "./components/PlateauSearchLoading";
import styles from "./PlateauCesiumPickerReact.module.css";

const CESIUM_WIDGET_CSS_ID = "cesium-widget-css";
const CESIUM_WIDGETS_CSS_PATH = "Widgets/widgets.css";

const getRuntimeAppConfig = (): Partial<AppConfig> | undefined => {
    if (typeof window === "undefined") {
        return undefined;
    }

    const runtime = window as any;
    if (runtime.__APP_CONFIG__) {
        return runtime.__APP_CONFIG__ as AppConfig;
    }

    if (typeof __APP_CONFIG__ !== "undefined") {
        return __APP_CONFIG__;
    }

    return undefined;
};

const clampResolutionScale = (value: number, fallback: number): number => {
    if (!Number.isFinite(value)) return fallback;
    return Math.min(Math.max(value, 0.5), 2);
};

const ensureCesiumRuntime = () => {
    if (typeof document === "undefined") {
        return;
    }

    const runtime = window;
    const appConfig = getRuntimeAppConfig();
    const rawBaseUrl = appConfig?.cesiumBaseUrl || "/cesium/";
    const baseUrl = rawBaseUrl.endsWith("/") ? rawBaseUrl : `${rawBaseUrl}/`;

    runtime.CESIUM_BASE_URL = baseUrl;

    const ionToken = appConfig?.cesiumIonToken;
    if (ionToken) {
        Cesium.Ion.defaultAccessToken = ionToken;
    }

    if (!document.getElementById(CESIUM_WIDGET_CSS_ID)) {
        const link = document.createElement("link");
        link.id = CESIUM_WIDGET_CSS_ID;
        link.rel = "stylesheet";
        link.href = `${baseUrl}${CESIUM_WIDGETS_CSS_PATH}`;
        document.head.appendChild(link);
        return;
    }

    const existing = document.getElementById(CESIUM_WIDGET_CSS_ID) as HTMLLinkElement | null;
    if (existing) {
        const href = `${baseUrl}${CESIUM_WIDGETS_CSS_PATH}`;
        const resolvedHref = new URL(href, window.location.href).href;
        if (existing.href !== resolvedHref) {
            existing.href = href;
        }
    }
};

ensureCesiumRuntime();

export interface PlateauCesiumPickerReactProps {
    onClose: (result: DialogResult, data?: { selectedBuildings: PickedBuilding[] }) => void;
}

interface SearchResult {
    id: string;
    displayName: string;
    latitude: number;
    longitude: number;
    gmlId?: string;
    buildingId?: string;
    distanceMeters?: number;
    municipalityCode?: string;
    osmType?: string;
    osmId?: number;
    usage?: string;
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
    const handlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);
    const buildingPickerRef = useRef<CesiumBuildingPicker | null>(null);
    const tilesetLoaderRef = useRef<CesiumTilesetLoader | null>(null);
    const perfDefaultsRef = useRef<{ resolutionScale: number; globeMaxSSE: number | null } | null>(null);

    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [viewerReady, setViewerReady] = useState(false);
    const [pickerStage, setPickerStage] = useState<"search" | "map">("search");
    const [pendingResult, setPendingResult] = useState<SearchResult | null>(null);
    const [activeResultId, setActiveResultId] = useState<string | null>(null);

    // Search state
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState<boolean>(false);
    const [searchError, setSearchError] = useState<string | null>(null);
    const [showResults, setShowResults] = useState<boolean>(false);

    const [selectedResultIndex, setSelectedResultIndex] = useState<number>(-1);
    const abortControllerRef = useRef<AbortController | null>(null);
    const searchContainerRef = useRef<HTMLDivElement | null>(null);
    const searchInputRef = useRef<HTMLInputElement | null>(null);
    const focusRequestIdRef = useRef(0);

    // Search mode state
    const [searchMode, setSearchMode] = useState<"facility" | "address" | "buildingId">("facility");
    const [searchRadius, setSearchRadius] = useState<number>(100); // meters
    const [meshCode, setMeshCode] = useState<string>("");

    // UI state for Google-style progressive disclosure
    const [isExpanded, setIsExpanded] = useState<boolean>(false);
    const isComposingRef = useRef<boolean>(false);
    const isSearchStage = pickerStage === "search";
    const showExpandedSearch = isSearchStage || isExpanded;
    const appConfig = getRuntimeAppConfig();
    const preferredPickLod = Math.min(3, Math.max(1, Number(appConfig?.cesiumPickLod ?? 2)));
    const preferredResolutionScale = clampResolutionScale(appConfig?.cesiumResolutionScale ?? 0.6, 0.6);
    const preferNoTexture = Boolean(appConfig?.cesiumPreferNoTexture);

    const applyPerformanceMode = (viewer: Cesium.Viewer) => {
        if (!perfDefaultsRef.current) {
            perfDefaultsRef.current = {
                resolutionScale: viewer.resolutionScale ?? preferredResolutionScale,
                globeMaxSSE: viewer.scene?.globe?.maximumScreenSpaceError ?? null,
            };
        }

        viewer.resolutionScale = Math.min(
            viewer.resolutionScale ?? preferredResolutionScale,
            preferredResolutionScale,
        );
        if (viewer.scene?.globe) {
            const current = viewer.scene.globe.maximumScreenSpaceError;
            viewer.scene.globe.maximumScreenSpaceError = Math.max(current, 8);
        }
    };

    const restorePerformanceMode = (viewer: Cesium.Viewer) => {
        const defaults = perfDefaultsRef.current;
        if (!defaults) return;

        viewer.resolutionScale = defaults.resolutionScale;
        if (viewer.scene?.globe && defaults.globeMaxSSE !== null) {
            viewer.scene.globe.maximumScreenSpaceError = defaults.globeMaxSSE;
        }
        perfDefaultsRef.current = null;
        viewer.scene?.requestRender();
    };

    // City initialization removed - using unified search interface (Issue #177)

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

            // Check for CTRL modifier safely
            const clickWithModifier = click as Cesium.ScreenSpaceEventHandler.PositionedEvent & {
                modifier?: Cesium.KeyboardEventModifier;
            };
            const isMultiSelect = clickWithModifier.modifier === Cesium.KeyboardEventModifier.CTRL;

            try {
                const picked = picker.pickBuilding(
                    { x: click.position.x, y: click.position.y },
                    isMultiSelect,
                );
                setSelectedBuildings(picker.getSelectedBuildings());
                if (picked?.gmlId) {
                    const resultIndex = searchResults.findIndex(
                        (result) => result.gmlId === picked.gmlId || result.buildingId === picked.gmlId,
                    );
                    if (resultIndex >= 0) {
                        setSelectedResultIndex(resultIndex);
                        setActiveResultId(searchResults[resultIndex].id);
                    }
                }
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
    }, [searchResults, setSelectedBuildings, viewerReady]);

    // Initialize CesiumView when container is ready
    useEffect(() => {
        if (pickerStage !== "map" || !containerRef.current) return;

        const container = containerRef.current;
        let mounted = true;
        let resizeObserver: ResizeObserver | null = null;

        const initCesium = async () => {
            // Wait for container size to be determined before initializing Cesium
            // This prevents canvas height: 0 issue caused by initializing before layout is complete
            await new Promise<void>((resolve) => {
                const checkSize = () => {
                    const rect = container.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        resolve();
                    } else {
                        requestAnimationFrame(checkSize);
                    }
                };
                checkSize();
            });

            if (!mounted) return;

            // Create and initialize CesiumView
            const cesiumView = new CesiumView(container);
            await cesiumView.initialize("gsi-pale", {
                deferBasemap: true,
                deferTerrain: true,
            });
            cesiumViewRef.current = cesiumView;

            const viewer = cesiumView.getViewer();
            if (!viewer || !mounted) return;

            const resizeViewer = () => {
                if (viewer.isDestroyed()) return;
                viewer.resize();
                viewer.scene?.requestRender();
            };

            // Force resize after initialization (and again after layout settles)
            resizeViewer();
            requestAnimationFrame(() => resizeViewer());
            requestAnimationFrame(() => requestAnimationFrame(() => resizeViewer()));

            // Initialize building picker and tileset loader
            buildingPickerRef.current = new CesiumBuildingPicker(viewer);
            tilesetLoaderRef.current = new CesiumTilesetLoader(viewer);

            // Watch for container resize
            resizeObserver = new ResizeObserver(() => {
                resizeViewer();
            });
            resizeObserver.observe(container);

            if (mounted) setViewerReady(true);
        };

        initCesium();

        return () => {
            mounted = false;
            focusRequestIdRef.current += 1;
            resizeObserver?.disconnect();
            handlerRef.current?.destroy();
            handlerRef.current = null;
            buildingPickerRef.current?.clearPreviewHighlight();
            buildingPickerRef.current = null;
            tilesetLoaderRef.current = null;
            cesiumViewRef.current?.dispose();
            cesiumViewRef.current = null;
            setViewerReady(false);
        };
    }, [pickerStage]);

    // Tileset loading removed - using mesh-based dynamic loading (Issue #177)

    // Close search results and collapse when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (
                isSearchStage &&
                searchContainerRef.current &&
                !searchContainerRef.current.contains(e.target as Node)
            ) {
                setShowResults(false);
                if (!searchQuery.trim()) {
                    setIsExpanded(false);
                }
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [isSearchStage, searchQuery]);

    // handleCityChange removed - using mesh-based dynamic loading (Issue #177)

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

    const handleDialogKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLDivElement>) => {
            e.stopPropagation();
            if (e.key === "Escape") {
                e.preventDefault();
                handleClose();
            }
        },
        [handleClose],
    );

    const METERS_PER_DEGREE = 111000;
    const DEFAULT_TOKYO_LAT = 35.681236;
    const DEFAULT_TOKYO_LON = 139.767125;
    const MUNICIPALITY_CODE_PATTERN = /^(\d{5})/;
    const getMunicipalityCodeFromBuildingId = (buildingId?: string | null) => {
        if (!buildingId) return undefined;
        const match = buildingId.match(MUNICIPALITY_CODE_PATTERN);
        return match?.[1];
    };

    const toNumberOrUndefined = (value: unknown): number | undefined => {
        const numeric = typeof value === "number" ? value : Number(value);
        return Number.isFinite(numeric) ? numeric : undefined;
    };

    useEffect(() => {
        if (pickerStage === "map") return;
        buildingPickerRef.current?.clearPreviewHighlight();
    }, [pickerStage]);

    const loadTilesetsForResult = useCallback(
        async (result: SearchResult) => {
            const viewer = cesiumViewRef.current?.getViewer();
            const loader = tilesetLoaderRef.current;
            if (!viewer || !loader) return;

            const targetLatitude = result.latitude;
            const targetLongitude = result.longitude;
            const municipalityCode = result.municipalityCode;
            const centerMeshCodes = resolveMeshCodesFromCoordinates(targetLatitude, targetLongitude, false);
            const loadedMeshCodes = new Set(loader.getLoadedMeshCodes());
            const hasCenterMeshLoaded = centerMeshCodes.some((meshCode) => loadedMeshCodes.has(meshCode));

            if (hasCenterMeshLoaded) {
                viewer.scene.requestRender();
                return;
            }

            setLoading(true);
            setLoadingMessage("3D Tilesを読み込み中...");
            applyPerformanceMode(viewer);
            let restoreOnFinish = true;

            try {
                const apiBaseUrl = getRuntimeAppConfig()?.stepUnfoldApiUrl || "http://localhost:8001/api";
                const fetchTilesetsForMeshes = async (meshCodes: string[]) => {
                    const requestBody: Record<string, unknown> = {
                        mesh_codes: meshCodes,
                        lod: preferredPickLod,
                    };
                    if (preferNoTexture) {
                        requestBody["prefer_no_texture"] = true;
                    }
                    if (municipalityCode) {
                        requestBody["municipality_code"] = municipalityCode;
                    }

                    const response = await fetch(`${apiBaseUrl}/plateau/mesh-to-tilesets`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(requestBody),
                    });

                    if (!response.ok) {
                        throw new Error(`API error: ${response.status}`);
                    }

                    return response.json();
                };

                let data = await fetchTilesetsForMeshes(centerMeshCodes);
                let tilesets = data.tilesets || [];

                if (tilesets.length === 0) {
                    const neighborMeshCodes = resolveMeshCodesFromCoordinates(
                        targetLatitude,
                        targetLongitude,
                        true,
                    );
                    data = await fetchTilesetsForMeshes(neighborMeshCodes);
                    tilesets = data.tilesets || [];
                }

                if (municipalityCode) {
                    const filtered = tilesets.filter(
                        (tileset: any) => tileset.municipality_code === municipalityCode,
                    );
                    if (filtered.length > 0) {
                        tilesets = filtered;
                    }
                }

                if (tilesets.length === 0) {
                    console.warn("[PlateauCesiumPicker] No 3D Tiles found for this area");
                    return;
                }

                const MAX_TILESETS_TO_LOAD = 2;
                const PRIMARY_TILESETS_TO_LOAD = 1;
                const BACKGROUND_BATCH_SIZE = 1;
                const tilesetsToLoad = tilesets.slice(0, MAX_TILESETS_TO_LOAD);
                const meshCodesToLoad = tilesetsToLoad.map((tileset: any) => tileset.mesh_code);
                const primaryTilesets = tilesetsToLoad.slice(0, PRIMARY_TILESETS_TO_LOAD);
                const backgroundTilesets = tilesetsToLoad.slice(PRIMARY_TILESETS_TO_LOAD);

                loader.retainMeshes(meshCodesToLoad);

                const primaryLoad = await loader.loadMultipleTilesets(
                    primaryTilesets.map((tileset: any) => ({
                        meshCode: tileset.mesh_code,
                        url: tileset.tileset_url,
                    })),
                );
                let failedMeshCount = primaryLoad.failedMeshes.length;

                if (cesiumViewRef.current) {
                    setLoadingMessage("地図タイルを読み込み中...");
                    await cesiumViewRef.current.activateBasemap(undefined, { includeTerrain: false });
                }

                if (backgroundTilesets.length > 0) {
                    restoreOnFinish = false;
                    const yieldToBrowser = () =>
                        new Promise<void>((resolve) => {
                            if (typeof requestAnimationFrame === "function") {
                                requestAnimationFrame(() => resolve());
                            } else {
                                setTimeout(resolve, 0);
                            }
                        });

                    const loadBackgroundTilesets = async () => {
                        for (let i = 0; i < backgroundTilesets.length; i += BACKGROUND_BATCH_SIZE) {
                            const batch = backgroundTilesets.slice(i, i + BACKGROUND_BATCH_SIZE);
                            const loadResult = await loader.loadMultipleTilesets(
                                batch.map((tileset: any) => ({
                                    meshCode: tileset.mesh_code,
                                    url: tileset.tileset_url,
                                })),
                            );
                            failedMeshCount += loadResult.failedMeshes.length;
                            await yieldToBrowser();
                        }

                        if (failedMeshCount > 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.tilesetLoadFailed:{0}",
                                failedMeshCount,
                            );
                        }

                        if (cesiumViewRef.current) {
                            void cesiumViewRef.current.activateBasemap(undefined, { includeTerrain: true });
                        }
                    };

                    void loadBackgroundTilesets()
                        .catch((error) => {
                            console.warn("[PlateauCesiumPicker] Background tileset load failed:", error);
                            if (failedMeshCount > 0) {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.tilesetLoadFailed:{0}",
                                    failedMeshCount,
                                );
                            }
                        })
                        .finally(() => {
                            restorePerformanceMode(viewer);
                        });
                } else {
                    if (failedMeshCount > 0) {
                        PubSub.default.pub(
                            "showToast",
                            "toast.plateau.tilesetLoadFailed:{0}",
                            failedMeshCount,
                        );
                    }
                    if (cesiumViewRef.current) {
                        void cesiumViewRef.current.activateBasemap(undefined, { includeTerrain: true });
                    }
                }
            } finally {
                if (restoreOnFinish) {
                    restorePerformanceMode(viewer);
                }
                setLoading(false);
                setLoadingMessage("");
            }
        },
        [preferNoTexture, preferredPickLod, setLoading, setLoadingMessage],
    );

    const focusResultOnMap = useCallback(
        async (result: SearchResult) => {
            const viewer = cesiumViewRef.current?.getViewer();
            if (!viewer) return;

            const requestId = ++focusRequestIdRef.current;
            const index = searchResults.findIndex((candidate) => candidate.id === result.id);
            if (index >= 0) {
                setSelectedResultIndex(index);
            }
            setActiveResultId(result.id);

            await new Promise<void>((resolve) => {
                viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromDegrees(result.longitude, result.latitude, 420),
                    duration: 1.2,
                    complete: () => resolve(),
                    cancel: () => resolve(),
                });
            });
            viewer.scene.requestRender();

            if (focusRequestIdRef.current !== requestId) return;
            await loadTilesetsForResult(result);
            if (focusRequestIdRef.current !== requestId) return;

            const picker = buildingPickerRef.current;
            if (!picker) return;

            const attemptPreviewHighlight = () => {
                const targets = [result.gmlId, result.buildingId].filter(
                    (value): value is string => typeof value === "string" && value.length > 0,
                );
                const center = {
                    x: Math.floor(viewer.canvas.clientWidth / 2),
                    y: Math.floor(viewer.canvas.clientHeight / 2),
                };

                for (const target of targets) {
                    if (
                        picker.previewBuildingAtCoordinates(result.longitude, result.latitude, target) ||
                        picker.previewBuildingAtScreen(center, target)
                    ) {
                        return true;
                    }
                }

                return (
                    picker.previewBuildingAtCoordinates(result.longitude, result.latitude) ||
                    picker.previewBuildingAtScreen(center)
                );
            };

            if (attemptPreviewHighlight()) return;

            let retries = 0;
            const MAX_RETRIES = 40;
            const RETRY_INTERVAL_MS = 150;
            const retryPreview = () => {
                if (focusRequestIdRef.current !== requestId) return;
                if (viewer.isDestroyed()) return;
                viewer.scene.requestRender();
                retries += 1;
                if (attemptPreviewHighlight() || retries >= MAX_RETRIES) {
                    if (retries >= MAX_RETRIES) {
                        console.warn(
                            "[PlateauCesiumPicker] Search result highlight timed out",
                            result.gmlId || result.buildingId || result.id,
                        );
                    }
                    return;
                }
                window.setTimeout(retryPreview, RETRY_INTERVAL_MS);
            };
            window.setTimeout(retryPreview, RETRY_INTERVAL_MS);
        },
        [loadTilesetsForResult, searchResults],
    );

    const activateSearchResult = useCallback(
        (result: SearchResult) => {
            setShowResults(true);
            if (pickerStage !== "map") {
                setPickerStage("map");
                setPendingResult(result);
                setIsExpanded(false);
                return;
            }

            if (!viewerReady) {
                setPendingResult(result);
                return;
            }

            void focusResultOnMap(result);
        },
        [focusResultOnMap, pickerStage, viewerReady],
    );

    const performSearch = useCallback(async () => {
        const query = searchQuery.trim();
        if (!query) return;

        if (searchMode === "buildingId" && !meshCode.trim()) {
            setSearchError(
                I18n.translate("error.plateau.emptyMeshCode") || "メッシュコードを入力してください",
            );
            setShowResults(true);
            return;
        }

        setIsSearching(true);
        setSearchError(null);
        setShowResults(false);

        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            const apiBaseUrl = getRuntimeAppConfig()?.stepUnfoldApiUrl || "http://localhost:8001/api";
            const endpoint =
                searchMode === "buildingId"
                    ? "/plateau/search-by-id-and-mesh"
                    : "/plateau/search-by-address";
            const requestBody =
                searchMode === "buildingId"
                    ? {
                          building_id: query,
                          mesh_code: meshCode.trim(),
                          debug: false,
                          merge_building_parts: false,
                      }
                    : {
                          query,
                          radius: searchRadius / METERS_PER_DEGREE,
                          limit: 20,
                          search_mode: searchMode === "facility" ? "hybrid" : "distance",
                          name_filter: searchMode === "facility" ? query : undefined,
                      };

            const response = await fetch(`${apiBaseUrl}${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            if (!data.success) {
                setSearchError(
                    data.error || I18n.translate("error.plateau.searchFailed:{0}", "Unknown error"),
                );
                setSearchResults([]);
                setShowResults(true);
                setActiveResultId(null);
                return;
            }

            const results: SearchResult[] = [];
            if (searchMode === "buildingId") {
                if (!data.building) {
                    setSearchError(I18n.translate("error.plateau.noBuildingsFound:{0}", query));
                    setSearchResults([]);
                    setShowResults(true);
                    setActiveResultId(null);
                    return;
                }

                const building = data.building;
                const latitude = toNumberOrUndefined(building.latitude) ?? DEFAULT_TOKYO_LAT;
                const longitude = toNumberOrUndefined(building.longitude) ?? DEFAULT_TOKYO_LON;
                const gmlId =
                    typeof building.gml_id === "string"
                        ? building.gml_id
                        : typeof building.building_id === "string" &&
                            building.building_id.startsWith("bldg_")
                          ? building.building_id
                          : undefined;
                const buildingId =
                    typeof building.building_id === "string" ? building.building_id : undefined;

                results.push({
                    id: gmlId || buildingId || "single-result",
                    displayName: building.name || building.building_id || building.gml_id || query,
                    latitude,
                    longitude,
                    gmlId,
                    buildingId,
                    distanceMeters: toNumberOrUndefined(building.distance_meters),
                    municipalityCode: getMunicipalityCodeFromBuildingId(buildingId),
                    usage: building.usage,
                });
            } else {
                const buildings = Array.isArray(data.buildings) ? data.buildings : [];
                const geocoding = data.geocoding;

                buildings.forEach((building: any, index: number) => {
                    const latitude =
                        toNumberOrUndefined(building.latitude) ??
                        toNumberOrUndefined(geocoding?.latitude) ??
                        DEFAULT_TOKYO_LAT;
                    const longitude =
                        toNumberOrUndefined(building.longitude) ??
                        toNumberOrUndefined(geocoding?.longitude) ??
                        DEFAULT_TOKYO_LON;
                    const gmlId =
                        typeof building.gml_id === "string"
                            ? building.gml_id
                            : typeof building.building_id === "string" &&
                                building.building_id.startsWith("bldg_")
                              ? building.building_id
                              : undefined;
                    const buildingId =
                        typeof building.building_id === "string" ? building.building_id : undefined;
                    const resultId = gmlId || buildingId || `search-result-${index + 1}`;

                    results.push({
                        id: resultId,
                        displayName:
                            building.name || building.building_id || building.gml_id || `候補 ${index + 1}`,
                        latitude,
                        longitude,
                        gmlId,
                        buildingId,
                        distanceMeters: toNumberOrUndefined(building.distance_meters),
                        municipalityCode: getMunicipalityCodeFromBuildingId(buildingId),
                        usage: building.usage,
                        osmType: geocoding?.osm_type,
                        osmId: geocoding?.osm_id,
                    });
                });
            }

            if (results.length === 0) {
                setSearchError(I18n.translate("error.plateau.noBuildingsFound:{0}", query));
                setSearchResults([]);
                setShowResults(true);
                setActiveResultId(null);
                return;
            }

            setSearchResults(results);
            setSelectedResultIndex(0);
            setActiveResultId(results[0].id);
            setShowResults(true);
            setPendingResult(results[0]);
            if (pickerStage !== "map") {
                setPickerStage("map");
                setIsExpanded(false);
            }
        } catch (error: unknown) {
            if (error instanceof Error && error.name === "AbortError") return;
            const errorMsg = error instanceof Error ? error.message : "Unknown error";
            setSearchError(I18n.translate("error.plateau.searchFailed:{0}", errorMsg));
            setShowResults(true);
        } finally {
            setIsSearching(false);
        }
    }, [meshCode, pickerStage, searchMode, searchQuery, searchRadius]);

    const handleResultClick = useCallback(
        (result: SearchResult) => {
            activateSearchResult(result);
        },
        [activateSearchResult],
    );

    // IME composition handlers for proper Japanese input support
    const handleCompositionStart = useCallback(() => {
        isComposingRef.current = true;
    }, []);

    const handleCompositionEnd = useCallback(() => {
        setTimeout(() => {
            isComposingRef.current = false;
        }, 10);
    }, []);

    const handleSearchKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLInputElement>) => {
            if (e.key === "Enter") {
                if (e.nativeEvent.isComposing) {
                    return;
                }
                e.preventDefault();
                if (
                    !isSearchStage &&
                    showResults &&
                    selectedResultIndex >= 0 &&
                    searchResults[selectedResultIndex]
                ) {
                    activateSearchResult(searchResults[selectedResultIndex]);
                } else {
                    void performSearch();
                }
                return;
            }

            if (isComposingRef.current || e.nativeEvent.isComposing) {
                return;
            }

            switch (e.key) {
                case "Escape":
                    setShowResults(false);
                    setSearchError(null);
                    if (!searchQuery.trim()) {
                        setIsExpanded(false);
                        searchInputRef.current?.blur();
                    }
                    break;
                case "ArrowDown":
                    if (showResults && searchResults.length > 0) {
                        e.preventDefault();
                        setSelectedResultIndex((prev) =>
                            prev < searchResults.length - 1 ? prev + 1 : prev,
                        );
                    }
                    break;
                case "ArrowUp":
                    if (showResults && searchResults.length > 0) {
                        e.preventDefault();
                        setSelectedResultIndex((prev) => (prev > 0 ? prev - 1 : 0));
                    }
                    break;
            }
        },
        [
            activateSearchResult,
            isSearchStage,
            performSearch,
            searchQuery,
            searchResults,
            selectedResultIndex,
            showResults,
        ],
    );

    const handleSearchFocus = useCallback(() => {
        if (!isSearchStage) {
            setIsExpanded(true);
        }
    }, [isSearchStage]);

    const handleSearchClear = useCallback(() => {
        setSearchQuery("");
        setSearchResults([]);
        setShowResults(false);
        setSearchError(null);
        setSelectedResultIndex(-1);
        setActiveResultId(null);
        setPendingResult(null);
        buildingPickerRef.current?.clearPreviewHighlight();
        searchInputRef.current?.focus();
    }, []);

    const handleSearchSubmit = useCallback(() => {
        void performSearch();
    }, [performSearch]);

    useEffect(() => {
        if (!viewerReady || !pendingResult) return;
        const result = pendingResult;
        setPendingResult(null);
        void focusResultOnMap(result);
    }, [focusResultOnMap, pendingResult, viewerReady]);

    const handleBackToSearch = useCallback(() => {
        setPickerStage("search");
        setPendingResult(null);
        setIsExpanded(false);
        setShowResults(searchResults.length > 0);
        buildingPickerRef.current?.clearPreviewHighlight();
    }, [searchResults.length]);

    const renderSearchPanel = (variant: "dialog" | "floating") => {
        const isDialogPanel = variant === "dialog";
        const showDetails = isDialogPanel || showExpandedSearch;
        const containerClassName = `${isDialogPanel ? styles.searchDialogContainer : styles.searchContainer} ${
            isSearching ? styles.searchLoadingContainer : ""
        }`;

        if (isSearching) {
            return (
                <div ref={searchContainerRef} className={containerClassName}>
                    <PlateauSearchLoading minimal />
                </div>
            );
        }

        return (
            <div ref={searchContainerRef} className={containerClassName}>
                <div
                    className={`${styles.searchBox} ${showDetails ? styles.expanded : ""} ${
                        isDialogPanel ? styles.searchBoxDialog : styles.searchBoxFloating
                    }`}
                >
                    {isDialogPanel && (
                        <div className={styles.searchHeader}>
                            <div className={styles.searchEyebrow}>PLATEAU Building Import</div>
                            <div className={styles.searchTitle}>建物を検索</div>
                            <div className={styles.searchSubtitle}>
                                検索後は3D地図で結果を確認しながら候補をクリックできます。
                            </div>
                        </div>
                    )}

                    <div className={styles.searchInputWrapper}>
                        <span className={styles.searchIcon}>
                            <svg viewBox="0 0 24 24">
                                <circle cx="11" cy="11" r="7" />
                                <path d="M21 21l-4.35-4.35" />
                            </svg>
                        </span>
                        <input
                            ref={searchInputRef}
                            type="text"
                            className={styles.searchInput}
                            placeholder="場所や施設を検索"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onFocus={handleSearchFocus}
                            onKeyDown={handleSearchKeyDown}
                            onCompositionStart={handleCompositionStart}
                            onCompositionEnd={handleCompositionEnd}
                            disabled={isSearching}
                            autoComplete="off"
                        />
                        <button
                            className={styles.searchSubmitButton}
                            onClick={handleSearchSubmit}
                            disabled={isSearching || !searchQuery.trim()}
                            type="button"
                        >
                            検索
                        </button>
                        {isSearching && <div className={styles.searchSpinner} />}
                        {!isSearching && searchQuery && (
                            <button
                                className={styles.searchClearButton}
                                onClick={handleSearchClear}
                                onMouseDown={(e) => e.preventDefault()}
                                type="button"
                            >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M18 6L6 18M6 6l12 12" />
                                </svg>
                            </button>
                        )}
                    </div>

                    <div className={`${styles.searchModes} ${showDetails ? styles.visible : ""}`}>
                        <button
                            className={`${styles.searchModeChip} ${searchMode === "facility" ? styles.active : ""}`}
                            onClick={() => setSearchMode("facility")}
                        >
                            施設名
                        </button>
                        <button
                            className={`${styles.searchModeChip} ${searchMode === "address" ? styles.active : ""}`}
                            onClick={() => setSearchMode("address")}
                        >
                            住所
                        </button>
                        <button
                            className={`${styles.searchModeChip} ${searchMode === "buildingId" ? styles.active : ""}`}
                            onClick={() => setSearchMode("buildingId")}
                        >
                            建物ID
                        </button>
                    </div>

                    {showDetails && searchMode === "buildingId" && (
                        <div className={styles.meshCodeSection}>
                            <input
                                type="text"
                                className={styles.meshCodeInput}
                                placeholder="メッシュコード（例: 53394511）"
                                value={meshCode}
                                onChange={(e) => setMeshCode(e.target.value)}
                                disabled={isSearching}
                            />
                        </div>
                    )}

                    {showResults && <div className={styles.searchDivider} />}

                    <div
                        className={`${styles.searchResults} ${showResults ? styles.visible : ""}`}
                        role="listbox"
                    >
                        {searchError ? (
                            <div className={styles.searchError}>{searchError}</div>
                        ) : (
                            searchResults.map((result, index) =>
                                (() => {
                                    const isResultActive =
                                        index === selectedResultIndex || result.id === activeResultId;
                                    const isResultSelected = !!result.gmlId
                                        ? selectedBuildings.some(
                                              (building) => building.gmlId === result.gmlId,
                                          )
                                        : false;

                                    return (
                                        <div
                                            key={result.id}
                                            className={`${styles.searchResultItem} ${
                                                isResultActive ? styles.selected : ""
                                            }`}
                                            onClick={() => handleResultClick(result)}
                                            role="option"
                                            aria-selected={isResultActive}
                                        >
                                            <div className={styles.locationName}>{result.displayName}</div>
                                            <div className={styles.resultMetaRow}>
                                                {typeof result.distanceMeters === "number" && (
                                                    <span className={styles.resultMetaText}>
                                                        {Math.round(result.distanceMeters)}m
                                                    </span>
                                                )}
                                                {result.buildingId && (
                                                    <span className={styles.resultMetaText}>
                                                        {result.buildingId}
                                                    </span>
                                                )}
                                                {isResultSelected && (
                                                    <span className={styles.resultTag}>選択済み</span>
                                                )}
                                                {result.id === activeResultId && (
                                                    <span
                                                        className={`${styles.resultTag} ${styles.resultTagActive}`}
                                                    >
                                                        ハイライト中
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })(),
                            )
                        )}
                    </div>

                    {!showResults && !searchQuery && (
                        <div className={styles.searchHint}>
                            Enterで検索。結果をクリックすると地図でハイライト表示されます。
                        </div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className={styles.dialog} onKeyDown={handleDialogKeyDown}>
            {isSearchStage ? (
                <div className={styles.searchStage}>
                    <button
                        className={`${styles.closeButton} ${styles.searchStageCloseButton}`}
                        onClick={handleClose}
                        aria-label="閉じる"
                    >
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>
                    {renderSearchPanel("dialog")}
                </div>
            ) : (
                <div className={styles.body}>
                    <div className={styles.mapContainer}>
                        <div className={styles.cesiumContainer}>
                            <div
                                ref={containerRef}
                                id="plateau-cesium-host"
                                style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
                            />
                        </div>

                        <button className={styles.closeButton} onClick={handleClose} aria-label="閉じる">
                            <svg viewBox="0 0 24 24" fill="none">
                                <path d="M18 6L6 18M6 6l12 12" />
                            </svg>
                        </button>

                        <button className={styles.backButton} onClick={handleBackToSearch} type="button">
                            検索に戻る
                        </button>

                        {renderSearchPanel("floating")}

                        <Instructions />
                        {!viewerReady && <Loading message="地図ビューを準備中..." />}
                        {loading && <Loading message={loadingMessage} />}
                    </div>

                    <Sidebar
                        selectedBuildings={selectedBuildings}
                        onRemove={handleRemoveBuilding}
                        onImport={handleImport}
                        onClear={handleClear}
                    />
                </div>
            )}
        </div>
    );
}
