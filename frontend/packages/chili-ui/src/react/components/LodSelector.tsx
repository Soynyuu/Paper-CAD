// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import React from "react";
import styles from "./LodSelector.module.css";

/** LOD level value: null means "auto" (backend fallback LOD3→LOD2→LOD1) */
export type LodLevel = "LOD1" | "LOD2" | "LOD3" | null;

export interface LodSelectorProps {
    selectedLod: LodLevel;
    onChange: (lod: LodLevel) => void;
    disabled?: boolean;
}

interface LodOption {
    value: LodLevel;
    label: string;
    sub: string;
}

const LOD_OPTIONS: LodOption[] = [
    { value: null, label: "自動", sub: "auto" },
    { value: "LOD1", label: "かんたん", sub: "LOD1" },
    { value: "LOD2", label: "標準", sub: "LOD2" },
    { value: "LOD3", label: "詳細", sub: "LOD3" },
];

/**
 * LodSelector - Segmented control for selecting LOD level (assembly difficulty).
 *
 * Lower LOD = simpler geometry = easier papercraft assembly.
 * - null (自動): Backend decides using LOD3→LOD2→LOD1 fallback
 * - LOD1: Simple block models (easy)
 * - LOD2: PLATEAU standard (medium)
 * - LOD3: Architectural detail (hard)
 */
export function LodSelector({ selectedLod, onChange, disabled }: LodSelectorProps) {
    return (
        <div className={styles.lodSelector}>
            <div className={styles.lodLabel}>組み立て難易度</div>
            <div className={styles.segmentGroup}>
                {LOD_OPTIONS.map((option) => {
                    const isActive = selectedLod === option.value;
                    return (
                        <button
                            key={option.sub}
                            type="button"
                            className={`${styles.segment} ${isActive ? styles.segmentActive : ""}`}
                            onClick={() => onChange(option.value)}
                            disabled={disabled}
                            aria-pressed={isActive}
                            title={`${option.label} (${option.sub})`}
                        >
                            <span className={styles.segmentName}>{option.label}</span>
                            <span className={styles.segmentSub}>{option.sub}</span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
