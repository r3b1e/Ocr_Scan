/**
 * Reminder health: everything that can stop an on-device reminder from firing
 * on Android, with a way to fix each one.
 */
import notifee, { AndroidNotificationSetting, AuthorizationStatus } from '@notifee/react-native';
import { NativeModules, Platform } from 'react-native';

const RxSystem = NativeModules.RxSystem as
    | {
          canUseFullScreenIntent(): Promise<boolean>;
          openFullScreenIntentSettings(): Promise<boolean>;
          setShowOverLockScreen(on: boolean): void;
      }
    | undefined;

/** Let the alarm ringer (and only it) appear over the lock screen. */
export const setShowOverLockScreen = (on: boolean) => {
    if (Platform.OS === 'android') RxSystem?.setShowOverLockScreen(on);
};

export interface ReminderHealth {
    notifications: boolean;
    exactAlarm: boolean;
    fullScreen: boolean;
    /** true = Android may delay/kill reminders to save battery. */
    batteryOptimized: boolean;
}

export type HealthKey = keyof ReminderHealth;

export const HEALTH_COPY: Record<HealthKey, { title: string; ok: string; bad: string }> = {
    notifications: { title: 'Notifications', ok: 'Allowed', bad: 'Blocked: reminders can’t appear' },
    exactAlarm: { title: 'Alarms & reminders', ok: 'Exact timing on', bad: 'Off: reminders may be late or never fire' },
    fullScreen: { title: 'Full-screen alarm', ok: 'Alarms can take over the screen', bad: 'Off: alarms show as a small notification' },
    batteryOptimized: { title: 'Battery optimisation', ok: 'Unrestricted', bad: 'Restricted: Android may delay reminders' },
};

export const isHealthy = (h: ReminderHealth) => h.notifications && h.exactAlarm && h.fullScreen && !h.batteryOptimized;

export const issues = (h: ReminderHealth): HealthKey[] =>
    (Object.keys(HEALTH_COPY) as HealthKey[]).filter(k => (k === 'batteryOptimized' ? h[k] : !h[k]));

export async function getReminderHealth(): Promise<ReminderHealth> {
    if (Platform.OS !== 'android') {
        const s = await notifee.getNotificationSettings().catch(() => null);
        return { notifications: s?.authorizationStatus !== AuthorizationStatus.DENIED, exactAlarm: true, fullScreen: true, batteryOptimized: false };
    }
    const [s, battery, fullScreen] = await Promise.all([
        notifee.getNotificationSettings().catch(() => null),
        notifee.isBatteryOptimizationEnabled().catch(() => false),
        RxSystem?.canUseFullScreenIntent().catch(() => true) ?? Promise.resolve(true),
    ]);
    return {
        notifications: !!s && s.authorizationStatus !== AuthorizationStatus.DENIED && s.authorizationStatus !== AuthorizationStatus.NOT_DETERMINED,
        exactAlarm: s?.android?.alarm === AndroidNotificationSetting.ENABLED,
        fullScreen,
        batteryOptimized: battery,
    };
}

/** Ask for / deep-link to the setting behind one health item. */
export async function fixHealth(key: HealthKey): Promise<void> {
    switch (key) {
        case 'notifications': {
            const s = await notifee.requestPermission();
            if (s.authorizationStatus === AuthorizationStatus.DENIED) await notifee.openNotificationSettings();
            return;
        }
        case 'exactAlarm':
            return notifee.openAlarmPermissionSettings();
        case 'fullScreen':
            await RxSystem?.openFullScreenIntentSettings();
            return;
        case 'batteryOptimized':
            return notifee.openBatteryOptimizationSettings();
    }
}
