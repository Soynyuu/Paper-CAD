// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { command, IApplication, ICommand } from "chili-core";
import { UnitSettings } from "chili-ui/src/property/unitSettings";

@command({
    key: "settings.units",
    icon: "icon-settings",
})
export class UnitSettingsCommand implements ICommand {
    async execute(application: IApplication): Promise<void> {
        const dialog = document.createElement("dialog");
        dialog.style.padding = "0";
        dialog.style.border = "1px solid #333";
        dialog.style.borderRadius = "4px";
        dialog.style.backgroundColor = "#2b2b2b";
        dialog.style.color = "#e0e0e0";

        const unitSettings = new UnitSettings();
        dialog.appendChild(unitSettings);

        const closeButton = document.createElement("button");
        closeButton.textContent = "✕";
        closeButton.style.position = "absolute";
        closeButton.style.top = "8px";
        closeButton.style.right = "8px";
        closeButton.style.background = "transparent";
        closeButton.style.border = "none";
        closeButton.style.color = "#e0e0e0";
        closeButton.style.fontSize = "18px";
        closeButton.style.cursor = "pointer";
        closeButton.onclick = () => dialog.close();
        dialog.appendChild(closeButton);

        document.body.appendChild(dialog);
        dialog.showModal();

        dialog.addEventListener("close", () => {
            dialog.remove();
        });

        // Close dialog when clicking outside
        dialog.addEventListener("click", (e) => {
            if (e.target === dialog) {
                dialog.close();
            }
        });
    }
}
