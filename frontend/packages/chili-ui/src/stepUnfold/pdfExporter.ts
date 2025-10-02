// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import jsPDF from "jspdf";
import { svg2pdf } from "svg2pdf.js";

export interface PageFormat {
    name: string;
    width: number;  // mm
    height: number; // mm
}

export interface PDFExportOptions {
    pageFormat: "A4" | "A3" | "Letter";
    orientation: "portrait" | "landscape";
    margin: number; // mm
    splitPages: boolean; // Whether to split content across multiple pages
    scale?: number; // Optional scale factor
}

export class PDFExporter {
    private static pageFormats: Record<string, PageFormat> = {
        A4: { name: "A4", width: 210, height: 297 },
        A3: { name: "A3", width: 297, height: 420 },
        Letter: { name: "Letter", width: 215.9, height: 279.4 }
    };

    /**
     * Export SVG content to PDF with automatic page splitting
     */
    static async exportToPDF(
        svgElement: SVGElement,
        options: PDFExportOptions
    ): Promise<void> {
        const format = this.pageFormats[options.pageFormat];
        if (!format) {
            throw new Error(`Unknown page format: ${options.pageFormat}`);
        }

        // Get actual page dimensions based on orientation
        const pageWidth = options.orientation === "portrait" ? format.width : format.height;
        const pageHeight = options.orientation === "portrait" ? format.height : format.width;

        // Calculate printable area (excluding margins)
        const printableWidth = pageWidth - (options.margin * 2);
        const printableHeight = pageHeight - (options.margin * 2);

        // Create PDF document
        const pdf = new jsPDF({
            orientation: options.orientation,
            unit: "mm",
            format: options.pageFormat.toLowerCase() as any
        });

        // For now, always use single page export regardless of splitPages setting
        // Multi-page splitting will be re-implemented in a future update
        await this.exportSinglePage(
            pdf,
            svgElement,
            printableWidth,
            printableHeight,
            options
        );

        // Save the PDF
        const timestamp = new Date().toISOString().replace(/:/g, '-').slice(0, 19);
        pdf.save(`paper-cad-unfold-${timestamp}.pdf`);
    }

    /**
     * Export SVG to a single PDF page
     */
    private static async exportSinglePage(
        pdf: jsPDF,
        svgElement: SVGElement,
        printableWidth: number,
        printableHeight: number,
        options: PDFExportOptions
    ): Promise<void> {
        const svgClone = svgElement.cloneNode(true) as SVGElement;

        // Get SVG dimensions - prioritize viewBox if available
        const viewBox = svgElement.getAttribute("viewBox");
        let svgWidth: number, svgHeight: number;

        if (viewBox) {
            const parts = viewBox.split(/\s+/).map(Number);
            if (parts.length === 4) {
                svgWidth = parts[2];
                svgHeight = parts[3];
                // Ensure viewBox is set on clone
                svgClone.setAttribute("viewBox", viewBox);
            } else {
                svgWidth = parseFloat(svgElement.getAttribute("width") || "800");
                svgHeight = parseFloat(svgElement.getAttribute("height") || "600");
            }
        } else {
            svgWidth = parseFloat(svgElement.getAttribute("width") || "800");
            svgHeight = parseFloat(svgElement.getAttribute("height") || "600");
            // Set viewBox if not present
            svgClone.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);
        }

        // Remove width/height attributes - let svg2pdf handle sizing
        svgClone.removeAttribute("width");
        svgClone.removeAttribute("height");

        // Calculate scale to fit on page
        const svgAspectRatio = svgWidth / svgHeight;
        const pageAspectRatio = printableWidth / printableHeight;

        let renderWidth: number, renderHeight: number;

        if (svgAspectRatio > pageAspectRatio) {
            // SVG is wider - fit to width
            renderWidth = printableWidth;
            renderHeight = printableWidth / svgAspectRatio;
        } else {
            // SVG is taller - fit to height
            renderHeight = printableHeight;
            renderWidth = printableHeight * svgAspectRatio;
        }

