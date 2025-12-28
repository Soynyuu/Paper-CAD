// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import React from "react";
import { ReactBridge } from "../src/ReactBridge";

describe("ReactBridge", () => {
    it("renders a Web Component with the specified tag name", () => {
        const { container } = render(<ReactBridge tagName="test-element" data-testid="test" />);

        const element = container.querySelector("test-element");
        expect(element).toBeInTheDocument();
    });

    it("sets string attributes correctly", () => {
        const { container } = render(<ReactBridge tagName="test-element" customAttr="test-value" />);

        const element = container.querySelector("test-element");
        expect(element).toHaveAttribute("customAttr", "test-value");
    });

    it("sets number attributes correctly", () => {
        const { container } = render(<ReactBridge tagName="test-element" count={42} />);

        const element = container.querySelector("test-element");
        expect(element).toHaveAttribute("count", "42");
    });

    it("sets boolean attributes correctly", () => {
        const { container } = render(<ReactBridge tagName="test-element" enabled={true} />);

        const element = container.querySelector("test-element");
        expect(element).toHaveAttribute("enabled", "true");
    });

    it("applies className correctly", () => {
        const { container } = render(
            <ReactBridge tagName="test-element" className="test-class another-class" />,
        );

        const element = container.querySelector("test-element");
        expect(element).toHaveClass("test-class", "another-class");
    });

    it("applies inline styles correctly", () => {
        const { container } = render(
            <ReactBridge tagName="test-element" style={{ color: "red", fontSize: "14px" }} />,
        );

        const element = container.querySelector("test-element") as HTMLElement;
        expect(element?.style.color).toBe("red");
        expect(element?.style.fontSize).toBe("14px");
    });

    it("renders children correctly", () => {
        const { container } = render(
            <ReactBridge tagName="test-element">
                <span>Child content</span>
            </ReactBridge>,
        );

        const element = container.querySelector("test-element");
        expect(element).toHaveTextContent("Child content");
    });

    it("sets complex property values (not as attributes)", () => {
        const complexValue = { foo: "bar", nested: { value: 123 } };
        const { container } = render(<ReactBridge tagName="test-element" data={complexValue} />);

        const element = container.querySelector("test-element") as any;
        expect(element?.data).toEqual(complexValue);
        // Complex values should NOT be set as attributes
        expect(element).not.toHaveAttribute("data");
    });
});
