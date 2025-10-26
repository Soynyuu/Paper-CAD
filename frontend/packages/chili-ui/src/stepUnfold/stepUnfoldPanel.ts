// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, span, label, select, option } from "chili-controls";
import {
    IApplication,
    IDocument,
    PubSub,
    StepUnfoldService,
    ShapeNode,
    EditableShapeNode,
    VisualNode,
    I18n,
    UnfoldOptions,
    FaceTextureService,
} from "chili-core";
import { config } from "chili-core/src/config/config";
import Editor from "svgedit";
import "svgedit/dist/editor/svgedit.css";
import "./svgedit-override.css"; // Apply our design system overrides
import style from "./stepUnfoldPanel.module.css";
import { SimplePDFExporter, SimplePDFExportOptions } from "./pdfExporterSimple";
import { Dialog } from "../dialog";

export class StepUnfoldPanel extends HTMLElement {
    private static _instance: StepUnfoldPanel | null = null;
    private readonly _service: StepUnfoldService;
    private readonly _svgContainer: HTMLDivElement;
    private readonly _svgWrapper: HTMLDivElement;
    private readonly _showFaceNumbersButton: HTMLButtonElement;
    private _faceNumbersVisible: boolean = false;
    private readonly _layoutModeButton: HTMLButtonElement;
    // 面ハイライト用のUI要素
    private readonly _faceHighlightContainer: HTMLDivElement;
    private readonly _faceNumberInput: HTMLInputElement;
    private readonly _highlightFaceButton: HTMLButtonElement;
    private readonly _clearHighlightsButton: HTMLButtonElement;
    private readonly _highlightedFacesList: HTMLDivElement;
    private readonly _pageSettingsContainer: HTMLDivElement;
    private readonly _pageFormatSelect: HTMLSelectElement;
    private readonly _pageOrientationSelect: HTMLSelectElement;
    private _layoutMode: "canvas" | "paged" = "paged";
    private readonly _pdfExportButton: HTMLButtonElement;
    private readonly _pdfSplitPagesCheckbox: HTMLInputElement;
    private readonly _pdfScaleInput: HTMLInputElement;
    private readonly _pdfSettingsContainer: HTMLDivElement;
    private _secondaryControlsContainer: HTMLDivElement = null as any; // Will be initialized in _render()
    private _svgEditor: Editor | null = null;
    private _svgEditContainer: HTMLDivElement | null = null;
    private readonly _app: IApplication;
    private _scaleSlider: HTMLInputElement;
    private _scaleValueDisplay: HTMLSpanElement;
    private _modelSizeDisplay: HTMLDivElement;
    private _currentScale: number = 1; // Default to 1:1 scale
    private _modelBoundingSize: number = 0; // Model's bounding box max dimension in mm
    private _textureService: FaceTextureService | null = null;
    private _lastStepData: BlobPart | null = null; // Cache last STEP data for PDF export
    private _lastUnfoldOptions: UnfoldOptions | null = null; // Cache last unfold options

    constructor(app: IApplication) {
        super();
        console.log("StepUnfoldPanel constructor called with app:", app);
        this._app = app;
        StepUnfoldPanel._instance = this;

        this._service = new StepUnfoldService(config.stepUnfoldApiUrl);

        this._svgWrapper = div({
            className: style.svgWrapper,
        });

        this._svgContainer = div({
            className: style.svgContainer,
        });

        this._showFaceNumbersButton = button({
            textContent: "🔢 Numbers",
            className: style.faceNumberButton,
        });
        this._faceNumbersVisible = false;

        // Create face highlight UI components
        this._faceNumberInput = input({
            type: "number",
            min: "1",
            placeholder: "面番号",
            className: style.faceNumberInput,
            style: { width: "80px", marginRight: "8px" },
        });

        this._highlightFaceButton = button({
            textContent: "🎯 ハイライト",
            className: style.highlightButton,
            style: { marginRight: "8px" },
        });

        this._clearHighlightsButton = button({
            textContent: "🗑 クリア",
            className: style.clearButton,
        });

        this._highlightedFacesList = div({
            className: style.highlightedFacesList,
            style: { marginTop: "8px", fontSize: "12px" },
        });

        this._faceHighlightContainer = div(
            {
                className: style.faceHighlightContainer,
                style: {
                    padding: "8px",
                    border: "1px solid #ddd",
                    borderRadius: "4px",
                    display: "none", // Hidden by default
                },
            },
            div(
                { style: { display: "flex", alignItems: "center" } },
                label({ textContent: "面選択: ", style: { marginRight: "8px" } }),
                this._faceNumberInput,
                this._highlightFaceButton,
                this._clearHighlightsButton,
            ),
            this._highlightedFacesList,
        );

        // Create layout mode button (initial state: paged mode)
        this._layoutModeButton = button({
            textContent: "📄 " + I18n.translate("stepUnfold.layoutMode.paged"),
            className: `${style.layoutModeButton} ${style.active}`,
        });

        // Create page settings controls
        this._pageFormatSelect = select(
            {
                className: style.pageFormatSelect,
            },
            option({ value: "A4", textContent: I18n.translate("stepUnfold.pageFormat.A4") }),
            option({ value: "A3", textContent: I18n.translate("stepUnfold.pageFormat.A3") }),
            option({ value: "Letter", textContent: I18n.translate("stepUnfold.pageFormat.Letter") }),
        );

        this._pageOrientationSelect = select(
            {
                className: style.pageOrientationSelect,
            },
            option({
                value: "portrait",
                textContent: I18n.translate("stepUnfold.pageOrientation.portrait"),
            }),
            option({
                value: "landscape",
                textContent: I18n.translate("stepUnfold.pageOrientation.landscape"),
            }),
        );

        this._pageSettingsContainer = div(
            {
                className: style.compactPageSettings,
                style: { display: "flex" }, // Visible by default (paged mode)
            },
            this._pageFormatSelect,
            this._pageOrientationSelect,
        );

        // Create scale slider
        this._scaleSlider = input({
            type: "range",
            min: "0",
            max: "7",
            value: "0",
            className: style.scaleSlider,
        });

        this._scaleValueDisplay = span({
            className: style.scaleValue,
            textContent: "1:1",
        });

        this._modelSizeDisplay = div({
            className: style.modelSizeInfo,
        });

        // Create PDF export button and settings
        this._pdfExportButton = button({
            textContent: "📄 PDF Export",
            className: style.pdfExportButton,
            title: "Export to PDF with page splitting options",
        });

        this._pdfSplitPagesCheckbox = input({
            type: "checkbox",
            id: "pdfSplitPages",
            checked: true,
        });

        this._pdfScaleInput = input({
            type: "number",
            min: "0.1",
            max: "10",
            step: "0.1",
            value: "1",
            className: style.pdfScaleInput,
            style: { width: "60px", marginLeft: "8px" },
        });

        this._pdfSettingsContainer = div(
            {
                className: style.pdfSettingsContainer,
                style: {
                    padding: "8px",
                    border: "1px solid #ddd",
                    borderRadius: "4px",
                    marginTop: "8px",
                    display: "none",
                },
            },
            div(
                {
                    style: {
                        padding: "10px",
                        backgroundColor: "#f0f8ff",
                        borderRadius: "4px",
                        marginBottom: "8px",
                    },
                },
                span({
                    textContent:
                        "📄 PDFエクスポートは展開図を選択したページサイズ（A4/A3）に自動的にフィットさせます。\n" +
                        "📌 Pagedモード: バックエンドで複数ページPDFを高精度生成（正しいレイアウト保証）\n" +
                        "📌 Canvasモード: クライアントサイドで表示中のSVGをPDF化",
                    style: { fontSize: "12px", color: "#333", whiteSpace: "pre-line" },
                }),
            ),
            // Temporarily hide complex settings until multi-page export is re-implemented
            /*
            label(
                {
                    style: { display: "flex", alignItems: "center", marginBottom: "8px" },
                },
                this._pdfSplitPagesCheckbox,
                span({ textContent: " Split across multiple A4 pages", style: { marginLeft: "8px" } }),
            ),
            label(
                {
                    style: { display: "flex", alignItems: "center" },
                },
                span({ textContent: "Scale: " }),
                this._pdfScaleInput,
                span({ textContent: " (1.0 = actual size)", style: { marginLeft: "8px", fontSize: "12px" } }),
            ),
            */
        );

        this._svgWrapper.appendChild(this._svgContainer);

        this._render();
        this._checkBackendHealth();

        // ドキュメントの変更を監視
        this._setupDocumentListener();

        // PubSubイベントリスナーを追加
        (PubSub.default as any).sub("stepUnfold.showResult", this._handleUnfoldResult);

        // Add click handler for face numbers button
        this._showFaceNumbersButton.onclick = () => this._toggleFaceNumbers();

        // Add click handler for layout mode button
        this._layoutModeButton.onclick = () => this._toggleLayoutMode();

        // Add PDF export button handler
        this._pdfExportButton.onclick = () => this._handlePDFExport();

        // Add event handlers for face highlight UI
        this._highlightFaceButton.onclick = () => this._highlightSelectedFace();
        this._clearHighlightsButton.onclick = () => this._clearAllHighlights();
        this._faceNumberInput.onkeypress = (e) => {
            if (e.key === "Enter" && !e.isComposing) {
                this._highlightSelectedFace();
            }
        };

        // Add scale slider change handler
        this._scaleSlider.oninput = () => this._updateScaleDisplay();

        // Initialize scale display and calculate initial model size
        this._updateScaleDisplay();
        this._updateModelSizeFromCurrentDocument();

        // FaceTextureServiceのインスタンスを取得または作成
        this._initializeTextureService();

        console.log("StepUnfoldPanel fully initialized, element:", this);
    }

