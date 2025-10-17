// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { I18n } from "chili-core";

export interface TexturePattern {
    id: string;
    name: string;
    nameEn: string;
    description: string;
    descriptionEn: string;
    image: string | null;
    scale: number;
    category: string;
    rotation?: number; // Optional rotation angle in degrees (0-360)
    svgPattern: {
        width: number;
        height: number;
        patternUnits: string;
    };
}

export interface PatternCategory {
    name: string;
    nameEn: string;
    icon: string;
}

export interface PatternConfig {
    patterns: TexturePattern[];
    categories: Record<string, PatternCategory>;
    defaultPattern: string;
    version: string;
}

/**
 * Manages texture patterns for SVG fill operations
 */
export class TexturePatternManager {
    private patterns: Map<string, TexturePattern> = new Map();
    private categories: Map<string, PatternCategory> = new Map();
    private loadedPatterns: Set<string> = new Set();
    private defaultPatternId: string = "paper";
    private svgDefsElement: SVGDefsElement | null = null;

    constructor() {
        this.loadPatterns();
    }

    /**
     * Load pattern definitions from JSON config
     */
    private async loadPatterns(): Promise<void> {
        try {
            const response = await fetch("/textures/patterns.json");
            if (!response.ok) {
                console.warn("Failed to load texture patterns config");
                return;
            }

            const config: PatternConfig = await response.json();

            // Store patterns
            config.patterns.forEach((pattern) => {
                this.patterns.set(pattern.id, pattern);
            });

            // Store categories
            Object.entries(config.categories).forEach(([key, category]) => {
                this.categories.set(key, category);
            });

            this.defaultPatternId = config.defaultPattern;
            console.log(`Loaded ${this.patterns.size} texture patterns`);
        } catch (error) {
            console.error("Error loading texture patterns:", error);
        }
    }

    /**
     * Get all available patterns
     */
    public getPatterns(): TexturePattern[] {
        return Array.from(this.patterns.values());
    }

    /**
     * Get patterns by category
     */
    public getPatternsByCategory(categoryId: string): TexturePattern[] {
        return Array.from(this.patterns.values()).filter((pattern) => pattern.category === categoryId);
    }

    /**
     * Get all categories
     */
    public getCategories(): PatternCategory[] {
        return Array.from(this.categories.values());
    }

    /**
     * Get a specific pattern by ID
     */
    public getPattern(patternId: string): TexturePattern | undefined {
        return this.patterns.get(patternId);
    }

    /**
     * Initialize SVG defs element for pattern storage
     */
    public initializeSvgDefs(svgRoot: SVGSVGElement): void {
        // Find or create defs element
        this.svgDefsElement = svgRoot.querySelector("defs") as SVGDefsElement;
        if (!this.svgDefsElement) {
            this.svgDefsElement = document.createElementNS("http://www.w3.org/2000/svg", "defs");
            svgRoot.insertBefore(this.svgDefsElement, svgRoot.firstChild);
        }
    }

    /**
     * Create and inject SVG pattern definition with optional rotation
     */
    public async injectPattern(patternId: string, rotation?: number): Promise<boolean> {
        if (!this.svgDefsElement) {
            console.error("SVG defs element not initialized");
            return false;
        }

        const pattern = this.patterns.get(patternId);
        if (!pattern) {
            console.error(`Pattern ${patternId} not found`);
            return false;
        }

        // Check if pattern already loaded
        if (this.loadedPatterns.has(patternId)) {
            return true;
        }

        // Skip if no image defined
        if (!pattern.image) {
            console.warn(`Pattern ${patternId} has no image`);
            return false;
        }

        try {
            // Create pattern element
            const patternElement = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
            patternElement.setAttribute("id", `texture-pattern-${patternId}`);
            patternElement.setAttribute("patternUnits", pattern.svgPattern.patternUnits);
            patternElement.setAttribute("width", pattern.svgPattern.width.toString());
            patternElement.setAttribute("height", pattern.svgPattern.height.toString());

            // Create image element
            const imageElement = document.createElementNS("http://www.w3.org/2000/svg", "image");
            imageElement.setAttribute("href", `/textures/${pattern.image}`);
            imageElement.setAttribute("width", pattern.svgPattern.width.toString());
            imageElement.setAttribute("height", pattern.svgPattern.height.toString());

            // Apply scale if needed
            if (pattern.scale !== 1.0) {
                const scaledWidth = pattern.svgPattern.width * pattern.scale;
                const scaledHeight = pattern.svgPattern.height * pattern.scale;
                imageElement.setAttribute("width", scaledWidth.toString());
                imageElement.setAttribute("height", scaledHeight.toString());
            }

            // Add image to pattern
            patternElement.appendChild(imageElement);

            // Apply rotation if specified (use parameter or pattern default)
            const rotationAngle = rotation !== undefined ? rotation : pattern.rotation || 0;
            if (rotationAngle !== 0) {
                // Rotate around the center of the pattern
                const centerX = pattern.svgPattern.width / 2;
                const centerY = pattern.svgPattern.height / 2;
                const transform = `rotate(${rotationAngle} ${centerX} ${centerY})`;
                patternElement.setAttribute("patternTransform", transform);
            }

            // Add pattern to defs
            this.svgDefsElement.appendChild(patternElement);
            this.loadedPatterns.add(patternId);

            console.log(`Injected pattern: ${patternId}`);
            return true;
        } catch (error) {
            console.error(`Error injecting pattern ${patternId}:`, error);
            return false;
        }
    }

