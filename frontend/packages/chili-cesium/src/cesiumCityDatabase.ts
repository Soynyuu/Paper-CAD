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
        name: "東京都 千代田区",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/0e/e5948a-e95c-4e31-be85-1f8c066ed996/13101_chiyoda-ku_pref_2023_citygml_1_op_bldg_3dtiles_13101_chiyoda-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7514,
            latitude: 35.6895,
            height: 1000,
        },
    },
    {
        key: "shibuya",
        name: "東京都 渋谷区",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/d6/09251d-eaf4-4288-a68d-41c449edbe5d/13113_shibuya-ku_pref_2023_citygml_1_op_bldg_3dtiles_13113_shibuya-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7016,
            latitude: 35.6617,
            height: 1000,
        },
    },
    {
        key: "shinjuku",
        name: "東京都 新宿区",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/5f/0f37a7-bf11-4df6-88e3-5ec71a0e1bfa/13104_shinjuku-ku_pref_2023_citygml_1_op_bldg_3dtiles_13104_shinjuku-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7036,
            latitude: 35.6938,
            height: 1000,
        },
    },
    {
        key: "minato",
        name: "東京都 港区",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/88/fc4ed4-d3e6-458a-bd6c-ec1063e43ebd/13103_minato-ku_pref_2023_citygml_1_op_bldg_3dtiles_13103_minato-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7514,
            latitude: 35.6581,
            height: 1000,
        },
    },
    {
        key: "chuo",
        name: "東京都 中央区",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/72/d3e0b0-79bb-441c-9de4-9cf1be4d8e1d/13102_chuo-ku_pref_2023_citygml_1_op_bldg_3dtiles_13102_chuo-ku_lod1/tileset.json",
        initialView: {
            longitude: 139.7714,
            latitude: 35.6704,
            height: 1000,
        },
    },
    {
        key: "osaka",
        name: "大阪府 大阪市",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/d5/f79a06-e849-40a6-b55f-94b0aadc6f7a/27100_osaka-shi_pref_2022_citygml_1_op_bldg_3dtiles_27100_osaka-shi_lod1/tileset.json",
        initialView: {
            longitude: 135.5022,
            latitude: 34.6937,
            height: 1500,
        },
    },
    {
        key: "nagoya",
        name: "愛知県 名古屋市",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/d2/8a5d22-c4e1-4e6b-b0ee-0c02a70a06b1/23100_nagoya-shi_pref_2022_citygml_1_op_bldg_3dtiles_23100_nagoya-shi_lod1/tileset.json",
        initialView: {
            longitude: 136.9066,
            latitude: 35.1815,
            height: 1500,
        },
    },
    {
        key: "yokohama",
        name: "神奈川県 横浜市",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/1a/7ab5cc-2f48-4739-bd11-15a45a6ebab7/14100_yokohama-shi_pref_2022_citygml_1_op_bldg_3dtiles_14100_yokohama-shi_lod1/tileset.json",
        initialView: {
            longitude: 139.638,
            latitude: 35.4437,
            height: 1500,
        },
    },
    {
        key: "fukuoka",
        name: "福岡県 福岡市",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/aa/1c95f3-7e31-4d84-8c70-3bf35c4a72f7/40130_fukuoka-shi_pref_2022_citygml_1_op_bldg_3dtiles_40130_fukuoka-shi_lod1/tileset.json",
        initialView: {
            longitude: 130.4017,
            latitude: 33.5904,
            height: 1500,
        },
    },
    {
        key: "sapporo",
        name: "北海道 札幌市",
        tilesetUrl:
            "https://assets.cms.plateau.reearth.io/assets/cd/c8a72f-5a2f-4b01-9c21-3aad02e34f7a/01100_sapporo-shi_pref_2022_citygml_1_op_bldg_3dtiles_01100_sapporo-shi_lod1/tileset.json",
        initialView: {
            longitude: 141.3545,
            latitude: 43.0642,
            height: 1500,
        },
    },
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
