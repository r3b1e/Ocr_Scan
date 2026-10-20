/**
 * In-tab reminder engine. A website can't wake a closed browser without a push
 * server, so reminders ring only while RemindRx is open: a 15 s tick (plus a
 * check whenever the tab becomes visible) compares today's doses with the clock.
 *
 * Each alert has a deterministic key, recorded in rx.fired.v1 once shown, so a
 * reload never rings the same reminder twice:
 *   {doseId}             main reminder at the dose time
 *   {doseId}:early       lead-time reminder
 *   {doseId}:snooze:{ms} snoozed re-fire
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { addDaysISO, dosesForDay, formatTime, MISSED_AFTER_MIN, SNOOZE_MIN, todayISO, type DoseView } from '@shared/index';
import { readJSON, store, useStore, writeJSON } from './store';
import { chime, startAlarm, stopAlarm } from './sound';

const FIRED_KEY = 'rx.fired.v1';
const SNOOZE_KEY = 'rx.snooze.v1';

export interface ActiveAlert {
    key: string;
    view: DoseView;
    kind: 'due' | 'early' | 'snooze';
}

type Fired = Record<string, number>; // key → fired at (ms); pruned after 2 days
type Snoozes = Record<string, number>; // doseId → until (ms)

const prune = <T extends Record<string, number>>(m: T, olderThan: number): T =>
    Object.fromEntries(Object.entries(m).filter(([, v]) => v >= olderThan)) as T;

export function snoozeDose(doseId: string, now = Date.now()) {
    const s = readJSON<Snoozes>(SNOOZE_KEY, {});
    s[doseId] = now + SNOOZE_MIN * 60_000;
    writeJSON(SNOOZE_KEY, s);
}

export function snoozedUntil(doseId: string): number | undefined {
    return readJSON<Snoozes>(SNOOZE_KEY, {})[doseId];
}

export function clearSnooze(doseId: string) {
    const s = readJSON<Snoozes>(SNOOZE_KEY, {});
    if (doseId in s) {
        delete s[doseId];
        writeJSON(SNOOZE_KEY, s);
    }
}

/** Which alerts should be showing right now and haven't been shown yet. */
export function dueAlerts(now: Date, fired: Fired, snoozes: Snoozes): ActiveAlert[] {
    const { meds, doses } = store.get();
    const nowMs = now.getTime();
    const today = todayISO(now);
    // Yesterday too, so a 23:50 dose still rings at 00:05.
    const views = [addDaysISO(today, -1), today].flatMap(d => dosesForDay(meds, doses, d, now));
    const out: ActiveAlert[] = [];
    for (const v of views) {
        if (!v.med.remindersEnabled || v.log) continue;
        const at = v.scheduledAt.getTime();
        const lateCutoff = at + MISSED_AFTER_MIN * 60_000;
        const lead = v.med.reminderLeadMinutes || 0;
        if (lead > 0) {
            const key = `${v.id}:early`;
            if (nowMs >= at - lead * 60_000 && nowMs < at && !fired[key]) out.push({ key, view: v, kind: 'early' });
        }
        const until = snoozes[v.id];
        if (until) {
            const key = `${v.id}:snooze:${until}`;
            if (nowMs >= until && nowMs < until + MISSED_AFTER_MIN * 60_000 && !fired[key]) out.push({ key, view: v, kind: 'snooze' });
        } else if (nowMs >= at && nowMs < lateCutoff && !fired[v.id]) {
            out.push({ key: v.id, view: v, kind: 'due' });
        }
    }
    return out;
}

export type NotifyPermission = NotificationPermission | 'unsupported';

export const notifyPermission = (): NotifyPermission =>
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission;

export async function requestNotifyPermission(): Promise<NotifyPermission> {
    if (typeof Notification === 'undefined') return 'unsupported';
    try {
        return await Notification.requestPermission();
    } catch {
        return Notification.permission;
    }
}

