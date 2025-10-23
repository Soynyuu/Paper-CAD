// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    AsyncController,
    CancelableCommand,
    Combobox,
    command,
    I18n,
    INode,
    Property,
    PubSub,
    ShapeNode,
    UnfoldOptions,
} from "chili-core";
import { SelectNodeWithListStep } from "../step";

@command({
    key: "file.stepUnfold",
    icon: "icon-export",
})
export class StepUnfold extends CancelableCommand {
    @Property.define("file.format")
    public get format() {
        return this.getPrivateValue("format", this.initCombobox());
    }
    public set format(value: Combobox<string>) {
        this.setProperty("format", value);
    }

    private initCombobox() {
        const box = new Combobox<string>();
        box.items.push("SVG展開図");
        box.selectedIndex = 0;
        return box;
    }

    protected async executeAsync() {
        const nodes = await this.selectNodesAsync();
        if (!nodes || nodes.length === 0) {
            PubSub.default.pub("showToast", "toast.select.noSelected");
            return;
        }

        // TODO: Get stepUnfoldService from application services
        // For now, create directly
        const { StepUnfoldService } = await import("chili-core");
        const { config } = await import("chili-core/src/config/config");

        const stepUnfoldService = new StepUnfoldService(config.stepUnfoldApiUrl);

        const selectedFormat = this.format.selectedItem;
        if (selectedFormat === undefined) {
            PubSub.default.pub("showToast", "toast.fail");
            return;
        }

        PubSub.default.pub(
            "showPermanent",
            async () => {
                try {
                    console.log("Selected nodes:", nodes);
                    console.log("First node:", nodes[0]);

                    // 選択されたノードから3D形状データを取得
                    const shapeNode = nodes[0] as ShapeNode;
                    console.log("ShapeNode:", shapeNode);
                    console.log("Has shape:", !!shapeNode.shape);

                    if (!shapeNode.shape) {
                        PubSub.default.pub("showToast", "toast.select.noSelected");
                        return;
                    }

                    // 3D形状をSTEPファイル形式でエクスポート
                    const stepData = await this.application.dataExchange.export(".step", nodes);
                    if (!stepData) {
                        PubSub.default.pub("showToast", "toast.fail");
                        return;
                    }

                    // STEPデータをunfoldサービスに送信（オプションを含む）
                    const stepBlob = Array.isArray(stepData) ? stepData[0] : stepData;

                    // StepUnfoldPanelから現在の設定を取得
                    let unfoldOptions: UnfoldOptions = {
                        scale: 1,
                        layoutMode: "canvas",
                        pageFormat: "A4",
                        pageOrientation: "portrait",
                    };

                    // StepUnfoldPanelのインスタンスから設定を取得
                    try {
                        const { StepUnfoldPanel } = await import("chili-ui");
                        const panel = StepUnfoldPanel.getInstance();
                        if (panel) {
                            unfoldOptions = panel.getCurrentOptions();
                            console.log("取得したオプション:", unfoldOptions);
                        }
                    } catch (e) {
                        console.log("デフォルトオプションを使用:", unfoldOptions);
                    }

                    // FaceTextureServiceからテクスチャマッピングを取得
                    try {
                        const { FaceTextureService } = await import("chili-core");
                        const services = (this.application as any).services;
                        if (services && Array.isArray(services)) {
                            const textureService = services.find(
                                (s: any) => s instanceof FaceTextureService,
                            );
                            if (textureService) {
                                const mappings = textureService.getUnfoldMappings();
                                if (mappings && mappings.length > 0) {
                                    // 各マッピングに画像データを追加
                                    const mappingsWithImages = await Promise.all(
                                        mappings.map(async (mapping: any) => {
                                            // テクスチャ画像をBase64エンコード
                                            const imageData = await this.loadTextureImage(mapping.patternId);
                                            return {
                                                ...mapping,
                                                imageData: imageData,
                                            };
                                        }),
                                    );
                                    unfoldOptions.textureMappings = mappingsWithImages;
                                    console.log(
                                        "[StepUnfold] テクスチャマッピングを送信（画像データ付き）:",
                                        mappingsWithImages,
                                    );
                                }
                            }
                        }
                    } catch (e) {
                        console.log("[StepUnfold] テクスチャマッピング取得エラー:", e);
                    }

                    const result = await stepUnfoldService.unfoldStepFromData(stepBlob, unfoldOptions);
                    if (result.isOk) {
                        // SVGデータを表示パネルに送信（STEPデータとオプションも含める）
                        (PubSub.default as any).pub("stepUnfold.showResult", {
                            ...result.value,
                            stepData: stepBlob, // STEPデータを追加
                            unfoldOptions: unfoldOptions, // オプションを追加
                        });
                        PubSub.default.pub("showToast", "toast.stepUnfold.success");
                    } else {
                        PubSub.default.pub("showToast", "toast.stepUnfold.error");
                    }
                } catch (error) {
                    PubSub.default.pub("showToast", "toast.stepUnfold.error");
                }
            },
            "toast.excuting{0}",
            I18n.translate("command.file.stepUnfold"),
        );
    }

    private async selectNodesAsync() {
        this.controller = new AsyncController();
        const step = new SelectNodeWithListStep("prompt.select.models", {
            multiple: false,
            keepSelection: true,
            allowListSelection: true,
            filter: {
                allow: (node: INode) => {
                    // ShapeNodeのみを選択可能にする
                    return (
                        node instanceof ShapeNode ||
                        (node as any).shape !== undefined ||
                        node.name?.toLowerCase().includes("pyramid") ||
                        node.name?.toLowerCase().includes("box") ||
                        node.name?.toLowerCase().includes("cylinder") ||
                        node.name?.toLowerCase().includes("untitled")
                    );
                },
            },
        });
        const data = await step.execute(this.application.activeView?.document!, this.controller);
        if (!data?.nodes) {
            PubSub.default.pub("showToast", "prompt.select.noModelSelected");
            return undefined;
        }
        return data.nodes;
    }

    /**
     * テクスチャ画像をBase64エンコードして返す
     * @param patternId パターンID
     * @returns Base64エンコードされた画像データ（data:image/png;base64,... 形式）
     */
    private async loadTextureImage(patternId: string): Promise<string | undefined> {
        try {
            // テクスチャ画像のURLを生成
            const imageUrl = `textures/${patternId}.png`;

            // 画像をフェッチ
            const response = await fetch(imageUrl);
            if (!response.ok) {
                console.warn(`[StepUnfold] テクスチャ画像が見つかりません: ${imageUrl}`);
                return undefined;
            }

            // Blobとして取得
            const blob = await response.blob();

            // Base64エンコード
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64Data = reader.result as string;
                    resolve(base64Data);
                };
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        } catch (error) {
            console.error(`[StepUnfold] テクスチャ画像の読み込みエラー: ${patternId}`, error);
            return undefined;
        }
    }
}
