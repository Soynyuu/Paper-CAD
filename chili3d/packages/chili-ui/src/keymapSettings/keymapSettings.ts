// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, input, label, option, select, span } from "chili-controls";
import { I18n, IApplication, Logger } from "chili-core";
import { HotkeyService, KeymapPreset, KeymapPresetManager } from "chili";
import style from "./keymapSettings.module.css";

export class KeymapSettings extends HTMLElement {
    private app?: IApplication;
    private hotkeyService?: HotkeyService;
    private presetManager?: KeymapPresetManager;
    private presetSelect?: HTMLSelectElement;
    private descriptionDiv?: HTMLDivElement;
    private keymapListDiv?: HTMLDivElement;
    private searchInput?: HTMLInputElement;
    private currentPreset?: KeymapPreset;

    constructor(app?: IApplication) {
        super();
        this.app = app;
        this.initializeService();
        this.render();
    }

    private initializeService(): void {
        if (!this.app) {
            // Try to get app from global context if not provided
            const globalApp = (window as any).app as IApplication;
            if (globalApp) {
                this.app = globalApp;
            }
        }

        if (this.app) {
            // Get HotkeyService from app's services
            const services = (this.app as any).services as any[];
            this.hotkeyService = services?.find((s: any) => s instanceof HotkeyService) as HotkeyService;

            if (this.hotkeyService) {
                this.presetManager = this.hotkeyService.getPresetManager();
                if (this.presetManager) {
                    // Subscribe to preset changes
                    this.presetManager.onPresetChange(this.onPresetChanged.bind(this));
                    this.currentPreset = this.presetManager.getCurrentPreset();
                }
            }
        }

        if (!this.presetManager) {
            Logger.warn("KeymapSettings: Could not initialize preset manager");
        }
    }

    private render(): void {
        // Clear all children
        while (this.firstChild) {
            this.removeChild(this.firstChild);
        }

        const container = div({
            className: style.container,
        });

        // Title
        container.appendChild(
            div({
                className: style.title,
                textContent: I18n.translate("settings.keymap") || "Keyboard Shortcuts",
            }),
        );

        // Preset selector section
        const presetSection = div({ className: style.section });
        presetSection.appendChild(
            div({
                className: style.sectionTitle,
                textContent: I18n.translate("settings.keymap.preset") || "Preset",
            }),
        );

        const selectorContainer = div({ className: style.presetSelector });
        this.presetSelect = select({
            className: style.presetSelect,
            onchange: this.onPresetSelectChange.bind(this),
        });

        this.updatePresetOptions();
        selectorContainer.appendChild(this.presetSelect);
        presetSection.appendChild(selectorContainer);

        // Preset description
        this.descriptionDiv = div({
            className: style.presetDescription,
        });
        this.updateDescription();
        presetSection.appendChild(this.descriptionDiv);

        container.appendChild(presetSection);

        // Keymap list section
        const keymapSection = div({ className: style.section });
        keymapSection.appendChild(
            div({
                className: style.sectionTitle,
                textContent: I18n.translate("settings.keymap.shortcuts") || "Shortcuts",
            }),
        );

        // Search box
        this.searchInput = input({
            type: "text",
            className: style.searchBox,
            placeholder: I18n.translate("settings.keymap.search") || "Search shortcuts...",
            oninput: this.onSearchInput.bind(this),
        });
        keymapSection.appendChild(this.searchInput);

        // Keymap list
        this.keymapListDiv = div({
            className: style.keymapList,
        });
        this.updateKeymapList();
        keymapSection.appendChild(this.keymapListDiv);

        container.appendChild(keymapSection);

        // Action buttons
        const buttonGroup = div({ className: style.buttonGroup });

        // Export button
        buttonGroup.appendChild(
            button({
                className: style.button + " " + style.buttonSecondary,
                textContent: I18n.translate("settings.keymap.export") || "Export",
                onclick: this.exportPreset.bind(this),
            }),
        );

        // Import button
        const fileInput = input({
            type: "file",
            accept: ".json",
            className: style.fileInput,
            onchange: this.importPreset.bind(this),
        });
        buttonGroup.appendChild(fileInput);

        buttonGroup.appendChild(
            button({
                className: style.button + " " + style.buttonSecondary,
                textContent: I18n.translate("settings.keymap.import") || "Import",
                onclick: () => fileInput.click(),
            }),
        );

        // Reset to default button
        buttonGroup.appendChild(
            button({
                className: style.button + " " + style.buttonDanger,
                textContent: I18n.translate("settings.keymap.reset") || "Reset to Default",
                onclick: this.resetToDefault.bind(this),
            }),
        );

        container.appendChild(buttonGroup);

        this.appendChild(container);
    }

