// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, span } from "chili-controls";
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
            this._svgContainer
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
                span({ className: style.statusValue, textContent: I18n.translate("assembly.ready") })
            ),
            div(
                {
                    className: style.statusItem,
                },
                span({ className: style.statusLabel, textContent: I18n.translate("assembly.selectedFace") + ":" }),
                span({ className: style.statusValue, textContent: "-", id: "selected-face-display" })
            )
        );

        this._render();
        this._setupEventListeners();

        console.log("AssemblyPanel initialized");
    }

    private _render() {
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
                        span({ textContent: I18n.translate("assembly.title") })
                    ),
                    div(
                        { className: style.controls },
                        helpText,
                        closeButton
                    )
                ),
                div(
                    { className: style.content },
                    div(
                        { className: style.viewContainer },
                        div(
                            { className: style.viewHeader },
                            I18n.translate("assembly.3dModel")
                        ),
                        this._view3D
                    ),
                    div(
                        { className: style.viewContainer },
                        div(
                            { className: style.viewHeader },
                            I18n.translate("assembly.2dUnfold")
                        ),
                        this._view2D
                    )
                ),
                this._statusBar
            )
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

    private async _initialize(data: { nodes: ShapeNode[], stepData: Blob }) {
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

            // Clone the 3D view content to display in the assembly panel
            const viewportElement = (activeView as any).renderer?.domElement;
            if (viewportElement) {
                // Create a copy of the current 3D view
                const clonedCanvas = document.createElement("canvas");
                clonedCanvas.style.width = "100%";
                clonedCanvas.style.height = "100%";
                this._view3D.appendChild(clonedCanvas);

                // Copy the rendering context
                const ctx = clonedCanvas.getContext("2d");
                if (ctx && viewportElement instanceof HTMLCanvasElement) {
                    // Set up periodic rendering from the main view
                    const renderFrame = () => {
                        if (this._view3D.parentElement) {
                            ctx.drawImage(viewportElement, 0, 0, clonedCanvas.width, clonedCanvas.height);
                            requestAnimationFrame(renderFrame);
                        }
                    };
                    renderFrame();
                }
            }

            // Enable face number display for interaction
            this._enableFaceNumbersFor3D();

            console.log("3D view setup complete");
        } catch (error) {
            console.error("Failed to setup 3D view:", error);
        }
    }

    private _enableFaceNumbersFor3D() {
        const activeDocument = this._app.activeView?.document;
        if (activeDocument && activeDocument.visual) {
            const visual = activeDocument.visual as any;
            if (visual.context && visual.context._NodeVisualMap) {
                visual.context._NodeVisualMap.forEach((visualObject: any) => {
                    if (visualObject && "setFaceNumbersVisible" in visualObject) {
                        // Enable face detection without showing numbers
                        visualObject.enableFaceInteraction = true;
                    }
                });
            }
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
            // Add data attribute for identification
            element.setAttribute("data-face-index", index.toString());

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
                this._handle2DClick(index);
            });
        });
    }

    private _handle3DClick(event: MouseEvent) {
        // Use raycasting to detect which face was clicked
        if (!this._threeView) return;

        const rect = this._view3D.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Get the intersected face (this would need to be implemented in ThreeView)
        // For now, we'll simulate with a placeholder
        const faceIndex = this._detectFaceAt3DPosition(x, y);

        if (faceIndex !== null) {
            this._highlightCorrespondingFace(faceIndex, "3d");
        }
    }

    private _handle2DClick(svgFaceIndex: number) {
        // Find corresponding 3D face and highlight it
        this._highlightCorrespondingFace(svgFaceIndex, "2d");
    }

    private _detectFaceAt3DPosition(x: number, y: number): number | null {
        // TODO: Implement actual raycasting to detect face
        // This is a placeholder that returns a random face for demonstration
        return Math.floor(Math.random() * 6);
    }

    private _highlightCorrespondingFace(faceIndex: number, source: "2d" | "3d") {
        // Clear previous highlights
        this._clearHighlights();

        // Update status
        this._selectedFaceIndex = faceIndex;
        const statusValue = document.getElementById("selected-face-display");
        if (statusValue) {
            statusValue.textContent = `Face ${faceIndex + 1}`;
        }

        if (source === "3d") {
            // Highlight in 2D view
            const svgElementId = this._faceMapping.get(faceIndex);
            if (svgElementId) {
                const svgElement = this._svgContainer.querySelector(`#${svgElementId}`);
                if (svgElement) {
                    svgElement.classList.add("highlighted");
                    (svgElement as SVGElement).style.fill = "rgba(255, 220, 0, 0.5)";
                    (svgElement as SVGElement).style.stroke = "#ffa500";
                    (svgElement as SVGElement).style.strokeWidth = "3";
                }
            } else {
                // Fallback: highlight by index
                const svgElements = this._svgContainer.querySelectorAll("path, polygon");
                if (svgElements[faceIndex]) {
                    const element = svgElements[faceIndex] as SVGElement;
                    element.classList.add("highlighted");
                    element.style.fill = "rgba(255, 220, 0, 0.5)";
                    element.style.stroke = "#ffa500";
                    element.style.strokeWidth = "3";
                }
            }
        } else {
            // Highlight in 3D view
            // TODO: Implement 3D highlighting through Three.js
            console.log(`Would highlight 3D face ${faceIndex}`);
        }
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

        // Clear 3D highlights (TODO)
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