// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    AsyncController,
    command,
    FaceTextureService,
    IApplication,
    ICommand,
    IDocument,
    IFace,
    INode,
    IShape,
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
            imageUrl: `/textures/${this.patternId}.png`,
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
        console.log(`[ApplyTextureCommand] Selected ${this.selectedFaces.length} faces`);

        // Step 2: 面番号を生成
        await this.generateFaceNumbers(document);

        // Step 3: テクスチャパラメータをUIで設定（プロパティパネルに表示）
        // TODO: Show texture parameters in property panel
        console.log("Texture parameters ready for UI");

        // Step 4: テクスチャを適用
        await this.applyTextureWithConfirmation(document);
    }

    /**
     * 面番号を生成
     */
    private async generateFaceNumbers(document: IDocument): Promise<void> {
        // 選択された面から親形状を取得
        const processedShapes = new Set<IShape>();

        for (const face of this.selectedFaces) {
            // 面の親形状を探す（通常はソリッドまたはシェル）
            let parentShape = face;
            while (parentShape && parentShape.shapeType === ShapeType.Face) {
                // 親形状を探す処理（実際の実装では適切な方法で親を取得）
                break;
            }

            if (parentShape && !processedShapes.has(parentShape)) {
                processedShapes.add(parentShape);

                // FaceNumberDisplayの決定論的面番号生成を使用
                // 実際にはThreeGeometryから取得する必要がある
                const faceNumberMap = new Map<number, number>();

                // 仮の面番号割り当て（実際には適切な方法で生成）
                const faces = parentShape.findSubShapes(ShapeType.Face);
                faces.forEach((f, index) => {
                    if (this.selectedFaces.includes(f)) {
                        // 簡易的な面番号（実際にはFaceNumberDisplayを使用）
                        this.faceNumbers.push(index + 1);
                    }
                });
            }
        }

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
     * テクスチャを適用（確認付き）
     */
    private async applyTextureWithConfirmation(document: IDocument): Promise<void> {
        // ユーザーに確認
        const confirmed = await this.showConfirmDialog();
        if (!confirmed) {
            console.log("Texture application cancelled");
            return;
        }

        // トランザクション内でテクスチャを適用
        Transaction.execute(document, "applyTexture", () => {
            const textureData = this.parameters.toTextureData();

            // FaceTextureServiceに保存
            this.faceNumbers.forEach((faceNumber) => {
                this.textureService?.applyTextureToFace(faceNumber, textureData);
            });

            // 各面にマテリアルを適用
            this.applyMaterialToFaces(document, textureData);
        });

        console.log(`Applied texture to ${this.faceNumbers.length} faces`);
        console.log(`[ApplyTextureCommand] Applied texture to ${this.faceNumbers.length} faces`);
    }

    /**
     * 面にマテリアルを適用
     */
    private applyMaterialToFaces(document: IDocument, textureData: TextureData): void {
        // テクスチャ付きマテリアルを作成
        const material = new PhongMaterial(document, `Texture_${textureData.patternId}`, 0xffffff);

        // テクスチャを設定
        material.map.image = textureData.imageUrl;
        material.map.repeat = { x: textureData.tileCount, y: textureData.tileCount } as any;

        // 選択された面にマテリアルを適用
        // TODO: 実際の面ごとのマテリアル適用を実装
        this.selectedFaces.forEach((face) => {
            console.log(`[ApplyTextureCommand] Applying material to face:`, face);
            // face.material = material; // 実際の実装が必要
        });
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