async function systemNotify(a: ActiveAlert) {
    if (notifyPermission() !== 'granted') return;
    const m = a.view.med;
    const title = a.kind === 'early' ? `Coming up: ${m.name}` : `Time for ${m.name}`;
    const body = `${m.quantityPerDose} ${m.doseUnit} · ${formatTime(a.view.time)}${m.mealRelation && m.mealRelation !== 'any' ? ` · ${m.mealRelation} food` : ''}`;
    const opts: NotificationOptions = { body, tag: a.key, icon: '/icon-192.png', badge: '/icon-192.png', requireInteraction: m.reminderMode === 'alarm', data: { url: '/' } };
    try {
        const reg = await navigator.serviceWorker?.getRegistration();
        if (reg) return void (await reg.showNotification(title, opts));
    } catch {
        /* fall through to the page-level API */
    }
    try {
        const n = new Notification(title, opts);
        n.onclick = () => {
            window.focus();
            n.close();
        };
    } catch {
        /* some mobile browsers only allow SW notifications */
    }
}

/** Close shown system notifications whose dose matches (tags start with the dose id). */
async function closeNotifications(match: (doseId: string) => boolean) {
    try {
        const reg = await navigator.serviceWorker?.getRegistration();
        for (const n of (await reg?.getNotifications()) ?? []) {
            if (match(n.tag.split(':').slice(0, 3).join(':'))) n.close();
        }
    } catch {
        /* no service worker: page-level notifications close on click */
    }
}

/** Runs the engine and exposes the queue of alerts awaiting the user. */
export function useReminderEngine() {
    const { meds, doses } = useStore();
    const [alerts, setAlerts] = useState<ActiveAlert[]>([]);
    const titleRef = useRef(document.title);

    const check = useCallback(() => {
        const now = new Date();
        const fired = prune(readJSON<Fired>(FIRED_KEY, {}), now.getTime() - 2 * 86_400_000);
        const snoozes = readJSON<Snoozes>(SNOOZE_KEY, {});
        const fresh = dueAlerts(now, fired, snoozes);
        if (!fresh.length) return;
        for (const a of fresh) fired[a.key] = now.getTime();
        writeJSON(FIRED_KEY, fired);
        setAlerts(cur => [...cur.filter(c => !fresh.some(f => f.view.id === c.view.id)), ...fresh]);
        fresh.forEach(a => void systemNotify(a));
    }, []);

    useEffect(() => {
        check();
        const id = window.setInterval(check, 15_000);
        document.addEventListener('visibilitychange', check);
        window.addEventListener('focus', check);
        return () => {
            window.clearInterval(id);
            document.removeEventListener('visibilitychange', check);
            window.removeEventListener('focus', check);
        };
    }, [check]);

    // Re-check right away when data changes (e.g. a medicine was just saved).
    useEffect(() => {
        check();
    }, [meds, doses, check]);

    // Drop alerts (and their system notifications) for doses that were logged
    // anywhere: the alert, the Today screen or another tab.
    useEffect(() => {
        const logged = new Set(doses.map(d => d.id));
        setAlerts(cur => (cur.some(a => logged.has(a.view.id)) ? cur.filter(a => !logged.has(a.view.id)) : cur));
        void closeNotifications(id => logged.has(id));
    }, [doses]);

    // Sound + tab title follow the head of the queue.
    const head = alerts[0];
    useEffect(() => {
        if (!head) {
            stopAlarm();
            document.title = titleRef.current;
            return;
        }
        document.title = `⏰ ${head.view.med.name} · RemindRx`;
        if (head.view.med.reminderMode === 'alarm' && head.kind !== 'early') startAlarm();
        else {
            stopAlarm();
            chime();
        }
    }, [head?.key]);

    const dismiss = useCallback((doseId: string) => {
        setAlerts(cur => cur.filter(a => a.view.id !== doseId));
        void closeNotifications(id => id === doseId);
    }, []);

    return { alerts, dismiss };
}
