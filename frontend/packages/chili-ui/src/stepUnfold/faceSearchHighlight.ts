export type SvgBounds = { x: number; y: number; width: number; height: number };

export const SEARCH_MATCH_ATTRIBUTE = "data-search-match";

const originalStyles = new WeakMap<SVGGraphicsElement, { value: string; existed: boolean }>();

export function highlightSvgFaceShapes(svgRoot: SVGElement, faceNumber: number): SVGGraphicsElement[] {
    const selector = `path[data-face-number="${faceNumber}"], polygon[data-face-number="${faceNumber}"]`;
    const shapes = Array.from(svgRoot.querySelectorAll<SVGGraphicsElement>(selector));

    shapes.forEach((shape) => {
        if (!originalStyles.has(shape)) {
            originalStyles.set(shape, {
                value: shape.getAttribute("style") ?? "",
                existed: shape.hasAttribute("style"),
            });
        }
        shape.setAttribute(SEARCH_MATCH_ATTRIBUTE, "true");
        // Keep the original fill (including texture patterns) visible and emphasize its boundary.
        shape.style.setProperty("stroke", "#f59e0b", "important");
        shape.style.setProperty("stroke-width", "3", "important");
        shape.style.setProperty("stroke-opacity", "0.95", "important");
        shape.style.setProperty("paint-order", "stroke fill", "important");
        shape.style.setProperty("filter", "drop-shadow(0 0 4px rgba(245, 158, 11, 0.75))", "important");
    });

    return shapes;
}

export function clearSvgFaceShapes(svgRoot: SVGElement): void {
    svgRoot
        .querySelectorAll<SVGGraphicsElement>(
            `path[${SEARCH_MATCH_ATTRIBUTE}="true"], polygon[${SEARCH_MATCH_ATTRIBUTE}="true"]`,
        )
        .forEach((shape) => {
            const originalStyle = originalStyles.get(shape);
            if (originalStyle?.existed) {
                shape.setAttribute("style", originalStyle.value);
            } else {
                shape.removeAttribute("style");
            }
            originalStyles.delete(shape);
            shape.removeAttribute(SEARCH_MATCH_ATTRIBUTE);
        });
}

export function getSvgElementsBounds(elements: SVGGraphicsElement[]): SvgBounds | undefined {
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;

    elements.forEach((element) => {
        try {
            const box = element.getBBox();
            if (![box.x, box.y, box.width, box.height].every(Number.isFinite)) return;
            minX = Math.min(minX, box.x);
            minY = Math.min(minY, box.y);
            maxX = Math.max(maxX, box.x + box.width);
            maxY = Math.max(maxY, box.y + box.height);
        } catch {
            // Detached or temporarily hidden SVG elements can reject getBBox().
        }
    });

    if (![minX, minY, maxX, maxY].every(Number.isFinite)) return undefined;
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}
