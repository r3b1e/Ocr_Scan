/**
 * Wall-clock math in an EXPLICIT IANA zone, via Intl.
 *
 * WHY NOT `new Date(y, m, d, h, min)`: found on a real Pixel — Hermes keeps
 * using the timezone it started with for local Date construction, while Intl
 * sees a zone change immediately. After a New York → Dubai switch the app
 * re-armed every alarm on New York's 08:00 again (16:00 in Dubai). Everything
 * that turns "08:00 on this date" into an instant goes through here with the
 * zone read fresh from Intl.
 *
 * Same algorithm as the backend's src/shared/time/user-time.ts.
 */

interface Parts { year: number; month: number; day: number; hour: number; minute: number }

function partsIn(d: Date, tz: string): Parts {
    const p: Record<string, string> = {};
    for (const x of new Intl.DateTimeFormat('en-CA', {
        timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(d)) p[x.type] = x.value;
    return { year: +p.year, month: +p.month, day: +p.day, hour: +p.hour % 24, minute: +p.minute };
}

/** yyyy-mm-dd of `d` on the wall clock in `tz`. */
export function dateISOIn(d: Date, tz: string): string {
    const p = partsIn(d, tz);
    return `${p.year}-${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}`;
}

/** Shift a yyyy-mm-dd calendar date by whole days (no zone involved). */
export function addDaysISO(iso: string, n: number): string {
    const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

/** Weekday (0 = Sunday) and day-of-month of a calendar date, zone-free. */
export function calendarOf(iso: string): { weekday: number; dayOfMonth: number; daysInMonth: number } {
    const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d));
    return { weekday: dt.getUTCDay(), dayOfMonth: d, daysInMonth: new Date(Date.UTC(y, m, 0)).getUTCDate() };
}

/** Whole days from calendar date a to b. */
export function daysBetweenISO(a: string, b: string): number {
    return Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86_400_000);
}

/** The instant at which the wall clock in `tz` reads `iso` hh:mm (DST-safe). */
export function zonedTimeToUtc(iso: string, tz: string, hour = 0, minute = 0): Date {
    const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
    const target = Date.UTC(y, m - 1, d, hour, minute);
    let guess = target;
    for (let i = 0; i < 2; i++) {
        const p = partsIn(new Date(guess), tz);
        guess += target - Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
    }
    return new Date(guess);
}
