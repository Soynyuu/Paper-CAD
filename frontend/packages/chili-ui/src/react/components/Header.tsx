// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { I18n } from "chili-core";
import { CitySelector } from "./CitySelector";
import styles from "./Header.module.css";

export interface HeaderProps {
    currentCity: string;
    onCityChange: (cityKey: string) => void;
    onClose: () => void;
    loading?: boolean;
}

/**
 * Header - Top bar of the Cesium picker dialog
 *
 * Contains title, city selector, and close button.
 */
export function Header({ currentCity, onCityChange, onClose, loading = false }: HeaderProps) {
    return (
        <div className={styles.header}>
            <h2 className={styles.title}>Building Picker</h2>
            <div className={styles.headerControls}>
                <CitySelector currentCity={currentCity} onChange={onCityChange} disabled={loading} />
                <button
                    className={styles.closeButton}
                    onClick={onClose}
                    type="button"
                    aria-label="Close dialog"
                >
                    ×
                </button>
            </div>
        </div>
    );
}
