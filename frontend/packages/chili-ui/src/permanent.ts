// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import lottie, { AnimationItem } from "lottie-web";
import { div, span } from "chili-controls";
import { I18n, I18nKeys } from "chili-core";
import style from "./permanent.module.css";

export class Permanent {
    static async show(action: () => Promise<void>, message: I18nKeys, ...args: any[]) {
        let dialog = document.createElement("dialog");
        let animationInstance: AnimationItem | null = null;

        // Create Lottie container
        const lottieContainer = div({
            className: style.lottieContainer,
        });

        dialog.appendChild(
            div(
                { className: style.container },
                lottieContainer,
                span({
                    className: style.message,
                    textContent: I18n.translate(message, ...args),
                }),
            ),
        );
        document.body.appendChild(dialog);
        dialog.showModal();

        // Load and play Lottie animation
        try {
            animationInstance = lottie.loadAnimation({
                container: lottieContainer,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/loading_building.json",
            });
        } catch (error) {
            console.error("Failed to load Lottie animation:", error);
            // Fallback: show CSS spinner
            lottieContainer.className = style.loading;
            lottieContainer.style.animation = `${style.circle} infinite 0.75s linear`;
        }

        action().finally(() => {
            // Clean up animation
            if (animationInstance) {
                animationInstance.destroy();
            }
            dialog.remove();
        });
    }
}
