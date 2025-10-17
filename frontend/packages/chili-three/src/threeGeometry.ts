// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    BoundingBox,
    EdgeMeshData,
    FaceMeshData,
    FaceTextureService,
    GeometryNode,
    IShape,
    ISubShape,
    IVisualGeometry,
    Matrix4,
    ShapeMeshRange,
    ShapeNode,
    ShapeType,
    TextureData,
    VisualConfig,
} from "chili-core";
import { MeshUtils } from "chili-geo";
import {
    DoubleSide,
    Material,
    Mesh,
    MeshLambertMaterial,
    TextureLoader,
    RepeatWrapping,
    Vector2,
    Texture,
} from "three";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry";
import { ThreeGeometryFactory } from "./threeGeometryFactory";
import { ThreeHelper } from "./threeHelper";
import { ThreeVisualContext } from "./threeVisualContext";
import { ThreeVisualObject } from "./threeVisualObject";
import { Constants } from "./constants";
import { FaceNumberDisplay } from "./faceNumberDisplay";

export class ThreeGeometry extends ThreeVisualObject implements IVisualGeometry {
    private _faceMaterial: Material | Material[];
    private _edgeMaterial = new LineMaterial({
        linewidth: 1,
        color: VisualConfig.defaultEdgeColor,
        side: DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: -2,
        polygonOffsetUnits: -2,
    });
    private _edges?: LineSegments2;
    private _faces?: Mesh;
    private _faceNumbers?: FaceNumberDisplay;
    private _textureLoader = new TextureLoader();
    private _texturedMaterials: Map<number, Material> = new Map();
    private _faceTextureService: FaceTextureService | null = null;

    constructor(
        readonly geometryNode: GeometryNode,
        readonly context: ThreeVisualContext,
    ) {
        super(geometryNode);
        this._faceMaterial = context.getMaterial(geometryNode.materialId);
        this.generateShape();
        geometryNode.onPropertyChanged(this.handleGeometryPropertyChanged);
    }

    getMainMaterial() {
        return this._faces ? this._faceMaterial : this._edgeMaterial;
    }

    changeFaceMaterial(material: Material | Material[]) {
        if (this._faces) {
            this._faceMaterial = material;
            this._faces.material = material;
        }
    }

    /**
     * FaceTextureServiceを設定
     */
    setFaceTextureService(service: FaceTextureService) {
        this._faceTextureService = service;
    }

    /**
     * 面にテクスチャを適用（Multi-Material対応）
     * @param faceIndex 面のインデックス
     * @param textureData テクスチャデータ
     */
    async applyTextureToFace(faceIndex: number, textureData: TextureData) {
        if (!this._faces || !this._faces.geometry.groups || this._faces.geometry.groups.length === 0) {
            console.warn("ThreeGeometry: No face groups available for texture application");
            return;
        }

        // テクスチャをロード
        const texture = await this.loadTexture(textureData.imageUrl);
        if (!texture) {
            console.error(`Failed to load texture: ${textureData.imageUrl}`);
            return;
        }

        // テクスチャ設定
        texture.wrapS = texture.wrapT = RepeatWrapping;
        if (textureData.repeat) {
            texture.repeat.set(textureData.repeat.x, textureData.repeat.y);
        }
        if (textureData.offset) {
            texture.offset.set(textureData.offset.x, textureData.offset.y);
        }

        // 回転を設定
        if (textureData.rotation !== undefined && textureData.rotation !== 0) {
            const rotationRadians = (textureData.rotation * Math.PI) / 180;
            texture.center.set(0.5, 0.5);
            texture.rotation = rotationRadians;
        }

        // テクスチャ付きマテリアルを作成
        const texturedMaterial = new MeshLambertMaterial({
            map: texture,
            side: DoubleSide,
            transparent: true,
        });

        // マテリアルを保存
        this._texturedMaterials.set(faceIndex, texturedMaterial);

        // Multi-Material配列を更新
        this.updateMultiMaterial();
    }

    /**
     * テクスチャをロード（キャッシュ付き）
     */
    private async loadTexture(url: string): Promise<Texture | null> {
        return new Promise((resolve) => {
            this._textureLoader.load(
                url,
                (texture) => {
                    console.log(`Loaded texture: ${url}`);
                    resolve(texture);
                },
                undefined,
                (error) => {
                    console.error(`Failed to load texture: ${url}`, error);
                    resolve(null);
                },
            );
        });
    }

