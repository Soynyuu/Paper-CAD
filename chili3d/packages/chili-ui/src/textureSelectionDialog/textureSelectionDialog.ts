// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, img, input, label, option, select, span } from "chili-controls";
import { I18n } from "chili-core";
import { TexturePatternManager, TexturePattern } from "../stepUnfold/texturePatternManager";
import style from "./textureSelectionDialog.module.css";

export interface TextureSelectionResult {
    patternId: string;
    tileCount: number;
    confirmed: boolean;
}

/**
 * Modal dialog for texture pattern selection and configuration
 */
export class TextureSelectionDialog extends HTMLElement {
    private patternManager: TexturePatternManager;
    private selectedPatternId: string = "grass";
    private tileCount: number = 5;
    private patternSelector!: HTMLSelectElement;
    private previewContainer!: HTMLDivElement;
    private tileCountInput!: HTMLInputElement;
    private tileCountLabel!: HTMLSpanElement;
    private applyButton!: HTMLButtonElement;
    private cancelButton!: HTMLButtonElement;
    private dialog!: HTMLDialogElement;
    private resolvePromise?: (result: TextureSelectionResult) => void;

    constructor() {
        super();
        this.patternManager = new TexturePatternManager();
        this.render();
        this.setupEventListeners();
        this.loadPatterns();
    }

    /**
     * Show the dialog and return a promise with the result
     */
    public show(): Promise<TextureSelectionResult> {
        return new Promise((resolve) => {
            this.resolvePromise = resolve;
            this.dialog.showModal();
            document.body.appendChild(this.dialog);
        });
    }

    private render() {
        // Create dialog element
        this.dialog = document.createElement("dialog");
        this.dialog.style.cssText = `
            padding: 20px;
            border: 1px solid #333;
            border-radius: 8px;
            background-color: #2b2b2b;
            color: #e0e0e0;
            min-width: 400px;
            max-width: 600px;
        `;

        const container = div({ className: style.container });

        // Title
        const title = div({
            className: style.title,
            textContent: I18n.translate("texture.selection.title") || "テクスチャー選択",
        });
        container.appendChild(title);

        // Pattern selection
        const patternSection = div({ className: style.section });
        patternSection.appendChild(
            label({
                className: style.label,
                textContent: I18n.translate("texture.pattern") || "パターン:",
            }),
        );

        this.patternSelector = select({
            className: style.patternSelect,
            onchange: this.onPatternChange.bind(this),
        });
        patternSection.appendChild(this.patternSelector);
        container.appendChild(patternSection);

        // Preview section
        const previewSection = div({ className: style.section });
        previewSection.appendChild(
            label({
                className: style.label,
                textContent: I18n.translate("texture.preview") || "プレビュー:",
            }),
        );

        this.previewContainer = div({ className: style.previewContainer });
        previewSection.appendChild(this.previewContainer);
        container.appendChild(previewSection);

        // Tile count section
        const tileSection = div({ className: style.section });
        tileSection.appendChild(
            label({
                className: style.label,
                textContent: I18n.translate("texture.tileCount") || "タイル数:",
            }),
        );

        const tileControls = div({ className: style.tileControls });

        this.tileCountInput = input({
            type: "range",
            min: "1",
            max: "10",
            value: this.tileCount.toString(),
            className: style.tileSlider,
            oninput: this.onTileCountChange.bind(this),
        });

        this.tileCountLabel = span({
            className: style.tileLabel,
            textContent: this.tileCount.toString(),
        });

        tileControls.appendChild(this.tileCountInput);
        tileControls.appendChild(this.tileCountLabel);
        tileSection.appendChild(tileControls);
        container.appendChild(tileSection);

        // Buttons
        const buttonSection = div({ className: style.buttonSection });

        this.cancelButton = button({
            className: style.button + " " + style.buttonSecondary,
            textContent: I18n.translate("common.cancel") || "キャンセル",
            onclick: this.onCancel.bind(this),
        });

        this.applyButton = button({
            className: style.button + " " + style.buttonPrimary,
            textContent: I18n.translate("common.confirm") || "適用",
            onclick: this.onApply.bind(this),
        });

        buttonSection.appendChild(this.cancelButton);
        buttonSection.appendChild(this.applyButton);
        container.appendChild(buttonSection);

        // Close button (X)
        const closeButton = button({
            className: style.closeButton,
            textContent: "✕",
            onclick: this.onCancel.bind(this),
        });

        this.dialog.appendChild(container);
        this.dialog.appendChild(closeButton);
    }

    private setupEventListeners() {
        // Close on click outside
        this.dialog.addEventListener("click", (e) => {
            if (e.target === this.dialog) {
                this.onCancel();
            }
        });

        // Close on escape key
        this.dialog.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                this.onCancel();
            }
        });

        // Close event cleanup
        this.dialog.addEventListener("close", () => {
            this.dialog.remove();
        });
    }

    private async loadPatterns() {
        try {
            // TexturePatternManager loads patterns in constructor automatically
            // Wait a bit for async loading to complete
            await new Promise((resolve) => setTimeout(resolve, 100));
            this.populatePatternSelector();
            this.updatePreview();
        } catch (error) {
            console.error("Failed to load texture patterns:", error);
        }
    }

    private populatePatternSelector() {
        // Clear existing options
        while (this.patternSelector.firstChild) {
            this.patternSelector.removeChild(this.patternSelector.firstChild);
        }

        const patterns = this.patternManager.getPatterns();
        patterns.forEach((pattern: TexturePattern) => {
            const opt = option({
                value: pattern.id,
                textContent: pattern.name,
                selected: pattern.id === this.selectedPatternId,
            });
            this.patternSelector.appendChild(opt);
        });
    }

    private onPatternChange(event: Event) {
        const select = event.target as HTMLSelectElement;
        this.selectedPatternId = select.value;
        this.updatePreview();
    }

    private onTileCountChange(event: Event) {
        const input = event.target as HTMLInputElement;
        this.tileCount = parseInt(input.value);
        this.tileCountLabel.textContent = this.tileCount.toString();
        this.updatePreview();
    }

    private updatePreview() {
        // Clear previous preview
        while (this.previewContainer.firstChild) {
            this.previewContainer.removeChild(this.previewContainer.firstChild);
        }

        const pattern = this.patternManager.getPattern(this.selectedPatternId);
        if (pattern && pattern.image) {
            const previewImg = img({
                src: `/textures/${pattern.image}`,
                className: style.previewImage,
                alt: pattern.name,
            });

            // Add tiling preview effect
            previewImg.style.cssText = `
                width: 200px;
                height: 200px;
                object-fit: repeat;
                background-repeat: repeat;
                background-size: ${200 / this.tileCount}px ${200 / this.tileCount}px;
                background-image: url(/textures/${pattern.image});
            `;

            this.previewContainer.appendChild(previewImg);
        }
    }

    private onApply() {
        if (this.resolvePromise) {
            this.resolvePromise({
                patternId: this.selectedPatternId,
                tileCount: this.tileCount,
                confirmed: true,
            });
        }
        this.dialog.close();
    }

    private onCancel() {
        if (this.resolvePromise) {
            this.resolvePromise({
                patternId: this.selectedPatternId,
                tileCount: this.tileCount,
                confirmed: false,
            });
        }
        this.dialog.close();
    }
}

// Register custom element
customElements.define("texture-selection-dialog", TextureSelectionDialog);
