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

    const runtime = window;
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

interface SearchResult {
    displayName: string;
    latitude: number;
    longitude: number;
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
    const [isComposing, setIsComposing] = useState<boolean>(false);

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

        console.log("[PlateauCesiumPickerReact] Initializing CesiumView");

        let mounted = true;

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

        // Initialize tileset loader
        tilesetLoaderRef.current = new CesiumTilesetLoader(viewer);

        if (mounted) {
            setViewerReady(true);
            console.log("[PlateauCesiumPickerReact] CesiumView initialized successfully");
        }

        // Cleanup on unmount
        return () => {
            mounted = false;
            console.log("[PlateauCesiumPickerReact] Disposing CesiumView");

            if (handlerRef.current) {
                handlerRef.current.destroy();
                handlerRef.current = null;
            }

            buildingPickerRef.current = null;
            tilesetLoaderRef.current = null;

            cesiumViewRef.current?.dispose();
            cesiumViewRef.current = null;

            setViewerReady(false);
        };
    }, []); // Run once on mount

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

    // Constants for coordinate conversion
    const METERS_PER_DEGREE = 111000; // Approximate meters per degree at equator (OK for small ranges)
    const DEFAULT_TOKYO_LAT = 35.681236; // Tokyo Station latitude
    const DEFAULT_TOKYO_LON = 139.767125; // Tokyo Station longitude

    // Search handlers
    const performSearch = useCallback(async () => {
        const query = searchQuery.trim();
        if (!query) return;

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
            const apiBaseUrl = window.__APP_CONFIG__?.stepUnfoldApiUrl || "http://localhost:8001/api";

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

            const response = await fetch(`${apiBaseUrl}${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                signal: abortControllerRef.current.signal,
            });

            // Check HTTP status
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
                result = {
                    displayName: data.building.name || data.building.gml_id,
                    latitude: data.building.latitude || DEFAULT_TOKYO_LAT,
                    longitude: data.building.longitude || DEFAULT_TOKYO_LON,
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
                result = {
                    displayName: data.geocoding.display_name,
                    latitude: data.geocoding.latitude,
                    longitude: data.geocoding.longitude,
                    osmType: data.geocoding.osm_type,
                    osmId: data.geocoding.osm_id,
                    buildingCount: data.buildings ? data.buildings.length : 0,
                };
            }

            setSearchResults([result]);
            setShowResults(true);
            setSelectedResultIndex(0);
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
        setIsComposing(true);
    }, []);

    const handleCompositionEnd = useCallback(() => {
        setIsComposing(false);
    }, []);

    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        // Block keyboard handling during IME composition
        if (isComposing || e.nativeEvent.isComposing) return;

        if (e.key === "Enter") {
            e.preventDefault();
            performSearch();
        } else if (e.key === "Escape") {
            setShowResults(false);
            setSearchError(null);
            if (!searchQuery.trim()) {
                setIsExpanded(false);
                searchInputRef.current?.blur();
            }
        } else if (e.key === "ArrowDown" && showResults && searchResults.length > 0) {
            e.preventDefault();
            setSelectedResultIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : prev));
        } else if (e.key === "ArrowUp" && showResults && searchResults.length > 0) {
            e.preventDefault();
            setSelectedResultIndex((prev) => (prev > 0 ? prev - 1 : 0));
        }
    };

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

            // 検索ドロップダウンを閉じる
            setShowResults(false);
            setSearchQuery(result.displayName);

            // Load 3D Tiles FIRST, then move camera (Issue #177 - mesh-based dynamic loading)
            try {
                setLoading(true);
                setLoadingMessage("3D Tilesを読み込み中...");

                // Calculate mesh codes (center + surrounding)
                const meshCodes = resolveMeshCodesFromCoordinates(
                    result.latitude,
                    result.longitude,
                    true, // Include neighbors
                );

                console.log(`[PlateauCesiumPicker] Loading 3D Tiles for ${meshCodes.length} mesh codes`);

                // Get API base URL
                const apiBaseUrl = window.__APP_CONFIG__?.stepUnfoldApiUrl || "http://localhost:8001";

                // Fetch 3D Tiles URLs from backend
                const response = await fetch(`${apiBaseUrl}/api/plateau/mesh-to-tilesets`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mesh_codes: meshCodes, lod: 1 }),
                });

                if (!response.ok) {
                    throw new Error(`API error: ${response.status}`);
                }

                const data = await response.json();
                const tilesets = data.tilesets || [];

                if (tilesets.length === 0) {
                    console.warn("[PlateauCesiumPicker] No 3D Tiles found for this area");
                    setLoading(false);
                    setLoadingMessage("");
                    return;
                }

                // Load tilesets
                const tilesetsToLoad = tilesets.map((t: any) => ({
                    meshCode: t.mesh_code,
                    url: t.tileset_url,
                }));

                const { failedMeshes } = await loader.loadMultipleTilesets(tilesetsToLoad);
                if (failedMeshes.length > 0) {
                    PubSub.default.pub(
                        "showToast",
                        "toast.plateau.tilesetLoadFailed:{0}",
                        failedMeshes.length,
                    );
                }

                console.log(`[PlateauCesiumPicker] Loaded ${tilesets.length} tilesets successfully`);

                // NOW move camera AFTER tiles are loaded (matching Web Components version)
                viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromDegrees(
                        result.longitude,
                        result.latitude,
                        1000, // 高度1000m（建物が見やすい高さ）
                    ),
                    duration: 1.5,
                });

                setLoading(false);
                setLoadingMessage("");

                // ユーザーに建物選択を促す（カメラ移動完了後）
                if (result.buildingCount && result.buildingCount > 0) {
                    console.log(
                        `[PlateauCesiumPicker] 周辺に${result.buildingCount}件の建物があります。3D地図上でクリックして選択してください。`,
                    );
                }
            } catch (error) {
                console.error("[PlateauCesiumPicker] Failed to load 3D Tiles:", error);
                setLoading(false);
                setLoadingMessage("");
            }
        },
        [setLoading, setLoadingMessage],
    );

    return (
        <div className={styles.dialog}>
            <Header onClose={handleClose} loading={loading} />
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
                    {/* Google-style search box with progressive disclosure */}
                    <div ref={searchContainerRef} className={styles.searchContainer}>
                        <div className={`${styles.searchBox} ${isExpanded ? styles.expanded : ""}`}>
                            {/* Main search input */}
                            <div className={styles.searchInputWrapper}>
                                <span className={styles.searchIcon} aria-hidden="true">
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
                                    aria-label="場所や施設を検索"
                                    autoComplete="off"
                                    spellCheck="false"
                                />
                                {isSearching && <div className={styles.searchSpinner} />}
                                {!isSearching && searchQuery && (
                                    <button
                                        className={styles.searchClearButton}
                                        onClick={handleSearchClear}
                                        aria-label="クリア"
                                    >
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M18 6L6 18M6 6l12 12" />
                                        </svg>
                                    </button>
                                )}
                            </div>

                            {/* Mode chips - appears on expand */}
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

                            {/* Mesh code input - only for buildingId mode */}
                            <div
                                className={`${styles.meshCodeSection} ${isExpanded && searchMode === "buildingId" ? styles.visible : ""}`}
                            >
                                <input
                                    type="text"
                                    className={styles.meshCodeInput}
                                    placeholder="メッシュコード（例: 53394511）"
                                    value={meshCode}
                                    onChange={(e) => setMeshCode(e.target.value)}
                                    onCompositionStart={handleCompositionStart}
                                    onCompositionEnd={handleCompositionEnd}
                                    disabled={isSearching}
                                    aria-label="メッシュコードを入力"
                                />
                            </div>

                            {/* Divider before results */}
                            {showResults && <div className={styles.searchDivider} />}

                            {/* Search results */}
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
                                            <div className={styles.locationName}>
                                                {result.displayName}
                                            </div>
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

                            {/* Hint text */}
                            {isExpanded && !showResults && !searchQuery && (
                                <div className={styles.searchHint}>
                                    Enter で検索
                                </div>
                            )}
                        </div>
                    </div>
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
