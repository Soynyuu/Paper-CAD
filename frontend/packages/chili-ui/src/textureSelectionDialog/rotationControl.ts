// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { div, span } from "chili-controls";
import style from "./rotationControl.module.css";

export interface RotationChangeEvent {
    angle: number; // 0-360 degrees
}

/**
 * Circular rotation control component (PowerPoint-style)
 * Allows users to rotate texture by dragging a handle around a circle
 */
export class RotationControl extends HTMLElement {
    private angle: number = 0;
    private isDragging: boolean = false;
    private centerX: number = 0;
    private centerY: number = 0;
    private radius: number = 60;
    private container!: HTMLDivElement;
    private handle!: HTMLDivElement;
    private angleDisplay!: HTMLSpanElement;
    private circle!: HTMLDivElement;
    private snapToGrid: boolean = false;
    private onChangeCallback?: (angle: number) => void;

    constructor() {
        super();
        this.render();
        this.setupEventListeners();
    }

    /**
     * Set the current rotation angle
     */
    public setAngle(angle: number) {
        this.angle = this.normalizeAngle(angle);
        this.updateDisplay();
    }

    /**
     * Get the current rotation angle
     */
    public getAngle(): number {
        return this.angle;
    }

    /**
     * Set callback for angle changes
     */
    public onChange(callback: (angle: number) => void) {
        this.onChangeCallback = callback;
    }

    private render() {
        this.container = div({ className: style.rotationControl });

        // Circle background
        this.circle = div({ className: style.circle });

        // Center dot
        const centerDot = div({ className: style.centerDot });

        // Rotation handle
        this.handle = div({ className: style.handle });

        // Angle display
        this.angleDisplay = span({
            className: style.angleDisplay,
            textContent: "0°",
        });

        // Instruction text
        const instruction = span({
            className: style.instruction,
            textContent: "Drag to rotate • Shift for 15° snap",
        });

        this.circle.appendChild(centerDot);
        this.circle.appendChild(this.handle);
        this.container.appendChild(this.circle);
        this.container.appendChild(this.angleDisplay);
        this.container.appendChild(instruction);

        this.appendChild(this.container);

        // Update initial position
        this.updateHandlePosition();
    }

    private setupEventListeners() {
        // Mouse events
        this.handle.addEventListener("mousedown", this.onDragStart.bind(this));
        document.addEventListener("mousemove", this.onDragMove.bind(this));
        document.addEventListener("mouseup", this.onDragEnd.bind(this));

        // Touch events for mobile
        this.handle.addEventListener("touchstart", this.onDragStart.bind(this), { passive: false });
        document.addEventListener("touchmove", this.onDragMove.bind(this), { passive: false });
        document.addEventListener("touchend", this.onDragEnd.bind(this));

        // Keyboard support for Shift key (snap to grid)
        document.addEventListener("keydown", (e) => {
            if (e.key === "Shift") {
                this.snapToGrid = true;
            }
        });
        document.addEventListener("keyup", (e) => {
            if (e.key === "Shift") {
                this.snapToGrid = false;
            }
        });

        // Double-click to reset
        this.circle.addEventListener("dblclick", () => {
            this.setAngle(0);
            this.notifyChange();
        });

        // Update center position on resize
        window.addEventListener("resize", () => this.updateCenterPosition());
    }

    private onDragStart(e: MouseEvent | TouchEvent) {
        e.preventDefault();
        this.isDragging = true;
        this.handle.classList.add(style.dragging);
        this.updateCenterPosition();
    }

    private onDragMove(e: MouseEvent | TouchEvent) {
        if (!this.isDragging) return;

        e.preventDefault();

        // Get mouse/touch position
        const clientX = e instanceof MouseEvent ? e.clientX : e.touches[0].clientX;
        const clientY = e instanceof MouseEvent ? e.clientY : e.touches[0].clientY;

        // Calculate angle from center
        const dx = clientX - this.centerX;
        const dy = clientY - this.centerY;
        let angle = Math.atan2(dy, dx) * (180 / Math.PI);

        // Convert from [-180, 180] to [0, 360] and rotate to start from top
        angle = (angle + 90 + 360) % 360;

        // Apply snap if Shift is pressed
        if (this.snapToGrid) {
            angle = Math.round(angle / 15) * 15;
        }

        this.angle = angle;
        this.updateDisplay();
        this.notifyChange();
    }

    private onDragEnd(e: MouseEvent | TouchEvent) {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.handle.classList.remove(style.dragging);
    }

    private updateCenterPosition() {
        const rect = this.circle.getBoundingClientRect();
        this.centerX = rect.left + rect.width / 2;
        this.centerY = rect.top + rect.height / 2;
    }

    private updateDisplay() {
        this.updateHandlePosition();
        this.angleDisplay.textContent = `${Math.round(this.angle)}°`;
    }

    private updateHandlePosition() {
        // Convert angle to radians (subtract 90 to start from top)
        const radians = ((this.angle - 90) * Math.PI) / 180;

        // Calculate handle position on circle
        const x = Math.cos(radians) * this.radius;
        const y = Math.sin(radians) * this.radius;

        // Apply transform
        this.handle.style.transform = `translate(${x}px, ${y}px)`;
    }

    private normalizeAngle(angle: number): number {
        return ((angle % 360) + 360) % 360;
    }

    private notifyChange() {
        // Dispatch custom event
        const event = new CustomEvent<RotationChangeEvent>("rotationchange", {
            detail: { angle: this.angle },
            bubbles: true,
        });
        this.dispatchEvent(event);

        // Call callback if set
        if (this.onChangeCallback) {
            this.onChangeCallback(this.angle);
        }
    }

    // Clean up event listeners when element is removed
    disconnectedCallback() {
        document.removeEventListener("mousemove", this.onDragMove.bind(this));
        document.removeEventListener("mouseup", this.onDragEnd.bind(this));
        document.removeEventListener("touchmove", this.onDragMove.bind(this));
        document.removeEventListener("touchend", this.onDragEnd.bind(this));
    }
}

// Register custom element
customElements.define("rotation-control", RotationControl);
