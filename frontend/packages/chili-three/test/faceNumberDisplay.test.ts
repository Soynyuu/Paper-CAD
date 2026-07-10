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

test("all face numbers stay visible even for dense models", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions(
        Array.from({ length: 160 }, (_, index) => ({
            x: index,
            y: index % 8,
            z: 0,
        })),
    );

    display.setVisible(true);
    expect(display.getDisplayStats()).toMatchObject({
        total: 160,
        limited: false,
    });
    expect(display.getDisplayStats().visible).toBe(160);

    expect(display.focusFace(77)).toBe(true);
    expect(display.getHighlightedFaces()).toEqual([77]);
    expect(
        Array.from((display as any).sprites.values()).some(
            (sprite: any) => sprite.userData.faceNumber === 77,
        ),
    ).toBe(true);
    expect(display.getDisplayStats().visible).toBe(160);

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

test("strict backend mapping hides faces without a verified correspondence", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions([
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 0, z: 0 },
    ]);
    display.setVisible(true);

    display.setBackendFaceNumbers([{ faceIndex: 1, faceNumber: 42 }], true);

    expect(display.getAllFaceNumbers()).toEqual([42]);
    expect(display.getFaceNumberByIndex(0)).toBeUndefined();
    expect(display.getFaceNumberByIndex(1)).toBe(42);
});

test("ordinary numbers use depth while the searched number stays visible", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    display.createFaceNumbersAtPositions([
        { x: 0, y: 0, z: 0 },
        { x: 1, y: 0, z: 0 },
    ]);
    display.setVisible(true);

    display.highlightFace(2);

    const sprites = Array.from((display as any).sprites.values()) as any[];
    expect(sprites.find((sprite) => sprite.userData.faceNumber === 1).material.depthTest).toBe(true);
    expect(sprites.find((sprite) => sprite.userData.faceNumber === 1).material.polygonOffset).toBe(true);
    expect(sprites.find((sprite) => sprite.userData.faceNumber === 2).material.depthTest).toBe(false);
});

test("regular face labels stay clear of the source surface", () => {
    const display = new FaceNumberDisplay();
    (display as any).modelSize = 100;

    const position = (display as any).calculateLabelPosition(
        new Vector3(0, 0, 0),
        new Vector3(0, 0, 1),
        10,
        0,
    );

    expect(position.z).toBeCloseTo(0.4);
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
        anchorPosition: new Vector3(0.33, 0.33, 0),
        position: new Vector3(0.33, 0.33, 0),
        normal: new Vector3(0, 0, 1),
        faceSize: 1,
        faceGeometry: {
            position: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
            index: new Uint32Array([0, 1, 2]),
        },
    });
    display.setVisible(true);

    expect(display.highlightFace(42)).toBe(true);

    const overlays = display.children.filter((child) => child.name.startsWith("FaceNumberHighlight"));
    expect(overlays).toHaveLength(1);
    expect(overlays[0].userData["faceNumber"]).toBe(42);
    expect(overlays[0].userData["faceIndex"]).toBe(0);
});

test("small face marker renders a leader line and exposes a focus target", () => {
    jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(mockCanvasContext());

    const display = new FaceNumberDisplay();
    (display as any).modelSize = 100;
    (display as any).setMarker({
        faceIndex: 3,
        faceNumber: 9,
        anchorPosition: new Vector3(1, 2, 3),
        position: new Vector3(4, 5, 6),
        faceSize: 0.5,
    });
    display.setVisible(true);

    expect((display as any).calloutLines.size).toBe(1);
    expect(display.getFaceFocusInfo(9)?.center.toArray()).toEqual([1, 2, 3]);

    display.setVisible(false);
    expect((display as any).calloutLines.size).toBe(0);
});