    /**
     * Multi-Material配列を更新
     */
    private updateMultiMaterial() {
        if (!this._faces || !this._faces.geometry.groups) return;

        const materials: Material[] = [];
        const groups = this._faces.geometry.groups;

        // 各グループに対してマテリアルを割り当て
        groups.forEach((group, index) => {
            const texturedMaterial = this._texturedMaterials.get(index);
            if (texturedMaterial) {
                materials.push(texturedMaterial);
            } else {
                // デフォルトマテリアルを使用
                const defaultMat = Array.isArray(this._faceMaterial)
                    ? this._faceMaterial[index] || this._faceMaterial[0]
                    : this._faceMaterial;
                materials.push(defaultMat);
            }
        });

        // Meshのマテリアルを更新
        this._faces.material = materials;
        console.log(`Updated multi-material with ${materials.length} materials`);
    }

    /**
     * Update texture rotation for a specific face (real-time editing)
     * @param faceIndex Face index
     * @param rotationDegrees Rotation angle in degrees (0-360)
     */
    updateTextureRotation(faceIndex: number, rotationDegrees: number) {
        const material = this._texturedMaterials.get(faceIndex);
        if (!material || !(material instanceof MeshLambertMaterial)) {
            console.warn(`No textured material found for face ${faceIndex}`);
            return;
        }

        const texture = material.map;
        if (!texture) {
            console.warn(`No texture found in material for face ${faceIndex}`);
            return;
        }

        // Convert degrees to radians
        const rotationRadians = (rotationDegrees * Math.PI) / 180;

        // Set rotation center to the middle of the texture
        texture.center.set(0.5, 0.5);

        // Apply rotation
        texture.rotation = rotationRadians;

        // Explicitly update texture matrix (CRITICAL for texture transform changes)
        // Without this, rotation/offset/repeat changes don't take effect
        texture.matrixAutoUpdate = true;
        texture.updateMatrix();

        // Mark texture as needing update
        texture.needsUpdate = true;

        // Mark material as needing update (critical for Multi-Material rendering)
        material.needsUpdate = true;

        // Force multi-material update to ensure changes propagate to mesh
        this.updateMultiMaterial();

        console.log(`Updated texture rotation for face ${faceIndex}: ${rotationDegrees}°`);
    }

    /**
     * Get current texture rotation for a face
     * @param faceIndex Face index
     * @returns Rotation angle in degrees, or null if no texture
     */
    getTextureRotation(faceIndex: number): number | null {
        const material = this._texturedMaterials.get(faceIndex);
        if (!material || !(material instanceof MeshLambertMaterial)) {
            return null;
        }

        const texture = material.map;
        if (!texture) {
            return null;
        }

        // Convert radians to degrees
        const rotationDegrees = (texture.rotation * 180) / Math.PI;
        return rotationDegrees;
    }

    /**
     * 全てのテクスチャをクリア
     */
    clearAllTextures() {
        this._texturedMaterials.clear();
        if (this._faces) {
            this._faces.material = this._faceMaterial;
        }
    }

    box() {
        return this._faces?.geometry.boundingBox ?? this._edges?.geometry.boundingBox;
    }

    override boundingBox(): BoundingBox | undefined {
        const box = this._faces?.geometry.boundingBox ?? this._edges?.geometry.boundingBox;
        if (!box) return undefined;

        return {
            min: ThreeHelper.toXYZ(box.min),
            max: ThreeHelper.toXYZ(box.max),
        };
    }

    private readonly handleGeometryPropertyChanged = (property: keyof GeometryNode) => {
        if (property === "materialId") {
            this.changeFaceMaterial(this.context.getMaterial(this.geometryNode.materialId));
        } else if ((property as keyof ShapeNode) === "shape") {
            this.removeMeshes();
            this.generateShape();
        }
    };

    private generateShape() {
        const mesh = this.geometryNode.mesh;
        if (mesh?.faces?.position.length) this.initFaces(mesh.faces);
        if (mesh?.edges?.position.length) this.initEdges(mesh.edges);
    }

    override dispose() {
        super.dispose();
        this._edges?.material.dispose();
        this._edgeMaterial = null as any;
        this._faceNumbers?.dispose();
        this.geometryNode.removePropertyChanged(this.handleGeometryPropertyChanged);
        this.removeMeshes();
    }

