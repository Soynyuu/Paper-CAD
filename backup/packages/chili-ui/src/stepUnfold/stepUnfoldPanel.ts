// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, span } from "chili-controls";
import {
    IApplication,
    IDocument,
    PubSub,
    StepUnfoldService,
    ShapeNode,
    EditableShapeNode,
    VisualNode,
} from "chili-core";
import { Editor } from "simple-svg-edit/features/editor";
import "simple-svg-edit/features/default-helper";
import "simple-svg-edit/features/text";
import "simple-svg-edit/features/default-text-helper";
import "simple-svg-edit/features/text-align";
import "simple-svg-edit/features/align";
import style from "./stepUnfoldPanel.module.css";

export class StepUnfoldPanel extends HTMLElement {
    private readonly _service: StepUnfoldService;
    private readonly _svgContainer: HTMLDivElement;
    private readonly _svgWrapper: HTMLDivElement;
    private readonly _convertButton: HTMLButtonElement;
    private readonly _statusText: HTMLSpanElement;
    private readonly _showFaceNumbersButton: HTMLButtonElement;
    private readonly _undoButton: HTMLButtonElement;
    private readonly _redoButton: HTMLButtonElement;
    private readonly _deleteButton: HTMLButtonElement;
    private readonly _alignLeftButton: HTMLButtonElement;
    private readonly _alignCenterButton: HTMLButtonElement;
    private readonly _alignRightButton: HTMLButtonElement;
    private _faceNumbersVisible: boolean = false;
    private _svgEditor: Editor | null = null;
    private readonly _app: IApplication;

    constructor(app: IApplication) {
        super();
        console.log("StepUnfoldPanel constructor called with app:", app);
        this._app = app;
        this._service = new StepUnfoldService();

        this._convertButton = button({
            textContent: "Use Ribbon Button",
            onclick: () => {
                alert("Please use the '展開図' button in the ribbon (Import/Export group) instead.");
            },
        });

        this._statusText = span({
            textContent: this._getActiveDocument() ? "Ready to convert" : "No document available",
            className: style.status,
        });

        this._svgWrapper = div({
            className: style.svgWrapper,
        });

        this._svgContainer = div({
            className: style.svgContainer,
        });

        this._showFaceNumbersButton = button({
            textContent: "🔢 Numbers",
            onclick: () => this._toggleFaceNumbers(),
        });
        this._faceNumbersVisible = false;

        this._undoButton = button({
            textContent: "↶ Undo",
            onclick: () => this._handleUndo(),
            disabled: true,
        });

        this._redoButton = button({
            textContent: "↷ Redo",
            onclick: () => this._handleRedo(),
            disabled: true,
        });

        this._deleteButton = button({
            textContent: "🗑 Delete",
            onclick: () => this._handleDelete(),
            disabled: true,
        });

        this._alignLeftButton = button({
            textContent: "◀ Left",
            onclick: () => this._handleAlign(0, null),
            disabled: true,
        });

        this._alignCenterButton = button({
            textContent: "■ Center",
            onclick: () => this._handleAlign(0.5, 0.5),
            disabled: true,
        });

        this._alignRightButton = button({
            textContent: "▶ Right",
            onclick: () => this._handleAlign(1, null),
            disabled: true,
        });

        this._svgWrapper.appendChild(this._svgContainer);

        this._render();
        this._checkBackendHealth();

        // ドキュメントの変更を監視
        this._setupDocumentListener();

        // PubSubイベントリスナーを追加
        (PubSub.default as any).sub("stepUnfold.showResult", this._handleUnfoldResult);

        console.log("StepUnfoldPanel fully initialized, element:", this);
    }

    private _render() {
        this.append(
            div(
                { className: style.root },
                div({ className: style.header }, this._convertButton, this._statusText),
                div(
                    { className: style.controls },
                    this._undoButton,
                    this._redoButton,
                    this._deleteButton,
                    div({ className: style.separator }),
                    this._alignLeftButton,
                    this._alignCenterButton,
                    this._alignRightButton,
                    div({ className: style.separator }),
                    this._showFaceNumbersButton,
                ),
                this._svgWrapper,
            ),
        );
    }

    private async _checkBackendHealth() {
        const result = await this._service.checkBackendHealth();
        if (!result.isOk) {
            this._statusText.textContent = `Backend unavailable: ${result.error}`;
            this._statusText.className = `${style.status} ${style.error}`;
            this._convertButton.disabled = true;
        } else {
            const health = result.value;
            if (health.status !== "healthy" || !health.opencascade_available) {
                this._statusText.textContent = `Backend unavailable - OpenCASCADE not available`;
                this._statusText.className = `${style.status} ${style.error}`;
                this._convertButton.disabled = true;
            } else {
                this._updateStatus();
            }
        }
    }

