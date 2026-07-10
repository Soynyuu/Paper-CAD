// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { IApplication } from "../application";
import { config } from "../config/config";
import { Result } from "../foundation";
import { IService } from "../service";
import { ShapeNode, VisualNode } from "../model";
import { IFace, ShapeType } from "../shape";

export interface SourceFaceDescriptor {
    nodeIndex: number;
    faceIndex: number;
    faceNumber: number;
    centroid: [number, number, number];
    normal: [number, number, number] | null;
    area: number;
    bounds: { min: [number, number, number]; max: [number, number, number] };
    meshPositions: number[];
    meshIndices: number[];
}

export function buildSourceFaceDescriptors(nodes: VisualNode[]): SourceFaceDescriptor[] {
    const descriptors: SourceFaceDescriptor[] = [];
    let faceNumber = 1;

    nodes
        .filter((node): node is ShapeNode => node instanceof ShapeNode)
        .forEach((node, nodeIndex) => {
            if (!node.shape.isOk) return;
            const transformedShape = node.shape.value.transformedMul(node.worldTransform());
            try {
                transformedShape.findSubShapes(ShapeType.Face).forEach((shape, faceIndex) => {
                    const face = shape as IFace;
                    const faceMesh = face.mesh?.faces;
                    const positions = faceMesh?.position;
                    const assignedFaceNumber = faceNumber++;

                    let minX = 0;
                    let minY = 0;
                    let minZ = 0;
                    let maxX = 0;
                    let maxY = 0;
                    let maxZ = 0;
                    if (positions && positions.length >= 3) {
                        minX = maxX = positions[0];
                        minY = maxY = positions[1];
                        minZ = maxZ = positions[2];
                        for (let index = 3; index < positions.length; index += 3) {
                            minX = Math.min(minX, positions[index]);
                            minY = Math.min(minY, positions[index + 1]);
                            minZ = Math.min(minZ, positions[index + 2]);
                            maxX = Math.max(maxX, positions[index]);
                            maxY = Math.max(maxY, positions[index + 1]);
                            maxZ = Math.max(maxZ, positions[index + 2]);
                        }
                    }

                    let normal: [number, number, number] | null = null;
                    try {
                        const [point, value] = face.normal(0.5, 0.5);
                        if (!positions?.length) {
                            minX = maxX = point.x;
                            minY = maxY = point.y;
                            minZ = maxZ = point.z;
                        }
                        const length = Math.hypot(value.x, value.y, value.z);
                        if (length > 1e-12) normal = [value.x / length, value.y / length, value.z / length];
                    } catch {
                        // Area and centroid are sufficient for non-planar faces without a stable normal.
                    }

                    descriptors.push({
                        nodeIndex,
                        faceIndex,
                        faceNumber: assignedFaceNumber,
                        centroid: [(minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2],
                        normal,
                        area: face.area(),
                        bounds: {
                            min: [minX, minY, minZ],
                            max: [maxX, maxY, maxZ],
                        },
                        meshPositions: positions ? Array.from(positions) : [],
                        meshIndices: faceMesh?.index ? Array.from(faceMesh.index) : [],
                    });
                });
            } finally {
                transformedShape.dispose();
            }
        });

    return descriptors;
}

export interface UnfoldOptions {
    scaleMode?: "fixed" | "fitPage";
    scale?: number;
    units?: "mm" | "cm" | "m";
    layoutMode?: "canvas" | "paged";
    pageFormat?: "A4" | "A3" | "Letter";
    pageOrientation?: "portrait" | "landscape";
    mergeMode?: "improved" | "legacy";
    curveMode?: "smooth" | "faceted";
    returnFaceNumbers?: boolean;
    mirrorHorizontal?: boolean; // 左右反転モード
    sourceFaceDescriptors?: SourceFaceDescriptor[];
    textureMappings?: Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
        rotation?: number; // Rotation angle in degrees (0-360)
        imageData?: string; // Base64エンコードされた画像データ（data:image/png;base64,...形式）
    }>;
}

