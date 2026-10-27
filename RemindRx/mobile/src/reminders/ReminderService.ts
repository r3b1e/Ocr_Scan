/**
 * ReminderService — on-device medication reminders via @notifee/react-native.
 * Ported from HealthApp's MedicationNotificationService with the server push,
 * auth token and travel guard removed: here every reminder is armed locally.
 *
 * Reminders are explicit one-shot TimestampTriggers over a rolling 14-day
 * window (the 7 frequency modes can't be expressed as notifee repeats), armed
 * with AlarmManager exact + allowWhileIdle so they fire on time under Doze,
 * with the app swiped away and the phone locked.
 *
 *   'notification' — heads-up notification with Taken / Skip / Snooze actions.
 *   'alarm'        — full-screen intent + looping sound → AlarmScreen.
 *
 * Notification ids are deterministic, so re-arming is idempotent:
 *   med:{medId}:{YYYYMMDD}:{slot}          main reminder
 *   med:{medId}:{YYYYMMDD}:{slot}:early    lead-time reminder
 *   med:{medId}:{YYYYMMDD}:{slot}:snooze   snoozed re-fire
 */
import notifee, {
    AndroidCategory,
    AndroidImportance,
    AndroidVisibility,
    EventType,
    TriggerType,
} from '@notifee/react-native';
import {
    DoseLog,
    Medication,
    MedicationStatus,
    SNOOZE_MIN,
    TimeOfDay,
    deviceTimeZone,
    doseId,
    expandFireTimesInZone,
    formatTime,
} from '@shared/index';
import { recordDose } from '../state/storage';

export const CHANNEL_REMINDER = 'rx-reminder';
export const CHANNEL_ALARM = 'rx-alarm';
const WINDOW_DAYS = 14;

/** Notification data is string-only; everything the action handler needs. */
export interface MedData {
    medId: string;
    dateISO: string;
    slotIndex: string;
    scheduledAt: string;
    mode: string;
    name: string;
    dose: string;
    time: string;
    meal: string;
}

const MEAL_TEXT: Record<string, string> = { before: 'before food', after: 'after food', with: 'with food' };
const doseText = (med: Medication) => `${med.quantityPerDose} ${med.doseUnit}`;
const baseId = (medId: string, dateISO: string, slot: number) => `med:${medId}:${dateISO.replace(/-/g, '')}:${slot}`;

// ── Serialised queue for every change to armed reminders ────────────────────
// A save and a full re-arm racing could cancel each other's triggers.
let queue: Promise<unknown> = Promise.resolve();
const enqueue = <T,>(job: () => Promise<T>): Promise<T> => {
    const run = queue.then(job, job);
    queue = run.catch(() => undefined);
    return run;
};

// ── Listeners: the UI reloads when a notification action logs a dose ─────────
type Listener = () => void;
const doseListeners = new Set<Listener>();
const alarmListeners = new Set<(d: MedData) => void>();
export const onDoseRecorded = (l: Listener) => { doseListeners.add(l); return () => { doseListeners.delete(l); }; };
export const onAlarm = (l: (d: MedData) => void) => { alarmListeners.add(l); return () => { alarmListeners.delete(l); }; };

// ── Which alarm is ringing right now ──────────────────────────────────────
// The alarm notification is ongoing until the user acts, so the notification
// shade is the source of truth: no stored hand-off that can race the app
// becoming active.
export const ringingAlarm = async (): Promise<MedData | null> => {
    try {
        const shown = await notifee.getDisplayedNotifications();
        const hit = shown.find(n => n.notification.android?.channelId === CHANNEL_ALARM && !n.id?.endsWith(':early'));
        return (hit?.notification.data as unknown as MedData) ?? null;
    } catch {
        return null;
    }
};

const ACTIONS = [
    { title: '✅ Taken', pressAction: { id: 'TAKEN' } },
    { title: 'Skip', pressAction: { id: 'SKIP' } },
    { title: `⏰ Snooze ${SNOOZE_MIN}m`, pressAction: { id: 'SNOOZE' } },
];