    private removeMeshes() {
        if (this._edges) {
            this.remove(this._edges);
            this._edges.geometry.dispose();
            this._edges = null as any;
        }
        if (this._faces) {
            this.remove(this._faces);
            this._faces.geometry.dispose();
            this._faces = null as any;
        }
        if (this._faceNumbers) {
            this.remove(this._faceNumbers);
            this._faceNumbers = null as any;
        }
    }

    /**
     * 面番号表示オブジェクトを取得（遅延初期化）
     */
    get faceNumberDisplay(): FaceNumberDisplay | undefined {
        return this._faceNumbers;
    }

    /**
     * 面番号表示オブジェクトを初期化（必要に応じて作成）
     */
    ensureFaceNumberDisplay(): FaceNumberDisplay {
        if (!this._faceNumbers) {
            this._faceNumbers = new FaceNumberDisplay();
            console.log("ThreeGeometry: Created FaceNumberDisplay");
            this.add(this._faceNumbers);
        }
        return this._faceNumbers;
    }

    /**
     * 面番号の表示/非表示を切り替え
     */
    setFaceNumbersVisible(visible: boolean): void {
        console.log(`ThreeGeometry.setFaceNumbersVisible(${visible})`);

        if (visible) {
            // 面番号表示を初期化
            const faceNumbers = this.ensureFaceNumberDisplay();

            // ShapeNodeから実際の形状を取得して面番号を生成
            if (this.geometryNode instanceof ShapeNode) {
                const shape = this.geometryNode.shape.value;
                if (shape) {
                    console.log("ThreeGeometry: Generating face numbers from shape");
                    faceNumbers.generateFromShape(shape);
                } else {
                    console.log("ThreeGeometry: No shape found in ShapeNode");
                }
            } else if (this._faces && this._faces.geometry) {
                // ShapeNodeでない場合は、バウンディングボックスベースの簡易配置
                console.log("ThreeGeometry: Using simplified face numbering");

                this._faces.geometry.computeBoundingBox();
                const bbox = this._faces.geometry.boundingBox;

                if (bbox) {
                    const halfSize = {
                        x: (bbox.max.x - bbox.min.x) / 2,
                        y: (bbox.max.y - bbox.min.y) / 2,
                        z: (bbox.max.z - bbox.min.z) / 2,
                    };
                    const center = {
                        x: (bbox.max.x + bbox.min.x) / 2,
                        y: (bbox.max.y + bbox.min.y) / 2,
                        z: (bbox.max.z + bbox.min.z) / 2,
                    };

                    const offset = 20.0;
                    // 実際の面の数を推測（簡単のため最大12面まで対応）
                    const facePositions = [];

                    // 基本的な6面の位置
                    facePositions.push({ x: center.x, y: center.y, z: center.z + halfSize.z + offset });
                    facePositions.push({ x: center.x, y: center.y, z: center.z - halfSize.z - offset });
                    facePositions.push({ x: center.x + halfSize.x + offset, y: center.y, z: center.z });
                    facePositions.push({ x: center.x - halfSize.x - offset, y: center.y, z: center.z });
                    facePositions.push({ x: center.x, y: center.y + halfSize.y + offset, z: center.z });
                    facePositions.push({ x: center.x, y: center.y - halfSize.y - offset, z: center.z });

                    // 追加の面用の位置（角の方向）
                    facePositions.push({
                        x: center.x + halfSize.x + offset,
                        y: center.y + halfSize.y + offset,
                        z: center.z,
                    });
                    facePositions.push({
                        x: center.x - halfSize.x - offset,
                        y: center.y + halfSize.y + offset,
                        z: center.z,
                    });
                    facePositions.push({
                        x: center.x + halfSize.x + offset,
                        y: center.y - halfSize.y - offset,
                        z: center.z,
                    });
                    facePositions.push({
                        x: center.x - halfSize.x - offset,
                        y: center.y - halfSize.y - offset,
                        z: center.z,
                    });
                    facePositions.push({
                        x: center.x,
                        y: center.y + halfSize.y + offset,
                        z: center.z + halfSize.z + offset,
                    });
                    facePositions.push({
                        x: center.x,
                        y: center.y - halfSize.y - offset,
                        z: center.z + halfSize.z + offset,
                    });

                    faceNumbers.createFaceNumbersAtPositions(facePositions);
                }
            } else {
                console.log("ThreeGeometry: No geometry available for face numbering");
            }
        }

        if (this._faceNumbers) {
            this._faceNumbers.setVisible(visible);
            console.log(`ThreeGeometry: Set face numbers visible: ${visible}`);
        }
    }

