// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    AsyncController,
    command,
    FaceTextureService,
    GeometryNode,
    IApplication,
    ICommand,
    IDocument,
    INode,
    IShape,
    ISubFaceShape,
    PubSub,
    ShapeType,
    Transaction,
    VisualState,
} from "chili-core";
import { SelectShapeStep } from "../../step";

/**
 * テクスチャの回転を編集するコマンド
 * 既にテクスチャが適用されている面の回転角度をリアルタイムで調整
 */
@command({
    key: "modify.editTextureRotation",
    icon: "icon-rotate",
})
export class EditTextureRotationCommand implements ICommand {
    private selectedFace: IShape | null = null;
    private selectedNode: INode | null = null;
    private faceNumber: number | null = null;
    private faceIndex: number | null = null;
    private textureService: FaceTextureService | null = null;
    private geometryNode: GeometryNode | null = null;

    async execute(application: IApplication): Promise<void> {
        const document = application.activeView?.document;
        if (!document) {
            PubSub.default.pub("showToast", "toast.document.noActivated");
            return;
        }

        // FaceTextureServiceを取得
        this.textureService = this.getTextureService(application);
        if (!this.textureService) {
            PubSub.default.pub("showToast", "error.textureService.notFound");
            console.warn("[EditTextureRotationCommand] FaceTextureService not found");
            return;
        }

        // Step 1: テクスチャが適用されている面を選択
        console.log("[EditTextureRotationCommand] Starting face selection...");
        const controller = new AsyncController();
        const selectStep = new SelectShapeStep(ShapeType.Face, "prompt.selectTexturedFace", {
            multiple: false,
            selectedState: VisualState.edgeHighlight,
        });

        const result = await selectStep.execute(document, controller);
        console.log("[EditTextureRotationCommand] SelectShapeStep result:", result);

        if (!result || result.shapes.length === 0) {
            console.log("[EditTextureRotationCommand] No face selected");
            return;
        }

        this.selectedFace = result.shapes[0].shape as IShape;
        this.selectedNode = result.nodes?.[0] || null;

        // Step 2: 面番号と面インデックスを取得
        if ("index" in this.selectedFace) {
            const subFace = this.selectedFace as ISubFaceShape;
            this.faceIndex = subFace.index;
            this.faceNumber = subFace.index + 1; // バックエンドと同じ番号体系
            console.log(
                `[EditTextureRotationCommand] Face index: ${this.faceIndex}, Face number: ${this.faceNumber}`,
            );
        } else {
            PubSub.default.pub("showToast", "error.faceNumber.notFound");
            console.warn("[EditTextureRotationCommand] Could not get face index");
            return;
        }

        // Step 3: 面にテクスチャが適用されているか確認
        const texture = this.textureService.getTextureForFace(this.faceNumber);
        if (!texture) {
            PubSub.default.pub("showToast", "error.texture.notApplied");
            console.log(`[EditTextureRotationCommand] No texture found for face ${this.faceNumber}`);
            return;
        }

        console.log(`[EditTextureRotationCommand] Found texture on face ${this.faceNumber}:`, texture);

        // Step 4: GeometryNodeを探す
        this.geometryNode = this.findGeometryNode(this.selectedNode);
        if (!this.geometryNode) {
            PubSub.default.pub("showToast", "error.geometryNode.notFound");
            console.warn("[EditTextureRotationCommand] GeometryNode not found");
            return;
        }

        console.log("[EditTextureRotationCommand] Found GeometryNode:", this.geometryNode);

        // Step 5: 回転編集モードを開始
        const initialRotation = this.textureService.startRotationEdit(this.faceNumber);
        console.log(`[EditTextureRotationCommand] Started rotation edit, initial: ${initialRotation}°`);

        // Step 6: TextureRotationToolbarを表示
        const toolbarResult = await this.showRotationToolbar(initialRotation);

        // Step 7: 結果を処理
        if (toolbarResult.confirmed) {
            // 確定: トランザクション内で最終的な回転を保存
            Transaction.execute(document, "editTextureRotation", () => {
                if (this.textureService && this.faceNumber !== null) {
                    this.textureService.updateTextureRotation(this.faceNumber, toolbarResult.rotation);
                    this.textureService.confirmRotationEdit();
                    console.log(
                        `[EditTextureRotationCommand] Confirmed rotation: ${toolbarResult.rotation}° for face ${this.faceNumber}`,
                    );
                }
            });

            PubSub.default.pub(
                "showToast",
                "toast.texture.rotationSet:{0}",
                Math.round(toolbarResult.rotation),
            );
        } else {
            // キャンセル: 元の回転に戻す
            if (this.textureService && this.faceNumber !== null && this.faceIndex !== null) {
                this.textureService.cancelRotationEdit();
                // Three.jsでも元の回転に戻す
                this.updateThreeJsRotation(document, initialRotation);
                console.log(
                    `[EditTextureRotationCommand] Cancelled rotation edit, restored to ${initialRotation}°`,
                );
            }
        }
    }

