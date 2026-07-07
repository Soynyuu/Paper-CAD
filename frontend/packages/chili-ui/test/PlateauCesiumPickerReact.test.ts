import React, { act } from "react";
import "@testing-library/jest-dom";
import { jest } from "@jest/globals";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

(globalThis as any).TransformStream =
    (globalThis as any).TransformStream ||
    class {
        readable = {};
        writable = {};
    };

jest.doMock("chili-core", () => ({
    DialogResult: {
        ok: 0,
        cancel: 1,
    },
    I18n: {
        translate: (key: string, ...args: string[]) => {
            const translations: Record<string, string> = {
                "plateau.cesium.noSelection": "建物が選択されていません",
                "plateau.cesium.clickToSelectBuilding": "建物をクリックして選択してください",
                "plateau.cesium.ctrlClickForMultiple": "複数選択にはCtrlキーを押しながらクリック",
                "plateau.cesium.importSelected": "選択した建物を取り込む",
                "plateau.cesium.clearSelection": "選択をクリア",
                "items.tool.delete": "削除",
                "error.plateau.emptyMeshCode": "メッシュコードを入力してください",
                "error.plateau.noBuildingsFound:{0}": `建物が見つかりませんでした: ${args[0]}`,
                "error.plateau.searchFailed:{0}": `建物の検索に失敗しました: ${args[0]}`,
            };
            return translations[key] ?? key;
        },
    },
    PubSub: {
        default: {
            pub: jest.fn(),
        },
    },
}));

jest.doMock("cesium", () => ({
    Cartesian3: {
        fromDegrees: jest.fn(() => ({})),
    },
    ScreenSpaceEventHandler: jest.fn().mockImplementation(() => ({
        setInputAction: jest.fn(),
        destroy: jest.fn(),
    })),
    ScreenSpaceEventType: {
        LEFT_CLICK: "LEFT_CLICK",
    },
    KeyboardEventModifier: {
        CTRL: "CTRL",
    },
    Math: {
        toRadians: jest.fn((value: number) => value),
    },
    Ion: {
        defaultAccessToken: "",
    },
}));

jest.doMock("lottie-web", () => ({
    loadAnimation: jest.fn(() => ({
        destroy: jest.fn(),
    })),
}));

const viewerMock = {
    canvas: document.createElement("canvas"),
    isDestroyed: () => false,
    resize: jest.fn(),
    scene: {
        requestRender: jest.fn(),
        globe: {
            maximumScreenSpaceError: 2,
        },
    },
    resolutionScale: 1,
    camera: {
        flyTo: jest.fn(({ complete }: { complete?: () => void }) => complete?.()),
    },
};

const selectedBuildings: any[] = [];

jest.doMock("chili-cesium", () => ({
    CesiumView: jest.fn().mockImplementation(() => ({
        initialize: jest.fn(async () => undefined),
        getViewer: jest.fn(() => viewerMock),
        activateBasemap: jest.fn(async () => undefined),
        dispose: jest.fn(),
    })),
    CesiumBuildingPicker: jest.fn().mockImplementation(() => ({
        getSelectedBuildings: jest.fn(() => selectedBuildings),
        pickBuilding: jest.fn(),
        clearSelection: jest.fn(),
        removeBuilding: jest.fn(),
        clearPreviewHighlight: jest.fn(),
        previewBuildingAtCoordinates: jest.fn(() => true),
        previewBuildingAtScreen: jest.fn(() => true),
    })),
    CesiumTilesetLoader: jest.fn().mockImplementation(() => ({
        createTilesetKey: jest.fn((meshCode: string, url: string) => `${meshCode}:${url}`),
        retainMeshes: jest.fn(),
        loadMultipleTilesets: jest.fn(async () => ({ failedMeshes: [] })),
    })),
    resolveMeshCodesFromCoordinates: jest.fn(() => ["53394511"]),
}));

const { PlateauCesiumPickerReact } = await import("../src/react/PlateauCesiumPickerReact");
const { Sidebar } = await import("../src/react/components/Sidebar");

const mockFetch = (body: unknown) =>
    jest.fn(async () => ({
        ok: true,
        json: async () => body,
    }));

beforeEach(() => {
    (globalThis as any).__APP_CONFIG__ = {
        stepUnfoldApiUrl: "http://localhost:8001/api",
        cesiumBaseUrl: "/cesium/",
    };
    viewerMock.camera.flyTo.mockClear();
    viewerMock.scene.requestRender.mockClear();
});

afterEach(() => {
    jest.restoreAllMocks();
    document.body.innerHTML = "";
});

test("facility search renders candidates and advances to map confirmation", async () => {
    global.fetch = mockFetch({
        success: true,
        geocoding: { latitude: 35.681236, longitude: 139.767125 },
        buildings: [
            {
                gml_id: "bldg_tokyo_station",
                building_id: "13101-bldg_tokyo_station",
                name: "東京駅",
                latitude: 35.681236,
                longitude: 139.767125,
                distance_meters: 12,
                municipality_code: "13101",
            },
        ],
    }) as any;

    render(React.createElement(PlateauCesiumPickerReact, { onClose: jest.fn() }));

    fireEvent.change(screen.getByPlaceholderText("場所や施設を検索"), {
        target: { value: "東京駅" },
    });
    fireEvent.click(screen.getByRole("button", { name: "検索" }));

    expect(await screen.findByText("東京駅")).toBeTruthy();
    expect(document.getElementById("plateau-cesium-host")).toBeTruthy();
});

test("building id mode requires a mesh code before searching", async () => {
    render(React.createElement(PlateauCesiumPickerReact, { onClose: jest.fn() }));

    fireEvent.click(screen.getByRole("tab", { name: "建物ID" }));
    fireEvent.change(screen.getByPlaceholderText("建物IDを入力"), {
        target: { value: "bldg_example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "検索" }));

    expect(await screen.findByText("メッシュコードを入力してください")).toBeTruthy();
});

test("sidebar disables actions with no selection and calls remove for selected buildings", async () => {
    const onRemove = jest.fn();
    const building = {
        gmlId: "bldg_selected",
        meshCode: "53394511",
        position: {
            latitude: 35.681236,
            longitude: 139.767125,
            height: 0,
        },
        properties: {
            name: "選択中の建物",
            measuredHeight: 42,
            usage: "401",
        },
    };

    const { rerender } = render(
        React.createElement(Sidebar, {
            selectedBuildings: [],
            onRemove,
            onImport: jest.fn(),
            onUnfoldBeta: jest.fn(),
            onClear: jest.fn(),
        }),
    );

    expect(screen.getByRole("button", { name: "選択した建物を取り込む" })).toBeDisabled();

    rerender(
        React.createElement(Sidebar, {
            selectedBuildings: [building],
            onRemove,
            onImport: jest.fn(),
            onUnfoldBeta: jest.fn(),
            onClear: jest.fn(),
        }),
    );

    expect(screen.getByText("選択中の建物")).toBeTruthy();
    await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Remove 選択中の建物" }));
    });
    await waitFor(() => expect(onRemove).toHaveBeenCalledWith("bldg_selected"));
});

test("dialog close reports cancel", async () => {
    const onClose = jest.fn();
    render(React.createElement(PlateauCesiumPickerReact, { onClose }));

    fireEvent.click(screen.getByRole("button", { name: "閉じる" }));

    await waitFor(() => expect(onClose).toHaveBeenCalledWith(1));
});