    private initEdges(data: EdgeMeshData) {
        const buff = ThreeGeometryFactory.createEdgeBufferGeometry(data);
        this._edges = new LineSegments2(buff, this._edgeMaterial);
        this._edges.layers.set(Constants.Layers.Wireframe);
        this.add(this._edges);
    }

    private initFaces(data: FaceMeshData) {
        const buff = ThreeGeometryFactory.createFaceBufferGeometry(data);
        if (data.groups.length > 1) buff.groups = data.groups;
        this._faces = new Mesh(buff, this._faceMaterial);
        this._faces.layers.set(Constants.Layers.Solid);
        this.add(this._faces);
    }

    setFacesMateiralTemperary(material: MeshLambertMaterial) {
        if (this._faces) this._faces.material = material;
    }

    setEdgesMateiralTemperary(material: LineMaterial) {
        if (this._edges) this._edges.material = material;
    }

    removeTemperaryMaterial(): void {
        if (this._edges) this._edges.material = this._edgeMaterial;
        if (this._faces) this._faces.material = this._faceMaterial;
    }

    cloneSubEdge(index: number) {
        const positions = MeshUtils.subEdge(this.geometryNode.mesh.edges!, index);
        if (!positions) return undefined;

        const buff = new LineSegmentsGeometry();
        buff.setPositions(positions);
        buff.applyMatrix4(this.matrixWorld);

        return new LineSegments2(buff, this._edgeMaterial);
    }

    cloneSubFace(index: number) {
        const mesh = MeshUtils.subFace(this.geometryNode.mesh.faces!, index);
        if (!mesh) return undefined;

        const buff = ThreeGeometryFactory.createFaceBufferGeometry(mesh);
        buff.applyMatrix4(this.matrixWorld);

        return new Mesh(buff, this._faceMaterial);
    }

    faces() {
        return this._faces;
    }

    edges() {
        return this._edges;
    }

    override getSubShapeAndIndex(shapeType: "face" | "edge", subVisualIndex: number) {
        let subShape: ISubShape | undefined = undefined;
        let transform: Matrix4 | undefined = undefined;
        let index: number = -1;
        let groups: ShapeMeshRange[] | undefined = undefined;
        if (shapeType === "edge") {
            groups = this.geometryNode.mesh.edges?.range;
            if (groups) {
                index = ThreeHelper.findGroupIndex(groups, subVisualIndex)!;
                subShape = groups[index].shape;
                transform = groups[index].transform;
            }
        } else {
            groups = this.geometryNode.mesh.faces?.range;
            if (groups) {
                index = ThreeHelper.findGroupIndex(groups, subVisualIndex)!;
                subShape = groups[index].shape;
                transform = groups[index].transform;
            }
        }

        let shape: IShape | undefined = subShape;
        if (this.geometryNode instanceof ShapeNode) {
            shape = this.geometryNode.shape.value;
        }
        return { transform, shape, subShape, index, groups: groups ?? [] };
    }

    override subShapeVisual(shapeType: ShapeType): (Mesh | LineSegments2)[] {
        const shapes: (Mesh | LineSegments2 | undefined)[] = [];

        const isWhole =
            shapeType === ShapeType.Shape ||
            ShapeType.hasCompound(shapeType) ||
            ShapeType.hasCompoundSolid(shapeType) ||
            ShapeType.hasSolid(shapeType);

        if (isWhole || ShapeType.hasEdge(shapeType) || ShapeType.hasWire(shapeType)) {
            shapes.push(this.edges());
        }

        if (isWhole || ShapeType.hasFace(shapeType) || ShapeType.hasShell(shapeType)) {
            shapes.push(this.faces());
        }

        return shapes.filter((x) => x !== undefined);
    }

    override wholeVisual(): (Mesh | LineSegments2)[] {
        return [this.edges(), this.faces()].filter((x) => x !== undefined);
    }
}
