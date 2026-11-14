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
t("recommendations rank stands, not people, and confirmed Finnish changes them", () => {
  const me = P.find(c => c.id === "C-027");
  const before = L.recommend(me, D.companies.map(c => L.companyProfile(c))).rec.map(o => o.p.company.id);
  const after = L.recommend(me, D.companies.map(c => L.companyProfile(c, c.id === "puro" ? { finnish: "helpful" } : undefined))).rec.map(o => o.p.company.id);
  assert.ok(!before.includes("puro") && after[0] === "puro");
});
console.log(`${n} tests passed`);
