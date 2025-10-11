// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    CityGMLService,
    command,
    I18n,
    IApplication,
    ICommand,
    Property,
    PubSub,
    Transaction,
} from "chili-core";

@command({
    key: "file.importCityGMLByAddress",
    icon: "icon-search-location",
})
export class ImportCityGMLByAddress implements ICommand {
    @Property.define("plateau.searchQuery")
    public searchQuery: string = "";

    @Property.define("plateau.searchRadius")
    public searchRadius: number = 0.001; // ~100m in degrees

    @Property.define("plateau.buildingLimit")
    public buildingLimit: number = 1;

    @Property.define("plateau.autoReproject")
    public autoReproject: boolean = true;

    private cityGMLService: CityGMLService;

    constructor() {
        this.cityGMLService = new CityGMLService();
    }

    async execute(application: IApplication): Promise<void> {
        // Validate search query
        if (!this.searchQuery || this.searchQuery.trim() === "") {
            PubSub.default.pub("showToast", "error.plateau.emptyQuery");
            return;
        }

        const query = this.searchQuery.trim();

        // Get or create document
        let document = application.activeView?.document ?? (await application.newDocument("PLATEAU Import"));

        PubSub.default.pub(
            "showPermanent",
            async () => {
                try {
                    // Step 1: Search for buildings
                    PubSub.default.pub("showToast", "toast.plateau.searching");

                    const searchResult = await this.cityGMLService.searchByAddress(query, {
                        radius: this.searchRadius,
                        limit: this.buildingLimit > 0 ? this.buildingLimit : 10,
                    });

                    if (!searchResult.isOk) {
                        PubSub.default.pub(
                            "showToast",
                            "error.plateau.searchFailed:{0}",
                            searchResult.error,
                        );
                        return;
                    }

                    const searchData = searchResult.value;

                    if (!searchData.success || searchData.buildings.length === 0) {
                        PubSub.default.pub(
                            "showToast",
                            "error.plateau.noBuildingsFound:{0}",
                            searchData.error || query,
                        );
                        return;
                    }

                    // Log search results
                    console.log("[PLATEAU] Search results:", {
                        query,
                        geocoded: searchData.geocoding?.display_name,
                        found: searchData.found_count,
                        buildings: searchData.buildings.map((b) => ({
                            id: b.building_id || b.gml_id,
                            distance: `${b.distance_meters.toFixed(1)}m`,
                        })),
                    });

                    // Step 2: Fetch and convert
                    PubSub.default.pub("showToast", "toast.plateau.converting");

                    const stepResult = await this.cityGMLService.fetchAndConvertByAddress(query, {
                        radius: this.searchRadius,
                        buildingLimit: this.buildingLimit,
                        autoReproject: this.autoReproject,
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

                    // Step 3: Import the converted STEP data
                    await Transaction.executeAsync(document, "import PLATEAU model", async () => {
                        // Convert blob to File object
                        const filename = `${query.replace(/[^a-zA-Z0-9]/g, "_")}_plateau.step`;
                        const stepFile = new File([stepResult.value], filename, {
                            type: "application/step",
                        });

                        await document.application.dataExchange.import(document, [stepFile]);
                    });

                    // Step 4: Fit camera and show success
                    document.application.activeView?.cameraController.fitContent();

                    // Show success message with building info
                    const nearest = searchData.buildings[0];
                    const buildingId = nearest.building_id || nearest.gml_id;
                    const distance = nearest.distance_meters.toFixed(1);

                    PubSub.default.pub(
                        "showToast",
                        "toast.plateau.importSuccess:{0}:{1}m",
                        buildingId,
                        distance,
                    );

                    console.log("[PLATEAU] Import successful:", {
                        query,
                        geocoded_address: searchData.geocoding?.display_name,
                        building_id: buildingId,
                        distance_meters: nearest.distance_meters,
                        coordinates: [nearest.latitude, nearest.longitude],
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
    }
}
