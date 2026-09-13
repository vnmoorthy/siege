// Read-only capture of the existing SIEGE UI; run from the repository root.
const { chromium } = require('../../deck/node_modules/playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const out = path.resolve(process.argv[2]);
  const profile = JSON.parse(fs.readFileSync(path.join(out, 'attacker-profile.json'), 'utf8'));
  const origin = 'http://localhost:8000';
  const manifest = {
    capture_started_at: new Date().toISOString(), origin,
    policy: 'GET-only network access. No joins, attacks, admin mutations, resets, or round changes.',
    profile_note: 'Existing attacker profile served from a read-only SQLite snapshot to prevent the live GET endpoint updating last_seen. All history requests use the live read-only endpoint. Screenshots show the actual product UI.',
    captures: [], blocked_requests: [], errors: []
  };
  const browser = await chromium.launch({headless: true});
  async function context(options = {}) {
    const ctx = await browser.newContext({colorScheme: 'dark', deviceScaleFactor: 1, ...options});
    await ctx.route('**/*', async route => {
      const request = route.request();
      if (!['GET', 'HEAD'].includes(request.method())) {
        manifest.blocked_requests.push({method: request.method(), url: request.url()});
        return route.abort();
      }
      const url = new URL(request.url());
      if (url.origin === origin && url.pathname === '/api/attackers/' + profile.id) {
        return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(profile)});
      }
      if (url.origin === origin && /^\/api\/attackers\/[^/]+$/.test(url.pathname)) {
        manifest.blocked_requests.push({method: 'GET', url: request.url(), reason: 'presence-mutating profile endpoint'});
        return route.abort();
      }
      return route.continue();
    });
    return ctx;
  }
  async function ready(page, route) {
    await page.goto(origin + route, {waitUntil: 'domcontentloaded', timeout: 60000});
    await page.waitForFunction(() => document.body.innerText.includes('SIEGE') && !document.body.innerText.includes('Loading state…'), {timeout: 60000});
    await page.waitForTimeout(1500);
    const text = await page.locator('body').innerText();
    if (/(?:sk-(?:proj-)?[A-Za-z0-9]{15,}|WANDB_API_KEY\s*[=:]|TYPESAFE_API_KEY\s*[=:]|ANTHROPIC_API_KEY\s*[=:])/.test(text)) {
      throw new Error('Possible secret-like text rendered; capture skipped');
    }
  }
  async function shot(page, name, note) {
    const state = await page.request.get(origin + '/api/state', {timeout: 45000}).then(r => r.json()).catch(() => null);
    await page.screenshot({path: path.join(out, name), fullPage: false, timeout: 60000});
    manifest.captures.push({file: name, captured_at: new Date().toISOString(), viewport: page.viewportSize(), url: page.url(), note,
      mode: state?.mode, gate_version: state?.gate_version, totals: state?.totals,
      providers: state?.providers, join_url: state?.join_url,
      current_round: state?.current_round});
    console.log('Saved ' + name);
  }
  try {
    const desktop = await context({viewport: {width: 1920, height: 1080}, recordVideo: {dir: path.join(out, 'video'), size: {width: 1920, height: 1080}}});
    const war = await desktop.newPage();
    await ready(war, '/?mock=0');
    await shot(war, 'warroom-live-1920x1080.png', 'Actual live war room; metrics are those captured, not a staged round.');
    const videoStart = new Date().toISOString();
    await war.waitForTimeout(10000);
    await shot(war, 'warroom-live-end-1920x1080.png', 'End of ten-second live observation.');
    await desktop.close();
    manifest.video = {file: path.relative(out, await war.video().path()), steady_observation_started_at: videoStart,
      note: 'Raw Playwright screen recording includes initial page load plus a ten-second steady observation; no simulated events injected.'};
  } catch (e) {manifest.errors.push({stage: 'warroom', error: String(e)}); console.log('Warroom: ' + e.message);}
  try {
    const adminCtx = await context({viewport: {width: 1920, height: 1080}});
    const admin = await adminCtx.newPage();
    await ready(admin, '/admin?mock=0');
    await shot(admin, 'admin-live-1920x1080.png', 'Actual live admin overview. No admin control clicked; trace payloads remain collapsed.');
    await admin.getByText('Gate versions', {exact: true}).scrollIntoViewIfNeeded();
    const v3 = admin.getByRole('button').filter({hasText: /^v3\s/});
    if (await v3.count() === 1) {
      await v3.click();
      await admin.waitForTimeout(1200);
      await admin.getByText('Gate versions', {exact: true}).scrollIntoViewIfNeeded();
      await shot(admin, 'admin-recorded-gate-v3-1920x1080.png', 'Read-only selection of recorded v3 details; current active gate may differ.');
    }
    await adminCtx.close();
  } catch (e) {manifest.errors.push({stage: 'admin', error: String(e)}); console.log('Admin: ' + e.message);}
  try {
    const phoneCtx = await context({viewport: {width: 430, height: 932}, isMobile: true, hasTouch: true});
    await phoneCtx.addInitScript(id => {
      localStorage.setItem('siege_attacker_id', id);
      sessionStorage.removeItem('siege_mock');
    }, profile.id);
    const phone = await phoneCtx.newPage();
    await ready(phone, '/attack?mock=0');
    await phone.getByText('grant_store_credit', {exact: true}).first().waitFor({timeout: 45000});
    await phone.getByRole('button').filter({hasText: /grant_store_credit/}).first().click();
    await phone.getByText('oracle', {exact: true}).first().scrollIntoViewIfNeeded();
    await shot(phone, 'phone-recorded-credit-breach-430x932.png', 'Actual existing breach history. Tool call expanded; no chat submitted. Profile GET uses SQLite snapshot to preserve last_seen.');
    await phoneCtx.close();
  } catch (e) {manifest.errors.push({stage: 'phone', error: String(e)}); console.log('Phone: ' + e.message);}
  await browser.close();
  manifest.capture_ended_at = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log('Manifest: ' + path.join(out, 'manifest.json'));
})().catch(e => {console.error(e.message); process.exitCode = 1;});
