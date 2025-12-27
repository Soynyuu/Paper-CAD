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
                                I18n.translate("toast.plateau.converting").replace(
                                    "{0}",
                                    buildings.length.toString(),
                                ),
                            );

                            const stepBlobs: Blob[] = [];
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

                                    stepBlobs.push(result.value);
                                } catch (error) {
                                    console.error(
                                        `[ImportCityGMLByCesium] Exception converting ${building.gmlId}:`,
                                        error,
                                    );
                                    failedBuildings.push(building.properties.name || building.gmlId);
                                }
                            }

                            if (stepBlobs.length === 0) {
                                PubSub.default.pub(
                                    "showToast",
                                    `All conversions failed. Failed buildings: ${failedBuildings.join(", ")}`,
                                );
                                return;
                            }

                            // Import all converted STEP files
                            await Transaction.executeAsync(
                                document,
                                "import PLATEAU Cesium models",
                                async () => {
                                    for (let i = 0; i < stepBlobs.length; i++) {
                                        const building = buildings[i];
                                        const filename = `cesium_${building.properties.name || building.gmlId.substring(0, 20)}_${i + 1}.step`;
                                        const stepFile = new File([stepBlobs[i]], filename, {
                                            type: "application/step",
                                        });

                                        await document.application.dataExchange.import(document, [stepFile]);
                                    }
                                },
                            );

                            // Fit camera and show success
                            document.application.activeView?.cameraController.fitContent();

                            // Success message
                            const successMsg =
                                failedBuildings.length > 0
                                    ? I18n.translate("toast.plateau.cesiumImportSuccess")
                                          .replace("{0}", stepBlobs.length.toString())
                                          .concat(
                                              ` (${failedBuildings.length} failed: ${failedBuildings.join(", ")})`,
                                          )
                                    : I18n.translate("toast.plateau.cesiumImportSuccess").replace(
                                          "{0}",
                                          stepBlobs.length.toString(),
                                      );

                            PubSub.default.pub("showToast", successMsg);

                            console.log("[ImportCityGMLByCesium] Import successful:", {
                                succeeded: stepBlobs.length,
                                failed: failedBuildings.length,
                            });
                        } catch (error) {
                            const errorMessage = error instanceof Error ? error.message : "Unknown error";
                            PubSub.default.pub("showToast", `Import failed: ${errorMessage}`);
                            console.error("[ImportCityGMLByCesium] Import failed:", error);
                        }
                    },
                    "toast.excuting{0}",
                    I18n.translate("command.file.importCityGMLByCesium"),
                );
            },
        );
    }
}
