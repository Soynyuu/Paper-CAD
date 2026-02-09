// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React, { useEffect, useRef, useState } from "react";
import lottie, { AnimationItem } from "lottie-web";
import styles from "./PlateauSearchLoading.module.css";

interface PlateauSearchLoadingProps {
    message?: string;
    minimal?: boolean;
}

/**
 * Search-only loading indicator for PLATEAU building search.
 *
 * The animation source is extracted from `woman-driving-car.lottie` and
 * served as JSON for lottie-web runtime compatibility.
 */
export function PlateauSearchLoading({
    message = "建物を検索中...",
    minimal = false,
}: PlateauSearchLoadingProps) {
    const animationContainerRef = useRef<HTMLDivElement | null>(null);
    const [animationFailed, setAnimationFailed] = useState(false);

    useEffect(() => {
        const container = animationContainerRef.current;
        if (!container) return;

        let animation: AnimationItem | null = null;
        try {
            animation = lottie.loadAnimation({
                container,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/animations/woman-driving-car.json",
            });
        } catch (error) {
            console.warn("[PlateauSearchLoading] Failed to load lottie animation:", error);
            setAnimationFailed(true);
        }

        return () => {
            animation?.destroy();
        };
    }, []);

    return (
        <div className={minimal ? styles.minimalWrapper : styles.wrapper} aria-live="polite">
            {animationFailed ? (
                <div
                    className={`${styles.fallbackSpinner} ${
                        minimal ? styles.fallbackSpinnerMinimal : ""
                    }`}
                />
            ) : (
                <div
                    ref={animationContainerRef}
                    className={minimal ? styles.minimalAnimation : styles.animation}
                />
            )}
            {!minimal && <div className={styles.message}>{message}</div>}
        </div>
    );
}
