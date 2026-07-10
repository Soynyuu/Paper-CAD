// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    BufferAttribute,
    BufferGeometry,
    CanvasTexture,
    DoubleSide,
    Group,
    Line,
    LineBasicMaterial,
    Mesh,
    MeshBasicMaterial,
    Sprite,
    SpriteMaterial,
    Vector3,
} from "three";
import { IShape, IFace, ShapeType } from "chili-core";

interface FaceGeometryData {
    position: Float32Array;
    index?: Uint32Array;
}

interface FaceNumberMarker {
    faceIndex: number;
    faceNumber: number;
    anchorPosition?: Vector3;
    position: Vector3;
    normal?: Vector3;
    faceGeometry?: FaceGeometryData;
    faceSize?: number;
}

export class FaceNumberDisplay extends Group {
    private sprites: Map<string, Sprite> = new Map();
    private markers: Map<number, FaceNumberMarker[]> = new Map();
    private highlightOverlays: Map<string, Mesh> = new Map();
    private calloutLines: Map<string, Line> = new Map();
    private _visible: boolean = false;
    // バックエンドから受信した面番号データを保存
    private backendFaceNumbers: Map<number, number> = new Map();
    private requireBackendFaceNumber: boolean = false;
    // モデルのバウンディングボックスサイズ（動的オフセット計算用）
    private modelSize: number = 0;
    private modelCenter: Vector3 = new Vector3();
    // ハイライトされた面番号を追跡
    private highlightedFaces: Set<number> = new Set();
    // 面インデックスから面番号へのマッピング（ハイライト時に使用）
    private faceIndexToNumber: Map<number, number> = new Map();
    private focusedFaceNumber: number | null = null;

    constructor() {
        super();
        this.name = "FaceNumbers";
        // デフォルトモデルサイズを設定
        this.modelSize = 100;
    }

    private getMarkerKey(marker: FaceNumberMarker): string {
        return `${marker.faceNumber}:${marker.faceIndex}`;
    }

    private setMarker(marker: FaceNumberMarker): void {
        const markers = this.markers.get(marker.faceNumber) ?? [];
        const existingIndex = markers.findIndex((item) => item.faceIndex === marker.faceIndex);
        if (existingIndex >= 0) {
            markers[existingIndex] = marker;
        } else {
            markers.push(marker);
        }
        this.markers.set(marker.faceNumber, markers);
    }

    private getMarkers(faceNumber: number): FaceNumberMarker[] {
        return this.markers.get(faceNumber) ?? [];
    }

    private getAllMarkers(): FaceNumberMarker[] {
        return Array.from(this.markers.values()).flat();
    }

    private getMarkerCount(): number {
        return this.getAllMarkers().length;
    }

    /**
     * 面番号の表示/非表示を切り替え
     */
    setVisible(visible: boolean): void {
        this._visible = visible;
        this.visible = visible;
        this.applyDisplayFilter();
    }

    /**
     * 決定論的な面番号を生成（バックエンドと同じロジック）
     * 法線ベクトルの向きに基づいて面番号を割り当てる
     * @param shape 対象の形状
     * @returns 面インデックスから面番号へのマッピング
     */
    public generateDeterministicFaceNumbers(shape: IShape): Map<number, number> {
        const faceNumberMap = new Map<number, number>();
        if (!shape) return faceNumberMap;

        const faces = shape.findSubShapes(ShapeType.Face);
        console.log(`[FaceNumberDisplay] Generating deterministic face numbers for ${faces.length} faces`);

        // 各面の法線と中心を計算
        const faceData: Array<{
            index: number;
            normal: Vector3;
            center: Vector3;
        }> = [];

        faces.forEach((face: IShape, index: number) => {
            const normal = this.getFaceNormal(face as IFace);
            const center = this.getFaceCenter(face as IFace);

            if (normal && center) {
                faceData.push({ index, normal, center });
            }
        });

        // 法線の主成分に基づいて面を分類し、番号を割り当てる
        // X軸正方向 -> 1, X軸負方向 -> 2, Y軸正方向 -> 3, Y軸負方向 -> 4, Z軸正方向 -> 5, Z軸負方向 -> 6
        const threshold = 0.7; // 法線の主成分を判定する閾値
        let faceNumber = 1;

        // 優先順位: +X, -X, +Y, -Y, +Z, -Z
        const directions = [
            { axis: "x", positive: true },
            { axis: "x", positive: false },
            { axis: "y", positive: true },
            { axis: "y", positive: false },
            { axis: "z", positive: true },
            { axis: "z", positive: false },
        ];

        const assigned = new Set<number>();

        for (const dir of directions) {
            for (const data of faceData) {
                if (assigned.has(data.index)) continue;

                const normalComponent =
                    dir.axis === "x" ? data.normal.x : dir.axis === "y" ? data.normal.y : data.normal.z;

                const isAligned = dir.positive ? normalComponent > threshold : normalComponent < -threshold;

                if (isAligned) {
                    faceNumberMap.set(data.index, faceNumber);
                    assigned.add(data.index);
                    console.log(
                        `[FaceNumberDisplay] Face ${data.index} -> Number ${faceNumber} (${dir.axis}${dir.positive ? "+" : "-"})`,
                    );
                    faceNumber++;
                }
            }
        }

        // 主軸に整列していない面には連番を割り当てる
        for (const data of faceData) {
            if (!assigned.has(data.index)) {
                faceNumberMap.set(data.index, faceNumber);
                console.log(`[FaceNumberDisplay] Face ${data.index} -> Number ${faceNumber} (other)`);
                faceNumber++;
            }
        }

        console.log(`[FaceNumberDisplay] Generated ${faceNumberMap.size} face numbers`);
        return faceNumberMap;
    }

