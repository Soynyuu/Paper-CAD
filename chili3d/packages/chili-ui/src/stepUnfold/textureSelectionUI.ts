// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, img, select, option, span } from "chili-controls";
import { I18n } from "chili-core";
import { TexturePatternManager, TexturePattern } from "./texturePatternManager";
import style from "./textureSelectionUI.module.css";

export interface TextureSelectionOptions {
    onPatternSelected?: (patternId: string) => void;
    onPatternApplied?: (elementId: string, patternId: string) => void;
    onPatternRemoved?: (elementId: string) => void;
}

/**
 * UI component for texture pattern selection
 */
export class TextureSelectionUI extends HTMLElement {
    private patternManager: TexturePatternManager;
    private selectedPatternId: string | null = null;
    private selectedElements: Set<string> = new Set();
    private patternSelector: HTMLSelectElement;
    private previewContainer: HTMLDivElement;
    private applyButton: HTMLButtonElement;
    private clearButton: HTMLButtonElement;
    private options: TextureSelectionOptions;

    constructor(options: TextureSelectionOptions = {}) {
        super();
        this.options = options;
        this.patternManager = new TexturePatternManager();

        // Create UI elements
        this.patternSelector = this.createPatternSelector();
        this.previewContainer = this.createPreviewContainer();
        this.applyButton = this.createApplyButton();
        this.clearButton = this.createClearButton();

        this.render();
        this.setupEventListeners();

        // Load patterns after a short delay to ensure UI is ready
        setTimeout(() => this.loadPatterns(), 100);
    }

    private render() {
        this.className = style.root;

        const selectorContainer = div(
            { className: style.selectorContainer },
            span({
                className: style.label,
                textContent: I18n.translate("stepUnfold.texturePattern") || "テクスチャパターン",
            }),
            this.patternSelector,
        );

        const buttonContainer = div(
            { className: style.buttonContainer },
            this.applyButton,
            this.clearButton,
        );

        this.append(
            div(
                { className: style.container },
                div(
                    { className: style.header },
                    span({
                        className: style.title,
                        textContent:
                            "🎨 " + (I18n.translate("stepUnfold.textureSelection") || "テクスチャ選択"),
                    }),
                ),
                selectorContainer,
                this.previewContainer,
                buttonContainer,
            ),
        );
    }

    private createPatternSelector(): HTMLSelectElement {
        return select(
            { className: style.selector },
            option({
                value: "",
                textContent: I18n.translate("stepUnfold.selectPattern") || "パターンを選択...",
            }),
        );
    }

    private createPreviewContainer(): HTMLDivElement {
        return div(
            { className: style.preview },
            div({
                className: style.previewPlaceholder,
                textContent:
                    I18n.translate("stepUnfold.noPatternSelected") || "パターンが選択されていません",
            }),
        );
    }

    private createApplyButton(): HTMLButtonElement {
        return button({
            className: style.applyButton,
            textContent: "✓ " + (I18n.translate("stepUnfold.applyTexture") || "適用"),
            disabled: true,
        });
    }

    private createClearButton(): HTMLButtonElement {
        return button({
            className: style.clearButton,
            textContent: "✗ " + (I18n.translate("stepUnfold.clearTexture") || "クリア"),
            disabled: true,
        });
    }

    private async loadPatterns() {
        // Wait a bit for pattern manager to load its data
        await new Promise((resolve) => setTimeout(resolve, 500));

        const patterns = this.patternManager.getPatterns();
        const categories = this.patternManager.getCategories();

        // Clear existing options except the placeholder
        while (this.patternSelector.options.length > 1) {
            this.patternSelector.remove(1);
        }

        // Group patterns by category
        const patternsByCategory = new Map<string, TexturePattern[]>();
        patterns.forEach((pattern) => {
            if (!patternsByCategory.has(pattern.category)) {
                patternsByCategory.set(pattern.category, []);
            }
            patternsByCategory.get(pattern.category)!.push(pattern);
        });

        // Add patterns to selector grouped by category
        patternsByCategory.forEach((categoryPatterns, categoryId) => {
            const category = categories.find((cat) =>
                Object.entries(this.patternManager.getCategories()).some(
                    ([key, val]) => key === categoryId && val === cat,
                ),
            );

            if (categoryPatterns.length > 0) {
                // Add category as optgroup
                const optGroup = document.createElement("optgroup");
                const categoryName = this.getCategoryName(categoryId);
                optGroup.label = categoryName;

                categoryPatterns.forEach((pattern) => {
                    const opt = option({
                        value: pattern.id,
                        textContent: this.patternManager.getPatternName(pattern.id),
                    });
                    optGroup.appendChild(opt);
                });

                this.patternSelector.appendChild(optGroup);
            }
        });
    }

