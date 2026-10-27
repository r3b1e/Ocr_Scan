// End-to-end check against a running preview (default http://localhost:4175):
// add an alarm-mode medicine 1 minute out → alarm rings → Taken → History 100%
// → export → erase → import → reload persists. Uses the local Chrome.
// Usage: node scripts/e2e.mjs [baseUrl] [screenshotDir]
import { chromium } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const BASE = process.argv[2] || 'http://localhost:4175';
const OUT = process.argv[3] || '.';
const shot = async (page, name) => (await page.waitForTimeout(450), page.screenshot({ path: join(OUT, `web-${name}.png`), fullPage: false }));
const step = msg => console.log(`✓ ${msg}`);
const fail = msg => { console.error(`✗ ${msg}`); process.exit(1); };

const browser = await chromium.launch({ channel: 'chrome' });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, acceptDownloads: true });
await ctx.grantPermissions(['notifications'], { origin: BASE });
const page = await ctx.newPage();
const external = [];
page.on('request', r => { if (!r.url().startsWith(BASE) && !r.url().startsWith('data:') && !r.url().startsWith('blob:')) external.push(r.url()); });
page.on('dialog', d => d.accept());
page.on('pageerror', e => fail(`page error: ${e.message}`));

await page.goto(BASE);
await page.getByText('Add your first medicine').waitFor();
await shot(page, 'mobile-empty');
step('empty state renders');

await page.getByRole('button', { name: 'Add medication' }).first().click();
await page.getByLabel("Pill’s Name").fill('Metformin 500');
await page.getByRole('button', { name: /^Type/ }).click();
await page.getByRole('dialog', { name: 'Medication type' }).getByRole('button', { name: 'Capsule' }).click();
await page.getByRole('button', { name: 'After food' }).click();
await page.getByRole('button', { name: /Alarm/ }).click();
const at = new Date(Date.now() + 60_000);
const hhmm = `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`;
await page.getByLabel('Dose time 1').fill(hhmm);
await shot(page, 'mobile-form');
await page.getByRole('button', { name: 'Done' }).click();
await page.locator('[data-testid="dose-row"]').first().waitFor();
const st0 = await page.locator('[data-testid="dose-row"]').first().getAttribute('data-state');
if (st0 !== 'upcoming') fail(`expected upcoming, got ${st0}`);
await shot(page, 'mobile-today');
step(`medicine saved for ${hhmm}, dose upcoming`);

const alarm = page.getByRole('alertdialog');
await alarm.waitFor({ timeout: 120_000 });
if (!(await alarm.getByText('Metformin 500').isVisible())) fail('alarm shows wrong medicine');
await shot(page, 'mobile-alarm');
step('alarm modal fired at dose time');

await alarm.getByRole('button', { name: 'Taken' }).click();
await alarm.waitFor({ state: 'detached' });
const st1 = await page.locator('[data-testid="dose-row"]').first().getAttribute('data-state');
if (st1 !== 'taken') fail(`expected taken, got ${st1}`);
step('Taken logged on Today');

await page.getByRole('button', { name: 'History' }).click();
const pct = await page.getByTestId('adherence-pct').textContent();
if (pct !== '100%') fail(`adherence ${pct}`);
await shot(page, 'mobile-history');
step('History shows 100%');

await page.getByRole('button', { name: 'Medications' }).last().click();
await shot(page, 'mobile-meds');

await page.getByRole('button', { name: 'Settings' }).click();
const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export' }).click()]);
const file = await dl.path();
const json = JSON.parse(readFileSync(file, 'utf8'));
if (json.app !== 'RemindRx' || json.meds.length !== 1 || json.doses.length !== 1) fail('export content wrong');
step(`export valid (${dl.suggestedFilename()})`);
await shot(page, 'mobile-settings');

await page.getByRole('button', { name: 'Erase all data' }).click();
await page.getByText('All data erased.').waitFor();
await page.getByTestId('import-input').setInputFiles(file);
await page.getByRole('dialog', { name: 'Import backup' }).getByRole('button', { name: 'Replace' }).click();
await page.getByText('Imported 1 medication and 1 dose record.').waitFor();
step('erase + import restored data');

await page.reload();
await page.getByRole('button', { name: 'Medications' }).last().click();
const cards = await page.getByTestId('med-card').count();
if (cards !== 1) fail(`after reload ${cards} cards`);
step('data persists after reload');

const bad = await (async () => {
    const p = await ctx.newPage();
    await p.goto(BASE);
    await p.getByRole('button', { name: 'Settings' }).click();
    await p.getByTestId('import-input').setInputFiles({ name: 'x.json', mimeType: 'application/json', buffer: Buffer.from('{"nope":1}') });
    const t = await p.getByRole('status').textContent();
    await p.close();
    return t;
})();
if (!bad?.includes('not a RemindRx backup')) fail(`bad import message: ${bad}`);
step('foreign file rejected with message');

await page.setViewportSize({ width: 1366, height: 900 });
await page.getByRole('button', { name: 'Today' }).first().click();
await shot(page, 'desktop-today');

if (external.length) fail(`external requests: ${external.join(', ')}`);
step('no external network requests');
await browser.close();
console.log('ALL PASSED');
