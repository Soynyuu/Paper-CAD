// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { div, label, option, select, span } from "chili-controls";
import { AngleUnit, Config, I18n, LengthUnit, Localize, UnitSystem } from "chili-core";
import commonStyle from "./common.module.css";
import style from "./input.module.css";

export class UnitSettings extends HTMLElement {
    constructor() {
        super();
        this.className = commonStyle.properties;
        this.initializeUI();
    }

    private initializeUI() {
        const config = Config.instance;

        // Title
        const title = div(
            { className: commonStyle.title },
            span({ textContent: new Localize("unit.settings") }),
        );

        // Length Unit Selection
        const lengthUnitDiv = div(
            { className: commonStyle.panel },
            span({
                className: commonStyle.propertyName,
                textContent: new Localize("unit.lengthUnit"),
            }),
            select(
                {
                    className: style.box,
                    value: config.lengthUnit,
                    onchange: (e) => {
                        config.lengthUnit = (e.target as HTMLSelectElement).value as LengthUnit;
                    },
                },
                ...this.createLengthUnitOptions(),
            ),
        );

        // Angle Unit Selection
        const angleUnitDiv = div(
            { className: commonStyle.panel },
            span({
                className: commonStyle.propertyName,
                textContent: new Localize("unit.angleUnit"),
            }),
            select(
                {
                    className: style.box,
                    value: config.angleUnit,
                    onchange: (e) => {
                        config.angleUnit = (e.target as HTMLSelectElement).value as AngleUnit;
                    },
                },
                ...this.createAngleUnitOptions(),
            ),
        );

        // Length Precision
        const lengthPrecisionDiv = div(
            { className: commonStyle.panel },
            span({
                className: commonStyle.propertyName,
                textContent: new Localize("unit.lengthPrecision"),
            }),
            select(
                {
                    className: style.box,
                    value: String(config.lengthPrecision),
                    onchange: (e) => {
                        config.lengthPrecision = parseInt((e.target as HTMLSelectElement).value);
                    },
                },
                ...this.createPrecisionOptions(),
            ),
        );

        // Angle Precision
        const anglePrecisionDiv = div(
            { className: commonStyle.panel },
            span({
                className: commonStyle.propertyName,
                textContent: new Localize("unit.anglePrecision"),
            }),
            select(
                {
                    className: style.box,
                    value: String(config.anglePrecision),
                    onchange: (e) => {
                        config.anglePrecision = parseInt((e.target as HTMLSelectElement).value);
                    },
                },
                ...this.createPrecisionOptions(),
            ),
        );

        this.append(title, lengthUnitDiv, angleUnitDiv, lengthPrecisionDiv, anglePrecisionDiv);
    }

    private createLengthUnitOptions(): HTMLOptionElement[] {
        const config = Config.instance;
        return UnitSystem.getAllLengthUnits().map((unit) =>
            option({
                value: unit,
                textContent: I18n.translate(UnitSystem.getLengthUnitLabel(unit) as any),
                selected: unit === config.lengthUnit,
            }),
        );
    }

    private createAngleUnitOptions(): HTMLOptionElement[] {
        const config = Config.instance;
        return UnitSystem.getAllAngleUnits().map((unit) =>
            option({
                value: unit,
                textContent: I18n.translate(UnitSystem.getAngleUnitLabel(unit) as any),
                selected: unit === config.angleUnit,
            }),
        );
    }

    private createPrecisionOptions(): HTMLOptionElement[] {
        const options: HTMLOptionElement[] = [];
        for (let i = 0; i <= 6; i++) {
            options.push(
                option({
                    value: String(i),
                    textContent: String(i),
                }),
            );
        }
        return options;
    }
}

customElements.define("chili-unit-settings", UnitSettings);
