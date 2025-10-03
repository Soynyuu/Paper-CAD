// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

// Use SVG-Edit's bundled versions to avoid version conflicts
// @ts-ignore - These imports are from SVG-Edit's node_modules
import jsPDF from "svgedit/node_modules/jspdf";
// @ts-ignore - These imports are from SVG-Edit's node_modules
import { svg2pdf } from "svgedit/node_modules/svg2pdf.js";

export interface SimplePDFExportOptions {
    pageFormat: "A4" | "A3" | "Letter";
    orientation: "portrait" | "landscape";
    margin: number; // mm
}

/**
 * Simplified PDF exporter that focuses on correct scaling
 */
export class SimplePDFExporter {
    private static pageFormats = {
        A4: { width: 210, height: 297 },
        A3: { width: 297, height: 420 },
        Letter: { width: 215.9, height: 279.4 }
    };

    /**
     * Export SVG to PDF with proper scaling
     */
    static async exportToPDF(
        svgElement: SVGElement,
        options: SimplePDFExportOptions
    ): Promise<void> {
        console.log("=== SimplePDFExporter Start ===");

        // Get page dimensions in mm
        const format = this.pageFormats[options.pageFormat];
        const pageWidth = options.orientation === "portrait" ? format.width : format.height;
        const pageHeight = options.orientation === "portrait" ? format.height : format.width;
        const printableWidth = pageWidth - (options.margin * 2);
        const printableHeight = pageHeight - (options.margin * 2);

        console.log("Page dimensions (mm):", { pageWidth, pageHeight, printableWidth, printableHeight });

        // Create PDF
        const pdf = new jsPDF({
            orientation: options.orientation,
            unit: "mm",
            format: options.pageFormat.toLowerCase() as any
        });

        // Get SVG dimensions
        const svgInfo = this.getSVGDimensions(svgElement);
        console.log("SVG info:", svgInfo);

        // Clone SVG and prepare for export
        const svgClone = svgElement.cloneNode(true) as SVGElement;

        // IMPORTANT: Set explicit width/height in pixels and viewBox
        svgClone.setAttribute("width", String(svgInfo.width));
        svgClone.setAttribute("height", String(svgInfo.height));
        svgClone.setAttribute("viewBox", `0 0 ${svgInfo.width} ${svgInfo.height}`);

        // Calculate scale to fit page while maintaining aspect ratio
        const scaleX = printableWidth / (svgInfo.width * 0.264583); // Convert px to mm
        const scaleY = printableHeight / (svgInfo.height * 0.264583);
        const scale = Math.min(scaleX, scaleY, 1); // Don't upscale, only downscale if needed

        // Calculate final render size in mm
        const renderWidth = svgInfo.width * 0.264583 * scale;
        const renderHeight = svgInfo.height * 0.264583 * scale;

        // Center on page if smaller
        const xOffset = options.margin + (printableWidth - renderWidth) / 2;
        const yOffset = options.margin + (printableHeight - renderHeight) / 2;

        console.log("Render dimensions:", {
            scale,
            renderWidth,
            renderHeight,
            xOffset,
            yOffset
        });

        try {
            // Add SVG to PDF
            // The key is to provide correct dimensions in mm
            await svg2pdf(svgClone, pdf, {
                x: xOffset,
                y: yOffset,
                width: renderWidth,
                height: renderHeight
            });

            // Add debug info to PDF
            pdf.setFontSize(8);
            pdf.setTextColor(150);
            pdf.text(`SVG: ${svgInfo.width}x${svgInfo.height}px | Scale: ${scale.toFixed(2)} | Size: ${renderWidth.toFixed(1)}x${renderHeight.toFixed(1)}mm`,
                     options.margin, pageHeight - 5);

            // Save PDF
            const timestamp = new Date().toISOString().replace(/:/g, '-').slice(0, 19);
            pdf.save(`paper-cad-unfold-${timestamp}.pdf`);

            console.log("=== PDF Export Success ===");
        } catch (error) {
            console.error("PDF export error:", error);
            throw error;
        }
    }

    /**
     * Get accurate SVG dimensions from various sources
     */
    private static getSVGDimensions(svg: SVGElement): { width: number; height: number } {
        // Try viewBox first (most reliable)
        const viewBox = svg.getAttribute("viewBox");
        if (viewBox) {
            const parts = viewBox.trim().split(/\s+/).map(Number);
            if (parts.length === 4 && !isNaN(parts[2]) && !isNaN(parts[3])) {
                return { width: parts[2], height: parts[3] };
            }
        }

        // Try width/height attributes
        const width = svg.getAttribute("width");
        const height = svg.getAttribute("height");
        if (width && height) {
            // Remove units if present (px, %, etc)
            const w = parseFloat(width);
            const h = parseFloat(height);
            if (!isNaN(w) && !isNaN(h)) {
                return { width: w, height: h };
            }
        }

        // Try getBBox() as fallback
        try {
            const bbox = (svg as any).getBBox();
            if (bbox) {
                return { width: bbox.width, height: bbox.height };
            }
        } catch (e) {
            console.warn("getBBox failed:", e);
        }

        // Default fallback
        console.warn("Could not determine SVG dimensions, using defaults");
        return { width: 800, height: 600 };
    }
}