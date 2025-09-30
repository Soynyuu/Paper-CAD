// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { Config, IConverter, LengthUnit, Result, UnitSystem, XY, XYZ } from "chili-core";

export class XYConverter implements IConverter<XY> {
    private readonly useUnits: boolean;

    constructor(useUnits: boolean = true) {
        this.useUnits = useUnits;
    }

    convert(value: XY) {
        if (!this.useUnits) {
            return Result.ok(`${value.x},${value.y}`);
        }

        const config = Config.instance;
        const xDisplay = UnitSystem.convertLength(value.x, LengthUnit.Millimeter, config.lengthUnit);
        const yDisplay = UnitSystem.convertLength(value.y, LengthUnit.Millimeter, config.lengthUnit);
        const xStr = xDisplay.toFixed(config.lengthPrecision);
        const yStr = yDisplay.toFixed(config.lengthPrecision);
        return Result.ok(`${xStr},${yStr} ${config.lengthUnit}`);
    }

    convertBack(value: string): Result<XY> {
        if (!this.useUnits) {
            const vs = value.split(",").map(Number).filter(isFinite);
            return vs.length === 2
                ? Result.ok(new XY(vs[0], vs[1]))
                : Result.err(`${value} convert to XY error`);
        }

        const config = Config.instance;
        // Remove unit suffix if present
        const cleanValue = value.replace(/\s*[a-zA-Z]+\s*$/, "");
        const parts = cleanValue.split(",").map((s) => s.trim());

        if (parts.length !== 2) {
            return Result.err(`${value} convert to XY error`);
        }

        const values: number[] = [];
        for (const part of parts) {
            const parsed = UnitSystem.parseLength(part, config.lengthUnit);
            if (!parsed) {
                return Result.err(`${value} convert to XY error`);
            }
            const internalValue = UnitSystem.convertLength(parsed.value, parsed.unit, LengthUnit.Millimeter);
            values.push(internalValue);
        }

        return Result.ok(new XY(values[0], values[1]));
    }
}

export class XYZConverter implements IConverter<XYZ> {
    private readonly useUnits: boolean;

    constructor(useUnits: boolean = true) {
        this.useUnits = useUnits;
    }

    convert(value: XYZ) {
        if (!this.useUnits) {
            return Result.ok(`${value.x},${value.y},${value.z}`);
        }

        const config = Config.instance;
        const xDisplay = UnitSystem.convertLength(value.x, LengthUnit.Millimeter, config.lengthUnit);
        const yDisplay = UnitSystem.convertLength(value.y, LengthUnit.Millimeter, config.lengthUnit);
        const zDisplay = UnitSystem.convertLength(value.z, LengthUnit.Millimeter, config.lengthUnit);
        const xStr = xDisplay.toFixed(config.lengthPrecision);
        const yStr = yDisplay.toFixed(config.lengthPrecision);
        const zStr = zDisplay.toFixed(config.lengthPrecision);
        return Result.ok(`${xStr},${yStr},${zStr} ${config.lengthUnit}`);
    }

    convertBack(value: string): Result<XYZ> {
        if (!this.useUnits) {
            const vs = value.split(",").map(Number).filter(isFinite);
            return vs.length === 3
                ? Result.ok(new XYZ(vs[0], vs[1], vs[2]))
                : Result.err(`${value} convert to XYZ error`);
        }

        const config = Config.instance;
        // Remove unit suffix if present
        const cleanValue = value.replace(/\s*[a-zA-Z]+\s*$/, "");
        const parts = cleanValue.split(",").map((s) => s.trim());

        if (parts.length !== 3) {
            return Result.err(`${value} convert to XYZ error`);
        }

        const values: number[] = [];
        for (const part of parts) {
            const parsed = UnitSystem.parseLength(part, config.lengthUnit);
            if (!parsed) {
                return Result.err(`${value} convert to XYZ error`);
            }
            const internalValue = UnitSystem.convertLength(parsed.value, parsed.unit, LengthUnit.Millimeter);
            values.push(internalValue);
        }

        return Result.ok(new XYZ(values[0], values[1], values[2]));
    }
}
