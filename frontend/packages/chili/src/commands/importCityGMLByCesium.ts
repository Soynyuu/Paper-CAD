// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    CityGMLService,
    command,
    DialogResult,
    I18n,
    IApplication,
    ICommand,
    PubSub,
    Transaction,
} from "chili-core";
import { PlateauCesiumPickerDialog, type PlateauCesiumPickerResult } from "chili-ui";

@command({
    key: "file.importCityGMLByCesium",
    icon: "icon-3d-map",
    isApplicationCommand: true,
})
export class ImportCityGMLByCesium implements ICommand {
    private cityGMLService: CityGMLService;

    constructor() {
        // Use the configured API URL from environment
        const apiUrl = __APP_CONFIG__.stepUnfoldApiUrl || "http://localhost:8001/api";
        this.cityGMLService = new CityGMLService(apiUrl);
    }

    async execute(application: IApplication): Promise<void> {
        // Open Cesium 3D Tiles picker dialog
        PlateauCesiumPickerDialog.show(
            application,
            async (result: DialogResult, data?: PlateauCesiumPickerResult) => {
                if (result !== DialogResult.ok || !data || data.selectedBuildings.length === 0) {
                    return;
                }

                const buildings = data.selectedBuildings;
                console.log(
                    `[ImportCityGMLByCesium] User selected ${buildings.length} building(s):`,
                    buildings,
                );

                // Get or create document
                let document =
                    application.activeView?.document ??
                    (await application.newDocument("PLATEAU Cesium Import"));

                // Convert and import buildings
                PubSub.default.pub(
                    "showPermanent",
                    async () => {
                        try {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.converting:{0}",
                                buildings.length.toString(),
                            );

                            const conversions: Array<{ blob: Blob; building: (typeof buildings)[0] }> = [];
                            const failedBuildings: string[] = [];

                            // Convert each building to STEP
                            for (let i = 0; i < buildings.length; i++) {
                                const building = buildings[i];
                                console.log(
                                    `[ImportCityGMLByCesium] Converting building ${i + 1}/${buildings.length}: ${building.gmlId}`,
                                );

                                try {
                                    const result =
                                        await this.cityGMLService.fetchAndConvertByBuildingIdAndMesh(
                                            building.gmlId,
                                            building.meshCode,
                                            {
                                                debug: false,
                                                mergeBuildingParts: false,
                                            },
                                        );

                                    if (!result.isOk) {
                                        console.error(
                                            `[ImportCityGMLByCesium] Failed to convert ${building.gmlId}:`,
                                            result.error,
                                        );
                                        failedBuildings.push(building.properties.name || building.gmlId);
                                        continue;
                                    }

                                    // Store blob WITH its corresponding building metadata
                                    conversions.push({ blob: result.value, building });
                                } catch (error) {
                                    console.error(
                                        `[ImportCityGMLByCesium] Exception converting ${building.gmlId}:`,
                                        error,
                                    );
                                    failedBuildings.push(building.properties.name || building.gmlId);
                                }
                            }

                            if (conversions.length === 0) {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.allConversionsFailed:{0}",
                                    failedBuildings.join(", "),
                                );
                                return;
                            }

                            // Import all converted STEP files
                            await Transaction.executeAsync(
                                document,
                                "import PLATEAU Cesium models",
                                async () => {
                                    for (let i = 0; i < conversions.length; i++) {
                                        const { blob, building } = conversions[i]; // Correct mapping!
                                        const filename = `cesium_${building.properties.name || building.gmlId.substring(0, 20)}_${i + 1}.step`;
                                        const stepFile = new File([blob], filename, {
                                            type: "application/step",
                                        });

                                        await document.application.dataExchange.import(document, [stepFile]);
                                    }
                                },
                            );

                            // Fit camera and show success
                            document.application.activeView?.cameraController.fitContent();

                            // Success message
                            if (failedBuildings.length > 0) {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.cesiumImportSuccessWithFailures:{0}:{1}:{2}",
                                    conversions.length.toString(),
                                    failedBuildings.length.toString(),
                                    failedBuildings.join(", "),
                                );
                            } else {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.cesiumImportSuccess:{0}",
                                    conversions.length.toString(),
                                );
                            }

                            console.log("[ImportCityGMLByCesium] Import successful:", {
                                succeeded: conversions.length,
                                failed: failedBuildings.length,
                            });
                        } catch (error) {
                            const errorMessage = error instanceof Error ? error.message : "Unknown error";
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.cesiumImportFailed:{0}",
                                errorMessage,
                            );
                            console.error("[ImportCityGMLByCesium] Import failed:", error);
                        }
                    },
                    "toast.excuting{0}",
                    "command.file.importCityGMLByCesium",
                );
            },
        );
    }
}
