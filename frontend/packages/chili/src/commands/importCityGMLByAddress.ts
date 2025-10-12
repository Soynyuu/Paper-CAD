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
import { PlateauSearchDialog, PlateauSearchOptions } from "chili-ui";

@command({
    key: "file.importCityGMLByAddress",
    icon: "icon-search-location",
})
export class ImportCityGMLByAddress implements ICommand {
    private cityGMLService: CityGMLService;

    constructor() {
        // Use the configured API URL from environment
        const apiUrl = __APP_CONFIG__.stepUnfoldApiUrl || "http://localhost:8001/api";
        this.cityGMLService = new CityGMLService(apiUrl);
    }

    async execute(application: IApplication): Promise<void> {
        // Show the PLATEAU search dialog
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

                // Get or create document
                let document =
                    application.activeView?.document ?? (await application.newDocument("PLATEAU Import"));

                PubSub.default.pub(
                    "showPermanent",
                    async () => {
                        try {
                            // Show search and conversion status
                            PubSub.default.pub("showToast", "toast.plateau.searching");

                            console.log("[PLATEAU] Fetching building:", {
                                query,
                                radius: options.radius,
                                buildingLimit: options.buildingLimit,
                            });

                            // Fetch and convert in one step (backend handles search internally)
                            const stepResult = await this.cityGMLService.fetchAndConvertByAddress(query, {
                                radius: options.radius,
                                buildingLimit: options.buildingLimit,
                                autoReproject: options.autoReproject,
                                method: "solid",
                            });

                            if (!stepResult.isOk) {
                                PubSub.default.pub(
                                    "showToast",
                                    "error.plateau.conversionFailed:{0}",
                                    stepResult.error,
                                );
                                return;
                            }

                            // Import the converted STEP data
                            PubSub.default.pub("showToast", "toast.plateau.converting");

                            await Transaction.executeAsync(document, "import PLATEAU model", async () => {
                                // Convert blob to File object
                                const filename = `${query.replace(/[^a-zA-Z0-9]/g, "_")}_plateau.step`;
                                const stepFile = new File([stepResult.value], filename, {
                                    type: "application/step",
                                });

                                await document.application.dataExchange.import(document, [stepFile]);
                            });

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
                                radius_degrees: options.radius,
                                radius_meters: radiusMeters,
                                building_limit: options.buildingLimit,
                            });
                        } catch (error) {
                            const errorMessage = error instanceof Error ? error.message : "Unknown error";
                            PubSub.default.pub("showToast", "error.plateau.importFailed:{0}", errorMessage);
                            console.error("[PLATEAU] Import failed:", error);
                        }
                    },
                    "toast.excuting{0}",
                    I18n.translate("command.file.importCityGMLByAddress"),
                );
            },
        );
    }
}
