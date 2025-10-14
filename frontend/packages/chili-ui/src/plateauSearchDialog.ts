// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, label } from "chili-controls";
import { DialogResult, I18n, IApplication } from "chili-core";
import style from "./dialog.module.css";

export interface PlateauSearchOptions {
    query: string;
    radius: number;
    buildingLimit: number;
    autoReproject: boolean;
    mergeBuildingParts: boolean;
}

export class PlateauSearchDialog {
    private constructor() {}

    static show(
        app: IApplication,
        callback?: (result: DialogResult, options?: PlateauSearchOptions) => void,
    ) {
        const dialog = document.createElement("dialog");
        document.body.appendChild(dialog);

        // State for form inputs
        let query = "";
        let radius = 0.001; // ~100m default
        let buildingLimit = 1;
        let autoReproject = true;
        let mergeBuildingParts = false;

        // Create form inputs
        const queryInput = input({
            type: "text",
            placeholder: I18n.translate("plateau.searchQuery") ?? "Address or Facility Name",
            style: {
                width: "100%",
                padding: "8px",
                marginTop: "8px",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--font-size-sm)",
            },
            oninput: (e) => {
                query = (e.target as HTMLInputElement).value;
            },
        });

        const radiusInput = input({
            type: "number",
            value: "0.001",
            step: "0.0001",
            min: "0.0001",
            max: "0.01",
            style: {
                width: "100%",
                padding: "8px",
                marginTop: "8px",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--font-size-sm)",
            },
            oninput: (e) => {
                radius = parseFloat((e.target as HTMLInputElement).value);
            },
        });

        const buildingLimitInput = input({
            type: "number",
            value: "1",
            min: "1",
            max: "10",
            style: {
                width: "100%",
                padding: "8px",
                marginTop: "8px",
                border: "1px solid var(--border-color)",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--font-size-sm)",
            },
            oninput: (e) => {
                buildingLimit = parseInt((e.target as HTMLInputElement).value);
            },
        });

        const autoReprojectCheckbox = input({
            type: "checkbox",
            checked: true,
            style: {
                marginLeft: "8px",
                cursor: "pointer",
            },
            onchange: (e) => {
                autoReproject = (e.target as HTMLInputElement).checked;
            },
        });

        const mergeBuildingPartsCheckbox = input({
            type: "checkbox",
            checked: false,
            style: {
                marginLeft: "8px",
                cursor: "pointer",
            },
            onchange: (e) => {
                mergeBuildingParts = (e.target as HTMLInputElement).checked;
            },
        });

        const content = div(
            {
                style: {
                    minWidth: "400px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                },
            },
            div(
                {},
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                        },
                    },
                    I18n.translate("plateau.searchQuery") ?? "Address or Facility Name",
                ),
                queryInput,
                div(
                    {
                        style: {
                            fontSize: "var(--font-size-xs)",
                            color: "var(--neutral-600)",
                            marginTop: "4px",
                        },
                    },
                    'e.g. "東京駅", "渋谷スクランブルスクエア", "東京都千代田区丸の内1-9-1"',
                ),
            ),
            div(
                {},
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                        },
                    },
                    I18n.translate("plateau.searchRadius") ?? "Search Radius",
                ),
                radiusInput,
                div(
                    {
                        style: {
                            fontSize: "var(--font-size-xs)",
                            color: "var(--neutral-600)",
                            marginTop: "4px",
                        },
                    },
                    "Default: 0.001 degrees (~100m)",
                ),
            ),
            div(
                {},
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                        },
                    },
                    I18n.translate("plateau.buildingLimit") ?? "Building Limit",
                ),
                buildingLimitInput,
                div(
                    {
                        style: {
                            fontSize: "var(--font-size-xs)",
                            color: "var(--neutral-600)",
                            marginTop: "4px",
                        },
                    },
                    "Number of buildings to import (1-10)",
                ),
            ),
            div(
                {
                    style: {
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                    },
                },
                autoReprojectCheckbox,
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            autoReprojectCheckbox.checked = !autoReprojectCheckbox.checked;
                            autoReproject = autoReprojectCheckbox.checked;
                        },
                    },
                    I18n.translate("plateau.autoReproject") ?? "Auto Reproject",
                ),
            ),
            div(
                {
                    style: {
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                    },
                },
                mergeBuildingPartsCheckbox,
                label(
                    {
                        style: {
                            fontWeight: "var(--font-weight-medium)",
                            fontSize: "var(--font-size-sm)",
                            color: "var(--foreground-color)",
                            cursor: "pointer",
                        },
                        onclick: () => {
                            mergeBuildingPartsCheckbox.checked = !mergeBuildingPartsCheckbox.checked;
                            mergeBuildingParts = mergeBuildingPartsCheckbox.checked;
                        },
                    },
                    I18n.translate("plateau.mergeBuildingParts") ?? "Merge Building Parts",
                ),
            ),
        );

        const closeDialog = (result: DialogResult) => {
            if (result === DialogResult.ok) {
                // Validate query
                if (!query.trim()) {
                    alert(
                        I18n.translate("error.plateau.emptyQuery") ??
                            "Please enter an address or facility name",
                    );
                    return; // Don't close dialog if validation fails
                }

                dialog.remove();
                callback?.(DialogResult.ok, {
                    query: query.trim(),
                    radius,
                    buildingLimit,
                    autoReproject,
                    mergeBuildingParts,
                });
            } else {
                dialog.remove();
                callback?.(DialogResult.cancel);
            }
        };

        dialog.appendChild(
            div(
                { className: style.root },
                div(
                    { className: style.title },
                    I18n.translate("command.file.importCityGMLByAddress") ?? "Import from Address",
                ),
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
            // Stop event propagation to prevent background shortcuts from triggering
            e.stopPropagation();

            if (e.key === "Escape") {
                e.preventDefault();
                closeDialog(DialogResult.cancel);
            } else if (e.key === "Enter" && !e.isComposing && e.target === queryInput) {
                // Allow Enter to submit from the query input (but not during IME composition)
                e.preventDefault();
                closeDialog(DialogResult.ok);
            }
        };

        dialog.addEventListener("keydown", handleKeydown);

        // Prevent click events from propagating to background
        dialog.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        dialog.showModal();

        // Focus on the first input
        setTimeout(() => {
            queryInput.focus();
        }, 100);
    }
}
