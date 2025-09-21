// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { CommandKeys } from "chili-core";
import { HotkeyMap } from "./hotkeyService";

/**
 * Represents a keyboard shortcut preset configuration
 */
export interface KeymapPreset {
    /** Unique identifier for the preset */
    id: string;
    /** Display name for the preset */
    name: string;
    /** Description of the preset */
    description: string;
    /** The actual key mappings */
    keymap: HotkeyMap;
    /** Whether this is a built-in preset that cannot be deleted */
    isBuiltin: boolean;
}

/**
 * Default keymap preset matching current behavior
 */
export const DefaultPreset: KeymapPreset = {
    id: "default",
    name: "Default",
    description: "Standard Chili3D keyboard shortcuts",
    keymap: {
        Delete: "modify.deleteNode",
        Backspace: "modify.deleteNode",
        " ": "special.last",
        Enter: "special.last",
        "ctrl+z": "edit.undo",
        "ctrl+y": "edit.redo",
    },
    isBuiltin: true,
};

/**
 * Fusion 360 inspired keymap preset
 */
export const Fusion360Preset: KeymapPreset = {
    id: "fusion360",
    name: "Fusion 360",
    description: "Keyboard shortcuts similar to Fusion 360",
    keymap: {
        // Basic operations
        Delete: "modify.deleteNode",
        Backspace: "modify.deleteNode",
        "ctrl+z": "edit.undo",
        "ctrl+y": "edit.redo",

        // Creation tools
        l: "create.line",
        c: "create.circle",
        r: "create.rect",
        p: "create.polygon",

        // Modification tools
        m: "modify.move",
        f: "modify.fillet",
        e: "create.extrude",

        // View controls
        "shift+f": "act.alignCamera",

        // Measure
        i: "measure.length",
    },
    isBuiltin: true,
};

/**
 * Blender inspired keymap preset
 */
export const BlenderPreset: KeymapPreset = {
    id: "blender",
    name: "Blender",
    description: "Keyboard shortcuts similar to Blender",
    keymap: {
        // Basic operations
        x: "modify.deleteNode",
        Delete: "modify.deleteNode",
        "ctrl+z": "edit.undo",
        "ctrl+shift+z": "edit.redo",

        // Transform operations
        g: "modify.move",
        r: "modify.rotate",

        // Creation (using shift+a menu in Blender, simplified here)
        "shift+a": "create.box",

        // Extrude
        e: "create.extrude",

        // Duplicate
        "shift+d": "create.copyShape",

        // Special command
        " ": "special.last",
    },
    isBuiltin: true,
};

/**
 * Collection of all built-in presets
 */
export const BuiltinPresets: KeymapPreset[] = [DefaultPreset, Fusion360Preset, BlenderPreset];
