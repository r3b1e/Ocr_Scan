import { makeBackup, mergeBackup, parseBackup } from '../backup';
import { med } from './fixtures';

const data = { meds: [med()], doses: [], settings: { userName: 'Asha' } };

describe('backup', () => {
    it('round-trips', () => {
        const r = parseBackup(JSON.stringify(makeBackup(data)));
        expect(r.ok).toBe(true);
        if (r.ok) expect(r.data.meds[0].name).toBe('Metformin');
    });
    it.each([
        ['not json', 'not valid JSON'],
        ['{"foo":1}', 'not a RemindRx backup'],
        ['{"app":"RemindRx","version":2,"meds":[],"doses":[]}', 'Unsupported backup version'],
        ['{"app":"RemindRx","version":1,"meds":[{"id":"x"}],"doses":[]}', 'Medication #1'],
        ['{"app":"RemindRx","version":1,"meds":[],"doses":[{"id":1}]}', 'Dose record #1'],
    ])('rejects %s', (text, msg) => {
        const r = parseBackup(text);
        expect(r.ok).toBe(false);
        if (!r.ok) expect(r.error).toContain(msg);
    });
    it('merge: imported record wins on the same id; replace drops local', () => {
        const cur = { meds: [med(), med({ id: 'local' })], doses: [], settings: {} };
        const inc = { meds: [med({ name: 'Imported' })], doses: [], settings: { userName: 'B' } };
        const merged = mergeBackup(cur, inc, 'merge');
        expect(merged.meds.map(m => `${m.id}:${m.name}`).sort()).toEqual(['local:Metformin', 'm1:Imported']);
        expect(mergeBackup(cur, inc, 'replace').meds.map(m => m.id)).toEqual(['m1']);
    });
});