    private _initializeTextureService() {
        // 既存のサービスを検索
        const services = this._app.services as any;
        if (services && Array.isArray(services)) {
            this._textureService = services.find((s: any) => s instanceof FaceTextureService) || null;
        }

        if (!this._textureService) {
            // サービスが存在しない場合は作成して登録
            this._textureService = new FaceTextureService();
            this._textureService.register(this._app);
            this._textureService.start();

            if (services && Array.isArray(services)) {
                services.push(this._textureService);
            }
            console.log("[StepUnfoldPanel] Created FaceTextureService");
        } else {
            console.log("[StepUnfoldPanel] Found existing FaceTextureService");
        }
    }

    private _render() {
        // Create secondary controls container (visible by default in paged mode)
        this._secondaryControlsContainer = div(
            {
                className: style.secondaryControls,
                style: { display: "flex" }, // Visible by default (paged mode)
            },
            this._faceHighlightContainer,
            this._pdfSettingsContainer,
            // Model size info and experimental badge (moved to secondary area)
            div(
                { className: style.infoSection },
                div(
                    { className: style.experimentalBadge },
                    span({ textContent: I18n.translate("stepUnfold.experimental") }),
                    span({
                        className: style.experimentalTooltip,
                        textContent: I18n.translate("stepUnfold.experimentalWarning"),
                    }),
                ),
                this._modelSizeDisplay,
            ),
        );

        this.append(
            div(
                { className: style.root },
                // Horizontal top bar containing all controls
                div(
                    { className: style.topBar },
                    // Left section: Buttons
                    div(
                        { className: style.buttonGroup },
                        this._showFaceNumbersButton,
                        this._layoutModeButton,
                        this._pdfExportButton,
                    ),
                    // Spacer to push right controls to the end
                    div({ style: { flex: "1" } }),
                    // Right section: Page settings and scale controls
                    this._pageSettingsContainer,
                    div(
                        { className: style.compactScaleControls },
                        label(
                            { className: style.compactScaleLabel },
                            span({ textContent: I18n.translate("stepUnfold.scale") + ": " }),
                            this._scaleValueDisplay,
                        ),
                        this._scaleSlider,
                    ),
                ),
                // Secondary controls (face highlight and PDF settings)
                this._secondaryControlsContainer,
                this._svgWrapper,
            ),
        );
    }

    private _highlightSelectedFace() {
        const faceNumber = parseInt(this._faceNumberInput.value, 10);
        if (isNaN(faceNumber) || faceNumber < 1) {
            console.warn("Invalid face number:", this._faceNumberInput.value);
            return;
        }

        console.log(`Highlighting face number: ${faceNumber}`);

        // Get active document and visual
        const activeDocument = this._getActiveDocument();
        if (!activeDocument || !activeDocument.visual) {
            console.warn("No active document or visual");
            return;
        }

        const visual = activeDocument.visual;
        const context = visual.context as any;
        if (!context?._NodeVisualMap) {
            console.warn("No _NodeVisualMap found");
            return;
        }

        // Find geometries with face number display
        context._NodeVisualMap.forEach((visualObject: any) => {
            if (visualObject && "faceNumberDisplay" in visualObject) {
                const faceNumberDisplay = visualObject.faceNumberDisplay;
                if (faceNumberDisplay) {
                    // Toggle highlight on the selected face
                    faceNumberDisplay.toggleHighlight(faceNumber);

                    // Update the highlighted faces list
                    this._updateHighlightedFacesList(faceNumberDisplay);
                }
            }
        });

        // Clear input after highlighting
        this._faceNumberInput.value = "";
    }

