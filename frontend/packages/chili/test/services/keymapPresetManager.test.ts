// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { KeymapPresetManager } from "../../src/services/keymapPresetManager";
import {
    KeymapPreset,
    DefaultPreset,
    Fusion360Preset,
    BlenderPreset,
} from "../../src/services/keymapPreset";
import { HotkeyMap } from "../../src/services/hotkeyService";

describe("KeymapPresetManager", () => {
    let manager: KeymapPresetManager;

    beforeEach(() => {
        manager = new KeymapPresetManager();
    });

    describe("Built-in presets", () => {
        it("should have default preset initialized", () => {
            const presets = manager.getPresets();
            expect(presets.length).toBeGreaterThan(0);

            const defaultPreset = presets.find((p) => p.id === "default");
            expect(defaultPreset).toBeDefined();
            expect(defaultPreset?.name).toBe("Default");
        });

        it("should have Fusion 360 preset", () => {
            const presets = manager.getPresets();
            const fusion360Preset = presets.find((p) => p.id === "fusion360");
            expect(fusion360Preset).toBeDefined();
            expect(fusion360Preset?.name).toBe("Fusion 360");
        });

        it("should have Blender preset", () => {
            const presets = manager.getPresets();
            const blenderPreset = presets.find((p) => p.id === "blender");
            expect(blenderPreset).toBeDefined();
            expect(blenderPreset?.name).toBe("Blender");
        });
    });

    describe("Current preset management", () => {
        it("should return default preset as current initially", () => {
            const current = manager.getCurrentPreset();
            expect(current.id).toBe("default");
        });

        it("should switch to different preset", async () => {
            const result = await manager.setCurrentPreset("fusion360");
            expect(result).toBe(true);

            const current = manager.getCurrentPreset();
            expect(current.id).toBe("fusion360");
        });

        it("should return false when switching to non-existent preset", async () => {
            const result = await manager.setCurrentPreset("non-existent");
            expect(result).toBe(false);

            // Should stay on current preset
            const current = manager.getCurrentPreset();
            expect(current.id).toBe("default");
        });

        it("should get current keymap", () => {
            const keymap = manager.getCurrentKeymap();
            expect(keymap).toBeDefined();
            expect(keymap["Delete"]).toBe("modify.deleteNode");
        });
    });

    describe("Custom presets", () => {
        const customPreset: KeymapPreset = {
            id: "custom1",
            name: "My Custom",
            description: "Custom preset",
            keymap: {
                a: "create.arc",
                d: "modify.deleteNode",
            },
            isBuiltin: false,
        };

        it("should save custom preset", async () => {
            const result = await manager.saveCustomPreset(customPreset);
            expect(result).toBe(true);

            const presets = manager.getPresets();
            const saved = presets.find((p) => p.id === "custom1");
            expect(saved).toBeDefined();
            expect(saved?.name).toBe("My Custom");
        });

        it("should not allow saving built-in preset", async () => {
            const builtinPreset = { ...customPreset, isBuiltin: true };
            const result = await manager.saveCustomPreset(builtinPreset);
            expect(result).toBe(false);
        });

        it("should delete custom preset", async () => {
            await manager.saveCustomPreset(customPreset);
            const result = await manager.deleteCustomPreset("custom1");
            expect(result).toBe(true);

            const presets = manager.getPresets();
            const deleted = presets.find((p) => p.id === "custom1");
            expect(deleted).toBeUndefined();
        });

        it("should not allow deleting built-in preset", async () => {
            const result = await manager.deleteCustomPreset("default");
            expect(result).toBe(false);

            const presets = manager.getPresets();
            const defaultPreset = presets.find((p) => p.id === "default");
            expect(defaultPreset).toBeDefined();
        });

        it("should switch to default when deleting current custom preset", async () => {
            await manager.saveCustomPreset(customPreset);
            await manager.setCurrentPreset("custom1");

            await manager.deleteCustomPreset("custom1");

            const current = manager.getCurrentPreset();
            expect(current.id).toBe("default");
        });
    });

    describe("Import/Export", () => {
        it("should export preset as JSON", () => {
            const json = manager.exportPreset("default");
            expect(json).toBeDefined();

            const parsed = JSON.parse(json!);
            expect(parsed.id).toBe("default");
            expect(parsed.name).toBe("Default");
        });

        it("should return null when exporting non-existent preset", () => {
            const json = manager.exportPreset("non-existent");
            expect(json).toBeNull();
        });

        it("should import valid preset", async () => {
            const presetData = {
                id: "imported",
                name: "Imported",
                description: "Imported preset",
                keymap: { i: "create.line" },
                isBuiltin: false,
            };

            const json = JSON.stringify(presetData);
            const result = await manager.importPreset(json);
            expect(result).toBe(true);

            const presets = manager.getPresets();
            const imported = presets.find((p) => p.name === "Imported");
            expect(imported).toBeDefined();
            expect(imported?.isBuiltin).toBe(false);
        });

        it("should reject invalid preset format", async () => {
            const invalidJson = JSON.stringify({ invalid: "data" });
            const result = await manager.importPreset(invalidJson);
            expect(result).toBe(false);
        });

        it("should handle import with duplicate ID", async () => {
            const preset = {
                id: "default",
                name: "Duplicate",
                description: "Test",
                keymap: {},
                isBuiltin: false,
            };

            const result = await manager.importPreset(JSON.stringify(preset));
            expect(result).toBe(true);

            const presets = manager.getPresets();
            const imported = presets.find((p) => p.name === "Duplicate");
            expect(imported).toBeDefined();
            expect(imported?.id).not.toBe("default");
        });
    });

    describe("Helper methods", () => {
        it("should reset to default preset", async () => {
            await manager.setCurrentPreset("fusion360");
            await manager.resetToDefault();

            const current = manager.getCurrentPreset();
            expect(current.id).toBe("default");
        });

        it("should create custom preset from current", async () => {
            const keymap: HotkeyMap = { c: "create.circle" };
            const preset = await manager.createCustomFromCurrent("New Custom", "Description", keymap);

            expect(preset).toBeDefined();
            expect(preset.name).toBe("New Custom");
            expect(preset.isBuiltin).toBe(false);
            expect(preset.keymap).toEqual(keymap);

            const presets = manager.getPresets();
            const saved = presets.find((p) => p.id === preset.id);
            expect(saved).toBeDefined();
        });
    });
});
