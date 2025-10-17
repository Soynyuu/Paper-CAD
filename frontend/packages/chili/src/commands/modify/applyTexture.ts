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
    IFace,
    INode,
    IShape,
    ISubFaceShape,
    Material,
    PhongMaterial,
    Property,
    PubSub,
    Result,
    Serializer,
    ShapeType,
    TextureData,
    Transaction,
    VisualState,
    XY,
} from "chili-core";
import { SelectShapeStep } from "../../step";

/**
 * テクスチャ選択パラメータ
 */
export class TextureParameters {
    @Property.define("texture.patternId")
    get patternId(): string {
        return this._patternId;
    }
    set patternId(value: string) {
        this._patternId = value;
        this.onParametersChanged();
    }
    private _patternId: string = "brick";

    @Property.define("texture.tileCount")
    get tileCount(): number {
        return this._tileCount;
    }
    set tileCount(value: number) {
        this._tileCount = value;
        this.onParametersChanged();
    }
    private _tileCount: number = 5;

    constructor(
        private document: IDocument,
        private onParametersChanged: () => void = () => {},
    ) {}

    /**
     * 現在のパラメータからテクスチャデータを生成
     */
    toTextureData(): TextureData {
        return {
            patternId: this.patternId,
            tileCount: this.tileCount,
            rotation: 0, // 初期回転は0度
            imageUrl: `textures/${this.patternId}.png`,
            repeat: { x: this.tileCount, y: this.tileCount },
        };
    }
}

/**
 * 3Dモデルの面にテクスチャを適用するコマンド
 */
@command({
    key: "modify.applyTexture",
    icon: "icon-edit",
})
export class ApplyTextureCommand implements ICommand {
    private selectedFaces: IShape[] = [];
    private selectedNodes: INode[] = [];
    private faceNumbers: number[] = [];
    private textureService: FaceTextureService | null = null;
    private parameters!: TextureParameters;

    async execute(application: IApplication): Promise<void> {
        const document = application.activeView?.document;
        if (!document) {
            PubSub.default.pub("showToast", "toast.document.noActivated");
            return;
        }
        // FaceTextureServiceを取得または作成
        this.textureService = this.getOrCreateTextureService(document.application);

        // テクスチャパラメータを初期化
        this.parameters = new TextureParameters(document, () => this.updatePreview(document));

        // Step 1: 面を選択
        console.log("[ApplyTextureCommand] Starting face selection...");
        const controller = new AsyncController();
        const selectStep = new SelectShapeStep(ShapeType.Face, "prompt.selectFacesForTexture", {
            multiple: false,
            selectedState: VisualState.edgeHighlight,
        });

        console.log("[ApplyTextureCommand] Executing SelectShapeStep...");
        const result = await selectStep.execute(document, controller);
        console.log("[ApplyTextureCommand] SelectShapeStep result:", result);

        if (!result || result.shapes.length === 0) {
            console.log("[ApplyTextureCommand] No faces selected for texture");
            return;
        }

        this.selectedFaces = result.shapes
            .map((s) => s.shape)
            .filter((shape) => shape !== undefined) as IShape[];
        this.selectedNodes = result.nodes || [];
        console.log(
            `[ApplyTextureCommand] Selected ${this.selectedFaces.length} faces, ${this.selectedNodes.length} nodes`,
        );

        // Step 2: 面番号を生成
        await this.generateFaceNumbers(document);

        // Step 3: テクスチャパラメータをUIで設定
        const textureResult = await this.showTextureSelectionDialog();
        if (!textureResult.confirmed) {
            console.log("[ApplyTextureCommand] Texture selection cancelled");
            return;
        }

        // Update parameters with user selection
        this.parameters.patternId = textureResult.patternId;
        this.parameters.tileCount = textureResult.tileCount;
        console.log("[ApplyTextureCommand] Texture parameters selected:", {
            patternId: textureResult.patternId,
            tileCount: textureResult.tileCount,
            rotation: textureResult.rotation,
        });

        // Step 4: テクスチャを適用（回転も含めて）
        await this.applyTextureDirectlyWithRotation(document, textureResult.rotation);
    }

