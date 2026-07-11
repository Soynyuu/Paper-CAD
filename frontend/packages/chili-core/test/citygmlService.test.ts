import { jest } from "@jest/globals";
import { CityGMLService } from "../src/services/citygmlService";

test("PLATEAU unfold forwards fit-page scale mode", async () => {
    const fetchMock = jest.fn(async () => ({
        ok: true,
        json: async () => ({ svg_content: "<svg />", stats: {} }),
    })) as unknown as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock as any;

    const service = new CityGMLService("http://example.test/api");
    const result = await service.unfoldTexturedByBuildingIdAndMesh("bldg_test", "53393586", {
        scaleMode: "fitPage",
        scaleFactor: 150,
        pageFormat: "A4",
        pageOrientation: "portrait",
    });

    expect(result.isOk).toBe(true);
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(request.body as string);
    expect(body.scale_mode).toBe("fit_page");
    expect(body.scale_factor).toBe(150);
});

test("PLATEAU import forwards LOD and reads actual LOD headers", async () => {
    const headers = new Headers({
        "X-LOD-Requested": "LOD2",
        "X-LOD-Used": "LOD1",
        "X-LOD-Fallback": "true",
    });
    const fetchMock = jest.fn(async () => ({
        ok: true,
        headers,
        blob: async () => new Blob(["STEP"]),
    })) as unknown as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock as any;

    const service = new CityGMLService("http://example.test/api");
    const result = await service.fetchAndConvertByBuildingIdAndMesh("bldg_test", "53393586", {
        lodTarget: "LOD2",
    });

    expect(result.isOk).toBe(true);
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string).lod_target).toBe("LOD2");
    if (result.isOk) {
        expect(result.value.usedLod).toBe("LOD1");
        expect(result.value.lodFallback).toBe(true);
    }
});

test("PLATEAU unfold forwards selected LOD", async () => {
    const fetchMock = jest.fn(async () => ({
        ok: true,
        json: async () => ({ svg_content: "<svg />", stats: {} }),
    })) as unknown as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock as any;

    const service = new CityGMLService("http://example.test/api");
    await service.unfoldTexturedByBuildingIdAndMesh("bldg_test", "53393586", {
        lodTarget: "LOD1",
    });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string).lod_target).toBe("LOD1");
});
