// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { describe, expect, test } from "@jest/globals";
import { isValidMeshCode, meshToLatLon, resolveMeshCodesFromCoordinates } from "../src/cesiumMeshResolver";

describe("cesiumMeshResolver", () => {
    const TOKYO_STATION_LAT = 35.681236;
    const TOKYO_STATION_LON = 139.767125;

    describe("resolveMeshCodesFromCoordinates", () => {
        test("should include center mesh for Tokyo Station", () => {
            const meshes = resolveMeshCodesFromCoordinates(TOKYO_STATION_LAT, TOKYO_STATION_LON);
            expect(meshes).toContain("53394611");
            expect(meshes.length).toBe(9);
            expect(new Set(meshes).size).toBe(meshes.length);
        });

        test("should return only center mesh when neighbors are disabled", () => {
            const meshes = resolveMeshCodesFromCoordinates(TOKYO_STATION_LAT, TOKYO_STATION_LON, false);
            expect(meshes).toEqual(["53394611"]);
        });
    });

    describe("meshToLatLon", () => {
        test("should round-trip a mesh code back to itself", () => {
            const meshCode = "53394611";
            const center = meshToLatLon(meshCode);
            const meshes = resolveMeshCodesFromCoordinates(center.latitude, center.longitude, false);
            expect(meshes).toEqual([meshCode]);
        });
    });

    describe("isValidMeshCode", () => {
        test("should validate mesh code format and ranges", () => {
            expect(isValidMeshCode("53394511")).toBe(true);
            expect(isValidMeshCode("53398511")).toBe(false);
            expect(isValidMeshCode("5339451")).toBe(false);
            expect(isValidMeshCode("53A94511")).toBe(false);
        });
    });
});
