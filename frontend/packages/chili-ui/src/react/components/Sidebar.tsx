// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { I18n } from "chili-core";
import type { PickedBuilding } from "chili-cesium";
import { BuildingCard } from "./BuildingCard";
import styles from "./Sidebar.module.css";

export interface SidebarProps {
    selectedBuildings: PickedBuilding[];
    onRemove: (gmlId: string) => void;
    onImport: () => void;
    onClear: () => void;
}

/**
 * Sidebar - Right panel displaying selected buildings and actions
 *
 * Shows list of selected buildings with remove buttons.
 * Footer includes Import and Clear buttons.
 */
export function Sidebar({ selectedBuildings, onRemove, onImport, onClear }: SidebarProps) {
    const count = selectedBuildings.length;
    const canImport = count > 0;

    return (
        <div className={styles.sidebar}>
            {/* Header */}
            <div className={styles.sidebarHeader}>
                {count > 0 ? (
                    <div className={styles.selectionCount}>{`Selected: ${count}`}</div>
                ) : (
                    <div className={styles.emptyHeader}>{I18n.translate("plateau.cesium.noSelection")}</div>
                )}
            </div>

            {/* Building List */}
            <div className={styles.sidebarList}>
                {count === 0 ? (
                    <div className={styles.emptyState}>
                        <div>{I18n.translate("plateau.cesium.clickToSelectBuilding")}</div>
                        <div style={{ fontSize: "10px", opacity: 0.7 }}>
                            {I18n.translate("plateau.cesium.ctrlClickForMultiple")}
                        </div>
                    </div>
                ) : (
                    selectedBuildings.map((building, index) => (
                        <BuildingCard
                            key={building.gmlId}
                            building={building}
                            index={index}
                            onRemove={onRemove}
                        />
                    ))
                )}
            </div>

            {/* Footer */}
            <div className={styles.sidebarFooter}>
                <button
                    className={styles.importButton}
                    onClick={onImport}
                    disabled={!canImport}
                    type="button"
                >
                    {I18n.translate("plateau.cesium.importSelected")}
                </button>
                <button className={styles.clearButton} onClick={onClear} disabled={!canImport} type="button">
                    {I18n.translate("plateau.cesium.clearSelection")}
                </button>
            </div>
        </div>
    );
}
