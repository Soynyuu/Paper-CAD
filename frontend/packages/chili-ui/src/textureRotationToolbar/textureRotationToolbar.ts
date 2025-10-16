// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, span } from "chili-controls";
import { RotationControl } from "../textureSelectionDialog/rotationControl";
import style from "./textureRotationToolbar.module.css";

export interface TextureRotationResult {
    rotation: number;
    confirmed: boolean;
}

/**
 * Floating toolbar for real-time texture rotation editing on 3D models
 * Appears as an overlay on the 3D view
 */
export class TextureRotationToolbar extends HTMLElement {
    private rotation: number = 0;
    private initialRotation: number = 0;
    private rotationControl!: RotationControl;
    private rotationSlider!: HTMLInputElement;
    private rotationInput!: HTMLInputElement;
    private confirmButton!: HTMLButtonElement;
    private cancelButton!: HTMLButtonElement;
    private toolbar!: HTMLDivElement;
    private header!: HTMLDivElement;
    private resolvePromise?: (result: TextureRotationResult) => void;
    private isDragging: boolean = false;
    private dragStartX: number = 0;
    private dragStartY: number = 0;
    private toolbarStartX: number = 0;
    private toolbarStartY: number = 0;
    private onChangeCallback?: (rotation: number) => void;

    constructor() {
        super();
        this.render();
        this.setupEventListeners();
    }

    /**
     * Show the toolbar and return a promise with the result
     */
    public show(initialRotation: number = 0): Promise<TextureRotationResult> {
        this.rotation = initialRotation;
        this.initialRotation = initialRotation;
        this.updateAllControls();

        return new Promise((resolve) => {
            this.resolvePromise = resolve;
            document.body.appendChild(this.toolbar);
            this.centerToolbar();
        });
    }

    /**
     * Set callback for real-time rotation changes
     */
    public onChange(callback: (rotation: number) => void) {
        this.onChangeCallback = callback;
    }

    /**
     * Hide the toolbar
     */
    public hide() {
        if (this.toolbar.parentElement) {
            this.toolbar.remove();
        }
    }

    private render() {
        // Create floating toolbar
        this.toolbar = div({ className: style.toolbar });

        // Header with drag handle and close button
        this.header = div({ className: style.header });

        const dragHandle = div({
            className: style.dragHandle,
            textContent: "⋮⋮ テクスチャ回転",
        });
        this.header.appendChild(dragHandle);

        const closeButton = button({
            className: style.closeButton,
            textContent: "✕",
            onclick: () => this.onCancel(),
        });
        this.header.appendChild(closeButton);

        this.toolbar.appendChild(this.header);

        // Content area
        const content = div({ className: style.content });

        // Circular rotation control
        this.rotationControl = new RotationControl();
        this.rotationControl.onChange((angle) => {
            this.rotation = angle;
            this.rotationSlider.value = angle.toString();
            this.rotationInput.value = Math.round(angle).toString();
            this.notifyChange();
        });
        content.appendChild(this.rotationControl);

        // Preset buttons
        const presetButtons = div({ className: style.presetButtons });
        const presetAngles = [0, 45, 90, 135, 180];
        presetAngles.forEach((angle) => {
            const btn = button({
                className: style.presetButton,
                textContent: `${angle}°`,
                onclick: () => this.setRotation(angle),
            });
            presetButtons.appendChild(btn);
        });
        content.appendChild(presetButtons);

        // Fine-tune controls
        const finetuneControls = div({ className: style.finetuneControls });

        this.rotationSlider = input({
            type: "range",
            min: "0",
            max: "360",
            value: "0",
            step: "1",
            className: style.rotationSlider,
            oninput: this.onRotationSliderChange.bind(this),
        });

        this.rotationInput = input({
            type: "number",
            min: "0",
            max: "360",
            value: "0",
            className: style.rotationInput,
            oninput: this.onRotationInputChange.bind(this),
        });

        const degreeLabel = span({
            className: style.degreeLabel,
            textContent: "°",
        });

        finetuneControls.appendChild(this.rotationSlider);
        finetuneControls.appendChild(this.rotationInput);
        finetuneControls.appendChild(degreeLabel);
        content.appendChild(finetuneControls);

        this.toolbar.appendChild(content);

        // Action buttons
        const actions = div({ className: style.actions });

        this.cancelButton = button({
            className: style.button + " " + style.buttonCancel,
            textContent: "✕ キャンセル",
            onclick: () => this.onCancel(),
        });

        this.confirmButton = button({
            className: style.button + " " + style.buttonConfirm,
            textContent: "✓ 確定",
            onclick: () => this.onConfirm(),
        });

        actions.appendChild(this.cancelButton);
        actions.appendChild(this.confirmButton);
        this.toolbar.appendChild(actions);

        this.appendChild(this.toolbar);
    }

