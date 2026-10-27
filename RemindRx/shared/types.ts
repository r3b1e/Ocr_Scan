/**
 * Add Medication — in-memory data model.
 *
 * Copied from Vivotal.HealthApp src/features/medication/types.ts and kept
 * field-compatible with it. Persistence-agnostic: each app's storage layer
 * saves these objects as JSON on the device.
 */

export enum MedicationType {
    Tablet = 'Tablet',
    Capsule = 'Capsule',
    Liquid = 'Liquid',
    Lotion = 'Lotion',
    Spray = 'Spray',
    Ointment = 'Ointment',
    Drops = 'Drops',
    Gel = 'Gel',
    Suppository = 'Suppository',
    Injection = 'Injection',
    Cream = 'Cream',
    Powder = 'Powder',
    Foam = 'Foam',
    Inhaler = 'Inhaler',
    Gummy = 'Gummy',
    NasalCannula = 'Nasal Cannula',
    Herb = 'Herb',
    Ampoule = 'Ampoule',
    Softgel = 'Softgel',
    Toothpaste = 'Toothpaste',
    ChewyBite = 'Chewy bite',
    Shampoo = 'Shampoo',
}

export enum DoseUnit {
    Tablet = 'Tablet',
    Capsule = 'Capsule',
    Teaspoon = 'Teaspoon',
    Tablespoon = 'Tablespoon',
    Pump = 'Pump',
    ML = 'ML',
    Suppository = 'Suppository',
    Puff = 'Puff',
    Ampoule = 'Ampoule',
    Packet = 'Packet',
    Pessary = 'Pessary',
    Piece = 'Piece',
    Inch = 'Inch',
    Fingertip = 'Fingertip',
    Device = 'Device',
    Application = 'Application',
    Spray = 'Spray',
    Drop = 'Drop',
    Unit = 'Unit',
    Injection = 'Injection',
    Scoop = 'Scoop',
    Patch = 'Patch',
    Inhalation = 'Inhalation',
    EA = 'EA',
    Gummy = 'Gummy',
    IU = 'IU',
    MG = 'MG',
    Cup = 'Cup',
    L = 'L',
    KG = 'KG',
    LB = 'LB',
    Minute = 'Minute',
    Ounce = 'Ounce',
}

export enum FrequencyType {
    /** 1 time, Daily */
    OnceDaily = 'ONCE_DAILY',
    /** 2 times, Daily */
    TwiceDaily = 'TWICE_DAILY',
    /** 3 times, Daily */
    ThriceDaily = 'THRICE_DAILY',
    /** X times, Daily — X in 4..10 */
    MultiDaily = 'MULTI_DAILY',
    /** Specific days of the week */
    SpecificDays = 'SPECIFIC_DAYS',
    /** Every X days */
    EveryXDays = 'EVERY_X_DAYS',
    /** Monthly, on a given day of the month */
    DayOfMonth = 'DAY_OF_MONTH',
}

export enum MedicationStatus {
    Active = 'active',
    Completed = 'completed',
    Paused = 'paused',
    Deleted = 'deleted',
}

/** How a reminder alerts the user. */
export type ReminderMode = 'notification' | 'alarm';

/**
 * Whether a medicine is taken around food.
 *
 * Asked for every medicine added: plenty of tablets do nothing on a
 * full stomach and upset an empty one, the patient has usually been told which,
 * and a reminder that does not say leaves them guessing at the one moment they
 * need to know.
 */
export type MealRelation = 'before' | 'after' | 'with' | 'any';

/** A wall-clock time of day, 24h. */
export interface TimeOfDay {
    hour: number;   // 0..23
    minute: number; // 0..59
}

/** Mode-specific payload for the chosen frequency. */
export interface FrequencyConfig {
    /** Intakes per active day — drives how many Schedule Time slots render. */
    timesPerDay: number;
    /** MULTI_DAILY: the chosen X (4..10). */
    multiCount?: number;
    /** SPECIFIC_DAYS: weekday indices, 0=Sun … 6=Sat. */
    weekdays?: number[];
    /** EVERY_X_DAYS: interval in days (>=1). */
    intervalDays?: number;
    /** DAY_OF_MONTH: 1..31. */
    dayOfMonth?: number;
}

export interface Medication {
    id: string;
    name: string;
    type: MedicationType;
    startDate: string; // ISO yyyy-mm-dd
    endDate: string;   // ISO yyyy-mm-dd
    quantityPerDose: number;
    doseUnit: DoseUnit;
    frequencyType: FrequencyType;
    frequencyConfig: FrequencyConfig;
    scheduleTimes: TimeOfDay[];
    remindersEnabled: boolean;
    reminderLeadMinutes: number;
    reminderMode: ReminderMode;
    /** before | after | with | any — whether it is taken around food. */
    mealRelation?: MealRelation;
    createdAt: string;
    updatedAt: string;
    status: MedicationStatus;
}

/** Draft state held by the form before it is finalised into a Medication. */
export interface MedicationDraft {
    id?: string;
    name: string;
    type: MedicationType;
    startDate: Date;
    endDate: Date;
    quantityPerDose: string; // kept as text while editing
    doseUnit: DoseUnit;
    frequencyType: FrequencyType;
    frequencyConfig: FrequencyConfig;
    scheduleTimes: TimeOfDay[];
    remindersEnabled: boolean;
    reminderLeadMinutes: number;
    reminderMode: ReminderMode;
    mealRelation?: MealRelation;
    createdAt?: string;
    status?: MedicationStatus;
}
