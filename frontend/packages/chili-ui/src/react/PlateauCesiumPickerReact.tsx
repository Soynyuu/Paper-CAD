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
    displayName: string;
    latitude: number;
    longitude: number;
    targetLatitude?: number;
    targetLongitude?: number;
    municipalityCode?: string;
    osmType?: string;
    osmId?: number;
    buildingCount?: number; // NEW: 周辺の建物件数
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
    const tilesetLoaderRef = useRef<CesiumTilesetLoader | null>(null);

    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [viewerReady, setViewerReady] = useState(false);

    // Search state
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState<boolean>(false);
    const [searchError, setSearchError] = useState<string | null>(null);
    const [showResults, setShowResults] = useState<boolean>(false);

    // Debug: monitor component mount/unmount
    useEffect(() => {
        console.log("[Debug] Component MOUNTED");
        return () => console.log("[Debug] Component UNMOUNTED");
    }, []);

    // Debug: monitor searchQuery changes
    useEffect(() => {
        console.log("[Debug] searchQuery changed to:", searchQuery);
    }, [searchQuery]);

    // Debug: monitor showResults changes
    useEffect(() => {
        console.log("[Debug] showResults changed to:", showResults, "searchResults:", searchResults);
    }, [showResults, searchResults]);
    const [selectedResultIndex, setSelectedResultIndex] = useState<number>(-1);
    const abortControllerRef = useRef<AbortController | null>(null);
    const searchContainerRef = useRef<HTMLDivElement | null>(null);
    const searchInputRef = useRef<HTMLInputElement | null>(null);

    // Search mode state
    const [searchMode, setSearchMode] = useState<"facility" | "address" | "buildingId">("facility");
    const [searchRadius, setSearchRadius] = useState<number>(100); // meters
    const [meshCode, setMeshCode] = useState<string>("");

    // UI state for Google-style progressive disclosure
    const [isExpanded, setIsExpanded] = useState<boolean>(false);
    const isComposingRef = useRef<boolean>(false);
    const preferredPickLod = Math.min(3, Math.max(1, Number(getRuntimeAppConfig()?.cesiumPickLod ?? 2)));

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
            await cesiumView.initialize("plateau-ortho-2023", {
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
            resizeObserver?.disconnect();
            handlerRef.current?.destroy();
            handlerRef.current = null;
            buildingPickerRef.current = null;
            tilesetLoaderRef.current = null;
            cesiumViewRef.current?.dispose();
            cesiumViewRef.current = null;
            setViewerReady(false);
        };
    }, []);

    // Tileset loading removed - using mesh-based dynamic loading (Issue #177)

    // Close search results and collapse when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
                setShowResults(false);
                if (!searchQuery.trim()) {
                    setIsExpanded(false);
                }
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [searchQuery]);

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

    // Constants for coordinate conversion
    const METERS_PER_DEGREE = 111000; // Approximate meters per degree at equator (OK for small ranges)
    const DEFAULT_TOKYO_LAT = 35.681236; // Tokyo Station latitude
    const DEFAULT_TOKYO_LON = 139.767125; // Tokyo Station longitude
    const MUNICIPALITY_CODE_PATTERN = /^(\d{5})/;

    const getMunicipalityCodeFromBuildingId = (buildingId?: string | null) => {
        if (!buildingId) return undefined;
        const match = buildingId.match(MUNICIPALITY_CODE_PATTERN);
        return match?.[1];
    };

    // Search handlers
    const performSearch = useCallback(async () => {
        console.log("[Search] performSearch called, searchQuery:", searchQuery);
        const query = searchQuery.trim();
        if (!query) {
            console.log("[Search] Empty query, returning");
            return;
        }

        // GML IDモードの場合、メッシュコードもチェック
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

            // 検索モードに応じてエンドポイント切り替え
            const endpoint =
                searchMode === "buildingId"
                    ? `/plateau/search-by-id-and-mesh`
                    : `/plateau/search-by-address`;

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
                          radius: searchRadius / METERS_PER_DEGREE, // Convert meters to degrees
                          limit: 20,
                          search_mode: searchMode === "facility" ? "hybrid" : "distance",
                          name_filter: searchMode === "facility" ? query : undefined,
                      };

            console.log("[Search] Fetching:", `${apiBaseUrl}${endpoint}`, requestBody);
            const response = await fetch(`${apiBaseUrl}${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                signal: abortControllerRef.current.signal,
            });

            console.log("[Search] Response status:", response.status);

            // Check HTTP status
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log("[Search] Response data:", JSON.stringify(data, null, 2));

            if (!data.success) {
                setSearchError(
                    data.error || I18n.translate("error.plateau.searchFailed:{0}", "Unknown error"),
                );
                setSearchResults([]);
                setShowResults(true);
                return;
            }

            // 検索結果を統一フォーマットに変換
            let result: SearchResult;

            if (searchMode === "buildingId") {
                // GML ID検索の場合
                if (!data.building) {
                    setSearchError(I18n.translate("error.plateau.noBuildingsFound:{0}", query));
                    setSearchResults([]);
                    setShowResults(true);
                    return;
                }
                const municipalityCode = getMunicipalityCodeFromBuildingId(data.building.building_id);
                result = {
                    displayName: data.building.name || data.building.gml_id,
                    latitude: data.building.latitude || DEFAULT_TOKYO_LAT,
                    longitude: data.building.longitude || DEFAULT_TOKYO_LON,
                    targetLatitude: data.building.latitude,
                    targetLongitude: data.building.longitude,
                    municipalityCode,
                    buildingCount: 1,
                };
            } else {
                // 施設名/住所検索の場合
                if (!data.geocoding) {
                    setSearchError(I18n.translate("error.plateau.noBuildingsFound:{0}", query));
                    setSearchResults([]);
                    setShowResults(true);
                    return;
                }
                const primaryBuilding = data.buildings?.[0];
                const municipalityCode = getMunicipalityCodeFromBuildingId(primaryBuilding?.building_id);
                result = {
                    displayName: data.geocoding.display_name,
                    latitude: data.geocoding.latitude,
                    longitude: data.geocoding.longitude,
                    targetLatitude: primaryBuilding?.latitude,
                    targetLongitude: primaryBuilding?.longitude,
                    municipalityCode,
                    osmType: data.geocoding.osm_type,
                    osmId: data.geocoding.osm_id,
                    buildingCount: data.buildings ? data.buildings.length : 0,
                };
            }

            console.log("[Search] Setting result:", result);
            setSearchResults([result]);
            setShowResults(true);
            setSelectedResultIndex(0);
            console.log("[Search] Results set, showResults should be true now");
        } catch (error: unknown) {
            if (error instanceof Error && error.name === "AbortError") return;
            console.error("[PlateauCesiumPickerReact] Search failed:", error);
            const errorMsg = error instanceof Error ? error.message : "Unknown error";
            setSearchError(I18n.translate("error.plateau.searchFailed:{0}", errorMsg));
            setShowResults(true);
        } finally {
            setIsSearching(false);
        }
    }, [searchQuery, searchMode, searchRadius, meshCode]);

    // IME composition handlers for proper Japanese input support
    const handleCompositionStart = useCallback(() => {
        isComposingRef.current = true;
    }, []);

    const handleCompositionEnd = useCallback(() => {
        // Delay to ensure composition is fully complete
        setTimeout(() => {
            isComposingRef.current = false;
        }, 10);
    }, []);

    const handleSearchKeyDown = useCallback(
        (e: React.KeyboardEvent<HTMLInputElement>) => {
            // For Enter key, only check nativeEvent.isComposing to allow search after IME confirmation
            if (e.key === "Enter") {
                // If IME is actively composing (e.g., showing candidates), don't trigger search
                if (e.nativeEvent.isComposing) {
                    console.log("[KeyDown] Enter blocked - IME composing");
                    return;
                }
                console.log("[KeyDown] Enter pressed, calling performSearch");
                e.preventDefault();
                performSearch();
                return;
            }

            // For other keys, block during active IME composition
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
        [performSearch, searchQuery, showResults, searchResults.length],
    );

    const handleSearchFocus = useCallback(() => {
        setIsExpanded(true);
    }, []);

    const handleSearchClear = useCallback(() => {
        setSearchQuery("");
        setSearchResults([]);
        setShowResults(false);
        setSearchError(null);
        setSelectedResultIndex(-1);
        searchInputRef.current?.focus();
    }, []);

    // findNearestCity removed - using mesh-based dynamic loading (Issue #177)

    const handleResultClick = useCallback(
        async (result: SearchResult) => {
            const viewer = cesiumViewRef.current?.getViewer();
            const loader = tilesetLoaderRef.current;
            if (!viewer || !loader) return;

            const targetLatitude = result.targetLatitude ?? result.latitude;
            const targetLongitude = result.targetLongitude ?? result.longitude;
            const municipalityCode = result.municipalityCode;

            // 検索ドロップダウンを閉じる
            setShowResults(false);
            setSearchQuery(result.displayName);

            setLoading(true);
            setLoadingMessage("地図を準備中...");

            viewer.camera.setView({
                destination: Cesium.Cartesian3.fromDegrees(targetLongitude, targetLatitude, 1200),
            });
            viewer.scene.requestRender();

            const loadTilesets = async () => {
                setLoadingMessage("3D Tilesを読み込み中...");

                // Get API base URL
                const apiBaseUrl = getRuntimeAppConfig()?.stepUnfoldApiUrl || "http://localhost:8001/api";

                const fetchTilesetsForMeshes = async (meshCodes: string[]) => {
                    const requestBody: Record<string, unknown> = {
                        mesh_codes: meshCodes,
                        lod: preferredPickLod,
                    };
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

                // Start with center mesh only; fallback to neighbors if nothing is found.
                const centerMeshCodes = resolveMeshCodesFromCoordinates(
                    targetLatitude,
                    targetLongitude,
                    false,
                );
                console.log(
                    `[PlateauCesiumPicker] Loading 3D Tiles for ${centerMeshCodes.length} mesh codes`,
                );

                let data = await fetchTilesetsForMeshes(centerMeshCodes);
                let tilesets = data.tilesets || [];

                if (tilesets.length === 0) {
                    const neighborMeshCodes = resolveMeshCodesFromCoordinates(
                        targetLatitude,
                        targetLongitude,
                        true,
                    );
                    console.log(
                        `[PlateauCesiumPicker] No tilesets found for center mesh; retrying with ${neighborMeshCodes.length} meshes`,
                    );
                    data = await fetchTilesetsForMeshes(neighborMeshCodes);
                    tilesets = data.tilesets || [];
                }

                if (result.municipalityCode) {
                    const filtered = tilesets.filter(
                        (tileset: any) => tileset.municipality_code === result.municipalityCode,
                    );
                    if (filtered.length > 0) {
                        tilesets = filtered;
                    }
                }

                if (tilesets.length === 0) {
                    console.warn("[PlateauCesiumPicker] No 3D Tiles found for this area");
                    return;
                }

                const MAX_TILESETS_TO_LOAD = 6;
                const PRIMARY_TILESETS_TO_LOAD = 1;
                const BACKGROUND_BATCH_SIZE = 2;
                const tilesetsToLoad = tilesets.slice(0, MAX_TILESETS_TO_LOAD);
                const meshCodesToLoad = tilesetsToLoad.map((t: any) => t.mesh_code);
                loader.retainMeshes(meshCodesToLoad);
                const primaryTilesets = tilesetsToLoad.slice(0, PRIMARY_TILESETS_TO_LOAD);
                const backgroundTilesets = tilesetsToLoad.slice(PRIMARY_TILESETS_TO_LOAD);

                const primaryLoad = await loader.loadMultipleTilesets(
                    primaryTilesets.map((t: any) => ({
                        meshCode: t.mesh_code,
                        url: t.tileset_url,
                    })),
                );
                let failedMeshCount = primaryLoad.failedMeshes.length;

                if (cesiumViewRef.current) {
                    setLoadingMessage("地図タイルを読み込み中...");
                    await cesiumViewRef.current.activateBasemap(undefined, { includeTerrain: false });
                }

                if (backgroundTilesets.length > 0) {
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
                                batch.map((t: any) => ({
                                    meshCode: t.mesh_code,
                                    url: t.tileset_url,
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

                    void loadBackgroundTilesets().catch((error) => {
                        console.warn("[PlateauCesiumPicker] Background tileset load failed:", error);
                        if (failedMeshCount > 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.tilesetLoadFailed:{0}",
                                failedMeshCount,
                            );
                        }
                    });
                } else if (failedMeshCount > 0) {
                    PubSub.default.pub(
                        "showToast",
                        "toast.plateau.tilesetLoadFailed:{0}",
                        failedMeshCount,
                    );
                } else if (cesiumViewRef.current) {
                    void cesiumViewRef.current.activateBasemap(undefined, { includeTerrain: true });
                }

                console.log(`[PlateauCesiumPicker] Loaded ${primaryTilesets.length} tilesets first`);

                // ユーザーに建物選択を促す（カメラ移動完了後）
                if (result.buildingCount && result.buildingCount > 0) {
                    console.log(
                        `[PlateauCesiumPicker] 周辺に${result.buildingCount}件の建物があります。3D地図上でクリックして選択してください。`,
                    );
                }
            };

            void loadTilesets()
                .catch((error) => {
                    console.error("[PlateauCesiumPicker] Failed to load 3D Tiles:", error);
                })
                .finally(() => {
                    setLoading(false);
                    setLoadingMessage("");
                });
        },
        [setLoading, setLoadingMessage],
    );

    return (
        <div className={styles.dialog} onKeyDown={handleDialogKeyDown}>
            <div className={styles.body}>
                {/* Map area */}
                <div className={styles.mapContainer}>
                    {/* Cesium container */}
                    <div className={styles.cesiumContainer}>
                        <div
                            ref={containerRef}
                            id="plateau-cesium-host"
                            style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
                        />
                    </div>

                    {/* Close button */}
                    <button className={styles.closeButton} onClick={handleClose} aria-label="閉じる">
                        <svg viewBox="0 0 24 24" fill="none">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>

                    {/* Search box */}
                    <div ref={searchContainerRef} className={styles.searchContainer}>
                        <div className={`${styles.searchBox} ${isExpanded ? styles.expanded : ""}`}>
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
                                {isSearching && <div className={styles.searchSpinner} />}
                                {!isSearching && searchQuery && (
                                    <button
                                        className={styles.searchClearButton}
                                        onClick={handleSearchClear}
                                        onMouseDown={(e) => e.preventDefault()}
                                        type="button"
                                    >
                                        <svg
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                        >
                                            <path d="M18 6L6 18M6 6l12 12" />
                                        </svg>
                                    </button>
                                )}
                            </div>

                            <div className={`${styles.searchModes} ${isExpanded ? styles.visible : ""}`}>
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

                            {isExpanded && searchMode === "buildingId" && (
                                <div
                                    className={styles.meshCodeSection}
                                    style={{ opacity: 1, maxHeight: 60, padding: "0 16px 12px" }}
                                >
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
                                    searchResults.map((result, index) => (
                                        <div
                                            key={`${result.osmType}-${result.osmId}-${index}`}
                                            className={`${styles.searchResultItem} ${
                                                index === selectedResultIndex ? styles.selected : ""
                                            }`}
                                            onClick={() => handleResultClick(result)}
                                            role="option"
                                            aria-selected={index === selectedResultIndex}
                                        >
                                            <div className={styles.locationName}>{result.displayName}</div>
                                            {result.buildingCount !== undefined &&
                                                result.buildingCount > 0 && (
                                                    <div className={styles.buildingCount}>
                                                        {result.buildingCount}件の建物
                                                    </div>
                                                )}
                                        </div>
                                    ))
                                )}
                            </div>

                            {isExpanded && !showResults && !searchQuery && (
                                <div className={styles.searchHint}>Enter で検索</div>
                            )}
                        </div>
                    </div>

                    <Instructions />
                    {loading && <Loading message={loadingMessage} />}
                </div>

                {/* Sidebar */}
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
