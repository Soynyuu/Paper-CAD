// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import styles from "./Loading.module.css";

export interface LoadingProps {
    message?: string;
}

/**
 * Loading - Centered loading indicator overlay
 *
 * Displayed while tilesets are being loaded.
 */
export function Loading({ message = "Loading..." }: LoadingProps) {
    return (
        <div className={styles.loading}>
            <span>{message}</span>
        </div>
    );
}