    private async _convertCurrentModel() {
        const activeDocument = this._getActiveDocument();
        if (!activeDocument) {
            this._statusText.textContent = "No document available";
            this._statusText.className = `${style.status} ${style.error}`;
            return;
        }

        // 既存のExportコマンドと同じ方法でノードを取得
        const allNodes = this._getAllVisualNodes(activeDocument);
        if (allNodes.length === 0) {
            this._statusText.textContent = "No shapes to convert";
            this._statusText.className = `${style.status} ${style.error}`;
            return;
        }

        this._statusText.textContent = "Converting to STEP...";
        this._statusText.className = `${style.status} ${style.processing}`;
        this._convertButton.disabled = true;

        try {
            console.log(
                "Converting nodes:",
                allNodes.map((n) => ({ name: n.name, type: n.constructor.name })),
            );

            // Export current model to STEP format (既存のDataExchangeと同じ方法)
            const stepData = await this._app.dataExchange.export(".step", allNodes);
            if (!stepData || stepData.length === 0) {
                this._statusText.textContent = "Failed to export to STEP";
                this._statusText.className = `${style.status} ${style.error}`;
                return;
            }

            // Send STEP data to backend for unfolding
            const result = await this._service.unfoldStepFromData(stepData[0]);

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

                this._statusText.textContent = `Successfully converted model`;
                this._statusText.className = `${style.status} ${style.success}`;
            } else {
                this._statusText.textContent = `Error: ${result.error}`;
                this._statusText.className = `${style.status} ${style.error}`;
                PubSub.default.pub("showToast", "toast.converter.error");
            }
        } catch (error) {
            this._statusText.textContent = `Unexpected error: ${error}`;
            this._statusText.className = `${style.status} ${style.error}`;
            PubSub.default.pub("showToast", "toast.converter.error");
        } finally {
            this._convertButton.disabled = false;
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
            this._statusText.textContent = "No document available";
            this._statusText.className = `${style.status} ${style.error}`;
            this._convertButton.disabled = true;
        } else {
            this._statusText.textContent = "Ready - Use ribbon button to unfold shapes";
            this._statusText.className = `${style.status} ${style.ready}`;
            this._convertButton.disabled = false;
        }
    }

    private readonly _handleUnfoldResult = (data: any) => {
        console.log("🚀 _handleUnfoldResult called with:", data);

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
        }

        this._statusText.textContent = "Unfold diagram generated";
        this._statusText.className = `${style.status} ${style.success}`;
    };

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

    private _displaySVG(svgContent: string) {
        // Destroy existing editor if present
        if (this._svgEditor) {
            this._svgEditor.destroy();
            this._svgEditor = null;
        }

        // Clear container and create a new SVG element for the editor
        this._svgContainer.innerHTML = "";

        // Create a container div for the editor
        const editorContainer = document.createElement("div");
        editorContainer.style.width = "100%";
        editorContainer.style.height = "100%";
        editorContainer.style.position = "relative";
        this._svgContainer.appendChild(editorContainer);

        // Create SVG element from content
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = svgContent;
        const svgElement = tempDiv.querySelector("svg");

        if (svgElement) {
            // Ensure SVG has proper dimensions
            svgElement.style.width = "100%";
            svgElement.style.height = "100%";
            editorContainer.appendChild(svgElement);

            // Initialize simple-svg-edit editor with enhanced features
            try {
                // Add required classes for editing functionality
                svgElement.classList.add("sse-editable");

                this._svgEditor = new Editor(svgElement, {
                    // Enable all editing features
                });

                // Setup event listeners for the editor
                this._setupEditorEvents();

                // Enable editing buttons
                this._updateEditButtons();
            } catch (error) {
                console.error("Failed to initialize SVG editor:", error);
                // Fallback: just display the SVG without editing capabilities
                this._svgContainer.innerHTML = svgContent;
            }
        }
    }

    private _setupEditorEvents() {
        if (!this._svgEditor) return;

        // Listen to selection changes
        this._svgEditor.on("selection-changed", () => {
            console.log("Selection changed:", this._svgEditor?.getSelectedElements());
            this._updateEditButtons();
        });

        // Listen to content changes
        this._svgEditor.on("change", () => {
            console.log("SVG content changed");
            this._updateEditButtons();
        });

        // Enable click-to-select on SVG elements
        const svgElements = this._svgEditor.canvas.querySelectorAll(
            "path, rect, circle, ellipse, line, polyline, polygon, text",
        );

        svgElements.forEach((element) => {
            element.addEventListener("click", (e: Event) => {
                e.stopPropagation();
                this._svgEditor?.selectElement(element as SVGElement);
            });

            // Add hover effect
            element.addEventListener("mouseenter", () => {
                const selectedElements = this._svgEditor?.getSelectedElements() || [];
                if (!selectedElements.includes(element as SVGElement)) {
                    (element as SVGElement).style.opacity = "0.8";
                }
            });

            element.addEventListener("mouseleave", () => {
                const selectedElements = this._svgEditor?.getSelectedElements() || [];
                if (!selectedElements.includes(element as SVGElement)) {
                    (element as SVGElement).style.opacity = "1";
                }
            });
        });

        // Click on empty space to deselect
        this._svgEditor.canvas.addEventListener("click", (e: Event) => {
            if (e.target === this._svgEditor?.canvas) {
                this._svgEditor.deselectAll();
            }
        });
    }

    private _updateEditButtons() {
        if (!this._svgEditor) {
            this._disableAllEditButtons();
            return;
        }

        // Update undo/redo buttons based on actual history state
        this._undoButton.disabled = !this._svgEditor.canUndo();
        this._redoButton.disabled = !this._svgEditor.canRedo();

        // Update selection-based buttons
        const selectedElements = this._svgEditor.getSelectedElements();
        const hasSelection = selectedElements && selectedElements.length > 0;
        this._deleteButton.disabled = !hasSelection;
        this._alignLeftButton.disabled = !hasSelection;
        this._alignCenterButton.disabled = !hasSelection;
        this._alignRightButton.disabled = !hasSelection;
    }

    private _disableAllEditButtons() {
        this._undoButton.disabled = true;
        this._redoButton.disabled = true;
        this._deleteButton.disabled = true;
        this._alignLeftButton.disabled = true;
        this._alignCenterButton.disabled = true;
        this._alignRightButton.disabled = true;
    }

    private _handleUndo() {
        if (!this._svgEditor) return;
        this._svgEditor.undo();
        this._updateEditButtons();
    }

    private _handleRedo() {
        if (!this._svgEditor) return;
        this._svgEditor.redo();
        this._updateEditButtons();
    }

    private _handleDelete() {
        if (!this._svgEditor) return;
        this._svgEditor.deleteSelected();
        this._updateEditButtons();
    }

    private _handleAlign(x: number | null, y: number | null) {
        if (!this._svgEditor) return;
        console.log(`Align to x: ${x}, y: ${y}`);
        // TODO: Implement alignment functionality using moveSelected
        // For now, just log the requested alignment
    }

    private _toggleFaceNumbers() {
        this._faceNumbersVisible = !this._faceNumbersVisible;
        console.log(`Toggling face numbers: ${this._faceNumbersVisible}`);

        // 3D viewの面番号表示を切り替え
        const activeDocument = this._getActiveDocument();
        if (activeDocument && activeDocument.visual) {
            // visualのcontextからgeometriesを取得
            const visual = activeDocument.visual as any;
            console.log("Visual object:", visual);

            if (visual.context && visual.context._NodeVisualMap) {
                console.log("Found _NodeVisualMap, size:", visual.context._NodeVisualMap.size);
                let geometryCount = 0;

                visual.context._NodeVisualMap.forEach((visualObject: any, node: any) => {
                    console.log("Checking visual object:", visualObject);
                    // ThreeGeometryインスタンスかチェック
                    if (visualObject && "setFaceNumbersVisible" in visualObject) {
                        console.log("Found geometry with setFaceNumbersVisible method");
                        visualObject.setFaceNumbersVisible(this._faceNumbersVisible);
                        geometryCount++;

                        // 面番号が表示される場合で、まだバックエンドの面番号が設定されていない場合は再設定を試行
                        if (
                            this._faceNumbersVisible &&
                            visualObject.faceNumberDisplay &&
                            visualObject.faceNumberDisplay.backendFaceNumbers &&
                            visualObject.faceNumberDisplay.backendFaceNumbers.size === 0
                        ) {
                            console.log("Backend face numbers not set, checking if we have cached data");
                            // ここで必要に応じてバックエンドから面番号データを再取得する処理を追加
                        }
                    }
                });

                console.log(`Updated ${geometryCount} geometries`);
            } else {
                console.log("No _NodeVisualMap found in context");
            }
        } else {
            console.log("No active document or visual");
        }

        // ボタンのスタイルを更新
        if (this._faceNumbersVisible) {
            this._showFaceNumbersButton.classList.add(style.active);
            this._showFaceNumbersButton.textContent = "🔢 Numbers ✓";
        } else {
            this._showFaceNumbersButton.classList.remove(style.active);
            this._showFaceNumbersButton.textContent = "🔢 Numbers";
        }

        // SVG側の面番号表示も切り替え（将来的に実装）
        this._toggleSvgFaceNumbers();
    }

    private _toggleSvgFaceNumbers() {
        if (!this._svgEditor || !this._svgEditor.canvas) return;

        // SVG内の面番号要素を表示/非表示
        const faceNumbers = this._svgEditor.canvas.querySelectorAll(".face-number");
        faceNumbers.forEach((element) => {
            const svgElement = element as SVGElement;
            svgElement.style.display = this._faceNumbersVisible ? "block" : "none";
        });
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
}

customElements.define("chili-step-unfold-panel", StepUnfoldPanel);
