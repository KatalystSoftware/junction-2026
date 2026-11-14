// Plain-node tests of the core logic: no browser, no dependencies. Run: node tools/test_logic.js
globalThis.window = globalThis;
require("../app/data.js"); require("../app/logic.js");
const assert = require("assert"), D = window.DATA, L = window.LOGIC;
let n = 0; const t = (name, fn) => { fn(); n++; console.log("ok", name); };
const co = id => D.companies.find(c => c.id === id), P = D.candidates;

t("extractor reads must-haves, nice-to-haves and sources from a job ad", () => {
  const p = L.extract(co("kuura").ad);
  assert.deepStrictEqual(p.must, [["java", "kotlin"], ["sql"]]);
  assert.ok(p.nice.includes("kubernetes"));
  assert.ok(p.src["skill:sql"].length > 0, "every field keeps its source line");
});
t("Finnish: only explicit wording counts; company descriptions don't", () => {
  assert.strictEqual(L.extract(co("puro").ad).finnish, "required");
  assert.strictEqual(L.extract(co("lahde").ad).finnish, "unstated"); // "Finnish and English." is unclear, so ask the company
  assert.strictEqual(L.extract("Developer\nWe build apps for Finnish brands.").finnish, "unstated");
});
t("live count is aggregate and suppresses small numbers", () => {
  const req = L.poolCount(L.companyProfile(co("puro")), P), help = L.poolCount(L.companyProfile(co("puro"), { finnish: "helpful" }), P);
  assert.strictEqual(req.n, 7); assert.strictEqual(help.n, 14);
  const tiny = L.poolCount(L.companyProfile(co("kajo")), P);
  if (tiny.n < L.K_MIN) assert.strictEqual(tiny.text, `fewer than ${L.K_MIN}`);
});
t("pair facts carry sources and contain no score", () => {
  const f = L.pairFacts(L.companyProfile(co("puro"), { finnish: "helpful" }), P.find(c => c.id === "C-027"));
  for (const k of ["overlap", "gap", "check", "style"]) for (const x of f[k]) { assert.ok(x.src.length > 0, "fact without source: " + x.text); assert.ok(!/score|%|rank/i.test(x.text), "score-like text: " + x.text); }
});
t("a missing portfolio or nice-to-have is never a gap", () => {
  const c = P.find(x => !x.evidence), f = L.pairFacts(L.companyProfile(co("tammi")), c);
  assert.ok(!f.gap.some(g => /portfolio|work sample|nice-to-have/i.test(g.text)));
});
t("recommendations rank stands, not people; an unconfirmed Finnish line never excludes, a confirmed one does", () => {
  const me = P.find(c => c.id === "C-027"); // basic Finnish
  const rec = edits => L.recommend(me, D.companies.map(c => L.companyProfile(c, c.id === "puro" ? edits : undefined))).rec.map(o => o.p.company.id);
  const draft = rec(undefined);                       // ad says "fluent Finnish required", company has not confirmed
  const confirmedReq = rec({ finnish: "required", confirmedAt: "2026-11-14T10:00:00Z" });
  const helpful = rec({ finnish: "helpful", confirmedAt: "2026-11-14T10:00:00Z" });
  assert.ok(draft.includes("puro") && !confirmedReq.includes("puro") && helpful[0] === "puro");
  // the company's own live count applies its draft as written, so it sees what the requirement costs
  const n = p => L.poolCount(p, P).n;
  const puro = D.companies.find(c => c.id === "puro");
  assert.ok(n(L.companyProfile(puro)) < n(L.companyProfile(puro, { finnish: "helpful" })));
  // the organiser filter does not apply an unconfirmed Finnish line
  assert.ok(L.meetsMust(L.companyProfile(puro), me) && !L.meetsMust(L.companyProfile(puro), me, true));
  // one schedule for both sides
  assert.strictEqual(L.slotFor("puro", "C-027"), L.slotFor("puro", "C-027"));
});
console.log(`${n} tests passed`);