        // Apply user scale if specified
        if (options.scale) {
            renderWidth *= options.scale;
            renderHeight *= options.scale;
            // Ensure it still fits on page
            if (renderWidth > printableWidth) {
                const scaleFactor = printableWidth / renderWidth;
                renderWidth = printableWidth;
                renderHeight *= scaleFactor;
            }
            if (renderHeight > printableHeight) {
                const scaleFactor = printableHeight / renderHeight;
                renderHeight = printableHeight;
                renderWidth *= scaleFactor;
            }
        }

        console.log('Single page export:', {
            svgWidth,
            svgHeight,
            svgAspectRatio,
            printableWidth,
            printableHeight,
            renderWidth,
            renderHeight,
            scale: options.scale
        });

        // Add to PDF
        try {
            await svg2pdf(svgClone, pdf, {
                x: options.margin,
                y: options.margin,
                width: renderWidth,
                height: renderHeight
            });
        } catch (error) {
            console.error('svg2pdf error:', error);
            throw error;
        }
    }

    /**
     * Export SVG split across multiple PDF pages
     */
    private static async exportWithPageSplit(
        pdf: jsPDF,
        svgElement: SVGElement,
        printableWidth: number,
        printableHeight: number,
        options: PDFExportOptions
    ): Promise<void> {
        // Get SVG dimensions - these are typically in pixels
        let svgWidth = parseFloat(svgElement.getAttribute("width") || "800");
        let svgHeight = parseFloat(svgElement.getAttribute("height") || "600");
        const viewBox = svgElement.getAttribute("viewBox");

        // Parse viewBox if exists
        let vbX = 0, vbY = 0, vbWidth = svgWidth, vbHeight = svgHeight;
        if (viewBox) {
            const parts = viewBox.split(" ").map(Number);
            if (parts.length === 4) {
                [vbX, vbY, vbWidth, vbHeight] = parts;
                // Use viewBox dimensions as they're more accurate
                svgWidth = vbWidth;
                svgHeight = vbHeight;
            }
        }

        // Convert pixels to mm (assuming 96 DPI, which is standard for web)
        // 1 inch = 25.4mm, 96 pixels = 1 inch
        // So 1 pixel = 25.4/96 mm = 0.264583 mm
        const PIXELS_TO_MM = 0.264583;
        const svgWidthMm = svgWidth * PIXELS_TO_MM;
        const svgHeightMm = svgHeight * PIXELS_TO_MM;

        // Apply user scale
        const scale = options.scale || 1;
        const scaledWidthMm = svgWidthMm * scale;
        const scaledHeightMm = svgHeightMm * scale;

        console.log('PDF Export dimensions:', {
            svgWidthPx: svgWidth,
            svgHeightPx: svgHeight,
            svgWidthMm,
            svgHeightMm,
            scaledWidthMm,
            scaledHeightMm,
            printableWidth,
            printableHeight
        });

        // For now, always use single page export
        // Multi-page splitting needs more complex implementation
        console.log('Using single page export mode');
        await this.exportSinglePage(pdf, svgElement, printableWidth, printableHeight, options);
        return;

        // Calculate number of pages needed
        const pagesX = Math.ceil(scaledWidthMm / printableWidth);
        const pagesY = Math.ceil(scaledHeightMm / printableHeight);

        console.log(`Creating ${pagesX} x ${pagesY} = ${pagesX * pagesY} pages`);

        // Create pages
        for (let py = 0; py < pagesY; py++) {
            for (let px = 0; px < pagesX; px++) {
                // Add new page (except for the first one)
                if (px > 0 || py > 0) {
                    pdf.addPage();
                }

                // Calculate viewport for this page (in original SVG units/pixels)
                const viewportX = vbX + (px * printableWidth / PIXELS_TO_MM / scale);
                const viewportY = vbY + (py * printableHeight / PIXELS_TO_MM / scale);
                const viewportWidth = Math.min(
                    printableWidth / PIXELS_TO_MM / scale,
                    svgWidth - (px * printableWidth / PIXELS_TO_MM / scale)
                );
                const viewportHeight = Math.min(
                    printableHeight / PIXELS_TO_MM / scale,
                    svgHeight - (py * printableHeight / PIXELS_TO_MM / scale)
                );

                // Create a cloned SVG for this page
                const pageSvg = svgElement.cloneNode(true) as SVGElement;
                pageSvg.setAttribute("width", String(viewportWidth));
                pageSvg.setAttribute("height", String(viewportHeight));
                pageSvg.setAttribute("viewBox", `${viewportX} ${viewportY} ${viewportWidth} ${viewportHeight}`);

                // Add page number and grid reference
                const pageNumber = py * pagesX + px + 1;
                const totalPages = pagesX * pagesY;

                // Calculate the actual size in mm for this page section
                const pageWidthMm = Math.min(printableWidth, scaledWidthMm - (px * printableWidth));
                const pageHeightMm = Math.min(printableHeight, scaledHeightMm - (py * printableHeight));

                // Add to PDF
                await svg2pdf(pageSvg, pdf, {
                    x: options.margin,
                    y: options.margin,
                    width: pageWidthMm,
                    height: pageHeightMm
                });

                // Add page info footer
                pdf.setFontSize(10);
                pdf.setTextColor(128, 128, 128);
                const pageInfo = `Page ${pageNumber} of ${totalPages} (${px + 1},${py + 1})`;
                const pageInfoWidth = pdf.getTextWidth(pageInfo);
                pdf.text(
                    pageInfo,
                    (printableWidth + 2 * options.margin - pageInfoWidth) / 2,
                    printableHeight + options.margin + 5
                );

                // Add cut marks and alignment guides
                this.addCutMarks(pdf, options.margin, printableWidth, printableHeight, px, py, pagesX, pagesY);
            }
        }
    }

    /**
     * Add cut marks and alignment guides to help with page assembly
     */
    private static addCutMarks(
        pdf: jsPDF,
        margin: number,
        printableWidth: number,
        printableHeight: number,
        px: number,
        py: number,
        pagesX: number,
        pagesY: number
    ): void {
        const markLength = 5; // mm
        pdf.setDrawColor(200, 200, 200);
        pdf.setLineWidth(0.1);

        // Top-left corner mark
        if (px > 0 || py > 0) {
            pdf.line(margin - markLength, margin, margin, margin);
            pdf.line(margin, margin - markLength, margin, margin);
        }

        // Top-right corner mark
        if (px < pagesX - 1) {
            pdf.line(margin + printableWidth, margin, margin + printableWidth + markLength, margin);
            pdf.line(margin + printableWidth, margin - markLength, margin + printableWidth, margin);
        }

        // Bottom-left corner mark
        if (py < pagesY - 1) {
            pdf.line(margin - markLength, margin + printableHeight, margin, margin + printableHeight);
            pdf.line(margin, margin + printableHeight, margin, margin + printableHeight + markLength);
        }

        // Bottom-right corner mark
        if (px < pagesX - 1 || py < pagesY - 1) {
            pdf.line(
                margin + printableWidth,
                margin + printableHeight,
                margin + printableWidth + markLength,
                margin + printableHeight
            );
            pdf.line(
                margin + printableWidth,
                margin + printableHeight,
                margin + printableWidth,
                margin + printableHeight + markLength
            );
        }
    }

    /**
     * Calculate optimal scale for fitting content on pages
     */
    static calculateOptimalScale(
        svgWidth: number,
        svgHeight: number,
        pageFormat: "A4" | "A3" | "Letter",
        orientation: "portrait" | "landscape",
        margin: number
    ): number {
        const format = this.pageFormats[pageFormat];
        const pageWidth = orientation === "portrait" ? format.width : format.height;
        const pageHeight = orientation === "portrait" ? format.height : format.width;

        const printableWidth = pageWidth - (margin * 2);
        const printableHeight = pageHeight - (margin * 2);

        // Calculate scale to fit at least one dimension
        const scaleX = printableWidth / svgWidth;
        const scaleY = printableHeight / svgHeight;

        // Return the scale that fits best without being too small
        return Math.max(Math.min(scaleX, scaleY), 0.1);
    }
}