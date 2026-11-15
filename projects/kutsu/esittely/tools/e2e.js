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
  // applicant joining: invitation -> reading -> general -> event questions -> own words -> confirm -> done, every step a URL
  await go("#/join"); await pg.evaluate(() => localStorage.removeItem("esittely-demo-v2")); await pg.reload(); await pg.waitForTimeout(300); await go("#/join"); await shot("join0", true);
  await pg.click('button[data-act="jn-scan"]'); await pg.waitForTimeout(4200); await shot("join1"); const h1 = await pg.evaluate(() => location.hash);
  await pg.click('button[data-act="jn-go"][data-v="check/general"]'); await pg.waitForTimeout(200); await shot("join-general", true); const h2 = await pg.evaluate(() => location.hash);
  const live0 = await pg.textContent(".livemini b"), nextOn0 = await pg.$eval('.jnav button[data-act="jn-go"]', b => !b.disabled);
  await pg.click('.jf:has(button[data-act="jn-rm"]) button[data-act="jn-edit"]'); await pg.waitForTimeout(150); const opened = await pg.$$eval(".jf .edit", e => e.length);
  await pg.click('.jf button[data-act="jn-depth"][data-v="project"]'); await pg.waitForTimeout(150);   // correct one skill's depth
  await pg.click('.jf button[data-act="jn-rm"]'); await pg.waitForTimeout(150);
  let ticks = 0; while (await pg.$('button[data-act="jn-ok"]')) { await pg.click('button[data-act="jn-ok"]'); ticks++; await pg.waitForTimeout(80); }
  const live1 = await pg.textContent(".livemini b"); await shot("join-general-b", true);
  await go("#/join/check/event"); await shot("join-event", true);
  const pre = await pg.$$eval(".evq .pre", e => e.length), qn = await pg.$$eval(".evq", e => e.length);
  await pg.click('.evq .opt:not(.on)[data-act="jn-evskill"]'); await pg.waitForTimeout(120);
  for (const [id, v] of [["build", "b"], ["depth", "a"], ["pace", "b"]]) { await pg.click(`button[data-act="jn-trade"][data-t="${id}"][data-v="${v}"]`); await pg.waitForTimeout(80); }
  const ynl = await pg.$('button[data-act="jn-ans"][data-v="learning"]'); if (ynl) { await ynl.click(); await pg.waitForTimeout(100); }
  await pg.click('.jnav button[data-act="jn-go"]'); await pg.waitForTimeout(200); const h3 = await pg.evaluate(() => location.hash);
  await pg.fill('textarea[data-act="jn-own"][data-v="about"]', "I like explaining numbers to people who hate numbers."); await pg.dispatchEvent('textarea[data-act="jn-own"][data-v="about"]', "change");
  await pg.click('.jnav button[data-act="jn-go"]'); await pg.waitForTimeout(200); await shot("join-confirm", true);
  const confOn = await pg.$eval('button[data-act="jn-confirm"]', b => !b.disabled);
  await pg.click('button[data-act="jn-confirm"]'); await pg.waitForTimeout(250); await shot("join-done", true); const h4 = await pg.evaluate(() => location.hash), done = await pg.textContent("h1");
  await go("#/org/puro"); await pg.click('.head[data-id="C-027"]'); await pg.waitForTimeout(200); const badge = await pg.textContent('.cand:has(.head[data-id="C-027"])');
  console.log("join: urls", h1, h2, h3, h4, "| live", live0, "->", live1, "| ticked", ticks, "| controls open before change:", opened, "| next enabled unfilled:", nextOn0, "| event questions", qn, "prefilled", pre, "| confirm enabled:", confOn, "|", done.slice(0, 30), "| organiser sees checked badge:", /checked by candidate/.test(badge), "| own words:", /In their own words/.test(badge), "| event answers:", /Event questions/.test(badge));
  // organiser edits the event's questions
  await go("#/org/questions"); await shot("org-questions", true); const nq = await pg.$$eval(".qedit", e => e.length);
  await pg.fill("#qe-new", "Would you present a 5-minute demo at a stand?"); await pg.click('button[data-act="qe-add"]'); await pg.waitForTimeout(150);
  await pg.click('.qedit input[data-act="qe-on"]'); await pg.waitForTimeout(150); const nq2 = await pg.$$eval(".qedit", e => e.length), off = await pg.$$eval(".qedit.off", e => e.length);
  await go("#/join/check/event"); const shown = await pg.$$eval(".evq", e => e.length), custom = await pg.$('input[data-act="jn-anstext"]') !== null;
  console.log("event questions: organiser", nq, "->", nq2, "off", off, "| applicant sees", shown, "custom free-text:", custom);
  // organiser review queue: one at a time, decide with a reason, auto-advance
  await go("#/org/virta/review"); await shot("review", true);
  const q0 = await pg.textContent(".livecount .n"), first = await pg.$eval(".qrow.on span", e => e.textContent);
  await pg.click('.revcard button[data-act="pick"][data-v="introduce"]'); await pg.fill('.revcard input[id^="why-"]', "Their exact stack at work for years; asked to meet them."); await pg.click('.revcard button[data-act="decide"]'); await pg.waitForTimeout(250);
  const q1 = await pg.textContent(".livecount .n"), second = await pg.$eval(".qrow.on span", e => e.textContent);
  await pg.click('.revcard button[data-act="rq-skip"]'); await pg.waitForTimeout(150); const third = await pg.$eval(".qrow.on span", e => e.textContent);
  console.log("review: to decide", q0, "->", q1, "| current", first, "->", second, "-> skip ->", third, "| decided badge:", (await pg.textContent(".qrow.done")).includes("Introduce"));
  // demo control panel
  await pg.click("#demo summary"); await pg.click('[data-dbg="org-intro"]'); await pg.waitForTimeout(200); console.log("dbg org-intro ->", location_hash = await pg.evaluate(() => location.hash), (await pg.textContent(".cand:has(.head[data-id=\"C-027\"])")).includes("Introduce") );
  await pg.click("#demo summary"); await pg.click('[data-dbg="jn-done"]'); await pg.waitForTimeout(200); console.log("dbg jn-done ->", await pg.evaluate(() => location.hash), (await pg.textContent("h1")).slice(0, 30));
  console.log("errors:", errs.length ? errs : "none");
  await b.close();
})().catch(e => { console.error("FAIL", e.message); process.exit(1); });
