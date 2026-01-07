// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useCallback, useState, useMemo } from "react";
import { useAtom } from "jotai";
import * as Cesium from "cesium";
import { DialogResult, I18n, PubSub } from "chili-core";
import {
    CesiumView,
    CesiumBuildingPicker,
    CesiumTilesetLoader,
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

    const [currentCity, setCurrentCity] = useAtom(currentCityAtom);
    const [selectedBuildings, setSelectedBuildings] = useAtom(selectedBuildingsAtom);
    const [loading, setLoading] = useAtom(loadingAtom);
    const [loadingMessage, setLoadingMessage] = useAtom(loadingMessageAtom);
    const [tilesetUrl, setTilesetUrl] = useState<string>("");
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

        // Initialize tileset loader (Phase 4.4)
        tilesetLoaderRef.current = new CesiumTilesetLoader(viewer);

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

    // Search handlers
    const performSearch = useCallback(async () => {
        const query = searchQuery.trim();
        if (!query) return;

        // GML IDモードの場合、メッシュコードもチェック
        if (searchMode === "buildingId" && !meshCode.trim()) {
            setSearchError("メッシュコードを入力してください");
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
            const apiBaseUrl = (window as any).__APP_CONFIG__?.stepUnfoldApiUrl ||
                              "http://localhost:8001/api";

            // 検索モードに応じてエンドポイント切り替え
            const endpoint = searchMode === "buildingId"
                ? `/plateau/search-by-building-id-and-mesh`
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
                    radius: searchRadius / 111000, // m → degrees
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

            const data = await response.json();

            if (!data.success) {
                setSearchError(data.error || "検索に失敗しました");
                setSearchResults([]);
                setShowResults(true);
                return;
            }

            // 検索結果を統一フォーマットに変換
            let result: SearchResult;

            if (searchMode === "buildingId") {
                // GML ID検索の場合
                if (!data.building) {
                    setSearchError("建物が見つかりません");
                    setSearchResults([]);
                    setShowResults(true);
                    return;
                }
                result = {
                    displayName: data.building.name || data.building.gml_id,
                    latitude: data.building.latitude || 35.681,
                    longitude: data.building.longitude || 139.767,
                    buildingCount: 1
                };
            } else {
                // 施設名/住所検索の場合
                if (!data.geocoding) {
                    setSearchError("該当する場所が見つかりません");
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

        } catch (error: any) {
            if (error.name === 'AbortError') return;
            console.error("[PlateauCesiumPickerReact] Search failed:", error);
            setSearchError("検索中にエラーが発生しました");
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

    // Camera control for search results
    const findNearestCity = useCallback((latitude: number, longitude: number) => {
        const toRadians = (deg: number) => deg * (Math.PI / 180);
        const haversine = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
            const R = 6371;
            const dLat = toRadians(lat2 - lat1);
            const dLon = toRadians(lon2 - lon1);
            const a = Math.sin(dLat / 2) ** 2 +
                      Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
                      Math.sin(dLon / 2) ** 2;
            return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        };

        const cities = [
            { key: "chiyoda", name: "千代田区", lat: 35.6938, lon: 139.7536 },
            { key: "shibuya", name: "渋谷区", lat: 35.6617, lon: 139.6980 },
            { key: "shinjuku", name: "新宿区", lat: 35.6938, lon: 139.7036 },
            { key: "minato", name: "港区", lat: 35.6585, lon: 139.7514 },
            { key: "chuo", name: "中央区", lat: 35.6704, lon: 139.7703 },
            { key: "osaka", name: "大阪市", lat: 34.6937, lon: 135.5023 },
            { key: "nagoya", name: "名古屋市", lat: 35.1815, lon: 136.9066 },
            { key: "yokohama", name: "横浜市", lat: 35.4437, lon: 139.6380 },
            { key: "fukuoka", name: "福岡市", lat: 33.5904, lon: 130.4017 },
            { key: "sapporo", name: "札幌市", lat: 43.0642, lon: 141.3469 }
        ];

        let nearestCity = cities[0];
        let minDistance = haversine(latitude, longitude, cities[0].lat, cities[0].lon);

        for (const city of cities.slice(1)) {
            const distance = haversine(latitude, longitude, city.lat, city.lon);
            if (distance < minDistance) {
                minDistance = distance;
                nearestCity = city;
            }
        }

        return nearestCity;
    }, []);

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

        // 最寄り都市の3Dタイルを自動読み込み
        const nearestCity = findNearestCity(result.latitude, result.longitude);
        if (nearestCity && nearestCity.key !== currentCity) {
            setCurrentCity(nearestCity.key);
        }

        // ユーザーに建物選択を促すトースト（将来的にi18nキーに置き換え）
        // PubSubはi18nキーが必要なため、コンソールログに変更
        if (result.buildingCount && result.buildingCount > 0) {
            console.log(`[PlateauCesiumPicker] 周辺に${result.buildingCount}件の建物があります。3D地図上でクリックして選択してください。`);
        }
    }, [currentCity, setCurrentCity, findNearestCity]);

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
                    {/* Google Earth-style search box (top-left overlay) */}
                    <div ref={searchContainerRef} className={styles.searchContainer}>
                        <div className={styles.searchInputWrapper}>
                            <span className={styles.searchIcon} aria-hidden="true">🔍</span>
                            <input
                                type="text"
                                className={styles.searchInput}
                                placeholder="施設名や住所を検索（例: 東京駅）"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleSearchKeyDown}
                                disabled={isSearching}
                                aria-label="施設名または住所を検索"
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
