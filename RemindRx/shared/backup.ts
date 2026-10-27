/**
 * Backup file format, shared by web and mobile so a file exported on one opens
 * on the other. There is no server, so this file is the only way to move data.
 */
import { FrequencyType, Medication } from './types';
import { DoseLog } from './doses';

export interface Settings {
    userName?: string;
}

export interface AppData {
    meds: Medication[];
    doses: DoseLog[];
    settings: Settings;
}

export interface BackupFile extends AppData {
    app: 'RemindRx';
    version: 1;
    exportedAt: string;
}

export type ParseResult = { ok: true; data: BackupFile } | { ok: false; error: string };

export const BACKUP_VERSION = 1;

export const makeBackup = (data: AppData, now: Date = new Date()): BackupFile => ({
    app: 'RemindRx',
    version: BACKUP_VERSION,
    exportedAt: now.toISOString(),
    meds: data.meds,
    doses: data.doses,
    settings: data.settings,
});

export const backupFileName = (now: Date = new Date()) => `remindrx-backup-${now.toISOString().slice(0, 10)}.json`;

const isObj = (v: unknown): v is Record<string, any> => typeof v === 'object' && v !== null && !Array.isArray(v);
const FREQS = new Set<string>(Object.values(FrequencyType));

const validMed = (m: unknown): m is Medication =>
    isObj(m) &&
    typeof m.id === 'string' && !!m.id &&
    typeof m.name === 'string' &&
    typeof m.startDate === 'string' && /^\d{4}-\d{2}-\d{2}/.test(m.startDate) &&
    typeof m.endDate === 'string' && /^\d{4}-\d{2}-\d{2}/.test(m.endDate) &&
    FREQS.has(m.frequencyType) &&
    isObj(m.frequencyConfig) &&
    Array.isArray(m.scheduleTimes) &&
    m.scheduleTimes.every((t: unknown) => isObj(t) && Number.isInteger(t.hour) && Number.isInteger(t.minute)) &&
    typeof m.status === 'string';

const validDose = (d: unknown): d is DoseLog =>
    isObj(d) &&
    typeof d.id === 'string' &&
    typeof d.medId === 'string' &&
    typeof d.dateISO === 'string' &&
    Number.isInteger(d.slot) &&
    typeof d.scheduledAt === 'string' &&
    (d.status === 'taken' || d.status === 'skipped');

export const parseBackup = (text: string): ParseResult => {
    let raw: unknown;
    try {
        raw = JSON.parse(text);
    } catch {
        return { ok: false, error: 'This file is not valid JSON.' };
    }
    if (!isObj(raw) || raw.app !== 'RemindRx') return { ok: false, error: 'This is not a RemindRx backup file.' };
    if (raw.version !== BACKUP_VERSION) return { ok: false, error: `Unsupported backup version (${String(raw.version)}). Update the app and try again.` };
    if (!Array.isArray(raw.meds) || !Array.isArray(raw.doses)) return { ok: false, error: 'The backup is missing its medication list.' };
    const badMed = raw.meds.findIndex(m => !validMed(m));
    if (badMed >= 0) return { ok: false, error: `Medication #${badMed + 1} in the backup is damaged.` };
    const badDose = raw.doses.findIndex(d => !validDose(d));
    if (badDose >= 0) return { ok: false, error: `Dose record #${badDose + 1} in the backup is damaged.` };
    return {
        ok: true,
        data: {
            app: 'RemindRx',
            version: BACKUP_VERSION,
            exportedAt: typeof raw.exportedAt === 'string' ? raw.exportedAt : '',
            meds: raw.meds,
            doses: raw.doses,
            settings: isObj(raw.settings) ? { userName: typeof raw.settings.userName === 'string' ? raw.settings.userName : undefined } : {},
        },
    };
};

const byIdMerge = <T extends { id: string }>(cur: T[], inc: T[]): T[] => {
    const m = new Map(cur.map(x => [x.id, x] as const));
    for (const x of inc) m.set(x.id, x);
    return [...m.values()];
};

/** merge: imported records win on the same id. replace: imported data only. */
export const mergeBackup = (cur: AppData, inc: AppData, mode: 'merge' | 'replace'): AppData =>
    mode === 'replace'
        ? { meds: inc.meds, doses: inc.doses, settings: { ...inc.settings } }
        : { meds: byIdMerge(cur.meds, inc.meds), doses: byIdMerge(cur.doses, inc.doses), settings: { ...cur.settings, ...inc.settings } };