    /**
     * TextureRotationToolbarを表示
     */
    private async showRotationToolbar(initialRotation: number): Promise<any> {
        // Dynamically import to avoid circular dependencies
        const { TextureRotationToolbar } = await import("chili-ui");

        const toolbar = new TextureRotationToolbar();

        // リアルタイム変更のコールバックを設定
        toolbar.onChange((rotation: number) => {
            this.onRotationChange(rotation);
        });

        const result = await toolbar.show(initialRotation);
        return result;
    }

    /**
     * 回転が変更されたときのコールバック（リアルタイムプレビュー）
     */
    private onRotationChange(rotation: number): void {
        if (!this.textureService || this.faceNumber === null || this.faceIndex === null) {
            return;
        }

        // FaceTextureServiceを更新
        this.textureService.updateTextureRotation(this.faceNumber, rotation);

        // Three.jsの表示を更新
        const document = this.geometryNode?.document;
        if (document) {
            this.updateThreeJsRotation(document, rotation);
        }

        console.log(`[EditTextureRotationCommand] Real-time rotation update: ${rotation}°`);
    }

    /**
     * Three.jsでテクスチャの回転を更新
     */
    private updateThreeJsRotation(document: IDocument, rotation: number): void {
        if (!this.geometryNode || this.faceIndex === null) {
            return;
        }

        // VisualContextからThreeGeometryを取得
        const display = document.visual.context.getVisual(this.geometryNode);
        if (!display) {
            console.warn("[EditTextureRotationCommand] No display found on GeometryNode");
            return;
        }

        // displayオブジェクトがupdateTextureRotationメソッドを持っているか確認
        if (typeof (display as any).updateTextureRotation === "function") {
            (display as any).updateTextureRotation(this.faceIndex, rotation);
            console.log(`[EditTextureRotationCommand] Updated Three.js texture rotation: ${rotation}°`);
        } else {
            console.warn("[EditTextureRotationCommand] display.updateTextureRotation method not found");
        }

        // ドキュメント全体の再描画をトリガー
        document.visual.update();
    }

    /**
     * ノードの親をたどってGeometryNodeを探す
     */
    private findGeometryNode(node: INode | null): GeometryNode | null {
        let currentNode: INode | undefined = node || undefined;
        while (currentNode) {
            if (currentNode instanceof GeometryNode) {
                return currentNode;
            }
            currentNode = currentNode.parent;
        }
        return null;
    }

    /**
     * FaceTextureServiceを取得
     */
    private getTextureService(app: IApplication): FaceTextureService | null {
        const services = app.services as any;
        const textureService = services?.find((s: any) => s instanceof FaceTextureService);

        if (!textureService) {
            console.warn("[EditTextureRotationCommand] FaceTextureService not found in app.services");
        }

        return textureService || null;
    }
}
