// Type definitions for svgedit
declare module "svgedit" {
    export interface ConfigOptions {
        allowInitialUserOverride?: boolean;
        imgPath?: string;
        langPath?: string;
        extPath?: string;
        extensions?: string[];
        noDefaultExtensions?: boolean;
        userExtensions?: any[];
        dimensions?: [number, number];
        initFill?: {
            color?: string;
            opacity?: number;
        };
        initStroke?: {
            color?: string;
            opacity?: number;
            width?: number;
        };
        initTool?: string;
        wireframe?: boolean;
        showRulers?: boolean;
        baseUnit?: string;
        gridSnapping?: boolean;
        gridColor?: string;
        snappingStep?: number;
        showGrid?: boolean;
        canvasName?: string;
        no_save_warning?: boolean;
    }

    export interface SvgCanvas {
        updateCanvas(w: number, h: number): void;
        setZoom(zoom: number): void;
        getZoom(): number;
        getMode(): string;
        setMode(mode: string): void;
        getSelectedElems(): SVGElement[];
        deleteSelectedElements(): void;
        moveSelectedElements(dx: number, dy: number, animate?: boolean): void;
        copySelectedElements(): void;
        pasteElements(): void;
        clearSelection(noCall?: boolean): void;
        selectAllInCurrentLayer(): void;
        setSvgString(xmlString: string): boolean;
        getSvgString(): string;
        save(opts?: any): void;
        undo(): void;
        redo(): void;
        getUndoStackSize(): number;
        getRedoStackSize(): number;
        addToSelection(elemsToAdd: Element[], showGrips?: boolean): void;
        removeFromSelection(elemsToRemove: Element[]): void;
        getNextId(): string;
        bind(event: string, callback: Function): void;
        setColor(type: string, val: string, preventUndo?: boolean): void;
        setStrokeWidth(val: number): void;
        setFontSize(val: number): void;
        setFontFamily(val: string): void;
        setBold(val: boolean): void;
        setItalic(val: boolean): void;
        getTitle(elem?: Element): string;
        setDocumentTitle(title: string): void;
        getEditorNS(add?: boolean): string;
        getResolution(): { w: number; h: number };
        getDocumentTitle(): string;
        getContentElem(): SVGSVGElement;
        getRootElem(): SVGSVGElement;
        addSVGElementFromJson(data: any): Element;
        getCurrentDrawing(): any;
        createLayer(name: string, hrService?: any): void;
        deleteCurrentLayer(): boolean;
        setCurrentLayer(name: string): boolean;
        renameCurrentLayer(newName: string): boolean;
        setCurrentLayerPosition(newPos: number): boolean;
        getCurrentLayerName(): string;
        setLayerVisibility(layerName: string, visible: boolean): boolean;
        moveSelectedToLayer(layerName: string): boolean;
        getLayerVisibility(layerName: string): boolean;
        getNumLayers(): number;
        getLayer(index: number): any;
        getCurrentLayerPosition(): number;
        getLayerName(index: number): string;
    }

    export default class Editor {
        constructor(container: HTMLElement);

        canvas: SvgCanvas;
        configObj: ConfigOptions;

        init(): Promise<void>;
        setConfig(opts: ConfigOptions): void;
        getConfig(): ConfigOptions;
        loadFromString(str: string): void;
        loadFromURL(url: string): Promise<void>;
        loadFromDataURI(dataUri: string): void;

        // Tool methods
        setMode(mode: string): void;

        // UI methods
        toggleSidePanel(close?: boolean): void;

        // Zoom methods
        changeZoom?: (zoom: number) => void;

        // Export methods
        exportPDF(exportWindowName?: string): void;

        // Event methods
        addExtension(name: string, initFunc: Function, priorityArr?: any[]): void;

        // Utility methods
        ready(callback: Function): void;

        // Properties
        svgCanvas: SvgCanvas;
        uiStrings: any;
        curConfig: ConfigOptions;
    }
}

declare module "@svgedit/svgcanvas" {
    export class SvgCanvas {
        constructor(container: HTMLElement, config?: any);
        // Canvas methods - same as above
    }
}
