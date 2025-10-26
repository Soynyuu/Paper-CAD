// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, span } from "chili-controls";
import {
    IApplication,
    IDocument,
    PubSub,
    StepUnfoldService,
    ShapeNode,
    I18n,
    UnfoldOptions,
    IView,
} from "chili-core";
import { config } from "chili-core/src/config/config";
import { FaceNumberDisplay } from "chili-three/src/faceNumberDisplay";
import { Raycaster, Vector2 } from "three";
import style from "./assemblyPanel.module.css";

export class AssemblyPanel extends HTMLElement {
    private static _instance: AssemblyPanel | null = null;
    private readonly _app: IApplication;
    private readonly _service: StepUnfoldService;
    private _view3D: HTMLDivElement;
    private _view2D: HTMLDivElement;
    private _svgContainer: HTMLDivElement;
    private _statusBar: HTMLDivElement;
    private _threeView: IView | null = null;
    private _selectedFaceIndex: number | null = null;
    private _faceMapping: Map<number, string> = new Map(); // 3D face index to 2D element ID
    private _nodes: ShapeNode[] = [];
    private _svgContent: string = "";
    private _faceNumberDisplay: FaceNumberDisplay | null = null;
    private _faceNumberInput: HTMLInputElement | null = null;
    private _raycaster: Raycaster = new Raycaster();
    private _mouse: Vector2 = new Vector2();

    constructor(app: IApplication) {
        super();
        this._app = app;
        AssemblyPanel._instance = this;

        this._service = new StepUnfoldService(config.stepUnfoldApiUrl);

        this._view3D = div({
            className: style.view3D,
        });

        this._svgContainer = div({
            className: style.svgContainer,
        });

        this._view2D = div(
            {
                className: style.view2D,
            },
            this._svgContainer,
        );

        this._statusBar = div(
            {
                className: style.statusBar,
            },
            div(
                {
                    className: style.statusItem,
                },
                span({ className: style.statusLabel, textContent: I18n.translate("assembly.status") + ":" }),
                span({ className: style.statusValue, textContent: I18n.translate("assembly.ready") }),
            ),
            div(
                {
                    className: style.statusItem,
                },
                span({
                    className: style.statusLabel,
                    textContent: I18n.translate("assembly.selectedFace") + ":",
                }),
                span({ className: style.statusValue, textContent: "-", id: "selected-face-display" }),
            ),
        );

        this._render();
        this._setupEventListeners();

        console.log("AssemblyPanel initialized");
    }

    private _render() {
        // 面番号入力フィールド
        this._faceNumberInput = input({
            type: "number",
            min: "1",
            className: style.faceNumberInput,
            placeholder: I18n.translate("assembly.enterFaceNumber"),
            onkeydown: (e: KeyboardEvent) => {
                if (e.key === "Enter") {
                    this._highlightByFaceNumber();
                }
            },
        }) as HTMLInputElement;

        // 面番号入力グループ
        const faceNumberInputGroup = div(
            { className: style.inputGroup },
            span({ className: style.inputLabel, textContent: I18n.translate("assembly.faceNumberInput") }),
            this._faceNumberInput,
            button({
                textContent: I18n.translate("assembly.highlight"),
                className: style.highlightButton,
                onclick: () => this._highlightByFaceNumber(),
            }),
        );

        const closeButton = button({
            textContent: "✕ " + I18n.translate("assembly.close"),
            className: style.closeButton,
            onclick: () => this._close(),
        });

        const helpText = div({
            className: style.helpText,
            textContent: I18n.translate("assembly.helpText"),
        });

        this.append(
            div(
                { className: style.root },
                div(
                    { className: style.header },
                    div(
                        { className: style.title },
                        span({ className: style.titleIcon, textContent: "🔧" }),
                        span({ textContent: I18n.translate("assembly.title") }),
                    ),
                    div({ className: style.controls }, faceNumberInputGroup, helpText, closeButton),
                ),
                div(
                    { className: style.content },
                    div(
                        { className: style.viewContainer },
                        div({ className: style.viewHeader }, I18n.translate("assembly.3dModel")),
                        this._view3D,
                    ),
                    div(
                        { className: style.viewContainer },
                        div({ className: style.viewHeader }, I18n.translate("assembly.2dUnfold")),
                        this._view2D,
                    ),
                ),
                this._statusBar,
            ),
        );
    }

