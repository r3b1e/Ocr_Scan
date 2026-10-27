# RemindRx: mobile

Offline medication reminders for Android (iOS-ready code, not yet built or tested on iOS).
No backend, no login and no network: medicines and the dose log live in AsyncStorage, and
reminders are armed on the device with notifee (AlarmManager exact, allowWhileIdle).

## Run (debug)

```sh
npm install
npm start                      # Metro on :8088
adb reverse tcp:8088 tcp:8088
npm run android                # builds + installs com.periscope.remindrx
```

## Layout

- `App.tsx`: navigation (tabs: Today / Medications / History / Settings, plus Add and Alarm), and startup alarm routing
- `src/state/`: AsyncStorage persistence + React store (every medicine change re-arms reminders)
- `src/reminders/ReminderService.ts`: notifee scheduling, notification actions, background handler
- `src/reminders/permissions.ts` + `RxSystemModule.kt`: the "reminder health" checks (notifications, exact alarms, full-screen intent, battery)
- `src/screens/`, `src/components/`: UI; pickers ported from Vivotal HealthApp
- `../shared/`: medication logic shared with the website (types, schedule, dose log, adherence, backup)

## Reminder modes

- **Notification**: heads-up with Taken / Skip / Snooze 10m; works with the app closed.
- **Alarm**: full-screen ringer over the lock screen with a looping sound until you act.

Settings → "Send a test alarm" fires one in 10 s so you can check your phone's setup.