    /**
     * バックエンドから受信した面番号データを設定
     * @param faceNumbers 面インデックスと面番号のマッピング
     */
    setBackendFaceNumbers(
        faceNumbers: Map<number, number> | Array<{ faceIndex: number; faceNumber: number }>,
        requireMatch: boolean = false,
    ): void {
        this.backendFaceNumbers.clear();
        this.requireBackendFaceNumber = requireMatch;

        if (Array.isArray(faceNumbers)) {
            // 配列の場合はMapに変換
            faceNumbers.forEach(({ faceIndex, faceNumber }) => {
                this.backendFaceNumbers.set(faceIndex, faceNumber);
            });
        } else {
            // Mapの場合はそのまま設定
            this.backendFaceNumbers = new Map(faceNumbers);
        }

        console.log("🟢 setBackendFaceNumbers: 受信した面番号データ:", {
            count: this.backendFaceNumbers.size,
            data: Array.from(this.backendFaceNumbers.entries()),
            currentSpriteCount: this.sprites.size,
        });

        if (this.markers.size > 0) {
            console.log("🟢 FaceNumberDisplay: 既存の面番号マーカーを更新します");
            this.remapExistingMarkers();
        } else if (this.sprites.size > 0) {
            console.log("🟢 FaceNumberDisplay: 既存の表示を更新します");
            this.updateExistingSprites();
        } else {
            console.log("🟢 FaceNumberDisplay: まだスプライトがありません（後で生成時に使用されます）");
        }
    }

    /**
     * 形状から面番号を生成（バックエンドの面番号を使用）
     */
    generateFromShape(shape: IShape): void {
        // 既存のスプライトをクリア
        this.clearNumbers();
        this.clearHighlightOverlays();
        this.markers.clear();
        this.faceIndexToNumber.clear();

        if (!shape) {
            console.log("FaceNumberDisplay: No shape provided");
            return;
        }

        // モデル全体のサイズを計算（動的オフセット用）
        this.modelSize = this.calculateModelSize(shape);
        console.log(`FaceNumberDisplay: Model size calculated: ${this.modelSize}`);

        // 各面に対して番号を生成
        const faces = shape.findSubShapes(ShapeType.Face);
        console.log(`FaceNumberDisplay: Found ${faces.length} faces`);
        console.log("FaceNumberDisplay: Processing faces with backend face numbers...");

        faces.forEach((face: IShape, index: number) => {
            console.log(`\n=== Processing Face ${index} ===`);
            console.log(`Face type: ${face.shapeType}`);

            let center = this.getFaceCenter(face as IFace);
            const normal = this.getFaceNormal(face as IFace);

            // フォールバック：面の中心が取得できない場合は、メッシュ情報から推定
            if (!center) {
                console.log(`Face ${index}: Primary center calculation failed, trying mesh estimation`);
                center = this.estimateFaceCenterFromMesh(face, index, shape);
            }

            // バックエンドから受信した面番号を使用
            const backendNumber = this.backendFaceNumbers.get(index);
            if (this.requireBackendFaceNumber && backendNumber === undefined) {
                console.warn(`FaceNumberDisplay: no verified correspondence for face ${index}`);
                return;
            }
            const faceNumber = backendNumber !== undefined ? backendNumber : index + 1; // フォールバック：インデックス+1

            // 面インデックスから面番号へのマッピングを保存
            this.faceIndexToNumber.set(index, faceNumber);

            console.log("🟡 generateFromShape: 面", index, "の番号決定:", {
                backendNumber: backendNumber,
                finalFaceNumber: faceNumber,
                hasBackendData: this.backendFaceNumbers.size > 0,
            });

            if (center) {
                console.log(
                    `🟡 FaceNumberDisplay: Face ${index} - Final center:`,
                    center,
                    "Normal:",
                    normal,
                    "Final face number:",
                    faceNumber,
                );
                const anchorPosition = center.clone();
                const faceMesh = (face as IFace).mesh?.faces;
                const faceSize = faceMesh?.position
                    ? this.calculatePositionBounds(faceMesh.position).size
                    : 0;
                const position = this.calculateLabelPosition(anchorPosition, normal, faceSize, index);

                this.setMarker({
                    faceIndex: index,
                    faceNumber,
                    anchorPosition,
                    position,
                    normal: normal?.clone().normalize(),
                    faceGeometry: faceMesh?.position
                        ? {
                              position: faceMesh.position.slice(),
                              index: faceMesh.index?.slice(),
                          }
                        : undefined,
                    faceSize,
                });
            } else {
                console.log(`FaceNumberDisplay: ERROR - Could not get center for face ${index}`);
            }
        });

        this.applyDisplayFilter();
        console.log(
            `FaceNumberDisplay: Prepared ${this.markers.size} face numbers, rendering ${this.sprites.size}`,
        );
    }

