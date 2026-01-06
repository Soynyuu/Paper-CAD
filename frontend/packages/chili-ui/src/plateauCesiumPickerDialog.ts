// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, label, select } from "chili-controls";
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
    getAllCities,
    getCityConfig,
    type PickedBuilding,
    type CityConfig,
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

        // Disambiguation popup state (Phase 5.2)
        let candidatePopup: HTMLElement | null = null;

        // Metadata cache (Phase 6.3)
        const metadataCache = new Map<string, PickedBuilding>();

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

        // City selector dropdown
        const cities = getAllCities();
        const cityOptions = cities.map((city: CityConfig) => ({
            value: city.key,
            text: city.name,
        }));

        const citySelectElement = select(
            {
                style: {
                    width: "100%",
                    padding: "8px",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--font-size-sm)",
                    marginBottom: "12px",
                },
                onchange: async (e) => {
                    const cityKey = (e.target as HTMLSelectElement).value;
                    await loadCity(cityKey);
                },
            },
            ...cityOptions.map((opt: { value: string; text: string }) =>
                Object.assign(document.createElement("option"), {
                    value: opt.value,
                    textContent: opt.text,
                }),
            ),
        );

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
         * Load city tileset
         */
        const loadCity = async (cityKey: string) => {
            const cityConfig = getCityConfig(cityKey);
            if (!cityConfig) {
                PubSub.default.pub("showToast", "error.plateau.cityNotFound:{0}", cityKey);
                return;
            }

            try {
                // Show loading
                loadingIndicator.style.display = "block";

                // Clear previous selection
                if (buildingPicker) {
                    buildingPicker.clearSelection();
                }

                // Load tileset
                if (tilesetLoader && cesiumView) {
                    await tilesetLoader.loadTileset(cityConfig.tilesetUrl);

                    // Fly to city
                    cesiumView.flyToCity(cityConfig);
                }

                // Update panel
                updateSelectedPanel();
            } catch (error) {
                console.error("[PlateauCesiumPickerDialog] Failed to load city:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.cityLoadFailed:{0}:{1}",
                    cityConfig.name,
                    error instanceof Error ? error.message : String(error),
                );
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
                        const baseUrl =
                            (window as any).__APP_CONFIG__?.stepUnfoldApiUrl ||
                            "https://backend-paper-cad.soynyuu.com/api";

                        // Fetch batch
                        const citygmlService = new CityGMLService(baseUrl);
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
                    gap: "12px",
                    width: "1200px",
                    maxWidth: "90vw",
                },
            },
            // City selector
            div(
                { style: { display: "flex", flexDirection: "column", gap: "4px" } },
                label(
                    { style: { fontSize: "var(--font-size-sm)", fontWeight: "500" } },
                    I18n.translate("plateau.cesium.selectCity"),
                ),
                citySelectElement,
            ),
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

                // Load first city
                if (cities.length > 0) {
                    await loadCity(cities[0].key);
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
