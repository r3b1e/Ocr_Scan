/**
 * Reminder scheduling logic (from HealthApp). Uses the device's wall-clock
 * time: a dose at 08:00 fires at 08:00 local, wherever the phone is.
 * expandFireTimesInZone is what the schedulers use, with the zone read fresh
 * from Intl (Hermes caches the start-up zone for local Date construction).
 */
import { Medication, TimeOfDay } from './types';
import { addDays, daysBetween, parseISODateLocal, toISODate } from './logic';
import { addDaysISO, calendarOf, dateISOIn, daysBetweenISO, zonedTimeToUtc } from './zonedTime';

const daysInMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();

/** Does this medication have an intake on the given LOCAL calendar date? */
export const firesOn = (med: Medication, date: Date): boolean => {
    const start = parseISODateLocal(med.startDate);
    const end = parseISODateLocal(med.endDate);
    if (daysBetween(start, date) < 0 || daysBetween(date, end) < 0) return false;

    const cfg = (med.frequencyConfig ?? {}) as Record<string, any>;
    switch (med.frequencyType) {
        case 'SPECIFIC_DAYS': {
            const weekdays: number[] = Array.isArray(cfg.weekdays) ? cfg.weekdays : [];
            return weekdays.includes(date.getDay());
        }
        case 'EVERY_X_DAYS': {
            const interval = Number(cfg.intervalDays) || 1;
            return daysBetween(start, date) % interval === 0;
        }
        case 'DAY_OF_MONTH': {
            const dom = Number(cfg.dayOfMonth) || 1;
            return date.getDate() === Math.min(dom, daysInMonth(date));
        }
        // ONCE/TWICE/THRICE/MULTI_DAILY — every day in range.
        default:
            return true;
    }
};

export interface FireEntry {
    dateISO: string;   // yyyy-mm-dd (local)
    slotIndex: number; // index into scheduleTimes
    fireAt: Date;      // exact local fire time
    time: TimeOfDay;
}

/**
 * All future intake fire times within [windowStart, windowStart+windowDays).
 * Drops anything already past or beyond the course end date (end-of-day).
 */
export const expandFireTimes = (
    med: Medication,
    windowStart: Date,
    windowDays: number,
    now: Date = new Date(),
): FireEntry[] => {
    const out: FireEntry[] = [];
    const end = parseISODateLocal(med.endDate);
    const endOfCourse = new Date(end.getFullYear(), end.getMonth(), end.getDate(), 23, 59, 59, 999).getTime();
    const nowMs = now.getTime();

    for (let i = 0; i < windowDays; i++) {
        const day = addDays(windowStart, i);
        if (!firesOn(med, day)) continue;
        (med.scheduleTimes ?? []).forEach((t, slotIndex) => {
            const fireAt = new Date(day.getFullYear(), day.getMonth(), day.getDate(), t.hour, t.minute, 0, 0);
            const ms = fireAt.getTime();
            if (ms <= nowMs || ms > endOfCourse) return;
            out.push({ dateISO: toISODate(day), slotIndex, fireAt, time: t });
        });
    }
    return out;
};

/** firesOn for a zone-free yyyy-mm-dd calendar date (see expandFireTimesInZone). */
export const firesOnISO = (med: Medication, dayISO: string): boolean => {
    const start = String(med.startDate).slice(0, 10);
    const end = String(med.endDate).slice(0, 10);
    if (daysBetweenISO(start, dayISO) < 0 || daysBetweenISO(dayISO, end) < 0) return false;
    const cfg = (med.frequencyConfig ?? {}) as Record<string, any>;
    const cal = calendarOf(dayISO);
    switch (med.frequencyType) {
        case 'SPECIFIC_DAYS': {
            const weekdays: number[] = Array.isArray(cfg.weekdays) ? cfg.weekdays : [];
            return weekdays.includes(cal.weekday);
        }
        case 'EVERY_X_DAYS': {
            const interval = Number(cfg.intervalDays) || 1;
            return daysBetweenISO(start, dayISO) % interval === 0;
        }
        case 'DAY_OF_MONTH': {
            const dom = Number(cfg.dayOfMonth) || 1;
            return cal.dayOfMonth === Math.min(dom, cal.daysInMonth);
        }
        default:
            return true;
    }
};

/**
 * expandFireTimes on an EXPLICIT zone — what the scheduler uses. Local Date
 * construction goes stale in Hermes after a zone change (see zonedTime.ts), so
 * "today", each date and each 08:00 are all taken in `tz`, read fresh via Intl.
 */
export const expandFireTimesInZone = (
    med: Medication,
    tz: string,
    windowDays: number,
    now: Date = new Date(),
): FireEntry[] => {
    const out: FireEntry[] = [];
    const endOfCourse = zonedTimeToUtc(addDaysISO(String(med.endDate).slice(0, 10), 1), tz).getTime() - 1;
    const nowMs = now.getTime();
    const today = dateISOIn(now, tz);
    for (let i = 0; i < windowDays; i++) {
        const dayISO = addDaysISO(today, i);
        if (!firesOnISO(med, dayISO)) continue;
        (med.scheduleTimes ?? []).forEach((t, slotIndex) => {
            const fireAt = zonedTimeToUtc(dayISO, tz, t.hour, t.minute);
            const ms = fireAt.getTime();
            if (ms <= nowMs || ms > endOfCourse) return;
            out.push({ dateISO: dayISO, slotIndex, fireAt, time: t });
        });
    }
    return out;
};