    /**
     * 既存のスプライトの面番号を更新する
     */
    private updateExistingSprites(): void {
        console.log("FaceNumberDisplay: 既存スプライトの面番号を更新中...");

        // 現在のスプライトの位置情報を保存
        const spritePositions = new Map<number, Vector3>();
        const sprites = Array.from(this.sprites.values());

        sprites.forEach((sprite, index) => {
            const faceIndex = (sprite.userData["faceIndex"] as number | undefined) ?? index;
            spritePositions.set(faceIndex, sprite.position.clone());
        });

        // 全てのスプライトをクリア
        this.clearNumbers();
        this.markers.clear();
        this.faceIndexToNumber.clear();

        // バックエンドの面番号を使用して新しいスプライトを作成
        Array.from(spritePositions.keys()).forEach((faceIndex) => {
            const position = spritePositions.get(faceIndex);
            const backendFaceNumber = this.backendFaceNumbers.get(faceIndex);

            if (position && backendFaceNumber !== undefined) {
                console.log(
                    `Updating face ${faceIndex}: old number was at position, new number is ${backendFaceNumber}`,
                );

                this.setMarker({
                    faceIndex,
                    faceNumber: backendFaceNumber,
                    position,
                });
                this.faceIndexToNumber.set(faceIndex, backendFaceNumber);
            }
        });

        this.applyDisplayFilter();
        console.log(`FaceNumberDisplay: Updated ${this.sprites.size} sprites with backend face numbers`);
    }

    private remapExistingMarkers(): void {
        const existingMarkers = this.getAllMarkers();
        this.clearNumbers();
        this.clearHighlightOverlays();
        this.markers.clear();
        this.faceIndexToNumber.clear();

        const nextHighlighted = new Set<number>();
        existingMarkers.forEach((marker) => {
            const backendFaceNumber = this.backendFaceNumbers.get(marker.faceIndex);
            if (this.requireBackendFaceNumber && backendFaceNumber === undefined) return;
            const nextFaceNumber = backendFaceNumber ?? marker.faceNumber;
            const nextMarker: FaceNumberMarker = {
                ...marker,
                faceNumber: nextFaceNumber,
                position: marker.position.clone(),
                normal: marker.normal?.clone(),
            };

            this.setMarker(nextMarker);
            this.faceIndexToNumber.set(marker.faceIndex, nextFaceNumber);

            if (this.highlightedFaces.has(marker.faceNumber)) {
                nextHighlighted.add(nextFaceNumber);
            }
        });

        this.highlightedFaces = nextHighlighted;
        this.focusedFaceNumber =
            this.focusedFaceNumber === null ? null : (Array.from(nextHighlighted.values())[0] ?? null);

        this.applyDisplayFilter();
    }

    /**
     * 面の中心座標を取得（シンプルで確実な計算）
     */
    private getFaceCenter(face: IFace): Vector3 | null {
        // Prefer an area-weighted point that stays on small and concave faces.
        const meshCenter = this.calculateFaceCenterFromMesh(face);
        if (meshCenter) {
            console.log("Face center calculated from mesh data:", meshCenter);
            return meshCenter;
        }

        const boundingBoxCenter = this.calculateFaceBoundingBoxCenter(face);
        if (boundingBoxCenter) {
            return boundingBoxCenter;
        }

        // Final fallback: use a point on the parametric surface.
        try {
            const [point, _] = face.normal(0.5, 0.5);
            if (!point) {
                console.warn("Could not get face center point from normal()");
                return null;
            }

            console.log("Face center from normal(0.5, 0.5) fallback:", point);
            return new Vector3(point.x, point.y, point.z);
        } catch (error) {
            console.warn("Failed to get face center:", error);
            return null;
        }
    }

