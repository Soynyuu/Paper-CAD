// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, label } from "chili-controls";
import { DialogResult, I18n, IApplication } from "chili-core";
import style from "./dialog.module.css";

export interface BuildingCandidate {
    gml_id: string;
    measured_height?: number;
    height?: number;
    distance_meters: number;
    usage?: string;
    building_structure_type?: string;
    has_lod2: boolean;
    has_lod3: boolean;
    name?: string;
}

export interface PlateauBuildingSelection {
    selectedBuildingIds: string[];
}

export class PlateauBuildingSelectionDialog {
    private constructor() {}

    static show(
        app: IApplication,
        buildings: BuildingCandidate[],
        callback?: (result: DialogResult, selection?: PlateauBuildingSelection) => void,
    ) {
        const dialog = document.createElement("dialog");
        document.body.appendChild(dialog);

        // State: selected building IDs
        const selectedIds = new Set<string>();

        // Usage code translations (common PLATEAU codes)
        const usageCodeMap: Record<string, string> = {
            "401": "業務施設 (Office)",
            "402": "商業施設 (Commercial)",
            "411": "宿泊施設 (Hotel)",
            "421": "文教厚生施設 (Educational/Welfare)",
            "431": "運動施設 (Sports)",
            "441": "公共施設 (Public)",
            "451": "工場 (Factory)",
            "461": "運輸倉庫施設 (Transport/Warehouse)",
            "471": "供給処理施設 (Utility)",
        };

        const getUsageLabel = (usage?: string): string => {
            if (!usage) return "N/A";
            return usageCodeMap[usage] || usage;
        };

        const createBuildingRow = (building: BuildingCandidate, index: number): HTMLElement => {
            const height = building.measured_height || building.height || 0;
            const lodBadge = building.has_lod3 ? "LOD3" : building.has_lod2 ? "LOD2" : "LOD1";
            const lodColor = building.has_lod3 ? "#10b981" : building.has_lod2 ? "#3b82f6" : "#94a3b8";

            const checkbox = input({
                type: "checkbox",
                id: `building-${index}`,
                style: {
                    cursor: "pointer",
                    width: "16px",
                    height: "16px",
                },
                onchange: (e) => {
                    const checked = (e.target as HTMLInputElement).checked;
                    if (checked) {
                        selectedIds.add(building.gml_id);
                    } else {
                        selectedIds.delete(building.gml_id);
                    }
                },
            });

            return div(
                {
                    style: {
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "12px",
                        border: "1px solid var(--border-color)",
                        borderRadius: "var(--radius-sm)",
                        backgroundColor: "var(--neutral-100)",
                        cursor: "pointer",
                        transition: "background-color 0.2s",
                    },
                    onmouseover: (e) => {
                        (e.currentTarget as HTMLElement).style.backgroundColor = "var(--neutral-200)";
                    },
                    onmouseout: (e) => {
                        (e.currentTarget as HTMLElement).style.backgroundColor = "var(--neutral-100)";
                    },
                    onclick: () => {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(new Event("change"));
                    },
                },
                checkbox,
                div(
                    {
                        style: {
                            flex: "1",
                            display: "flex",
                            flexDirection: "column",
                            gap: "4px",
                        },
                    },
                    div(
                        {
                            style: {
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                                fontSize: "var(--font-size-sm)",
                                fontWeight: "var(--font-weight-medium)",
                                color: "var(--foreground-color)",
                            },
                        },
                        building.name
                            ? `#${index + 1}: ${building.name} (${height.toFixed(1)}m, ${building.distance_meters.toFixed(1)}m away)`
                            : `#${index + 1}: ${height.toFixed(1)}m tall, ${building.distance_meters.toFixed(1)}m away`,
                        div(
                            {
                                style: {
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    backgroundColor: lodColor,
                                    color: "white",
                                    fontSize: "10px",
                                    fontWeight: "600",
                                },
                            },
                            lodBadge,
                        ),
                    ),
                    div(
                        {
                            style: {
                                fontSize: "var(--font-size-xs)",
                                color: "var(--neutral-600)",
                            },
                        },
                        `Usage: ${getUsageLabel(building.usage)}`,
                    ),
                    div(
                        {
                            style: {
                                fontSize: "var(--font-size-xs)",
                                color: "var(--neutral-500)",
                                fontFamily: "monospace",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                            },
                        },
                        `ID: ${building.gml_id.substring(0, 40)}...`,
                    ),
                ),
            );
        };

        const buildingList = div(
            {
                style: {
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    maxHeight: "400px",
                    overflowY: "auto",
                    padding: "4px",
                },
            },
            ...buildings.map((building, index) => createBuildingRow(building, index)),
        );

        const content = div(
            {
                style: {
                    minWidth: "500px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                },
            },
            div(
                {
                    style: {
                        fontSize: "var(--font-size-sm)",
                        color: "var(--neutral-700)",
                        padding: "8px",
                        backgroundColor: "var(--neutral-50)",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-color)",
                    },
                },
                `Found ${buildings.length} building(s). Select one or more buildings to import:`,
            ),
            buildingList,
        );

        const closeDialog = (result: DialogResult) => {
            if (result === DialogResult.ok) {
                // Validate selection
                if (selectedIds.size === 0) {
                    alert("Please select at least one building to import.");
                    return; // Don't close dialog if no selection
                }

                dialog.remove();
                callback?.(DialogResult.ok, {
                    selectedBuildingIds: Array.from(selectedIds),
                });
            } else {
                dialog.remove();
                callback?.(DialogResult.cancel);
            }
        };

        dialog.appendChild(
            div(
                { className: style.root },
                div({ className: style.title }, "Select Buildings to Import"),
                div({ className: style.content }, content),
                div(
                    { className: style.buttons },
                    button({
                        textContent: I18n.translate("common.confirm"),
                        onclick: () => closeDialog(DialogResult.ok),
                    }),
                    button({
                        textContent: I18n.translate("common.cancel"),
                        onclick: () => closeDialog(DialogResult.cancel),
                    }),
                ),
            ),
        );

        // Handle keyboard shortcuts
        const handleKeydown = (e: KeyboardEvent) => {
            e.stopPropagation();
            if (e.key === "Escape") {
                e.preventDefault();
                closeDialog(DialogResult.cancel);
            } else if (e.key === "Enter") {
                e.preventDefault();
                closeDialog(DialogResult.ok);
            }
        };

        dialog.addEventListener("keydown", handleKeydown);
        dialog.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        dialog.showModal();
    }
}
