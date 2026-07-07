// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { I18n } from "chili-core";
import type { PickedBuilding } from "chili-cesium";
import { BuildingCard } from "./BuildingCard";
import {
    ScrollArea,
    ScrollAreaContent,
    ScrollAreaThumb,
    ScrollAreaViewport,
    ScrollBar,
} from "./ui/scroll-area";
import { Button } from "./ui/button";
import styles from "./Sidebar.module.css";

export interface SidebarProps {
    selectedBuildings: PickedBuilding[];
    onRemove: (gmlId: string) => void;
    onImport: () => void;
    onUnfoldBeta: () => void;
    onClear: () => void;
}

/**
 * Sidebar - Right panel displaying selected buildings and actions
 *
 * Shows list of selected buildings with remove buttons.
 * Footer includes Import and Clear buttons.
 */
export function Sidebar({ selectedBuildings, onRemove, onImport, onUnfoldBeta, onClear }: SidebarProps) {
    const count = selectedBuildings.length;
    const canImport = count > 0;

    return (
        <div className={styles.sidebar}>
            {/* Header */}
            <div className={styles.sidebarHeader}>
                {count > 0 ? (
                    <div className={styles.selectionCount}>{`選択 ${count}`}</div>
                ) : (
                    <div className={styles.emptyHeader}>未選択</div>
                )}
            </div>

            <ScrollArea className={styles.sidebarList}>
                <ScrollAreaViewport className={styles.sidebarViewport}>
                    <ScrollAreaContent className={styles.sidebarContent}>
                        {count === 0 ? (
                            <div className={styles.emptyState}>
                                <div>{I18n.translate("plateau.cesium.clickToSelectBuilding")}</div>
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
                    </ScrollAreaContent>
                </ScrollAreaViewport>
                <ScrollBar className={styles.scrollbar}>
                    <ScrollAreaThumb className={styles.scrollThumb} />
                </ScrollBar>
            </ScrollArea>

            {/* Footer */}
            <div className={styles.sidebarFooter}>
                <Button
                    className={styles.importButton}
                    onClick={onImport}
                    disabled={!canImport}
                    type="button"
                >
                    {I18n.translate("plateau.cesium.importSelected")}
                </Button>
                <Button
                    variant="outline"
                    className={styles.unfoldBetaButton}
                    onClick={onUnfoldBeta}
                    disabled={!canImport}
                    type="button"
                >
                    展開図
                </Button>
                <Button
                    variant="ghost"
                    className={styles.clearButton}
                    onClick={onClear}
                    disabled={!canImport}
                    type="button"
                >
                    {I18n.translate("plateau.cesium.clearSelection")}
                </Button>
            </div>
        </div>
    );
}