    /**
     * Apply pattern to SVG element with optional rotation
     */
    public async applyPatternToElement(
        element: SVGElement,
        patternId: string,
        rotation?: number,
    ): Promise<boolean> {
        // Ensure pattern is loaded with rotation
        const success = await this.injectPattern(patternId, rotation);
        if (!success) {
            return false;
        }

        // Apply pattern fill
        element.setAttribute("fill", `url(#texture-pattern-${patternId})`);
        element.setAttribute("data-texture-id", patternId);

        // Store rotation if specified
        if (rotation !== undefined) {
            element.setAttribute("data-texture-rotation", rotation.toString());
        }

        return true;
    }

    /**
     * Remove pattern from element
     */
    public removePatternFromElement(element: SVGElement): void {
        element.removeAttribute("fill");
        element.removeAttribute("data-texture-id");
    }

    /**
     * Get applied pattern ID from element
     */
    public getElementPattern(element: SVGElement): string | null {
        return element.getAttribute("data-texture-id");
    }

    /**
     * Clear all loaded patterns from SVG
     */
    public clearPatterns(): void {
        if (this.svgDefsElement) {
            // Remove only our pattern elements
            const patterns = this.svgDefsElement.querySelectorAll('pattern[id^="texture-pattern-"]');
            patterns.forEach((pattern) => pattern.remove());
        }
        this.loadedPatterns.clear();
    }

    /**
     * Get localized pattern name
     */
    public getPatternName(patternId: string): string {
        const pattern = this.patterns.get(patternId);
        if (!pattern) return patternId;

        const currentLang = I18n.currentLanguage();
        const isJapanese = (currentLang as string) === "ja-jp" || (currentLang as string) === "zh-cn";
        return isJapanese ? pattern.name : pattern.nameEn;
    }

    /**
     * Get localized pattern description
     */
    public getPatternDescription(patternId: string): string {
        const pattern = this.patterns.get(patternId);
        if (!pattern) return "";

        const currentLang = I18n.currentLanguage();
        const isJapanese = (currentLang as string) === "ja-jp" || (currentLang as string) === "zh-cn";
        return isJapanese ? pattern.description : pattern.descriptionEn;
    }

    /**
     * Export patterns configuration for saving
     */
    public exportAppliedPatterns(): Record<string, string> {
        const applied: Record<string, string> = {};

        if (this.svgDefsElement) {
            const elements = this.svgDefsElement.parentElement?.querySelectorAll("[data-texture-id]");
            elements?.forEach((element) => {
                const id = element.getAttribute("id");
                const textureId = element.getAttribute("data-texture-id");
                if (id && textureId) {
                    applied[id] = textureId;
                }
            });
        }

        return applied;
    }

    /**
     * Import and apply saved patterns configuration
     */
    public async importAppliedPatterns(config: Record<string, string>): Promise<void> {
        if (!this.svgDefsElement) return;

        for (const [elementId, patternId] of Object.entries(config)) {
            const element = this.svgDefsElement.parentElement?.querySelector(`#${elementId}`);
            if (element instanceof SVGElement) {
                await this.applyPatternToElement(element, patternId);
            }
        }
    }
}
