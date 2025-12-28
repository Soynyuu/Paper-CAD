// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, select } from "chili-controls";
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
import style from "./plateauCesiumPickerDialog.module.css";

export interface PlateauCesiumPickerResult {
    selectedBuildings: PickedBuilding[];
}

/**
 * PlateauCesiumPickerDialog
 *
 * Interactive dialog for picking PLATEAU buildings from Cesium 3D Tiles.
 * Implements an "Immersive Map & Sidebar" layout.
 *
 * Automatically uses React-based picker if USE_REACT_CESIUM_PICKER feature flag is enabled.
 */
export class PlateauCesiumPickerDialog {
    private constructor() {}

    static show(
        app: IApplication,
        callback?: (result: DialogResult, data?: PlateauCesiumPickerResult) => void,
    ) {
        // Check feature flag for React-based picker
        if (__APP_CONFIG__.useReactCesiumPicker) {
            return PlateauCesiumPickerDialog.showReact(callback);
        }

        // Legacy Web Components implementation
        const dialog = document.createElement("dialog");
        dialog.className = style.dialog;
        document.body.appendChild(dialog);

        // State
        let cesiumView: CesiumView | null = null;
        let tilesetLoader: CesiumTilesetLoader | null = null;
        let buildingPicker: CesiumBuildingPicker | null = null;
        let clickHandler: Cesium.ScreenSpaceEventHandler | null = null;

        // --- Components ---

        // 1. Map Container (Left/Main)
        const viewerContainer = div({ className: style.mapContainer });

        // Instructions Overlay
        const instructionsOverlay = div(
            { className: style.instructions },
            div(
                { className: style.instructionsTitle },
                div({
                    style: {
                        display: "inline-block",
                        width: "8px",
                        height: "8px",
                        backgroundColor: "#4CAF50",
                        borderRadius: "50%",
                    },
                }), // Status dot
                I18n.translate("plateau.cesium.clickToSelect"),
            ),
            div(I18n.translate("plateau.cesium.instructions.click")),
            div(I18n.translate("plateau.cesium.instructions.ctrlClick")),
            div(I18n.translate("plateau.cesium.instructions.clearArea")),
        );
        viewerContainer.appendChild(instructionsOverlay);

        // Loading Indicator
        const loadingIndicator = div(
            { className: style.loading, style: { display: "none" } },
            I18n.translate("plateau.cesium.loading"),
        );
        viewerContainer.appendChild(loadingIndicator);

        // 2. Sidebar (Right)
        const sidebarList = div({ className: style.sidebarList });
        const sidebarHeader = div({ className: style.sidebarHeader }); // Will hold count

        // Import Button (Sidebar Footer)
        const importButton = button({
            className: style.importButton,
            textContent: I18n.translate("plateau.cesium.importSelected"),
            disabled: true,
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

        // Clear Button (Sidebar Footer)
        const clearButton = button({
            className: style.clearButton,
            textContent: I18n.translate("plateau.cesium.clearSelection"),
            style: { display: "none" }, // Hidden initially
            onclick: () => {
                if (buildingPicker) {
                    buildingPicker.clearSelection();
                    updateSelectedPanel();
                }
            },
        });

        const sidebarFooter = div({ className: style.sidebarFooter }, importButton, clearButton);

        const sidebar = div({ className: style.sidebar }, sidebarHeader, sidebarList, sidebarFooter);

        // 3. Header Controls (City Selector + Close)
        const cities = getAllCities();
        const cityOptions = cities.map((city: CityConfig) => ({
            value: city.key,
            text: city.name,
        }));

        const citySelectElement = select(
            {
                className: style.citySelect,
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

        const closeButton = button({
            className: style.closeButton,
            innerHTML: `<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M14 1.41L12.59 0L7 5.59L1.41 0L0 1.41L5.59 7L0 12.59L1.41 14L7 8.41L12.59 14L14 12.59L8.41 7L14 1.41Z"/></svg>`,
            onclick: () => closeDialog(DialogResult.cancel),
        });

        const header = div(
            { className: style.header },
            div({ className: style.title }, "Building Picker"),
            div({ className: style.headerControls }, citySelectElement, closeButton),
        );

        // --- Logic Functions ---

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
                loadingIndicator.style.display = "flex";

                if (buildingPicker) buildingPicker.clearSelection();

                if (tilesetLoader && cesiumView) {
                    await tilesetLoader.loadTileset(cityConfig.tilesetUrl);
                    cesiumView.flyToCity(cityConfig);
                }

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
         * Create building card
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

            const removeBtn = button({
                className: style.removeButton,
                textContent: "×",
                title: I18n.translate("items.tool.delete"),
                onclick: (e) => {
                    e.stopPropagation();
                    if (buildingPicker) {
                        buildingPicker.removeBuilding(building.gmlId);
                        updateSelectedPanel();
                    }
                },
            });

            return div(
                { className: style.buildingCard },
                div(
                    { className: style.cardHeader },
                    div(
                        { className: style.buildingName },
                        `#${index + 1} ${building.properties.name || "Unnamed Building"}`,
                    ),
                    removeBtn,
                ),
                div({ className: style.cardDetail }, div(`${height.toFixed(1)}m`), div(usageLabel)),
                div({ className: style.cardId }, `ID: ${building.gmlId}`),
            );
        };

        /**
         * Update sidebar
         */
        const updateSelectedPanel = () => {
            if (!buildingPicker) return;

            sidebarList.innerHTML = "";
            const selected = buildingPicker.getSelectedBuildings();
            const count = selected.length;

            // Update Header
            sidebarHeader.innerHTML = "";
            if (count > 0) {
                sidebarHeader.appendChild(
                    div(
                        {
                            style: {
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                            },
                        },
                        div("Selected Buildings"),
                        div({ className: style.selectionCount }, `${count}`),
                    ),
                );
            } else {
                sidebarHeader.textContent = "Selection";
            }

            // Update List
            if (count === 0) {
                sidebarList.appendChild(
                    div(
                        { className: style.emptyState },
                        div({
                            innerHTML: `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.3;"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>`,
                        }),
                        div(I18n.translate("plateau.cesium.noBuildingsSelected")),
                    ),
                );
            } else {
                selected.forEach((b, i) => {
                    sidebarList.appendChild(createBuildingCard(b, i));
                });
            }

            // Update Footer Buttons
            importButton.disabled = count === 0;
            importButton.textContent =
                count > 0
                    ? `${I18n.translate("plateau.cesium.importSelected")} (${count})`
                    : I18n.translate("plateau.cesium.importSelected");

            clearButton.style.display = count > 0 ? "block" : "none";
        };

        // --- Assembly ---

        const body = div({ className: style.body }, viewerContainer, sidebar);

        dialog.appendChild(header);
        dialog.appendChild(body);

        // --- Dialog Lifecycle ---

        const closeDialog = (result: DialogResult, data?: PlateauCesiumPickerResult) => {
            if (clickHandler) clickHandler.destroy();
            if (buildingPicker) buildingPicker.dispose();
            if (cesiumView) cesiumView.dispose();
            dialog.remove();
            callback?.(result, data);
        };

        dialog.addEventListener("close", () => closeDialog(DialogResult.cancel));
        dialog.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                e.preventDefault();
                closeDialog(DialogResult.cancel);
            }
        });

        dialog.showModal();

        // Initialize Cesium
        setTimeout(async () => {
            try {
                cesiumView = new CesiumView(viewerContainer);
                cesiumView.initialize();

                const viewer = cesiumView.getViewer();
                if (!viewer) throw new Error("Failed to initialize Cesium viewer");

                tilesetLoader = new CesiumTilesetLoader(viewer);
                buildingPicker = new CesiumBuildingPicker(viewer);

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

                // Initial Load
                if (cities.length > 0) {
                    await loadCity(cities[0].key);
                }
                updateSelectedPanel(); // Init empty state
            } catch (error) {
                console.error("[PlateauCesiumPickerDialog] Initialization error:", error);
                PubSub.default.pub(
                    "showToast",
                    "error.plateau.cesiumInitFailed:{0}",
                    error instanceof Error ? error.message : String(error),
                );
            }
        }, 100);
    }

    /**
     * Show React-based Cesium picker (when feature flag enabled)
     */
    private static showReact(callback?: (result: DialogResult, data?: PlateauCesiumPickerResult) => void) {
        // Lazy load React components to avoid bundling when not used
        import("./react").then(({ PlateauCesiumPickerReact, renderReactDialog }) => {
            const cleanup = renderReactDialog(PlateauCesiumPickerReact, {
                onClose: (result, data) => {
                    cleanup();
                    if (callback) {
                        callback(result, data);
                    }
                },
            });
        });
    }
}
