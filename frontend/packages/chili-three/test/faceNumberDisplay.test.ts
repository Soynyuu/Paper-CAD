// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { expect, jest, test } from "@jest/globals";
import { Vector3 } from "three";
import { FaceNumberDisplay } from "../src/faceNumberDisplay";

function mockCanvasContext() {
    const context = {
        beginPath: jest.fn(),
        closePath: jest.fn(),
        fill: jest.fn(),
        fillText: jest.fn(),
        lineTo: jest.fn(),
        moveTo: jest.fn(),
        quadraticCurveTo: jest.fn(),
        stroke: jest.fn(),
    };

    Object.defineProperties(context, {
        fillStyle: { writable: true, value: "" },
        font: { writable: true, value: "" },
        lineWidth: { writable: true, value: 0 },
        shadowBlur: { writable: true, value: 0 },
        shadowColor: { writable: true, value: "" },
        shadowOffsetY: { writable: true, value: 0 },
        strokeStyle: { writable: true, value: "" },
        textAlign: { writable: true, value: "" },
        textBaseline: { writable: true, value: "" },
    });

    return context as unknown as CanvasRenderingContext2D;
}

test("face numbers are sampled when dense but searched faces stay visible", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions(
        Array.from({ length: 80 }, (_, index) => ({
            x: index,
            y: index % 8,
            z: 0,
        })),
    );

    display.setVisible(true);
    expect(display.getDisplayStats()).toMatchObject({
        total: 80,
        limited: true,
    });
    expect(display.getDisplayStats().visible).toBeLessThanOrEqual(36);

    expect(display.focusFace(77)).toBe(true);
    expect(display.getHighlightedFaces()).toEqual([77]);
    expect(
        Array.from((display as any).sprites.values()).some(
            (sprite: any) => sprite.userData.faceNumber === 77,
        ),
    ).toBe(true);
    expect(display.getDisplayStats().visible).toBeLessThanOrEqual(37);

    display.setVisible(false);
    expect(display.getDisplayStats().visible).toBe(0);
});

test("backend face numbers remap existing markers for search and click lookup", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions([
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 0, z: 0 },
    ]);
    display.setVisible(true);

    display.setBackendFaceNumbers([
        { faceIndex: 0, faceNumber: 20 },
        { faceIndex: 1, faceNumber: 10 },
    ]);

    expect(display.getAllFaceNumbers()).toEqual([10, 20]);
    expect(display.getFaceNumberByIndex(0)).toBe(20);
    expect(display.getFaceNumberByIndex(1)).toBe(10);
    expect(display.focusFace(20)).toBe(true);
    expect(display.focusFace(1)).toBe(false);
});

test("same backend face numbers keep all matching markers", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions([
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 0, z: 0 },
        { x: 2, y: 0, z: 0 },
    ]);
    display.setVisible(true);

    display.setBackendFaceNumbers([
        { faceIndex: 0, faceNumber: 312 },
        { faceIndex: 1, faceNumber: 312 },
        { faceIndex: 2, faceNumber: 8 },
    ]);

    expect(display.getAllFaceNumbers()).toEqual([8, 312]);
    expect(display.getFaceNumberOccurrences(312)).toBe(2);
    expect(display.getMultiFaceNumbers()).toEqual([{ faceNumber: 312, count: 2 }]);
    expect(display.focusFace(312)).toBe(true);
    expect(
        Array.from((display as any).sprites.values()).filter(
            (sprite: any) => sprite.userData.faceNumber === 312,
        ),
    ).toHaveLength(2);
});

test("highlighting a face creates a 3D face overlay, not only a number label", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    (display as any).setMarker({
        faceIndex: 0,
        faceNumber: 42,
        position: new Vector3(0.33, 0.33, 0),
        normal: new Vector3(0, 0, 1),
        faceMesh: {
            position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
            normal: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
            uv: new Float32Array([0, 0, 1, 0, 0, 1]),
            index: new Uint32Array([0, 1, 2]),
            groups: [],
            range: [],
        },
    });
    display.setVisible(true);

    expect(display.highlightFace(42)).toBe(true);

    const overlays = display.children.filter((child) => child.name.startsWith("FaceNumberHighlight"));
    expect(overlays).toHaveLength(1);
    expect(overlays[0].userData["faceNumber"]).toBe(42);
    expect(overlays[0].userData["faceIndex"]).toBe(0);
});
