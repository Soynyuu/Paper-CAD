// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

/**
 * Japanese Standard Regional Mesh Code Utilities for Cesium
 *
 * Converts latitude/longitude coordinates to Japanese Standard Regional Mesh Codes
 * according to JIS X 0410 standard. Mirrors the backend mesh_utils.py implementation.
 *
 * Mesh Levels:
 * - 1st mesh (80km): 4 digits (e.g., "5339")
 * - 2nd mesh (10km): 6 digits (e.g., "533945")
 * - 3rd mesh (1km): 8 digits (e.g., "53394511")
 *
 * Reference:
 * https://www.stat.go.jp/data/mesh/gaiyou.html
 */

/**
 * 座標からメッシュコード + 周辺メッシュを計算
 *
 * @param latitude - Latitude in degrees
 * @param longitude - Longitude in degrees
 * @param includeNeighbors - Include 8 neighboring meshes (default: true)
 * @returns Array of mesh codes (9 codes if includeNeighbors=true, 1 if false)
 *
 * @example
 * // Tokyo Station: 35.681236, 139.767125
 * const meshCodes = resolveMeshCodesFromCoordinates(35.681236, 139.767125);
 * // Returns: ["53394510", "53394511", "53394512", ...]  (9 meshes in 3x3 grid)
 */
export function resolveMeshCodesFromCoordinates(
    latitude: number,
    longitude: number,
    includeNeighbors: boolean = true,
): string[] {
    // 中心メッシュ計算（3rd mesh = 1km）
    const centerMesh = latLonToMesh3rd(latitude, longitude);

    if (!includeNeighbors) {
        return [centerMesh];
    }

    // 周辺8メッシュを取得（3x3グリッド）
    const neighbors = getNeighboringMeshes3rd(centerMesh);

    return neighbors; // 9個のメッシュコード
}

/**
 * 座標 → 3次メッシュコード (1km)
 *
 * Mirrors backend mesh_utils.py::latlon_to_mesh_3rd()
 *
 * @param lat - Latitude in degrees
 * @param lon - Longitude in degrees
 * @returns 8-digit 3rd mesh code
 *
 * @example
 * latLonToMesh3rd(35.681236, 139.767125)  // Returns: "53394511"
 */
function latLonToMesh3rd(lat: number, lon: number): string {
    // 1次メッシュ (4桁)
    const p = Math.floor((lat * 60) / 40);
    const q = Math.floor(lon - 100);
    const mesh1 = `${p.toString().padStart(2, "0")}${q.toString().padStart(2, "0")}`;

    // 2次メッシュ (6桁)
    const latRemainder1 = lat - (p * 40) / 60;
    const lonRemainder1 = lon - (100 + q);
    const r = Math.floor((latRemainder1 * 60) / 5);
    const s = Math.floor((lonRemainder1 * 60) / 7.5);

    // 3次メッシュ (8桁)
    const latRemainder2 = latRemainder1 - (r * 5) / 60;
    const lonRemainder2 = lonRemainder1 - (s * 7.5) / 60;
    const t = Math.floor((latRemainder2 * 60) / 0.5);
    const u = Math.floor((lonRemainder2 * 60) / 0.75);

    return `${mesh1}${r}${s}${t}${u}`;
}

/**
 * 周辺8メッシュ + 中心メッシュを取得 (3x3グリッド)
 *
 * Mirrors backend mesh_utils.py::get_neighboring_meshes_3rd()
 *
 * @param meshCode - 8-digit 3rd mesh code
 * @returns Array of 9 mesh codes (center + 8 neighbors)
 *
 * @throws Error if meshCode is not 8 digits
 *
 * @example
 * getNeighboringMeshes3rd("53394511")
 * // Returns: ["53394510", "53394511", "53394512", ...]
 */