    private _clearAllHighlights() {
        console.log("Clearing all face highlights");

        const activeDocument = this._getActiveDocument();
        if (!activeDocument || !activeDocument.visual) {
            return;
        }

        const visual = activeDocument.visual;
        const context = visual.context as any;
        if (!context?._NodeVisualMap) {
            return;
        }

        // Clear highlights on all geometries
        context._NodeVisualMap.forEach((visualObject: any) => {
            if (visualObject && "faceNumberDisplay" in visualObject) {
                const faceNumberDisplay = visualObject.faceNumberDisplay;
                if (faceNumberDisplay) {
                    faceNumberDisplay.clearHighlights();
                }
            }
        });

        // Clear the highlighted faces list display
        this._highlightedFacesList.innerHTML = "";
    }

    private _updateHighlightedFacesList(faceNumberDisplay: any) {
        if (!faceNumberDisplay) return;

        const highlightedFaces = faceNumberDisplay.getHighlightedFaces();

        if (highlightedFaces.length === 0) {
            this._highlightedFacesList.innerHTML = "ハイライトされた面: なし";
        } else {
            const facesList = highlightedFaces.sort((a: number, b: number) => a - b).join(", ");
            this._highlightedFacesList.innerHTML = `ハイライトされた面: ${facesList}`;
        }
    }

    private async _checkBackendHealth() {
        const result = await this._service.checkBackendHealth();
        if (!result.isOk) {
            console.error(`Backend unavailable: ${result.error}`);
        } else {
            const health = result.value;
            if (health.status !== "healthy" || !health.opencascade_available) {
                console.error(`Backend unavailable - OpenCASCADE not available`);
            } else {
                this._updateStatus();
            }
        }
    }

    private async _convertCurrentModel() {
        const activeDocument = this._getActiveDocument();
        if (!activeDocument) {
            console.error("No document available");
            return;
        }

        // 既存のExportコマンドと同じ方法でノードを取得
        const allNodes = this._getAllVisualNodes(activeDocument);
        if (allNodes.length === 0) {
            console.error("No shapes to convert");
            return;
        }

        console.log("Converting to STEP...");

        try {
            console.log(
                "Converting nodes:",
                allNodes.map((n) => ({ name: n.name, type: n.constructor.name })),
            );

            // Calculate model bounding size before export
            this._calculateModelBoundingSize(allNodes);

            // Export current model to STEP format (既存のDataExchangeと同じ方法)
            const stepData = await this._app.dataExchange.export(".step", allNodes);
            if (!stepData || stepData.length === 0) {
                console.error("Failed to export to STEP");
                return;
            }

            // FaceTextureServiceからテクスチャマッピングを取得
            let textureMappings: any[] = [];
            if (this._textureService) {
                textureMappings = this._textureService.getBackendFormat();
                if (textureMappings.length > 0) {
                    console.log("[StepUnfoldPanel] Including texture mappings:", textureMappings);
                }
            }

            // Send STEP data to backend for unfolding with options
            const options: UnfoldOptions = {
                scale: this._currentScale,
                layoutMode: this._layoutMode,
                pageFormat: this._pageFormatSelect.value as "A4" | "A3" | "Letter",
                pageOrientation: this._pageOrientationSelect.value as "portrait" | "landscape",
                textureMappings: textureMappings.length > 0 ? textureMappings : undefined,
            };

            // Cache STEP data and options for later PDF export
            this._lastStepData = stepData[0];
            this._lastUnfoldOptions = options;

            const result = await this._service.unfoldStepFromData(stepData[0], options);

            if (result.isOk) {
                const responseData = result.value as any; // 型安全性を一時的に回避

                // SVGコンテンツを表示（複数のフィールド名に対応）
                const svgContent = responseData.svg_content || responseData.svgContent || "";
                if (svgContent) {
                    this._displaySVG(svgContent);
                } else {
                    console.error("No SVG content found in API response:", responseData);
                }

                // バックエンドから受信した面番号データを適用（複数のフィールド名に対応）
                const faceNumbers = responseData.face_numbers || responseData.faceNumbers;
                if (faceNumbers) {
                    this._applyBackendFaceNumbers(faceNumbers);
                }

                // 警告がある場合、ダイアログを表示
                if (responseData.warnings && responseData.warnings.length > 0) {
                    this._showWarningsDialog(responseData.warnings);
                }

                console.log("Successfully converted model");
            } else {
                console.error(`Error: ${result.error}`);
                PubSub.default.pub("showToast", "toast.converter.error");
            }
        } catch (error) {
            console.error(`Unexpected error: ${error}`);
            PubSub.default.pub("showToast", "toast.converter.error");
        }
    }

    private _getAllVisualNodes(document: IDocument): VisualNode[] {
        const visualNodes: VisualNode[] = [];

        const collectVisualNodes = (node: any) => {
            console.log("Checking node:", node?.constructor?.name, node?.name);

            // より寛容なチェック - ShapeNodeやEditableShapeNodeも含む
            if (
                node &&
                (node instanceof VisualNode ||
                    node instanceof ShapeNode ||
                    node instanceof EditableShapeNode ||
                    node.constructor?.name?.includes("Shape") ||
                    node.shape) // shapeプロパティを持つノード
            ) {
                console.log("Found shape node:", node.name, node.constructor.name);
                visualNodes.push(node);
            }

            if (node && node.children && node.children.length > 0) {
                console.log("Node has children:", node.children.length);
                for (const child of node.children) {
                    collectVisualNodes(child);
                }
            }
        };

        console.log("Starting node collection from root:", document.rootNode?.constructor?.name);
        if (document.rootNode) {
            collectVisualNodes(document.rootNode);
        }

        // 代替方法: documentから直接取得を試行
        if (visualNodes.length === 0 && document.history) {
            console.log("Trying alternative method via document history");
            const allNodes = (document as any).history?.execute?.commands || [];
            console.log("Found commands in history:", allNodes.length);
        }

        console.log("Found visual nodes:", visualNodes.length);
        return visualNodes;
    }

    private _hasShapeNodes(): boolean {
        const activeDocument = this._getActiveDocument();
        if (!activeDocument) return false;
        return this._getAllVisualNodes(activeDocument).length > 0;
    }

    private _getActiveDocument(): IDocument | null {
        // 既存のExportコマンドと同じ方法でアクティブドキュメントを取得
        return this._app.activeView?.document || null;
    }

    private _setupDocumentListener() {
        // ドキュメントの追加/削除を監視
        setInterval(() => {
            this._updateStatus();
            this._updateModelSizeFromCurrentDocument();
        }, 1000); // 1秒ごとに状態をチェック
    }

