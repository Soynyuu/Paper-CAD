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
    readFilesAsync,
    Transaction,
} from "chili-core";

@command({
    key: "file.importCityGML",
    icon: "icon-import",
})
export class ImportCityGML implements ICommand {
    @Property.define("citygml.defaultHeight")
    public defaultHeight: number = 10.0;

    @Property.define("citygml.buildingLimit")
    public buildingLimit: number = 50;

    @Property.define("citygml.autoReproject")
    public autoReproject: boolean = true;

    @Property.define("citygml.buildingIds")
    public buildingIds: string = "";

    @Property.define("citygml.filterAttribute")
    public filterAttribute: string = "gml:id";

    private cityGMLService: CityGMLService;

    constructor() {
        this.cityGMLService = new CityGMLService();
    }

    async execute(application: IApplication): Promise<void> {
        // Read CityGML files with explicit MIME types for better filtering
        const files = await readFilesAsync(".gml,.xml,application/gml+xml,text/xml,application/xml", false);
        if (!files.isOk || files.value.length === 0) {
            if (files.error) {
                alert(files.error);
            }
            return;
        }

        const file = files.value[0];

        // Validate file extension explicitly
        const fileName = file.name.toLowerCase();
        if (!fileName.endsWith(".gml") && !fileName.endsWith(".xml")) {
            PubSub.default.pub("showToast", "error.import.invalidFileExtension");
            return;
        }

        // Check if it's likely a CityGML file by content
        const isCityGML = await this.checkIfCityGML(file);
        if (!isCityGML) {
            PubSub.default.pub("showToast", "error.import.notCityGML");
            return;
        }

        // Get or create document
        let document = application.activeView?.document ?? (await application.newDocument("CityGML Import"));

        PubSub.default.pub(
            "showPermanent",
            async () => {
                try {
                    // Convert CityGML to STEP
                    PubSub.default.pub("showToast", "toast.citygml.converting");

                    // Parse building IDs if provided
                    const buildingIdsArray =
                        this.buildingIds.trim() !== ""
                            ? this.buildingIds
                                  .split(",")
                                  .map((id) => id.trim())
                                  .filter((id) => id !== "")
                            : undefined;

                    const stepResult = await this.cityGMLService.convertToStep(file, {
                        defaultHeight: this.defaultHeight,
                        limit: this.buildingLimit === 0 ? undefined : this.buildingLimit,
                        autoReproject: this.autoReproject,
                        buildingIds: buildingIdsArray,
                        filterAttribute: this.filterAttribute,
                    });

                    if (!stepResult.isOk) {
                        PubSub.default.pub(
                            "showToast",
                            "error.citygml.conversionFailed:{0}",
                            stepResult.error,
                        );
                        return;
                    }

                    // Import the converted STEP data
                    await Transaction.executeAsync(document, "import CityGML model", async () => {
                        // Convert blob to File object for the data exchange
                        const stepFile = new File([stepResult.value], "converted.step", {
                            type: "application/step",
                        });

                        await document.application.dataExchange.import(document, [stepFile]);
                    });

                    document.application.activeView?.cameraController.fitContent();
                    PubSub.default.pub("showToast", "toast.citygml.importSuccess");
                } catch (error) {
                    const errorMessage = error instanceof Error ? error.message : "Unknown error";
                    PubSub.default.pub("showToast", "error.citygml.importFailed:{0}", errorMessage);
                }
            },
            "toast.excuting{0}",
            I18n.translate("command.file.importCityGML"),
        );
    }

    private async checkIfCityGML(file: File): Promise<boolean> {
        // Quick check for CityGML content
        const slice = file.slice(0, 4096);
        const text = await slice.text();

        return (
            text.includes("citygml") ||
            text.includes("CityGML") ||
            text.includes("bldg:") ||
            text.includes("<Building") ||
            (text.includes("gml:") && text.includes("xmlns"))
        );
    }
}
