// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { expect, test } from "@jest/globals";
import { detectOverlappingFaceNumberGroups } from "../src/assembly/faceNumberOverlap";

function rect(left: number, top: number, width: number, height: number) {
    return {
        bottom: top + height,
        height,
        left,
        right: left + width,
        top,
        width,
    };
}

test("detects overlapping face number label groups", () => {
    expect(
        detectOverlappingFaceNumberGroups([
            { faceNumber: 261, rect: rect(10, 10, 38, 24) },
            { faceNumber: 262, rect: rect(44, 12, 38, 24) },
            { faceNumber: 8, rect: rect(160, 10, 24, 20) },
        ]),
    ).toEqual([[261, 262]]);
});

test("deduplicates repeated labels and keeps separate overlap groups apart", () => {
    expect(
        detectOverlappingFaceNumberGroups([
            { faceNumber: 10, rect: rect(0, 0, 20, 20) },
            { faceNumber: 10, rect: rect(8, 0, 20, 20) },
            { faceNumber: 11, rect: rect(14, 0, 20, 20) },
            { faceNumber: 30, rect: rect(100, 0, 20, 20) },
            { faceNumber: 31, rect: rect(116, 0, 20, 20) },
        ]),
    ).toEqual([
        [10, 11],
        [30, 31],
    ]);
});