    private _updateStatus() {
        const activeDoc = this._getActiveDocument();
        const hasShapes = this._hasShapeNodes();

        console.log("StepUnfoldPanel - Update Status:", {
            documentCount: this._app.documents.size,
            activeDoc: !!activeDoc,
            hasShapes,
            shapeCount: activeDoc ? this._getAllVisualNodes(activeDoc).length : 0,
        });

        if (!activeDoc) {
            console.log("No document available");
        } else {
            console.log("Ready - Use ribbon button to unfold shapes");
        }
    }

    private readonly _handleUnfoldResult = (data: any) => {
        console.log("🚀 _handleUnfoldResult called with:", data);

        // Cache STEP data if provided (from ribbon button command)
        if (typeof data === "object") {
            if (data.stepData) {
                console.log("🚀 Caching STEP data from ribbon command");
                this._lastStepData = data.stepData;
            }
            if (data.unfoldOptions) {
                console.log("🚀 Caching unfold options from ribbon command");
                this._lastUnfoldOptions = data.unfoldOptions;
            }
        }

        // SVGコンテンツを表示（後方互換性のため複数のフィールド名に対応）
        let svgContent: string;
        if (typeof data === "string") {
            svgContent = data;
        } else {
            // APIレスポンスのsvg_contentフィールドを使用（新形式）、フォールバックでsvgContent（旧形式）
            svgContent = data.svg_content || data.svgContent || "";
        }

        if (svgContent) {
            this._displaySVG(svgContent);
            console.log("🚀 SVG displayed successfully");
        } else {
            console.error("🚀 No SVG content found in response:", data);
        }

        // バックエンドから受信した面番号データがある場合は3Dビューに適用（複数のフィールド名に対応）
        if (typeof data === "object") {
            const faceNumbers = data.face_numbers || data.faceNumbers;
            console.log("🚀 Face numbers from response:", faceNumbers);
            if (faceNumbers) {
                this._applyBackendFaceNumbers(faceNumbers);
            } else {
                console.log("🚀 No face numbers found in response");
            }

            // 警告がある場合、ダイアログを表示
            if (data.warnings && data.warnings.length > 0) {
                this._showWarningsDialog(data.warnings);
            }
        }

        console.log("Unfold diagram generated");
    };

    /**
     * 警告ダイアログを表示
     */
    private _showWarningsDialog(warnings: Array<{ type: string; message: string; details?: any }>): void {
        console.log("Showing warnings dialog:", warnings);

        // 警告メッセージを整形
        const warningMessages = warnings.map((warning) => {
            let message = warning.message;

            // 詳細情報がある場合、追加情報を表示
            if (warning.details) {
                const details = warning.details;
                if (details.original_size_mm && details.scaled_size_mm) {
                    message += `\n\n詳細:\n`;
                    message += `元のサイズ: ${details.original_size_mm.width} × ${details.original_size_mm.height} mm\n`;
                    message += `調整後のサイズ: ${details.scaled_size_mm.width} × ${details.scaled_size_mm.height} mm\n`;
                    message += `スケール比率: ${details.scale_factor}\n`;
                    message += `用紙: ${details.page_format} (${details.page_orientation})`;
                }
            }

            return message;
        });

        // ダイアログのコンテンツを作成
        const content = div(
            { style: { padding: "10px", maxWidth: "500px" } },
            ...warningMessages.map((msg) =>
                div({ style: { marginBottom: "10px", whiteSpace: "pre-line" } }, msg),
            ),
        );

        // ダイアログを表示（OKボタンのみ）
        Dialog.show("stepUnfold.warning" as any, content, () => {
            console.log("Warning dialog closed");
        });
    }

    /**
     * バックエンドから受信した面番号データを3Dビューに適用
     */
    private _applyBackendFaceNumbers(faceNumbers: Array<{ faceIndex: number; faceNumber: number }>): void {
        console.log("🔢 _applyBackendFaceNumbers called with:", faceNumbers);

        const activeDocument = this._getActiveDocument();
        console.log("🔢 Active document:", !!activeDocument);

        if (activeDocument && activeDocument.visual) {
            const visual = activeDocument.visual as any;
            console.log("🔢 Visual object:", !!visual);

            if (visual.context && visual.context._NodeVisualMap) {
                console.log("🔢 Found _NodeVisualMap, size:", visual.context._NodeVisualMap.size);

                let processedCount = 0;
                visual.context._NodeVisualMap.forEach((visualObject: any, node: any) => {
                    console.log("🔢 Checking visualObject:", {
                        hasObject: !!visualObject,
                        hasShape: !!visualObject?.shape,
                        hasFaceNumberDisplay: !!visualObject?.faceNumberDisplay,
                        objectType: visualObject?.constructor?.name,
                    });

                    // ThreeGeometryインスタンスかチェック
                    if (visualObject && "faceNumberDisplay" in visualObject) {
                        console.log("🔢 Processing geometry with ThreeGeometry interface");
                        processedCount++;

                        // faceNumberDisplayを取得（まだなければnullになる）
                        let faceNumberDisplay = visualObject.faceNumberDisplay;
                        console.log("🔢 Current faceNumberDisplay:", !!faceNumberDisplay);

                        // faceNumberDisplayがまだない場合、強制的に作成
                        if (!faceNumberDisplay && "ensureFaceNumberDisplay" in visualObject) {
                            console.log("🔢 Creating faceNumberDisplay for backend face numbers");
                            // ensureFaceNumberDisplayメソッドがあれば呼び出し、なければsetFaceNumbersVisibleで作成
                            if (typeof visualObject.ensureFaceNumberDisplay === "function") {
                                faceNumberDisplay = (visualObject as any).ensureFaceNumberDisplay();
                            } else if (typeof visualObject.setFaceNumbersVisible === "function") {
                                // setFaceNumbersVisibleでfaceNumberDisplayを作成（visibility=falseで作成のみ）
                                visualObject.setFaceNumbersVisible(true);
                                visualObject.setFaceNumbersVisible(false); // すぐに非表示にしてfaceNumberDisplayだけ残す
                                faceNumberDisplay = visualObject.faceNumberDisplay;
                            }
                        }

                        if (faceNumberDisplay) {
                            console.log("🔢 Processing geometry with faceNumberDisplay");

                            // まず現在の状態をログ
                            console.log(
                                "🔢 Current sprite count:",
                                (faceNumberDisplay as any).sprites?.size || 0,
                            );
                            console.log(
                                "🔢 Current backend face numbers:",
                                (faceNumberDisplay as any).backendFaceNumbers?.size || 0,
                            );

                            // バックエンドの面番号データを設定
                            faceNumberDisplay.setBackendFaceNumbers(faceNumbers);

                            // 面番号表示を再生成（既存のShape情報を使って）
                            if (visualObject.shape) {
                                console.log("🔢 Regenerating face number display with backend data");
                                faceNumberDisplay.generateFromShape(visualObject.shape);

                                // 再生成後の状態もログ
                                console.log(
                                    "🔢 After regeneration - sprite count:",
                                    (faceNumberDisplay as any).sprites?.size || 0,
                                );
                            } else {
                                console.log("🔢 No shape available for regenerating face numbers");
                            }
                        } else {
                            console.log("🔢 Could not create faceNumberDisplay");
                        }
                    } else {
                        console.log("🔢 Skipping visualObject - not a ThreeGeometry");
                    }
                });

                console.log("🔢 Processed", processedCount, "objects with faceNumberDisplay");
            } else {
                console.log("🔢 No _NodeVisualMap found in visual.context");
            }
        } else {
            console.log("🔢 No active document or visual available");
        }
    }

