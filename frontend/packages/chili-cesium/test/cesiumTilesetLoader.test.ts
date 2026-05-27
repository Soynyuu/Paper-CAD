// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { describe, expect, test } from "@jest/globals";
import { TransformStream } from "stream/web";
import type { CesiumTilesetLoader as CesiumTilesetLoaderType } from "../src/cesiumTilesetLoader";

if (typeof globalThis.TransformStream === "undefined") {
    globalThis.TransformStream = TransformStream as typeof globalThis.TransformStream;
}

const { CesiumTilesetLoader } = await import("../src/cesiumTilesetLoader");

describe("CesiumTilesetLoader", () => {
    test("uses municipality code in tileset cache keys", () => {
        const loader = Object.create(CesiumTilesetLoader.prototype) as CesiumTilesetLoaderType;

        expect(loader.createTilesetKey("53393673", "https://example.com/13102/tileset.json", "13102")).toBe(
            "53393673:13102",
        );
        expect(loader.createTilesetKey("53393673", "https://example.com/13108/tileset.json", "13108")).toBe(
            "53393673:13108",
        );
    });

    test("falls back to tileset URL when municipality code is unavailable", () => {
        const loader = Object.create(CesiumTilesetLoader.prototype) as CesiumTilesetLoaderType;

        expect(loader.createTilesetKey("53393673", "https://example.com/tileset.json")).toBe(
            "53393673:https://example.com/tileset.json",
        );
    });
});