    /**
     * 面のバウンディングボックスから中心を計算
     */
    private calculateFaceBoundingBoxCenter(face: IFace): Vector3 | null {
        try {
            const mesh = face.mesh;
            if (!mesh?.faces?.position) {
                console.log("No face mesh data available");
                return null;
            }

            const positions = mesh.faces.position;
            if (positions.length === 0) {
                console.log("Empty positions array");
                return null;
            }

            // 面のすべての頂点からバウンディングボックスを計算
            let minX = Infinity,
                maxX = -Infinity;
            let minY = Infinity,
                maxY = -Infinity;
            let minZ = Infinity,
                maxZ = -Infinity;

            for (let i = 0; i < positions.length; i += 3) {
                const x = positions[i];
                const y = positions[i + 1];
                const z = positions[i + 2];

                minX = Math.min(minX, x);
                maxX = Math.max(maxX, x);
                minY = Math.min(minY, y);
                maxY = Math.max(maxY, y);
                minZ = Math.min(minZ, z);
                maxZ = Math.max(maxZ, z);
            }

            // バウンディングボックスの中心を計算
            const center = new Vector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);

            console.log(
                `Face bounding box: [${minX.toFixed(2)}, ${minY.toFixed(2)}, ${minZ.toFixed(2)}] to [${maxX.toFixed(2)}, ${maxY.toFixed(2)}, ${maxZ.toFixed(2)}]`,
            );
            console.log("Face bounding box center:", center);

            return center;
        } catch (error) {
            console.warn("Failed to calculate face bounding box center:", error);
            return null;
        }
    }

    /**
     * 面のメッシュデータから正確な重心を計算
     */
    private calculateFaceCenterFromMesh(face: IFace): Vector3 | null {
        try {
            const mesh = face.mesh;
            if (!mesh?.faces?.position) {
                console.log("No mesh data available for face");
                return null;
            }

            const positions = mesh.faces.position;
            const indices = mesh.faces.index;

            console.log(`Face mesh - positions: ${positions.length}, indices: ${indices?.length}`);

            if (indices && indices.length > 0) {
                // インデックスがある場合は、三角形の重心を計算
                return this.calculateTriangleCentroid(positions, indices);
            } else {
                // インデックスがない場合は、単純な頂点の平均
                return this.calculateVertexAverage(positions);
            }
        } catch (error) {
            console.warn("Failed to calculate face center from mesh:", error);
            return null;
        }
    }

    /**
     * 三角形メッシュから重心を計算（改良版）
     */
    private calculateTriangleCentroid(positions: Float32Array, indices: Uint32Array): Vector3 {
        let totalArea = 0;
        let weightedCenterX = 0,
            weightedCenterY = 0,
            weightedCenterZ = 0;

        console.log(`Computing centroid from ${indices.length / 3} triangles`);

        // 各三角形の重心と面積で重みづけされた平均を計算
        for (let i = 0; i < indices.length; i += 3) {
            const i1 = indices[i] * 3;
            const i2 = indices[i + 1] * 3;
            const i3 = indices[i + 2] * 3;

            // 三角形の頂点
            const v1 = new Vector3(positions[i1], positions[i1 + 1], positions[i1 + 2]);
            const v2 = new Vector3(positions[i2], positions[i2 + 1], positions[i2 + 2]);
            const v3 = new Vector3(positions[i3], positions[i3 + 1], positions[i3 + 2]);

            // 三角形の重心
            const triangleCenter = new Vector3(
                (v1.x + v2.x + v3.x) / 3,
                (v1.y + v2.y + v3.y) / 3,
                (v1.z + v2.z + v3.z) / 3,
            );

            // 三角形の面積を計算（外積の半分）
            const edge1 = new Vector3().subVectors(v2, v1);
            const edge2 = new Vector3().subVectors(v3, v1);
            const crossProduct = new Vector3().crossVectors(edge1, edge2);
            const area = crossProduct.length() / 2;

            // 面積が非常に小さい三角形（退化三角形）をスキップ
            if (area > 0.000001) {
                totalArea += area;
                weightedCenterX += triangleCenter.x * area;
                weightedCenterY += triangleCenter.y * area;
                weightedCenterZ += triangleCenter.z * area;
            }
        }

        if (totalArea > 0.000001) {
            const centroid = new Vector3(
                weightedCenterX / totalArea,
                weightedCenterY / totalArea,
                weightedCenterZ / totalArea,
            );
            console.log(`Calculated precise triangle centroid:`, centroid, `totalArea: ${totalArea}`);
            return centroid;
        }

        console.log("Triangle centroid failed, falling back to vertex average");
        // フォールバックとして頂点の平均を返す
        return this.calculateVertexAverage(positions);
    }

    /**
     * 頂点の単純平均を計算
     */
    private calculateVertexAverage(positions: Float32Array): Vector3 {
        let centerX = 0,
            centerY = 0,
            centerZ = 0;
        const vertexCount = positions.length / 3;

        for (let i = 0; i < positions.length; i += 3) {
            centerX += positions[i];
            centerY += positions[i + 1];
            centerZ += positions[i + 2];
        }

        const average = new Vector3(centerX / vertexCount, centerY / vertexCount, centerZ / vertexCount);
        console.log(`Calculated vertex average:`, average, `from ${vertexCount} vertices`);
        return average;
    }

    /**
     * メッシュ情報から面の中心座標を推定
     */
    private estimateFaceCenterFromMesh(face: IShape, faceIndex: number, shape: IShape): Vector3 | null {
        try {
            // 面のメッシュデータから中心を推定
            const faceMesh = face.mesh;
            if (faceMesh?.faces?.position) {
                const positions = faceMesh.faces.position;
                let centerX = 0,
                    centerY = 0,
                    centerZ = 0;
                const vertexCount = positions.length / 3;

                // すべての頂点の平均を計算
                for (let i = 0; i < positions.length; i += 3) {
                    centerX += positions[i];
                    centerY += positions[i + 1];
                    centerZ += positions[i + 2];
                }

                if (vertexCount > 0) {
                    const center = new Vector3(
                        centerX / vertexCount,
                        centerY / vertexCount,
                        centerZ / vertexCount,
                    );
                    console.log(`Estimated face ${faceIndex} center from mesh vertices:`, center);
                    return center;
                }
            }

            // フォールバック: 簡単な位置推定
            console.log(`Using simple fallback for face ${faceIndex}`);
            const offset = 30;
            const positions = [
                new Vector3(0, 0, offset), // 前面
                new Vector3(0, 0, -offset), // 背面
                new Vector3(offset, 0, 0), // 右面
                new Vector3(-offset, 0, 0), // 左面
                new Vector3(0, offset, 0), // 上面
                new Vector3(0, -offset, 0), // 下面
            ];

            if (faceIndex < positions.length) {
                console.log(`Using fallback position for face ${faceIndex}:`, positions[faceIndex]);
                return positions[faceIndex];
            }

            return null;
        } catch (error) {
            console.warn(`Failed to estimate center for face ${faceIndex}:`, error);
            return null;
        }
    }

    /**
     * モデル全体のサイズを計算（バウンディングボックスの対角線長）
     */
    private calculatePositionBounds(positions: Float32Array): { center: Vector3; size: number } {
        let minX = Infinity;
        let minY = Infinity;
        let minZ = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        let maxZ = -Infinity;
        for (let i = 0; i < positions.length; i += 3) {
            minX = Math.min(minX, positions[i]);
            minY = Math.min(minY, positions[i + 1]);
            minZ = Math.min(minZ, positions[i + 2]);
            maxX = Math.max(maxX, positions[i]);
            maxY = Math.max(maxY, positions[i + 1]);
            maxZ = Math.max(maxZ, positions[i + 2]);
        }
        const center = new Vector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);
        return { center, size: new Vector3(maxX - minX, maxY - minY, maxZ - minZ).length() };
    }

    private calculateLabelPosition(
        anchor: Vector3,
        normal: Vector3 | null,
        faceSize: number,
        faceIndex: number,
    ): Vector3 {
        // Keep the whole camera-facing badge clear of its source surface. A tiny
        // epsilon leaves the corners of an oblique sprite behind the face and
        // makes the badge look sliced in half.
        const surfaceOffset = Math.max(this.modelSize * 0.004, 0.05);
        if (faceSize >= this.modelSize * 0.025) {
            return normal
                ? anchor.clone().addScaledVector(normal.clone().normalize(), surfaceOffset)
                : anchor.clone();
        }

        const outward = anchor.clone().sub(this.modelCenter);
        if (outward.lengthSq() < 1e-12 && normal) outward.copy(normal);
        if (outward.lengthSq() < 1e-12) outward.set(1, 0, 0);
        outward.normalize();
        const angle = faceIndex * 2.399963229728653;
        const jitter = new Vector3(Math.cos(angle), Math.sin(angle), Math.sin(angle * 0.5)).normalize();
        const distance = Math.min(this.modelSize * 0.03, Math.max(this.modelSize * 0.012, faceSize * 2));
        return anchor
            .clone()
            .addScaledVector(outward, distance)
            .addScaledVector(jitter, distance * 0.35);
    }

    private calculateModelSize(shape: IShape): number {
        try {
            const mesh = shape.mesh;
            if (!mesh?.faces?.position) {
                console.log("FaceNumberDisplay: No mesh data for size calculation, using default");
                return 100; // デフォルトサイズ
            }

            const bounds = this.calculatePositionBounds(mesh.faces.position);
            this.modelCenter.copy(bounds.center);
            return bounds.size || 100;
        } catch (error) {
            console.warn("Failed to calculate model size:", error);
            return 100; // デフォルトサイズ
        }
    }

    /**
     * 面の法線ベクトルを取得
     */
    private getFaceNormal(face: IFace): Vector3 | null {
        try {
            // 面の中心での法線を取得
            const [_, normal] = face.normal(0.5, 0.5);
            if (!normal) {
                console.warn("Could not get normal from face.normal()");
                return null;
            }

            console.log("Face normal:", normal);
            return new Vector3(normal.x, normal.y, normal.z);
        } catch (error) {
            console.warn("Failed to get face normal:", error);
            return null;
        }
    }

    /**
     * 番号スプライトを作成
     */
    private createNumberSprite(
        number: number,
        isHighlighted: boolean = false,
        isDense: boolean = false,
    ): Sprite {
        const canvas = document.createElement("canvas");
        const size = 256;
        canvas.width = size;
        canvas.height = size;

        const context = canvas.getContext("2d");
        if (!context) {
            throw new Error("Failed to get canvas context");
        }

        const label = number.toString();
        const radius = 56;
        const badgeWidth = Math.min(210, Math.max(132, 82 + label.length * 42));
        const badgeHeight = 116;
        const x = (size - badgeWidth) / 2;
        const y = (size - badgeHeight) / 2;

        context.shadowColor = "rgba(15, 23, 42, 0.22)";
        context.shadowBlur = 14;
        context.shadowOffsetY = 8;
        context.fillStyle = isHighlighted ? "rgba(255, 248, 220, 0.96)" : "rgba(255, 255, 255, 0.92)";
        this.roundRect(context, x, y, badgeWidth, badgeHeight, radius);
        context.fill();

        context.shadowColor = "transparent";
        context.lineWidth = isHighlighted ? 10 : 7;
        context.strokeStyle = isHighlighted ? "#f59e0b" : "rgba(37, 99, 235, 0.88)";
        this.roundRect(context, x + 4, y + 4, badgeWidth - 8, badgeHeight - 8, radius - 4);
        context.stroke();

        context.fillStyle = isHighlighted ? "#92400e" : "#1e3a8a";
        const fontSize = label.length >= 4 ? 64 : label.length === 3 ? 76 : 92;
        context.font = `700 ${fontSize}px Arial, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(label, size / 2, size / 2 + 3);

        // テクスチャとマテリアルを作成
        const texture = new CanvasTexture(canvas);
        const material = new SpriteMaterial({
            map: texture,
            sizeAttenuation: false, // ズームしても面番号のサイズを一定に保つ
            depthTest: !isHighlighted,
            depthWrite: false,
            // Avoid z-fighting with the labelled surface while retaining depth
            // testing against geometry in front of the label.
            polygonOffset: !isHighlighted,
            polygonOffsetFactor: -1,
            polygonOffsetUnits: -1,
            transparent: true,
        });

        const sprite = new Sprite(material);
        // 画面上で一定のサイズを保つ固定スケール
        // ハイライト時は少し大きくする
        const scale = isHighlighted ? 0.06 : isDense ? 0.034 : 0.046;
        sprite.scale.set(scale, scale, 1);
        sprite.name = `FaceNumber_${number}`;
        sprite.renderOrder = 999; // 最前面に表示
        sprite.frustumCulled = false; // カメラに関係なく常に表示

        return sprite;
    }

    private applyDisplayFilter(): void {
        const visibleNumbers = this.getVisibleFaceNumbers();

        Array.from(this.sprites.entries()).forEach(([key, sprite]) => {
            const faceNumber = sprite.userData["faceNumber"] as number | undefined;
            if (faceNumber === undefined || !this._visible || !visibleNumbers.has(faceNumber)) {
                this.removeSprite(key);
            }
        });

        if (!this._visible) {
            this.clearCalloutLines();
            this.syncHighlightOverlays();
            return;
        }

        const isDense = this.getMarkerCount() > 96;
        visibleNumbers.forEach((faceNumber) => {
            const markers = this.getMarkers(faceNumber);
            if (markers.length === 0) return;

            const highlighted = this.highlightedFaces.has(faceNumber);
            markers.forEach((marker) => {
                const key = this.getMarkerKey(marker);
                const existing = this.sprites.get(key);
                if (existing) {
                    if (
                        existing.userData["highlighted"] !== highlighted ||
                        existing.userData["dense"] !== isDense
                    ) {
                        this.removeSprite(key);
                    } else {
                        existing.position.copy(marker.position);
                        return;
                    }
                }

                const sprite = this.createNumberSprite(faceNumber, highlighted, isDense);
                sprite.userData["highlighted"] = highlighted;
                sprite.userData["dense"] = isDense;
                sprite.userData["faceNumber"] = faceNumber;
                sprite.userData["faceIndex"] = marker.faceIndex;
                sprite.position.copy(marker.position);
                this.sprites.set(key, sprite);
                this.add(sprite);
            });
        });

        this.syncCalloutLines();
        this.syncHighlightOverlays();
    }

    private syncCalloutLines(): void {
        this.clearCalloutLines();
        this.getAllMarkers().forEach((marker) => {
            const anchor = marker.anchorPosition;
            if (!anchor || anchor.distanceToSquared(marker.position) < 1e-10) return;
            const geometry = new BufferGeometry().setFromPoints([anchor, marker.position]);
            const material = new LineBasicMaterial({
                color: this.highlightedFaces.has(marker.faceNumber) ? 0xf59e0b : 0x2563eb,
                depthTest: !this.highlightedFaces.has(marker.faceNumber),
                depthWrite: false,
                transparent: true,
                opacity: this.highlightedFaces.has(marker.faceNumber) ? 1 : 0.8,
            });
            const line = new Line(geometry, material);
            line.renderOrder = 997;
            line.frustumCulled = false;
            const key = this.getMarkerKey(marker);
            this.calloutLines.set(key, line);
            this.add(line);
        });
    }

    private clearCalloutLines(): void {
        this.calloutLines.forEach((line) => {
            line.geometry.dispose();
            (line.material as LineBasicMaterial).dispose();
            this.remove(line);
        });
        this.calloutLines.clear();
    }

    private getVisibleFaceNumbers(): Set<number> {
        const numbers = Array.from(this.markers.keys()).sort((a, b) => a - b);
        const visible = new Set<number>(numbers);

        this.highlightedFaces.forEach((number) => {
            if (this.markers.has(number)) {
                visible.add(number);
            }
        });

        if (this.focusedFaceNumber !== null && this.markers.has(this.focusedFaceNumber)) {
            visible.add(this.focusedFaceNumber);
        }

        return visible;
    }

    private removeSprite(key: string): void {
        const sprite = this.sprites.get(key);
        if (!sprite) return;

        sprite.material.dispose();
        (sprite.material as SpriteMaterial).map?.dispose();
        this.remove(sprite);
        this.sprites.delete(key);
    }

    private syncHighlightOverlays(): void {
        Array.from(this.highlightOverlays.entries()).forEach(([key, overlay]) => {
            const faceNumber = overlay.userData["faceNumber"] as number | undefined;
            if (faceNumber === undefined || !this._visible || !this.highlightedFaces.has(faceNumber)) {
                this.removeHighlightOverlay(key);
            }
        });

        if (!this._visible) return;

        this.highlightedFaces.forEach((faceNumber) => {
            this.getMarkers(faceNumber).forEach((marker) => {
                const key = this.getMarkerKey(marker);
                if (this.highlightOverlays.has(key) || !marker.faceGeometry) return;

                const overlay = this.createHighlightOverlay(marker);
                this.highlightOverlays.set(key, overlay);
                this.add(overlay);
            });
        });
    }

    private createHighlightOverlay(marker: FaceNumberMarker): Mesh {
        const geometry = new BufferGeometry();
        geometry.setAttribute("position", new BufferAttribute(marker.faceGeometry!.position, 3));
        if (marker.faceGeometry!.index?.length) {
            geometry.setIndex(new BufferAttribute(marker.faceGeometry!.index!, 1));
        }
        geometry.computeVertexNormals();
        const material = new MeshBasicMaterial({
            color: 0xf59e0b,
            transparent: true,
            opacity: 0.42,
            side: DoubleSide,
            depthTest: false,
            depthWrite: false,
            polygonOffset: true,
            polygonOffsetFactor: -8,
            polygonOffsetUnits: -8,
        });
        const overlay = new Mesh(geometry, material);
        overlay.name = `FaceNumberHighlight_${marker.faceNumber}_${marker.faceIndex}`;
        overlay.userData["faceNumber"] = marker.faceNumber;
        overlay.userData["faceIndex"] = marker.faceIndex;
        overlay.renderOrder = 998;
        overlay.frustumCulled = false;

        return overlay;
    }

    private removeHighlightOverlay(key: string): void {
        const overlay = this.highlightOverlays.get(key);
        if (!overlay) return;

        overlay.geometry.dispose();
        if (Array.isArray(overlay.material)) {
            overlay.material.forEach((material) => material.dispose());
        } else {
            overlay.material.dispose();
        }
        this.remove(overlay);
        this.highlightOverlays.delete(key);
    }

    private clearHighlightOverlays(): void {
        Array.from(this.highlightOverlays.keys()).forEach((faceNumber) => {
            this.removeHighlightOverlay(faceNumber);
        });
    }

    private roundRect(
        context: CanvasRenderingContext2D,
        x: number,
        y: number,
        width: number,
        height: number,
        radius: number,
    ): void {
        const r = Math.min(radius, width / 2, height / 2);
        context.beginPath();
        context.moveTo(x + r, y);
        context.lineTo(x + width - r, y);
        context.quadraticCurveTo(x + width, y, x + width, y + r);
        context.lineTo(x + width, y + height - r);
        context.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
        context.lineTo(x + r, y + height);
        context.quadraticCurveTo(x, y + height, x, y + height - r);
        context.lineTo(x, y + r);
        context.quadraticCurveTo(x, y, x + r, y);
        context.closePath();
    }

    /**
     * 指定された位置に面番号を作成
     */
    createFaceNumbersAtPositions(positions: Array<{ x: number; y: number; z: number }>): void {
        // 既存のスプライトをクリア
        this.clearNumbers();
        this.clearHighlightOverlays();
        this.markers.clear();
        this.faceIndexToNumber.clear();

        positions.forEach((pos, index) => {
            const faceNumber = index + 1;
            this.setMarker({
                faceIndex: index,
                faceNumber,
                position: new Vector3(pos.x, pos.y, pos.z),
            });
            this.faceIndexToNumber.set(index, faceNumber);
            console.log(`FaceNumberDisplay: Added face number ${faceNumber} at`, pos);
        });

        this.applyDisplayFilter();
        console.log(`FaceNumberDisplay: Total sprites created: ${this.sprites.size}`);
        console.log(`FaceNumberDisplay: Children count: ${this.children.length}`);
    }

    /**
     * 簡易的に面番号を作成（位置は自動配置）
     */
    createSimpleFaceNumber(faceNumber: number): void {
        // 立方体の6面に対応する位置を設定（より離れた位置に配置）
        const positions = [
            new Vector3(0, 0, 100), // 前面
            new Vector3(0, 0, -100), // 背面
            new Vector3(100, 0, 0), // 右面
            new Vector3(-100, 0, 0), // 左面
            new Vector3(0, 100, 0), // 上面
            new Vector3(0, -100, 0), // 下面
        ];

        if (faceNumber <= positions.length) {
            this.setMarker({
                faceIndex: faceNumber - 1,
                faceNumber,
                position: positions[faceNumber - 1].clone(),
            });
        } else {
            // 追加の面の場合はランダム配置
            this.setMarker({
                faceIndex: faceNumber - 1,
                faceNumber,
                position: new Vector3(
                    (Math.random() - 0.5) * 60,
                    (Math.random() - 0.5) * 60,
                    (Math.random() - 0.5) * 60,
                ),
            });
        }

        this.applyDisplayFilter();
        console.log(`FaceNumberDisplay: Added simple face number ${faceNumber}`);
    }

    /**
     * 全ての番号をクリア
     */
    clearNumbers(): void {
        this.sprites.forEach((sprite) => {
            sprite.material.dispose();
            (sprite.material as SpriteMaterial).map?.dispose();
            this.remove(sprite);
        });
        this.sprites.clear();
        this.clearCalloutLines();
        this.clearHighlightOverlays();
    }

    /**
     * 特定の面番号をハイライト
     * @param faceNumber ハイライトする面番号
     */
    highlightFace(faceNumber: number): boolean {
        if (!this.markers.has(faceNumber)) {
            console.warn(`Face ${faceNumber} not found`);
            return false;
        }

        if (this.highlightedFaces.has(faceNumber)) {
            console.log(`Face ${faceNumber} is already highlighted`);
            return true;
        }

        this.highlightedFaces.add(faceNumber);
        this.focusedFaceNumber = faceNumber;
        this.applyDisplayFilter();
        console.log(`Highlighted face ${faceNumber}`);
        return true;
    }

    focusFace(faceNumber: number): boolean {
        if (!this.markers.has(faceNumber)) {
            console.warn(`Face ${faceNumber} not found`);
            return false;
        }

        this.highlightedFaces.clear();
        this.highlightedFaces.add(faceNumber);
        this.focusedFaceNumber = faceNumber;
        this.applyDisplayFilter();
        return true;
    }

    getFaceFocusInfo(faceNumber: number): { center: Vector3; radius: number } | undefined {
        const marker = this.getMarkers(faceNumber)[0];
        if (!marker) return undefined;
        this.updateWorldMatrix(true, false);
        const localCenter = marker.anchorPosition ?? marker.position;
        const center = this.localToWorld(localCenter.clone());
        const localEdge = localCenter
            .clone()
            .add(new Vector3(marker.faceSize || this.modelSize * 0.01, 0, 0));
        const radius = Math.max(center.distanceTo(this.localToWorld(localEdge)), this.modelSize * 0.002);
        return { center, radius };
    }

    /**
     * 特定の面番号のハイライトを解除
     * @param faceNumber ハイライトを解除する面番号
     */
    unhighlightFace(faceNumber: number): void {
        if (!this.highlightedFaces.has(faceNumber)) {
            console.log(`Face ${faceNumber} is not highlighted`);
            return;
        }

        this.highlightedFaces.delete(faceNumber);
        if (this.focusedFaceNumber === faceNumber) {
            this.focusedFaceNumber = null;
        }
        this.applyDisplayFilter();
        console.log(`Unhighlighted face ${faceNumber}`);
    }

    /**
     * すべての面のハイライトを解除
     */
    clearHighlights(): void {
        this.highlightedFaces.clear();
        this.focusedFaceNumber = null;
        this.applyDisplayFilter();
        console.log("Cleared all highlights");
    }

    /**
     * 現在ハイライトされている面番号を取得
     * @returns ハイライトされている面番号の配列
     */
    getHighlightedFaces(): number[] {
        return Array.from(this.highlightedFaces);
    }

    /**
     * 面番号のハイライト状態を切り替え
     * @param faceNumber 切り替える面番号
     */
    toggleHighlight(faceNumber: number): boolean {
        if (this.highlightedFaces.has(faceNumber)) {
            this.unhighlightFace(faceNumber);
            return true;
        } else {
            return this.highlightFace(faceNumber);
        }
    }

    /**
     * スプライトのハイライト状態を更新
     * @param faceNumber 更新する面番号
     * @param isHighlighted ハイライト状態
     */
    private updateSpriteHighlight(faceNumber: number, isHighlighted: boolean): void {
        const marker = this.getMarkers(faceNumber)[0];
        const key = marker ? this.getMarkerKey(marker) : "";
        const sprite = this.sprites.get(key);
        if (!sprite) {
            console.warn(`Sprite for face ${faceNumber} not found`);
            return;
        }

        // 既存のスプライトの位置を保存
        const position = sprite.position.clone();

        // 古いスプライトを削除
        sprite.material.dispose();
        (sprite.material as SpriteMaterial).map?.dispose();
        this.remove(sprite);
        this.sprites.delete(key);

        // 新しいスプライトを作成（ハイライト状態を反映）
        const newSprite = this.createNumberSprite(faceNumber, isHighlighted);
        newSprite.position.copy(position);

        this.sprites.set(key, newSprite);
        this.add(newSprite);
        this.applyDisplayFilter();
    }

    /**
     * 面インデックスから面番号を取得
     * @param faceIndex 面インデックス
     * @returns 対応する面番号（見つからない場合はundefined）
     */
    getFaceNumberByIndex(faceIndex: number): number | undefined {
        return this.faceIndexToNumber.get(faceIndex);
    }

    /**
     * 利用可能なすべての面番号を取得
     * @returns 面番号の配列
     */
    getAllFaceNumbers(): number[] {
        if (this.markers.size > 0) {
            return Array.from(this.markers.keys()).sort((a, b) => a - b);
        }

        const spriteNumbers = Array.from(this.sprites.values())
            .map((sprite) => sprite.userData["faceNumber"] as number | undefined)
            .filter((faceNumber): faceNumber is number => faceNumber !== undefined);
        return Array.from(new Set(spriteNumbers)).sort((a, b) => a - b);
    }

    getFaceNumberOccurrences(faceNumber: number): number {
        return this.getMarkers(faceNumber).length;
    }

    getMultiFaceNumbers(): Array<{ faceNumber: number; count: number }> {
        return Array.from(this.markers.entries())
            .filter(([, markers]) => markers.length > 1)
            .map(([faceNumber, markers]) => ({ faceNumber, count: markers.length }))
            .sort((a, b) => a.faceNumber - b.faceNumber);
    }

    getFaceOccurrenceCount(): number {
        return this.getMarkerCount();
    }

    getDisplayStats(): { total: number; visible: number; limited: boolean } {
        const total = this.getMarkerCount();
        return {
            total,
            visible: this.sprites.size,
            limited: false,
        };
    }

    /**
     * クリーンアップ
     */
    dispose(): void {
        this.clearNumbers();
        this.clearHighlightOverlays();
        this.markers.clear();
        this.highlightedFaces.clear();
        this.faceIndexToNumber.clear();
        this.focusedFaceNumber = null;
        this.backendFaceNumbers.clear();
        this.requireBackendFaceNumber = false;
    }
}