    private setupEventListeners() {
        // Dragging functionality
        this.header.addEventListener("mousedown", this.onDragStart.bind(this));
        document.addEventListener("mousemove", this.onDrag.bind(this));
        document.addEventListener("mouseup", this.onDragEnd.bind(this));

        // Keyboard shortcuts
        document.addEventListener("keydown", this.onKeyDown.bind(this));
    }

    private onDragStart(e: MouseEvent) {
        // Only drag from the drag handle area
        const target = e.target as HTMLElement;
        if (!target.classList.contains(style.dragHandle)) {
            return;
        }

        this.isDragging = true;
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;

        const rect = this.toolbar.getBoundingClientRect();
        this.toolbarStartX = rect.left;
        this.toolbarStartY = rect.top;

        this.toolbar.classList.add(style.dragging);
        e.preventDefault();
    }

    private onDrag(e: MouseEvent) {
        if (!this.isDragging) return;

        const deltaX = e.clientX - this.dragStartX;
        const deltaY = e.clientY - this.dragStartY;

        const newX = this.toolbarStartX + deltaX;
        const newY = this.toolbarStartY + deltaY;

        this.toolbar.style.left = `${newX}px`;
        this.toolbar.style.top = `${newY}px`;
    }

    private onDragEnd() {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.toolbar.classList.remove(style.dragging);
    }

    private onKeyDown(e: KeyboardEvent) {
        // Only handle if toolbar is visible
        if (!this.toolbar.parentElement) return;

        if (e.key === "Escape") {
            e.preventDefault();
            this.onCancel();
        } else if (e.key === "Enter" && !e.isComposing) {
            e.preventDefault();
            this.onConfirm();
        }
    }

    private centerToolbar() {
        const rect = this.toolbar.getBoundingClientRect();
        const x = (window.innerWidth - rect.width) / 2;
        const y = Math.max(20, (window.innerHeight - rect.height) / 3); // Upper third

        this.toolbar.style.left = `${x}px`;
        this.toolbar.style.top = `${y}px`;
    }

    private setRotation(angle: number) {
        this.rotation = angle;
        this.updateAllControls();
        this.notifyChange();
    }

    private onRotationSliderChange(event: Event) {
        const input = event.target as HTMLInputElement;
        const angle = parseFloat(input.value);
        this.rotation = angle;
        this.rotationControl.setAngle(angle);
        this.rotationInput.value = Math.round(angle).toString();
        this.notifyChange();
    }

    private onRotationInputChange(event: Event) {
        const input = event.target as HTMLInputElement;
        let angle = parseFloat(input.value) || 0;
        // Clamp to 0-360
        angle = ((angle % 360) + 360) % 360;
        this.rotation = angle;
        this.rotationControl.setAngle(angle);
        this.rotationSlider.value = angle.toString();
        this.notifyChange();
    }

    private updateAllControls() {
        this.rotationControl.setAngle(this.rotation);
        this.rotationSlider.value = this.rotation.toString();
        this.rotationInput.value = Math.round(this.rotation).toString();
    }

    private notifyChange() {
        if (this.onChangeCallback) {
            this.onChangeCallback(this.rotation);
        }
    }

    private onConfirm() {
        if (this.resolvePromise) {
            this.resolvePromise({
                rotation: this.rotation,
                confirmed: true,
            });
        }
        this.hide();
    }

    private onCancel() {
        // Restore initial rotation before canceling
        if (this.onChangeCallback) {
            this.onChangeCallback(this.initialRotation);
        }

        if (this.resolvePromise) {
            this.resolvePromise({
                rotation: this.initialRotation,
                confirmed: false,
            });
        }
        this.hide();
    }

    // Clean up event listeners when element is removed
    disconnectedCallback() {
        document.removeEventListener("mousemove", this.onDrag.bind(this));
        document.removeEventListener("mouseup", this.onDragEnd.bind(this));
        document.removeEventListener("keydown", this.onKeyDown.bind(this));
    }
}

// Register custom element
customElements.define("texture-rotation-toolbar", TextureRotationToolbar);
