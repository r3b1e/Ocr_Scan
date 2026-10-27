import { MedicationStatus } from '../types';
import { adherence, dosesForDay, makeLog, upsertLog } from '../doses';
import { med, TZ, ist } from './fixtures';

const D = '2026-10-20';
const states = (meds: any[], logs: any[], now: Date, d = D) => dosesForDay(meds, logs, d, now, TZ).map(v => `${v.med.id}#${v.slot}:${v.state}`);

describe('dosesForDay', () => {
    it('upcoming → due → missed across the 60-minute window', () => {
        expect(states([med()], [], ist(D, 7, 59))).toEqual(['m1#0:upcoming']);
        expect(states([med()], [], ist(D, 8, 30))).toEqual(['m1#0:due']);
        expect(states([med()], [], ist(D, 9, 1))).toEqual(['m1#0:missed']);
    });
    it('two medicines at the same minute stay distinct', () => {
        const v = dosesForDay([med(), med({ id: 'm2', name: 'Aspirin' })], [], D, ist(D, 7), TZ);
        expect(v.map(x => x.id)).toEqual(['m2:2026-10-20:0', 'm1:2026-10-20:0']);
    });
    it('paused and finished medicines are not scheduled', () => {
        expect(states([med({ status: MedicationStatus.Paused })], [], ist(D, 9))).toEqual([]);
        expect(states([med({ endDate: '2026-10-19' })], [], ist(D, 9))).toEqual([]);
    });
    it('a medicine added after a dose time does not start with a missed dose', () => {
        expect(states([med({ createdAt: ist(D, 10).toISOString() })], [], ist(D, 11))).toEqual([]);
    });
    it('a logged dose survives a time edit and is not double counted', () => {
        const original = med();
        const view = dosesForDay([original], [], D, ist(D, 8, 5), TZ)[0];
        const logs = [makeLog(view, 'taken', ist(D, 8, 5))];
        const edited = med({ scheduleTimes: [{ hour: 21, minute: 0 }] });
        const v = dosesForDay([edited], logs, D, ist(D, 12), TZ);
        expect(v).toHaveLength(1);
        expect(v[0].state).toBe('taken');
        expect(v[0].time).toEqual({ hour: 8, minute: 0 });
    });
    it('logs of a deleted medicine still show in history', () => {
        const view = dosesForDay([med()], [], D, ist(D, 8), TZ)[0];
        const logs = [makeLog(view, 'skipped')];
        expect(states([med({ status: MedicationStatus.Deleted })], logs, ist(D, 12))).toEqual(['m1#0:skipped']);
    });
});

describe('adherence', () => {
    it('counts taken over taken+skipped+missed and computes the streak', () => {
        const m = med({ createdAt: '2026-10-17T00:00:00.000Z' });
        let logs: any[] = [];
        for (const d of ['2026-10-18', '2026-10-19', '2026-10-20']) {
            const v = dosesForDay([m], logs, d, ist(d, 9), TZ)[0];
            logs = upsertLog(logs, makeLog(v, 'taken'));
        }
        // 10-17: created 05:30 IST, 08:00 dose never logged → missed.
        const a = adherence([m], logs, 7, ist('2026-10-20', 12), TZ);
        expect(a.taken).toBe(3);
        expect(a.scheduled).toBe(4);
        expect(a.pct).toBe(75);
        expect(a.streak).toBe(3);
        expect(a.days).toHaveLength(7);
    });
    it('returns null pct when nothing was due', () => {
        expect(adherence([], [], 7, ist(D, 12), TZ).pct).toBeNull();
    });
});
