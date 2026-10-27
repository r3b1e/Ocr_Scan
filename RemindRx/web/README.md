# RemindRx — web

An installable website (PWA) for manual medication reminders. It has no backend and no account. All data stays in this browser's localStorage (`rx.meds.v1`, `rx.doses.v1`, `rx.settings.v1`).

```bash
npm install
npm run dev        # http://localhost:5175
npm run build      # type-check + production build → dist/
npm run preview    # serve dist/ on http://localhost:4175
```

- Domain logic comes from `../shared` through the `@shared` alias. The web app has no copies of it.
- Reminders ring (sound, popup and system notification) only while the site is open in a tab or as the installed app. When you reopen it, doses that passed while it was closed show as missed.
- Backup: Settings → Export/Import. The JSON format is the same one the mobile app uses.
- Scan tab: reads a prescription photo through the extraction service in the parent repository (`python -m service`). Set `VITE_EXTRACT_API` in `.env` (see `.env.example`); the tab explains itself when the service is unreachable. Medicines are only saved after you confirm them in the Add Medication form.
- `node scripts/make-icons.mjs` re-renders the PNG icons from `public/icon.svg`. It uses your local Chrome.
- `node scripts/e2e.mjs [baseUrl] [screenshotDir]` runs an end-to-end check against a running preview. It takes about 90 s because it waits for a real reminder.