    /**
     * 面番号を生成
     */
    private async generateFaceNumbers(document: IDocument): Promise<void> {
        // 面インデックスから面番号を計算
        // バックエンドと同じ番号体系を使用（インデックス + 1）
        this.selectedFaces.forEach((face) => {
            if ("index" in face) {
                const subFace = face as ISubFaceShape;
                const faceNumber = subFace.index + 1; // バックエンドと同じ番号体系
                this.faceNumbers.push(faceNumber);
                console.log(
                    `[ApplyTextureCommand] Face index: ${subFace.index}, Face number: ${faceNumber}`,
                );
            }
        });

        console.log(`[ApplyTextureCommand] Generated face numbers:`, this.faceNumbers);
    }

    /**
     * プレビューを更新（3Dビューでマテリアルを変更）
     */
    private updatePreview(document: IDocument): void {
        // Three.jsでのプレビュー更新
        // TODO: 実際の3Dマテリアル更新を実装
        console.log(
            `[ApplyTextureCommand] Preview update: ${this.parameters.patternId} x${this.parameters.tileCount}`,
        );
    }

    /**
     * テクスチャー選択ダイアログを表示
     */
    private async showTextureSelectionDialog(): Promise<any> {
        // Dynamically import to avoid circular dependencies
        const { TextureSelectionDialog } = await import("chili-ui");

        const dialog = new TextureSelectionDialog();
        const result = await dialog.show();
        return result;
    }

    /**
     * テクスチャを直接適用（確認ダイアログ済み、回転付き）
     */
    private async applyTextureDirectlyWithRotation(document: IDocument, rotation: number): Promise<void> {
        // テクスチャデータを準備
        const textureData = this.parameters.toTextureData();
        textureData.rotation = rotation;

        // Step 1: トランザクション内でメタデータを保存（同期処理）
        Transaction.execute(document, "applyTexture", () => {
            this.faceNumbers.forEach((faceNumber) => {
                this.textureService?.applyTextureToFace(faceNumber, textureData);
            });
        });

        // Step 2: 非同期でマテリアルとテクスチャを適用（レンダリング処理）
        await this.applyMaterialToFaces(document, textureData);

        console.log(`Applied texture to ${this.faceNumbers.length} faces with rotation ${rotation}°`);
        console.log(
            `[ApplyTextureCommand] Applied texture to ${this.faceNumbers.length} faces with rotation ${rotation}°`,
        );
    }

    /**
     * テクスチャを直接適用（確認ダイアログ済み）
     */
    private async applyTextureDirectly(document: IDocument): Promise<void> {
        await this.applyTextureDirectlyWithRotation(document, 0);
    }

    /**
     * テクスチャを適用（確認付き）
     */
    private async applyTextureWithConfirmation(document: IDocument): Promise<void> {
        // ユーザーに確認
        const confirmed = await this.showConfirmDialog();
        if (!confirmed) {
            console.log("Texture application cancelled");
            return;
        }

        // テクスチャデータを準備
        const textureData = this.parameters.toTextureData();

        // Step 1: トランザクション内でメタデータを保存（同期処理）
        Transaction.execute(document, "applyTexture", () => {
            this.faceNumbers.forEach((faceNumber) => {
                this.textureService?.applyTextureToFace(faceNumber, textureData);
            });
        });

        // Step 2: 非同期でマテリアルとテクスチャを適用（レンダリング処理）
        await this.applyMaterialToFaces(document, textureData);

        console.log(`Applied texture to ${this.faceNumbers.length} faces`);
        console.log(`[ApplyTextureCommand] Applied texture to ${this.faceNumbers.length} faces`);
    }

