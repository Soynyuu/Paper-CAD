// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { div } from "chili-controls";
import style from "./resizablePanels.module.css";

export interface ResizablePanelsProps {
    leftPanel: HTMLElement;
    rightPanel: HTMLElement;
    initialLeftWidth?: number;
    minLeftWidth?: number;
    maxLeftWidth?: number;
    className?: string;
    storageKey?: string;
}

export class ResizablePanels extends HTMLElement {
    private readonly _leftPanel: HTMLElement;
    private readonly _rightPanel: HTMLElement;
    private readonly _resizer: HTMLDivElement;
    private _isResizing = false;
    private _startX = 0;
    private _startLeftWidth = 0;
    private _minLeftWidth: number;
    private _maxLeftWidth: number;
    private readonly _storageKey: string;

    constructor(props: ResizablePanelsProps) {
        super();

        this._leftPanel = props.leftPanel;
        this._rightPanel = props.rightPanel;
        this._minLeftWidth = props.minLeftWidth || 300;
        this._maxLeftWidth = props.maxLeftWidth || 800;
        this._storageKey = `resizable-panels-${props.storageKey || "default"}`;

        if (props.className) {
            this.className = props.className;
        }

        this._resizer = div({
            className: style.resizer,
        });

        this._leftPanel.classList.add(style.leftPanel);
        this._rightPanel.classList.add(style.rightPanel);

        // 保存された幅を復元、または初期幅を使用
        const savedWidth = this._loadWidth();
        const initialWidth = savedWidth || props.initialLeftWidth || 400;
        this._leftPanel.style.width = `${initialWidth}px`;
        this._rightPanel.style.width = `calc(100% - ${initialWidth}px - 4px)`;

        this._render();
        this._bindEvents();
    }

    private _render() {
        this.className = `${this.className} ${style.container}`;
        this.append(this._leftPanel, this._resizer, this._rightPanel);
    }

    private _bindEvents() {
        this._resizer.addEventListener("mousedown", this._handleMouseDown.bind(this));
        document.addEventListener("mousemove", this._handleMouseMove.bind(this));
        document.addEventListener("mouseup", this._handleMouseUp.bind(this));
    }

    private _handleMouseDown(e: MouseEvent) {
        e.preventDefault();
        this._isResizing = true;
        this._startX = e.clientX;
        this._startLeftWidth = this._leftPanel.offsetWidth;

        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        this._resizer.classList.add(style.resizing);
    }

    private _handleMouseMove(e: MouseEvent) {
        if (!this._isResizing) return;

        e.preventDefault();
        const deltaX = e.clientX - this._startX;
        const newLeftWidth = this._startLeftWidth + deltaX;

        // 最小・最大幅制限を適用
        const clampedWidth = Math.max(this._minLeftWidth, Math.min(this._maxLeftWidth, newLeftWidth));

        this._leftPanel.style.width = `${clampedWidth}px`;
        this._rightPanel.style.width = `calc(100% - ${clampedWidth}px - 4px)`;

        // 幅をローカルストレージに保存
        this._saveWidth(clampedWidth);
    }

    private _handleMouseUp() {
        if (!this._isResizing) return;

        this._isResizing = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";

        this._resizer.classList.remove(style.resizing);
    }

    private _loadWidth(): number | null {
        try {
            const saved = localStorage.getItem(this._storageKey);
            return saved ? parseInt(saved, 10) : null;
        } catch {
            return null;
        }
    }

    private _saveWidth(width: number): void {
        try {
            localStorage.setItem(this._storageKey, width.toString());
        } catch {
            // ローカルストレージが使用できない場合は無視
        }
    }

    public setLeftWidth(width: number) {
        const clampedWidth = Math.max(this._minLeftWidth, Math.min(this._maxLeftWidth, width));

        this._leftPanel.style.width = `${clampedWidth}px`;
        this._rightPanel.style.width = `calc(100% - ${clampedWidth}px - 4px)`;

        // 幅をローカルストレージに保存
        this._saveWidth(clampedWidth);
    }

    public getLeftWidth(): number {
        return this._leftPanel.offsetWidth;
    }

    public setMinMaxWidth(min: number, max: number) {
        this._minLeftWidth = min;
        this._maxLeftWidth = max;
    }

    disconnectedCallback() {
        document.removeEventListener("mousemove", this._handleMouseMove.bind(this));
        document.removeEventListener("mouseup", this._handleMouseUp.bind(this));
    }
}

customElements.define("chili-resizable-panels", ResizablePanels);
