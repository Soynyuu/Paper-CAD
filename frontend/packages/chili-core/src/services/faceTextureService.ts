// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { IApplication } from "../application";
import { IService } from "../service";

/**
 * テクスチャデータの型定義
 */
export interface TextureData {
    patternId: string;
    tileCount: number;
    rotation?: number; // Rotation angle in degrees (0-360)
    imageUrl: string;
    repeat?: { x: number; y: number };
    offset?: { x: number; y: number };
}

/**
 * 面番号とテクスチャのマッピングデータ
 */
export interface FaceTextureMapping {
    faceNumber: number;
    texture: TextureData;
}

/**
 * 面にテクスチャを管理するサービス
 * 3Dモデルの面番号とテクスチャデータのマッピングを保持し、
 * 展開時にバックエンドに送信するためのデータを準備する
 */
export class FaceTextureService implements IService {
    private textureMappings: Map<number, TextureData> = new Map();
    private app: IApplication | null = null;

    // Rotation editing state
    private isEditingRotation: boolean = false;
    private editingFaceNumber: number | null = null;
    private initialRotation: number = 0;

    register(app: IApplication): void {
        this.app = app;
        console.log("[FaceTextureService] Registered");
    }

    start(): void {
        console.log("[FaceTextureService] Started");
    }

    stop(): void {
        console.log("[FaceTextureService] Stopped");
        this.clearAll();
    }

    /**
     * 面にテクスチャを適用
     * @param faceNumber 面番号
     * @param textureData テクスチャデータ
     */
    applyTextureToFace(faceNumber: number, textureData: TextureData): void {
        this.textureMappings.set(faceNumber, textureData);
        console.log(`[FaceTextureService] Applied texture to face ${faceNumber}:`, textureData);
    }

    /**
     * 複数の面に同じテクスチャを適用
     * @param faceNumbers 面番号の配列
     * @param textureData テクスチャデータ
     */
    applyTextureToFaces(faceNumbers: number[], textureData: TextureData): void {
        faceNumbers.forEach((faceNumber) => {
            this.applyTextureToFace(faceNumber, textureData);
        });
    }

    /**
     * 面からテクスチャを削除
     * @param faceNumber 面番号
     */
    removeTextureFromFace(faceNumber: number): void {
        this.textureMappings.delete(faceNumber);
        console.log(`[FaceTextureService] Removed texture from face ${faceNumber}`);
    }

    /**
     * 面のテクスチャを取得
     * @param faceNumber 面番号
     * @returns テクスチャデータ（存在しない場合はundefined）
     */
    getTextureForFace(faceNumber: number): TextureData | undefined {
        return this.textureMappings.get(faceNumber);
    }

    /**
     * 全てのテクスチャマッピングを取得
     * @returns 面番号とテクスチャデータのマッピング配列
     */
    getAllMappings(): FaceTextureMapping[] {
        const mappings: FaceTextureMapping[] = [];
        this.textureMappings.forEach((texture, faceNumber) => {
            mappings.push({ faceNumber, texture });
        });
        return mappings;
    }

