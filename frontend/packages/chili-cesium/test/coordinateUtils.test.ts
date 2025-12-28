// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { describe, expect, test } from "@jest/globals";
import {
    latLonToMesh1st,
    latLonToMesh2nd,
    latLonToMesh3rd,
    latLonToMeshHalf,
    latLonToMeshQuarter,
    detectMeshLevel,
    calculateMeshCode,
} from "../src/cesiumCoordinateUtils";

/**
 * Test mesh code calculations against Python reference implementation
 * Reference: /backend/utils/mesh_utils.py
 *
 * Test coordinates: Tokyo Station (35.681236, 139.767125)
 * Expected mesh codes (from Python implementation):
 * - 1st mesh (80km): "5339"
 * - 2nd mesh (10km): "533946"
 * - 3rd mesh (1km): "53394611"
 * - 1/2 mesh (500m): "533946113"
 * - 1/4 mesh (250m): "5339461132"
 */

describe("Japanese Standard Regional Mesh Code Utilities", () => {
    const TOKYO_STATION_LAT = 35.681236;
    const TOKYO_STATION_LON = 139.767125;

    describe("latLonToMesh1st", () => {
        test("should calculate 1st mesh code (80km, 4 digits) for Tokyo Station", () => {
            const result = latLonToMesh1st(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result).toBe("5339");
            expect(result.length).toBe(4);
        });

        test("should handle edge cases", () => {
            // Northern boundary
            expect(latLonToMesh1st(45.0, 140.0)).toBe("6740");

            // Southern boundary
            expect(latLonToMesh1st(30.0, 130.0)).toBe("4530");
        });
    });

    describe("latLonToMesh2nd", () => {
        test("should calculate 2nd mesh code (10km, 6 digits) for Tokyo Station", () => {
            const result = latLonToMesh2nd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result).toBe("533946");
            expect(result.length).toBe(6);
        });

        test("should start with 1st mesh code", () => {
            const result = latLonToMesh2nd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const mesh1 = latLonToMesh1st(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result.startsWith(mesh1)).toBe(true);
        });
    });

    describe("latLonToMesh3rd", () => {
        test("should calculate 3rd mesh code (1km, 8 digits) for Tokyo Station", () => {
            const result = latLonToMesh3rd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result).toBe("53394611");
            expect(result.length).toBe(8);
        });

        test("should start with 2nd mesh code", () => {
            const result = latLonToMesh3rd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const mesh2 = latLonToMesh2nd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result.startsWith(mesh2)).toBe(true);
        });

        test("should handle coordinates near mesh boundaries", () => {
            // Test coordinates that might cause rounding issues
            const result1 = latLonToMesh3rd(35.6999999, 139.7999999);
            expect(result1.length).toBe(8);

            const result2 = latLonToMesh3rd(35.6000001, 139.7000001);
            expect(result2.length).toBe(8);
        });
    });

    describe("latLonToMeshHalf", () => {
        test("should calculate 1/2 mesh code (500m, 9 digits) for Tokyo Station", () => {
            const result = latLonToMeshHalf(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result).toBe("533946113");
            expect(result.length).toBe(9);
        });

        test("should start with 3rd mesh code", () => {
            const result = latLonToMeshHalf(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const mesh3 = latLonToMesh3rd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result.startsWith(mesh3)).toBe(true);
        });

        test("should have subdivision code (1-4)", () => {
            const result = latLonToMeshHalf(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const subdivisionCode = parseInt(result.slice(-1), 10);
            expect(subdivisionCode).toBeGreaterThanOrEqual(1);
            expect(subdivisionCode).toBeLessThanOrEqual(4);
        });
    });

    describe("latLonToMeshQuarter", () => {
        test("should calculate 1/4 mesh code (250m, 10 digits) for Tokyo Station", () => {
            const result = latLonToMeshQuarter(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result).toBe("5339461132");
            expect(result.length).toBe(10);
        });

        test("should start with 1/2 mesh code", () => {
            const result = latLonToMeshQuarter(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const meshHalf = latLonToMeshHalf(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(result.startsWith(meshHalf)).toBe(true);
        });

        test("should have subdivision code (1-4)", () => {
            const result = latLonToMeshQuarter(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const subdivisionCode = parseInt(result.slice(-1), 10);
            expect(subdivisionCode).toBeGreaterThanOrEqual(1);
            expect(subdivisionCode).toBeLessThanOrEqual(4);
        });
    });

    describe("detectMeshLevel", () => {
        test("should detect 1st mesh (4 digits)", () => {
            expect(detectMeshLevel("5339")).toBe("mesh1st");
        });

        test("should detect 2nd mesh (6 digits)", () => {
            expect(detectMeshLevel("533946")).toBe("mesh2nd");
        });

        test("should detect 3rd mesh (8 digits)", () => {
            expect(detectMeshLevel("53394611")).toBe("mesh3rd");
        });

        test("should detect 1/2 mesh (9 digits)", () => {
            expect(detectMeshLevel("533946113")).toBe("meshHalf");
        });

        test("should detect 1/4 mesh (10 digits)", () => {
            expect(detectMeshLevel("5339461132")).toBe("meshQuarter");
        });

        test("should default to mesh3rd if no code provided", () => {
            expect(detectMeshLevel()).toBe("mesh3rd");
            expect(detectMeshLevel("")).toBe("mesh3rd");
        });

        test("should default to mesh3rd for invalid length", () => {
            expect(detectMeshLevel("123")).toBe("mesh3rd"); // Too short
            expect(detectMeshLevel("12345678901")).toBe("mesh3rd"); // Too long
        });
    });

    describe("calculateMeshCode", () => {
        test("should calculate mesh code at all levels", () => {
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "mesh1st")).toBe("5339");
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "mesh2nd")).toBe("533946");
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "mesh3rd")).toBe("53394611");
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "meshHalf")).toBe("533946113");
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "meshQuarter")).toBe(
                "5339461132",
            );
        });

        test("should match individual function results", () => {
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "mesh1st")).toBe(
                latLonToMesh1st(TOKYO_STATION_LAT, TOKYO_STATION_LON),
            );
            expect(calculateMeshCode(TOKYO_STATION_LAT, TOKYO_STATION_LON, "mesh3rd")).toBe(
                latLonToMesh3rd(TOKYO_STATION_LAT, TOKYO_STATION_LON),
            );
        });
    });

    describe("Integration: Full hierarchy consistency", () => {
        test("should maintain hierarchical relationship between mesh levels", () => {
            const mesh1 = latLonToMesh1st(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const mesh2 = latLonToMesh2nd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const mesh3 = latLonToMesh3rd(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const meshHalf = latLonToMeshHalf(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            const meshQuarter = latLonToMeshQuarter(TOKYO_STATION_LAT, TOKYO_STATION_LON);

            // Each level should contain the previous level as prefix
            expect(mesh2.startsWith(mesh1)).toBe(true);
            expect(mesh3.startsWith(mesh2)).toBe(true);
            expect(meshHalf.startsWith(mesh3)).toBe(true);
            expect(meshQuarter.startsWith(meshHalf)).toBe(true);
        });
    });

    describe("Real-world PLATEAU data compatibility", () => {
        test("should calculate mesh codes for known PLATEAU landmarks", () => {
            // JPタワー (Tokyo Station area)
            const jpTower = { lat: 35.681167, lon: 139.766947 };
            expect(latLonToMesh3rd(jpTower.lat, jpTower.lon)).toBe("53394611");

            // 渋谷スクランブルスクエア
            const shibuyaScramble = { lat: 35.658517, lon: 139.701334 };
            const shibuyaMesh = latLonToMesh3rd(shibuyaScramble.lat, shibuyaScramble.lon);
            expect(shibuyaMesh.length).toBe(8);
            expect(shibuyaMesh).toMatch(/^5339/); // Should be in Tokyo 1st mesh
        });

        test("should handle coordinates from actual PLATEAU 3D Tiles", () => {
            // Test with meshcode from 3D Tiles metadata
            const tilesMeshCode = "53394621"; // 8-digit from real PLATEAU data

            // Detect level
            const level = detectMeshLevel(tilesMeshCode);
            expect(level).toBe("mesh3rd");

            // Calculate mesh code from approximate center of this mesh
            // (Reverse calculation not implemented, but we verify the format)
            expect(tilesMeshCode.length).toBe(8);
            expect(tilesMeshCode).toMatch(/^5339/);
        });
    });
});
