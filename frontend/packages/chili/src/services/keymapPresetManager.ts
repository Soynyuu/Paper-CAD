// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { IStorage, Logger } from "chili-core";
import { HotkeyMap } from "./hotkeyService";
import { KeymapPreset, BuiltinPresets, DefaultPreset } from "./keymapPreset";

export type KeymapPresetChangeCallback = (preset: KeymapPreset) => void;

/**
 * Manages keyboard shortcut presets
 */
export class KeymapPresetManager {
    private readonly presets = new Map<string, KeymapPreset>();
    private currentPresetId: string = "default";
    private storage?: IStorage;
    private readonly storageKey = "keymap-settings";
    private readonly customPresetsKey = "keymap-custom-presets";
    private readonly changeCallbacks: Set<KeymapPresetChangeCallback> = new Set();

    constructor(storage?: IStorage) {
        this.storage = storage;
        this.initializeBuiltinPresets();
    }

    /**
     * Initialize the manager with built-in presets
     */
    private initializeBuiltinPresets(): void {
        BuiltinPresets.forEach((preset) => {
            this.presets.set(preset.id, preset);
        });
    }

    /**
     * Initialize the manager and load saved settings
     */
    async initialize(): Promise<void> {
        if (!this.storage) {
            Logger.warn("KeymapPresetManager: No storage available, settings won't be persisted");
            return;
        }

        try {
            // Load saved preset selection
            const savedSettings = await this.storage.get("chili3d", "settings", this.storageKey);
            if (savedSettings?.currentPresetId) {
                this.currentPresetId = savedSettings.currentPresetId;
            }

            // Load custom presets
            const customPresets = await this.storage.get("chili3d", "settings", this.customPresetsKey);
            if (customPresets && Array.isArray(customPresets)) {
                customPresets.forEach((preset: KeymapPreset) => {
                    if (!preset.isBuiltin) {
                        this.presets.set(preset.id, preset);
                    }
                });
            }

            Logger.info(`KeymapPresetManager initialized with preset: ${this.currentPresetId}`);
        } catch (error) {
            Logger.error("Failed to load keymap settings:", error);
        }
    }

    /**
     * Get all available presets
     */
    getPresets(): KeymapPreset[] {
        return Array.from(this.presets.values());
    }

    /**
     * Get the currently active preset
     */
    getCurrentPreset(): KeymapPreset {
        return this.presets.get(this.currentPresetId) || DefaultPreset;
    }

    /**
     * Get the current hotkey map
     */
    getCurrentKeymap(): HotkeyMap {
        return this.getCurrentPreset().keymap;
    }

    /**
     * Switch to a different preset
     */
    async setCurrentPreset(presetId: string): Promise<boolean> {
        const preset = this.presets.get(presetId);
        if (!preset) {
            Logger.error(`Preset not found: ${presetId}`);
            return false;
        }

        this.currentPresetId = presetId;

        // Save to storage
        if (this.storage) {
            try {
                await this.storage.put("chili3d", "settings", this.storageKey, {
                    currentPresetId: this.currentPresetId,
                });
            } catch (error) {
                Logger.error("Failed to save keymap settings:", error);
            }
        }

        // Notify listeners
        this.notifyChange(preset);
        Logger.info(`Switched to keymap preset: ${preset.name}`);

        return true;
    }

    /**
     * Add or update a custom preset
     */
    async saveCustomPreset(preset: KeymapPreset): Promise<boolean> {
        if (preset.isBuiltin) {
            Logger.error("Cannot modify built-in presets");
            return false;
        }

        this.presets.set(preset.id, preset);

        // Save all custom presets to storage
        if (this.storage) {
            try {
                const customPresets = Array.from(this.presets.values()).filter((p) => !p.isBuiltin);
                await this.storage.put("chili3d", "settings", this.customPresetsKey, customPresets);
                Logger.info(`Saved custom preset: ${preset.name}`);
            } catch (error) {
                Logger.error("Failed to save custom preset:", error);
                return false;
            }
        }

        return true;
    }

    /**
     * Delete a custom preset
     */
    async deleteCustomPreset(presetId: string): Promise<boolean> {
        const preset = this.presets.get(presetId);
        if (!preset) {
            Logger.error(`Preset not found: ${presetId}`);
            return false;
        }

        if (preset.isBuiltin) {
            Logger.error("Cannot delete built-in presets");
            return false;
        }

        // Switch to default if deleting current preset
        if (this.currentPresetId === presetId) {
            await this.setCurrentPreset("default");
        }

        this.presets.delete(presetId);

        // Update storage
        if (this.storage) {
            try {
                const customPresets = Array.from(this.presets.values()).filter((p) => !p.isBuiltin);
                await this.storage.put("chili3d", "settings", this.customPresetsKey, customPresets);
                Logger.info(`Deleted custom preset: ${preset.name}`);
            } catch (error) {
                Logger.error("Failed to update storage after deletion:", error);
                return false;
            }
        }

        return true;
    }

    /**
     * Export a preset as JSON string
     */
    exportPreset(presetId: string): string | null {
        const preset = this.presets.get(presetId);
        if (!preset) {
            Logger.error(`Preset not found: ${presetId}`);
            return null;
        }

        return JSON.stringify(preset, null, 2);
    }

    /**
     * Import a preset from JSON string
     */
    async importPreset(jsonString: string): Promise<boolean> {
        try {
            const preset = JSON.parse(jsonString) as KeymapPreset;

            // Validate preset structure
            if (!preset.id || !preset.name || !preset.keymap) {
                Logger.error("Invalid preset format");
                return false;
            }

            // Mark as custom preset
            preset.isBuiltin = false;

            // Generate unique ID if it conflicts with existing
            if (this.presets.has(preset.id)) {
                preset.id = `${preset.id}_${Date.now()}`;
            }

            return await this.saveCustomPreset(preset);
        } catch (error) {
            Logger.error("Failed to import preset:", error);
            return false;
        }
    }

    /**
     * Reset to default preset
     */
    async resetToDefault(): Promise<void> {
        await this.setCurrentPreset("default");
    }

    /**
     * Create a custom preset from current modifications
     */
    async createCustomFromCurrent(
        name: string,
        description: string,
        keymap: HotkeyMap,
    ): Promise<KeymapPreset> {
        const preset: KeymapPreset = {
            id: `custom_${Date.now()}`,
            name,
            description,
            keymap,
            isBuiltin: false,
        };

        await this.saveCustomPreset(preset);
        return preset;
    }

    /**
     * Subscribe to preset change events
     */
    onPresetChange(callback: KeymapPresetChangeCallback): void {
        this.changeCallbacks.add(callback);
    }

    /**
     * Unsubscribe from preset change events
     */
    offPresetChange(callback: KeymapPresetChangeCallback): void {
        this.changeCallbacks.delete(callback);
    }

    /**
     * Notify all listeners of a preset change
     */
    private notifyChange(preset: KeymapPreset): void {
        this.changeCallbacks.forEach((callback) => {
            try {
                callback(preset);
            } catch (error) {
                Logger.error("Error in preset change callback:", error);
            }
        });
    }
}
