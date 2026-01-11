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
import { type PlateauCesiumPickerResult, renderReactDialog, PlateauCesiumPickerReact } from "chili-ui";

@command({
    key: "file.importPlateauBuilding",
    icon: "icon-3d-map",
    isApplicationCommand: true,
})
export class ImportPlateauBuilding implements ICommand {
    private cityGMLService: CityGMLService;

    constructor() {
        console.log("[ImportPlateauBuilding] Command registered and constructor called");
        // Use the configured API URL from environment
        const apiUrl = __APP_CONFIG__.stepUnfoldApiUrl || "http://localhost:8001/api";
        this.cityGMLService = new CityGMLService(apiUrl);
    }

    async execute(application: IApplication): Promise<void> {
        let cleanup: (() => void) | undefined;

        // Unified dialog with integrated search and Cesium picker
        const handleDialogResult = async (result: DialogResult, data?: PlateauCesiumPickerResult) => {
            cleanup?.();
            cleanup = undefined;

            if (result !== DialogResult.ok || !data || data.selectedBuildings.length === 0) {
                return;
            }

            const buildings = data.selectedBuildings;
            console.log(`[ImportPlateauBuilding] User selected ${buildings.length} building(s):`, buildings);

            // Get or create document
            let document =
                application.activeView?.document ??
                (await application.newDocument("PLATEAU Building Import"));

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

                        const stepBlobs: Blob[] = [];
                        const failedBuildings: string[] = [];

                        // Convert each building to STEP
                        for (let i = 0; i < buildings.length; i++) {
                            const building = buildings[i];
                            console.log(
                                `[ImportPlateauBuilding] Converting building ${i + 1}/${buildings.length}: ${building.gmlId}`,
                            );

                            try {
                                const result = await this.cityGMLService.fetchAndConvertByBuildingIdAndMesh(
                                    building.gmlId,
                                    building.meshCode,
                                    {
                                        debug: false,
                                        mergeBuildingParts: false,
                                    },
                                );

                                if (!result.isOk) {
                                    console.error(
                                        `[ImportPlateauBuilding] Failed to convert ${building.gmlId}:`,
                                        result.error,
                                    );
                                    failedBuildings.push(building.properties.name || building.gmlId);
                                    continue;
                                }

                                stepBlobs.push(result.value);
                            } catch (error) {
                                console.error(
                                    `[ImportPlateauBuilding] Exception converting ${building.gmlId}:`,
                                    error,
                                );
                                failedBuildings.push(building.properties.name || building.gmlId);
                            }
                        }

                        if (stepBlobs.length === 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.allConversionsFailed:{0}",
                                failedBuildings.join(", "),
                            );
                            return;
                        }

                        // Import all converted STEP files
                        await Transaction.executeAsync(document, "import PLATEAU buildings", async () => {
                            for (let i = 0; i < stepBlobs.length; i++) {
                                const building = buildings[i];
                                const filename = `plateau_${building.properties.name || building.gmlId.substring(0, 20)}_${i + 1}.step`;
                                const stepFile = new File([stepBlobs[i]], filename, {
                                    type: "application/step",
                                });

                                await document.application.dataExchange.import(document, [stepFile]);
                            }
                        });

                        // Fit camera and show success
                        document.application.activeView?.cameraController.fitContent();

                        // Success message
                        if (failedBuildings.length > 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.importSuccessWithFailures:{0}:{1}:{2}",
                                stepBlobs.length.toString(),
                                failedBuildings.length.toString(),
                                failedBuildings.join(", "),
                            );
                        } else {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.importSuccess:{0}",
                                stepBlobs.length.toString(),
                            );
                        }

                        console.log("[ImportPlateauBuilding] Import successful:", {
                            succeeded: stepBlobs.length,
                            failed: failedBuildings.length,
                        });
                    } catch (error) {
                        const errorMessage = error instanceof Error ? error.message : "Unknown error";
                        PubSub.default.pub("showToast", "toast.plateau.importFailed:{0}", errorMessage);
                        console.error("[ImportPlateauBuilding] Import failed:", error);
                    }
                },
                "toast.excuting{0}",
                "command.file.importPlateauBuilding",
            );
        };

        // Use React-based unified search + Cesium picker dialog
        cleanup = renderReactDialog(PlateauCesiumPickerReact, { onClose: handleDialogResult });
    }
}
