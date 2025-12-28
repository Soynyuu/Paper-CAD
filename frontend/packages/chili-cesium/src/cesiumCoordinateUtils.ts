// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import type { MeshLevel } from "./types";

/**
 * Japanese Standard Regional Mesh Code Utilities
 *
 * Converts latitude/longitude coordinates to Japanese Standard Regional Mesh Codes
 * according to JIS X 0410 standard.
 *
 * Mesh Levels:
 * - 1st mesh (80km): 4 digits (e.g., "5339")
 * - 2nd mesh (10km): 6 digits (e.g., "533945")
 * - 3rd mesh (1km): 8 digits (e.g., "53394511")
 * - 1/2 mesh (500m): 9 digits (e.g., "533945111")
 * - 1/4 mesh (250m): 10 digits (e.g., "5339451111")
 *
 * Reference:
 * - https://www.stat.go.jp/data/mesh/gaiyou.html
 * - Backend: /backend/utils/mesh_utils.py
 */

/**
 * Convert lat/lon to 1st mesh code (80km, 4 digits)
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 4-digit mesh code (e.g., "5339")
 */
export function latLonToMesh1st(lat: number, lon: number): string {
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);
    return `${p.toString().padStart(2, "0")}${q.toString().padStart(2, "0")}`;
}

/**
 * Convert lat/lon to 2nd mesh code (10km, 6 digits)
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 6-digit mesh code (e.g., "533945")
 */
export function latLonToMesh2nd(lat: number, lon: number): string {
    // 1st mesh
    const mesh1 = latLonToMesh1st(lat, lon);

    // Calculate 2nd mesh indices within 1st mesh
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);

    const latRemainder = lat - (p * 40) / 60;
    const lonRemainder = lon - (100 + q);

    const r = Math.floor((latRemainder * 60) / 5);
    const s = Math.floor((lonRemainder * 60) / 7.5);

    return `${mesh1}${r}${s}`;
}

/**
 * Convert lat/lon to 3rd mesh code (1km, 8 digits)
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 8-digit mesh code (e.g., "53394511")
 */
export function latLonToMesh3rd(lat: number, lon: number): string {
    // 2nd mesh
    const mesh2 = latLonToMesh2nd(lat, lon);

    // Calculate 3rd mesh indices within 2nd mesh
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);

    const latRemainder1 = lat - (p * 40) / 60;
    const lonRemainder1 = lon - (100 + q);

    const r = Math.floor((latRemainder1 * 60) / 5);
    const s = Math.floor((lonRemainder1 * 60) / 7.5);

    const latRemainder2 = latRemainder1 - (r * 5) / 60;
    const lonRemainder2 = lonRemainder1 - (s * 7.5) / 60;

    const t = Math.floor((latRemainder2 * 60) / 0.5);
    const u = Math.floor((lonRemainder2 * 60) / 0.75);

    return `${mesh2}${t}${u}`;
}

/**
 * Convert lat/lon to 1/2 mesh code (500m, 9 digits)
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 9-digit mesh code (e.g., "533945111")
 */
export function latLonToMeshHalf(lat: number, lon: number): string {
    // 3rd mesh
    const mesh3 = latLonToMesh3rd(lat, lon);

    // Calculate 1/2 mesh index within 3rd mesh
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);

    const latRemainder1 = lat - (p * 40) / 60;
    const lonRemainder1 = lon - (100 + q);

    const r = Math.floor((latRemainder1 * 60) / 5);
    const s = Math.floor((lonRemainder1 * 60) / 7.5);

    const latRemainder2 = latRemainder1 - (r * 5) / 60;
    const lonRemainder2 = lonRemainder1 - (s * 7.5) / 60;

    const t = Math.floor((latRemainder2 * 60) / 0.5);
    const u = Math.floor((lonRemainder2 * 60) / 0.75);

    const latRemainder3 = latRemainder2 - (t * 0.5) / 60;
    const lonRemainder3 = lonRemainder2 - (u * 0.75) / 60;

    // 1/2 mesh: 2x2 subdivision (1=SW, 2=SE, 3=NW, 4=NE)
    const halfLat = Math.floor(latRemainder3 / (0.25 / 60));
    const halfLon = Math.floor(lonRemainder3 / (0.375 / 60));

    const halfCode = halfLat * 2 + halfLon + 1;

    return `${mesh3}${halfCode}`;
}

/**
 * Convert lat/lon to 1/4 mesh code (250m, 10 digits)
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 10-digit mesh code (e.g., "5339451111")
 */
export function latLonToMeshQuarter(lat: number, lon: number): string {
    // 1/2 mesh
    const meshHalf = latLonToMeshHalf(lat, lon);

    // Calculate 1/4 mesh index within 1/2 mesh
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);

    const latRemainder1 = lat - (p * 40) / 60;
    const lonRemainder1 = lon - (100 + q);

    const r = Math.floor((latRemainder1 * 60) / 5);
    const s = Math.floor((lonRemainder1 * 60) / 7.5);

    const latRemainder2 = latRemainder1 - (r * 5) / 60;
    const lonRemainder2 = lonRemainder1 - (s * 7.5) / 60;

    const t = Math.floor((latRemainder2 * 60) / 0.5);
    const u = Math.floor((lonRemainder2 * 60) / 0.75);

    const latRemainder3 = latRemainder2 - (t * 0.5) / 60;
    const lonRemainder3 = lonRemainder2 - (u * 0.75) / 60;

    const halfLat = Math.floor(latRemainder3 / (0.25 / 60));
    const halfLon = Math.floor(lonRemainder3 / (0.375 / 60));

    const latRemainder4 = latRemainder3 - (halfLat * 0.25) / 60;
    const lonRemainder4 = lonRemainder3 - (halfLon * 0.375) / 60;

    // 1/4 mesh: 2x2 subdivision (1=SW, 2=SE, 3=NW, 4=NE)
    const quarterLat = Math.floor(latRemainder4 / (0.125 / 60));
    const quarterLon = Math.floor(lonRemainder4 / (0.1875 / 60));

    const quarterCode = quarterLat * 2 + quarterLon + 1;

    return `${meshHalf}${quarterCode}`;
}

/**
 * Detect mesh level from mesh code length
 *
 * @param meshCode - Optional mesh code from 3D Tiles
 * @returns Detected mesh level, defaults to mesh3rd if not provided
 */
export function detectMeshLevel(meshCode?: string): MeshLevel {
    if (!meshCode) {
        return "mesh3rd"; // Default to 1km mesh
    }

    const len = meshCode.length;

    switch (len) {
        case 4:
            return "mesh1st";
        case 6:
            return "mesh2nd";
        case 8:
            return "mesh3rd";
        case 9:
            return "meshHalf";
        case 10:
            return "meshQuarter";
        default:
            return "mesh3rd"; // Safe default
    }
}

/**
 * Calculate mesh code at specified level
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @param level - Mesh level to calculate
 * @returns Mesh code at the specified level
 */
export function calculateMeshCode(lat: number, lon: number, level: MeshLevel): string {
    switch (level) {
        case "mesh1st":
            return latLonToMesh1st(lat, lon);
        case "mesh2nd":
            return latLonToMesh2nd(lat, lon);
        case "mesh3rd":
            return latLonToMesh3rd(lat, lon);
        case "meshHalf":
            return latLonToMeshHalf(lat, lon);
        case "meshQuarter":
            return latLonToMeshQuarter(lat, lon);
        default:
            return latLonToMesh3rd(lat, lon); // Safe default
    }
}
