// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { atom } from "jotai";
import type { PickedBuilding } from "chili-cesium";

/**
 * Currently selected city key (e.g., "tokyo-chiyoda")
 */
export const currentCityAtom = atom<string>("");

/**
 * Array of selected buildings
 */
export const selectedBuildingsAtom = atom<PickedBuilding[]>([]);

/**
 * Loading state for tileset operations
 */
export const loadingAtom = atom<boolean>(false);

/**
 * Current loading message
 */
export const loadingMessageAtom = atom<string>("");

/**
 * Camera position for the current city
 * Used to restore camera when switching cities
 */
export const cameraPositionAtom = atom<{
    lat: number;
    lng: number;
    height: number;
} | null>(null);

/**
 * Highlighted building IDs (visual feedback on hover)
 */
export const highlightedBuildingIdsAtom = atom<Set<string>>(new Set());

/**
 * Derived atom: Number of selected buildings
 */
export const selectedCountAtom = atom((get) => get(selectedBuildingsAtom).length);

/**
 * Derived atom: Is import button enabled?
 */
export const canImportAtom = atom((get) => get(selectedBuildingsAtom).length > 0);
