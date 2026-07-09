import { jest } from "@jest/globals";
import { CityGMLService } from "../src/services/citygmlService";

test("PLATEAU unfold forwards fit-page scale mode", async () => {
    const fetchMock = jest.fn(async () => ({
        ok: true,
        json: async () => ({ svg_content: "<svg />", stats: {} }),
    })) as unknown as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock as any;

    const service = new CityGMLService("http://example.test/api");
    const result = await service.unfoldTexturedByBuildingIdAndMesh(
        "bldg_test",
        "53393586",
        {
            scaleMode: "fitPage",
            scaleFactor: 150,
            pageFormat: "A4",
            pageOrientation: "portrait",
        },
    );

    expect(result.isOk).toBe(true);
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(request.body as string);
    expect(body.scale_mode).toBe("fit_page");
    expect(body.scale_factor).toBe(150);
});
