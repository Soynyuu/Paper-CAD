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
import { ThreeGeometryFactory } from "chili-three/src/threeGeometryFactory";
import {
    AmbientLight,
    Box3,
    DirectionalLight,
    Mesh,
    PerspectiveCamera,
    Raycaster,
    Scene,
    Vector2,
    Vector3,
    WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import panzoom, { PanZoom } from "panzoom";
import style from "./assemblyPanel.module.css";

export class AssemblyPanel extends HTMLElement {
    private static _instance: AssemblyPanel | null = null;
    private readonly _app: IApplication;
    private readonly _service: StepUnfoldService;
    private _view3D: HTMLDivElement;
    private _view2D: HTMLDivElement;
    private _svgContainer: HTMLDivElement;
    private _statusBar: HTMLDivElement;
    private _selectedFaceIndex: number | null = null;
    private _faceMapping: Map<number, string> = new Map(); // 3D face index to 2D element ID
    private _nodes: ShapeNode[] = [];
    private _svgContent: string = "";
    private _faceNumberDisplay: FaceNumberDisplay | null = null;
    private _faceNumberInput: HTMLInputElement | null = null;
    private _raycaster: Raycaster = new Raycaster();
    private _mouse: Vector2 = new Vector2();
    private _panzoomInstance: PanZoom | null = null;

    // Three.js environment
    private _scene: Scene | null = null;
    private _camera: PerspectiveCamera | null = null;
    private _renderer: WebGLRenderer | null = null;
    private _controls: OrbitControls | null = null;
    private _animationFrameId: number | null = null;
    private _resizeHandler: (() => void) | null = null;

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

        // Remove existing panel if any
        const existingPanel = document.querySelector("chili-assembly-panel");
        if (existingPanel && existingPanel !== this) {
            console.log("Removing existing assembly panel");
            existingPanel.remove();
        }

        // Show the panel with explicit styles
        this.style.display = "block";
        this.style.position = "fixed";
        this.style.top = "0";
        this.style.left = "0";
        this.style.width = "100vw";
        this.style.height = "100vh";
        this.style.zIndex = "9999";

        // Add to DOM if not already connected
        if (!this.isConnected) {
            document.body.appendChild(this);
        }
        console.log("Assembly panel added to DOM:", this.isConnected);

        // Initialize 3D view with the current document's view
        await this._setup3DView();

        // Generate and display 2D unfold
        await this._generateUnfold(data.stepData);

        console.log("Assembly mode initialized with nodes:", this._nodes);
    }

    private async _setup3DView() {
        try {
            // Wait for DOM to be fully rendered
            await new Promise((resolve) => setTimeout(resolve, 0));

            // Get actual dimensions
            const width = this._view3D.clientWidth || 800;
            const height = this._view3D.clientHeight || 600;

            console.log(`3D view dimensions: ${width}x${height}`);

            // Create new Three.js scene
            this._scene = new Scene();
            this._scene.background = null; // Transparent background

            // Create camera
            const aspect = width / height;
            this._camera = new PerspectiveCamera(50, aspect, 0.1, 10000);
            this._camera.position.set(5, 5, 5);

            // Create renderer
            this._renderer = new WebGLRenderer({ antialias: true, alpha: true });
            this._renderer.setSize(width, height);
            this._renderer.setPixelRatio(window.devicePixelRatio);
            this._view3D.appendChild(this._renderer.domElement);

            // Create orbit controls
            this._controls = new OrbitControls(this._camera, this._renderer.domElement);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.05;

            // Add lights
            const ambientLight = new AmbientLight(0xffffff, 0.5);
            this._scene.add(ambientLight);

            const directionalLight = new DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(5, 10, 7.5);
            this._scene.add(directionalLight);

            // Add shape meshes from selected nodes
            const boundingBox = new Box3();
            for (const node of this._nodes) {
                if (node instanceof ShapeNode) {
                    const shapeResult = node.shape;
                    if (shapeResult && shapeResult.isOk) {
                        const shape = shapeResult.value;

                        // Get mesh data and create Three.js geometries
                        const meshData = shape.mesh;

                        // Create face geometry
                        if (meshData.faces) {
                            const faceMesh = ThreeGeometryFactory.createFaceGeometry(meshData.faces);
                            this._scene.add(faceMesh);
                            faceMesh.geometry.computeBoundingBox();
                            if (faceMesh.geometry.boundingBox) {
                                boundingBox.union(faceMesh.geometry.boundingBox);
                            }
                        }

                        // Create edge geometry
                        if (meshData.edges) {
                            const edgeMesh = ThreeGeometryFactory.createEdgeGeometry(meshData.edges);
                            this._scene.add(edgeMesh);
                        }

                        // Create FaceNumberDisplay
                        this._faceNumberDisplay = new FaceNumberDisplay();
                        this._faceNumberDisplay.generateFromShape(shape);
                        this._faceNumberDisplay.setVisible(true);
                        this._scene.add(this._faceNumberDisplay);
                    }
                }
            }

            // Fit camera to view all objects
            if (!boundingBox.isEmpty()) {
                const center = boundingBox.getCenter(new Vector3());
                const size = boundingBox.getSize(new Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const fov = this._camera.fov * (Math.PI / 180);
                let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
                cameraZ *= 1.5; // Add some padding

                this._camera.position.set(center.x + cameraZ, center.y + cameraZ, center.z + cameraZ);
                this._camera.lookAt(center);
                this._controls.target.copy(center);
                this._controls.update();
            }

            // Setup resize handler
            this._resizeHandler = () => {
                if (this._camera && this._renderer) {
                    const width = this._view3D.clientWidth || 800;
                    const height = this._view3D.clientHeight || 600;
                    this._camera.aspect = width / height;
                    this._camera.updateProjectionMatrix();
                    this._renderer.setSize(width, height);
                }
            };
            window.addEventListener("resize", this._resizeHandler);

            // Start animation loop
            this._animate();

            console.log("3D view setup complete with", this._nodes.length, "nodes");
        } catch (error) {
            console.error("Failed to setup 3D view:", error);
        }
    }

    private _animate = () => {
        this._animationFrameId = requestAnimationFrame(this._animate);

        if (this._controls) {
            this._controls.update();
        }

        if (this._renderer && this._scene && this._camera) {
            this._renderer.render(this._scene, this._camera);
        }
    };

    private async _generateUnfold(stepData: Blob) {
        try {
            // Generate unfold with face numbers
            const options: UnfoldOptions = {
                scale: 1,
                layoutMode: "paged",
                pageFormat: "A4",
                pageOrientation: "portrait",
                returnFaceNumbers: true,
            };

            const result = await this._service.unfoldStepFromData(stepData, options);

            if (result.isOk) {
                const responseData = result.value as any;
                console.log("🔍 API Response structure:", {
                    hasResponse: !!responseData,
                    keys: Object.keys(responseData || {}),
                    hasSvgContent: "svg_content" in (responseData || {}),
                    hasSvgContentCamel: "svgContent" in (responseData || {}),
                    hasFaceNumbers: "face_numbers" in (responseData || {}),
                    hasFaceNumbersCamel: "faceNumbers" in (responseData || {}),
                });

                this._svgContent = responseData.svg_content || responseData.svgContent || "";
                console.log("🔍 SVG Content length:", this._svgContent.length);
                if (this._svgContent.length > 0) {
                    console.log(
                        "🔍 SVG Content preview (first 200 chars):",
                        this._svgContent.substring(0, 200),
                    );
                } else {
                    console.error("❌ SVG content is empty!");
                }

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
        console.log("🔍 _displaySVG called");
        console.log("🔍 SVG container dimensions:", {
            width: this._svgContainer.clientWidth,
            height: this._svgContainer.clientHeight,
            offsetWidth: this._svgContainer.offsetWidth,
            offsetHeight: this._svgContainer.offsetHeight,
        });
        console.log("🔍 SVG content length:", svgContent.length);

        if (!svgContent || svgContent.length === 0) {
            console.error("❌ Cannot display SVG: content is empty");
            this._svgContainer.innerHTML =
                '<div style="padding: 20px; color: red;">Error: SVG content is empty</div>';
            return;
        }

        // Clear existing content
        this._svgContainer.innerHTML = "";

        // Create a wrapper for the SVG
        const wrapper = document.createElement("div");
        wrapper.innerHTML = svgContent;
        console.log("🔍 Wrapper created, children count:", wrapper.children.length);

        // Make SVG responsive
        const svg = wrapper.querySelector("svg");
        if (svg) {
            console.log("🔍 SVG element found");
            console.log("🔍 SVG original attributes:", {
                width: svg.getAttribute("width"),
                height: svg.getAttribute("height"),
                viewBox: svg.getAttribute("viewBox"),
            });
            svg.setAttribute("width", "100%");
            svg.setAttribute("height", "100%");
            svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
            console.log("🔍 SVG attributes updated");
        } else {
            console.error("❌ No SVG element found in content");
            console.log("🔍 Wrapper HTML preview:", wrapper.innerHTML.substring(0, 500));
        }

        this._svgContainer.appendChild(wrapper);
        console.log("🔍 SVG wrapper appended to container");

        // Initialize panzoom for interactive zoom/pan
        if (svg) {
            // Dispose existing panzoom instance if any
            if (this._panzoomInstance) {
                this._panzoomInstance.dispose();
                this._panzoomInstance = null;
            }

            // Create new panzoom instance on the wrapper div instead of SVG
            // This allows SVG elements to receive click events normally
            const wrapper = svg.parentElement;
            if (wrapper) {
                this._panzoomInstance = panzoom(svg, {
                    maxZoom: 10,
                    minZoom: 0.1,
                    initialZoom: 1,
                    zoomSpeed: 0.1,
                    smoothScroll: false,
                    bounds: true,
                    boundsPadding: 0.1,
                    // Use beforeWheel to always allow zoom, but filter mousedown for panning
                    beforeMouseDown: function (e) {
                        const target = e.target as SVGElement;
                        const className =
                            typeof target.className === "string"
                                ? target.className
                                : target.className.baseVal;
                        console.log("🐭 Mouse down on:", target.tagName, "class:", className);

                        // Allow panning only when NOT clicking on face polygons
                        const shouldPreventPan = className.includes("face-polygon");

                        if (shouldPreventPan) {
                            console.log("🚫 Preventing pan to allow click on face polygon");
                            return false;
                        }
                        console.log("✅ Allowing pan");
                        return true;
                    },
                });
            }

            console.log("🔍 Panzoom initialized for SVG");
        }

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
        console.log("🔧 Setting up SVG interaction handlers");

        // Add hover and click effects to SVG faces
        // Only select face polygons, not tabs or other elements
        const svgFaces = this._svgContainer.querySelectorAll(
            "path.face-polygon, path.face-polygon-textured, polygon.face-polygon, polygon.face-polygon-textured",
        );

        console.log(`📊 Found ${svgFaces.length} SVG face elements to set up`);

        // Debug: log all SVG elements to see what we have
        const allSvgElements = this._svgContainer.querySelectorAll("path, polygon");
        console.log(`📊 Total SVG path/polygon elements: ${allSvgElements.length}`);
        allSvgElements.forEach((el, idx) => {
            const svgEl = el as SVGElement;
            const className =
                typeof svgEl.className === "string" ? svgEl.className : svgEl.className.baseVal;
            console.log(
                `  Element ${idx}: <${svgEl.tagName}> classes="${className}" data-face-number="${svgEl.getAttribute("data-face-number")}"`,
            );
        });

        svgFaces.forEach((element, index) => {
            // Add data attributes for identification
            element.setAttribute("data-face-index", index.toString());

            // Use backend's data-face-number if available, otherwise fallback to index + 1
            let faceNumber: number;
            const existingFaceNumber = element.getAttribute("data-face-number");
            if (existingFaceNumber) {
                faceNumber = parseInt(existingFaceNumber, 10);
                console.log(`SVG element ${index}: Using backend face number ${faceNumber}`);
            } else {
                // Fallback: Use index + 1 for backward compatibility
                faceNumber = index + 1;
                element.setAttribute("data-face-number", faceNumber.toString());
                console.log(`SVG element ${index}: Fallback to index-based face number ${faceNumber}`);
            }

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
            element.addEventListener("click", (e) => {
                console.log(`🖱️ 2D SVG face clicked: ${faceNumber}`);
                e.stopPropagation(); // Prevent event bubbling
                this._handle2DClick(faceNumber);
            });

            console.log(`  ✅ Registered click handler for face ${faceNumber} (element ${index})`);
        });

        console.log(`🔧 SVG interaction setup complete: ${svgFaces.length} faces registered`);
    }

    private _handle3DClick(event: MouseEvent) {
        console.log(`🖱️ 3D view clicked`);

        // Use raycasting to detect which face was clicked
        if (!this._scene || !this._camera) {
            console.warn("Scene or camera not available for 3D click");
            return;
        }

        const rect = this._view3D.getBoundingClientRect();
        this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Perform raycasting
        this._raycaster.setFromCamera(this._mouse, this._camera);
        const intersects = this._raycaster.intersectObjects(this._scene.children, true);

        console.log(`🎯 Raycasting found ${intersects.length} intersections`);

        if (intersects.length > 0) {
            const intersect = intersects[0];
            console.log(`🎯 First intersection:`, {
                object: intersect.object.type,
                hasFace: !!intersect.face,
                faceIndex: intersect.faceIndex,
            });

            // Try to get face number from the intersected object
            if (intersect.face && this._faceNumberDisplay) {
                const faceIndex = intersect.faceIndex ?? 0;
                const faceNumber = this._faceNumberDisplay.getFaceNumberByIndex(faceIndex);
                if (faceNumber !== undefined) {
                    console.log(`✅ 3D face clicked: index=${faceIndex}, number=${faceNumber}`);
                    this._highlightFace(faceNumber);
                } else {
                    console.warn(`❌ Could not find face number for face index ${faceIndex}`);
                }
            } else {
                console.warn(`❌ No face or FaceNumberDisplay available`);
            }
        } else {
            console.log(`ℹ️ No 3D object clicked (empty space)`);
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
            PubSub.default.pub("showToast", "toast.assemblyMode.invalidFaceNumber");
            return;
        }

        console.log(`Highlighting face number: ${faceNumber}`);
        this._highlightFace(faceNumber);
    }

    /**
     * 指定された面番号をハイライト（3DとSVG両方）
     */
    private _highlightFace(faceNumber: number) {
        console.log(`🎨 Highlighting face number: ${faceNumber}`);

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
            console.log(`✅ 3D face ${faceNumber} highlighted via FaceNumberDisplay`);
        } else {
            console.warn("❌ FaceNumberDisplay not available for 3D highlighting");
        }

        // Highlight in 2D view (SVG)
        this._highlightSVGFace(faceNumber);
    }

    /**
     * SVG展開図の指定された面をハイライト
     */
    private _highlightSVGFace(faceNumber: number) {
        console.log(`🔍 Searching for SVG face ${faceNumber}`);

        // Try to find SVG element by data-face-number attribute
        const svgElement = this._svgContainer.querySelector(`[data-face-number="${faceNumber}"]`);
        if (svgElement) {
            svgElement.classList.add("highlighted");
            (svgElement as SVGElement).style.fill = "rgba(255, 220, 0, 0.5)";
            (svgElement as SVGElement).style.stroke = "#ffa500";
            (svgElement as SVGElement).style.strokeWidth = "3";
            console.log(`✅ 2D SVG face ${faceNumber} highlighted by data-face-number`);
        } else {
            console.log(`⚠️ No element found with data-face-number="${faceNumber}", trying fallback`);
            // Fallback: highlight by index (faceNumber - 1)
            const svgElements = this._svgContainer.querySelectorAll("path, polygon");
            console.log(`📊 Found ${svgElements.length} total SVG path/polygon elements`);
            if (svgElements[faceNumber - 1]) {
                const element = svgElements[faceNumber - 1] as SVGElement;
                element.classList.add("highlighted");
                element.style.fill = "rgba(255, 220, 0, 0.5)";
                element.style.stroke = "#ffa500";
                element.style.strokeWidth = "3";
                console.log(
                    `✅ 2D SVG face ${faceNumber} highlighted (fallback by index ${faceNumber - 1})`,
                );
            } else {
                console.warn(
                    `❌ Could not find SVG element for face ${faceNumber} (index ${faceNumber - 1} out of ${svgElements.length})`,
                );
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
        console.log(`🧹 Clearing ${highlightedElements.length} highlighted 2D elements`);
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
            console.log("✅ 3D highlights cleared");
        }
    }

    private _close() {
        // Clean up and close the panel
        this._clearHighlights();

        // Dispose panzoom instance
        if (this._panzoomInstance) {
            this._panzoomInstance.dispose();
            this._panzoomInstance = null;
        }

        // Remove resize handler
        if (this._resizeHandler) {
            window.removeEventListener("resize", this._resizeHandler);
            this._resizeHandler = null;
        }

        // Stop animation loop
        if (this._animationFrameId !== null) {
            cancelAnimationFrame(this._animationFrameId);
            this._animationFrameId = null;
        }

        // Dispose Three.js resources
        if (this._controls) {
            this._controls.dispose();
            this._controls = null;
        }

        if (this._renderer) {
            this._renderer.dispose();
            this._renderer = null;
        }

        if (this._scene) {
            this._scene.traverse((object) => {
                if (object instanceof Mesh) {
                    object.geometry.dispose();
                    if (Array.isArray(object.material)) {
                        object.material.forEach((material) => material.dispose());
                    } else {
                        object.material.dispose();
                    }
                }
            });
            this._scene.clear();
            this._scene = null;
        }

        this._camera = null;
        this._faceNumberDisplay = null;

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
