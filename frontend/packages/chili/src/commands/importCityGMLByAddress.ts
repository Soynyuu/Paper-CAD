// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    BuildingInfo,
    CityGMLService,
    command,
    DialogResult,
    I18n,
    IApplication,
    ICommand,
    PubSub,
    Transaction,
} from "chili-core";
import {
    BuildingCandidate,
    PlateauBuildingSelectionDialog,
    PlateauBuildingSelection,
    PlateauSearchDialog,
    PlateauSearchOptions,
} from "chili-ui";

@command({
    key: "file.importCityGMLByAddress",
    icon: "icon-import",
    isApplicationCommand: true,
})
export class ImportCityGMLByAddress implements ICommand {
    private cityGMLService: CityGMLService;

    constructor() {
        // Use the configured API URL from environment
        const apiUrl = __APP_CONFIG__.stepUnfoldApiUrl || "http://localhost:8001/api";
        this.cityGMLService = new CityGMLService(apiUrl);
    }

    async execute(application: IApplication): Promise<void> {
        // Step 1: Show the PLATEAU search dialog to get search parameters
        PlateauSearchDialog.show(
            application,
            async (result: DialogResult, options?: PlateauSearchOptions) => {
                if (result !== DialogResult.ok || !options) {
                    return;
                }

                // Validate query
                if (!options.query.trim()) {
                    PubSub.default.pub("showToast", "error.plateau.emptyQuery");
                    return;
                }

                const query = options.query.trim();

                // Step 2: Search for buildings and show selection dialog
                let buildings: BuildingInfo[] = [];

                try {
                    // Wrap search in loading animation
                    const searchPromise = new Promise<void>((resolve, reject) => {
                        PubSub.default.pub(
                            "showPermanent",
                            async () => {
                                try {
                                    // 建物IDモードの場合
                                    if (options.searchMode === "buildingId" && options.buildingId) {
                                        // メッシュコードがある場合は最適化されたエンドポイントを使用
                                        if (options.meshCode) {
                                            console.log(
                                                "[PLATEAU] Searching by building ID + mesh code (optimized):",
                                                {
                                                    buildingId: options.buildingId,
                                                    meshCode: options.meshCode,
                                                },
                                            );

                                            const searchResult =
                                                await this.cityGMLService.searchByBuildingIdAndMesh(
                                                    options.buildingId,
                                                    options.meshCode,
                                                    {
                                                        debug: false,
                                                        mergeBuildingParts: options.mergeBuildingParts,
                                                    },
                                                );

                                            if (!searchResult.isOk) {
                                                reject(new Error(searchResult.error));
                                                return;
                                            }

                                            const response = searchResult.value;

                                            if (!response.success || !response.building) {
                                                const errorMsg =
                                                    response.error_details ||
                                                    response.error ||
                                                    "Building not found in mesh area";
                                                reject(new Error(errorMsg));
                                                return;
                                            }

                                            // 1件の建物を配列に変換
                                            buildings = [response.building];

                                            console.log(
                                                `[PLATEAU] Found building: ${response.building.gml_id} in mesh ${options.meshCode}`,
                                            );
                                            resolve();
                                        } else {
                                            // メッシュコードなし：従来の市区町村全体検索（後方互換性）
                                            console.log(
                                                "[PLATEAU] Searching by building ID (municipality-wide):",
                                                {
                                                    buildingId: options.buildingId,
                                                },
                                            );

                                            const searchResult =
                                                await this.cityGMLService.searchByBuildingId(
                                                    options.buildingId,
                                                    {
                                                        debug: false,
                                                    },
                                                );

                                            if (!searchResult.isOk) {
                                                reject(new Error(searchResult.error));
                                                return;
                                            }

                                            const response = searchResult.value;

                                            if (!response.success || !response.building) {
                                                const errorMsg =
                                                    response.error_details ||
                                                    response.error ||
                                                    "Building not found";
                                                reject(new Error(errorMsg));
                                                return;
                                            }

                                            // 1件の建物を配列に変換
                                            buildings = [response.building];

                                            console.log(
                                                `[PLATEAU] Found building: ${response.building.gml_id} in ${response.municipality_name}`,
                                            );
                                            resolve();
                                        }
                                    } else {
                                        // 住所/施設名検索モード
                                        console.log("[PLATEAU] Searching for buildings:", {
                                            query,
                                            radius: options.radius,
                                            searchMode: options.searchMode,
                                            nameFilter: options.nameFilter,
                                        });

                                        // searchModeの型を明示的に指定（buildingIdはここには来ない）
                                        const validSearchMode: "distance" | "name" | "hybrid" =
                                            options.searchMode === "distance" ||
                                            options.searchMode === "name" ||
                                            options.searchMode === "hybrid"
                                                ? options.searchMode
                                                : "hybrid";

                                        const searchResult = await this.cityGMLService.searchByAddress(
                                            query,
                                            {
                                                radius: options.radius,
                                                limit: 20, // Get more candidates for user to choose from
                                                searchMode: validSearchMode,
                                                nameFilter: options.nameFilter,
                                            },
                                        );

                                        if (!searchResult.isOk) {
                                            reject(new Error(searchResult.error));
                                            return;
                                        }

                                        buildings = searchResult.value.buildings;

                                        if (buildings.length === 0) {
                                            reject(new Error(`No buildings found: ${query}`));
                                            return;
                                        }

                                        console.log(
                                            `[PLATEAU] Found ${buildings.length} building(s), showing selection dialog`,
                                        );
                                        resolve();
                                    }
                                } catch (error) {
                                    reject(error);
                                }
                            },
                            "toast.excuting{0}",
                            I18n.translate("toast.plateau.searching"),
                        );
                    });

                    await searchPromise;
                } catch (error) {
                    const errorMessage = error instanceof Error ? error.message : "Unknown error";
                    if (errorMessage.startsWith("No buildings found:")) {
                        PubSub.default.pub("showToast", "error.plateau.noBuildingsFound:{0}", query);
                    } else {
                        PubSub.default.pub("showToast", "error.plateau.searchFailed:{0}", errorMessage);
                    }
                    console.error("[PLATEAU] Search failed:", error);
                    return;
                }

                // Convert BuildingInfo to BuildingCandidate format for the dialog
                const candidates: BuildingCandidate[] = buildings.map((b: BuildingInfo) => ({
                    gml_id: b.gml_id,
                    measured_height: b.measured_height,
                    height: b.height,
                    distance_meters: b.distance_meters,
                    usage: b.usage,
                    building_structure_type: b.building_structure_type,
                    has_lod2: b.has_lod2 ?? false,
                    has_lod3: b.has_lod3 ?? false,
                    name: b.name,
                    relevance_score: b.relevance_score,
                    name_similarity: b.name_similarity,
                    match_reason: b.match_reason,
                }));

                // Step 3: Show building selection dialog
                PlateauBuildingSelectionDialog.show(
                    application,
                    candidates,
                    async (selectionResult: DialogResult, selection?: PlateauBuildingSelection) => {
                        if (selectionResult !== DialogResult.ok || !selection) {
                            return;
                        }

                        // Step 4: Convert selected buildings to STEP
                        const selectedIds = selection.selectedBuildingIds;
                        console.log(
                            `[PLATEAU] User selected ${selectedIds.length} building(s):`,
                            selectedIds,
                        );

                        // Get or create document
                        let document =
                            application.activeView?.document ??
                            (await application.newDocument("PLATEAU Import"));

                        PubSub.default.pub(
                            "showPermanent",
                            async () => {
                                try {
                                    PubSub.default.pub("showToast", "toast.plateau.converting");

                                    console.log("[PLATEAU] Converting selected buildings:", {
                                        query,
                                        buildingIds: selectedIds,
                                        count: selectedIds.length,
                                        searchMode: options.searchMode,
                                    });

                                    let stepResult;

                                    // GML ID検索の場合は、fetch-by-id-and-meshエンドポイントを使用
                                    if (options.searchMode === "buildingId" && options.meshCode) {
                                        // 複数の建物を順次変換してマージ
                                        const stepBlobs: Blob[] = [];
                                        for (const buildingId of selectedIds) {
                                            console.log(`[PLATEAU] Converting building: ${buildingId}`);
                                            const result =
                                                await this.cityGMLService.fetchAndConvertByBuildingIdAndMesh(
                                                    buildingId,
                                                    options.meshCode,
                                                    {
                                                        debug: false,
                                                        mergeBuildingParts: options.mergeBuildingParts,
                                                    },
                                                );

                                            if (!result.isOk) {
                                                PubSub.default.pub(
                                                    "showToast",
                                                    "error.plateau.conversionFailed:{0}",
                                                    result.error,
                                                );
                                                return;
                                            }

                                            stepBlobs.push(result.value);
                                        }

                                        // 複数のSTEPファイルをマージ（最初のファイルのみ使用、または将来的に結合）
                                        stepResult = Result.ok(stepBlobs[0]);
                                    } else {
                                        // 住所/施設名検索の場合は、従来のエンドポイントを使用
                                        stepResult = await this.cityGMLService.fetchAndConvertByAddress(
                                            query,
                                            {
                                                radius: options.radius,
                                                buildingIds: selectedIds, // Use selected IDs
                                                autoReproject: options.autoReproject,
                                                method: "solid",
                                                mergeBuildingParts: options.mergeBuildingParts,
                                            },
                                        );
                                    }

                                    if (!stepResult.isOk) {
                                        PubSub.default.pub(
                                            "showToast",
                                            "error.plateau.conversionFailed:{0}",
                                            stepResult.error,
                                        );
                                        return;
                                    }

                                    // Import the converted STEP data
                                    await Transaction.executeAsync(
                                        document,
                                        "import PLATEAU model",
                                        async () => {
                                            // Convert blob to File object
                                            const filename = `${query.replace(/[^a-zA-Z0-9]/g, "_")}_plateau.step`;
                                            const stepFile = new File([stepResult.value], filename, {
                                                type: "application/step",
                                            });

                                            await document.application.dataExchange.import(document, [
                                                stepFile,
                                            ]);
                                        },
                                    );

                                    // Fit camera and show success
                                    document.application.activeView?.cameraController.fitContent();

                                    // Show success message
                                    const radiusMeters = Math.round(options.radius * 111000); // Convert degrees to meters
                                    PubSub.default.pub(
                                        "showToast",
                                        "toast.plateau.importSuccess:{0}:{1}m",
                                        query,
                                        radiusMeters,
                                    );

                                    console.log("[PLATEAU] Import successful:", {
                                        query,
                                        selectedBuildings: selectedIds.length,
                                    });
                                } catch (error) {
                                    const errorMessage =
                                        error instanceof Error ? error.message : "Unknown error";
                                    PubSub.default.pub(
                                        "showToast",
                                        "error.plateau.importFailed:{0}",
                                        errorMessage,
                                    );
                                    console.error("[PLATEAU] Import failed:", error);
                                }
                            },
                            "toast.excuting{0}",
                            I18n.translate("command.file.importCityGMLByAddress"),
                        );
                    },
                );
            },
        );
    }
}
