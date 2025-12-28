// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { useEffect, useRef } from "react";

/**
 * useWebComponentProps - Synchronize React props with Web Component properties
 *
 * Automatically updates Web Component properties when React props change.
 * Useful when wrapping existing Web Components with custom React wrappers.
 *
 * @param elementRef - Ref to the Web Component DOM element
 * @param props - Props object to synchronize
 *
 * @example
 * ```tsx
 * function MyComponentWrapper({ value, onChange }: Props) {
 *   const ref = useRef<HTMLElement>(null);
 *   useWebComponentProps(ref, { value });
 *
 *   useEffect(() => {
 *     const element = ref.current;
 *     if (!element) return;
 *     element.addEventListener('change', onChange);
 *     return () => element.removeEventListener('change', onChange);
 *   }, [onChange]);
 *
 *   return <my-component ref={ref} />;
 * }
 * ```
 */
export function useWebComponentProps<T extends HTMLElement>(
    elementRef: React.RefObject<T>,
    props: Record<string, any>,
) {
    // Store previous props to detect changes
    const prevPropsRef = useRef<Record<string, any>>({});

    useEffect(() => {
        const element = elementRef.current;
        if (!element) return;

        const prevProps = prevPropsRef.current;

        // Update changed properties
        for (const [key, value] of Object.entries(props)) {
            if (prevProps[key] !== value) {
                // Skip event handlers (handled separately)
                if (key.startsWith("on")) continue;

                // Update property
                (element as any)[key] = value;

                // Also set as attribute for primitive values
                if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
                    element.setAttribute(key, String(value));
                }
            }
        }

        // Remove properties that are no longer present
        for (const key of Object.keys(prevProps)) {
            if (!(key in props)) {
                (element as any)[key] = undefined;
                element.removeAttribute(key);
            }
        }

        // Store current props for next comparison
        prevPropsRef.current = { ...props };
    }, [elementRef, props]);
}