    private updatePresetOptions(): void {
        if (!this.presetSelect || !this.presetManager) return;

        // Clear all options
        while (this.presetSelect.firstChild) {
            this.presetSelect.removeChild(this.presetSelect.firstChild);
        }

        const presets = this.presetManager.getPresets();
        const currentPreset = this.presetManager.getCurrentPreset();

        presets.forEach((preset) => {
            const opt = option({
                value: preset.id,
                textContent: preset.name + (preset.isBuiltin ? "" : " (Custom)"),
                selected: preset.id === currentPreset.id,
            });
            this.presetSelect!.appendChild(opt);
        });
    }

    private updateDescription(): void {
        if (!this.descriptionDiv || !this.currentPreset) return;

        this.descriptionDiv.textContent = this.currentPreset.description;
    }

    private updateKeymapList(searchTerm: string = ""): void {
        if (!this.keymapListDiv || !this.currentPreset) return;

        // Clear all children
        while (this.keymapListDiv.firstChild) {
            this.keymapListDiv.removeChild(this.keymapListDiv.firstChild);
        }

        const keymap = this.currentPreset.keymap;
        const entries = Object.entries(keymap);

        // Filter by search term
        const filtered = searchTerm
            ? entries.filter(
                  ([key, command]) =>
                      key.toLowerCase().includes(searchTerm.toLowerCase()) ||
                      command.toLowerCase().includes(searchTerm.toLowerCase()),
              )
            : entries;

        if (filtered.length === 0) {
            this.keymapListDiv.appendChild(
                div({
                    className: style.emptyState,
                    textContent: I18n.translate("settings.keymap.noResults") || "No shortcuts found",
                }),
            );
            return;
        }

        // Sort by key
        filtered.sort(([a], [b]) => a.localeCompare(b));

        filtered.forEach(([key, command]) => {
            const item = div({ className: style.keymapItem });

            // Format key display
            const keyDisplay = this.formatKeyDisplay(key);
            item.appendChild(
                span({
                    className: style.keyCombo,
                    textContent: keyDisplay,
                }),
            );

            // Format command display
            const commandDisplay = this.formatCommandDisplay(command);
            item.appendChild(
                span({
                    className: style.commandName,
                    textContent: commandDisplay,
                }),
            );

            this.keymapListDiv!.appendChild(item);
        });
    }

    private formatKeyDisplay(key: string): string {
        // Convert key combinations to display format
        return key
            .replace(/ctrl\+/g, "Ctrl+")
            .replace(/shift\+/g, "Shift+")
            .replace(/alt\+/g, "Alt+")
            .replace(/cmd\+/g, "Cmd+")
            .replace(/ /g, "Space");
    }

    private formatCommandDisplay(command: string): string {
        // Try to get translated command name
        const i18nKey = `command.${command}` as any;
        const translated = I18n.translate(i18nKey);

        // If translation exists and is different from the key, use it
        if (translated && translated !== i18nKey) {
            return translated;
        }

        // Otherwise, format the command string
        return command
            .split(".")
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" → ");
    }

    private async onPresetSelectChange(event: Event): Promise<void> {
        const select = event.target as HTMLSelectElement;
        const presetId = select.value;

        if (this.hotkeyService) {
            const success = await this.hotkeyService.switchPreset(presetId);
            if (success && this.presetManager) {
                this.currentPreset = this.presetManager.getCurrentPreset();
                this.updateDescription();
                this.updateKeymapList();
            } else {
                // Revert selection on failure
                this.updatePresetOptions();
            }
        }
    }

    private onSearchInput(event: Event): void {
        const input = event.target as HTMLInputElement;
        this.updateKeymapList(input.value);
    }

    private onPresetChanged(preset: KeymapPreset): void {
        this.currentPreset = preset;
        this.updatePresetOptions();
        this.updateDescription();
        this.updateKeymapList();
    }

    private exportPreset(): void {
        if (!this.presetManager || !this.currentPreset) return;

        const json = this.presetManager.exportPreset(this.currentPreset.id);
        if (!json) return;

        // Create download link
        const blob = new Blob([json], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `keymap-${this.currentPreset.id}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    private async importPreset(event: Event): Promise<void> {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0];
        if (!file || !this.presetManager) return;

        try {
            const text = await file.text();
            const success = await this.presetManager.importPreset(text);

            if (success) {
                this.updatePresetOptions();
                // Show success message
                Logger.info("Preset imported successfully");
            } else {
                // Show error message
                Logger.error("Failed to import preset");
            }
        } catch (error) {
            Logger.error("Error reading file:", error);
        }

        // Reset file input
        input.value = "";
    }

    private async resetToDefault(): Promise<void> {
        if (!this.presetManager) return;

        // Confirm action
        const confirmed = confirm(
            I18n.translate("settings.keymap.resetConfirm") ||
                "Are you sure you want to reset to default keyboard shortcuts?",
        );

        if (confirmed) {
            await this.presetManager.resetToDefault();
        }
    }
}

// Register custom element
customElements.define("keymap-settings", KeymapSettings);
