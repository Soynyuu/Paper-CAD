// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef } from "react";

export interface ReactBridgeProps<T extends HTMLElement = HTMLElement> {
    /**
     * Tag name of the Web Component (e.g., "my-custom-element")
     */
    tagName: string;

    /**
     * Props to pass to the Web Component.
     * - String/number/boolean values set as attributes
     * - Objects/arrays set as properties
     * - Functions starting with "on" are treated as event listeners
     */
    [key: string]: any;

    /**
     * Ref to access the underlying DOM element
     */
    elementRef?: React.Ref<T>;

    /**
     * CSS class name
     */
    className?: string;

    /**
     * Inline styles
     */
    style?: React.CSSProperties;

    /**
     * Children elements
     */
    children?: React.ReactNode;
}

/**
 * ReactBridge - Generic wrapper for Web Components in React
 *
 * Enables gradual React migration by allowing Web Components to be used
 * seamlessly within React component trees.
 *
 * @example
 * ```tsx
 * <ReactBridge
 *   tagName="my-custom-element"
 *   customProp="value"
 *   onCustomEvent={(e) => console.log(e.detail)}
 * />
 * ```
 */
export function ReactBridge<T extends HTMLElement = HTMLElement>({
    tagName,
    elementRef,
    className,
    style,
    children,
    ...props
}: ReactBridgeProps<T>) {
    const localRef = useRef<T>(null);
    const ref = (elementRef as React.RefObject<T>) || localRef;

    useEffect(() => {
        const element = ref.current;
        if (!element) return;

        // Separate props into attributes, properties, and event listeners
        const attributes: Record<string, string> = {};
        const properties: Record<string, any> = {};
        const eventListeners: Record<string, EventListener> = {};

        for (const [key, value] of Object.entries(props)) {
            // Event listeners (onEventName -> eventname)
            if (key.startsWith("on") && typeof value === "function") {
                const eventName = key.slice(2).toLowerCase();
                eventListeners[eventName] = value as EventListener;
                continue;
            }

            // Primitive values -> attributes
            if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
                attributes[key] = String(value);
                continue;
            }

            // Complex values -> properties
            if (value !== null && value !== undefined) {
                properties[key] = value;
            }
        }

        // Set attributes
        for (const [key, value] of Object.entries(attributes)) {
            element.setAttribute(key, value);
        }

        // Set properties
        for (const [key, value] of Object.entries(properties)) {
            (element as any)[key] = value;
        }

        // Add event listeners
        for (const [event, listener] of Object.entries(eventListeners)) {
            element.addEventListener(event, listener);
        }

        // Cleanup
        return () => {
            for (const [event, listener] of Object.entries(eventListeners)) {
                element.removeEventListener(event, listener);
            }
        };
    }, [ref, props]);

    return React.createElement(
        tagName,
        {
            ref,
            className,
            style,
        },
        children,
    );
}
