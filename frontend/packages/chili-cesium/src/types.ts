// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

/**
 * Represents a building picked from Cesium 3D Tiles
 */
export interface PickedBuilding {
    /** GML ID from 3D Tiles feature properties (e.g., "bldg_71e4dcdd-bbe2-48b3-a99c-b86d3e947d04") */
    gmlId: string;

    /** Calculated mesh code from picked WGS84 coordinates (6/8/9/10 digits) */
    meshCode: string;

    /** Geographic position of the picked point */
    position: {
        latitude: number;
        longitude: number;
        height: number;
    };

    /** Building metadata from 3D Tiles properties */
    properties: {
        /** Building name from gml:name */
        name?: string;

        /** Building usage code from bldg:usage (e.g., "401" for office) */
        usage?: string;

        /** Measured height in meters from bldg:measuredHeight */
        measuredHeight?: number;

        /** City name from city_name */
        cityName?: string;

        /** Original mesh code from 3D Tiles (may differ in precision) */
        meshcode?: string;

        /** Feature type (should be "bldg:Building" for validation) */
        featureType?: string;
    };
}

/**
 * City configuration for 3D Tiles tileset
 */
export interface CityConfig {
    /** Unique city key (e.g., "chiyoda", "shibuya") */
    key: string;

    /** Display name (e.g., "Tokyo (Chiyoda-ku)") */
    name: string;

    /** PLATEAU 3D Tiles tileset URL */
    tilesetUrl: string;

    /** Initial camera view position */
    initialView: {
        longitude: number;
        latitude: number;
        height: number;
    };
}

/**
 * Mesh level types based on JIS X 0410 standard
 */
export type MeshLevel = "mesh1st" | "mesh2nd" | "mesh3rd" | "meshHalf" | "meshQuarter";
