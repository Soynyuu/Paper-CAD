// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    command,
    GeometryNode,
    I18nKeys,
    ICommand,
    IDocument,
    RailwayTextureManager,
    RAILWAY_TEXTURE_PRESETS,
    ShapeNode,
} from "chili-core";
import { SelectStep } from "../step";

@command({
    key: "modify.applyRailwayTexture",
    icon: "icon-texture",
})
export class ApplyRailwayTextureCommand extends ICommand {
    readonly name: I18nKeys = "command.applyRailwayTexture";
    readonly display: I18nKeys = "command.applyRailwayTexture";
    readonly icon = "icon-texture";

    async execute(): Promise<void> {
        // ジオメトリノードを選択
        const step = new SelectStep("prompt.selectFace", this.document, {
            multiple: true,
            needType: GeometryNode,
        });

        const nodes = await step.execute();
        if (!nodes || nodes.length === 0) {
            this.document.application.showToast("warning", "テクスチャーを適用する面を選択してください");
            return;
        }

        // テクスチャー選択ダイアログを表示（簡易版）
        const textureId = await this.selectTexture();
        if (!textureId) {
            return;
        }

        // 選択したノードにテクスチャーを適用
        for (const node of nodes) {
            if (node instanceof GeometryNode) {
                this.applyTextureToNode(node, textureId);
            }
        }

        this.document.application.showToast("success", `テクスチャーを${nodes.length}個の面に適用しました`);
    }

    private async selectTexture(): Promise<string | null> {
        // 簡易的なテクスチャー選択（実際のUIは後で改善）
        const categories = ["walls", "roofs", "floors"];
        const category = await this.promptCategory(categories);
        if (!category) return null;

        const textures = RailwayTextureManager.getTexturesByCategory(category as any);
        if (textures.length === 0) {
            this.document.application.showToast("error", "利用可能なテクスチャーがありません");
            return null;
        }

        // テクスチャーリストから選択（簡易版）
        const options = textures.map((t) => ({
            value: t.id,
            label: `${t.nameJa} (${t.realSizeMm}mm)`,
        }));

        // 最初のテクスチャーを返す（実際のUIは後で実装）
        return textures[0].id;
    }

    private async promptCategory(categories: string[]): Promise<string | null> {
        // カテゴリ選択（簡易版）
        return categories[0];
    }

    private applyTextureToNode(node: GeometryNode, textureId: string): void {
        const preset = RailwayTextureManager.getPresetById(textureId);
        if (!preset) return;

        // ノードのマテリアルにテクスチャー情報を保存
        // 実際のレンダリングはthreeVisualObjectで処理される
        const material = node.material;
        if (material) {
            // カスタムプロパティとしてテクスチャーIDを保存
            (material as any).railwayTextureId = textureId;

            // マテリアルの更新をトリガー
            material.color = material.color; // プロパティ変更をトリガー
        }
    }
}