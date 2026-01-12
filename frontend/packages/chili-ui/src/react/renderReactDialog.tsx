// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import { createRoot, type Root } from "react-dom/client";
import { Provider } from "jotai";

/**
 * renderReactDialog - Utility to render React components as modal dialogs
 *
 * Creates a backdrop + container, renders React component with Jotai provider,
 * and handles cleanup on unmount.
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
    // Create backdrop
    const backdrop = document.createElement("div");
    backdrop.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: rgba(0, 0, 0, 0.75);
        backdrop-filter: blur(4px);
        z-index: 9998;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    document.body.appendChild(backdrop);

    // Create container for React component
    const container = document.createElement("div");
    backdrop.appendChild(container);

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
        backdrop.remove();
    };
}