export interface UnfoldResponse {
    svg_content: string;
    svgContent?: string; // 後方互換性のため
    face_numbers?: Array<{ faceIndex: number; faceNumber: number; nodeIndex?: number }>;
    faceNumbers?: Array<{ faceIndex: number; faceNumber: number; nodeIndex?: number }>; // 後方互換性のため
    textureMappings?: Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
        rotation?: number; // Rotation angle in degrees (0-360)
    }>;
    stats?: any;
    warnings?: Array<{
        type: string;
        message: string;
        details?: any;
    }>;
}

export interface IStepUnfoldService extends IService {
    unfoldStep(stepFile: File, options?: UnfoldOptions): Promise<Result<UnfoldResponse>>;
    unfoldStepFromData(stepData: BlobPart, options?: UnfoldOptions): Promise<Result<UnfoldResponse>>;
    unfoldStepToPDF(stepData: BlobPart, options?: UnfoldOptions): Promise<Result<Blob>>;
    convertSvgPagesToPDF(
        svgPages: string[],
        options?: Pick<UnfoldOptions, "pageFormat" | "pageOrientation">,
    ): Promise<Result<Blob>>;
    checkBackendHealth(): Promise<Result<HealthResponse>>;
}

export interface HealthResponse {
    status: string;
    version: string;
    opencascade_available: boolean;
    supported_formats: string[];
}

export class StepUnfoldService implements IStepUnfoldService {
    private readonly baseUrl: string;

    constructor(baseUrl: string = "http://localhost:8001/api") {
        this.baseUrl = baseUrl;
    }

    register(_app: IApplication): void {
        // サービス登録時の処理
    }

    start(): void {
        // サービス開始時の処理
    }

    stop(): void {
        // サービス停止時の処理
    }

