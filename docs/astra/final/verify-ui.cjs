const {chromium} = require('../../deck/node_modules/playwright');
const {spawn} = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const root = path.resolve(__dirname, '../../..');
  const origin = 'http://127.0.0.1:8768';
  const report = {started_at: new Date().toISOString(), origin, mode: 'mock', checks: [], page_errors: [], network_errors: []};
  const serverCode = `from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler\nfrom pathlib import Path\nimport os, sys\nos.chdir(sys.argv[1])\nclass Handler(SimpleHTTPRequestHandler):\n def do_GET(self):\n  target=self.path.split('?')[0]\n  if not Path('.'+target).is_file() and not Path('.'+target).is_dir():\n   self.path='/index.html'\n  super().do_GET()\n def log_message(self,*args): pass\nThreadingHTTPServer(('127.0.0.1',8768),Handler).serve_forever()\n`;
  const server = spawn('python3', ['-u', '-c', serverCode, path.join(root, 'frontend/dist')], {stdio: ['ignore', 'ignore', 'pipe']});
  let serverError = '';
  server.stderr.on('data', d => serverError += d.toString());
  let browser;
  try {
    for (let i = 0; i < 30; i++) {
      if (server.exitCode !== null) throw new Error('Static server could not start: ' + serverError);
      try {if ((await fetch(origin)).ok) break;} catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    browser = await chromium.launch({headless: true});
    for (const spec of [
      {name: 'arena-desktop', width: 1440, height: 1000, route: '/?mock=1', ready: 'Break the agent.'},
      {name: 'arena-mobile', width: 390, height: 844, route: '/?mock=1', ready: 'Break the agent.'},
      {name: 'join-mobile', width: 390, height: 844, route: '/attack?mock=1', ready: 'Enter the siege.'}
    ]) {
      const ctx = await browser.newContext({viewport: {width: spec.width, height: spec.height}, deviceScaleFactor: 1, isMobile: spec.width < 500, hasTouch: spec.width < 500, colorScheme: 'dark'});
      const page = await ctx.newPage();
      page.on('pageerror', e => report.page_errors.push({screen: spec.name, error: e.message}));
      page.on('requestfailed', req => report.network_errors.push({screen: spec.name, url: req.url(), error: req.failure()?.errorText}));
      await page.goto(origin + spec.route, {waitUntil: 'domcontentloaded', timeout: 30000});
      await page.getByText(spec.ready, {exact: false}).first().waitFor({timeout: 30000});
      await page.getByText('Mock data', {exact: true}).waitFor();
      if (spec.name.startsWith('arena')) await page.locator('.arena-join small').filter({hasText: 'attack?mock=1'}).waitFor();
      await page.waitForTimeout(1000);
      const geometry = await page.evaluate(() => ({viewport: document.documentElement.clientWidth, width: document.documentElement.scrollWidth,
        overflowElements: [...document.querySelectorAll('body *')].filter(e => {const r=e.getBoundingClientRect();return r.width>0 && (r.left < -1 || r.right > innerWidth+1)}).slice(0,8).map(e => ({tag:e.tagName, class:e.className, right:e.getBoundingClientRect().right}))}));
      const check = {screen: spec.name, captured_at: new Date().toISOString(), no_horizontal_overflow: geometry.width <= geometry.viewport, geometry,
        mock_visible: await page.getByText('Mock data', {exact: true}).isVisible(), url: page.url()};
      if (spec.name.startsWith('arena')) {
        check.telemetry_href = await page.getByRole('link', {name: 'Telemetry', exact: true}).getAttribute('href');
        check.telemetry_correct = check.telemetry_href === '/warroom?mock=1';
        check.qr_display_url = await page.locator('.arena-join small').innerText();
        check.qr_correct = check.qr_display_url === '127.0.0.1:8768/attack?mock=1';
        check.qr_svg_present = await page.locator('.arena-qr svg').count() === 1;
      } else {
        check.nickname_field_height = (await page.getByLabel('Your nickname', {exact: true}).boundingBox()).height;
        check.join_button_height = (await page.getByRole('button', {name: 'Join the siege', exact: true}).boundingBox()).height;
        check.join_initially_disabled = await page.getByRole('button', {name: 'Join the siege', exact: true}).isDisabled();
      }
      await page.screenshot({path: path.join(__dirname, spec.name+'.png'), fullPage: false, animations: 'disabled'});
      report.checks.push(check);
      console.log(JSON.stringify(check));
      await ctx.close();
    }
  } catch (e) {report.error = e.message; console.error(e.message);process.exitCode=1;}
  finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    report.ended_at = new Date().toISOString();
    fs.writeFileSync(path.join(__dirname, 'verification.json'), JSON.stringify(report, null, 2));
  }
})();
