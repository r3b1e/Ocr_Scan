/**
 * On-device persistence (AsyncStorage). The notification background handler
 * writes dose logs here while the UI may not be running, so every write is a
 * read-modify-write of the stored value, never of in-memory state.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppData, DoseLog, Medication, Settings, upsertLog } from '@shared/index';

const K_MEDS = 'rx.meds.v1';
const K_DOSES = 'rx.doses.v1';
const K_SETTINGS = 'rx.settings.v1';

const readJSON = async <T,>(key: string, fallback: T): Promise<T> => {
    try {
        const raw = await AsyncStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
        return fallback;
    }
};

export const loadAll = async (): Promise<AppData> => ({
    meds: await readJSON<Medication[]>(K_MEDS, []),
    doses: await readJSON<DoseLog[]>(K_DOSES, []),
    settings: await readJSON<Settings>(K_SETTINGS, {}),
});

export const loadMeds = () => readJSON<Medication[]>(K_MEDS, []);

export const saveMeds = (meds: Medication[]) => AsyncStorage.setItem(K_MEDS, JSON.stringify(meds));
export const saveDoses = (doses: DoseLog[]) => AsyncStorage.setItem(K_DOSES, JSON.stringify(doses));
export const saveSettings = (s: Settings) => AsyncStorage.setItem(K_SETTINGS, JSON.stringify(s));

export const saveAll = async (d: AppData) => {
    await AsyncStorage.multiSet([
        [K_MEDS, JSON.stringify(d.meds)],
        [K_DOSES, JSON.stringify(d.doses)],
        [K_SETTINGS, JSON.stringify(d.settings)],
    ]);
};

/** Chain of dose writes so two quick actions can't overwrite each other. */
let doseQueue: Promise<unknown> = Promise.resolve();

export const mutateDoses = (fn: (doses: DoseLog[]) => DoseLog[]): Promise<DoseLog[]> => {
    const run = doseQueue.then(async () => {
        const next = fn(await readJSON<DoseLog[]>(K_DOSES, []));
        await saveDoses(next);
        return next;
    });
    doseQueue = run.catch(() => undefined);
    return run;
};

export const recordDose = (entry: DoseLog) => mutateDoses(d => upsertLog(d, entry));
