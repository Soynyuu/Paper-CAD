import { jest } from "@jest/globals";
import { StepUnfoldService } from "../src/services/stepUnfoldService";

function createFetchMock() {
    return jest.fn(async () => ({
        ok: true,
        json: async () => ({ svg_content: "<svg />" }),
    })) as unknown as jest.MockedFunction<typeof fetch>;
}

test("unfoldStepFromData sends fixed scale options to backend", async () => {
    const fetchMock = createFetchMock();
    global.fetch = fetchMock as any;

    const service = new StepUnfoldService("http://example.test/api");
    const result = await service.unfoldStepFromData("step-data", {
        scaleMode: "fixed",
        scale: 150,
        units: "m",
        layoutMode: "paged",
        pageFormat: "A4",
        pageOrientation: "portrait",
        mergeMode: "legacy",
        curveMode: "faceted",
    });

    expect(result.isOk).toBe(true);
    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect(body.get("scale_mode")).toBe("fixed");
    expect(body.get("scale_factor")).toBe("150");
    expect(body.get("units")).toBe("m");
    expect(body.get("page_format")).toBe("A4");
    expect(body.get("page_orientation")).toBe("portrait");
    expect(body.get("merge_mode")).toBe("legacy");
    expect(body.get("curve_mode")).toBe("faceted");
});

test("unfoldStepFromData maps fitPage scale mode for backend", async () => {
    const fetchMock = createFetchMock();
    global.fetch = fetchMock as any;

    const service = new StepUnfoldService("http://example.test/api");
    await service.unfoldStepFromData("step-data", {
        scaleMode: "fitPage",
        layoutMode: "paged",
        pageFormat: "A3",
        pageOrientation: "landscape",
    });

    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect(body.get("scale_mode")).toBe("fit_page");
    expect(body.get("scale_factor")).toBe("150");
    expect(body.get("page_format")).toBe("A3");
    expect(body.get("page_orientation")).toBe("landscape");
    expect(body.get("merge_mode")).toBe("improved");
    expect(body.get("curve_mode")).toBe("smooth");
});
