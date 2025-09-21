// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import {
    CityGMLService,
    EditableShapeNode,
    I18n,
    IDataExchange,
    IDocument,
    INode,
    IShape,
    PubSub,
    Result,
    ShapeNode,
    VisualNode,
} from "chili-core";

export class DefaultDataExchange implements IDataExchange {
    private cityGMLService: CityGMLService;

    constructor() {
        this.cityGMLService = new CityGMLService();
    }

    importFormats(): string[] {
        return [".step", ".stp", ".iges", ".igs", ".brep", ".stl", ".gml", ".xml"];
    }

    exportFormats(): string[] {
        return [".step", ".iges", ".brep", ".stl", ".stl binary", ".ply", ".ply binary", ".obj"];
    }

    async import(document: IDocument, files: FileList | File[]): Promise<void> {
        for (const file of files) {
            await this.handleSingleFileImport(document, file);
        }
    }

    private async handleSingleFileImport(document: IDocument, file: File) {
        let importResult: Result<INode> | undefined;

        const fileName = file.name.toLocaleLowerCase();
        if (this.extensionIs(fileName, ".brep")) {
            importResult = await this.importBrep(document, file);
        } else if (this.extensionIs(fileName, ".stl")) {
            importResult = await this.importStl(document, file);
        } else if (this.extensionIs(fileName, ".step", ".stp")) {
            importResult = await this.importStep(document, file);
        } else if (this.extensionIs(fileName, ".iges", ".igs")) {
            importResult = await this.importIges(document, file);
        } else if (this.extensionIs(fileName, ".gml", ".xml")) {
            // Check if it's likely a CityGML file
            if (await this.isCityGMLFile(file)) {
                importResult = await this.importCityGML(document, file);
            }
        }

        this.handleImportResult(document, fileName, importResult);
    }

    private extensionIs(fileName: string, ...extensions: string[]): boolean {
        return extensions.some((ext) => fileName.endsWith(ext));
    }

    private handleImportResult(document: IDocument, name: string, nodeResult: Result<INode> | undefined) {
        if (!nodeResult?.isOk) {
            alert(I18n.translate("error.import.unsupportedFileType:{0}", name));
            return;
        }

        const node = nodeResult.value;
        node.name = name;
        document.addNode(node);
        document.visual.update();
    }

    async importBrep(document: IDocument, file: File) {
        const shape = document.application.shapeFactory.converter.convertFromBrep(await file.text());
        if (!shape.isOk) {
            return Result.err(shape.error);
        }
        return Result.ok(new EditableShapeNode(document, file.name, shape.value));
    }

    private async importStl(document: IDocument, file: File) {
        const content = new Uint8Array(await file.arrayBuffer());
        return document.application.shapeFactory.converter.convertFromSTL(document, content);
    }

    private async importIges(document: IDocument, file: File) {
        const content = new Uint8Array(await file.arrayBuffer());
        return document.application.shapeFactory.converter.convertFromIGES(document, content);
    }

    private async importStep(document: IDocument, file: File) {
        const content = new Uint8Array(await file.arrayBuffer());
        return document.application.shapeFactory.converter.convertFromSTEP(document, content);
    }

    private async importCityGML(document: IDocument, file: File) {
        // Convert CityGML to STEP using the backend service
        const stepResult = await this.cityGMLService.convertToStep(file, {
            defaultHeight: 10.0,
            limit: 50,
            autoReproject: true,
        });

        if (!stepResult.isOk) {
            return Result.err(stepResult.error);
        }

        // Convert the STEP blob to array buffer
        const arrayBuffer = await stepResult.value.arrayBuffer();
        const content = new Uint8Array(arrayBuffer);

        // Use the existing STEP import logic
        return document.application.shapeFactory.converter.convertFromSTEP(document, content);
    }

    private async isCityGMLFile(file: File): Promise<boolean> {
        // Quick check for CityGML content by reading first few KB
        const slice = file.slice(0, 4096);
        const text = await slice.text();

        // Check for CityGML namespace or building elements
        return (
            text.includes("citygml") ||
            text.includes("CityGML") ||
            text.includes("bldg:") ||
            text.includes("<Building") ||
            text.includes("gml:")
        );
    }

    async export(type: string, nodes: VisualNode[]): Promise<BlobPart[] | undefined> {
        if (nodes.length === 0) return undefined;

        const document = nodes[0].document;
        let shapeResult: Result<BlobPart> | undefined;
        if (type === ".stl") {
            shapeResult = document.visual.meshExporter.exportToStl(nodes, true);
        } else if (type === ".stl binary") {
            shapeResult = document.visual.meshExporter.exportToStl(nodes, false);
        } else if (type === ".ply") {
            shapeResult = document.visual.meshExporter.exportToPly(nodes, true);
        } else if (type === ".ply binary") {
            shapeResult = document.visual.meshExporter.exportToPly(nodes, false);
        } else if (type === ".obj") {
            shapeResult = document.visual.meshExporter.exportToObj(nodes);
        } else {
            const shapes = this.getExportShapes(nodes);
            if (!shapes.length) return undefined;
            if (type === ".step") shapeResult = this.exportStep(document, shapes);
            if (type === ".iges") shapeResult = this.exportIges(document, shapes);
            if (type === ".brep") shapeResult = this.exportBrep(document, shapes);
        }

        if (shapeResult) {
            return this.handleExportResult(shapeResult);
        }
        return undefined;
    }

    private getExportShapes(nodes: VisualNode[]): IShape[] {
        const shapes = nodes
            .filter((x): x is ShapeNode => x instanceof ShapeNode)
            .map((x) => x.shape.value.transformedMul(x.worldTransform()));

        !shapes.length && PubSub.default.pub("showToast", "error.export.noNodeCanBeExported");
        return shapes;
    }

    private exportStep(doc: IDocument, shapes: IShape[]) {
        return doc.application.shapeFactory.converter.convertToSTEP(...shapes);
    }

    private exportIges(doc: IDocument, shapes: IShape[]) {
        return doc.application.shapeFactory.converter.convertToIGES(...shapes);
    }

    private exportBrep(document: IDocument, shapes: IShape[]) {
        const comp = document.application.shapeFactory.combine(shapes);
        if (!comp.isOk) {
            return Result.err(comp.error);
        }

        const result = document.application.shapeFactory.converter.convertToBrep(comp.value);
        comp.value.dispose();
        return result;
    }

    private handleExportResult(result: Result<BlobPart> | undefined) {
        if (!result?.isOk) {
            PubSub.default.pub("showToast", "error.default:{0}", result?.error);
            return undefined;
        }
        return [result.value];
    }
}
