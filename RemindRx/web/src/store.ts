/**
 * Device-only data store. Everything lives in this browser's localStorage;
 * nothing is ever sent anywhere. Every storage access is wrapped: in a private
 * window or with site data blocked the app keeps working in memory and shows a
 * warning instead of crashing.
 */
import { useSyncExternalStore } from 'react';
import type { AppData, DoseLog, DoseStatus, DoseView, Medication, MedicationStatus, Settings } from '@shared/index';
import { makeLog, removeLog, upsertLog } from '@shared/doses';

export const KEYS = { meds: 'rx.meds.v1', doses: 'rx.doses.v1', settings: 'rx.settings.v1' } as const;

export function readJSON<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
        return fallback;
    }
}

export function writeJSON(key: string, value: unknown): boolean {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch {
        return false;
    }
}

function probeStorage(): boolean {
    try {
        const k = '__rx_probe__';
        localStorage.setItem(k, '1');
        localStorage.removeItem(k);
        return true;
    } catch {
        return false;
    }
}

export interface StoreState extends AppData {
    storageOk: boolean;
}

let state: StoreState = {
    meds: readJSON<Medication[]>(KEYS.meds, []),
    doses: readJSON<DoseLog[]>(KEYS.doses, []),
    settings: readJSON<Settings>(KEYS.settings, {}),
    storageOk: probeStorage(),
};

const listeners = new Set<() => void>();

function set(patch: Partial<AppData>) {
    state = { ...state, ...patch };
    let ok = true;
    if (patch.meds) ok = writeJSON(KEYS.meds, patch.meds) && ok;
    if (patch.doses) ok = writeJSON(KEYS.doses, patch.doses) && ok;
    if (patch.settings) ok = writeJSON(KEYS.settings, patch.settings) && ok;
    if (ok !== state.storageOk) state = { ...state, storageOk: ok };
    listeners.forEach(l => l());
}

// Another tab changed the data → pick it up.
if (typeof window !== 'undefined') {
    window.addEventListener('storage', e => {
        if (!e.key || !Object.values(KEYS).includes(e.key as any)) return;
        state = {
            ...state,
            meds: readJSON(KEYS.meds, []),
            doses: readJSON(KEYS.doses, []),
            settings: readJSON(KEYS.settings, {}),
        };
        listeners.forEach(l => l());
    });
}

export const store = {
    get: () => state,
    subscribe(l: () => void) {
        listeners.add(l);
        return () => listeners.delete(l);
    },
    saveMed(med: Medication) {
        const exists = state.meds.some(m => m.id === med.id);
        set({ meds: exists ? state.meds.map(m => (m.id === med.id ? med : m)) : [...state.meds, med] });
    },
    setMedStatus(id: string, status: MedicationStatus) {
        set({ meds: state.meds.map(m => (m.id === id ? { ...m, status, updatedAt: new Date().toISOString() } : m)) });
    },
    logDose(view: Pick<DoseView, 'med' | 'dateISO' | 'slot' | 'scheduledAt'>, status: DoseStatus) {
        set({ doses: upsertLog(state.doses, makeLog(view, status)) });
    },
    undoDose(id: string) {
        set({ doses: removeLog(state.doses, id) });
    },
    setSettings(patch: Partial<Settings>) {
        set({ settings: { ...state.settings, ...patch } });
    },
    replaceAll(data: AppData) {
        set({ meds: data.meds, doses: data.doses, settings: data.settings });
    },
    wipe() {
        set({ meds: [], doses: [], settings: {} });
    },
};

export function useStore(): StoreState {
    return useSyncExternalStore(store.subscribe, store.get, store.get);
}
