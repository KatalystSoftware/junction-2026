// End-to-end walk through the demo path with headless Chrome; saves screenshots and fails on any page error.
// Usage: (cd app && python3 -m http.server 8765) & node tools/e2e.js   [env: BASE, CHROME=/path/to/chrome, PWCORE=/path/to/playwright-core, OUT]
const path = require("path");
const { chromium } = require(process.env.PWCORE || "playwright-core");
const BASE = process.env.BASE || "http://127.0.0.1:8765/";
const OUT = process.env.OUT || path.join(__dirname, "shots");
require("fs").mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || undefined, headless: true });
  const pg = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  const errs = []; pg.on("pageerror", e => errs.push(e.message)); pg.on("console", m => m.type() === "error" && errs.push(m.text()));
  const shot = async (n, full) => pg.screenshot({ path: `${OUT}/${n}.png`, fullPage: !!full });
  const go = async h => { await pg.goto(BASE + h); await pg.waitForTimeout(400); };
  await go("#/"); await pg.evaluate(() => localStorage.clear()); await go("#/"); await shot("home", true);
  // company: one-minute confirmation
  await go("#/company/puro"); const c0 = await pg.textContent("#cnt"); await shot("company0");
  await pg.click('button[data-act="fi"][data-v="helpful"]'); await pg.waitForTimeout(200); const c1 = await pg.textContent("#cnt");
  await pg.click('button[data-act="confirm"]'); await pg.waitForTimeout(300); await shot("company1", true);
  console.log("count required ->", c0, "| helpful ->", c1);
  // candidate
  await go("#/cand"); for (let i = 0; i < 7; i++) { await shot("cand" + i, true); const n = await pg.$('button[data-act="step"][data-v="' + (i + 1) + '"]'); if (n) { await n.click(); await pg.waitForTimeout(150); } }
  await go("#/cand/stands"); await shot("stands", true);
  const recs = await pg.$$eval(".stand .top2 b", e => e.map(x => x.textContent)); console.log("stands:", recs.slice(0, 5).join(" | "));
  await go("#/cand/me"); await pg.selectOption('select[data-act="medepth"][data-i="2"]', "work"); await pg.waitForTimeout(200); await shot("me", true);
  await go("#/cand/evidence"); await pg.click('button[data-act="evsum"]'); await pg.waitForTimeout(1500); await shot("evidence");
  // organiser
  await go("#/org/puro"); await pg.click('.head[data-id="C-027"]'); await pg.waitForTimeout(200);
  await pg.click('.cand .srcbtn'); await pg.waitForTimeout(200);
  await pg.click('button[data-act="pick"][data-v="introduce"][data-id="C-027"]');
  await pg.click('button[data-act="decide"][data-id="C-027"]'); await pg.waitForTimeout(200); const t1 = await pg.textContent("#toast");
  await pg.fill("#why-C-027", "Power BI and SQL at work for 4-5 years; their exact stack. Finnish only helpful."); await pg.click('button[data-act="decide"][data-id="C-027"]'); await pg.waitForTimeout(300);
  await pg.click('button[data-act="reveal"][data-id="C-027"]'); await pg.waitForTimeout(200);
  await shot("org1"); console.log("toast without reason:", t1);
  const el = await pg.$('.cand:has(.head[data-id="C-027"])'); await el.screenshot({ path: `${OUT}/org-pair.png` });
  await pg.click('input[data-act="filt"][data-v="must"]'); await pg.waitForTimeout(300);
  console.log("puro criteria:", (await pg.textContent(".crit")).slice(0, 90));
  await go("#/org/lahde"); await shot("org-lahde"); console.log("lahde alert:", (await pg.textContent(".warnbox")).slice(0, 160));
  await go("#/company/puro/intros"); await shot("intros", true);
  await go("#/log"); await shot("log");
  await go("#/after"); await pg.click('span[data-act="fb"][data-side="cand"][data-v="Yes"]'); await shot("after", true);
  await go("#/concept"); await pg.waitForTimeout(500); await shot("concept", true);
  await pg.setViewportSize({ width: 390, height: 844 }); await go("#/cand/stands"); await shot("mobile-stands"); await go("#/company/puro"); await shot("mobile-company"); await go("#/cand/me"); await shot("mobile-me", true); await go("#/log"); await shot("mobile-log");
  console.log("errors:", errs.length ? errs : "none");
  await b.close();
})().catch(e => { console.error("FAIL", e.message); process.exit(1); });
