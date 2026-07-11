import {
    clearSvgFaceShapes,
    getSvgElementsBounds,
    highlightSvgFaceShapes,
} from "../src/stepUnfold/faceSearchHighlight";

function createSvg(): SVGSVGElement {
    const container = document.createElement("div");
    container.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg">
            <defs><pattern id="texture" /></defs>
            <path id="hole" data-face-number="7" style="fill: url(#texture); opacity: 0.8" />
            <polygon id="part" data-face-number="7" fill="#fff" />
            <polygon id="other" data-face-number="8" fill="#000" />
        </svg>`;
    return container.querySelector("svg")!;
}

describe("face search SVG highlighting", () => {
    test("highlights every path and polygon for the requested face without replacing fill", () => {
        const svg = createSvg();
        const shapes = highlightSvgFaceShapes(svg, 7);

        expect(shapes.map((shape) => shape.id)).toEqual(["hole", "part"]);
        expect(shapes[0].style.fill).toBe("url(#texture)");
        expect(shapes[0].style.stroke).toBe("#f59e0b");
        expect(svg.querySelector<SVGElement>("#other")!.hasAttribute("data-search-match")).toBe(false);
    });

    test("restores exact inline styles and removes temporary search attributes", () => {
        const svg = createSvg();
        const styled = svg.querySelector<SVGElement>("#hole")!;
        const unstyled = svg.querySelector<SVGElement>("#part")!;
        const originalStyle = styled.getAttribute("style");

        highlightSvgFaceShapes(svg, 7);
        clearSvgFaceShapes(svg);

        expect(styled.getAttribute("style")).toBe(originalStyle);
        expect(unstyled.hasAttribute("style")).toBe(false);
        expect(svg.querySelector("[data-search-match]")).toBeNull();
    });

    test("combines bounds from multiple SVG elements", () => {
        const svg = createSvg();
        const shapes = highlightSvgFaceShapes(svg, 7);
        shapes[0].getBBox = (() => ({ x: 10, y: 20, width: 30, height: 40 })) as any;
        shapes[1].getBBox = (() => ({ x: 50, y: 5, width: 20, height: 10 })) as any;

        expect(getSvgElementsBounds(shapes)).toEqual({ x: 10, y: 5, width: 60, height: 55 });
    });
});
