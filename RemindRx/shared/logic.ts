/**
 * Pure logic for the Add Medication flow: frequency → schedule derivation,
 * smart default times, type→unit linking, validation, and finalisation into a
 * persistence-ready `Medication`. No React, no storage.
 */
import {
    ALL_UNITS,
    DECIMAL_UNITS,
    MAX_COURSE_DAYS,
    MAX_NAME_LENGTH,
    MULTI_DAILY_MAX,
    MULTI_DAILY_MIN,
    TYPE_UNIT_CONFIG,
    WEEKDAY_LABELS,
} from './catalog';
import {
    DoseUnit,
    FrequencyConfig,
    FrequencyType,
    Medication,
    MedicationDraft,
    MedicationStatus,
    MedicationType,
    TimeOfDay,
} from './types';

// ── Time helpers ────────────────────────────────────────────────────────────

export const toMinutes = (t: TimeOfDay) => t.hour * 60 + t.minute;

export const fromMinutes = (m: number): TimeOfDay => {
    const clamped = ((Math.round(m) % 1440) + 1440) % 1440;
    return { hour: Math.floor(clamped / 60), minute: clamped % 60 };
};

export const formatTime = (t: TimeOfDay): string => {
    const period = t.hour < 12 ? 'AM' : 'PM';
    const h12 = t.hour % 12 === 0 ? 12 : t.hour % 12;
    return `${h12}:${String(t.minute).padStart(2, '0')} ${period}`;
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const formatDateShort = (d: Date) => `${MONTHS[d.getMonth()]} ${d.getDate()}`;
export const toISODate = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
};
/** Parse a yyyy-mm-dd string as a LOCAL calendar date (no TZ shift). */
export const parseISODateLocal = (iso: string): Date => {
    const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
};
export const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
export const addDays = (d: Date, n: number) => {
    const r = startOfDay(d);
    r.setDate(r.getDate() + n);
    return r;
};
export const daysBetween = (a: Date, b: Date) =>
    Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / 86_400_000);

/** First day of the current month (earliest selectable date). */
export const currentMonthStart = (today: Date = new Date()): Date =>
    new Date(today.getFullYear(), today.getMonth(), 1);

/** Last day of next month (latest selectable date — "one month forward, whole month"). */
export const nextMonthEnd = (today: Date = new Date()): Date =>
    new Date(today.getFullYear(), today.getMonth() + 2, 0);

// ── Frequency → schedule ────────────────────────────────────────────────────

/** How many intake times a given frequency requires per active day. */
export const timesPerDayFor = (type: FrequencyType, config: FrequencyConfig): number => {
    switch (type) {
        case FrequencyType.OnceDaily:
            return 1;
        case FrequencyType.TwiceDaily:
            return 2;
        case FrequencyType.ThriceDaily:
            return 3;
        case FrequencyType.MultiDaily:
            return clamp(config.multiCount ?? MULTI_DAILY_MIN, MULTI_DAILY_MIN, MULTI_DAILY_MAX);
        // Day-based modes take one intake per occurrence.
        case FrequencyType.SpecificDays:
        case FrequencyType.EveryXDays:
        case FrequencyType.DayOfMonth:
            return 1;
        default:
            return 1;
    }
};

/**
 * Smart defaults: spread N times evenly between 08:00 and 22:00 (waking hours).
 * N=1 → 09:00. N=3 → 08:00, 15:00, 22:00.
 */
export const defaultTimes = (n: number): TimeOfDay[] => {
    if (n <= 1) return [{ hour: 9, minute: 0 }];
    const start = 8 * 60;
    const end = 22 * 60;
    const step = (end - start) / (n - 1);
    return Array.from({ length: n }, (_, i) => fromMinutes(start + i * step));
};

/**
 * Re-size the schedule-time list to `n` entries, preserving any user-set times
 * where indices overlap and only adding/removing the difference.
 */
export const resizeTimes = (existing: TimeOfDay[], n: number): TimeOfDay[] => {
    const defaults = defaultTimes(n);
    return defaults.map((d, i) => existing[i] ?? d);
};

// ── Type → unit dynamic link ────────────────────────────────────────────────

/** Unit list for a type: preferred units first, then the rest of the catalog. */
/**
 * The type's suggested units (its `preferred` list, catalog order) and every
 * other unit, split so pickers can label the two groups. `unitsForType` is the
 * same ordering flattened.
 */
export const splitUnitsForType = (type: MedicationType): { suggested: DoseUnit[]; others: DoseUnit[] } => {
    const rule = TYPE_UNIT_CONFIG[type];
    const suggested = rule ? rule.preferred.filter(u => ALL_UNITS.includes(u)) : [];
    const seen = new Set(suggested);
    return { suggested, others: ALL_UNITS.filter(u => !seen.has(u)) };
};