function getNeighboringMeshes3rd(meshCode: string): string[] {
    if (meshCode.length !== 8) {
        throw new Error(`Expected 8-digit 3rd mesh code, got: ${meshCode}`);
    }

    const mesh1 = meshCode.substring(0, 4);
    const r = parseInt(meshCode[4]);
    const s = parseInt(meshCode[5]);
    const t = parseInt(meshCode[6]);
    const u = parseInt(meshCode[7]);

    const meshes: string[] = [];

    // 3x3グリッド
    for (let dt = -1; dt <= 1; dt++) {
        for (let du = -1; du <= 1; du++) {
            let newT = t + dt;
            let newU = u + du;
            let newR = r;
            let newS = s;

            // オーバーフロー/アンダーフロー処理
            if (newT < 0) {
                newT += 10;
                newR -= 1;
            } else if (newT >= 10) {
                newT -= 10;
                newR += 1;
            }

            if (newU < 0) {
                newU += 10;
                newS -= 1;
            } else if (newU >= 10) {
                newU -= 10;
                newS += 1;
            }

            // 2次メッシュの境界チェック (0-7の範囲)
            if (newR < 0 || newR >= 8 || newS < 0 || newS >= 8) {
                continue; // 境界外はスキップ
            }

            meshes.push(`${mesh1}${newR}${newS}${newT}${newU}`);
        }
    }

    return meshes;
}

/**
 * メッシュコード → 中心座標を計算
 *
 * @param meshCode - 8-digit 3rd mesh code
 * @returns { latitude, longitude } center coordinates
 *
 * @example
 * meshToLatLon("53394511")  // Returns: { latitude: 35.6833, longitude: 139.7667 }
 */
export function meshToLatLon(meshCode: string): { latitude: number; longitude: number } {
    if (meshCode.length !== 8) {
        throw new Error(`Expected 8-digit 3rd mesh code, got: ${meshCode}`);
    }

    // 1次メッシュをデコード
    const p = parseInt(meshCode.substring(0, 2));
    const q = parseInt(meshCode.substring(2, 4));

    // 2次メッシュをデコード
    const r = parseInt(meshCode[4]);
    const s = parseInt(meshCode[5]);

    // 3次メッシュをデコード
    const t = parseInt(meshCode[6]);
    const u = parseInt(meshCode[7]);

    // 緯度計算 (南西隅 + メッシュサイズの半分 = 中心)
    const latBase = (p * 40) / 60;
    const latOffset2 = (r * 5) / 60;
    const latOffset3 = (t * 0.5) / 60;
    const latSouthWest = latBase + latOffset2 + latOffset3;
    const latitude = latSouthWest + 0.5 / 60 / 2; // メッシュ中心

    // 経度計算 (南西隅 + メッシュサイズの半分 = 中心)
    const lonBase = 100 + q;
    const lonOffset2 = (s * 7.5) / 60;
    const lonOffset3 = (u * 0.75) / 60;
    const lonSouthWest = lonBase + lonOffset2 + lonOffset3;
    const longitude = lonSouthWest + 0.75 / 60 / 2; // メッシュ中心

    return { latitude, longitude };
}

/**
 * メッシュコードのバリデーション
 *
 * @param meshCode - Mesh code to validate
 * @returns true if valid 8-digit 3rd mesh code
 */
export function isValidMeshCode(meshCode: string): boolean {
    // 8桁の数字のみ
    if (!/^\d{8}$/.test(meshCode)) {
        return false;
    }

    // 4, 5桁目は0-7の範囲 (2次メッシュ)
    const r = parseInt(meshCode[4]);
    const s = parseInt(meshCode[5]);
    if (r < 0 || r >= 8 || s < 0 || s >= 8) {
        return false;
    }

    // 6, 7桁目は0-9の範囲 (3次メッシュ)
    const t = parseInt(meshCode[6]);
    const u = parseInt(meshCode[7]);
    if (t < 0 || t >= 10 || u < 0 || u >= 10) {
        return false;
    }

    return true;
}
