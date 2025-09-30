// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { CommandKeys, IApplication, IService, IStorage, Logger, PubSub } from "chili-core";
import { KeymapPresetManager } from "./keymapPresetManager";
import { KeymapPreset } from "./keymapPreset";

export interface Keys {
    key: string;
    ctrlKey?: boolean;
    shiftKey?: boolean;
    altKey?: boolean;
}

export interface HotkeyMap {
    [key: string]: CommandKeys;
}

const DefaultKeyMap: HotkeyMap = {
    Delete: "modify.deleteNode",
    Backspace: "modify.deleteNode",
    " ": "special.last",
    Enter: "special.last",
    "ctrl+z": "edit.undo",
    "ctrl+y": "edit.redo",
};

export class HotkeyService implements IService {
    private app?: IApplication;
    private readonly _keyMap = new Map<string, CommandKeys>();
    private presetManager?: KeymapPresetManager;

    constructor() {
        // Initially use default keymap
        this.addMap(DefaultKeyMap);
    }

    register(app: IApplication): void {
        this.app = app;

        // Initialize preset manager with storage
        const storage = (app as any).storage as IStorage | undefined;
        this.presetManager = new KeymapPresetManager(storage);

        // Subscribe to preset changes
        this.presetManager.onPresetChange(this.onPresetChanged.bind(this));

        Logger.info(`${HotkeyService.name} registered`);
    }

    async start(): Promise<void> {
        window.addEventListener("keydown", this.eventHandlerKeyDown);
        window.addEventListener("keydown", this.commandKeyDown);

        // Initialize preset manager and load saved settings
        if (this.presetManager) {
            await this.presetManager.initialize();
            // Apply the saved preset
            const currentPreset = this.presetManager.getCurrentPreset();
            this.applyPreset(currentPreset);
        }

        Logger.info(`${HotkeyService.name} started`);
    }

    stop(): void {
        window.removeEventListener("keydown", this.eventHandlerKeyDown);
        window.removeEventListener("keydown", this.commandKeyDown);
        Logger.info(`${HotkeyService.name} stoped`);
    }

    private readonly eventHandlerKeyDown = (e: KeyboardEvent) => {
        e.preventDefault();
        let visual = this.app?.activeView?.document?.visual;
        let view = this.app?.activeView;
        if (view && visual) {
            visual.eventHandler.keyDown(view, e);
            visual.viewHandler.keyDown(view, e);
            if (this.app!.executingCommand) e.stopImmediatePropagation();
        }
    };

    private readonly commandKeyDown = (e: KeyboardEvent) => {
        e.preventDefault();
        let command = this.getCommand(e);
        if (command !== undefined) {
            PubSub.default.pub("executeCommand", command);
        }
    };

    getKey(keys: Keys): string {
        let key = keys.key;
        if (keys.ctrlKey) key = "ctrl+" + key;
        if (keys.shiftKey) key = "shift+" + key;
        if (keys.altKey) key = "alt+" + key;
        return key;
    }

    map(command: CommandKeys, keys: Keys) {
        let key = this.getKey(keys);
        this._keyMap.set(key, command);
    }

    getCommand(keys: Keys): CommandKeys | undefined {
        let key = this.getKey(keys);
        return this._keyMap.get(key);
    }

    addMap(map: HotkeyMap) {
        let keys = Object.keys(map);
        keys.forEach((key) => {
            this._keyMap.set(key, map[key]);
        });
    }

    /**
     * Clear all key mappings
     */
    clearMap(): void {
        this._keyMap.clear();
    }

    /**
     * Apply a preset to the current keymap
     */
    private applyPreset(preset: KeymapPreset): void {
        this.clearMap();
        this.addMap(preset.keymap);
        Logger.info(`Applied keymap preset: ${preset.name}`);
    }

    /**
     * Handle preset change events
     */
    private onPresetChanged(preset: KeymapPreset): void {
        this.applyPreset(preset);
    }

    /**
     * Get the preset manager
     */
    getPresetManager(): KeymapPresetManager | undefined {
        return this.presetManager;
    }

    /**
     * Switch to a different preset
     */
    async switchPreset(presetId: string): Promise<boolean> {
        if (!this.presetManager) {
            Logger.error("Preset manager not initialized");
            return false;
        }
        return await this.presetManager.setCurrentPreset(presetId);
    }
}
