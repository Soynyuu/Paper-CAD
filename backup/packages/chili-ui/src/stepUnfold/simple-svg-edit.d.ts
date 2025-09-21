// Type definitions for simple-svg-edit
declare module "simple-svg-edit" {
    export interface EditorOptions {
        container?: HTMLElement;
        width?: number;
        height?: number;
        viewBox?: string;
    }

    export interface Tool {
        name: string;
        icon?: string;
        cursor?: string;
        activate(): void;
        deactivate(): void;
    }

    export class Editor {
        constructor(svgElement: SVGSVGElement | HTMLElement, options?: EditorOptions);

        // Core methods
        loadSVG(svgContent: string): void;
        getSVG(): string;
        clear(): void;
        destroy(): void;

        // Tool management
        activateTool(toolName: string): void;
        deactivateTool(): void;
        getCurrentTool(): Tool | null;

        // Selection
        selectElement(element: SVGElement): void;
        deselectAll(): void;
        getSelectedElements(): SVGElement[];

        // Editing operations
        deleteSelected(): void;
        moveSelected(dx: number, dy: number): void;
        scaleSelected(scale: number): void;
        rotateSelected(angle: number): void;

        // History
        undo(): void;
        redo(): void;
        canUndo(): boolean;
        canRedo(): boolean;

        // Events
        on(event: string, callback: Function): void;
        off(event: string, callback?: Function): void;

        // Properties
        canvas: SVGSVGElement;
        container: HTMLElement;
        tools: Map<string, Tool>;
    }

    export class SimpleSvgEditor extends Editor {
        constructor(svgElement: SVGSVGElement | HTMLElement, options?: EditorOptions);
    }
}

declare module "simple-svg-edit/features/editor" {
    export { Editor } from "simple-svg-edit";
}

declare module "simple-svg-edit/features/default-helper" {
    // Default helper features are auto-registered
}

declare module "simple-svg-edit/features/text" {
    // Text editing features are auto-registered
}
