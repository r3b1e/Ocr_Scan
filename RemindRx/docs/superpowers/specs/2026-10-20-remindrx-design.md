# RemindRx — standalone, backend-free medication reminders (design)

Date: 2026-10-20 · Owner: Sunny

## Intent
A "RemindRx only" build: a small mobile app + website that does **only** manual
medication entry and reminders. No backend, no login, no network calls. All data
lives on the device (phone cache / browser storage) and all alarms are armed
locally. It reuses the proven HealthApp medication feature
(`Vivotal.HealthApp/src/features/medication/`) and the NativeFrontend web stack
(Vite + React + Tailwind), re-skinned to the RemindRx theme.

## Goals (v1)
1. **Add / edit / pause / delete medication manually** — same form as HealthApp
   AddMedicationScreen: name, type (22 types w/ icons), dose qty + unit,
   start/end date, 7 frequency modes (1/2/3/X× daily, specific weekdays,
   every X days, day of month), schedule times, meal relation, reminder
   on/off, lead time, mode (notification vs alarm).
2. **Reminders**
   - Mobile: notifee local triggers over a rolling 14-day window, re-armed on
     every save + app start (HealthApp pattern). `alarm` mode = full-screen
     ringer screen with looping sound; `notification` mode = heads-up with
     Taken / Skip / Snooze (10 min) actions. Fires with app killed / phone locked.
   - Web: installable PWA. While the tab or installed app is open, an in-page
     scheduler rings (sound + modal) and shows a system Notification. On open,
     doses whose time passed while closed are shown as "missed — log it?".
3. **Today** — timeline of today's doses (upcoming / due / taken / skipped /
   missed) with Taken / Skip / Snooze.
4. **History + adherence** — dose log by day, 7-day adherence %, current streak.
5. **Backup** — export all data to a JSON file, import from one (replace or merge).

## Non-goals
Backend, accounts, Auth0, Firebase/FCM, prescription scan/OCR, caretakers,
refill/stock tracking, iOS build/test this round (code stays cross-platform),
cross-device sync (backup file is the only bridge).

## Anti-goals (failure even if it "works")
- Any network call to Vivotal APIs or any analytics.
- A reminder that silently doesn't fire on Android (exact-alarm / notification
  permission / battery optimisation must be checked and surfaced in-app).
- Double-firing a dose.
- Touching the HealthApp or NativeFrontend repos (copy code; don't modify them).

## Theme
- Primary: Medical Teal / Deep Cyan `#0EA5E9` (pressed `#0284C7`, tint `#E0F2FE`)
- Accent: Coral `#FB7185` / soft orange `#F97316` — urgent alarms, missed/overdue
- Background: Pale Ice Blue `#F8FAFC`, cards crisp white, text slate-900/500
- Vibe: reliable, clean, clinical. Inputs, pickers, bottom sheets and type icons
  follow HealthApp's components (re-coloured), with light motion on the web.

## Structure
```
RemindRx/
  shared/   pure TS: types, logic, reminderLogic, zonedTime, catalog data,
            dose-log + adherence calc, backup schema/validation  (+ jest tests)
  mobile/   React Native 0.84 app, package com.periscope.remindrx, app name "RemindRx"
            deps: notifee, async-storage, datetimepicker, lucide-react-native,
            react-native-svg, safe-area-context, screens, navigation, sound,
            document picker + fs for backup. Metro watchFolders → ../shared
  web/      Vite + React 19 + Tailwind + lucide-react, PWA (manifest + SW for
            offline + notifications). Vite alias → ../shared
```
Storage: mobile AsyncStorage keys `rx.meds.v1`, `rx.doses.v1`, `rx.settings.v1`;
web localStorage same keys (wrapped in try/catch). Backup file = `{version:1,
exportedAt, meds, doses, settings}`.

Dose log entry: `{id: medId:YYYY-MM-DD:slot, medId, dateISO, slot, scheduledAt,
status: taken|skipped, at}`. "Missed" is derived (scheduled in past, no entry,
> 60 min late). Adherence = taken / scheduled-and-past over last 7 days.

## Verification
- shared: jest unit tests for firesOn/expand, adherence, backup validation.
- mobile: build debug APK, install on connected Pixel (4C061JEBF07719), add a
  med 2 min out in both modes, confirm notification + full-screen alarm fire
  with app swiped away; Taken/Skip from notification updates Today; export/import.
- web: `vite build` + run, browser test add → in-page alarm fires → log dose →
  history/adherence update; export/import round trip; reload persists.

## Detailed rules (settled by the builder)
- **Web is best-effort (Sunny chose this):** a persistent banner on the web
  explains "Reminders ring only while RemindRx is open in this browser — keep the
  tab/app open, or use the mobile app". Missed doses are caught up on reopen.
- **Code reuse:** copy and strip. Pure TS (types, logic, reminderLogic,
  zonedTime, catalog data) is lifted into `shared/` as-is, minus api/server
  flags/travel guard/prescription mapping. Types stay field-compatible with
  HealthApp `Medication`. UI is ported from HealthApp components and re-coloured.
- **Timezone:** follow device wall-clock (8:00 stays 8:00 after travel). There's
  no per-med tz. When the app comes to the foreground or the tz changes, it re-arms.
- **Slot** = index into `scheduleTimes` (sorted ascending). Past log entries are
  immutable. Editing times/frequency only affects future doses. Pause cancels
  alarms, and resume re-arms. Delete is a soft delete (status=deleted): alarms are
  cancelled, history is kept and shown greyed out.
- **Notification IDs** (deterministic, so re-arming can't double-fire):
  `med:{id}:{YYYYMMDD}:{slot}`, `…:early` for the lead-time reminder, and
  `…:snooze`. Taken/Skip cancels the siblings for that dose. Before re-arming,
  the app cancels all `med:` triggers.
- **Android reliability:** a Reminder Health card on Today and Settings shows
  notification permission, exact-alarm permission, full-screen-intent
  permission (Android 14+) and battery optimisation, each with a deep link to fix
  it. It's shown prominently, not as a blocking flow. First launch asks for the
  notification permission.
- **Backup:** the same JSON schema on web and mobile (files move either way).
  Validation rejects an unknown major version. Merge = the imported record wins
  on the same id. Replace = wipe then load. Device-only settings (permissions
  state) aren't exported. After import, the app re-arms all alarms.

## Builder's calls (not discussed with Sunny)
Package id, storage key names, 14-day window, 10-min snooze, 60-min "missed"
threshold, shared folder approach, AsyncStorage over SQLite, and everything
under "Detailed rules" except the web best-effort choice.
