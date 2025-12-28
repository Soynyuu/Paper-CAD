// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, label, select } from "chili-controls";
import { DialogResult, I18n, IApplication, PubSub } from "chili-core";
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
            div(I18n.translate("plateau.cesium.instructions.click")),
            div(I18n.translate("plateau.cesium.instructions.ctrlClick")),
            div(I18n.translate("plateau.cesium.instructions.clearArea")),
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
            I18n.translate("plateau.cesium.loading"),
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
                        I18n.translate("plateau.cesium.noBuildingsSelected"),
                    ),
                );
            } else {
                selected.forEach((building: PickedBuilding, index: number) => {
                    selectedPanelContainer.appendChild(createBuildingCard(building, index));
                });
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
            onclick: () => {
                if (!buildingPicker) return;

                const selected = buildingPicker.getSelectedBuildings();
                if (selected.length === 0) {
                    PubSub.default.pub("showToast", "error.plateau.selectAtLeastOne");
                    return;
                }

                closeDialog(DialogResult.ok, { selectedBuildings: selected });
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
            if (buildingPicker) {
                buildingPicker.dispose();
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
        // NOTE: setTimeout ensures the dialog container is fully rendered before Cesium initialization.
        // For PoC stage, 100ms is acceptable. In production, consider using requestAnimationFrame()
        // or IntersectionObserver for better reliability across devices.
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

                // Setup click handler
                clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
                clickHandler.setInputAction((click: any) => {
                    if (!buildingPicker) return;

                    const multiSelect = click.modifier === Cesium.KeyboardEventModifier.CTRL;

                    try {
                        buildingPicker.pickBuilding(click.position, multiSelect);
                        updateSelectedPanel();
                    } catch (error) {
                        if (error instanceof Error) {
                            PubSub.default.pub(
                                "showToast",
                                "error.plateau.selectionFailed:{0}",
                                error.message,
                            );
                        }
                    }
                }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

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
