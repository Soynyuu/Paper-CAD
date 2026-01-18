// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, label, select } from "chili-controls";
import {
    DialogResult,
    I18n,
    IApplication,
    PubSub,
    CityGMLService,
    type BatchBuildingRequest,
} from "chili-core";
import {
    CesiumBuildingPicker,
    CesiumTilesetLoader,
    CesiumView,
    latLonToMesh3rd,
    meshToLatLon,
    resolveMeshCodesFromCoordinates,
    type PickedBuilding,
} from "chili-cesium";
import * as Cesium from "cesium";
import style from "./dialog.module.css";

export interface PlateauCesiumPickerResult {
    selectedBuildings: PickedBuilding[];
}

/**
 * PlateauCesiumPickerDialog
 *
 * Interactive dialog for picking PLATEAU buildings from Cesium 3D Tiles.
 *
 * Features:
 * - Cesium 3D Tiles viewer (75% width)
 * - Selected buildings panel (25% width)
 * - City dropdown selector
 * - Multi-select with Ctrl+Click
 * - Building metadata display
 * - Batch import
 */
export class PlateauCesiumPickerDialog {
    private constructor() {}

    static show(
        app: IApplication,
        callback?: (result: DialogResult, data?: PlateauCesiumPickerResult) => void,
    ) {
        const dialog = document.createElement("dialog");
        document.body.appendChild(dialog);

        // State
        let cesiumView: CesiumView | null = null;
        let tilesetLoader: CesiumTilesetLoader | null = null;
        let buildingPicker: CesiumBuildingPicker | null = null;
        let clickHandler: Cesium.ScreenSpaceEventHandler | null = null;

        // Drag detection state (Phase 1.1)
        let mouseDownPosition: { x: number; y: number } | null = null;
        let isCameraMoving = false;
        const DRAG_THRESHOLD_PX = 6;
        const MESH_CODE_PATTERN = /^\d{8}$/;

        // Disambiguation popup state (Phase 5.2)
        let candidatePopup: HTMLElement | null = null;

        // Metadata cache (Phase 6.3)
        const metadataCache = new Map<string, PickedBuilding>();

        const apiBaseUrl = (__APP_CONFIG__.stepUnfoldApiUrl || "http://localhost:8001/api").replace(
            /\/$/,
            "",
        );
        const preferredPickLod = Math.min(3, Math.max(1, Number(__APP_CONFIG__?.cesiumPickLod ?? 2)));
        const preferNoTexture = Boolean(__APP_CONFIG__?.cesiumPreferNoTexture);

        // Cesium viewer container (left panel, 75%)
        const viewerContainer = div({
            style: {
                width: "75%",
                height: "600px",
                position: "relative",
                backgroundColor: "#000",
            },
        });

        // Selected buildings panel (right panel, 25%)
        const selectedPanelContainer = div({
            style: {
                width: "25%",
                height: "600px",
                overflowY: "auto",
                borderLeft: "1px solid var(--border-color)",
                padding: "12px",
                backgroundColor: "var(--neutral-50)",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
            },
        });

        // Search mode state
        let currentSearchMode: "address" | "buildingId" | "meshCode" = "address";

        // Search tabs container
        const searchTabsContainer = div(
            { className: style.searchTabsContainer },

            // Tab headers
            div(
                { className: style.searchTabsHeader },
                button({
                    className: style.searchTab,
                    dataset: { active: "true" },
                    textContent: "🔍 住所検索",
                    onclick: () => switchSearchTab("address"),
                }),
                button({
                    className: style.searchTab,
                    textContent: "🏢 建物ID",
                    onclick: () => switchSearchTab("buildingId"),
                }),
                button({
                    className: style.searchTab,
                    textContent: "📊 メッシュコード",
                    onclick: () => switchSearchTab("meshCode"),
                }),
            ),

            // Tab content: Address search
            div(
                {
                    id: "address-search",
                    className: style.searchTabContent,
                    dataset: { active: "true" },
                },
                input({
                    type: "text",
                    placeholder: "東京駅、千代田区丸の内...",
                    className: style.searchInput,
                    id: "address-input",
                }),
                button({
                    textContent: "検索",
                    className: style.searchButton,
                    onclick: () => executeAddressSearch(),
                }),
            ),

            // Tab content: Building ID search
            div(
                {
                    id: "building-id-search",
                    className: style.searchTabContent,
                },
                div(
                    { className: style.searchFormRow },
                    div(
                        { style: { flex: "1" } },
                        div({ className: style.inputLabel, textContent: "建物ID" }),
                        input({
                            type: "text",
                            placeholder: "bldg_xxx...",
                            className: style.searchInput,
                            id: "building-id-input",
                        }),
                    ),
                ),
                div(
                    { className: style.searchFormRow },
                    div(
                        { style: { flex: "1" } },
                        div({
                            className: style.inputLabel,
                            textContent: "メッシュコード (任意)",
                        }),
                        input({
                            type: "text",
                            placeholder: "53394511 (8桁)",
                            className: style.searchInput,
                            id: "mesh-code-optional-input",
                            pattern: "[0-9]{8}",
                        }),
                    ),
                ),
                button({
                    textContent: "検索",
                    className: style.searchButton,
                    onclick: () => executeBuildingIdSearch(),
                }),
            ),

            // Tab content: Mesh code search
            div(
                {
                    id: "mesh-search",
                    className: style.searchTabContent,
                },
                input({
                    type: "text",
                    placeholder: "53394511 (8桁)",
                    className: style.searchInput,
                    id: "mesh-code-input",
                    pattern: "[0-9]{8}",
                }),
                button({
                    textContent: "検索",
                    className: style.searchButton,
                    onclick: () => executeMeshCodeSearch(),
                }),
            ),
        );

        // Mesh indicator
        const meshIndicator = div({
            className: style.meshIndicator,
            textContent: "検索してください",
        });

        // Instructions overlay
        const instructionsOverlay = div(
            {
                style: {
                    position: "absolute",
                    top: "12px",
                    left: "12px",
                    backgroundColor: "rgba(0, 0, 0, 0.7)",
                    color: "white",
                    padding: "12px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--font-size-sm)",
                    zIndex: "1000",
                    maxWidth: "300px",
                },
            },
            div(
                { style: { fontWeight: "bold", marginBottom: "4px" } },
                I18n.translate("plateau.cesium.clickToSelect"),
            ),
            div("• Click: Select single building"),
            div("• Ctrl+Click: Toggle multi-select"),
            div("• Click empty area: Clear selection"),
        );

        viewerContainer.appendChild(instructionsOverlay);

        // Loading indicator
        const loadingIndicator = div(
            {
                style: {
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    backgroundColor: "rgba(0, 0, 0, 0.8)",
                    color: "white",
                    padding: "20px 40px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--font-size-md)",
                    zIndex: "1001",
                    display: "none",
                },
            },
            "Loading 3D Tiles...",
        );

        viewerContainer.appendChild(loadingIndicator);

        /**
         * Check if coordinates are within Japan's boundaries
         *
         * @param latitude - Latitude in degrees
         * @param longitude - Longitude in degrees
         * @returns true if within Japan
         */
        const isWithinJapan = (latitude: number, longitude: number): boolean => {
            // Japan's rough boundaries (including main islands and remote islands)
            // Latitude: 20°N (Okinotorishima) ~ 46°N (Etorofu)
            // Longitude: 122°E (Yonaguni) ~ 154°E (Minamitorishima)
            return latitude >= 20 && latitude <= 46 && longitude >= 122 && longitude <= 154;
        };

        const MUNICIPALITY_CODE_PATTERN = /^(\d{5})/;

        const extractMunicipalityCode = (buildingId?: string | null) => {
            if (!buildingId) return undefined;
            const match = buildingId.match(MUNICIPALITY_CODE_PATTERN);
            return match?.[1];
        };

        /**
         * Switch search tab
         */
        const switchSearchTab = (mode: "address" | "buildingId" | "meshCode") => {
            currentSearchMode = mode;

            // Update tab headers
            const tabs = dialog.querySelectorAll(`.${style.searchTab}`);
            tabs.forEach((tab, index) => {
                const modes = ["address", "buildingId", "meshCode"];
                tab.setAttribute("data-active", modes[index] === mode ? "true" : "false");
            });

            // Update tab contents
            const addressTab = dialog.querySelector("#address-search");
            const buildingIdTab = dialog.querySelector("#building-id-search");
            const meshTab = dialog.querySelector("#mesh-search");

            if (addressTab) addressTab.setAttribute("data-active", mode === "address" ? "true" : "false");
            if (buildingIdTab)
                buildingIdTab.setAttribute("data-active", mode === "buildingId" ? "true" : "false");
            if (meshTab) meshTab.setAttribute("data-active", mode === "meshCode" ? "true" : "false");
        };

        /**
         * Update mesh indicator
         */
        const updateMeshIndicator = (meshCount: number) => {
            const coverage = Math.sqrt(meshCount); // 3x3 = 9 → "約3km"
            meshIndicator.textContent = `💡 表示中: ${meshCount}メッシュ (約${coverage.toFixed(0)}km範囲)`;
        };

        const notifyMeshLoadFailures = (failedMeshes: string[]) => {
            if (failedMeshes.length === 0) {
                return;
            }
            PubSub.default.pub("showToast", "toast.plateau.tilesetLoadFailed:{0}", failedMeshes.length);
        };

        /**
         * Execute address search
         */
        const executeAddressSearch = async () => {
            const input = dialog.querySelector("#address-input") as HTMLInputElement;
            const query = input?.value.trim();

            if (!query) {
                PubSub.default.pub("showToast", "error.plateau.emptyQuery");
                return;
            }

            try {
                loadingIndicator.style.display = "block";
                meshIndicator.textContent = "検索中...";

                // Call backend API
                const citygmlService = new CityGMLService();
                const result = await citygmlService.searchByAddress(query, {
                    radius: 0.001,
                    limit: 50,
                });

                if (!result.isOk || !result.value.success || !result.value.geocoding) {
                    console.error(
                        "[Address Search] Search failed:",
                        result.isOk ? result.value.error : result.error,
                    );
                    meshIndicator.textContent = "検索に失敗しました";
                    loadingIndicator.style.display = "none";
                    return;
                }

                const coordinates = result.value.geocoding;

                // Check if coordinates are within Japan
                if (!isWithinJapan(coordinates.latitude, coordinates.longitude)) {
                    console.warn("[Address Search] Coordinates out of bounds:", coordinates);
                    meshIndicator.textContent = "日本国内の座標のみサポートしています";
                    loadingIndicator.style.display = "none";
                    return;
                }

                // Calculate mesh codes + neighbors
                const meshCodes = resolveMeshCodesFromCoordinates(
                    coordinates.latitude,
                    coordinates.longitude,
                    true, // Include neighbors
                );

                console.log(`[Search] Found ${meshCodes.length} mesh codes:`, meshCodes);
                const municipalityCode = extractMunicipalityCode(result.value.buildings?.[0]?.building_id);
                const requestBody: Record<string, unknown> = {
                    mesh_codes: meshCodes,
                    lod: preferredPickLod,
                };
                if (municipalityCode) {
                    requestBody["municipality_code"] = municipalityCode;
                }
                if (preferNoTexture) {
                    requestBody["prefer_no_texture"] = true;
                }

                // Fetch 3D Tiles URLs for mesh codes
                const response = await fetch(`${apiBaseUrl}/plateau/mesh-to-tilesets`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(requestBody),
                });

                if (!response.ok) {
                    throw new Error(`API error: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.total_found === 0) {
                    console.warn("[Address Search] No tilesets found for meshes:", meshCodes);

                    // Check if coordinate is likely on water or land without data
                    const displayName = coordinates.display_name?.toLowerCase() || "";
                    const isLikelyWater =
                        displayName.includes("sea") ||
                        displayName.includes("ocean") ||
                        displayName.includes("bay") ||
                        displayName.includes("海");

                    if (isLikelyWater) {
                        meshIndicator.textContent = "海上には建物データがありません";
                    } else {
                        meshIndicator.textContent = "この地域のPLATEAUデータは未整備です";
                    }

                    loadingIndicator.style.display = "none";
                    return;
                }

                // Load multiple tilesets
                const viewer = cesiumView?.getViewer();
                if (tilesetLoader && viewer) {
                    tilesetLoader.clearAll();
                    const { failedMeshes } = await tilesetLoader.loadMultipleTilesets(
                        data.tilesets.map((t: any) => ({
                            meshCode: t.mesh_code,
                            url: t.tileset_url,
                        })),
                    );
                    notifyMeshLoadFailures(failedMeshes);

                    // Fly to search location
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(
                            coordinates.longitude,
                            coordinates.latitude,
                            1000,
                        ),
                        duration: 1.5,
                    });
                }

                // Update indicator
                updateMeshIndicator(meshCodes.length);
            } catch (error) {
                console.error("[Search] Address search failed:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.searchFailed:{0}",
                    error instanceof Error ? error.message : String(error),
                );
                meshIndicator.textContent = "エラーが発生しました";
            } finally {
                loadingIndicator.style.display = "none";
            }
        };

        /**
         * Execute building ID search
         */
        const executeBuildingIdSearch = async () => {
            const buildingIdInput = dialog.querySelector("#building-id-input") as HTMLInputElement;
            const meshCodeInput = dialog.querySelector("#mesh-code-optional-input") as HTMLInputElement;

            const buildingId = buildingIdInput?.value.trim();
            const meshCode = meshCodeInput?.value.trim();

            if (!buildingId) {
                meshIndicator.textContent = "建物IDを入力してください";
                return;
            }

            // Validate mesh code if provided
            if (meshCode && !MESH_CODE_PATTERN.test(meshCode)) {
                meshIndicator.textContent = "メッシュコードは8桁の数字で入力してください";
                return;
            }

            try {
                loadingIndicator.style.display = "block";
                meshIndicator.textContent = "検索中...";

                const citygmlService = new CityGMLService(apiBaseUrl);

                // Use optimized endpoint if mesh code provided
                const result = meshCode
                    ? await citygmlService.searchByBuildingIdAndMesh(buildingId, meshCode)
                    : await citygmlService.searchByBuildingId(buildingId);

                if (!result.isOk || !result.value.success || !result.value.building) {
                    console.error(
                        "[Building ID Search] Not found:",
                        result.isOk ? result.value.error : result.error,
                    );
                    meshIndicator.textContent = "建物が見つかりませんでした";
                    loadingIndicator.style.display = "none";
                    return;
                }

                const building = result.value.building;

                // Calculate mesh code from coordinates if not provided
                const meshCodeToUse = meshCode || latLonToMesh3rd(building.latitude, building.longitude);
                const municipalityCode = extractMunicipalityCode(building.building_id || buildingId);
                const requestBody: Record<string, unknown> = {
                    mesh_codes: [meshCodeToUse],
                    lod: preferredPickLod,
                };
                if (municipalityCode) {
                    requestBody["municipality_code"] = municipalityCode;
                }
                if (preferNoTexture) {
                    requestBody["prefer_no_texture"] = true;
                }

                // Fetch 3D Tiles for the mesh
                const response = await fetch(`${apiBaseUrl}/plateau/mesh-to-tilesets`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(requestBody),
                });

                if (!response.ok) {
                    throw new Error(`API error: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.total_found === 0) {
                    console.warn("[Building ID Search] No 3D Tiles found for mesh:", meshCodeToUse);
                    meshIndicator.textContent = "該当する3D Tilesが見つかりませんでした";
                    loadingIndicator.style.display = "none";
                    return;
                }

                // Load tileset
                const viewer = cesiumView?.getViewer();
                if (tilesetLoader && viewer) {
                    tilesetLoader.clearAll();
                    const { failedMeshes } = await tilesetLoader.loadMultipleTilesets(
                        data.tilesets.map((t: any) => ({
                            meshCode: t.mesh_code,
                            url: t.tileset_url,
                        })),
                    );
                    notifyMeshLoadFailures(failedMeshes);

                    // Fly to building location
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(
                            building.longitude,
                            building.latitude,
                            1000,
                        ),
                        duration: 1.5,
                    });
                }

                updateMeshIndicator(1);
                meshIndicator.textContent = `✓ 建物を発見: ${building.name || building.gml_id}`;

                console.log("[Building ID Search] Success:", building);
            } catch (error) {
                console.error("[Building ID Search] Error:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.searchFailed:{0}",
                    error instanceof Error ? error.message : String(error),
                );
                meshIndicator.textContent = "エラーが発生しました";
            } finally {
                loadingIndicator.style.display = "none";
            }
        };

        /**
         * Execute mesh code search
         */
        const executeMeshCodeSearch = async () => {
            const input = dialog.querySelector("#mesh-code-input") as HTMLInputElement;
            const meshCode = input?.value.trim();

            if (!meshCode || !MESH_CODE_PATTERN.test(meshCode)) {
                meshIndicator.textContent = "メッシュコードは8桁の数字で入力してください";
                return;
            }

            try {
                loadingIndicator.style.display = "block";
                meshIndicator.textContent = "検索中...";

                // Fetch 3D Tiles URL for single mesh code
                const response = await fetch(`${apiBaseUrl}/plateau/mesh-to-tilesets`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        mesh_codes: [meshCode],
                        lod: preferredPickLod,
                        prefer_no_texture: preferNoTexture || undefined,
                    }),
                });

                if (!response.ok) {
                    throw new Error(`API error: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.total_found === 0) {
                    console.warn("[Mesh Search] Mesh code not found:", meshCode);
                    meshIndicator.textContent = "該当するメッシュが見つかりませんでした";
                    loadingIndicator.style.display = "none";
                    return;
                }

                // Load tileset
                const viewer = cesiumView?.getViewer();
                if (tilesetLoader && viewer) {
                    tilesetLoader.clearAll();
                    const { failedMeshes } = await tilesetLoader.loadMultipleTilesets(
                        data.tilesets.map((t: any) => ({
                            meshCode: t.mesh_code,
                            url: t.tileset_url,
                        })),
                    );
                    notifyMeshLoadFailures(failedMeshes);

                    // Calculate mesh center and fly to it
                    const center = meshToLatLon(meshCode);
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, 1000),
                        duration: 1.5,
                    });
                }

                updateMeshIndicator(1);

                console.log("[Mesh Search] Successfully loaded mesh:", meshCode);
            } catch (error) {
                console.error("[Search] Mesh code search failed:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.searchFailed:{0}",
                    error instanceof Error ? error.message : String(error),
                );
                meshIndicator.textContent = "エラーが発生しました";
            } finally {
                loadingIndicator.style.display = "none";
            }
        };

        /**
         * Create building card for selected panel
         */
        const createBuildingCard = (building: PickedBuilding, index: number): HTMLElement => {
            const height = building.properties.measuredHeight || 0;
            const usageCodeMap: Record<string, string> = {
                "401": "業務施設",
                "402": "商業施設",
                "411": "宿泊施設",
                "421": "文教厚生施設",
                "431": "運動施設",
                "441": "公共施設",
                "451": "工場",
                "461": "運輸倉庫施設",
                "471": "供給処理施設",
            };
            const usageLabel = building.properties.usage
                ? usageCodeMap[building.properties.usage] || building.properties.usage
                : "N/A";

            // Remove button
            const removeBtn = button({
                textContent: "✕",
                style: {
                    backgroundColor: "var(--error-color)",
                    color: "white",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    padding: "4px 8px",
                    cursor: "pointer",
                    fontSize: "var(--font-size-xs)",
                },
                onclick: (e) => {
                    e.stopPropagation();
                    if (buildingPicker) {
                        buildingPicker.removeBuilding(building.gmlId);
                        updateSelectedPanel();
                    }
                },
            });

            return div(
                {
                    style: {
                        padding: "10px",
                        border: "1px solid var(--border-color)",
                        borderRadius: "var(--radius-sm)",
                        backgroundColor: "var(--neutral-100)",
                        fontSize: "var(--font-size-xs)",
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                    },
                },
                div(
                    {
                        style: {
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            fontWeight: "bold",
                            fontSize: "var(--font-size-sm)",
                            marginBottom: "4px",
                        },
                    },
                    div(`#${index + 1}: ${building.properties.name || "Unnamed Building"}`),
                    removeBtn,
                ),
                div(`高さ: ${height.toFixed(1)}m`),
                div(`用途: ${usageLabel}`),
                div(`都市: ${building.properties.cityName || "N/A"}`),
                div({
                    style: {
                        fontSize: "10px",
                        color: "var(--neutral-500)",
                        fontFamily: "monospace",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                    },
                    textContent: `GML ID: ${building.gmlId.substring(0, 30)}...`,
                }),
                div({
                    style: {
                        fontSize: "10px",
                        color: "var(--neutral-500)",
                        fontFamily: "monospace",
                    },
                    textContent: `Mesh: ${building.meshCode}`,
                }),
            );
        };

        /**
         * Show candidate disambiguation popup (Phase 5.2)
         */
        const showCandidatePopup = (
            candidates: PickedBuilding[],
            screenCoords: { x: number; y: number },
            multiSelect: boolean,
        ) => {
            // Remove existing popup
            if (candidatePopup) {
                candidatePopup.remove();
                candidatePopup = null;
            }

            // Calculate popup position (avoid edges)
            const popupWidth = 300;
            const popupMaxHeight = 400;
            let left = screenCoords.x + 10;
            let top = screenCoords.y + 10;

            // Adjust if too close to right edge
            if (left + popupWidth > window.innerWidth - 20) {
                left = screenCoords.x - popupWidth - 10;
            }

            // Adjust if too close to bottom edge
            if (top + popupMaxHeight > window.innerHeight - 20) {
                top = screenCoords.y - popupMaxHeight - 10;
            }

            // Usage code map
            const usageCodeMap: Record<string, string> = {
                "401": "業務施設",
                "402": "商業施設",
                "411": "宿泊施設",
                "421": "文教厚生施設",
                "431": "運動施設",
                "441": "公共施設",
                "451": "工場",
                "461": "運輸倉庫施設",
                "471": "供給処理施設",
            };

            // Create candidate cards
            const candidateCards = candidates.map((candidate, index) => {
                const height = candidate.properties.measuredHeight || 0;
                const usageLabel = candidate.properties.usage
                    ? usageCodeMap[candidate.properties.usage] || candidate.properties.usage
                    : "N/A";

                return div(
                    {
                        style: {
                            padding: "10px",
                            border: "1px solid var(--border-color)",
                            borderRadius: "var(--radius-sm)",
                            backgroundColor: "var(--neutral-100)",
                            marginBottom: "8px",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            if (buildingPicker) {
                                buildingPicker.selectCandidate(candidate.gmlId, multiSelect);
                                updateSelectedPanel();
                                closeCandidatePopup();
                            }
                        },
                    },
                    div(
                        {
                            style: {
                                fontWeight: "bold",
                                fontSize: "var(--font-size-sm)",
                                marginBottom: "4px",
                            },
                        },
                        `候補 ${index + 1}: ${candidate.properties.name || "Unnamed"}`,
                    ),
                    div({ style: { fontSize: "var(--font-size-xs)" } }, `高さ: ${height.toFixed(1)}m`),
                    div({ style: { fontSize: "var(--font-size-xs)" } }, `用途: ${usageLabel}`),
                    div(
                        {
                            style: {
                                fontSize: "10px",
                                color: "var(--neutral-500)",
                                fontFamily: "monospace",
                                marginTop: "4px",
                            },
                        },
                        `ID: ${candidate.gmlId.substring(0, 20)}...`,
                    ),
                );
            });

            // Create popup
            candidatePopup = div(
                {
                    style: {
                        position: "fixed",
                        left: `${left}px`,
                        top: `${top}px`,
                        width: `${popupWidth}px`,
                        maxHeight: `${popupMaxHeight}px`,
                        overflowY: "auto",
                        backgroundColor: "white",
                        border: "2px solid var(--primary-color)",
                        borderRadius: "var(--radius-md)",
                        padding: "12px",
                        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
                        zIndex: "10000",
                    },
                },
                div(
                    {
                        style: {
                            fontWeight: "bold",
                            fontSize: "var(--font-size-md)",
                            marginBottom: "8px",
                            color: "var(--primary-color)",
                        },
                    },
                    `${candidates.length}件の建物が重複しています`,
                ),
                div(
                    { style: { fontSize: "var(--font-size-xs)", marginBottom: "12px" } },
                    "選択する建物をクリック:",
                ),
                ...candidateCards,
                button({
                    textContent: "キャンセル",
                    style: {
                        width: "100%",
                        marginTop: "8px",
                        padding: "6px",
                        backgroundColor: "var(--neutral-300)",
                        border: "none",
                        borderRadius: "var(--radius-sm)",
                        cursor: "pointer",
                    },
                    onclick: closeCandidatePopup,
                }),
            );

            // Add to viewer container
            viewerContainer.appendChild(candidatePopup);

            // Close on click outside
            const handleClickOutside = (e: MouseEvent) => {
                if (candidatePopup && !candidatePopup.contains(e.target as Node)) {
                    closeCandidatePopup();
                }
            };

            setTimeout(() => {
                document.addEventListener("click", handleClickOutside, { once: true });
            }, 100);
        };

        /**
         * Close candidate popup
         */
        const closeCandidatePopup = () => {
            if (candidatePopup) {
                candidatePopup.remove();
                candidatePopup = null;
            }
        };

        /**
         * Update selected buildings panel
         */
        const updateSelectedPanel = () => {
            if (!buildingPicker) return;

            selectedPanelContainer.innerHTML = "";

            const selected = buildingPicker.getSelectedBuildings();
            const count = selected.length;

            // Header
            selectedPanelContainer.appendChild(
                div(
                    {
                        style: {
                            fontWeight: "bold",
                            fontSize: "var(--font-size-md)",
                            marginBottom: "8px",
                            padding: "8px",
                            backgroundColor: "var(--primary-color)",
                            color: "white",
                            borderRadius: "var(--radius-sm)",
                            textAlign: "center",
                        },
                    },
                    `${I18n.translate("plateau.cesium.selectedCount").replace("{0}", count.toString())}`,
                ),
            );

            // Building cards
            if (count === 0) {
                selectedPanelContainer.appendChild(
                    div(
                        {
                            style: {
                                textAlign: "center",
                                color: "var(--neutral-500)",
                                fontSize: "var(--font-size-sm)",
                                padding: "20px",
                            },
                        },
                        "No buildings selected",
                    ),
                );
            } else {
                selected.forEach((building: PickedBuilding, index: number) => {
                    selectedPanelContainer.appendChild(createBuildingCard(building, index));
                });
            }

            // Zoom to selection button
            if (count > 0) {
                selectedPanelContainer.appendChild(
                    button({
                        textContent: "🎯 " + I18n.translate("plateau.cesium.zoomToSelection"),
                        style: {
                            width: "100%",
                            padding: "8px",
                            marginTop: "8px",
                            backgroundColor: "var(--primary-color)",
                            color: "white",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            if (!cesiumView) return;
                            const viewer = cesiumView.getViewer();
                            if (!viewer || !buildingPicker) return;

                            const selected = buildingPicker.getSelectedBuildings();
                            if (selected.length === 0) return;

                            // Calculate bounding sphere from all selected building positions
                            const positions = selected.map((b) =>
                                Cesium.Cartesian3.fromDegrees(
                                    b.position.longitude,
                                    b.position.latitude,
                                    b.position.height,
                                ),
                            );
                            const boundingSphere = Cesium.BoundingSphere.fromPoints(positions);

                            // Fly to bounding sphere with appropriate offset
                            viewer.camera.flyToBoundingSphere(boundingSphere, {
                                duration: 1.5,
                                offset: new Cesium.HeadingPitchRange(
                                    0,
                                    Cesium.Math.toRadians(-45),
                                    boundingSphere.radius * 3,
                                ),
                            });
                        },
                    }),
                );
            }

            // Clear all button
            if (count > 0) {
                selectedPanelContainer.appendChild(
                    button({
                        textContent: I18n.translate("plateau.cesium.clearSelection"),
                        style: {
                            width: "100%",
                            padding: "8px",
                            marginTop: "8px",
                            backgroundColor: "var(--neutral-300)",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            if (buildingPicker) {
                                buildingPicker.clearSelection();
                                updateSelectedPanel();
                            }
                        },
                    }),
                );
            }

            // Update import button state
            importButton.disabled = count === 0;
        };

        // Import button
        const importButton = button({
            textContent: I18n.translate("plateau.cesium.importSelected"),
            disabled: true,
            style: {
                backgroundColor: "var(--primary-color)",
                color: "white",
                padding: "10px 20px",
                border: "none",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                fontSize: "var(--font-size-md)",
            },
            onclick: async () => {
                if (!buildingPicker) return;

                const selected = buildingPicker.getSelectedBuildings();
                if (selected.length === 0) {
                    alert("Please select at least one building");
                    return;
                }

                // Phase 6.3: Batch metadata fetching with cache
                const needsMetadata = selected.filter((b) => !metadataCache.has(b.gmlId));

                if (needsMetadata.length > 0) {
                    try {
                        // Show loading
                        loadingIndicator.textContent = `Fetching metadata for ${needsMetadata.length} building(s)...`;
                        loadingIndicator.style.display = "block";

                        // Prepare batch request
                        const requests: BatchBuildingRequest[] = needsMetadata.map((b) => ({
                            buildingId: b.gmlId,
                            meshCode: b.meshCode,
                        }));

                        // Get base URL from config
                        // Fetch batch
                        const citygmlService = new CityGMLService(apiBaseUrl);
                        const result = await citygmlService.batchSearchByBuildingIds(requests);

                        if (result.isOk) {
                            // Cache successful results
                            result.value.results.forEach((res, index) => {
                                if (res.success && res.building) {
                                    const buildingFromRequest = needsMetadata[index];
                                    // Merge metadata into building object
                                    const enriched: PickedBuilding = {
                                        ...buildingFromRequest,
                                        properties: {
                                            ...buildingFromRequest.properties,
                                            name: res.building.name,
                                            usage: res.building.usage,
                                            measuredHeight: res.building.measured_height,
                                        },
                                    };
                                    metadataCache.set(buildingFromRequest.gmlId, enriched);
                                }
                            });

                            console.log(
                                `[PlateauCesiumPickerDialog] Cached metadata for ${result.value.total_success}/${needsMetadata.length} buildings`,
                            );
                        } else {
                            console.warn(
                                "[PlateauCesiumPickerDialog] Batch metadata fetch failed:",
                                result.error,
                            );
                        }
                    } catch (error) {
                        console.error("[PlateauCesiumPickerDialog] Metadata fetch error:", error);
                    } finally {
                        loadingIndicator.style.display = "none";
                    }
                }

                // Merge cached metadata into selected buildings
                const enrichedSelected = selected.map((b) => {
                    const cached = metadataCache.get(b.gmlId);
                    if (cached) {
                        return {
                            ...b,
                            properties: {
                                ...b.properties,
                                ...cached.properties,
                            },
                        };
                    }
                    return b;
                });

                closeDialog(DialogResult.ok, { selectedBuildings: enrichedSelected });
            },
        });

        // Main content layout
        const content = div(
            {
                style: {
                    display: "flex",
                    flexDirection: "column",
                    gap: "0px",
                    width: "1200px",
                    maxWidth: "90vw",
                },
            },
            // Search tabs
            searchTabsContainer,
            // Mesh indicator
            meshIndicator,
            // Viewer + Selected panel
            div(
                {
                    style: {
                        display: "flex",
                        height: "600px",
                        border: "1px solid var(--border-color)",
                        borderRadius: "var(--radius-sm)",
                        overflow: "hidden",
                    },
                },
                viewerContainer,
                selectedPanelContainer,
            ),
        );

        const closeDialog = (result: DialogResult, data?: PlateauCesiumPickerResult) => {
            // Cleanup
            if (clickHandler) {
                clickHandler.destroy();
            }
            if (cesiumView) {
                cesiumView.dispose();
            }

            dialog.remove();
            callback?.(result, data);
        };

        // Dialog structure
        dialog.appendChild(
            div(
                { className: style.root },
                div({ className: style.title }, "PLATEAU Cesium 3D Tiles - Building Picker"),
                div({ className: style.content }, content),
                div(
                    { className: style.buttons },
                    importButton,
                    button({
                        textContent: I18n.translate("common.cancel"),
                        onclick: () => closeDialog(DialogResult.cancel),
                    }),
                ),
            ),
        );

        // Initialize Cesium after dialog is shown
        dialog.addEventListener("close", () => closeDialog(DialogResult.cancel));

        dialog.showModal();

        // Initialize Cesium viewer
        setTimeout(async () => {
            try {
                // Initialize Cesium view
                cesiumView = new CesiumView(viewerContainer);
                cesiumView.initialize();

                const viewer = cesiumView.getViewer();
                if (!viewer) {
                    throw new Error("Failed to initialize Cesium viewer");
                }

                // Initialize loader and picker
                tilesetLoader = new CesiumTilesetLoader(viewer);
                buildingPicker = new CesiumBuildingPicker(viewer);

                // Setup click handler with drag detection (Phase 1.1)
                clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);

                // Camera motion listener (Phase 1.2)
                viewer.camera.moveStart.addEventListener(() => {
                    if (mouseDownPosition !== null) {
                        isCameraMoving = true;
                    }
                });

                // LEFT_DOWN: Store mouse position
                clickHandler.setInputAction((movement: any) => {
                    mouseDownPosition = {
                        x: movement.position.x,
                        y: movement.position.y,
                    };
                    isCameraMoving = false;
                }, Cesium.ScreenSpaceEventType.LEFT_DOWN);

                // LEFT_UP: Check drag distance before picking
                clickHandler.setInputAction((movement: any) => {
                    if (!buildingPicker || !mouseDownPosition) return;

                    const upPosition = movement.position;
                    const dx = upPosition.x - mouseDownPosition.x;
                    const dy = upPosition.y - mouseDownPosition.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    // Ignore if dragged beyond threshold
                    if (distance > DRAG_THRESHOLD_PX) {
                        mouseDownPosition = null;
                        return;
                    }

                    // Ignore if camera was moving
                    if (isCameraMoving) {
                        mouseDownPosition = null;
                        isCameraMoving = false;
                        return;
                    }

                    const multiSelect = movement.modifier === Cesium.KeyboardEventModifier.CTRL;

                    try {
                        buildingPicker.pickBuilding(upPosition, multiSelect);

                        // Check if disambiguation is needed (Phase 5.2)
                        const candidates = buildingPicker.getLastCandidates();
                        if (candidates.length > 1) {
                            // Show disambiguation popup
                            showCandidatePopup(candidates, upPosition, multiSelect);
                        } else {
                            // Single or no candidate - update panel normally
                            updateSelectedPanel();
                        }
                    } catch (error) {
                        if (error instanceof Error) {
                            PubSub.default.pub(
                                "showToast",
                                "error.plateau.selectionFailed:{0}",
                                error.message,
                            );
                        }
                    }

                    mouseDownPosition = null;
                }, Cesium.ScreenSpaceEventType.LEFT_UP);

                // Set initial camera position (Japan overview)
                viewer.camera.setView({
                    destination: Cesium.Cartesian3.fromDegrees(
                        138.0, // Japan center longitude
                        36.0, // Japan center latitude
                        1500000, // Altitude (m)
                    ),
                });

                // Focus on address search input
                const addressInput = dialog.querySelector("#address-input") as HTMLInputElement;
                if (addressInput) {
                    addressInput.focus();
                }
            } catch (error) {
                console.error("[PlateauCesiumPickerDialog] Initialization error:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.cesiumInitFailed:{0}",
                    error instanceof Error ? error.message : String(error),
                );
            }
        }, 100); // Delay to ensure container is rendered

        // Handle keyboard
        const handleKeydown = (e: KeyboardEvent) => {
            e.stopPropagation();
            if (e.key === "Escape") {
                e.preventDefault();
                closeDialog(DialogResult.cancel);
            }
        };

        dialog.addEventListener("keydown", handleKeydown);
        dialog.addEventListener("click", (e) => {
            e.stopPropagation();
        });
    }
}