    /**
     * 面にマテリアルを適用（非同期）
     * テクスチャローディングを待機してから面マテリアルを適用
     */
    private async applyMaterialToFaces(document: IDocument, textureData: TextureData): Promise<void> {
        // テクスチャ付きマテリアルを作成
        const material = new PhongMaterial(
            document,
            `Texture_${textureData.patternId}_${Date.now()}`,
            0xffffff,
        );

        // テクスチャを設定
        material.map.image = textureData.imageUrl;
        material.map.repeat = new XY(textureData.tileCount, textureData.tileCount);
        // wrapSとwrapTは数値で設定（Three.jsのRepeatWrapping = 1000）
        material.map.wrapS = 1000;
        material.map.wrapT = 1000;

        // マテリアルをドキュメントに追加
        document.materials.push(material);

        // 選択された面から面インデックスを取得
        const faceIndices: number[] = [];
        this.selectedFaces.forEach((face) => {
            if ("index" in face) {
                const subFace = face as ISubFaceShape;
                faceIndices.push(subFace.index);
                console.log(`[ApplyTextureCommand] Face index: ${subFace.index}`);
            }
        });

        if (faceIndices.length === 0) {
            console.warn("[ApplyTextureCommand] No face indices found");
            return;
        }

        // 選択されたノードからGeometryNodeを探す
        const geometryNodeMap = new Map<GeometryNode, number[]>();

        // 選択されたノードを処理
        this.selectedNodes.forEach((node, index) => {
            // 親をたどってGeometryNodeを探す
            let currentNode: INode | undefined = node;
            while (currentNode) {
                // GeometryNodeかどうか確認
                if (currentNode instanceof GeometryNode) {
                    if (!geometryNodeMap.has(currentNode)) {
                        geometryNodeMap.set(currentNode, []);
                    }
                    // 対応する面インデックスを追加
                    if (index < faceIndices.length) {
                        geometryNodeMap.get(currentNode)!.push(faceIndices[index]);
                    }
                    break;
                }
                currentNode = currentNode.parent;
            }
        });

        console.log(`[ApplyTextureCommand] Found ${geometryNodeMap.size} geometry nodes`);

        // 各GeometryNodeに対して面ごとにマテリアルを適用
        if (geometryNodeMap.size > 0) {
            // forEach ではなく for...of を使用して await を有効にする
            for (const [geometryNode, faceIndices] of geometryNodeMap.entries()) {
                console.log(
                    `[ApplyTextureCommand] Applying material to ${faceIndices.length} faces on geometry node`,
                );

                // STEP 1: addFaceMaterialを先に呼んで、ThreeGeometryインスタンスを再構築させる
                // Note: addFaceMaterial() → updateVisual() → redrawNode() → dispose(old) → new ThreeGeometry
                const pairs = faceIndices.map((faceIndex) => ({
                    faceIndex: faceIndex,
                    materialId: material.id,
                }));

                console.log(`[ApplyTextureCommand] Calling addFaceMaterial to rebuild geometry instance`);
                geometryNode.addFaceMaterial(pairs);

                // STEP 2: 新しく作成されたThreeGeometryインスタンスを取得
                // CRITICAL: Must get display AFTER addFaceMaterial to get the NEW instance
                const display = document.visual.context.getVisual(geometryNode);
                console.log(`[ApplyTextureCommand] Retrieved display after rebuild:`, display);

                // STEP 3: 新しいインスタンスにテクスチャを適用
                if (display && typeof (display as any).applyTextureToFace === "function") {
                    // 全てのテクスチャを非同期で適用（必ず完了を待つ）
                    await Promise.all(
                        faceIndices.map(async (faceIndex) => {
                            console.log(
                                `[ApplyTextureCommand] Applying texture to NEW ThreeGeometry instance, face ${faceIndex}`,
                            );
                            await (display as any).applyTextureToFace(faceIndex, textureData);
                        }),
                    );
                    console.log(`[ApplyTextureCommand] All textures applied to NEW ThreeGeometry instance`);
                } else {
                    console.warn(
                        `[ApplyTextureCommand] Display not found or applyTextureToFace method missing`,
                    );
                }
            }

            // ドキュメント全体の再描画をトリガー
            document.visual.update();
            console.log(`[ApplyTextureCommand] Applied texture to selected faces`);
        } else {
            console.warn("[ApplyTextureCommand] No geometry nodes found to apply material");
        }
    }

    /**
     * 確認ダイアログを表示
     */
    private async showConfirmDialog(): Promise<boolean> {
        // シンプルな確認（実際にはUIダイアログを実装）
        return new Promise((resolve) => {
            // TODO: 実際のダイアログUI実装
            console.log("[ApplyTextureCommand] Confirm dialog - auto-confirming for now");
            resolve(true);
        });
    }

    /**
     * FaceTextureServiceを取得または作成
     */
    private getOrCreateTextureService(app: IApplication): FaceTextureService {
        // 既存のサービスを検索
        const services = app.services as any;
        let textureService = services?.find((s: any) => s instanceof FaceTextureService);

        if (!textureService) {
            // サービスが存在しない場合は作成して登録
            textureService = new FaceTextureService();
            textureService.register(app);
            textureService.start();

            // サービスリストに追加
            if (services && Array.isArray(services)) {
                services.push(textureService);
            }

            console.log("[ApplyTextureCommand] Created and registered FaceTextureService");
        }

        return textureService;
    }
}