    private getCategoryName(categoryId: string): string {
        const categories = this.patternManager.getCategories();
        const category = categories.find((cat) => cat === categoryId);
        if (!category) return categoryId;

        const isJapanese = I18n.currentLanguage === "ja-jp" || I18n.currentLanguage === "zh-cn";
        return isJapanese ? category.name : category.nameEn;
    }

    private setupEventListeners() {
        // Pattern selection change
        this.patternSelector.addEventListener("change", () => {
            this.selectedPatternId = this.patternSelector.value || null;
            this.updatePreview();
            this.updateButtonStates();

            if (this.selectedPatternId && this.options.onPatternSelected) {
                this.options.onPatternSelected(this.selectedPatternId);
            }
        });

        // Apply button click
        this.applyButton.addEventListener("click", () => {
            if (this.selectedPatternId) {
                this.applyPatternToSelection();
            }
        });

        // Clear button click
        this.clearButton.addEventListener("click", () => {
            this.clearPatternFromSelection();
        });
    }

    private updatePreview() {
        this.previewContainer.innerHTML = "";

        if (!this.selectedPatternId) {
            this.previewContainer.appendChild(
                div({
                    className: style.previewPlaceholder,
                    textContent:
                        I18n.translate("stepUnfold.noPatternSelected") || "パターンが選択されていません",
                }),
            );
            return;
        }

        const pattern = this.patternManager.getPattern(this.selectedPatternId);
        if (!pattern) return;

        const previewContent = div({ className: style.previewContent });

        // Add pattern image preview if available
        if (pattern.image) {
            const imagePreview = div({ className: style.imagePreview });
            imagePreview.style.backgroundImage = `url(/textures/${pattern.image})`;
            imagePreview.style.backgroundSize = "cover";
            imagePreview.style.backgroundRepeat = "repeat";
            previewContent.appendChild(imagePreview);
        }

        // Add pattern info
        const info = div(
            { className: style.patternInfo },
            div(
                { className: style.patternName },
                this.patternManager.getPatternName(this.selectedPatternId),
            ),
            div(
                { className: style.patternDescription },
                this.patternManager.getPatternDescription(this.selectedPatternId),
            ),
        );

        previewContent.appendChild(info);
        this.previewContainer.appendChild(previewContent);
    }

    private updateButtonStates() {
        this.applyButton.disabled = !this.selectedPatternId || this.selectedElements.size === 0;
        this.clearButton.disabled = this.selectedElements.size === 0;
    }

    /**
     * Set the selected elements for texture application
     */
    public setSelectedElements(elementIds: string[]) {
        this.selectedElements = new Set(elementIds);
        this.updateButtonStates();
    }

    /**
     * Apply pattern to selected elements
     */
    private async applyPatternToSelection() {
        if (!this.selectedPatternId) return;

        for (const elementId of this.selectedElements) {
            // This would be called by the parent component with actual SVG elements
            if (this.options.onPatternApplied) {
                this.options.onPatternApplied(elementId, this.selectedPatternId);
            }
        }

        // Show success feedback
        this.showFeedback(I18n.translate("stepUnfold.textureApplied") || "テクスチャを適用しました");
    }

    /**
     * Clear pattern from selected elements
     */
    private clearPatternFromSelection() {
        for (const elementId of this.selectedElements) {
            if (this.options.onPatternRemoved) {
                this.options.onPatternRemoved(elementId);
            }
        }

        // Show success feedback
        this.showFeedback(I18n.translate("stepUnfold.textureCleared") || "テクスチャをクリアしました");
    }

    /**
     * Show temporary feedback message
     */
    private showFeedback(message: string) {
        const feedback = div({
            className: style.feedback,
            textContent: "✓ " + message,
        });

        this.append(feedback);

        setTimeout(() => {
            feedback.style.opacity = "0";
            setTimeout(() => feedback.remove(), 300);
        }, 2000);
    }

    /**
     * Get the pattern manager instance
     */
    public getPatternManager(): TexturePatternManager {
        return this.patternManager;
    }

    /**
     * Refresh the pattern list
     */
    public async refresh() {
        await this.loadPatterns();
        this.updatePreview();
    }
}

// Register the custom element
customElements.define("texture-selection-ui", TextureSelectionUI);