async function arm(
    id: string,
    data: MedData,
    fireAtMs: number,
    kind: 'main' | 'early' | 'snooze',
): Promise<void> {
    const useAlarm = data.mode === 'alarm' && kind !== 'early';
    const meal = MEAL_TEXT[data.meal] ? ` · ${MEAL_TEXT[data.meal]}` : '';
    await notifee.createTriggerNotification(
        {
            id,
            title: kind === 'early' ? `Upcoming: ${data.name}` : kind === 'snooze' ? `💊 Reminder: ${data.name}` : `💊 Time to take ${data.name}`,
            body: kind === 'early' ? `${data.dose} at ${data.time}${meal}` : `Take ${data.dose}${meal} · ${data.time}`,
            data: data as unknown as Record<string, string>,
            android: {
                channelId: useAlarm ? CHANNEL_ALARM : CHANNEL_REMINDER,
                importance: AndroidImportance.HIGH,
                visibility: AndroidVisibility.PUBLIC,
                category: useAlarm ? AndroidCategory.ALARM : AndroidCategory.REMINDER,
                color: useAlarm ? '#FB7185' : '#0EA5E9',
                // Not for alarms: waking the screen first makes an unlocked (no
                // PIN) phone "in use", so Android downgrades the full-screen
                // intent to a heads-up. The full-screen intent wakes it anyway.
                lightUpScreen: !useAlarm,
                pressAction: { id: 'default', launchActivity: 'default' },
                smallIcon: 'ic_stat_rx',
                ...(useAlarm
                    ? { fullScreenAction: { id: 'default', launchActivity: 'default' }, loopSound: true, ongoing: true, autoCancel: false }
                    : {}),
                actions: kind === 'early' ? undefined : ACTIONS,
            },
            ios: { sound: 'default', critical: useAlarm },
        },
        { type: TriggerType.TIMESTAMP, timestamp: fireAtMs, alarmManager: { allowWhileIdle: true } },
    );
}

const dataFor = (med: Medication, dateISO: string, slot: number, time: TimeOfDay, scheduledAt: Date): MedData => ({
    medId: med.id,
    dateISO,
    slotIndex: String(slot),
    scheduledAt: scheduledAt.toISOString(),
    mode: med.reminderMode,
    name: med.name,
    dose: doseText(med),
    time: formatTime(time),
    meal: med.mealRelation ?? 'any',
});

async function cancelWhere(pred: (id: string) => boolean) {
    try {
        const ids = await notifee.getTriggerNotificationIds();
        await Promise.all(ids.filter(pred).map(id => notifee.cancelNotification(id).catch(() => {})));
    } catch { /* notifee unavailable */ }
}

async function _armMedication(med: Medication, takenIds: Set<string>) {
    if (!med.remindersEnabled || med.status !== MedicationStatus.Active) return;
    const lead = Math.max(0, med.reminderLeadMinutes || 0);
    for (const e of expandFireTimesInZone(med, deviceTimeZone(), WINDOW_DAYS)) {
        // A dose already logged (e.g. taken early from Today) must not ring.
        if (takenIds.has(doseId(med.id, e.dateISO, e.slotIndex))) continue;
        const id = baseId(med.id, e.dateISO, e.slotIndex);
        const data = dataFor(med, e.dateISO, e.slotIndex, e.time, e.fireAt);
        await arm(id, data, e.fireAt.getTime(), 'main').catch(() => {});
        const earlyMs = e.fireAt.getTime() - lead * 60_000;
        if (lead > 0 && earlyMs > Date.now()) await arm(`${id}:early`, data, earlyMs, 'early').catch(() => {});
    }
}

