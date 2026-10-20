/**
 * Turn one extracted medication into a MedicationDraft prefill for MedForm.
 * Only fields the extraction knows about are set; everything else keeps the
 * draft defaults, and the user confirms the form before anything is saved.
 */
import {
    addDaysISO, createEmptyDraft, defaultUnitForType, DoseUnit, FrequencyType, MedicationType, parseISODateLocal, resizeTimes,
    todayISO, type MedicationDraft, type TimeOfDay,
} from '@shared/index';
import type { ExtractedMedication, Form, Slot, Timing } from '../api/extract';

const SLOT_TIMES: Record<Slot, TimeOfDay> = {
    morning: { hour: 8, minute: 0 },
    afternoon: { hour: 13, minute: 0 },
    evening: { hour: 18, minute: 0 },
    night: { hour: 21, minute: 0 },
};

const FORM_TYPES: Record<Form, MedicationType> = {
    tablet: MedicationType.Tablet,
    capsule: MedicationType.Capsule,
    syrup: MedicationType.Liquid,
    injection: MedicationType.Injection,
    drops: MedicationType.Drops,
    cream: MedicationType.Cream,
    inhaler: MedicationType.Spray,
    powder: MedicationType.Powder,
    other: MedicationType.Tablet,
};

const MEAL: Record<Timing, MedicationDraft['mealRelation']> = {
    before_food: 'before',
    empty_stomach: 'before',
    after_food: 'after',
    with_food: 'with',
    bedtime: 'any',
    any: 'any',
};

/** "1" → 1, "1/2" → 0.5, "5 ml" → 5, "2 tsp" → 2; unknown → 1. */
export function parseDoseQuantity(dose: string | null): number {
    if (!dose) return 1;
    const text = dose.trim().toLowerCase();
    const fraction = /^(\d+)\s*\/\s*(\d+)/.exec(text);
    if (fraction) return Math.round((Number(fraction[1]) / Number(fraction[2])) * 100) / 100 || 1;
    if (text.startsWith('half')) return 0.5;
    const number = /^(\d+(?:\.\d+)?)/.exec(text);
    return number ? Number(number[1]) || 1 : 1;
}

function unitFor(type: MedicationType, dose: string | null): DoseUnit {
    const text = (dose ?? '').toLowerCase();
    if (/\bml\b/.test(text)) return DoseUnit.ML;
    if (/\btsp|teaspoon/.test(text)) return DoseUnit.Teaspoon;
    if (/\btbsp|tablespoon/.test(text)) return DoseUnit.Tablespoon;
    if (/\bpuff/.test(text)) return DoseUnit.Puff;
    if (/\bcap/.test(text)) return DoseUnit.Capsule;
    if (/\btab/.test(text)) return DoseUnit.Tablet;
    return defaultUnitForType(type);
}

/** Evenly spaced times between 08:00 and 21:00 when the slots are unknown. */
function spreadTimes(n: number): TimeOfDay[] {
    if (n <= 1) return [SLOT_TIMES.morning];
    const start = 8 * 60;
    const span = 21 * 60 - start;
    return Array.from({ length: n }, (_, i) => {
        const minutes = Math.round(start + (span * i) / (n - 1));
        return { hour: Math.floor(minutes / 60), minute: minutes % 60 };
    });
}

export function displayName(m: ExtractedMedication): string {
    const base = (m.brand_matched ?? m.name).trim();
    return m.strength && !base.toLowerCase().includes(m.strength.toLowerCase()) ? `${base} ${m.strength}` : base;
}

export function prescriptionToDraft(m: ExtractedMedication): MedicationDraft {
    const draft = createEmptyDraft();
    const type = m.form ? FORM_TYPES[m.form] : MedicationType.Tablet;
    const times = m.frequency.slots.length ? m.frequency.slots.map(s => SLOT_TIMES[s]) : spreadTimes(m.frequency.times_per_day ?? 1);
    const n = Math.max(1, times.length);
    const frequencyType = n > 1 ? FrequencyType.MultiDaily : FrequencyType.OnceDaily;
    const frequencyConfig = n > 1 ? { ...draft.frequencyConfig, multiCount: n, timesPerDay: n } : { ...draft.frequencyConfig, timesPerDay: 1 };
    const start = todayISO();

    return {
        ...draft,
        name: displayName(m),
        type,
        doseUnit: unitFor(type, m.dose),
        quantityPerDose: String(parseDoseQuantity(m.dose)),
        frequencyType,
        frequencyConfig,
        scheduleTimes: resizeTimes(times, n),
        mealRelation: m.timing ? MEAL[m.timing] : draft.mealRelation,
        remindersEnabled: !m.frequency.as_needed,
        startDate: parseISODateLocal(start),
        endDate: parseISODateLocal(addDaysISO(start, Math.max(0, (m.duration_days ?? 10) - 1))),
    };
}