export const unitsForType = (type: MedicationType): DoseUnit[] => {
    const { suggested, others } = splitUnitsForType(type);
    return [...suggested, ...others];
};

export const defaultUnitForType = (type: MedicationType): DoseUnit =>
    TYPE_UNIT_CONFIG[type]?.default ?? DoseUnit.Tablet;

/**
 * After a type change, decide the unit. The full catalog is always valid, but a
 * "relevant" unit is the type's preferred set. If the current unit is not in the
 * preferred set, fall back to the type default and report the change so the UI
 * can inform the user.
 */
export const reconcileUnit = (
    type: MedicationType,
    currentUnit: DoseUnit,
): { unit: DoseUnit; changed: boolean } => {
    const rule = TYPE_UNIT_CONFIG[type];
    if (rule && rule.preferred.includes(currentUnit)) {
        return { unit: currentUnit, changed: false };
    }
    return { unit: defaultUnitForType(type), changed: true };
};

// ── Frequency summary label (shown on the form row) ─────────────────────────

export const frequencySummary = (type: FrequencyType, config: FrequencyConfig): string => {
    switch (type) {
        case FrequencyType.OnceDaily:
            return '1 time, Daily';
        case FrequencyType.TwiceDaily:
            return '2 times, Daily';
        case FrequencyType.ThriceDaily:
            return '3 times, Daily';
        case FrequencyType.MultiDaily:
            return `${config.multiCount ?? MULTI_DAILY_MIN} times, Daily`;
        case FrequencyType.SpecificDays: {
            const days = (config.weekdays ?? []).slice().sort((a, b) => a - b);
            if (days.length === 0) return 'Specific days';
            if (days.length === 7) return 'Every day';
            return days.map(d => WEEKDAY_LABELS[d]).join(', ');
        }
        case FrequencyType.EveryXDays: {
            const n = config.intervalDays ?? 2;
            return n === 1 ? 'Every day' : `Every ${n} days`;
        }
        case FrequencyType.DayOfMonth:
            return `Monthly · day ${config.dayOfMonth ?? 1}`;
        default:
            return '';
    }
};

/** Compact frequency label for list/schedule rows (e.g. "Daily", "Weekly"). */
export const frequencyShortLabel = (type: FrequencyType, config: FrequencyConfig): string => {
    switch (type) {
        case FrequencyType.SpecificDays:
            return 'Weekly';
        case FrequencyType.EveryXDays: {
            const n = config.intervalDays ?? 2;
            return n === 1 ? 'Daily' : `Every ${n} days`;
        }
        case FrequencyType.DayOfMonth:
            return 'Monthly';
        default:
            return 'Daily';
    }
};

// ── Validation ──────────────────────────────────────────────────────────────

export interface ValidationResult {
    /** Blocking errors keyed by field; Done is disabled while non-empty. */
    errors: Partial<Record<string, string>>;
    /** Non-blocking warnings keyed by field. */
    warnings: Partial<Record<string, string>>;
}

const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

/** Collapse runs of whitespace and trim. */
export const normaliseName = (raw: string) => raw.replace(/\s+/g, ' ').trim();

export const validateDraft = (
    draft: MedicationDraft,
    opts: { existingActiveNames?: string[] } = {},
): ValidationResult => {
    const errors: Partial<Record<string, string>> = {};
    const warnings: Partial<Record<string, string>> = {};

    // Name
    const name = normaliseName(draft.name);
    if (!name) {
        errors.name = 'Enter a medication name';
    } else if (name.length > MAX_NAME_LENGTH) {
        errors.name = `Keep the name under ${MAX_NAME_LENGTH} characters`;
    } else if (
        opts.existingActiveNames?.some(
            n => normaliseName(n).toLowerCase() === name.toLowerCase() && n !== draft.id,
        )
    ) {
        warnings.name = 'You already have an active medication with this name';
    }

    // Dates
    const span = daysBetween(draft.startDate, draft.endDate);
    if (span < 0) {
        errors.dates = 'End date must be on or after the start date';
    } else if (span > MAX_COURSE_DAYS) {
        errors.dates = `Course can’t exceed ${MAX_COURSE_DAYS} days`;
    }
    if (daysBetween(new Date(), draft.endDate) < 0) {
        warnings.dates = 'This course ends in the past';
    }

    // Dose quantity
    const qtyRaw = draft.quantityPerDose.trim();
    const qty = Number(qtyRaw);
    if (!qtyRaw || Number.isNaN(qty)) {
        errors.quantity = 'Enter a dose amount';
    } else if (qty <= 0) {
        errors.quantity = 'Dose must be greater than 0';
    } else if (qty > 9999) {
        errors.quantity = 'Dose amount looks too large';
    } else if (!DECIMAL_UNITS.has(draft.doseUnit) && !Number.isInteger(qty)) {
        errors.quantity = `${draft.doseUnit} doses must be whole numbers`;
    }

    // Frequency mode-specific
    const cfg = draft.frequencyConfig;
    switch (draft.frequencyType) {
        case FrequencyType.MultiDaily:
            if (
                cfg.multiCount == null ||
                cfg.multiCount < MULTI_DAILY_MIN ||
                cfg.multiCount > MULTI_DAILY_MAX
            ) {
                errors.frequency = `Pick between ${MULTI_DAILY_MIN} and ${MULTI_DAILY_MAX} times a day`;
            }
            break;
        case FrequencyType.SpecificDays:
            if (!cfg.weekdays || cfg.weekdays.length === 0) {
                errors.frequency = 'Select at least one day of the week';
            }
            break;
        case FrequencyType.EveryXDays:
            if (cfg.intervalDays == null || cfg.intervalDays < 1) {
                errors.frequency = 'Interval must be at least 1 day';
            }
            break;
        case FrequencyType.DayOfMonth:
            if (cfg.dayOfMonth == null || cfg.dayOfMonth < 1 || cfg.dayOfMonth > 31) {
                errors.frequency = 'Day of month must be 1–31';
            } else if (cfg.dayOfMonth > 28) {
                warnings.frequency = 'Short months will use their last day';
            }
            break;
        default:
            break;
    }

    // Schedule times
    const required = timesPerDayFor(draft.frequencyType, cfg);
    if (draft.scheduleTimes.length !== required || draft.scheduleTimes.some(t => t == null)) {
        errors.times = `Set all ${required} schedule time${required > 1 ? 's' : ''}`;
    } else {
        const seen = new Set<number>();
        for (const t of draft.scheduleTimes) {
            const m = toMinutes(t);
            if (seen.has(m)) {
                warnings.times = 'Two intakes are set to the same time';
                break;
            }
            seen.add(m);
        }
    }

    return { errors, warnings };
};