const ReminderService = {
    async createChannels(): Promise<void> {
        await notifee.createChannel({
            id: CHANNEL_REMINDER,
            name: 'Medication reminders',
            importance: AndroidImportance.HIGH,
            sound: 'notif_routine',
            vibration: true,
            visibility: AndroidVisibility.PUBLIC,
            lights: true,
            lightColor: '#0EA5E9',
        });
        await notifee.createChannel({
            id: CHANNEL_ALARM,
            name: 'Medication alarms',
            importance: AndroidImportance.HIGH,
            sound: 'notif_urgent',
            vibration: true,
            vibrationPattern: [300, 700, 300, 700],
            visibility: AndroidVisibility.PUBLIC,
            bypassDnd: true,
            lights: true,
            lightColor: '#FB7185',
        });
    },

    /**
     * Cancel every 'med:' trigger and re-arm the whole window. Called after any
     * change to medicines, after import, on app start and when the app returns
     * to the foreground (a timezone change moves every wall-clock time).
     */
    rescheduleAll(meds: Medication[], doses: DoseLog[]): Promise<void> {
        return enqueue(async () => {
            await cancelWhere(id => id.startsWith('med:') && !id.endsWith(':snooze'));
            const logged = new Set(doses.map(d => d.id));
            for (const med of meds) await _armMedication(med, logged).catch(() => {});
        });
    },

    /** Cancel a dose's main, early and snoozed reminders (it was logged) and clear it from the shade. */
    cancelDose(medId: string, dateISO: string, slot: number): Promise<void> {
        return enqueue(async () => {
            const base = baseId(medId, dateISO, slot);
            for (const id of [base, `${base}:early`, `${base}:snooze`]) await notifee.cancelNotification(id).catch(() => {});
        });
    },

    /** Re-ring this dose in SNOOZE_MIN minutes. */
    snooze(data: MedData): Promise<void> {
        return enqueue(async () => {
            const base = baseId(data.medId, data.dateISO, Number(data.slotIndex));
            await notifee.cancelNotification(base).catch(() => {});
            await notifee.cancelNotification(`${base}:snooze`).catch(() => {});
            await arm(`${base}:snooze`, data, Date.now() + SNOOZE_MIN * 60_000, 'snooze');
        });
    },

    dataFor,

    /** Fire a sample reminder in `seconds` so the user can check sound and full-screen. */
    async testReminder(mode: 'notification' | 'alarm', seconds = 10): Promise<void> {
        const at = new Date(Date.now() + seconds * 1000);
        const data: MedData = {
            medId: 'test', dateISO: '', slotIndex: '0', scheduledAt: at.toISOString(), mode,
            name: 'Test reminder', dose: '1 Tablet', time: formatTime({ hour: at.getHours(), minute: at.getMinutes() }), meal: 'any',
        };
        await arm(`test:${mode}`, data, at.getTime(), 'main');
    },

    async getPendingCount(): Promise<number> {
        try { return (await notifee.getTriggerNotificationIds()).filter(id => id.startsWith('med:')).length; } catch { return 0; }
    },

    /** Notification action (foreground or background): log the dose or snooze it. */
    async handleAction(actionId: string, data: MedData): Promise<void> {
        if (!data?.medId) return;
        if (data.medId === 'test') {
            await notifee.cancelNotification(`test:${data.mode}`).catch(() => {});
            return;
        }
        if (actionId === 'SNOOZE') {
            await this.snooze(data);
            return;
        }
        const status = actionId === 'TAKEN' ? 'taken' : actionId === 'SKIP' ? 'skipped' : null;
        if (!status) return;
        await this.cancelDose(data.medId, data.dateISO, Number(data.slotIndex));
        const entry: DoseLog = {
            id: doseId(data.medId, data.dateISO, Number(data.slotIndex)),
            medId: data.medId,
            dateISO: data.dateISO,
            slot: Number(data.slotIndex),
            scheduledAt: data.scheduledAt,
            status,
            at: new Date().toISOString(),
        };
        await recordDose(entry);
        doseListeners.forEach(l => l());
    },

    registerForegroundHandler(): () => void {
        return notifee.onForegroundEvent(async ({ type, detail }) => {
            const { notification, pressAction } = detail;
            if (!notification?.id) return;
            const data = (notification.data ?? {}) as unknown as MedData;
            if (type === EventType.ACTION_PRESS && pressAction?.id) {
                await this.handleAction(pressAction.id, data);
                return;
            }
            if ((type === EventType.DELIVERED || type === EventType.PRESS) && data.mode === 'alarm') {
                alarmListeners.forEach(l => l(data));
            }
        });
    },
};

/** notifee background handler — must be registered at module scope in index.js. */
export function registerBackgroundHandler(): void {
    notifee.onBackgroundEvent(async ({ type, detail }) => {
        const { notification, pressAction } = detail;
        if (!notification?.id) return;
        const data = (notification.data ?? {}) as unknown as MedData;
        if (type === EventType.ACTION_PRESS && pressAction?.id) await ReminderService.handleAction(pressAction.id, data);
    });
}

export default ReminderService;
