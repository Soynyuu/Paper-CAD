// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, span } from "chili-controls";
import {
    I18n,
    I18nKeys,
    IApplication,
    PubSub,
    StepUnfoldService,
    ShapeNode,
    UnfoldOptions,
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

type FaceNumberData = Array<{ faceIndex: number; faceNumber: number }>;

export class AssemblyPanel extends HTMLElement {
    private static _instance: AssemblyPanel | null = null;

    private readonly _service: StepUnfoldService;
    private readonly _view3D: HTMLDivElement;
    private readonly _view2D: HTMLDivElement;
    private readonly _svgContainer: HTMLDivElement;
    private readonly _statusValue: HTMLSpanElement;
    private readonly _selectedFaceValue: HTMLSpanElement;
    private readonly _faceCountValue: HTMLSpanElement;
    private readonly _faceNumberInput: HTMLInputElement;
    private readonly _view3DLoading: HTMLDivElement;
    private readonly _view2DLoading: HTMLDivElement;

    private readonly _raycaster: Raycaster = new Raycaster();
    private readonly _mouse: Vector2 = new Vector2();
    private readonly _faceElementsByNumber: Map<number, SVGElement[]> = new Map();

    private _nodes: ShapeNode[] = [];
    private _selectedFaceNumber: number | null = null;
    private _faceNumberDisplay: FaceNumberDisplay | null = null;
    private _panzoomInstance: PanZoom | null = null;

    // Three.js environment
    private _scene: Scene | null = null;
    private _camera: PerspectiveCamera | null = null;
    private _renderer: WebGLRenderer | null = null;
    private _controls: OrbitControls | null = null;
    private _animationFrameId: number | null = null;
    private _resizeHandler: (() => void) | null = null;

    private _defaultCameraPosition: Vector3 | null = null;
    private _defaultControlTarget: Vector3 | null = null;
    private _windowKeydownHandler: ((event: KeyboardEvent) => void) | null = null;

    constructor(_app: IApplication) {
        super();
        AssemblyPanel._instance = this;

        this.className = style.host;
        this._service = new StepUnfoldService(config.stepUnfoldApiUrl);

        this._view3D = div({ className: style.view3D });
        this._svgContainer = div({ className: style.svgContainer });
        this._view2D = div({ className: style.view2D }, this._svgContainer);

        this._view3DLoading = div({ className: style.loadingOverlay });
        this._view2DLoading = div({ className: style.loadingOverlay });

        this._statusValue = span({
            className: style.statusValue,
            textContent: I18n.translate("assembly.ready"),
        });

        this._selectedFaceValue = span({
            className: style.statusValue,
            textContent: "-",
        });

        this._faceCountValue = span({
            className: style.statusValue,
            textContent: "0",
        });

        this._faceNumberInput = input({
            type: "number",
            min: "1",
            className: style.faceNumberInput,
            placeholder: I18n.translate("assembly.enterFaceNumber"),
            onkeydown: (event: KeyboardEvent) => {
                if (event.key === "Enter" && !event.isComposing) {
                    event.preventDefault();
                    this._highlightByFaceNumber();
                }
            },
        }) as HTMLInputElement;

        this._render();
        this._setupEventListeners();
    }

    private _render() {
        const closeButton = button({
            textContent: I18n.translate("assembly.close"),
            className: `${style.button} ${style.buttonDanger}`,
            onclick: () => this._close(),
        });

        const highlightButton = button({
            textContent: I18n.translate("assembly.highlight"),
            className: `${style.button} ${style.buttonPrimary}`,
            onclick: () => this._highlightByFaceNumber(),
        });

        const clearButton = button({
            textContent: I18n.translate("assembly.clearSelection"),
            className: `${style.button} ${style.buttonSecondary}`,
            onclick: () => this._clearSelection(),
        });

        const reset3DButton = button({
            textContent: I18n.translate("assembly.reset3DView"),
            className: `${style.button} ${style.buttonSecondary}`,
            onclick: () => this._reset3DView(),
        });

        const zoomOutButton = button({
            textContent: "−",
            className: `${style.button} ${style.iconButton}`,
            title: I18n.translate("assembly.zoomOut"),
            onclick: () => this._zoom2D(0.85),
        });

        const zoomInButton = button({
            textContent: "+",
            className: `${style.button} ${style.iconButton}`,
            title: I18n.translate("assembly.zoomIn"),
            onclick: () => this._zoom2D(1.15),
        });

        const reset2DButton = button({
            textContent: I18n.translate("assembly.reset2DView"),
            className: `${style.button} ${style.buttonSecondary}`,
            onclick: () => this._reset2DView(),
        });

        const statusBar = div(
            { className: style.statusBar },
            div(
                { className: style.statusItem },
                span({ className: style.statusLabel, textContent: I18n.translate("assembly.status") + ":" }),
                this._statusValue,
            ),
            div(
                { className: style.statusItem },
                span({
                    className: style.statusLabel,
                    textContent: I18n.translate("assembly.selectedFace") + ":",
                }),
                this._selectedFaceValue,
            ),
            div(
                { className: style.statusItem },
                span({
                    className: style.statusLabel,
                    textContent: I18n.translate("assembly.faceCount") + ":",
                }),
                this._faceCountValue,
            ),
        );

        const faceInputGroup = div(
            { className: style.controlGroup },
            span({ className: style.inputLabel, textContent: I18n.translate("assembly.faceNumberInput") }),
            this._faceNumberInput,
            highlightButton,
            clearButton,
        );

        const viewControlGroup = div(
            { className: style.controlGroup },
            reset3DButton,
            zoomOutButton,
            zoomInButton,
            reset2DButton,
        );

        const view3DBody = div({ className: style.viewBody }, this._view3D, this._view3DLoading);

        const view2DBody = div({ className: style.viewBody }, this._view2D, this._view2DLoading);

        this.append(
            div(
                { className: style.root },
                div(
                    { className: style.header },
                    div(
                        { className: style.titleBlock },
                        span({ className: style.title, textContent: I18n.translate("assembly.title") }),
                        span({
                            className: style.subtitle,
                            textContent: I18n.translate("assembly.helpText"),
                        }),
                    ),
                    closeButton,
                ),
                div(
                    { className: style.toolbar },
                    div({ className: style.toolbarLeft }, faceInputGroup, viewControlGroup),
                    span({
                        className: style.toolbarHint,
                        textContent: I18n.translate("assembly.shortcutHint"),
                    }),
                ),
                div(
                    { className: style.content },
                    div(
                        { className: style.viewPanel },
                        div({ className: style.viewHeader }, I18n.translate("assembly.3dModel")),
                        view3DBody,
                    ),
                    div(
                        { className: style.viewPanel },
                        div({ className: style.viewHeader }, I18n.translate("assembly.2dUnfold")),
                        view2DBody,
                    ),
                ),
                statusBar,
            ),
        );
    }

    private _setupEventListeners() {
        PubSub.default.sub(
            "assemblyMode.showPanel",
            async (data: { nodes: ShapeNode[]; stepData: Blob }) => {
                await this._initialize(data);
            },
        );

        this._view3D.addEventListener("click", (event) => {
            this._handle3DClick(event);
        });
    }

    private async _initialize(data: { nodes: ShapeNode[]; stepData: Blob }) {
        this._nodes = data.nodes;

        const existingPanel = document.querySelector("chili-assembly-panel");
        if (existingPanel && existingPanel !== this) {
            existingPanel.remove();
        }

        if (!this.isConnected) {
            document.body.appendChild(this);
        }

        this._attachWindowListeners();
        this._clearSelection();
        this._updateFaceCount(0);
        this._prepareFreshViews();

        this._setLoading(this._view3DLoading, true, "assembly.loadingModel");
        this._setLoading(this._view2DLoading, true, "assembly.loadingUnfold");
        this._setStatus("assembly.loadingModel");

        await this._setup3DView();
        const unfoldReady = await this._generateUnfold(data.stepData);
        if (unfoldReady) {
            this._setStatus("assembly.ready");
        }
    }

    private _prepareFreshViews() {
        this._disposePanzoom();
        this._dispose3DView();

        this._view3D.replaceChildren();
        this._svgContainer.replaceChildren();

        this._faceElementsByNumber.clear();
        this._faceNumberInput.value = "";
    }

    private async _setup3DView() {
        try {
            await new Promise((resolve) => setTimeout(resolve, 0));

            const width = this._view3D.clientWidth || 800;
            const height = this._view3D.clientHeight || 600;

            this._scene = new Scene();

            const aspect = width / height;
            this._camera = new PerspectiveCamera(50, aspect, 0.1, 10000);
            this._camera.position.set(5, 5, 5);

            this._renderer = new WebGLRenderer({ antialias: true, alpha: true });
            this._renderer.setSize(width, height);
            this._renderer.setPixelRatio(window.devicePixelRatio);
            this._view3D.appendChild(this._renderer.domElement);

            this._controls = new OrbitControls(this._camera, this._renderer.domElement);
            this._controls.enableDamping = true;
            this._controls.dampingFactor = 0.06;

            this._scene.add(new AmbientLight(0xffffff, 0.58));
            const directionalLight = new DirectionalLight(0xffffff, 0.82);
            directionalLight.position.set(5, 10, 7.5);
            this._scene.add(directionalLight);

            const boundingBox = new Box3();
            let firstShape: any = null;

            for (const node of this._nodes) {
                const shapeResult = node.shape;
                if (!shapeResult?.isOk) {
                    continue;
                }

                const shape = shapeResult.value;
                if (!firstShape) {
                    firstShape = shape;
                }

                const meshData = shape.mesh;

                if (meshData.faces) {
                    const faceMesh = ThreeGeometryFactory.createFaceGeometry(meshData.faces);
                    this._scene.add(faceMesh);
                    faceMesh.geometry.computeBoundingBox();
                    if (faceMesh.geometry.boundingBox) {
                        boundingBox.union(faceMesh.geometry.boundingBox);
                    }
                }

                if (meshData.edges) {
                    const edgeMesh = ThreeGeometryFactory.createEdgeGeometry(meshData.edges);
                    this._scene.add(edgeMesh);
                }
            }

            if (firstShape) {
                this._faceNumberDisplay = new FaceNumberDisplay();
                this._faceNumberDisplay.generateFromShape(firstShape);
                this._faceNumberDisplay.setVisible(true);
                this._scene.add(this._faceNumberDisplay);
            }

            if (!boundingBox.isEmpty()) {
                const center = boundingBox.getCenter(new Vector3());
                const size = boundingBox.getSize(new Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                const fov = this._camera.fov * (Math.PI / 180);

                let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
                cameraZ *= 1.45;

                this._camera.position.set(center.x + cameraZ, center.y + cameraZ, center.z + cameraZ);
                this._camera.lookAt(center);
                this._controls.target.copy(center);
                this._controls.update();

                this._defaultCameraPosition = this._camera.position.clone();
                this._defaultControlTarget = center.clone();
            }

            this._resizeHandler = () => {
                if (!this._camera || !this._renderer) {
                    return;
                }

                const nextWidth = this._view3D.clientWidth || 800;
                const nextHeight = this._view3D.clientHeight || 600;
                this._camera.aspect = nextWidth / nextHeight;
                this._camera.updateProjectionMatrix();
                this._renderer.setSize(nextWidth, nextHeight);
            };
            window.addEventListener("resize", this._resizeHandler);

            this._animate();
        } catch (error) {
            console.error("Failed to setup 3D view:", error);
            PubSub.default.pub("showToast", "toast.assemblyMode.error");
        } finally {
            this._setLoading(this._view3DLoading, false, "assembly.loadingModel");
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

    private async _generateUnfold(stepData: Blob): Promise<boolean> {
        this._setStatus("assembly.loadingUnfold");

        try {
            const options: UnfoldOptions = {
                scale: 1,
                layoutMode: "paged",
                pageFormat: "A4",
                pageOrientation: "portrait",
                returnFaceNumbers: true,
            };

            const result = await this._service.unfoldStepFromData(stepData, options);
            if (!result.isOk) {
                PubSub.default.pub("showToast", "toast.assemblyMode.unfoldError");
                this._showEmptySVGState(I18n.translate("toast.assemblyMode.unfoldError"));
                this._setStatus("toast.assemblyMode.unfoldError");
                return false;
            }

            const responseData = result.value as {
                svg_content?: string;
                svgContent?: string;
                face_numbers?: FaceNumberData;
                faceNumbers?: FaceNumberData;
            };

            const svgContent = responseData.svg_content ?? responseData.svgContent ?? "";
            if (!svgContent.trim()) {
                this._showEmptySVGState(I18n.translate("toast.assemblyMode.unfoldError"));
                this._setStatus("toast.assemblyMode.unfoldError");
                return false;
            }

            this._displaySVG(svgContent);

            const faceNumbers = responseData.face_numbers ?? responseData.faceNumbers;
            if (faceNumbers && this._faceNumberDisplay) {
                this._faceNumberDisplay.setBackendFaceNumbers(faceNumbers);
            }

            const faceCount = Math.max(
                this._faceElementsByNumber.size,
                this._faceNumberDisplay?.getAllFaceNumbers().length ?? 0,
            );
            this._updateFaceCount(faceCount);
            return true;
        } catch (error) {
            console.error("Error generating unfold:", error);
            PubSub.default.pub("showToast", "toast.assemblyMode.unfoldError");
            this._showEmptySVGState(I18n.translate("toast.assemblyMode.unfoldError"));
            this._setStatus("toast.assemblyMode.unfoldError");
            return false;
        } finally {
            this._setLoading(this._view2DLoading, false, "assembly.loadingUnfold");
        }
    }

    private _displaySVG(svgContent: string) {
        this._svgContainer.replaceChildren();
        this._faceElementsByNumber.clear();

        const wrapper = document.createElement("div");
        wrapper.className = style.svgContent;
        wrapper.innerHTML = svgContent;

        const svg = wrapper.querySelector("svg");
        if (!svg) {
            this._showEmptySVGState(I18n.translate("toast.assemblyMode.unfoldError"));
            return;
        }

        svg.setAttribute("width", "100%");
        svg.setAttribute("height", "100%");
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

        this._svgContainer.appendChild(wrapper);
        this._initializePanZoom(svg);
        this._setupSVGInteraction();
    }

    private _initializePanZoom(svg: SVGElement) {
        this._disposePanzoom();

        this._panzoomInstance = panzoom(svg, {
            maxZoom: 10,
            minZoom: 0.1,
            initialZoom: 1,
            zoomSpeed: 0.1,
            smoothScroll: false,
            bounds: true,
            boundsPadding: 0.15,
            beforeMouseDown: (event) => {
                const target = event.target as Element | null;
                if (!target) {
                    return true;
                }

                return !target.classList.contains(style.interactiveFace);
            },
        });
    }

    private _setupSVGInteraction() {
        const faceSelector =
            "path.face-polygon, path.face-polygon-textured, polygon.face-polygon, polygon.face-polygon-textured";

        let svgFaces = Array.from(this._svgContainer.querySelectorAll<SVGElement>(faceSelector));
        if (svgFaces.length === 0) {
            svgFaces = Array.from(this._svgContainer.querySelectorAll<SVGElement>("[data-face-number]"));
        }

        svgFaces.forEach((element, index) => {
            const faceNumber = this._resolveFaceNumber(element, index);
            element.setAttribute("data-face-number", faceNumber.toString());
            element.classList.add(style.interactiveFace);

            const faces = this._faceElementsByNumber.get(faceNumber) ?? [];
            faces.push(element);
            this._faceElementsByNumber.set(faceNumber, faces);

            element.addEventListener("click", (event) => {
                event.stopPropagation();
                this._handle2DClick(faceNumber);
            });
        });
    }

    private _resolveFaceNumber(element: SVGElement, fallbackIndex: number): number {
        const rawValue = element.getAttribute("data-face-number");
        if (rawValue) {
            const parsed = Number.parseInt(rawValue, 10);
            if (!Number.isNaN(parsed) && parsed > 0) {
                return parsed;
            }
        }

        return fallbackIndex + 1;
    }

    private _handle3DClick(event: MouseEvent) {
        if (!this._scene || !this._camera || !this._faceNumberDisplay) {
            return;
        }

        const rect = this._view3D.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            return;
        }

        this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this._raycaster.setFromCamera(this._mouse, this._camera);
        const intersects = this._raycaster.intersectObjects(this._scene.children, true);
        const faceHit = intersects.find((intersect) => typeof intersect.faceIndex === "number");

        if (!faceHit || faceHit.faceIndex === undefined) {
            return;
        }

        const faceIndex = faceHit.faceIndex;
        if (faceIndex === undefined || faceIndex === null) {
            return;
        }

        const faceNumber = this._faceNumberDisplay.getFaceNumberByIndex(faceIndex);
        if (faceNumber === undefined) {
            return;
        }

        this._highlightFace(faceNumber);
    }

    private _handle2DClick(faceNumber: number) {
        this._highlightFace(faceNumber);
    }

    private _highlightByFaceNumber() {
        const faceNumber = Number.parseInt(this._faceNumberInput.value, 10);
        if (Number.isNaN(faceNumber) || faceNumber < 1) {
            PubSub.default.pub("showToast", "toast.assemblyMode.invalidFaceNumber");
            return;
        }

        this._highlightFace(faceNumber);
    }

    private _highlightFace(faceNumber: number) {
        if (!this._isFaceAvailable(faceNumber)) {
            PubSub.default.pub("showToast", "toast.assemblyMode.faceNotFound:{0}", faceNumber.toString());
            return;
        }

        this._clearHighlights(false);

        if (this._faceNumberDisplay) {
            this._faceNumberDisplay.highlightFace(faceNumber);
        }

        this._highlightSVGFace(faceNumber);
        this._selectedFaceNumber = faceNumber;
        this._selectedFaceValue.textContent = faceNumber.toString();
        this._faceNumberInput.value = faceNumber.toString();
        this._setStatus("assembly.faceSelected:{0}", faceNumber.toString());
    }

    private _highlightSVGFace(faceNumber: number) {
        const elements = this._faceElementsByNumber.get(faceNumber);
        if (!elements || elements.length === 0) {
            return;
        }

        elements.forEach((element) => {
            element.classList.add(style.faceHighlighted);
        });

        elements[0].scrollIntoView({
            behavior: "smooth",
            block: "center",
            inline: "center",
        });
    }

    private _isFaceAvailable(faceNumber: number): boolean {
        if (this._faceElementsByNumber.has(faceNumber)) {
            return true;
        }

        if (!this._faceNumberDisplay) {
            return false;
        }

        return this._faceNumberDisplay.getAllFaceNumbers().includes(faceNumber);
    }

    private _clearSelection() {
        this._clearHighlights();
        this._setStatus("assembly.ready");
    }

    private _clearHighlights(resetSelection: boolean = true) {
        const highlighted = this._svgContainer.querySelectorAll<SVGElement>(`.${style.faceHighlighted}`);
        highlighted.forEach((element) => {
            element.classList.remove(style.faceHighlighted);
        });

        this._faceNumberDisplay?.clearHighlights();

        if (resetSelection) {
            this._selectedFaceNumber = null;
            this._selectedFaceValue.textContent = "-";
            this._faceNumberInput.value = "";
        }
    }

    private _zoom2D(scaleMultiplier: number) {
        if (!this._panzoomInstance) {
            return;
        }

        const rect = this._view2D.getBoundingClientRect();
        this._panzoomInstance.smoothZoom(rect.width / 2, rect.height / 2, scaleMultiplier);
    }

    private _reset2DView() {
        if (!this._panzoomInstance) {
            return;
        }

        const rect = this._view2D.getBoundingClientRect();
        this._panzoomInstance.zoomAbs(rect.width / 2, rect.height / 2, 1);
        this._panzoomInstance.moveTo(0, 0);
    }

    private _reset3DView() {
        if (
            !this._camera ||
            !this._controls ||
            !this._defaultCameraPosition ||
            !this._defaultControlTarget
        ) {
            return;
        }

        this._camera.position.copy(this._defaultCameraPosition);
        this._controls.target.copy(this._defaultControlTarget);
        this._controls.update();
    }

    private _showEmptySVGState(message: string) {
        this._svgContainer.replaceChildren(
            div(
                {
                    className: style.emptyState,
                },
                span({ textContent: message }),
            ),
        );
    }

    private _setStatus(key: I18nKeys, ...args: any[]) {
        this._statusValue.textContent = I18n.translate(key, ...args);
    }

    private _setLoading(target: HTMLDivElement, visible: boolean, messageKey: I18nKeys) {
        target.textContent = I18n.translate(messageKey);
        target.classList.toggle(style.visible, visible);
    }

    private _updateFaceCount(faceCount: number) {
        this._faceCountValue.textContent = faceCount.toString();
    }

    private _attachWindowListeners() {
        if (this._windowKeydownHandler) {
            return;
        }

        this._windowKeydownHandler = (event: KeyboardEvent) => {
            if (!this.isConnected) {
                return;
            }

            if (event.key === "Escape") {
                event.preventDefault();
                this._close();
            }
        };

        window.addEventListener("keydown", this._windowKeydownHandler);
    }

    private _detachWindowListeners() {
        if (!this._windowKeydownHandler) {
            return;
        }

        window.removeEventListener("keydown", this._windowKeydownHandler);
        this._windowKeydownHandler = null;
    }

    private _disposePanzoom() {
        if (!this._panzoomInstance) {
            return;
        }

        this._panzoomInstance.dispose();
        this._panzoomInstance = null;
    }

    private _dispose3DView() {
        if (this._resizeHandler) {
            window.removeEventListener("resize", this._resizeHandler);
            this._resizeHandler = null;
        }

        if (this._animationFrameId !== null) {
            cancelAnimationFrame(this._animationFrameId);
            this._animationFrameId = null;
        }

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
        this._defaultCameraPosition = null;
        this._defaultControlTarget = null;
    }

    private _close() {
        this._clearHighlights();
        this._disposePanzoom();
        this._dispose3DView();
        this._detachWindowListeners();

        this.remove();

        PubSub.default.pub("assemblyMode.closed");
        PubSub.default.pub("showToast", "toast.assemblyMode.closed");
    }

    public static getInstance(): AssemblyPanel | null {
        return AssemblyPanel._instance;
    }
}

customElements.define("chili-assembly-panel", AssemblyPanel);
