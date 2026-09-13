// node shots.js <attackerId> <lsKey>   -> writes docs/shots/{warroom,admin,attack}.png
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
(async () => {
  const [attackerId, lsKey] = process.argv.slice(2);
  const out = path.resolve(__dirname, "..", "shots");
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const shot = async (url, w, h, file, setup, mobile = false) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: mobile, hasTouch: mobile, colorScheme: "dark" });
    const page = await ctx.newPage();
    if (setup) { await page.goto("http://localhost:8000/attack"); await page.evaluate(setup); }
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(3500);
    await page.screenshot({ path: path.join(out, file), fullPage: false });
    console.log("wrote", file);
    await ctx.close();
  };
  const only = process.argv[4];
  if (!only) { await shot("http://localhost:8000/", 1920, 1080, "warroom.png"); await shot("http://localhost:8000/admin", 1600, 1000, "admin.png"); }
  if (attackerId && lsKey) {
    await shot("http://localhost:8000/attack", 390, 844, "attack.png", `localStorage.setItem(${JSON.stringify(lsKey)}, ${JSON.stringify(attackerId)})`, true);
  }
  await browser.close();
})();