    async unfoldStep(stepFile: File, options: UnfoldOptions = {}): Promise<Result<UnfoldResponse>> {
        try {
            // ファイル拡張子チェック
            if (!this.isValidStepFile(stepFile)) {
                return Result.err("Invalid STEP file. Please select a .step or .stp file.");
            }

            const formData = new FormData();
            formData.append("file", stepFile);
            formData.append("return_face_numbers", "true");
            formData.append("output_format", "json");
            formData.append("scale_factor", (options.scale || 150).toString());
            formData.append("scale_mode", this.toBackendScaleMode(options.scaleMode));
            formData.append("units", options.units || "mm");
            formData.append("layout_mode", options.layoutMode || "paged");
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");
            formData.append("merge_mode", options.mergeMode || "improved");
            formData.append("curve_mode", options.curveMode || "smooth");

            // テクスチャマッピングを追加
            if (options.textureMappings && options.textureMappings.length > 0) {
                formData.append("texture_mappings", JSON.stringify(options.textureMappings));
                console.log("[StepUnfoldService] Sending texture mappings:", options.textureMappings);
            }
            if (options.sourceFaceDescriptors?.length) {
                formData.append("source_face_descriptors", JSON.stringify(options.sourceFaceDescriptors));
            }

            const response = await fetch(`${this.baseUrl}/step/unfold`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 400) {
                    errorMessage =
                        "STEPファイル（.step/.stp）のみ対応です。または、ファイルの読み込みに失敗しました。";
                } else if (response.status === 503) {
                    errorMessage = "OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const responseData: UnfoldResponse = await response.json();
            return Result.ok(responseData);
        } catch (error) {
            return Result.err(error instanceof Error ? error.message : "Unknown error");
        }
    }

    async unfoldStepFromData(
        stepData: BlobPart,
        options: UnfoldOptions = {},
    ): Promise<Result<UnfoldResponse>> {
        try {
            const formData = new FormData();
            const stepBlob = new Blob([stepData], { type: "application/octet-stream" });
            formData.append("file", stepBlob, "model.step");
            formData.append("return_face_numbers", "true");
            formData.append("output_format", "json");
            formData.append("scale_factor", (options.scale || 150).toString());
            formData.append("scale_mode", this.toBackendScaleMode(options.scaleMode));
            formData.append("units", options.units || "mm");
            formData.append("layout_mode", options.layoutMode || "paged");
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");
            formData.append("merge_mode", options.mergeMode || "improved");
            formData.append("curve_mode", options.curveMode || "smooth");

            // テクスチャマッピングを追加
            if (options.textureMappings && options.textureMappings.length > 0) {
                formData.append("texture_mappings", JSON.stringify(options.textureMappings));
                console.log("[StepUnfoldService] Sending texture mappings:", options.textureMappings);
            }
            if (options.sourceFaceDescriptors?.length) {
                formData.append("source_face_descriptors", JSON.stringify(options.sourceFaceDescriptors));
            }

            const response = await fetch(`${this.baseUrl}/step/unfold`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 400) {
                    errorMessage = "STEPデータの処理に失敗しました。";
                } else if (response.status === 503) {
                    errorMessage = "OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            const responseData: UnfoldResponse = await response.json();
            return Result.ok(responseData);
        } catch (error) {
            return Result.err(error instanceof Error ? error.message : "Unknown error");
        }
    }

    async checkBackendHealth(): Promise<Result<HealthResponse>> {
        try {
            const response = await fetch(`${this.baseUrl}/health`, {
                method: "GET",
                headers: {
                    Accept: "application/json",
                },
            });

            if (!response.ok) {
                return Result.err(`Backend health check failed: ${response.status} ${response.statusText}`);
            }

            const healthData = await response.json();
            return Result.ok(healthData);
        } catch (error) {
            return Result.err(
                `Backend connection failed: ${error instanceof Error ? error.message : "Unknown error"}`,
            );
        }
    }

    async unfoldStepToPDF(stepData: BlobPart, options: UnfoldOptions = {}): Promise<Result<Blob>> {
        try {
            const formData = new FormData();
            const stepBlob = new Blob([stepData], { type: "application/octet-stream" });
            formData.append("file", stepBlob, "model.step");
            formData.append("scale_factor", (options.scale || 150).toString());
            formData.append("scale_mode", this.toBackendScaleMode(options.scaleMode));
            formData.append("units", options.units || "mm");
            formData.append("layout_mode", options.layoutMode || "paged");
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");
            formData.append("merge_mode", options.mergeMode || "improved");
            formData.append("curve_mode", options.curveMode || "smooth");
            formData.append("mirror_horizontal", (options.mirrorHorizontal || false).toString());

            // テクスチャマッピングを追加
            if (options.textureMappings && options.textureMappings.length > 0) {
                formData.append("texture_mappings", JSON.stringify(options.textureMappings));
                console.log(
                    "[StepUnfoldService] Sending texture mappings to PDF endpoint:",
                    options.textureMappings,
                );
            }
            if (options.sourceFaceDescriptors?.length) {
                formData.append("source_face_descriptors", JSON.stringify(options.sourceFaceDescriptors));
            }

            const response = await fetch(`${this.baseUrl}/step/unfold-pdf`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let errorMessage: string;
                if (response.status === 400) {
                    errorMessage = "STEPデータの処理に失敗しました。";
                } else if (response.status === 503) {
                    errorMessage = "OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。";
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                return Result.err(errorMessage);
            }

            // Get PDF as Blob
            const pdfBlob = await response.blob();
            return Result.ok(pdfBlob);
        } catch (error) {
            return Result.err(error instanceof Error ? error.message : "Unknown error");
        }
    }

    async convertSvgPagesToPDF(
        svgPages: string[],
        options: Pick<UnfoldOptions, "pageFormat" | "pageOrientation"> = {},
    ): Promise<Result<Blob>> {
        try {
            if (svgPages.length === 0) {
                return Result.err("No SVG pages to export.");
            }

            const formData = new FormData();
            svgPages.forEach((svgPage, index) => {
                const svgBlob = new Blob([svgPage], { type: "image/svg+xml" });
                formData.append("files", svgBlob, `page_${String(index + 1).padStart(3, "0")}.svg`);
            });
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");

            const response = await fetch(`${this.baseUrl}/svg/to-pdf`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                return Result.err(errorMessage);
            }

            return Result.ok(await response.blob());
        } catch (error) {
            return Result.err(error instanceof Error ? error.message : "Unknown error");
        }
    }

    private toBackendScaleMode(scaleMode?: UnfoldOptions["scaleMode"]): string {
        return scaleMode === "fitPage" ? "fit_page" : "fixed";
    }

    private isValidStepFile(file: File): boolean {
        const validExtensions = [".step", ".stp"];
        const fileName = file.name.toLowerCase();
        return validExtensions.some((ext) => fileName.endsWith(ext));
    }
}