    private async _displaySVG(svgContent: string) {
        // Destroy existing editor if present
        if (this._svgEditContainer) {
            try {
                this._svgEditContainer.remove();
            } catch (e) {
                console.warn("Error removing existing SVG-Edit container:", e);
            }
            this._svgEditContainer = null;
            this._svgEditor = null;
        }

        // Clear container
        this._svgContainer.innerHTML = "";

        // Enable SVG-Edit for editing capability
        const USE_SVGEDIT = true; // Toggle this to enable/disable SVG-Edit

        if (!USE_SVGEDIT) {
            // Simple SVG display without editing capability
            console.log("Displaying SVG without SVG-Edit");
            this._svgContainer.innerHTML = svgContent;

            // Store the SVG element for PDF export
            const svgElement = this._svgContainer.querySelector("svg");
            if (svgElement) {
                // Ensure SVG has proper dimensions
                if (!svgElement.getAttribute("width")) {
                    svgElement.setAttribute("width", "100%");
                }
                if (!svgElement.getAttribute("height")) {
                    svgElement.setAttribute("height", "100%");
                }
                console.log("SVG displayed successfully");
            }
            return;
        }

        // Initialize SVG-Edit
        this._svgEditContainer = document.createElement("div");
        this._svgEditContainer.style.width = "100%";
        this._svgEditContainer.style.height = "100%";
        this._svgEditContainer.style.position = "relative";
        this._svgEditContainer.id = "svg-edit-container-" + Date.now();
        this._svgContainer.appendChild(this._svgEditContainer);

        try {
            console.log("Initializing SVG-Edit editor...");

            // Initialize SVG-Edit editor
            this._svgEditor = new Editor(this._svgEditContainer);

            // Configure SVG-Edit with proper resource paths
            const config: any = {
                // Resource paths - relative to the web root
                imgPath: "/assets/svgedit/images/",
                extPath: "/assets/svgedit/extensions/",
                langPath: "/assets/svgedit/locale/",

                // Editor configuration
                allowInitialUserOverride: false,
                dimensions: [800, 600],
                gridSnapping: true,
                gridColor: "#ddd",
                showRulers: true,
                showGrid: true,
                baseUnit: "px",
                snappingStep: 10,
                initFill: {
                    color: "FF0000",
                    opacity: 1,
                },
                initStroke: {
                    color: "000000",
                    opacity: 1,
                    width: 2,
                },
                initTool: "select",
                wireframe: false,
                no_save_warning: true,

                // Disable some features that might cause issues
                noDefaultExtensions: false,
                extensions: [],

                // Disable SVG sanitization to allow images with data URLs
                sanitize: false, // Allow all SVG content including images
                allowedOrigins: ["*"], // Allow all origins
            };
            this._svgEditor.setConfig(config);

            // Initialize the editor
            console.log("Calling SVG-Edit init()...");
            await this._svgEditor.init();
            console.log("SVG-Edit initialized successfully");

            // Use ready callback to ensure editor is fully loaded
            if (this._svgEditor.ready) {
                this._svgEditor.ready(() => {
                    console.log("SVG-Edit ready callback triggered");

                    // Load the SVG content
                    if (svgContent) {
                        console.log("Loading SVG content into editor...");

                        // Try to disable sanitization at canvas level
                        if (this._svgEditor && this._svgEditor.svgCanvas) {
                            // Try to disable sanitization (use type assertion to bypass type checking)
                            const canvas = this._svgEditor.svgCanvas as any;
                            if (canvas.sanitizeSvg) {
                                // Override sanitizeSvg to be a no-op
                                const originalSanitize = canvas.sanitizeSvg;
                                canvas.sanitizeSvg = function (node: any) {
                                    console.log("Bypassing SVG sanitization for images");
                                    return node;
                                };
                            }

                            if (this._svgEditor.svgCanvas.setSvgString) {
                                const success = this._svgEditor.svgCanvas.setSvgString(svgContent);
                                console.log("setSvgString result:", success);

                                // Force a canvas update after loading
                                if (this._svgEditor.svgCanvas.updateCanvas && this._svgEditContainer) {
                                    const svgElement = this._svgEditContainer.querySelector("svg");
                                    if (svgElement) {
                                        const width = svgElement.getAttribute("width") || "800";
                                        const height = svgElement.getAttribute("height") || "600";
                                        this._svgEditor.svgCanvas.updateCanvas(
                                            parseFloat(width),
                                            parseFloat(height),
                                        );
                                    }
                                }
                            } else if (this._svgEditor.loadFromString) {
                                this._svgEditor.loadFromString(svgContent);
                                console.log("Used loadFromString method");
                            }
                        } else {
                            console.error("SVG canvas not available");
                        }

                        // Setup event listeners for the editor
                        this._setupEditorEvents();
                    }
                });
            } else {
                // Fallback: use setTimeout if ready method is not available
                setTimeout(() => {
                    if (svgContent && this._svgEditor && this._svgEditor.svgCanvas) {
                        console.log("Loading SVG content (fallback)...");
                        if (this._svgEditor.svgCanvas.setSvgString) {
                            const success = this._svgEditor.svgCanvas.setSvgString(svgContent);
                            console.log("setSvgString result:", success);
                        } else if (this._svgEditor.loadFromString) {
                            this._svgEditor.loadFromString(svgContent);
                            console.log("Used loadFromString method");
                        }
                        this._setupEditorEvents();
                    }
                }, 1000);
            }
        } catch (error) {
            console.error("Failed to initialize SVG-Edit:", error);
            if (error instanceof Error) {
                console.error("Error details:", error.stack);
            }
            // Fallback: just display the SVG without editing capabilities
            this._svgContainer.innerHTML = svgContent;
        }
    }

