/**
 * Catalog data for the Add Medication flow: the type grid, the unit list, the
 * type→unit dynamic-link config, and the frequency-mode descriptors.
 *
 * Everything here is data — no UI. The type→unit relationship is expressed in a
 * SINGLE editable map (`TYPE_UNIT_CONFIG`) so the behaviour can be tuned in one
 * place without touching components.
 */
import { DoseUnit, FrequencyType, MedicationType } from './types';

/**
 * Lucide icon names (identical in lucide-react and lucide-react-native). Each
 * app maps these to its own icon components; shared/ stays UI-free.
 */
export type IconKey =
    | 'Pill' | 'Tablets' | 'FlaskConical' | 'Droplets' | 'SprayCan' | 'Container'
    | 'Droplet' | 'Syringe' | 'Package' | 'Wind' | 'Candy' | 'Leaf' | 'TestTube'
    | 'Brush' | 'Bath' | 'Cookie';

export interface TypeEntry {
    type: MedicationType;
    label: string;
    icon: IconKey;
}

/** Ordered grid of selectable medication types, each with its closest icon. */
export const MEDICATION_TYPES: TypeEntry[] = [
    { type: MedicationType.Tablet, label: 'Tablet', icon: 'Tablets' },
    { type: MedicationType.Capsule, label: 'Capsule', icon: 'Pill' },
    { type: MedicationType.Liquid, label: 'Liquid', icon: 'FlaskConical' },
    { type: MedicationType.Lotion, label: 'Lotion', icon: 'Droplets' },
    { type: MedicationType.Spray, label: 'Spray', icon: 'SprayCan' },
    { type: MedicationType.Ointment, label: 'Ointment', icon: 'Container' },
    { type: MedicationType.Drops, label: 'Drops', icon: 'Droplet' },
    { type: MedicationType.Gel, label: 'Gel', icon: 'Droplets' },
    { type: MedicationType.Suppository, label: 'Suppository', icon: 'Pill' },
    { type: MedicationType.Injection, label: 'Injection', icon: 'Syringe' },
    { type: MedicationType.Cream, label: 'Cream', icon: 'Container' },
    { type: MedicationType.Powder, label: 'Powder', icon: 'Package' },
    { type: MedicationType.Foam, label: 'Foam', icon: 'Droplets' },
    { type: MedicationType.Inhaler, label: 'Inhaler', icon: 'Wind' },
    { type: MedicationType.Gummy, label: 'Gummy', icon: 'Candy' },
    { type: MedicationType.NasalCannula, label: 'Nasal Cannula', icon: 'Wind' },
    { type: MedicationType.Herb, label: 'Herb', icon: 'Leaf' },
    { type: MedicationType.Ampoule, label: 'Ampoule', icon: 'TestTube' },
    { type: MedicationType.Softgel, label: 'Softgel', icon: 'Pill' },
    { type: MedicationType.Toothpaste, label: 'Toothpaste', icon: 'Brush' },
    { type: MedicationType.ChewyBite, label: 'Chewy bite', icon: 'Cookie' },
    { type: MedicationType.Shampoo, label: 'Shampoo', icon: 'Bath' },
];

/** Lookup of type → icon for use outside the grid (e.g. summary chips). */
export const TYPE_ICON: Record<MedicationType, IconKey> =
    MEDICATION_TYPES.reduce((acc, e) => {
        acc[e.type] = e.icon;
        return acc;
    }, {} as Record<MedicationType, IconKey>);

export const MEAL_RELATIONS: { value: 'before' | 'after' | 'with' | 'any'; label: string }[] = [
    { value: 'before', label: 'Before food' },
    { value: 'with', label: 'With food' },
    { value: 'after', label: 'After food' },
    { value: 'any', label: 'Anytime' },
];

export const LEAD_OPTIONS = [0, 5, 10, 15, 30];

/** Full, ordered unit catalog. Every unit is always selectable. */
export const ALL_UNITS: DoseUnit[] = [
    DoseUnit.Tablet,
    DoseUnit.Capsule,
    DoseUnit.Teaspoon,
    DoseUnit.Tablespoon,
    DoseUnit.Pump,
    DoseUnit.ML,
    DoseUnit.Suppository,
    DoseUnit.Puff,
    DoseUnit.Ampoule,
    DoseUnit.Packet,
    DoseUnit.Pessary,
    DoseUnit.Piece,
    DoseUnit.Inch,
    DoseUnit.Fingertip,
    DoseUnit.Device,
    DoseUnit.Application,
    DoseUnit.Spray,
    DoseUnit.Drop,
    DoseUnit.Unit,
    DoseUnit.Injection,
    DoseUnit.Scoop,
    DoseUnit.Patch,
    DoseUnit.Inhalation,
    DoseUnit.EA,
    DoseUnit.Gummy,
    DoseUnit.IU,
    DoseUnit.MG,
    DoseUnit.Cup,
    DoseUnit.L,
    DoseUnit.KG,
    DoseUnit.LB,
    DoseUnit.Minute,
    DoseUnit.Ounce,
];

/**
 * Dynamic link: per type, the default unit plus the units to surface first.
 * The remaining units stay accessible, appended after `preferred`.
 * THIS is the one place to edit type→unit behaviour.
 */
export interface TypeUnitRule {
    default: DoseUnit;
    preferred: DoseUnit[];
}