    private _setupEventListeners() {
        // Listen for assembly mode activation
        PubSub.default.sub("assemblyMode.showPanel", async (data: any) => {
            await this._initialize(data);
        });

        // Setup 3D view click handler
        this._view3D.addEventListener("click", (event) => {
            this._handle3DClick(event);
        });
    }

    private async _initialize(data: { nodes: ShapeNode[]; stepData: Blob }) {
        this._nodes = data.nodes;

        // Show the panel
        this.style.display = "block";
        document.body.appendChild(this);

        // Initialize 3D view with the current document's view
        await this._setup3DView();

        // Generate and display 2D unfold
        await this._generateUnfold(data.stepData);

        console.log("Assembly mode initialized with nodes:", this._nodes);
    }

    private async _setup3DView() {
        // Use the existing active view instead of creating a new one
        const activeView = this._app.activeView;
        if (!activeView) {
            console.error("No active view");
            return;
        }

        try {
            // Store reference to the existing view
            this._threeView = activeView;

            // Get FaceNumberDisplay from the active view
            const visual = activeView.document?.visual as any;
            if (visual && visual.context) {
                // Find FaceNumberDisplay in the scene
                const context = visual.context;
                const scene = (context as any)._scene;
                if (scene) {
                    // Search for FaceNumberDisplay in scene children
                    scene.traverse((child: any) => {
                        if (child instanceof FaceNumberDisplay) {
                            this._faceNumberDisplay = child;
                            console.log("Found FaceNumberDisplay in scene");
                        }
                    });
                }

                // If not found, try to create it from the selected nodes
                if (!this._faceNumberDisplay && this._nodes.length > 0) {
                    const shapeNode = this._nodes[0] as ShapeNode;
                    if (shapeNode.shape) {
                        this._faceNumberDisplay = new FaceNumberDisplay();
                        this._faceNumberDisplay.generateFromShape(shapeNode.shape);
                        this._faceNumberDisplay.setVisible(true);
                        scene?.add(this._faceNumberDisplay);
                        console.log("Created new FaceNumberDisplay");
                    }
                }
            }

            // Display the 3D view in the panel
            const viewportElement = (activeView as any).renderer?.domElement;
            if (viewportElement) {
                // Append the actual renderer canvas to show live 3D view
                this._view3D.appendChild(viewportElement.cloneNode(true));
                console.log("3D view canvas added to panel");
            }

            console.log("3D view setup complete");
        } catch (error) {
            console.error("Failed to setup 3D view:", error);
        }
    }

    private async _generateUnfold(stepData: Blob) {
        try {
            // Generate unfold with face numbers
            const options: UnfoldOptions = {
                scale: 1,
                layoutMode: "canvas",
                pageFormat: "A4",
                pageOrientation: "landscape",
                returnFaceNumbers: true,
            };

            const result = await this._service.unfoldStepFromData(stepData, options);

            if (result.isOk) {
                const responseData = result.value as any;
                this._svgContent = responseData.svg_content || responseData.svgContent || "";

                // Display SVG
                this._displaySVG(this._svgContent);

                // Setup face mapping
                const faceNumbers = responseData.face_numbers || responseData.faceNumbers;
                if (faceNumbers) {
                    this._setupFaceMapping(faceNumbers);

                    // Set face numbers to FaceNumberDisplay for 3D highlighting
                    if (this._faceNumberDisplay) {
                        this._faceNumberDisplay.setBackendFaceNumbers(faceNumbers);
                        console.log("Face numbers set to FaceNumberDisplay:", faceNumbers);
                    }
                }

                console.log("Unfold generated successfully");
            } else {
                console.error("Failed to generate unfold:", result.error);
                PubSub.default.pub("showToast", "toast.assemblyMode.unfoldError");
            }
        } catch (error) {
            console.error("Error generating unfold:", error);
        }
    }

