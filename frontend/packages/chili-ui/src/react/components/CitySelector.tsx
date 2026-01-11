// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { getAllCities, type CityConfig } from "chili-cesium";
import styles from "./CitySelector.module.css";

export interface CitySelectorProps {
    currentCity: string;
    onChange: (cityKey: string) => void;
    disabled?: boolean;
}

/**
 * CitySelector - Dropdown for selecting PLATEAU cities
 *
 * @deprecated This component is deprecated in favor of the unified search interface.
 * The city-based selection has been replaced with mesh-based dynamic loading (Issue #177).
 * Use the search interface in PlateauCesiumPickerReact instead.
 *
 * Displays all available cities from the city database.
 * Triggers onChange when a new city is selected.
 */
export function CitySelector({ currentCity, onChange, disabled = false }: CitySelectorProps) {
    const cities: CityConfig[] = getAllCities();

    const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        onChange(e.target.value);
    };

    return (
        <select
            className={styles.citySelect}
            value={currentCity}
            onChange={handleChange}
            disabled={disabled}
            aria-label="Select city"
        >
            <option value="" disabled>
                都市を選択
            </option>
            {cities.map((city) => (
                <option key={city.key} value={city.key}>
                    {city.name}
                </option>
            ))}
        </select>
    );
}
