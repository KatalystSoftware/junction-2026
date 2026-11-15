// Core logic. Principle: the software gathers, translates and lays out information; it never scores, ranks or labels people.
// Everything here is deterministic and explainable: every fact carries the source answer or ad sentence it came from.
(function (root) {
  const D = root.DATA;
  const SKILL = Object.fromEntries(D.skills.map(s => [s.id, s]));
  const K_MIN = 5; // aggregates below this are shown as "fewer than 5" so nobody can be singled out

  // ---------------------------------------------------------------- job ad -> draft profile (rule-based, every field keeps its source line)
  const ALIAS = {
    python: /\bpython\b/i, java: /\bjava\b(?!script)/i, kotlin: /\bkotlin\b/i, javascript: /\bjavascript\b/i, typescript: /\btypescript\b/i,
    csharp: /\bc#/i, cpp: /c\+\+|\bC programming\b/i, go: /\bgo\b(?= or | programming|lang)/i, rust: /\brust\b/i, sql: /\bsql\b/i, react: /\breact\b(?! native)/i,
    uiux: /\bux\b|\bui design\b|user experience/i, figma: /\bfigma\b/i, userresearch: /user research/i, aws: /\baws\b|amazon web/i, azure: /\bazure\b/i,
    docker: /\bdocker\b|\bcontainers?\b/i, kubernetes: /\bkubernetes\b|\bk8s\b/i, cicd: /ci\/cd|continuous integration/i, linux: /\blinux\b/i,
    terraform: /terraform|infrastructure as code/i, ml: /machine learning|data science/i, dataeng: /data pipelines?|\betl\b/i,
    analytics: /power bi|business intelligence|data analysis|\bbi\b|tableau|dashboards?/i, statistics: /statistic/i, llm: /\bllms?\b|generative ai/i,
    testauto: /test automation/i, manualtest: /manual testing/i, embedded: /\bembedded\b/i, electronics: /electronics/i, robotics: /robotics|\bros\b/i,
    security: /cybersecurity|security mindset|information security/i, networks: /\bnetwork(ing)? (knowledge|skills)|\bnetworking\b/i,
    iam: /identity (&|and) access/i, agile: /\bagile\b|\bscrum\b/i, projectmgmt: /project management/i, productmgmt: /product management/i,
    itsupport: /it support|service desk/i, sap: /\bsap\b|\berp\b/i, salesforce: /\bcrm\b|salesforce|hubspot/i, mobile: /mobile apps?|ios|android|react native/i,
    gamedev: /\bunity\b|game development|unreal/i, telecom: /telecom|\b5g\b/i, gis: /\bgis\b|map data/i, health: /health data regulation|\bmdr\b/i,
  };
  const ROLE_RULES = [[/devops|infrastructure/i, "devops"], [/machine learning|\bml\b|data scien/i, "ml"], [/data analyst|\bbi\b|power bi/i, "data"],
    [/embedded|firmware/i, "embedded"], [/\bsoc\b|security/i, "security"], [/\berp\b|\bsap\b/i, "erp"], [/test/i, "qa"], [/game/i, "game"],
    [/mobile/i, "mobile"], [/full-stack|front-end|frontend|web/i, "frontend"], [/designer|ux/i, "design"], [/product|project manager/i, "product"],
    [/support/i, "support"], [/back-end|backend|developer|engineer/i, "backend"]];

  function extract(ad) {
    const lines = ad.split(/\n/).map(l => l.trim()).filter(Boolean);
    const p = { title: lines[0] || "", role: null, exp: null, must: [], nice: [], finnish: "unstated", english: false, modes: [], types: [], intl: "unstated", start: null, src: {} };
    const src = (k, i) => { (p.src[k] = p.src[k] || []).includes(i) || p.src[k].push(i); };
    for (const [re, r] of ROLE_RULES) if (re.test(p.title)) { p.role = r; src("role", 0); break; }
    let sec = null;
    lines.forEach((l, i) => {
      if (/^(you have|requirements|we expect|what you bring)/i.test(l)) { sec = "must"; return; }
      if (/^(nice to have|bonus|it'?s a plus)/i.test(l)) { sec = "nice"; return; }
      if (!l.startsWith("-")) sec = null;
      const skills = Object.keys(ALIAS).filter(k => ALIAS[k].test(l) && !(k === "security" && /clearance/i.test(l)));
      if (sec && skills.length && !/finnish|english|swedish/i.test(l)) {
        skills.forEach(k => src("skill:" + k, i));
        const fresh = skills.filter(k => !p.must.flat().includes(k) && !p.nice.includes(k));
        if (sec === "must" && fresh.length) { /\bor\b/i.test(l) && fresh.length > 1 ? p.must.push(fresh) : fresh.forEach(k => p.must.push([k])); }
        if (sec === "nice") fresh.forEach(k => p.nice.push(k));
      }
      const y = l.match(/(\d+)\+?\s*years?/i);
      if (y && sec === "must" && p.exp === null) { const n = +y[1]; p.exp = n >= 6 ? 3 : n >= 3 ? 2 : n >= 1 ? 1 : 0; src("exp", i); }
      if (/junior|trainee|traineeship|internship|from studies/i.test(l) && p.exp === null) { p.exp = 0; src("exp", i); }
      if (/(fluent|native) finnish|finnish (language|skills|is|required|and english)|^-?\s*finnish\b/i.test(l)) {
        p.finnish = /not required|helpful|advantage|plus|nice/i.test(l) ? "helpful" : /required|must|fluent finnish/i.test(l) ? "required" : "unstated";
        src("finnish", i);
      }
      if (/english/i.test(l)) { p.english = true; src("english", i); }
      for (const [re, m] of [[/remote/i, "remote"], [/hybrid/i, "hybrid"], [/on-site|onsite|at our office/i, "onsite"]]) if (re.test(l)) { p.modes.includes(m) || p.modes.push(m); src("modes", i); }
      for (const [re, t] of [[/full-time/i, "full"], [/part-time/i, "part"], [/trainee|traineeship|internship/i, "trainee"], [/contract|freelance/i, "contract"]]) if (re.test(l)) { p.types.includes(t) || p.types.push(t); src("types", i); }
      if (/relocation|work permit|residence permit/i.test(l)) { p.intl = "supports"; src("intl", i); }
      else if (/welcome international|international applicants/i.test(l) && p.intl !== "supports") { p.intl = "open"; src("intl", i); }
      if (/as soon as possible|immediately|asap/i.test(l)) { p.start = "now"; src("start", i); }
      else if (/within 3 months/i.test(l)) { p.start = "3m"; src("start", i); }
    });
    if (!p.types.length) p.types = ["full"];
    if (p.exp === null) p.exp = 0;
    p.lines = lines;
    return p;
  }

  // ---------------------------------------------------------------- company profile = draft from the ad + the company's own corrections
  function companyProfile(c, edits) {
    const p = extract(c.ad);
    const corr = Object.assign({}, c.corrections || {}, edits || {});
    for (const k of ["finnish", "intl", "exp", "start", "role"]) if (corr[k] !== undefined) p[k] = corr[k];
    if (corr.international) p.intl = corr.international;
    if (corr.must) p.must = corr.must;
    if (corr.nice) p.nice = corr.nice;
    if (corr.modes) p.modes = corr.modes;
    p.note = corr.note || null;
    p.confirmed = (edits && edits.confirmedAt) ? { at: edits.confirmedAt, by: "You (just now)" } : c.confirmed;
    p.company = c;
    return p;
  }

  // ---------------------------------------------------------------- candidate helpers
  const EXPMIN = ["no minimum", "1+ years", "3+ years", "6+ years"];
  const LV = { none: 0, basic: 1, working: 2, fluent: 3 };
  const LVTXT = { none: "none", basic: "basic", working: "working level", fluent: "fluent / native" };
  const DEPTH = { work: "used at work", project: "used in own projects or studies", learning: "learning it now" };
  const MODE = { onsite: "on-site", hybrid: "hybrid", remote: "remote" };
  const TYPE = { full: "full-time", part: "part-time", trainee: "traineeship", contract: "contract" };
  const START = { now: "as soon as possible", "3m": "within 3 months", later: "later than 3 months" };
  const skillOf = (cand, id) => cand.skills.find(s => s.id === id);
  const usable = s => s && (s.depth === "work" || s.depth === "project");
  // A Finnish requirement filters only once the company has confirmed it; a bare job-ad line is shown as a gap but never excludes anyone.
  // strict=true applies the draft as written (the company's own live count, so it sees what its draft implies).
  const finnishOk = (p, cand, strict) => p.finnish !== "required" || LV[cand.langs.fi] >= 2 || (!strict && !p.confirmed);
  const groupMet = (cand, g) => g.some(id => usable(skillOf(cand, id)));
  const meetsMust = (p, cand, strict) => p.must.every(g => groupMet(cand, g)) && finnishOk(p, cand, strict) && cand.exp >= p.exp;

  // live anonymous count for the employer: aggregates only, never a list, small numbers suppressed
  function poolCount(p, pool) {
    const n = pool.filter(c => meetsMust(p, c, true)).length;
    return { n, text: n < K_MIN ? `fewer than ${K_MIN}` : String(n), suppressed: n < K_MIN };
  }

  const skillLabel = id => SKILL[id] ? SKILL[id].label : id;
  const groupLabel = g => g.map(skillLabel).join(" or ");
  const candSrc = (q, detail) => ({ side: "cand", q, detail });
  const compSrc = (p, key, fallback) => {
    return { side: "comp", q: p.confirmed ? "Confirmed by company" : "Draft from public job ad (unconfirmed)", detail: (p.src[key] || []).length ? p.src[key].map(i => p.lines[i].replace(/^-\s*/, "")).join(" · ") : fallback || "" };
  };
  const describeSkill = s => DEPTH[s.depth] + (s.years ? `, ${s.years} yr` : "") + (s.example ? ` — “${s.example}”` : "");

  // ---------------------------------------------------------------- facts for one possible introduction (no score, ever)
  function pairFacts(p, cand) {
    const F = { overlap: [], gap: [], check: [], style: [] };
    const add = (k, text, src) => F[k].push({ text, src });
    // role
    if (p.role) {
      if (cand.roles.includes(p.role)) add("overlap", `Wants to work in ${D.roles[p.role]}, the field of this role.`, [candSrc("Q1 Field", cand.roles.map(r => D.roles[r]).join("; ")), compSrc(p, "role", p.title)]);
      else add("gap", `Main field is ${D.roles[cand.roles[0]]}; this role is ${D.roles[p.role]}.`, [candSrc("Q1 Field", cand.roles.map(r => D.roles[r]).join("; ")), compSrc(p, "role", p.title)]);
    }
    // experience
    const expSrc = [candSrc("Q1 Experience in that field", D.exp[cand.exp]), compSrc(p, "exp")];
    if (cand.exp >= p.exp) { if (p.exp > 0) add("overlap", `Has ${D.exp[cand.exp].toLowerCase()} of experience; the company asks for ${EXPMIN[p.exp]}.`, expSrc); }
    else add("gap", `States ${D.exp[cand.exp].toLowerCase()} of experience; the company asks for ${EXPMIN[p.exp]}.`, expSrc);
    if (cand.careerChange) add("overlap", `Moving into tech from ${cand.careerChange}: earlier work experience may transfer.`, [candSrc("Q1 Background", `Career changer from ${cand.careerChange}`)]);
    // must-have skills
    for (const g of p.must) {
      const hit = g.map(id => skillOf(cand, id)).find(usable);
      const learning = g.map(id => skillOf(cand, id)).find(s => s && s.depth === "learning");
      const key = "skill:" + g[0];
      if (hit) add("overlap", `Must-have ${groupLabel(g)}: ${skillLabel(hit.id)} ${DEPTH[hit.depth]}${hit.years ? ` (${hit.years} yr)` : ""}.`, [candSrc("Q2 Tools and skills", `${skillLabel(hit.id)}: ${describeSkill(hit)}`), compSrc(p, key)]);
      else {
        const fam = SKILL[g[0]] && SKILL[g[0]].family;
        const rel = cand.skills.filter(s => usable(s) && SKILL[s.id] && SKILL[s.id].family === fam && !g.includes(s.id));
        add("gap", `Must-have ${groupLabel(g)}: ${learning ? "is learning it now" : "not mentioned"}.` + (rel.length ? ` Related skill in the same area: ${rel.map(s => skillLabel(s.id)).join(", ")}.` : ""),
          [candSrc("Q2 Tools and skills", learning ? `${skillLabel(learning.id)}: learning it now` : "Not listed"), compSrc(p, key)]);
      }
    }
    // nice-to-haves: only overlaps are listed; a missing nice-to-have is not a gap
    for (const id of p.nice) { const s = skillOf(cand, id); if (usable(s)) add("overlap", `Nice-to-have ${skillLabel(id)}: ${DEPTH[s.depth]}.`, [candSrc("Q2 Tools and skills", `${skillLabel(id)}: ${describeSkill(s)}`), compSrc(p, "skill:" + id)]); }
    // evidence: only if the candidate chose to share it and approved the summary; no evidence is never shown as a gap
    if (cand.evidence && cand.evidence.status === "approved") add("overlap", `Shared work sample (${skillLabel(cand.evidence.skill)}): ${cand.evidence.summary}`, [candSrc("Q6 Optional work sample", "Summary approved by the candidate. The link itself is shared only after an introduction, since links often contain a name.")]);
    // language
    const fiTxt = LVTXT[cand.langs.fi];
    const langSrc = [candSrc("Q3 Working languages", `English ${LVTXT[cand.langs.en]}; Finnish ${fiTxt}; Swedish ${LVTXT[cand.langs.sv]}`), compSrc(p, "finnish", p.english ? "Working language English" : "Language not stated")];
    if (p.finnish === "required") (LV[cand.langs.fi] >= 2 ? add("overlap", `Finnish is required and the candidate has ${fiTxt} Finnish.`, langSrc) : add("gap", `Finnish is required${p.confirmed ? " (confirmed by the company)" : " (job ad wording, not yet confirmed)"}; the candidate has ${fiTxt === "none" ? "no" : fiTxt} Finnish.`, langSrc));
    else if (p.finnish === "helpful") add("check", `Finnish is helpful, not required. The candidate has ${fiTxt === "none" ? "no" : fiTxt} Finnish; English ${LVTXT[cand.langs.en]}.`, langSrc);
    else if (p.finnish === "no") add("overlap", `The team works in English; the candidate has ${LVTXT[cand.langs.en]} English.`, langSrc);
    else add("check", `The company has not said whether Finnish is needed.`, langSrc);
    // practical
    const modeOk = cand.mode.some(m => p.modes.includes(m)) || !p.modes.length;
    (modeOk ? add("overlap", `Work mode fits: ${p.modes.map(m => MODE[m]).join(" / ")}.`, [candSrc("Q4 Practicalities", cand.mode.map(m => MODE[m]).join(", ")), compSrc(p, "modes")])
      : add("check", `Work mode: candidate wants ${cand.mode.map(m => MODE[m]).join(" / ")}; role is ${p.modes.map(m => MODE[m]).join(" / ")}.`, [candSrc("Q4 Practicalities", cand.mode.map(m => MODE[m]).join(", ")), compSrc(p, "modes")]));
    if (!cand.types.some(t => p.types.includes(t))) add("check", `Contract type: candidate looks for ${cand.types.map(t => TYPE[t]).join(" or ")}; role is ${p.types.map(t => TYPE[t]).join(" or ")}.`, [candSrc("Q4 Practicalities", cand.types.map(t => TYPE[t]).join(", ")), compSrc(p, "types")]);
    if (p.start === "now" && cand.start === "later") add("check", `Start: company wants someone ${START.now}; candidate is available ${START[cand.start]}.`, [candSrc("Q4 Practicalities", START[cand.start]), compSrc(p, "start")]);
    if (cand.permit) {
      if (p.intl === "supports") add("overlap", `Needs work-permit support, which the company says it provides.`, [candSrc("Q4 Practicalities (optional)", "Would need work-permit support"), compSrc(p, "intl")]);
      else add("check", `Would need work-permit support; the company ${p.intl === "open" ? "welcomes international hires but has not said whether it supports permits" : "has not said"}. Espoo's international recruitment advisers can help the company with this; it is not a reason by itself to skip.`, [candSrc("Q4 Practicalities (optional)", "Would need work-permit support"), compSrc(p, "intl", "Not stated in the ad")]);
    }
    // work style: conversation starters, never gaps
    for (const t of D.tradeoffs) {
      const cv = cand.tradeoffs[t.id], pv = p.company.tradeoffs[t.id];
      if (!cv || !pv) continue;
      const lab = v => (v === "a" ? t.a : t.b).toLowerCase();
      add("style", cv === pv ? `Both lean towards ${lab(cv)}.` : `The role leans towards ${lab(pv)}; the candidate prefers ${lab(cv)}. Worth talking about.`, [candSrc("Q5 Trade-offs", `${t.q} → ${cv === "a" ? t.a : t.b}`), { side: "comp", q: "Company answer", detail: `${t.qe} → ${pv === "a" ? t.a : t.b}` }]);
    }
    const mustCovered = p.must.filter(g => groupMet(cand, g)).length;
    return { ...F, mustCovered, mustTotal: p.must.length, asked: cand.wants.includes(p.company.id), finnishOk: finnishOk(p, cand), modeOk };
  }

  // ---------------------------------------------------------------- stand recommendations for a candidate (ranks stands, never people)
  function recommend(cand, profiles) {
    const out = [];
    for (const p of profiles) {
      const f = pairFacts(p, cand);
      const roleFit = p.role && cand.roles.includes(p.role);
      const shared = p.must.flat().concat(p.nice).filter(id => usable(skillOf(cand, id)));
      if (!f.finnishOk || (!roleFit && f.mustCovered === 0)) { out.push({ p, f, shared, rec: false }); continue; }
      const why = [];
      if (shared.length) why.push(`they ask for ${shared.slice(0, 3).map(skillLabel).join(", ")}, which you listed`);
      if (roleFit) why.push(`the role is in ${D.roles[p.role]}`);
      if (p.finnish === "no") why.push("the team works in English");
      if (p.finnish === "helpful") why.push("Finnish is helpful but not required");
      if (cand.permit && p.intl === "supports") why.push("they support work permits");
      const full = f.mustCovered === f.mustTotal, half = f.mustCovered >= Math.ceil(f.mustTotal / 2);
      out.push({ p, f, shared, rec: full || (roleFit && half), maybe: !full && half, why });
    }
    const rec = out.filter(o => o.rec).sort((a, b) => (b.f.mustCovered / (b.f.mustTotal || 1)) - (a.f.mustCovered / (a.f.mustTotal || 1)) || b.shared.length - a.shared.length);
    const recIds = new Set(rec.slice(0, 4).map(o => o.p.company.id));
    const maybe = out.filter(o => o.maybe && !recIds.has(o.p.company.id)).slice(0, 3);
    return { rec: rec.slice(0, 4), maybe, all: out };
  }


  // ---------------------------------------------------------------- applicant sources -> draft facts (consented scan)
  // Every fact keeps the document and line it came from, and the applicant confirms, edits or removes each one before anyone sees it.
  const LANGRE = { en: /\benglish\b/i, fi: /\bfinnish\b|\bsuomi\b/i, sv: /\bswedish\b|\bsvenska\b/i };
  const OTHERLANG = /\b(ukrainian|russian|german|french|spanish|arabic|hindi|chinese|mandarin|estonian|polish|italian|portuguese|turkish|persian|farsi|somali|vietnamese)\b/i;
  const LVL = l => /native|fluent|c1|c2|mother tongue|full professional/i.test(l) ? "fluent" : /working|professional|b1|b2|intermediate|good/i.test(l) ? "working" : /basic|beginner|a1|a2|elementary|learning|evening course/i.test(l) ? "basic" : null;
  const near = (l, re, n) => { const m = re.exec(l); return m ? l.slice(m.index + m[0].length, m.index + m[0].length + n) : ""; };
  function scanSources(src) {
    const facts = [], skipped = [], lines = []; let n = 0; const seen = {};
    const add = (kind, value, from, where, quote, extra, li) => { facts.push(Object.assign({ id: "f" + (++n), kind, value, from, where, quote, li, status: "new" }, extra || {})); return facts[facts.length - 1]; };
    const docs = [["LinkedIn", src.linkedin], ["CV", src.cv], ["Portfolio", src.portfolio]].filter(d => d[1]);
    for (const [from, text] of docs) {
      const doc = text.split(/\n/).map(l => l.trim()).filter(Boolean);
      let section = "Headline";
      doc.forEach((l, i) => {
        const li = lines.length; lines.push({ from, text: l });
        if (i > 0 && l.length < 32 && /^(experience|work experience|skills|languages|education|about|summary|projects)\b/i.test(l)) { section = l.replace(/:$/, ""); return; }
        const where = `${section}, line ${i + 1}`;
        if (/university|polytechnic|school|college|m\.sc|b\.sc|bachelor|master'?s|phd/i.test(l) && !seen.edu) { seen.edu = 1; skipped.push({ what: "school and university names", from, quote: l }); return; }
        if (/\b(born|age \d|nationality|citizen|photo)\b/i.test(l)) { skipped.push({ what: "age, nationality or photo", from, quote: l }); return; }
        if (OTHERLANG.test(l) && LVL(l)) { skipped.push({ what: "languages the companies here do not work in", from, quote: l }); return; }
        if (section === "Headline" && !seen.role) for (const [re, r] of ROLE_RULES) if (re.test(l)) { seen.role = 1; add("role", r, from, where, l, null, li); break; }
        const learningLine = /currently taking|learning|studying|course\b/i.test(l);
        for (const id of Object.keys(ALIAS)) {
          if (!ALIAS[id].test(l) || /finnish|english|swedish/i.test(l)) continue;
          const tail = near(l, ALIAS[id], 34);
          const y = tail.match(/^[^,;.)]*?(\d+)\s*\+?\s*(?:years?|yrs?|vuotta)/i) || (Object.keys(ALIAS).filter(k => ALIAS[k].test(l)).length === 1 ? l.match(/(\d+)\s*\+?\s*(?:years?|yrs?|vuotta)/i) : null);
          const depth = learningLine ? "learning" : /personal|own|hobby|side|university|thesis/i.test(tail) ? "project" : "work";
          const example = /\d/.test(l) && !/^\d{4}/.test(l) && !/years?|yrs?/i.test(l) && l.length > 30 && l.length < 170 ? l.replace(/^[-•*]\s*/, "") : null;
          const prev = facts.find(f => f.kind === "skill" && f.value === id);
          if (prev) { prev.lis.push(li); if (y && !prev.years) { prev.years = +y[1]; prev.yearsFrom = from; } if (example && !prev.example && depth === "work") { prev.example = example; prev.exampleFrom = from; if (prev.from === from) { prev.where = where; prev.quote = l; prev.li = li; } } if (prev.depth !== "work" && depth === "work") prev.depth = "work"; continue; }
          add("skill", id, from, where, l, { depth, years: y ? +y[1] : null, example: depth === "work" ? example : null, lis: [li] }, li);
        }
        for (const [k, re] of Object.entries(LANGRE)) if (re.test(l) && LVL(l) && !seen["lang:" + k] && /language|native|fluent|basic|working|professional|proficien|elementary|a1|a2|b1|b2|c1|c2/i.test(l)) { seen["lang:" + k] = 1; add("lang", k, from, where, l, { level: LVL(l) }, li); }
        const m = l.match(/(20\d\d)\s*[–-]\s*(20\d\d|present|now|today)/i);
        if (m && !seen["range:" + m[1] + m[2].toLowerCase()]) { seen["range:" + m[1] + m[2].toLowerCase()] = 1; const end = /\d/.test(m[2]) ? +m[2] : 2026; seen.years = (seen.years || 0) + Math.max(0, end - +m[1]); seen.yearsSrc = seen.yearsSrc || [from, where, l, li]; (seen.yearLis = seen.yearLis || []).push(li); }
        if (/open to|prefer|looking for|available/i.test(l)) for (const [re, v] of [[/\bremote\b/i, "remote"], [/\bhybrid\b/i, "hybrid"], [/on-site|onsite/i, "onsite"]]) if (re.test(l) && !seen["mode:" + v]) { seen["mode:" + v] = 1; add("mode", v, from, where, l, null, li); }
        if (!seen.start && /available (immediately|now)|start (immediately|asap|now)|notice period/i.test(l)) { seen.start = 1; add("start", /notice/i.test(l) ? "3m" : "now", from, where, l, null, li); }
      });
    }
    if (seen.years) add("exp", seen.years >= 6 ? 3 : seen.years >= 3 ? 2 : seen.years >= 1 ? 1 : 0, seen.yearsSrc[0], "dated positions", `${seen.years} years of dated positions, e.g. ${seen.yearsSrc[2]}`, { lis: seen.yearLis }, seen.yearsSrc[3]);
    for (const r of src.github || []) {
      const l = `${r.name}: ${r.desc} (${r.lang})`; const li = lines.length; lines.push({ from: "GitHub", text: l });
      for (const id of Object.keys(ALIAS).filter(k => ALIAS[k].test(l))) {
        const prev = facts.find(f => f.kind === "skill" && f.value === id);
        if (prev) { prev.lis.push(li); if (!prev.example) { prev.example = r.desc; prev.exampleFrom = "GitHub"; } continue; }
        add("skill", id, "GitHub", `repository ${r.name}`, l, { depth: "project", years: null, example: r.desc, lis: [li] }, li);
      }
    }
    return { facts, skipped, lines };
  }

  // meeting slot for an introduction: deterministic from the pair, so the company and the candidate see the same time
  const SLOTS = ["10:00", "10:20", "10:40", "11:00", "11:20", "13:00", "13:20", "13:40", "14:00", "14:20"];
  const slotFor = (coId, candId) => { let h = 0; for (const ch of coId + "|" + candId) h = (h * 31 + ch.charCodeAt(0)) % 1000003; return SLOTS[h % SLOTS.length]; };

  root.LOGIC = { slotFor, scanSources, extract, companyProfile, pairFacts, poolCount, recommend, meetsMust, finnishOk, skillLabel, groupLabel, SKILL, EXPMIN, LV, LVTXT, DEPTH, MODE, TYPE, START, K_MIN };
})(typeof window !== "undefined" ? window : globalThis);
