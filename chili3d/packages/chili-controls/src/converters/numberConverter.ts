// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { Config, IConverter, LengthUnit, Result, UnitSystem } from "chili-core";

export class NumberConverter implements IConverter<number> {
    private readonly useUnits: boolean;
    private readonly isAngle: boolean;

    constructor(useUnits: boolean = true, isAngle: boolean = false) {
        this.useUnits = useUnits;
        this.isAngle = isAngle;
    }

    convert(value: number): Result<string> {
        if (Number.isNaN(value)) {
            return Result.err("Number is NaN");
        }

        if (!this.useUnits) {
            return Result.ok(String(value));
        }

        const config = Config.instance;
        if (this.isAngle) {
            return Result.ok(UnitSystem.formatAngle(value, config.angleUnit, config.anglePrecision));
        } else {
            const displayValue = UnitSystem.convertLength(value, LengthUnit.Millimeter, config.lengthUnit);
            return Result.ok(
                UnitSystem.formatLength(displayValue, config.lengthUnit, config.lengthPrecision),
            );
        }
    }

    convertBack(value: string): Result<number> {
        if (!this.useUnits) {
            const n = Number(value);
            return Number.isNaN(n) ? Result.err(`${value} can not convert to number`) : Result.ok(n);
        }

        const config = Config.instance;

        if (this.isAngle) {
            const parsed = UnitSystem.parseAngle(value, config.angleUnit);
            if (!parsed) {
                return Result.err(`${value} cannot be converted to angle`);
            }
            const converted = UnitSystem.convertAngle(parsed.value, parsed.unit, config.angleUnit);
            return Result.ok(converted);
        } else {
            const parsed = UnitSystem.parseLength(value, config.lengthUnit);
            if (!parsed) {
                return Result.err(`${value} cannot be converted to length`);
            }
            const internalValue = UnitSystem.convertLength(parsed.value, parsed.unit, LengthUnit.Millimeter);
            return Result.ok(internalValue);
        }
    }
}