    private _displaySVG(svgContent: string) {
        // Clear existing content
        this._svgContainer.innerHTML = "";

        // Create a wrapper for the SVG
        const wrapper = document.createElement("div");
        wrapper.innerHTML = svgContent;

        // Make SVG responsive
        const svg = wrapper.querySelector("svg");
        if (svg) {
            svg.setAttribute("width", "100%");
            svg.setAttribute("height", "100%");
            svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
        }

        this._svgContainer.appendChild(wrapper);

        // Add click handlers to SVG elements
        this._setupSVGInteraction();
    }

    private _setupFaceMapping(faceNumbers: Array<{ faceIndex: number; faceNumber: number }>) {
        // Create mapping between 3D face indices and 2D SVG elements
        faceNumbers.forEach(({ faceIndex, faceNumber }) => {
            // SVG elements might have IDs like "face-1", "face-2", etc.
            this._faceMapping.set(faceIndex, `face-${faceNumber}`);
        });

        console.log("Face mapping established:", this._faceMapping);
    }

    private _setupSVGInteraction() {
        // Add hover and click effects to SVG faces
        const svgFaces = this._svgContainer.querySelectorAll("path, polygon, rect, circle");

        svgFaces.forEach((element, index) => {
            // Add data attributes for identification
            element.setAttribute("data-face-index", index.toString());
            // Face number is 1-indexed (index + 1)
            const faceNumber = index + 1;
            element.setAttribute("data-face-number", faceNumber.toString());

            // Add hover effect
            element.addEventListener("mouseenter", () => {
                (element as SVGElement).style.opacity = "0.7";
                (element as SVGElement).style.cursor = "pointer";
            });

            element.addEventListener("mouseleave", () => {
                if (!element.classList.contains("highlighted")) {
                    (element as SVGElement).style.opacity = "1";
                }
            });

            // Add click handler
            element.addEventListener("click", () => {
                this._handle2DClick(faceNumber);
            });
        });
    }

    private _handle3DClick(event: MouseEvent) {
        // Use raycasting to detect which face was clicked
        if (!this._threeView) return;

        const rect = this._view3D.getBoundingClientRect();
        this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Get the camera and scene from the view
        const threeView = this._threeView as any;
        const camera = threeView.camera;
        const scene = threeView.document?.visual?.context?._scene;

        if (!camera || !scene) {
            console.warn("Camera or scene not available for raycasting");
            return;
        }

        // Perform raycasting
        this._raycaster.setFromCamera(this._mouse, camera);
        const intersects = this._raycaster.intersectObjects(scene.children, true);

        if (intersects.length > 0) {
            const intersect = intersects[0];
            // Try to get face number from the intersected object
            if (intersect.face && this._faceNumberDisplay) {
                const faceIndex = intersect.faceIndex ?? 0;
                const faceNumber = this._faceNumberDisplay.getFaceNumberByIndex(faceIndex);
                if (faceNumber !== undefined) {
                    console.log(`3D face clicked: index=${faceIndex}, number=${faceNumber}`);
                    this._highlightFace(faceNumber);
                } else {
                    console.warn(`Could not find face number for face index ${faceIndex}`);
                }
            }
        }
    }

    private _handle2DClick(faceNumber: number) {
        // Highlight the corresponding face in both 2D and 3D
        console.log(`2D SVG face ${faceNumber} clicked`);
        this._highlightFace(faceNumber);
    }