    private _setupEditorEvents() {
        if (!this._svgEditor) return;

        // SVG-Edit may not immediately expose svgCanvas, so we'll try to access it safely
        try {
            // For SVG-Edit, the canvas might be available through different properties
            const canvas = this._svgEditor.svgCanvas || (this._svgEditor as any).canvas;

            if (canvas && canvas.bind) {
                // Listen to selection changes
                canvas.bind("selected", () => {
                    console.log("Selection changed");
                });

                // Listen to content changes
                canvas.bind("changed", () => {
                    console.log("SVG content changed");
                });

                // Additional event bindings for better user experience
                canvas.bind("cleared", () => {
                    console.log("Canvas cleared");
                });

                canvas.bind("zoomed", () => {
                    console.log("Zoom changed");
                });
            } else {
                console.log("SVG-Edit canvas not yet available, deferring event setup");
                // Try again after a delay
                setTimeout(() => this._setupEditorEvents(), 500);
            }
        } catch (error) {
            console.warn("Error setting up editor events:", error);
        }
    }

    private _toggleFaceNumbers() {
        this._faceNumbersVisible = !this._faceNumbersVisible;
        console.log(`Toggling face numbers: ${this._faceNumbersVisible}`);

        // Update button appearance
        if (this._faceNumbersVisible) {
            this._showFaceNumbersButton.classList.add(style.active);
            this._showFaceNumbersButton.textContent = "🔢 3D面番号の非表示✓";
        } else {
            this._showFaceNumbersButton.classList.remove(style.active);
            this._showFaceNumbersButton.textContent = "🔢 3D面番号の表示";
        }

        // Toggle 3D view face numbers
        const activeDocument = this._getActiveDocument();
        if (activeDocument && activeDocument.visual) {
            const visual = activeDocument.visual as any;
            console.log("Visual object:", visual);

            if (visual.context && visual.context._NodeVisualMap) {
                console.log("Found _NodeVisualMap, size:", visual.context._NodeVisualMap.size);
                let geometryCount = 0;

                visual.context._NodeVisualMap.forEach((visualObject: any, node: any) => {
                    console.log("Checking visual object:", visualObject);
                    // Check if it's a ThreeGeometry instance
                    if (visualObject && "setFaceNumbersVisible" in visualObject) {
                        console.log("Found geometry with setFaceNumbersVisible method");
                        visualObject.setFaceNumbersVisible(this._faceNumbersVisible);
                        geometryCount++;
                    }
                });

                console.log(`Updated ${geometryCount} geometries`);
            } else {
                console.log("No _NodeVisualMap found in context");
            }
        } else {
            console.log("No active document or visual");
        }

        // Toggle SVG face numbers
        this._toggleSvgFaceNumbers();
    }

    private _toggleSvgFaceNumbers() {
        if (!this._svgEditor) return;

        try {
            const canvas = this._svgEditor.svgCanvas || (this._svgEditor as any).canvas;
            if (!canvas) return;

            const svgRoot = canvas.getRootElem
                ? canvas.getRootElem()
                : canvas.getContentElem
                  ? canvas.getContentElem()
                  : null;
            if (!svgRoot) return;

            // Toggle face number elements in SVG
            const faceNumbers = svgRoot.querySelectorAll(".face-number");
            faceNumbers.forEach((element: Element) => {
                const svgElement = element as SVGElement;
                if (this._faceNumbersVisible) {
                    svgElement.style.display = "block";
                } else {
                    svgElement.style.display = "none";
                }
            });

            console.log(`Toggled ${faceNumbers.length} SVG face numbers`);
        } catch (error) {
            console.warn("Error toggling SVG face numbers:", error);
        }
    }

    private _getAllGeometryNodes(document: IDocument): any[] {
        const geometries: any[] = [];

        // documentのvisualからgeometriesを取得
        if (document.visual && "geometries" in document.visual) {
            const visualGeometries = (document.visual as any).geometries;
            if (visualGeometries && typeof visualGeometries.forEach === "function") {
                visualGeometries.forEach((geometry: any) => {
                    geometries.push(geometry);
                });
            }
        }

        return geometries;
    }

    private _updateModelSizeFromCurrentDocument() {
        const activeDocument = this._getActiveDocument();
        console.log("[UpdateModelSize] Active document:", !!activeDocument);

        if (activeDocument) {
            const allNodes = this._getAllVisualNodes(activeDocument);
            console.log("[UpdateModelSize] Found nodes:", allNodes.length);

            if (allNodes.length > 0) {
                console.log("[UpdateModelSize] Calculating bounding size for nodes:", allNodes);
                this._calculateModelBoundingSize(allNodes);
            } else {
                console.log("[UpdateModelSize] No visual nodes found");
            }
        } else {
            console.log("[UpdateModelSize] No active document");
        }
    }

    private _updateScaleDisplay() {
        const scaleMap = [1, 10, 50, 100, 150, 200, 300, 500];
        const scaleIndex = parseInt(this._scaleSlider.value);
        this._currentScale = scaleMap[scaleIndex];

        if (this._currentScale === 1) {
            this._scaleValueDisplay.textContent = "1:1";
        } else {
            this._scaleValueDisplay.textContent = `1:${this._currentScale}`;
        }

        // Update model size display - use a default size if not calculated yet
        const estimatedSize = this._modelBoundingSize > 0 ? this._modelBoundingSize : 200; // Default 200mm
        const scaledSize = estimatedSize / this._currentScale;
        const formattedSize =
            scaledSize > 1000 ? `${(scaledSize / 1000).toFixed(2)}m` : `${scaledSize.toFixed(1)}mm`;
        this._modelSizeDisplay.textContent = I18n.translate("stepUnfold.modelSize").replace(
            "{0}",
            formattedSize,
        );
    }

    /**
     * Get current unfold options for external use
     */
    public getCurrentOptions(): UnfoldOptions {
        return {
            scale: this._currentScale,
            layoutMode: this._layoutMode,
            pageFormat: this._pageFormatSelect.value as "A4" | "A3" | "Letter",
            pageOrientation: this._pageOrientationSelect.value as "portrait" | "landscape",
        };
    }

    /**
     * Static method to get current instance
     */
    public static getInstance(): StepUnfoldPanel | null {
        return StepUnfoldPanel._instance;
    }

    private _toggleLayoutMode() {
        this._layoutMode = this._layoutMode === "canvas" ? "paged" : "canvas";

        // Update button text and appearance
        if (this._layoutMode === "paged") {
            this._layoutModeButton.textContent = "📄 " + I18n.translate("stepUnfold.layoutMode.paged");
            this._layoutModeButton.classList.add(style.active);
            this._pageSettingsContainer.style.display = "flex";
            // Show secondary controls to display info when in paged mode
            this._secondaryControlsContainer.style.display = "flex";
        } else {
            this._layoutModeButton.textContent = "📄 " + I18n.translate("stepUnfold.layoutMode.canvas");
            this._layoutModeButton.classList.remove(style.active);
            this._pageSettingsContainer.style.display = "none";
            // Hide secondary controls if nothing else is showing
            if (this._pdfSettingsContainer.style.display === "none") {
                this._secondaryControlsContainer.style.display = "none";
            }
        }

        console.log(`Layout mode changed to: ${this._layoutMode}`);
    }

