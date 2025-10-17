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
                                    console.log("[PLATEAU] Searching for buildings:", {
                                        query,
                                        radius: options.radius,
                                        searchMode: options.searchMode,
                                        nameFilter: options.nameFilter,
                                    });

                                    const searchResult = await this.cityGMLService.searchByAddress(query, {
                                        radius: options.radius,
                                        limit: 20, // Get more candidates for user to choose from
                                        searchMode: options.searchMode,
                                        nameFilter: options.nameFilter,
                                    });

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
                                    });

                                    // Fetch and convert with specific building IDs
                                    const stepResult = await this.cityGMLService.fetchAndConvertByAddress(
                                        query,
                                        {
                                            radius: options.radius,
                                            buildingIds: selectedIds, // Use selected IDs
                                            autoReproject: options.autoReproject,
                                            method: "solid",
                                            mergeBuildingParts: options.mergeBuildingParts,
                                        },
                                    );

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
