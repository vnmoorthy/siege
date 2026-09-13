// Lightweight retry for live desktop screenshots, with no video encoding.
const { chromium } = require('../../deck/node_modules/playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const out = path.resolve(process.argv[2]);
  const manifestPath = path.join(out, 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1, colorScheme: 'dark'});
  await context.route('**/*', route => ['GET', 'HEAD'].includes(route.request().method()) ? route.continue() : route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(120000);
  async function capture(name, note) {
    const body = await page.locator('body').innerText();
    if (/(?:sk-(?:proj-)?[A-Za-z0-9]{15,}|WANDB_API_KEY\s*[=:]|TYPESAFE_API_KEY\s*[=:])/.test(body)) throw new Error('Secret-like text; capture skipped');
    const state = await page.request.get('http://localhost:8000/api/state', {timeout: 45000}).then(r => r.json()).catch(() => null);
    await page.screenshot({path: path.join(out, name), animations: 'disabled', timeout: 60000});
    manifest.captures.push({file: name, captured_at: new Date().toISOString(), url: page.url(), viewport: page.viewportSize(), note,
      mode: state?.mode, gate_version: state?.gate_version, totals: state?.totals, providers: state?.providers,
      join_url: state?.join_url, current_round: state?.current_round});
    console.log('Saved ' + name);
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  }
  for (const spec of [
    {route: '/?mock=0', ready: 'Leaderboard', file: 'warroom-live-1920x1080.png'},
    {route: '/admin?mock=0', ready: 'Gate versions', file: 'admin-live-1920x1080.png'}
  ]) {
    try {
      console.log('Navigating ' + spec.route);
      await page.goto('http://localhost:8000' + spec.route, {waitUntil: 'domcontentloaded', timeout: 60000}).catch(e => console.log('Navigation warning: ' + e.message.split('\n')[0]));
      await page.getByText(spec.ready, {exact: true}).first().waitFor({state: 'visible'});
      await page.waitForTimeout(1000);
      await capture(spec.file, 'Actual live UI. CSS animations paused only for still screenshot capture; no demo event or metric was changed.');
      if (spec.ready === 'Gate versions') {
        await page.getByText('Gate versions', {exact: true}).scrollIntoViewIfNeeded();
        const v3 = page.getByRole('button').filter({hasText: /^v3\s/});
        if (await v3.count() === 1) {
          await v3.click();
          await page.getByText('12 / 16', {exact: true}).waitFor();
          await page.getByText('Gate versions', {exact: true}).scrollIntoViewIfNeeded();
          await capture('admin-recorded-gate-v3-1920x1080.png', 'Recorded gate v3 selected using read-only UI; actual 12/12 attack catch and 15/16 benign allow evaluation.');
        }
      }
    } catch (e) {manifest.errors.push({stage: 'desktop_retry ' + spec.route, at: new Date().toISOString(), error: e.message}); console.log(e.message.split('\n')[0]);}
  }
  await browser.close();
  manifest.capture_ended_at = new Date().toISOString();
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
})().catch(e => {console.error(e.message);process.exitCode = 1;});
