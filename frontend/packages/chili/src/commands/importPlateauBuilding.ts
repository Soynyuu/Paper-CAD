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
    type LodTarget,
} from "chili-core";
import type { PlateauCesiumPickerResult } from "chili-ui/src/plateauCesiumPickerDialog";

@command({
    key: "file.importPlateauBuilding",
    icon: "icon-import-plateau",
    isApplicationCommand: true,
})
export class ImportPlateauBuilding implements ICommand {
    private cityGMLService: CityGMLService;

    private resolveSearchMeshCode(meshCode: string, rawMeshCode?: string): string {
        const normalizedRaw = rawMeshCode?.trim();
        if (normalizedRaw) {
            if (/^\d{8}$/.test(normalizedRaw)) {
                return normalizedRaw;
            }
            if (/^\d{9,10}$/.test(normalizedRaw)) {
                return normalizedRaw.slice(0, 8);
            }
        }
        return meshCode;
    }

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
            const action = data.action ?? "import";
            console.log(`[ImportPlateauBuilding] User selected ${buildings.length} building(s):`, buildings);

            // Convert and import buildings
            PubSub.default.pub(
                "showPermanent",
                async () => {
                    try {
                        if (action === "unfoldBeta") {
                            const targetBuilding = buildings[0];
                            if (!targetBuilding) {
                                return;
                            }
                            if (buildings.length > 1) {
                                console.warn(
                                    "[ImportPlateauBuilding] unfoldBeta currently uses first selected building only",
                                );
                            }

                            const unfoldOptions = await this.getCurrentUnfoldOptions();
                            const lodTarget = data.lodTargetByGmlId?.[targetBuilding.gmlId] ?? "auto";
                            const targetMeshCode = this.resolveSearchMeshCode(
                                targetBuilding.meshCode,
                                targetBuilding.properties.meshcode,
                            );
                            const unfoldResult = await this.cityGMLService.unfoldTexturedByBuildingIdAndMesh(
                                targetBuilding.gmlId,
                                targetMeshCode,
                                {
                                    debug: false,
                                    mergeBuildingParts: false,
                                    scaleMode: unfoldOptions.scaleMode,
                                    scaleFactor: unfoldOptions.scale,
                                    layoutMode: unfoldOptions.layoutMode,
                                    pageFormat: unfoldOptions.pageFormat,
                                    pageOrientation: unfoldOptions.pageOrientation,
                                    mirrorHorizontal: unfoldOptions.mirrorHorizontal,
                                    curveMode: unfoldOptions.curveMode,
                                    lodTarget,
                                },
                            );

                            if (!unfoldResult.isOk) {
                                console.error(
                                    `[ImportPlateauBuilding] Textured unfold failed:`,
                                    unfoldResult.error,
                                );
                                PubSub.default.pub("showToast", "toast.stepUnfold.error");
                                return;
                            }

                            (PubSub.default as any).pub("stepUnfold.showResult", unfoldResult.value);
                            PubSub.default.pub("showToast", "toast.stepUnfold.success");
                            if (unfoldResult.value.building?.lod_fallback) {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.lodFallback:{0}:{1}:{2}",
                                    targetBuilding.properties.name || targetBuilding.gmlId,
                                    unfoldResult.value.building.lod_requested,
                                    unfoldResult.value.building.lod_used,
                                );
                            }
                            console.log("[ImportPlateauBuilding] Textured unfold generated");
                            return;
                        }

                        // Import mode (default)
                        const document =
                            application.activeView?.document ??
                            (await application.newDocument("PLATEAU Building Import"));

                        PubSub.default.pub(
                            "showToast",
                            "toast.plateau.converting:{0}",
                            buildings.length.toString(),
                        );

                        const successfulImports: Array<{
                            building: (typeof buildings)[number];
                            blob: Blob;
                            requestedLod: LodTarget;
                            usedLod: string;
                            lodFallback: boolean;
                        }> = [];
                        const failedBuildings: string[] = [];

                        // Convert each building to STEP
                        for (let i = 0; i < buildings.length; i++) {
                            const building = buildings[i];
                            console.log(
                                `[ImportPlateauBuilding] Converting building ${i + 1}/${buildings.length}: ${building.gmlId}`,
                            );

                            try {
                                const meshCodeForFetch = this.resolveSearchMeshCode(
                                    building.meshCode,
                                    building.properties.meshcode,
                                );
                                const result = await this.cityGMLService.fetchAndConvertByBuildingIdAndMesh(
                                    building.gmlId,
                                    meshCodeForFetch,
                                    {
                                        debug: false,
                                        mergeBuildingParts: false,
                                        lodTarget: data.lodTargetByGmlId?.[building.gmlId] ?? "auto",
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

                                successfulImports.push({
                                    building,
                                    blob: result.value.blob,
                                    requestedLod: result.value.requestedLod,
                                    usedLod: result.value.usedLod,
                                    lodFallback: result.value.lodFallback,
                                });
                            } catch (error) {
                                console.error(
                                    `[ImportPlateauBuilding] Exception converting ${building.gmlId}:`,
                                    error,
                                );
                                failedBuildings.push(building.properties.name || building.gmlId);
                            }
                        }

                        if (successfulImports.length === 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.allConversionsFailed:{0}",
                                failedBuildings.join(", "),
                            );
                            return;
                        }

                        // Import all converted STEP files
                        await Transaction.executeAsync(document, "import PLATEAU buildings", async () => {
                            for (let i = 0; i < successfulImports.length; i++) {
                                const imported = successfulImports[i];
                                const building = imported.building;
                                const filename = `plateau_${building.properties.name || building.gmlId.substring(0, 20)}_${i + 1}.step`;
                                const stepFile = new File([imported.blob], filename, {
                                    type: "application/step",
                                });

                                await document.application.dataExchange.import(document, [stepFile]);
                            }
                        });

                        // Fit camera and show success
                        document.application.activeView?.cameraController.fitContent();

                        successfulImports
                            .filter((imported) => imported.lodFallback)
                            .forEach((imported) => {
                                PubSub.default.pub(
                                    "showToast",
                                    "toast.plateau.lodFallback:{0}:{1}:{2}",
                                    imported.building.properties.name || imported.building.gmlId,
                                    imported.requestedLod,
                                    imported.usedLod,
                                );
                            });

                        // Success message
                        if (failedBuildings.length > 0) {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.importSuccessWithFailures:{0}:{1}:{2}",
                                successfulImports.length.toString(),
                                failedBuildings.length.toString(),
                                failedBuildings.join(", "),
                            );
                        } else {
                            PubSub.default.pub(
                                "showToast",
                                "toast.plateau.importSuccess:{0}",
                                successfulImports.length.toString(),
                            );
                        }

                        console.log("[ImportPlateauBuilding] Import successful:", {
                            succeeded: successfulImports.length,
                            failed: failedBuildings.length,
                        });
                    } catch (error) {
                        const errorMessage = error instanceof Error ? error.message : "Unknown error";
                        if (action === "unfoldBeta") {
                            PubSub.default.pub("showToast", "toast.stepUnfold.error");
                        } else {
                            PubSub.default.pub("showToast", "toast.plateau.importFailed:{0}", errorMessage);
                        }
                        console.error("[ImportPlateauBuilding] Process failed:", error);
                    }
                },
                "toast.excuting{0}",
                "command.file.importPlateauBuilding",
            );
        };

        // Use React-based unified search + Cesium picker dialog
        const [{ renderReactDialog }, { PlateauCesiumPickerReact }] = await Promise.all([
            import("chili-ui/src/react/renderReactDialog"),
            import("chili-ui/src/react/PlateauCesiumPickerReact"),
        ]);
        cleanup = renderReactDialog(PlateauCesiumPickerReact, { onClose: handleDialogResult });
    }

    private async getCurrentUnfoldOptions(): Promise<{
        scaleMode: "fixed" | "fitPage";
        scale: number;
        layoutMode: "canvas" | "paged";
        pageFormat: "A4" | "A3" | "Letter";
        pageOrientation: "portrait" | "landscape";
        mirrorHorizontal: boolean;
        curveMode: "smooth" | "faceted";
    }> {
        const defaults = {
            scaleMode: "fixed" as const,
            scale: 10,
            layoutMode: "paged" as const,
            pageFormat: "A4" as const,
            pageOrientation: "portrait" as const,
            mirrorHorizontal: false,
            curveMode: "smooth" as const,
        };

        try {
            const { StepUnfoldPanel } = await import("chili-ui");
            const panel = StepUnfoldPanel.getInstance();
            if (!panel) {
                return defaults;
            }
            const options = panel.getCurrentOptions();
            return {
                scaleMode: options.scaleMode ?? defaults.scaleMode,
                scale: options.scale ?? defaults.scale,
                layoutMode: options.layoutMode ?? defaults.layoutMode,
                pageFormat: options.pageFormat ?? defaults.pageFormat,
                pageOrientation: options.pageOrientation ?? defaults.pageOrientation,
                mirrorHorizontal: options.mirrorHorizontal ?? defaults.mirrorHorizontal,
                curveMode: options.curveMode ?? defaults.curveMode,
            };
        } catch (error) {
            console.warn("[ImportPlateauBuilding] Failed to load unfold options; using defaults:", error);
            return defaults;
        }
    }
}
