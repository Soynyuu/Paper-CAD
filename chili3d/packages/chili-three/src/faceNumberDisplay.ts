// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { CanvasTexture, Sprite, SpriteMaterial, Vector3, Group } from "three";
import { IShape, IFace, ShapeType } from "chili-core";

export class FaceNumberDisplay extends Group {
    private sprites: Map<number, Sprite> = new Map();
    private _visible: boolean = false;
    // バックエンドから受信した面番号データを保存
    private backendFaceNumbers: Map<number, number> = new Map();
    // モデルのバウンディングボックスサイズ（動的オフセット計算用）
    private modelSize: number = 0;

    constructor() {
        super();
        this.name = "FaceNumbers";
        // デフォルトモデルサイズを設定
        this.modelSize = 100;
    }

    /**
     * 面番号の表示/非表示を切り替え
     */
    setVisible(visible: boolean): void {
        this._visible = visible;
        this.visible = visible;
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
    ): void {
        this.backendFaceNumbers.clear();

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

        // 既に表示されているスプライトがある場合は、面番号を更新
        if (this.sprites.size > 0) {
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

            // 立方体の場合、法線方向に基づいて正確な面中心を再計算
            if (center && normal) {
                center = this.refineFaceCenterForBox(center, normal, shape);
            }

            // フォールバック：面の中心が取得できない場合は、メッシュ情報から推定
            if (!center) {
                console.log(`Face ${index}: Primary center calculation failed, trying mesh estimation`);
                center = this.estimateFaceCenterFromMesh(face, index, shape);
            }

            // バックエンドから受信した面番号を使用
            const backendNumber = this.backendFaceNumbers.get(index);
            const faceNumber = backendNumber !== undefined ? backendNumber : index + 1; // フォールバック：インデックス+1

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
                const sprite = this.createNumberSprite(faceNumber);
                sprite.position.copy(center);

                // スプライトを面の表面から適切な距離に配置
                if (normal) {
                    const originalPosition = sprite.position.clone();
                    // モデルサイズに基づく動的オフセット（モデルサイズの3%、最小値5）
                    const offset = Math.max(this.modelSize * 0.03, 5);
                    sprite.position.addScaledVector(normal, offset);
                    console.log(
                        `FaceNumberDisplay: Face ${faceNumber} - Original:`,
                        originalPosition,
                        "Final:",
                        sprite.position,
                        "Offset:",
                        offset,
                    );
                }

                this.sprites.set(faceNumber, sprite);
                this.add(sprite);
            } else {
                console.log(`FaceNumberDisplay: ERROR - Could not get center for face ${index}`);
            }
        });

        console.log(`FaceNumberDisplay: Created ${this.sprites.size} sprites using backend face numbers`);
    }

    /**
     * 既存のスプライトの面番号を更新する
     */
    private updateExistingSprites(): void {
        console.log("FaceNumberDisplay: 既存スプライトの面番号を更新中...");

        // 現在のスプライトの位置情報を保存
        const spritePositions = new Map<number, Vector3>();
        const spriteKeys = Array.from(this.sprites.keys());

        spriteKeys.forEach((oldFaceNumber, index) => {
            const sprite = this.sprites.get(oldFaceNumber);
            if (sprite) {
                spritePositions.set(index, sprite.position.clone());
            }
        });

        // 全てのスプライトをクリア
        this.clearNumbers();

        // バックエンドの面番号を使用して新しいスプライトを作成
        spriteKeys.forEach((_, faceIndex) => {
            const position = spritePositions.get(faceIndex);
            const backendFaceNumber = this.backendFaceNumbers.get(faceIndex);

            if (position && backendFaceNumber !== undefined) {
                console.log(
                    `Updating face ${faceIndex}: old number was at position, new number is ${backendFaceNumber}`,
                );

                const sprite = this.createNumberSprite(backendFaceNumber);
                sprite.position.copy(position);

                this.sprites.set(backendFaceNumber, sprite);
                this.add(sprite);
            }
        });

        console.log(`FaceNumberDisplay: Updated ${this.sprites.size} sprites with backend face numbers`);
    }

    /**
     * 面の中心座標を取得（シンプルで確実な計算）
     */
    private getFaceCenter(face: IFace): Vector3 | null {
        // シンプルな面のバウンディングボックス中心計算
        const boundingBoxCenter = this.calculateFaceBoundingBoxCenter(face);
        if (boundingBoxCenter) {
            console.log("Face center from bounding box:", boundingBoxCenter);
            return boundingBoxCenter;
        }

        // フォールバック1: メッシュデータから重心を計算
        const meshCenter = this.calculateFaceCenterFromMesh(face);
        if (meshCenter) {
            console.log("Face center calculated from mesh data:", meshCenter);
            return meshCenter;
        }

        // フォールバック2: normal(0.5, 0.5)を使用
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
     * 立方体の面中心を法線方向に基づいて精密に計算
     */
    private refineFaceCenterForBox(center: Vector3, normal: Vector3, shape: IShape): Vector3 {
        try {
            // 全体の形状のバウンディングボックスを取得
            const shapeMesh = shape.mesh;
            if (!shapeMesh?.faces?.position) {
                console.log("No shape mesh for refinement, using original center");
                return center;
            }

            const positions = shapeMesh.faces.position;
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

            const shapeCenter = new Vector3((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);

            const halfSizeX = (maxX - minX) / 2;
            const halfSizeY = (maxY - minY) / 2;
            const halfSizeZ = (maxZ - minZ) / 2;

            // 法線方向に基づいて正確な面の中心を計算
            let refinedCenter = shapeCenter.clone();

            const normalThreshold = 0.8; // 法線の主成分を判定する閾値

            if (Math.abs(normal.x) > normalThreshold) {
                // X方向の面
                refinedCenter.x = normal.x > 0 ? maxX : minX;
                console.log(
                    `X-direction face: normal.x=${normal.x.toFixed(2)}, center.x=${refinedCenter.x.toFixed(2)}`,
                );
            } else if (Math.abs(normal.y) > normalThreshold) {
                // Y方向の面
                refinedCenter.y = normal.y > 0 ? maxY : minY;
                console.log(
                    `Y-direction face: normal.y=${normal.y.toFixed(2)}, center.y=${refinedCenter.y.toFixed(2)}`,
                );
            } else if (Math.abs(normal.z) > normalThreshold) {
                // Z方向の面
                refinedCenter.z = normal.z > 0 ? maxZ : minZ;
                console.log(
                    `Z-direction face: normal.z=${normal.z.toFixed(2)}, center.z=${refinedCenter.z.toFixed(2)}`,
                );
            }

            console.log(
                `Refined face center: original=${center.x.toFixed(2)}, ${center.y.toFixed(2)}, ${center.z.toFixed(2)} -> refined=${refinedCenter.x.toFixed(2)}, ${refinedCenter.y.toFixed(2)}, ${refinedCenter.z.toFixed(2)}`,
            );
            return refinedCenter;
        } catch (error) {
            console.warn("Failed to refine face center:", error);
            return center;
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
    private calculateModelSize(shape: IShape): number {
        try {
            const mesh = shape.mesh;
            if (!mesh?.faces?.position) {
                console.log("FaceNumberDisplay: No mesh data for size calculation, using default");
                return 100; // デフォルトサイズ
            }

            const positions = mesh.faces.position;
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

            // バウンディングボックスの対角線長を計算
            const sizeX = maxX - minX;
            const sizeY = maxY - minY;
            const sizeZ = maxZ - minZ;
            const diagonalLength = Math.sqrt(sizeX * sizeX + sizeY * sizeY + sizeZ * sizeZ);

            console.log(
                `FaceNumberDisplay: Bounding box size: [${sizeX.toFixed(2)}, ${sizeY.toFixed(2)}, ${sizeZ.toFixed(2)}]`,
            );
            console.log(`FaceNumberDisplay: Diagonal length: ${diagonalLength.toFixed(2)}`);

            return diagonalLength || 100; // 0の場合はデフォルト値
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
    private createNumberSprite(number: number): Sprite {
        const canvas = document.createElement("canvas");
        const size = 256;
        canvas.width = size;
        canvas.height = size;

        const context = canvas.getContext("2d");
        if (!context) {
            throw new Error("Failed to get canvas context");
        }

        // 背景を白色の円で描画
        context.fillStyle = "white";
        context.beginPath();
        context.arc(size / 2, size / 2, size / 2 - 4, 0, Math.PI * 2);
        context.fill();

        // 枠線を描画
        context.strokeStyle = "red";
        context.lineWidth = 8;
        context.stroke();

        // 番号を描画
        context.fillStyle = "red";
        context.font = "bold 120px Arial";
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(number.toString(), size / 2, size / 2);

        // テクスチャとマテリアルを作成
        const texture = new CanvasTexture(canvas);
        const material = new SpriteMaterial({
            map: texture,
            sizeAttenuation: false, // ズームしても面番号のサイズを一定に保つ
            depthTest: true,
            depthWrite: false,
        });

        const sprite = new Sprite(material);
        // 画面上で一定のサイズを保つ固定スケール
        const scale = 0.03; // スクリーン空間での固定サイズ
        sprite.scale.set(scale, scale, 1);
        sprite.name = `FaceNumber_${number}`;
        sprite.renderOrder = 999; // 最前面に表示
        sprite.frustumCulled = false; // カメラに関係なく常に表示

        return sprite;
    }

    /**
     * 指定された位置に面番号を作成
     */
    createFaceNumbersAtPositions(positions: Array<{ x: number; y: number; z: number }>): void {
        // 既存のスプライトをクリア
        this.clearNumbers();

        positions.forEach((pos, index) => {
            const faceNumber = index + 1;
            const sprite = this.createNumberSprite(faceNumber);
            sprite.position.set(pos.x, pos.y, pos.z);

            this.sprites.set(faceNumber, sprite);
            this.add(sprite);
            console.log(`FaceNumberDisplay: Added face number ${faceNumber} at`, pos);
        });

        console.log(`FaceNumberDisplay: Total sprites created: ${this.sprites.size}`);
        console.log(`FaceNumberDisplay: Children count: ${this.children.length}`);
    }

    /**
     * 簡易的に面番号を作成（位置は自動配置）
     */
    createSimpleFaceNumber(faceNumber: number): void {
        const sprite = this.createNumberSprite(faceNumber);

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
            sprite.position.copy(positions[faceNumber - 1]);
        } else {
            // 追加の面の場合はランダム配置
            sprite.position.set(
                (Math.random() - 0.5) * 60,
                (Math.random() - 0.5) * 60,
                (Math.random() - 0.5) * 60,
            );
        }

        this.sprites.set(faceNumber, sprite);
        this.add(sprite);
        console.log(`FaceNumberDisplay: Added simple face number ${faceNumber} at`, sprite.position);
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
    }

    /**
     * クリーンアップ
     */
    dispose(): void {
        this.clearNumbers();
    }
}
