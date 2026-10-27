import { FrequencyType } from '../types';
import { firesOnISO, expandFireTimesInZone } from '../reminderLogic';
import { med, TZ, ist } from './fixtures';

describe('firesOnISO', () => {
    it('daily modes fire every day inside the course only', () => {
        const m = med();
        expect(firesOnISO(m, '2026-10-01')).toBe(true);
        expect(firesOnISO(m, '2026-10-31')).toBe(true);
        expect(firesOnISO(m, '2026-09-30')).toBe(false);
        expect(firesOnISO(m, '2026-11-01')).toBe(false);
    });
    it('specific weekdays', () => {
        const m = med({ frequencyType: FrequencyType.SpecificDays, frequencyConfig: { timesPerDay: 1, weekdays: [1, 3] } });
        expect(firesOnISO(m, '2026-10-19')).toBe(true); // Monday
        expect(firesOnISO(m, '2026-10-20')).toBe(false); // Tuesday
        expect(firesOnISO(m, '2026-10-21')).toBe(true); // Wednesday
    });
    it('every X days counts from the start date', () => {
        const m = med({ frequencyType: FrequencyType.EveryXDays, frequencyConfig: { timesPerDay: 1, intervalDays: 3 } });
        expect(firesOnISO(m, '2026-10-01')).toBe(true);
        expect(firesOnISO(m, '2026-10-02')).toBe(false);
        expect(firesOnISO(m, '2026-10-04')).toBe(true);
    });
    it('day of month clamps to short months', () => {
        const m = med({ startDate: '2026-01-01', endDate: '2026-12-31', frequencyType: FrequencyType.DayOfMonth, frequencyConfig: { timesPerDay: 1, dayOfMonth: 31 } });
        expect(firesOnISO(m, '2026-02-28')).toBe(true);
        expect(firesOnISO(m, '2026-03-30')).toBe(false);
        expect(firesOnISO(m, '2026-03-31')).toBe(true);
    });
});

describe('expandFireTimesInZone', () => {
    it('skips past times and stops at the course end', () => {
        const m = med({ endDate: '2026-10-22', scheduleTimes: [{ hour: 8, minute: 0 }, { hour: 20, minute: 0 }] });
        const fires = expandFireTimesInZone(m, TZ, 14, ist('2026-10-20', 12));
        expect(fires.map(f => `${f.dateISO}#${f.slotIndex}`)).toEqual(['2026-10-20#1', '2026-10-21#0', '2026-10-21#1', '2026-10-22#0', '2026-10-22#1']);
        expect(fires[0].fireAt.toISOString()).toBe(ist('2026-10-20', 20).toISOString());
    });
});
