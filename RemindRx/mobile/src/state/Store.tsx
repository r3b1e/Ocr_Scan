/**
 * App state: medicines, dose log and settings, mirrored to AsyncStorage.
 * Every change to medicines re-arms the reminder window.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';
import {
    AppData,
    DoseStatus,
    DoseView,
    Medication,
    MedicationStatus,
    Settings,
    makeLog,
    mergeBackup,
    removeLog,
} from '@shared/index';
import * as storage from './storage';
import ReminderService, { onDoseRecorded } from '../reminders/ReminderService';

interface StoreValue extends AppData {
    ready: boolean;
    /** Re-renders every 30 s so due/missed states stay current. */
    now: Date;
    saveMed(med: Medication): Promise<void>;
    setStatus(id: string, status: MedicationStatus): Promise<void>;
    logDose(view: DoseView, status: DoseStatus): Promise<void>;
    undoDose(view: DoseView): Promise<void>;
    snoozeDose(view: DoseView): Promise<void>;
    importData(data: AppData, mode: 'merge' | 'replace'): Promise<void>;
    wipe(): Promise<void>;
    setSettings(p: Partial<Settings>): Promise<void>;
}

const StoreContext = createContext<StoreValue | null>(null);

export const StoreProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [data, setData] = useState<AppData>({ meds: [], doses: [], settings: {} });
    const [ready, setReady] = useState(false);
    const [now, setNow] = useState(new Date());
    const dataRef = useRef(data);
    dataRef.current = data;

    const reload = useCallback(async (rearm: boolean) => {
        const d = await storage.loadAll();
        setData(d);
        setNow(new Date());
        if (rearm) ReminderService.rescheduleAll(d.meds, d.doses).catch(() => {});
        return d;
    }, []);

    useEffect(() => {
        reload(true).then(() => setReady(true));
        const offDose = onDoseRecorded(() => { reload(false); });
        // Back in the foreground: pick up doses logged from the notification
        // shade and re-arm (the timezone may have changed while away).
        const sub = AppState.addEventListener('change', s => { if (s === 'active') reload(true); });
        const tick = setInterval(() => setNow(new Date()), 30_000);
        return () => { offDose(); sub.remove(); clearInterval(tick); };
    }, [reload]);

    const commitMeds = useCallback(async (meds: Medication[]) => {
        await storage.saveMeds(meds);
        setData(d => ({ ...d, meds }));
        await ReminderService.rescheduleAll(meds, dataRef.current.doses);
    }, []);

    const value = useMemo<StoreValue>(() => ({
        ...data,
        ready,
        now,
        async saveMed(med) {
            const meds = dataRef.current.meds;
            await commitMeds(meds.some(m => m.id === med.id) ? meds.map(m => (m.id === med.id ? med : m)) : [...meds, med]);
        },
        async setStatus(id, status) {
            const at = new Date().toISOString();
            await commitMeds(dataRef.current.meds.map(m => (m.id === id ? { ...m, status, updatedAt: at } : m)));
        },
        async logDose(view, status) {
            const doses = await storage.recordDose(makeLog(view, status));
            setData(d => ({ ...d, doses }));
            await ReminderService.cancelDose(view.med.id, view.dateISO, view.slot);
        },
        async undoDose(view) {
            const doses = await storage.mutateDoses(d => removeLog(d, view.id));
            setData(d => ({ ...d, doses }));
            await ReminderService.rescheduleAll(dataRef.current.meds, doses);
        },
        async snoozeDose(view) {
            await ReminderService.snooze(ReminderService.dataFor(view.med, view.dateISO, view.slot, view.time, view.scheduledAt));
        },
        async importData(incoming, mode) {
            const next = mergeBackup(dataRef.current, incoming, mode);
            await storage.saveAll(next);
            setData(next);
            await ReminderService.rescheduleAll(next.meds, next.doses);
        },
        async wipe() {
            const empty: AppData = { meds: [], doses: [], settings: {} };
            await storage.saveAll(empty);
            setData(empty);
            await ReminderService.rescheduleAll([], []);
        },
        async setSettings(p) {
            const settings = { ...dataRef.current.settings, ...p };
            await storage.saveSettings(settings);
            setData(d => ({ ...d, settings }));
        },
    }), [data, ready, now, commitMeds]);

    return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
};

export const useStore = (): StoreValue => {
    const v = useContext(StoreContext);
    if (!v) throw new Error('useStore outside StoreProvider');
    return v;
};