    /**
     * バックエンド送信用のフォーマットに変換
     * @returns バックエンドAPI用のテクスチャマッピングデータ
     */
    getBackendFormat(): Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
        rotation?: number;
    }> {
        return this.getAllMappings().map((mapping) => ({
            faceNumber: mapping.faceNumber,
            patternId: mapping.texture.patternId,
            tileCount: mapping.texture.tileCount,
            rotation: mapping.texture.rotation,
        }));
    }

    /**
     * 展開図生成用のテクスチャマッピングデータを取得
     * @returns UnfoldOptions用のテクスチャマッピングデータ
     */
    getUnfoldMappings(): Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
    }> {
        return this.getBackendFormat();
    }

    /**
     * シリアライズ（保存用）
     * @returns JSON文字列
     */
    serialize(): string {
        const data = {
            version: "1.0",
            mappings: this.getAllMappings(),
        };
        return JSON.stringify(data);
    }

    /**
     * デシリアライズ（復元用）
     * @param data JSON文字列
     */
    deserialize(data: string): void {
        try {
            const parsed = JSON.parse(data);
            if (parsed.mappings && Array.isArray(parsed.mappings)) {
                this.clearAll();
                parsed.mappings.forEach((mapping: FaceTextureMapping) => {
                    this.applyTextureToFace(mapping.faceNumber, mapping.texture);
                });
                console.log(`[FaceTextureService] Deserialized ${parsed.mappings.length} texture mappings`);
            }
        } catch (error) {
            console.error("[FaceTextureService] Failed to deserialize:", error);
        }
    }

    /**
     * 全てのマッピングをクリア
     */
    clearAll(): void {
        this.textureMappings.clear();
        console.log("[FaceTextureService] Cleared all texture mappings");
    }

    /**
     * テクスチャが適用されている面の数を取得
     * @returns テクスチャが適用されている面の数
     */
    getTexturedFaceCount(): number {
        return this.textureMappings.size;
    }

    /**
     * 特定のパターンIDを使用している面を検索
     * @param patternId パターンID
     * @returns 面番号の配列
     */
    findFacesWithPattern(patternId: string): number[] {
        const faces: number[] = [];
        this.textureMappings.forEach((texture, faceNumber) => {
            if (texture.patternId === patternId) {
                faces.push(faceNumber);
            }
        });
        return faces;
    }

    /**
     * タイルカウントを更新
     * @param faceNumber 面番号
     * @param tileCount 新しいタイルカウント
     */
    updateTileCount(faceNumber: number, tileCount: number): void {
        const texture = this.textureMappings.get(faceNumber);
        if (texture) {
            texture.tileCount = tileCount;
            console.log(`[FaceTextureService] Updated tile count for face ${faceNumber} to ${tileCount}`);
        }
    }

    /**
     * テクスチャの回転角度を更新
     * @param faceNumber 面番号
     * @param rotation 回転角度（度数、0-360）
     */
    updateTextureRotation(faceNumber: number, rotation: number): void {
        const texture = this.textureMappings.get(faceNumber);
        if (texture) {
            texture.rotation = rotation;
            console.log(`[FaceTextureService] Updated rotation for face ${faceNumber} to ${rotation}°`);
        }
    }

    /**
     * テクスチャの回転角度を取得
     * @param faceNumber 面番号
     * @returns 回転角度（度数）、テクスチャがない場合は0
     */
    getTextureRotation(faceNumber: number): number {
        const texture = this.textureMappings.get(faceNumber);
        return texture?.rotation ?? 0;
    }

    /**
     * 回転編集モードを開始
     * @param faceNumber 編集する面番号
     * @returns 現在の回転角度
     */
    startRotationEdit(faceNumber: number): number {
        const texture = this.textureMappings.get(faceNumber);
        if (!texture) {
            console.warn(`[FaceTextureService] No texture found for face ${faceNumber}`);
            return 0;
        }

        this.isEditingRotation = true;
        this.editingFaceNumber = faceNumber;
        this.initialRotation = texture.rotation ?? 0;

        console.log(
            `[FaceTextureService] Started rotation edit for face ${faceNumber}, initial: ${this.initialRotation}°`,
        );
        return this.initialRotation;
    }

    /**
     * 回転編集モードを確定
     */
    confirmRotationEdit(): void {
        if (this.isEditingRotation && this.editingFaceNumber !== null) {
            console.log(`[FaceTextureService] Confirmed rotation edit for face ${this.editingFaceNumber}`);
            this.isEditingRotation = false;
            this.editingFaceNumber = null;
            this.initialRotation = 0;
        }
    }

    /**
     * 回転編集モードをキャンセル（元の角度に戻す）
     */
    cancelRotationEdit(): void {
        if (this.isEditingRotation && this.editingFaceNumber !== null) {
            // Restore initial rotation
            this.updateTextureRotation(this.editingFaceNumber, this.initialRotation);
            console.log(
                `[FaceTextureService] Canceled rotation edit for face ${this.editingFaceNumber}, restored to ${this.initialRotation}°`,
            );

            this.isEditingRotation = false;
            this.editingFaceNumber = null;
            this.initialRotation = 0;
        }
    }

    /**
     * 現在編集中かどうか
     */
    isEditing(): boolean {
        return this.isEditingRotation;
    }

    /**
     * 現在編集中の面番号を取得
     */
    getEditingFaceNumber(): number | null {
        return this.editingFaceNumber;
    }
}
