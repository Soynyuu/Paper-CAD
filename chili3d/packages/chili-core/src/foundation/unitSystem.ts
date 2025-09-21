// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

export enum LengthUnit {
    Millimeter = "mm",
    Centimeter = "cm",
    Meter = "m",
    Inch = "in",
    Foot = "ft",
}

export enum AngleUnit {
    Degree = "°",
    Radian = "rad",
}

export class UnitSystem {
    private static readonly LENGTH_CONVERSIONS: Record<LengthUnit, number> = {
        [LengthUnit.Millimeter]: 1,
        [LengthUnit.Centimeter]: 10,
        [LengthUnit.Meter]: 1000,
        [LengthUnit.Inch]: 25.4,
        [LengthUnit.Foot]: 304.8,
    };

    private static readonly ANGLE_CONVERSIONS: Record<AngleUnit, number> = {
        [AngleUnit.Degree]: 1,
        [AngleUnit.Radian]: 180 / Math.PI,
    };

    static convertLength(value: number, from: LengthUnit, to: LengthUnit): number {
        if (from === to) return value;
        const mm = value * this.LENGTH_CONVERSIONS[from];
        return mm / this.LENGTH_CONVERSIONS[to];
    }

    static convertAngle(value: number, from: AngleUnit, to: AngleUnit): number {
        if (from === to) return value;
        const degrees = value * this.ANGLE_CONVERSIONS[from];
        return degrees / this.ANGLE_CONVERSIONS[to];
    }

    static formatLength(value: number, unit: LengthUnit, precision: number = 2): string {
        return `${value.toFixed(precision)} ${unit}`;
    }

    static formatAngle(value: number, unit: AngleUnit, precision: number = 2): string {
        return `${value.toFixed(precision)}${unit}`;
    }

    static parseLength(input: string, defaultUnit: LengthUnit): { value: number; unit: LengthUnit } | null {
        const trimmed = input.trim();
        const match = trimmed.match(/^(-?\d+\.?\d*)\s*([a-zA-Z]*)$/);

        if (!match) return null;

        const value = parseFloat(match[1]);
        if (isNaN(value)) return null;

        const unitStr = match[2].toLowerCase();
        let unit: LengthUnit;

        switch (unitStr) {
            case "mm":
            case "":
                unit = defaultUnit;
                break;
            case "cm":
                unit = LengthUnit.Centimeter;
                break;
            case "m":
                unit = LengthUnit.Meter;
                break;
            case "in":
            case "inch":
            case "inches":
                unit = LengthUnit.Inch;
                break;
            case "ft":
            case "foot":
            case "feet":
                unit = LengthUnit.Foot;
                break;
            default:
                unit = defaultUnit;
        }

        return { value, unit };
    }

    static parseAngle(input: string, defaultUnit: AngleUnit): { value: number; unit: AngleUnit } | null {
        const trimmed = input.trim();
        const match = trimmed.match(/^(-?\d+\.?\d*)\s*([°a-zA-Z]*)$/);

        if (!match) return null;

        const value = parseFloat(match[1]);
        if (isNaN(value)) return null;

        const unitStr = match[2].toLowerCase();
        let unit: AngleUnit;

        switch (unitStr) {
            case "°":
            case "deg":
            case "degree":
            case "degrees":
            case "":
                unit = defaultUnit;
                break;
            case "rad":
            case "radian":
            case "radians":
                unit = AngleUnit.Radian;
                break;
            default:
                unit = defaultUnit;
        }

        return { value, unit };
    }

    static getAllLengthUnits(): LengthUnit[] {
        return Object.values(LengthUnit);
    }

    static getAllAngleUnits(): AngleUnit[] {
        return Object.values(AngleUnit);
    }

    static getLengthUnitLabel(unit: LengthUnit): string {
        switch (unit) {
            case LengthUnit.Millimeter:
                return "unit.millimeter";
            case LengthUnit.Centimeter:
                return "unit.centimeter";
            case LengthUnit.Meter:
                return "unit.meter";
            case LengthUnit.Inch:
                return "unit.inch";
            case LengthUnit.Foot:
                return "unit.foot";
        }
    }

    static getAngleUnitLabel(unit: AngleUnit): string {
        switch (unit) {
            case AngleUnit.Degree:
                return "unit.degree";
            case AngleUnit.Radian:
                return "unit.radian";
        }
    }
}
