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
    }> {
        return this.getAllMappings().map((mapping) => ({
            faceNumber: mapping.faceNumber,
            patternId: mapping.texture.patternId,
            tileCount: mapping.texture.tileCount,
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
}
