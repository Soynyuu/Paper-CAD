// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { Config, IConverter, LengthUnit, Result, UnitSystem } from "chili-core";

export class UnitNumberConverter implements IConverter<number> {
    private readonly isAngle: boolean;

    constructor(isAngle: boolean = false) {
        this.isAngle = isAngle;
    }

    convert(value: number): Result<string> {
        if (Number.isNaN(value)) {
            return Result.err("Number is NaN");
        }

        const config = Config.instance;
        if (this.isAngle) {
            return Result.ok(UnitSystem.formatAngle(value, config.angleUnit, config.anglePrecision));
        } else {
            return Result.ok(UnitSystem.formatLength(value, config.lengthUnit, config.lengthPrecision));
        }
    }

    convertBack(value: string): Result<number> {
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