export const hasErrors = (r: ValidationResult) => Object.keys(r.errors).length > 0;

// ── Draft factory + finalisation ────────────────────────────────────────────

/** A blank draft seeded to match the sample (start today, end +10 days). */
export const createEmptyDraft = (): MedicationDraft => {
    const today = startOfDay(new Date());
    return {
        name: '',
        type: MedicationType.Tablet,
        startDate: today,
        endDate: addDays(today, 10),
        quantityPerDose: '1',
        doseUnit: DoseUnit.Tablet,
        frequencyType: FrequencyType.OnceDaily,
        frequencyConfig: { timesPerDay: 1 },
        scheduleTimes: defaultTimes(1),
        remindersEnabled: true,
        reminderLeadMinutes: 0,
        reminderMode: 'notification',
        mealRelation: 'any',
    };
};

/** Pre-fill a draft from an existing medication (Edit mode). */
export const draftFromMedication = (m: Medication): MedicationDraft => ({
    id: m.id,
    name: m.name,
    type: m.type,
    startDate: parseISODateLocal(m.startDate),
    endDate: parseISODateLocal(m.endDate),
    quantityPerDose: String(m.quantityPerDose),
    doseUnit: m.doseUnit,
    frequencyType: m.frequencyType,
    frequencyConfig: m.frequencyConfig,
    scheduleTimes: m.scheduleTimes,
    remindersEnabled: m.remindersEnabled,
    reminderLeadMinutes: m.reminderLeadMinutes,
    reminderMode: m.reminderMode ?? 'notification',
    mealRelation: m.mealRelation ?? 'any',
    createdAt: m.createdAt,
    status: m.status,
});

const uuid = (): string => {
    // RFC4122-ish v4 without external deps; ids only need to be unique on this device.
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
};

/**
 * Finalise a (validated) draft into a persistence-ready Medication. The caller
 * owns saving; this only builds the in-memory object. Re-uses id/createdAt in
 * Edit mode so the same record updates.
 */
export const buildMedication = (draft: MedicationDraft): Medication => {
    const now = new Date().toISOString();
    const cfg: FrequencyConfig = {
        ...draft.frequencyConfig,
        timesPerDay: timesPerDayFor(draft.frequencyType, draft.frequencyConfig),
    };
    return {
        id: draft.id ?? uuid(),
        name: normaliseName(draft.name),
        type: draft.type,
        startDate: toISODate(draft.startDate),
        endDate: toISODate(draft.endDate),
        quantityPerDose: Number(draft.quantityPerDose),
        doseUnit: draft.doseUnit,
        frequencyType: draft.frequencyType,
        frequencyConfig: cfg,
        scheduleTimes: draft.scheduleTimes,
        remindersEnabled: draft.remindersEnabled,
        reminderLeadMinutes: draft.reminderLeadMinutes,
        reminderMode: draft.reminderMode,
        mealRelation: draft.mealRelation ?? 'any',
        createdAt: draft.createdAt ?? now,
        updatedAt: now,
        status: draft.status ?? MedicationStatus.Active,
    };
};