    private _calculateModelBoundingSize(nodes: VisualNode[]) {
        let minX = Infinity,
            minY = Infinity,
            minZ = Infinity;
        let maxX = -Infinity,
            maxY = -Infinity,
            maxZ = -Infinity;
        let hasValidBounds = false;

        console.log("[CalculateBounds] Starting calculation for", nodes.length, "nodes");

        // Calculate bounding box from mesh data
        nodes.forEach((node, index) => {
            const shape = (node as any).shape;
            console.log(`[CalculateBounds] Node ${index}:`, {
                hasShape: !!shape,
                nodeName: node.name,
                nodeType: node.constructor.name,
            });

            if (shape) {
                // Try to access mesh - it might be a getter that needs to be called
                let mesh;
                try {
                    mesh = shape.mesh;
                    console.log(`[CalculateBounds] Node ${index} mesh:`, {
                        hasMesh: !!mesh,
                        hasFaces: !!mesh?.faces,
                        hasEdges: !!mesh?.edges,
                        facesPositionLength: mesh?.faces?.position?.length || 0,
                        edgesPositionLength: mesh?.edges?.position?.length || 0,
                    });
                } catch (e) {
                    console.log(`[CalculateBounds] Error accessing mesh for node ${index}:`, e);
                }

                if (mesh) {
                    // Get position data from faces
                    if (mesh.faces && mesh.faces.position) {
                        const positions = mesh.faces.position;
                        console.log(`[CalculateBounds] Processing ${positions.length / 3} face vertices`);

                        // Process positions in groups of 3 (x, y, z)
                        for (let i = 0; i < positions.length; i += 3) {
                            const x = positions[i];
                            const y = positions[i + 1];
                            const z = positions[i + 2];

                            minX = Math.min(minX, x);
                            minY = Math.min(minY, y);
                            minZ = Math.min(minZ, z);
                            maxX = Math.max(maxX, x);
                            maxY = Math.max(maxY, y);
                            maxZ = Math.max(maxZ, z);
                            hasValidBounds = true;
                        }
                    }

                    // Also check edges if available
                    if (mesh.edges && mesh.edges.position) {
                        const positions = mesh.edges.position;
                        console.log(`[CalculateBounds] Processing ${positions.length / 3} edge vertices`);

                        for (let i = 0; i < positions.length; i += 3) {
                            const x = positions[i];
                            const y = positions[i + 1];
                            const z = positions[i + 2];

                            minX = Math.min(minX, x);
                            minY = Math.min(minY, y);
                            minZ = Math.min(minZ, z);
                            maxX = Math.max(maxX, x);
                            maxY = Math.max(maxY, y);
                            maxZ = Math.max(maxZ, z);
                            hasValidBounds = true;
                        }
                    }
                }
            }
        });

        if (hasValidBounds) {
            // Calculate the maximum dimension
            const width = maxX - minX;
            const height = maxY - minY;
            const depth = maxZ - minZ;
            this._modelBoundingSize = Math.max(width, height, depth);

            console.log("Calculated bounding box:", {
                width,
                height,
                depth,
                maxDimension: this._modelBoundingSize,
            });
        } else {
            // Default size if no valid bounds found
            this._modelBoundingSize = 200;
            console.log("Using default size: 200mm");
        }

        this._updateScaleDisplay();
    }

    /**
     * Handle PDF export button click
     */
    private async _handlePDFExport() {
        // Check if SVG content exists first
        const hasSvgContent = this._checkSvgContent();

        if (!hasSvgContent) {
            alert(
                "展開図が読み込まれていません。まず3Dモデルを展開してください。\nNo unfold diagram loaded. Please unfold a 3D model first.",
            );
            return;
        }

        // Toggle settings visibility
        if (this._pdfSettingsContainer.style.display === "none") {
            this._pdfSettingsContainer.style.display = "block";
            this._secondaryControlsContainer.style.display = "flex"; // Show container

            // Add export button inside settings
            const existingExportBtn = this._pdfSettingsContainer.querySelector(".pdf-export-action");
            if (!existingExportBtn) {
                const exportBtn = button({
                    textContent: "Export PDF",
                    className: "pdf-export-action",
                    style: {
                        marginTop: "12px",
                        padding: "8px 16px",
                        backgroundColor: "#007bff",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                    },
                });

                exportBtn.onclick = () => this._performPDFExport();
                this._pdfSettingsContainer.appendChild(exportBtn);
            }
        } else {
            this._pdfSettingsContainer.style.display = "none";
            // Hide secondary controls if nothing else is showing
            if (this._layoutMode === "canvas") {
                this._secondaryControlsContainer.style.display = "none";
            }
        }
    }

    /**
     * Check if SVG content exists
     */
    private _checkSvgContent(): boolean {
        // Check if SVG Editor is initialized
        if (!this._svgEditor) {
            console.log("SVG Editor not initialized");
            return false;
        }

        // Check if there's any SVG in the container
        const svgInContainer = this._svgContainer.querySelector("svg");
        if (svgInContainer) {
            console.log("Found SVG in container");
            return true;
        }

        // Check if SVG-Edit has content
        const canvas = this._svgEditor.svgCanvas || (this._svgEditor as any).canvas;
        if (canvas && canvas.getSvgString) {
            const svgString = canvas.getSvgString();
            if (svgString && svgString.length > 100) {
                // Minimal SVG would be longer than 100 chars
                console.log("Found SVG content in canvas");
                return true;
            }
        }

        console.log("No SVG content found");
        return false;
    }

    /**
     * Perform the actual PDF export
     */
    private async _performPDFExport() {
        // Check layout mode and route to appropriate export method
        if (this._layoutMode === "paged") {
            // Use backend PDF generation for multi-page layouts with correct scaling
            await this._performBackendPDFExport();
        } else {
            // Use client-side PDF generation for single-page canvas mode
            await this._performClientPDFExport();
        }
    }