export const TYPE_UNIT_CONFIG: Record<MedicationType, TypeUnitRule> = {
    [MedicationType.Tablet]: { default: DoseUnit.Tablet, preferred: [DoseUnit.Tablet, DoseUnit.MG, DoseUnit.Piece, DoseUnit.Packet] },
    [MedicationType.Capsule]: { default: DoseUnit.Capsule, preferred: [DoseUnit.Capsule, DoseUnit.MG, DoseUnit.Piece] },
    [MedicationType.Softgel]: { default: DoseUnit.Capsule, preferred: [DoseUnit.Capsule, DoseUnit.MG, DoseUnit.Piece] },
    [MedicationType.Liquid]: { default: DoseUnit.ML, preferred: [DoseUnit.ML, DoseUnit.Teaspoon, DoseUnit.Tablespoon, DoseUnit.Cup, DoseUnit.Drop] },
    [MedicationType.Drops]: { default: DoseUnit.Drop, preferred: [DoseUnit.Drop, DoseUnit.ML] },
    [MedicationType.Spray]: { default: DoseUnit.Spray, preferred: [DoseUnit.Spray, DoseUnit.Puff, DoseUnit.Pump] },
    [MedicationType.NasalCannula]: { default: DoseUnit.Spray, preferred: [DoseUnit.Spray, DoseUnit.Puff, DoseUnit.Pump] },
    [MedicationType.Inhaler]: { default: DoseUnit.Puff, preferred: [DoseUnit.Puff, DoseUnit.Inhalation] },
    [MedicationType.Injection]: { default: DoseUnit.ML, preferred: [DoseUnit.ML, DoseUnit.Unit, DoseUnit.IU, DoseUnit.Injection] },
    [MedicationType.Ampoule]: { default: DoseUnit.ML, preferred: [DoseUnit.ML, DoseUnit.Unit, DoseUnit.IU, DoseUnit.Injection, DoseUnit.Ampoule] },
    [MedicationType.Cream]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Fingertip, DoseUnit.Inch, DoseUnit.Pump] },
    [MedicationType.Ointment]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Fingertip, DoseUnit.Inch, DoseUnit.Pump] },
    [MedicationType.Gel]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Fingertip, DoseUnit.Inch, DoseUnit.Pump] },
    [MedicationType.Lotion]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Fingertip, DoseUnit.Inch, DoseUnit.Pump] },
    [MedicationType.Foam]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Fingertip, DoseUnit.Inch, DoseUnit.Pump] },
    [MedicationType.Shampoo]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Pump, DoseUnit.ML] },
    [MedicationType.Toothpaste]: { default: DoseUnit.Application, preferred: [DoseUnit.Application, DoseUnit.Inch, DoseUnit.Fingertip] },
    [MedicationType.Powder]: { default: DoseUnit.Scoop, preferred: [DoseUnit.Scoop, DoseUnit.Packet, DoseUnit.MG] },
    [MedicationType.Suppository]: { default: DoseUnit.Suppository, preferred: [DoseUnit.Suppository, DoseUnit.Pessary] },
    [MedicationType.Gummy]: { default: DoseUnit.Gummy, preferred: [DoseUnit.Gummy, DoseUnit.Piece] },
    [MedicationType.ChewyBite]: { default: DoseUnit.Gummy, preferred: [DoseUnit.Gummy, DoseUnit.Piece] },
    [MedicationType.Herb]: { default: DoseUnit.MG, preferred: [DoseUnit.MG, DoseUnit.Scoop, DoseUnit.Teaspoon] },
};

/**
 * Units that accept fractional doses (liquids / weights). Countable units stay
 * integer-only. Used by validation to allow or reject decimals.
 */
export const DECIMAL_UNITS = new Set<DoseUnit>([
    DoseUnit.Teaspoon,
    DoseUnit.Tablespoon,
    DoseUnit.ML,
    DoseUnit.Cup,
    DoseUnit.L,
    DoseUnit.Ounce,
    DoseUnit.MG,
    DoseUnit.KG,
    DoseUnit.LB,
    DoseUnit.IU,
    DoseUnit.Inch,
    DoseUnit.Fingertip,
    DoseUnit.Scoop,
    DoseUnit.Drop,
    DoseUnit.Unit,
    DoseUnit.Minute,
]);

export interface FrequencyMode {
    type: FrequencyType;
    label: string;
    /** Short helper shown under the label in the picker. */
    hint: string;
}

export const FREQUENCY_MODES: FrequencyMode[] = [
    { type: FrequencyType.OnceDaily, label: '1 time, Daily', hint: 'Once every day' },
    { type: FrequencyType.TwiceDaily, label: '2 times, Daily', hint: 'Twice every day' },
    { type: FrequencyType.ThriceDaily, label: '3 times, Daily', hint: 'Three times every day' },
    { type: FrequencyType.MultiDaily, label: 'X times, Daily', hint: '4 to 10 times every day' },
    { type: FrequencyType.SpecificDays, label: 'Specific days of week', hint: 'e.g. Mon, Wed, Fri' },
    { type: FrequencyType.EveryXDays, label: 'Every X days', hint: 'Repeat on an interval' },
    { type: FrequencyType.DayOfMonth, label: 'Monthly', hint: 'On a set day each month' },
];

export const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const MULTI_DAILY_MIN = 4;
export const MULTI_DAILY_MAX = 10;
export const MAX_COURSE_DAYS = 365;
export const MAX_NAME_LENGTH = 60;
