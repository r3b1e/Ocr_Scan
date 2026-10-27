/**
 * Dose log + derived day views + adherence. Pure TS, no storage.
 *
 * Only taken/skipped are stored. upcoming / due / missed are derived from the
 * schedule and the clock, so nothing has to run in the background to keep the
 * log correct.
 */
import { Medication, MedicationStatus, TimeOfDay } from './types';
import { firesOnISO } from './reminderLogic';
import { addDaysISO, dateISOIn, zonedTimeToUtc } from './zonedTime';

export type DoseStatus = 'taken' | 'skipped';
export type DoseState = 'upcoming' | 'due' | 'taken' | 'skipped' | 'missed';

export interface DoseLog {
    /** doseId(medId, dateISO, slot) */
    id: string;
    medId: string;
    dateISO: string;
    /** Index into med.scheduleTimes at the time of logging. */
    slot: number;
    /** ISO instant the dose was scheduled for (kept even if times are edited later). */
    scheduledAt: string;
    status: DoseStatus;
    /** ISO instant the user logged it. */
    at: string;
}

export interface DoseView {
    id: string;
    med: Medication;
    dateISO: string;
    slot: number;
    time: TimeOfDay;
    scheduledAt: Date;
    log?: DoseLog;
    state: DoseState;
}

export interface DayStat {
    dateISO: string;
    taken: number;
    /** Doses whose outcome is known: taken + skipped + missed. */
    counted: number;
}

export interface Adherence {
    /** taken / counted over the window, 0..100, or null when nothing was due. */
    pct: number | null;
    taken: number;
    scheduled: number;
    /** Consecutive days (back from today) where every due dose was taken. */
    streak: number;
    days: DayStat[];
}

export const MISSED_AFTER_MIN = 60;
export const SNOOZE_MIN = 10;

export const doseId = (medId: string, dateISO: string, slot: number) => `${medId}:${dateISO}:${slot}`;

export const deviceTimeZone = (): string => {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
};

export const todayISO = (now: Date = new Date(), tz: string = deviceTimeZone()) => dateISOIn(now, tz);

const timeOf = (d: Date, tz: string): TimeOfDay => {
    const p: Record<string, string> = {};
    for (const x of new Intl.DateTimeFormat('en-CA', { timeZone: tz, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(d)) p[x.type] = x.value;
    return { hour: +p.hour % 24, minute: +p.minute };
};

const stateFor = (scheduledAt: Date, log: DoseLog | undefined, now: Date): DoseState => {
    if (log) return log.status;
    const ms = scheduledAt.getTime();
    if (now.getTime() < ms) return 'upcoming';
    if (now.getTime() < ms + MISSED_AFTER_MIN * 60_000) return 'due';
    return 'missed';
};

/**
 * Every dose on `dateISO`: scheduled doses of active medicines, plus logged
 * doses that no longer match the schedule (medicine paused, deleted or its
 * times edited). Doses scheduled before the medicine was added are left out
 * unless logged, so a new medicine never starts with a "missed" dose.
 */
export const dosesForDay = (
    meds: Medication[],
    logs: DoseLog[],
    dateISO: string,
    now: Date = new Date(),
    tz: string = deviceTimeZone(),
): DoseView[] => {
    const logById = new Map(logs.filter(l => l.dateISO === dateISO).map(l => [l.id, l] as const));
    const out = new Map<string, DoseView>();

    for (const med of meds) {
        if (med.status !== MedicationStatus.Active || !firesOnISO(med, dateISO)) continue;
        const created = Date.parse(med.createdAt);
        med.scheduleTimes.forEach((time, slot) => {
            const id = doseId(med.id, dateISO, slot);
            const log = logById.get(id);
            const scheduledAt = log ? new Date(log.scheduledAt) : zonedTimeToUtc(dateISO, tz, time.hour, time.minute);
            if (!log && scheduledAt.getTime() < created) return;
            out.set(id, { id, med, dateISO, slot, time: log ? timeOf(scheduledAt, tz) : time, scheduledAt, log, state: stateFor(scheduledAt, log, now) });
        });
    }

    const medById = new Map(meds.map(m => [m.id, m] as const));
    for (const log of logById.values()) {
        if (out.has(log.id)) continue;
        const med = medById.get(log.medId);
        if (!med) continue;
        const scheduledAt = new Date(log.scheduledAt);
        out.set(log.id, { id: log.id, med, dateISO, slot: log.slot, time: timeOf(scheduledAt, tz), scheduledAt, log, state: log.status });
    }

    return [...out.values()].sort((a, b) => a.scheduledAt.getTime() - b.scheduledAt.getTime() || a.med.name.localeCompare(b.med.name));
};

const statFor = (views: DoseView[], dateISO: string): DayStat => {
    const done = views.filter(v => v.state === 'taken' || v.state === 'skipped' || v.state === 'missed');
    return { dateISO, taken: done.filter(v => v.state === 'taken').length, counted: done.length };
};

/** Adherence over the last `days` days (today included) plus the current streak. */
export const adherence = (
    meds: Medication[],
    logs: DoseLog[],
    days: number,
    now: Date = new Date(),
    tz: string = deviceTimeZone(),
): Adherence => {
    const today = dateISOIn(now, tz);
    const stats: DayStat[] = [];
    for (let i = days - 1; i >= 0; i--) {
        const d = addDaysISO(today, -i);
        stats.push(statFor(dosesForDay(meds, logs, d, now, tz), d));
    }
    const taken = stats.reduce((s, d) => s + d.taken, 0);
    const scheduled = stats.reduce((s, d) => s + d.counted, 0);

    // Streak: walk back until a day with a skipped/missed dose. Days with nothing
    // due neither break nor extend it. Stop at the earliest medicine's start.
    const earliest = [...meds.map(m => m.createdAt.slice(0, 10)), ...logs.map(l => l.dateISO)].sort()[0];
    let streak = 0;
    for (let i = 0; earliest && i < 366; i++) {
        const d = addDaysISO(today, -i);
        if (d < earliest) break;
        const s = statFor(dosesForDay(meds, logs, d, now, tz), d);
        if (s.counted === 0) continue;
        if (s.taken < s.counted) break;
        streak++;
    }

    return { pct: scheduled ? Math.round((taken / scheduled) * 100) : null, taken, scheduled, streak, days: stats };
};

/** Build the log entry for marking a dose. */
export const makeLog = (view: Pick<DoseView, 'med' | 'dateISO' | 'slot' | 'scheduledAt'>, status: DoseStatus, at: Date = new Date()): DoseLog => ({
    id: doseId(view.med.id, view.dateISO, view.slot),
    medId: view.med.id,
    dateISO: view.dateISO,
    slot: view.slot,
    scheduledAt: view.scheduledAt.toISOString(),
    status,
    at: at.toISOString(),
});

/** Insert or replace a log entry (same dose id → newest wins). */
export const upsertLog = (logs: DoseLog[], entry: DoseLog): DoseLog[] => [...logs.filter(l => l.id !== entry.id), entry];

/** Remove a log entry (undo). */
export const removeLog = (logs: DoseLog[], id: string): DoseLog[] => logs.filter(l => l.id !== id);