    /**
     * Perform backend PDF export (for paged mode)
     */
    private async _performBackendPDFExport() {
        // Check if we have cached STEP data from previous unfold operation
        if (!this._lastStepData) {
            alert(
                "まず展開図を生成してください。リボンの「展開図」ボタンをクリックしてください。\n" +
                    "Please generate the unfold diagram first by clicking the 'Unfold' button in the ribbon.",
            );
            return;
        }

        // Show loading indicator
        const originalText = this._pdfExportButton.textContent;
        this._pdfExportButton.textContent = "📄 生成中... (Backend)";
        this._pdfExportButton.disabled = true;

        try {
            console.log("[BackendPDF] Using cached STEP data for PDF generation...");

            // Use cached unfold options or current settings
            const options: UnfoldOptions = this._lastUnfoldOptions || {
                scale: this._currentScale,
                layoutMode: this._layoutMode,
                pageFormat: this._pageFormatSelect.value as "A4" | "A3" | "Letter",
                pageOrientation: this._pageOrientationSelect.value as "portrait" | "landscape",
            };

            // Update with current page settings (user may have changed them)
            options.pageFormat = this._pageFormatSelect.value as "A4" | "A3" | "Letter";
            options.pageOrientation = this._pageOrientationSelect.value as "portrait" | "landscape";

            console.log("[BackendPDF] Sending to backend with options:", options);

            // Call backend PDF API with cached STEP data
            const result = await this._service.unfoldStepToPDF(this._lastStepData, options);

            if (result.isOk) {
                const pdfBlob = result.value;

                // Download PDF
                const timestamp = new Date().toISOString().replace(/:/g, "-").slice(0, 19);
                const filename = `paper-cad-unfold-${timestamp}.pdf`;

                const url = URL.createObjectURL(pdfBlob);
                const a = document.createElement("a");
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                console.log("[BackendPDF] PDF downloaded successfully:", filename);

                // Show success message
                this._pdfExportButton.textContent = "✓ 完了!";
                setTimeout(() => {
                    this._pdfExportButton.textContent = originalText;
                }, 2000);
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error("[BackendPDF] Export failed:", error);
            const errorMessage = error instanceof Error ? error.message : "Unknown error";
            alert(
                `バックエンドPDF生成に失敗しました:\n${errorMessage}\n\nBackend PDF generation failed:\n${errorMessage}`,
            );
            this._pdfExportButton.textContent = originalText;
        } finally {
            this._pdfExportButton.disabled = false;
        }
    }

    /**
     * Perform client-side PDF export (for canvas mode)
     */
    private async _performClientPDFExport() {
        if (!this._svgEditor) {
            console.error("SVG Editor not initialized");
            return;
        }

        try {
            // Try multiple methods to get the SVG element
            let svgElement: SVGElement | null = null;

            // Method 1: Try through SVG canvas
            const canvas = this._svgEditor.svgCanvas || (this._svgEditor as any).canvas;
            if (canvas) {
                console.log("Canvas object found:", canvas);

                // Try getRootElem
                if (canvas.getRootElem && typeof canvas.getRootElem === "function") {
                    svgElement = canvas.getRootElem();
                    console.log("Got SVG from getRootElem:", !!svgElement);
                }

                // Try getContentElem if getRootElem didn't work
                if (!svgElement && canvas.getContentElem && typeof canvas.getContentElem === "function") {
                    svgElement = canvas.getContentElem();
                    console.log("Got SVG from getContentElem:", !!svgElement);
                }

                // Try getSvgContent (might not be in type definitions)
                const canvasAny = canvas as any;
                if (
                    !svgElement &&
                    canvasAny.getSvgContent &&
                    typeof canvasAny.getSvgContent === "function"
                ) {
                    const svgContent = canvasAny.getSvgContent();
                    console.log("Got SVG content string, length:", svgContent?.length);
                    if (svgContent) {
                        // Create a temporary div to parse the SVG string
                        const tempDiv = document.createElement("div");
                        tempDiv.innerHTML = svgContent;
                        svgElement = tempDiv.querySelector("svg") as SVGElement;
                        console.log("Parsed SVG from content string:", !!svgElement);
                    }
                }
            }

            // Method 2: Try direct DOM query in the SVG-Edit container
            if (!svgElement && this._svgEditContainer) {
                console.log("Searching for SVG in edit container");

                // Look for SVG in the container or its iframe
                svgElement = this._svgEditContainer.querySelector("svg") as SVGElement;

                if (!svgElement) {
                    // Check if there's an iframe (SVG-Edit might render in iframe)
                    const iframe = this._svgEditContainer.querySelector("iframe") as HTMLIFrameElement;
                    if (iframe && iframe.contentDocument) {
                        svgElement = iframe.contentDocument.querySelector("svg") as SVGElement;
                        console.log("Found SVG in iframe:", !!svgElement);
                    }
                }

                // Also check in the svgContainer
                if (!svgElement) {
                    svgElement = this._svgContainer.querySelector("svg") as SVGElement;
                    console.log("Found SVG in svgContainer:", !!svgElement);
                }
            }

            // Method 3: Get SVG string and create element
            if (!svgElement && canvas && canvas.getSvgString) {
                const svgString = canvas.getSvgString();
                console.log("Got SVG string, length:", svgString?.length);
                if (svgString) {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(svgString, "image/svg+xml");
                    svgElement = doc.documentElement as unknown as SVGElement;
                    console.log("Parsed SVG from string:", !!svgElement);
                }
            }

            if (!svgElement) {
                console.error("SVG element not found after trying all methods");
                alert("Unable to find SVG content. Please make sure the unfold diagram is loaded.");
                return;
            }

            // Get export options from UI
            const options: SimplePDFExportOptions = {
                pageFormat: this._pageFormatSelect.value as "A4" | "A3" | "Letter",
                orientation: this._pageOrientationSelect.value as "portrait" | "landscape",
                margin: 10, // 10mm margin
            };

            console.log("Exporting PDF with SimplePDFExporter, options:", options);

            // Show loading indicator
            const originalText = this._pdfExportButton.textContent;
            this._pdfExportButton.textContent = "Exporting...";
            this._pdfExportButton.disabled = true;

            try {
                await SimplePDFExporter.exportToPDF(svgElement, options);
                console.log("PDF exported successfully");

                // Show success message temporarily
                this._pdfExportButton.textContent = "✓ Exported!";
                setTimeout(() => {
                    this._pdfExportButton.textContent = originalText;
                }, 2000);
            } catch (error) {
                console.error("PDF Export failed:", error);
                const errorMessage = error instanceof Error ? error.message : "Unknown error";
                alert(`PDF export failed: ${errorMessage}`);
                this._pdfExportButton.textContent = originalText;
            } finally {
                this._pdfExportButton.disabled = false;
            }
        } catch (error) {
            console.error("Failed to export PDF:", error);
            alert("Failed to export PDF. Please check the console for details.");
        }
    }
}

customElements.define("chili-step-unfold-panel", StepUnfoldPanel);
