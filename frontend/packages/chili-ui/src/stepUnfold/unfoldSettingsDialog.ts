// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { button, div, h2, input, label, option, select, span } from "chili-controls";
import { UnfoldOptions } from "chili-core";
import style from "./unfoldSettingsDialog.module.css";

type SourceUnits = NonNullable<UnfoldOptions["units"]>;
type MergeMode = NonNullable<UnfoldOptions["mergeMode"]>;

export interface StepUnfoldSettingsDialogContext {
    selectedCount?: number;
}

export class StepUnfoldSettingsDialog {
    private constructor() {}

    public static show(
        defaults: UnfoldOptions,
        context: StepUnfoldSettingsDialogContext = {},
    ): Promise<UnfoldOptions | undefined> {
        return new Promise((resolve) => {
            const dialog = document.createElement("dialog");
            dialog.className = style.dialog;

            const unitsSelect = select(
                { className: style.select },
                option({ value: "m", textContent: "m - PLATEAU / CityGML" }),
                option({ value: "mm", textContent: "mm - CAD / STEP" }),
                option({ value: "cm", textContent: "cm" }),
            );
            unitsSelect.value = defaults.units ?? "mm";

            const pageFormatSelect = select(
                { className: style.select },
                option({ value: "A4", textContent: "A4" }),
                option({ value: "A3", textContent: "A3" }),
                option({ value: "Letter", textContent: "Letter" }),
            );
            pageFormatSelect.value = defaults.pageFormat ?? "A4";

            const pageOrientationSelect = select(
                { className: style.select },
                option({ value: "portrait", textContent: "縦" }),
                option({ value: "landscape", textContent: "横" }),
            );
            pageOrientationSelect.value = defaults.pageOrientation ?? "portrait";

            const layoutModeSelect = select(
                { className: style.select },
                option({ value: "paged", textContent: "ページ分割" }),
                option({ value: "canvas", textContent: "キャンバス" }),
            );
            layoutModeSelect.value = defaults.layoutMode ?? "paged";

            const mergeModeSelect = select(
                { className: style.select },
                option({ value: "improved", textContent: "改善版（推奨）" }),
                option({ value: "legacy", textContent: "旧方式" }),
            );
            mergeModeSelect.value = defaults.mergeMode ?? "improved";

            const scaleSelect = select(
                { className: style.select },
                option({ value: "fitPage", textContent: "この紙で最大" }),
                option({ value: "150", textContent: "1:150 日本N" }),
                option({ value: "160", textContent: "1:160 N" }),
                option({ value: "148", textContent: "1:148 UK N" }),
                option({ value: "100", textContent: "1:100" }),
                option({ value: "200", textContent: "1:200" }),
                option({ value: "custom", textContent: "カスタム" }),
            );

            const customScaleInput = input({
                className: style.numberInput,
                type: "number",
                min: "1",
                step: "1",
                value: String(defaults.scale ?? 150),
            });

            const knownScale = defaults.scaleMode === "fitPage" ? "fitPage" : String(defaults.scale ?? 150);
            const hasPreset = Array.from(scaleSelect.options).some((item) => item.value === knownScale);
            scaleSelect.value = hasPreset ? knownScale : "custom";

            const customScaleField = this.field("分母", customScaleInput);
            const pageSettings = div(
                { className: style.inlineFields },
                this.field("用紙", pageFormatSelect),
                this.field("向き", pageOrientationSelect),
            );

            const updateControlState = () => {
                const isCanvas = layoutModeSelect.value === "canvas";
                const isCustomScale = scaleSelect.value === "custom";
                pageFormatSelect.disabled = isCanvas;
                pageOrientationSelect.disabled = isCanvas;
                customScaleInput.disabled = !isCustomScale;
                customScaleField.hidden = !isCustomScale;
                pageSettings.hidden = isCanvas;
            };

            const close = (result?: UnfoldOptions) => {
                dialog.remove();
                resolve(result);
            };

            scaleSelect.onchange = updateControlState;
            layoutModeSelect.onchange = updateControlState;

            dialog.addEventListener("close", () => close());
            dialog.addEventListener("click", (event) => {
                if (event.target === dialog) {
                    dialog.close();
                }
            });

            const confirmButton = button({
                className: `${style.button} ${style.primaryButton}`,
                textContent: "展開",
                onclick: () => {
                    const scaleMode = scaleSelect.value === "fitPage" ? "fitPage" : "fixed";
                    const scale =
                        scaleSelect.value === "custom"
                            ? Number(customScaleInput.value)
                            : Number(scaleSelect.value);

                    close({
                        ...defaults,
                        units: unitsSelect.value as SourceUnits,
                        scaleMode,
                        scale: Number.isFinite(scale) && scale > 0 ? scale : 150,
                        layoutMode: layoutModeSelect.value as "canvas" | "paged",
                        pageFormat: pageFormatSelect.value as "A4" | "A3" | "Letter",
                        pageOrientation: pageOrientationSelect.value as "portrait" | "landscape",
                        mergeMode: mergeModeSelect.value as MergeMode,
                    });
                },
            });

            const cancelButton = button({
                className: style.button,
                textContent: "キャンセル",
                onclick: () => dialog.close(),
            });

            dialog.appendChild(
                div(
                    { className: style.root },
                    div(
                        { className: style.header },
                        div(
                            { className: style.titleBlock },
                            h2({ className: style.title, textContent: "展開図設定" }),
                            span({
                                className: style.subtitle,
                                textContent: `${context.selectedCount ?? 0}個のモデル`,
                            }),
                        ),
                    ),
                    div(
                        { className: style.form },
                        this.field("縮尺", scaleSelect),
                        customScaleField,
                        pageSettings,
                        div(
                            { className: style.advanced },
                            div({ className: style.sectionLabel, textContent: "詳細" }),
                            div(
                                { className: style.inlineFields },
                                this.field("単位", unitsSelect),
                                this.field("結合", mergeModeSelect),
                            ),
                            this.field("出力", layoutModeSelect),
                        ),
                    ),
                    div({ className: style.actions }, cancelButton, confirmButton),
                ),
            );

            document.body.appendChild(dialog);
            updateControlState();
            dialog.showModal();
        });
    }

    private static field(title: string, control: HTMLElement) {
        return label(
            { className: style.field },
            span({ className: style.label, textContent: title }),
            control,
        );
    }
}