    /**
     * 面番号入力フィールドからハイライト
     */
    private _highlightByFaceNumber() {
        if (!this._faceNumberInput) return;

        const faceNumber = parseInt(this._faceNumberInput.value);
        if (isNaN(faceNumber) || faceNumber < 1) {
            PubSub.default.pub("showToast", "Please enter a valid face number (1 or greater)");
            return;
        }

        console.log(`Highlighting face number: ${faceNumber}`);
        this._highlightFace(faceNumber);
    }

    /**
     * 指定された面番号をハイライト（3DとSVG両方）
     */
    private _highlightFace(faceNumber: number) {
        // Clear previous highlights
        this._clearHighlights();

        // Update status
        this._selectedFaceIndex = faceNumber - 1; // Convert to 0-indexed
        const statusValue = document.getElementById("selected-face-display");
        if (statusValue) {
            statusValue.textContent = `Face ${faceNumber}`;
        }

        // Highlight in 3D view using FaceNumberDisplay
        if (this._faceNumberDisplay) {
            this._faceNumberDisplay.highlightFace(faceNumber);
            console.log(`3D face ${faceNumber} highlighted via FaceNumberDisplay`);
        } else {
            console.warn("FaceNumberDisplay not available for 3D highlighting");
        }

        // Highlight in 2D view (SVG)
        this._highlightSVGFace(faceNumber);
    }

    /**
     * SVG展開図の指定された面をハイライト
     */
    private _highlightSVGFace(faceNumber: number) {
        // Try to find SVG element by data-face-number attribute
        const svgElement = this._svgContainer.querySelector(`[data-face-number="${faceNumber}"]`);
        if (svgElement) {
            svgElement.classList.add("highlighted");
            (svgElement as SVGElement).style.fill = "rgba(255, 220, 0, 0.5)";
            (svgElement as SVGElement).style.stroke = "#ffa500";
            (svgElement as SVGElement).style.strokeWidth = "3";
            console.log(`2D SVG face ${faceNumber} highlighted`);
        } else {
            // Fallback: highlight by index (faceNumber - 1)
            const svgElements = this._svgContainer.querySelectorAll("path, polygon");
            if (svgElements[faceNumber - 1]) {
                const element = svgElements[faceNumber - 1] as SVGElement;
                element.classList.add("highlighted");
                element.style.fill = "rgba(255, 220, 0, 0.5)";
                element.style.stroke = "#ffa500";
                element.style.strokeWidth = "3";
                console.log(`2D SVG face ${faceNumber} highlighted (fallback by index)`);
            } else {
                console.warn(`Could not find SVG element for face ${faceNumber}`);
            }
        }
    }

    private _highlightCorrespondingFace(faceIndex: number, source: "2d" | "3d") {
        // Convert faceIndex to faceNumber (1-indexed)
        const faceNumber = faceIndex + 1;
        this._highlightFace(faceNumber);
    }

    private _clearHighlights() {
        // Clear 2D highlights
        const highlightedElements = this._svgContainer.querySelectorAll(".highlighted");
        highlightedElements.forEach((element) => {
            element.classList.remove("highlighted");
            (element as SVGElement).style.fill = "";
            (element as SVGElement).style.stroke = "";
            (element as SVGElement).style.strokeWidth = "";
            (element as SVGElement).style.opacity = "1";
        });

        // Clear 3D highlights using FaceNumberDisplay
        if (this._faceNumberDisplay) {
            this._faceNumberDisplay.clearHighlights();
            console.log("3D highlights cleared");
        }
    }

    private _close() {
        // Clean up and close the panel
        this._clearHighlights();

        if (this._threeView) {
            // Dispose Three.js view
            (this._threeView as any).dispose?.();
            this._threeView = null;
        }

        // Remove from DOM
        this.remove();

        // Notify that assembly mode is closed
        PubSub.default.pub("assemblyMode.closed");
        PubSub.default.pub("showToast", "toast.assemblyMode.closed");

        console.log("Assembly panel closed");
    }

    public static getInstance(): AssemblyPanel | null {
        return AssemblyPanel._instance;
    }
}

customElements.define("chili-assembly-panel", AssemblyPanel);
