// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { createRoot, type Root } from "react-dom/client";
import { Provider } from "jotai";

/**
 * renderReactDialog - Utility to render React components as modal dialogs
 *
 * Creates a full-screen container, renders the React component with Jotai
 * provider, and handles cleanup on unmount.
 *
 * @param Component - React component to render
 * @param props - Props to pass to the component
 * @returns Cleanup function to unmount and remove dialog
 *
 * @example
 * ```ts
 * const cleanup = renderReactDialog(PlateauCesiumPickerReact, {
 *   onClose: (result, data) => {
 *     cleanup();
 *     if (result === DialogResult.ok) {
 *       // Handle data
 *     }
 *   }
 * });
 * ```
 */
export function renderReactDialog<P extends object>(
    Component: React.ComponentType<P>,
    props: P,
): () => void {
    // Create a React owner node. Base UI portals the visible dialog to <body>,
    // so this mount point must not cover the app or intercept pointer events.
    const container = document.createElement("div");
    container.style.cssText = `
        position: relative;
        top: 0;
        left: 0;
        width: 0;
        height: 0;
        overflow: visible;
        pointer-events: none;
    `;
    document.body.appendChild(container);

    // Render React component with Jotai provider
    const root: Root = createRoot(container);
    root.render(
        <Provider>
            <Component {...props} />
        </Provider>,
    );

    // Cleanup function
    return () => {
        root.unmount();
        container.remove();
    };
}
