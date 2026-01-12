// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { I18n } from "chili-core";
import styles from "./Instructions.module.css";

/**
 * Instructions - Overlay showing interaction instructions
 *
 * Displayed in the bottom-left corner of the map.
 * Provides guidance on how to select buildings.
 */
export function Instructions() {
    return (
        <div className={styles.instructions}>
            <div className={styles.instructionsTitle}>
                <span className={styles.statusDot} />
                {I18n.translate("plateau.cesium.clickToSelect")}
            </div>
            <div>{I18n.translate("plateau.cesium.instructions.click")}</div>
            <div>{I18n.translate("plateau.cesium.instructions.ctrlClick")}</div>
        </div>
    );
}
