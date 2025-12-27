// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import type { CityConfig } from "./types";

/**
 * Database of PLATEAU 3D Tiles cities
 *
 * Maps city keys to their 3D Tiles tileset URLs and initial camera views.
 * URLs are for PLATEAU streaming data hosted on Re:Earth platform.
 *
 * To add more cities:
 * 1. Find the city's tileset URL from plateau-datasets API
 * 2. Determine initial camera position (center of city)
 * 3. Add entry to PLATEAU_CITIES array
 */

export const PLATEAU_CITIES: CityConfig[] = [
    {
        key: "chiyoda",
        name: "Tokyo (Chiyoda-ku)",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/0e/e5948a-e95c-4e31-be85-1f8c066ed996/13101_chiyoda-ku_pref_2023_citygml_1_op_bldg_3dtiles_13101_chiyoda-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7514,
            latitude: 35.6895,
            height: 1000,
        },
    },
    // TODO: Add more cities (Shibuya, Osaka, etc.)
    // See issue #142 for planned city list
];

/**
 * Get city configuration by key
 *
 * @param cityKey - City key (e.g., "chiyoda")
 * @returns City configuration or undefined if not found
 */
export function getCityConfig(cityKey: string): CityConfig | undefined {
    return PLATEAU_CITIES.find((city) => city.key === cityKey);
}

/**
 * Get all available city keys
 *
 * @returns Array of city keys
 */
export function getAvailableCityKeys(): string[] {
    return PLATEAU_CITIES.map((city) => city.key);
}

/**
 * Get all city configurations
 *
 * @returns Array of all city configurations
 */
export function getAllCities(): CityConfig[] {
    return PLATEAU_CITIES;
}
