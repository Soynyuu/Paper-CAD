// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { Tooltip } from "@base-ui/react/tooltip";
import { X } from "lucide-react";
import { I18n } from "chili-core";
import type { PickedBuilding } from "chili-cesium";
import { Button } from "./ui/button";
import styles from "./BuildingCard.module.css";

export interface BuildingCardProps {
    building: PickedBuilding;
    index: number;
    onRemove: (gmlId: string) => void;
}

// PLATEAU usage code to Japanese label mapping
const USAGE_CODE_MAP: Record<string, string> = {
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

/**
 * BuildingCard - Displays information about a selected building
 *
 * Shows building name, height, usage type, and GML ID.
 * Includes a remove button to deselect the building.
 */
export function BuildingCard({ building, index, onRemove }: BuildingCardProps) {
    const height = building.properties.measuredHeight || 0;
    const usageLabel = building.properties.usage
        ? USAGE_CODE_MAP[building.properties.usage] || building.properties.usage
        : "用途未設定";

    const handleRemove = (e: React.MouseEvent) => {
        e.stopPropagation();
        onRemove(building.gmlId);
    };

    return (
        <div className={styles.buildingCard}>
            <div className={styles.cardHeader}>
                <div className={styles.buildingName}>
                    {building.properties.name || `建物 ${index + 1}`}
                </div>
                <Tooltip.Root>
                    <Tooltip.Trigger
                        render={
                            <Button
                                variant="ghost"
                                size="icon"
                                className={styles.removeButton}
                                onClick={handleRemove}
                                type="button"
                                aria-label={`Remove ${building.properties.name || "building"}`}
                            />
                        }
                    >
                        <X aria-hidden="true" />
                    </Tooltip.Trigger>
                    <Tooltip.Portal>
                        <Tooltip.Positioner sideOffset={8}>
                            <Tooltip.Popup className={styles.tooltipPopup}>
                                {I18n.translate("items.tool.delete")}
                            </Tooltip.Popup>
                        </Tooltip.Positioner>
                    </Tooltip.Portal>
                </Tooltip.Root>
            </div>
            <div className={styles.cardDetail}>
                <div>{height.toFixed(1)}m</div>
                <div>{usageLabel}</div>
            </div>
            <div className={styles.cardId}>{building.gmlId}</div>
        </div>
    );
}
