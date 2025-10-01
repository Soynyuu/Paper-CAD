// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { IApplication } from "../application";
import { config } from "../config/config";
import { Result } from "../foundation";
import { IService } from "../service";

export interface UnfoldOptions {
    scale?: number;
    layoutMode?: "canvas" | "paged";
    pageFormat?: "A4" | "A3" | "Letter";
    pageOrientation?: "portrait" | "landscape";
    returnFaceNumbers?: boolean;
    textureMappings?: Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
        imageData?: string; // Base64エンコードされた画像データ（data:image/png;base64,...形式）
    }>;
}

export interface UnfoldResponse {
    svg_content: string;
    svgContent?: string; // 後方互換性のため
    face_numbers?: Array<{ faceIndex: number; faceNumber: number }>;
    faceNumbers?: Array<{ faceIndex: number; faceNumber: number }>; // 後方互換性のため
    textureMappings?: Array<{
        faceNumber: number;
        patternId: string;
        tileCount: number;
    }>;
    stats?: any;
}

export interface IStepUnfoldService extends IService {
    unfoldStep(stepFile: File, options?: UnfoldOptions): Promise<Result<UnfoldResponse>>;
    unfoldStepFromData(stepData: BlobPart, options?: UnfoldOptions): Promise<Result<UnfoldResponse>>;
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
            formData.append("scale_factor", (options.scale || 1).toString());
            formData.append("layout_mode", options.layoutMode || "canvas");
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");

            // テクスチャマッピングを追加
            if (options.textureMappings && options.textureMappings.length > 0) {
                formData.append("texture_mappings", JSON.stringify(options.textureMappings));
                console.log("[StepUnfoldService] Sending texture mappings:", options.textureMappings);
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
            formData.append("scale_factor", (options.scale || 1).toString());
            formData.append("layout_mode", options.layoutMode || "canvas");
            formData.append("page_format", options.pageFormat || "A4");
            formData.append("page_orientation", options.pageOrientation || "portrait");

            // テクスチャマッピングを追加
            if (options.textureMappings && options.textureMappings.length > 0) {
                formData.append("texture_mappings", JSON.stringify(options.textureMappings));
                console.log("[StepUnfoldService] Sending texture mappings:", options.textureMappings);
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

    private isValidStepFile(file: File): boolean {
        const validExtensions = [".step", ".stp"];
        const fileName = file.name.toLowerCase();
        return validExtensions.some((ext) => fileName.endsWith(ext));
    }
}
