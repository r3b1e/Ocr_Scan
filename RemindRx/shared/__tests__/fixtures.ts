import { DoseUnit, FrequencyType, Medication, MedicationStatus, MedicationType } from '../types';

export const TZ = 'Asia/Kolkata';
/** Instant for a wall-clock time in TZ (IST = UTC+5:30, no DST). */
export const ist = (iso: string, hh: number, mm = 0) => new Date(`${iso}T${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:00+05:30`);

export const med = (over: Partial<Medication> = {}): Medication => ({
    id: 'm1',
    name: 'Metformin',
    type: MedicationType.Tablet,
    startDate: '2026-10-01',
    endDate: '2026-10-31',
    quantityPerDose: 1,
    doseUnit: DoseUnit.Tablet,
    frequencyType: FrequencyType.OnceDaily,
    frequencyConfig: { timesPerDay: 1 },
    scheduleTimes: [{ hour: 8, minute: 0 }],
    remindersEnabled: true,
    reminderLeadMinutes: 0,
    reminderMode: 'notification',
    mealRelation: 'after',
    createdAt: '2026-09-30T00:00:00.000Z',
    updatedAt: '2026-09-30T00:00:00.000Z',
    status: MedicationStatus.Active,
    ...over,
});
