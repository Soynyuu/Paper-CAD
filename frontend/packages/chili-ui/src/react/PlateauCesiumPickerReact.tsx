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
    type PickedBuilding,
} from "chili-cesium";
import {
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

    interface AppConfig {
        cesiumBaseUrl?: string;
        cesiumIonToken?: string;
        stepUnfoldApiUrl?: string;
    }

    interface GlobalWithConfig extends Window {
        __APP_CONFIG__?: AppConfig;
        CESIUM_BASE_URL?: string;
    }

    const runtime = globalThis as unknown as GlobalWithConfig;
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

    // Search mode state (NEW)
    const [searchMode, setSearchMode] = useState<"facility" | "address" | "buildingId">("facility");
    const [searchRadius, setSearchRadius] = useState<number>(100); // meters
    const [meshCode, setMeshCode] = useState<string>("");

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

    // Load 3D Tiles tileset when URL changes
    useEffect(() => {
        if (!viewerReady || !tilesetUrl) return;

        const viewer = cesiumViewRef.current?.getViewer();
        if (!viewer) return;

        console.log("[PlateauCesiumPickerReact] Loading tileset:", tilesetUrl);

        // Phase 4.4: Use CesiumTilesetLoader instead of direct fromUrl()
        const loader = tilesetLoaderRef.current;
        if (!loader) {
            console.error("[PlateauCesiumPickerReact] TilesetLoader not initialized");
            setLoading(false);
            setLoadingMessage("");
            return;
        }

        loader
            .loadTileset(tilesetUrl)
            .then((tileset) => {
                tilesetRef.current = tileset;
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

    // Close search results when clicking outside
    useEffect(() => {
        if (!showResults) return;

        const handleClickOutside = (e: MouseEvent) => {
            if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
                setShowResults(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [showResults]);

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
    const METERS_PER_DEGREE = 111000; // Approximate meters per degree at equator
    const DEFAULT_TOKYO_LAT = 35.681236; // Tokyo Station latitude
    const DEFAULT_TOKYO_LON = 139.767125; // Tokyo Station longitude

    // Search handlers
    const performSearch = useCallback(async () => {
        const query = searchQuery.trim();
        if (!query) return;

        // GML IDモードの場合、メッシュコードもチェック
        if (searchMode === "buildingId" && !meshCode.trim()) {
            setSearchError(I18n.translate("error.plateau.emptyMeshCode") || "メッシュコードを入力してください");
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
            interface AppConfig {
                stepUnfoldApiUrl?: string;
            }
            interface WindowWithConfig extends Window {
                __APP_CONFIG__?: AppConfig;
            }
            const apiBaseUrl = (window as unknown as WindowWithConfig).__APP_CONFIG__?.stepUnfoldApiUrl ||
                              "http://localhost:8001/api";

            // 検索モードに応じてエンドポイント切り替え
            const endpoint = searchMode === "buildingId"
                ? `/plateau/search-by-id-and-mesh`
                : `/plateau/search-by-address`;

            const requestBody = searchMode === "buildingId"
                ? {
                    building_id: query,
                    mesh_code: meshCode.trim(),
                    debug: false,
                    merge_building_parts: false
                  }
                : {
                    query,
                    radius: searchRadius / METERS_PER_DEGREE, // Convert meters to degrees
                    limit: 20,
                    search_mode: searchMode === "facility" ? "hybrid" : "distance",
                    name_filter: searchMode === "facility" ? query : undefined
                  };

            const response = await fetch(`${apiBaseUrl}${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                signal: abortControllerRef.current.signal
            });

            // Check HTTP status
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (!data.success) {
                setSearchError(data.error || I18n.translate("error.plateau.searchFailed:{0}", "Unknown error"));
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
                    buildingCount: 1
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
                    buildingCount: data.buildings ? data.buildings.length : 0
                };
            }

            setSearchResults([result]);
            setShowResults(true);
            setSelectedResultIndex(0);

        } catch (error: unknown) {
            if (error instanceof Error && error.name === 'AbortError') return;
            console.error("[PlateauCesiumPickerReact] Search failed:", error);
            const errorMsg = error instanceof Error ? error.message : "Unknown error";
            setSearchError(I18n.translate("error.plateau.searchFailed:{0}", errorMsg));
            setShowResults(true);
        } finally {
            setIsSearching(false);
        }
    }, [searchQuery, searchMode, searchRadius, meshCode]);

    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.nativeEvent.isComposing) return;

        if (e.key === "Enter") {
            e.preventDefault();
            performSearch();
        } else if (e.key === "Escape") {
            setShowResults(false);
            setSearchError(null);
        } else if (e.key === "ArrowDown" && showResults && searchResults.length > 0) {
            e.preventDefault();
            setSelectedResultIndex((prev) =>
                prev < searchResults.length - 1 ? prev + 1 : prev
            );
        } else if (e.key === "ArrowUp" && showResults && searchResults.length > 0) {
            e.preventDefault();
            setSelectedResultIndex((prev) => (prev > 0 ? prev - 1 : 0));
        }
    };

    const handleSearchClear = () => {
        setSearchQuery("");
        setSearchResults([]);
        setShowResults(false);
        setSearchError(null);
        setSelectedResultIndex(-1);
    };

    // findNearestCity removed - using mesh-based dynamic loading (Issue #177)

    const handleResultClick = useCallback((result: SearchResult) => {
        const viewer = cesiumViewRef.current?.getViewer();
        if (!viewer) return;

        // 検索ドロップダウンを閉じる
        setShowResults(false);
        setSearchQuery(result.displayName);

        // Cesiumカメラを該当位置へ飛ばす
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(
                result.longitude,
                result.latitude,
                1000  // 高度1000m（建物が見やすい高さ）
            ),
            duration: 2.0,
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-45),  // 斜め上から見下ろす角度
                roll: 0
            }
        });

        // City switching removed - using mesh-based dynamic loading (Issue #177)

        // ユーザーに建物選択を促す（カメラ移動完了後）
        if (result.buildingCount && result.buildingCount > 0) {
            console.log(`[PlateauCesiumPicker] 周辺に${result.buildingCount}件の建物があります。3D地図上でクリックして選択してください。`);
        }
    }, []);

    return (
        <div className={styles.dialog}>
            <Header
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
                    {/* Google Earth-style search box (top-left overlay) */}
                    <div ref={searchContainerRef} className={styles.searchContainer}>
                        {/* Search mode tabs */}
                        <div className={styles.searchModeTabs}>
                            <button
                                className={`${styles.searchModeTab} ${searchMode === "facility" ? styles.active : ""}`}
                                onClick={() => setSearchMode("facility")}
                                aria-label="施設名で検索"
                            >
                                🏢 施設名
                            </button>
                            <button
                                className={`${styles.searchModeTab} ${searchMode === "address" ? styles.active : ""}`}
                                onClick={() => setSearchMode("address")}
                                aria-label="住所で検索"
                            >
                                📍 住所
                            </button>
                            <button
                                className={`${styles.searchModeTab} ${searchMode === "buildingId" ? styles.active : ""}`}
                                onClick={() => setSearchMode("buildingId")}
                                aria-label="建物IDで検索"
                            >
                                🆔 建物ID
                            </button>
                        </div>
                        
                        <div className={styles.searchInputWrapper}>
                            <span className={styles.searchIcon} aria-hidden="true">🔍</span>
                            <input
                                type="text"
                                className={styles.searchInput}
                                placeholder={
                                    searchMode === "facility"
                                        ? "施設名を検索（例: 東京駅）"
                                        : searchMode === "address"
                                        ? "住所を検索（例: 千代田区丸の内）"
                                        : "建物IDを入力（例: bldg_xxx）"
                                }
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleSearchKeyDown}
                                disabled={isSearching}
                                aria-label={
                                    searchMode === "facility"
                                        ? "施設名を検索"
                                        : searchMode === "address"
                                        ? "住所を検索"
                                        : "建物IDを検索"
                                }
                                role="combobox"
                                aria-expanded={showResults}
                            />
                            {isSearching && <div className={styles.searchSpinner} />}
                            {!isSearching && searchQuery && (
                                <button className={styles.searchClearButton} onClick={handleSearchClear}>
                                    ×
                                </button>
                            )}
                        </div>
                        
                        {/* Mesh code input for buildingId mode */}
                        {searchMode === "buildingId" && (
                            <div className={styles.meshCodeInputWrapper}>
                                <span className={styles.meshCodeIcon} aria-hidden="true">🗺️</span>
                                <input
                                    type="text"
                                    className={styles.meshCodeInput}
                                    placeholder="メッシュコード（例: 53394511）"
                                    value={meshCode}
                                    onChange={(e) => setMeshCode(e.target.value)}
                                    disabled={isSearching}
                                    aria-label="メッシュコードを入力"
                                />
                            </div>
                        )}

                        {showResults && (
                            <div className={styles.searchResults} role="listbox">
                                {searchError ? (
                                    <div className={styles.searchError}>⚠️ {searchError}</div>
                                ) : searchResults.map((result, index) => (
                                    <div
                                        key={`${result.osmType}-${result.osmId}-${index}`}
                                        className={`${styles.searchResultItem} ${
                                            index === selectedResultIndex ? styles.selected : ""
                                        }`}
                                        onClick={() => handleResultClick(result)}
                                        role="option"
                                        aria-selected={index === selectedResultIndex}
                                    >
                                        {/* 場所情報のみ表示 */}
                                        <div className={styles.locationName}>
                                            📍 {result.displayName}
                                        </div>

                                        {/* 建物件数の情報のみ追加 */}
                                        {result.buildingCount !== undefined && result.buildingCount > 0 && (
                                            <div className={styles.buildingCount}>
                                                周辺の建物 {result.buildingCount}件
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
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
