// Esittely prototype UI. Plain JS, no build step, no backend: all state lives in this browser (localStorage), data is synthetic.
(function () {
  const D = window.DATA, L = window.LOGIC;
  const app = document.getElementById("app");
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const CO = Object.fromEntries(D.companies.map(c => [c.id, c]));
  const BASE = Object.fromEntries(D.candidates.map(c => [c.id, c]));
  const ME = "C-027"; // the demo candidate
  const ORGANISER = "Aino (Espoo organiser)";
  const fmtTime = iso => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  // ---------------------------------------------------------------- state
  const KEY = "esittely-demo-v2";
  let S;
  function seed() {
    // Pre-existing organiser decisions for Lähde Logistics IT, so the fairness check has something to show in the demo.
    const dec = { lahde: {} };
    const asked = D.candidates.filter(c => c.wants.includes("lahde") && c.id !== ME);
    const fi = asked.filter(c => L.LV[c.langs.fi] >= 2).slice(0, 6), nofi = asked.filter(c => L.LV[c.langs.fi] < 2).slice(0, 3);
    const reasons = ["Has run SAP purchasing at work; exactly the ERP side they need.", "Led a system roll-out in logistics; career-changer route they welcomed.", "Project management at work plus SQL; good for their ERP team.",
      "Strong logistics background, learning SAP; they said career changers are welcome.", "ERP experience and available now.", "Project lead experience; they asked for exactly this."];
    fi.forEach((c, i) => dec.lahde[c.id] = { d: "introduce", reason: reasons[i], at: `2026-11-13T1${i}:20:00Z`, by: "Mikko (Espoo organiser)" });
    nofi.forEach(c => dec.lahde[c.id] = { d: "no", reason: "Not this time: no ERP or project-lead experience mentioned yet.", at: "2026-11-13T16:05:00Z", by: "Mikko (Espoo organiser)" });
    const puro = L.companyProfile(CO.puro, { finnish: "helpful" });
    dec.puro = {};
    D.candidates.filter(c => c.id !== ME && c.wants.includes("puro") && L.meetsMust(puro, c)).slice(0, 2).forEach((c, i) =>
      dec.puro[c.id] = { d: "introduce", reason: ["SQL and Power BI at work; they asked for exactly this.", "Dashboards for retail at work; matches their client base."][i], at: `2026-11-13T15:${10 + i}:00Z`, by: "Mikko (Espoo organiser)" });
    return { dec, comp: {}, cand: {}, corr: {}, ev: {}, fb: {}, ui: { show: "asked", f: {}, sort: "reg", open: {}, reveal: {}, step: 0 } };
  }
  try { S = JSON.parse(localStorage.getItem(KEY)) || seed(); } catch (e) { S = seed(); }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { } };
  const cand = id => Object.assign({}, BASE[id], S.cand[id] || {});
  const pool = () => D.candidates.map(c => cand(c.id));
  function prof(id) {
    if (!CO[id]) id = D.companies[0].id;
    const c = CO[id], e = S.comp[id] || {};
    const cc = e.tradeoffs ? Object.assign({}, c, { tradeoffs: Object.assign({}, c.tradeoffs, e.tradeoffs) }) : c;
    return L.companyProfile(cc, e);
  }
  const profiles = () => D.companies.map(c => prof(c.id));
  const decOf = (co, id) => (S.dec[co] || {})[id];
  function toast(t) { const el = document.getElementById("toast"); el.textContent = t; el.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("on"), 2600); }

  // ---------------------------------------------------------------- small render helpers
  const term = id => { const s = L.SKILL[id]; return s ? `<span class="term" title="${esc(s.plain + (s.esco ? " · ESCO: " + s.esco.title : ""))}">${esc(s.label)}</span>` : esc(id); };
  const terms = g => g.map(term).join(" or ");
  const seg = (name, opts, cur, extra = "") => `<div class="seg">${opts.map(([v, t]) => `<button data-act="${name}" data-v="${esc(v)}" class="${String(cur) === String(v) ? "on" : ""}" ${extra}>${t}</button>`).join("")}</div>`;
  const decBadge = d => d ? `<span class="dec ${d.d}">${{ introduce: "Introduce", maybe: "Maybe later", no: "Not this time" }[d.d]}</span>` : "";
  const confirmBadge = p => p.confirmed ? `<span class="badge ok" title="Confirmed ${esc(fmtTime(p.confirmed.at))} by ${esc(p.confirmed.by)}">Confirmed by company</span>` : `<span class="badge warn" title="The company has not responded; this is the draft made from its public job ad">Unconfirmed draft from job ad</span>`;
  const FI = { required: "Required", helpful: "Helpful, not required", no: "Not needed", unstated: "Not stated" };
  const INTL = { supports: "Supports relocation and work permits", open: "Welcomes international hires", unstated: "Not stated" };
  const srcHtml = src => `<div class="src">${src.map(s => `<div><span class="who">${s.side === "cand" ? "Candidate's answer" : "Company"} · ${esc(s.q)}:</span> ${esc(s.detail)}</div>`).join("")}</div>`;

  // ---------------------------------------------------------------- router
  function route() {
    const h = location.hash.replace(/^#\/?/, "").split("/");
    const k = h[0] || "";
    document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.k === ({ org: "org", log: "org", company: "company", cand: "cand", after: "after", concept: "doc", responsible: "doc", demo: "doc", mentors: "doc" }[k])));
    if (k === "org") return viewOrg(CO[h[1]] ? h[1] : "puro");
    if (k === "log") return viewLog();
    if (k === "company") { const id = CO[h[1]] ? h[1] : "puro"; return h[2] === "intros" ? viewIntros(id) : viewCompany(id); }
    if (k === "cand") return h[1] === "stands" ? viewStands() : h[1] === "me" ? viewMe() : h[1] === "evidence" ? viewEvidence() : viewWizard();
    if (k === "after") return viewAfter();
    if (["concept", "responsible", "demo", "mentors"].includes(k)) return viewDoc(k);
    return viewHome();
  }
  window.addEventListener("hashchange", () => { route(); window.scrollTo(0, 0); });
  document.getElementById("reset").onclick = () => { if (confirm("Reset all demo decisions, confirmations and edits?")) { S = seed(); save(); route(); toast("Demo reset"); } };

  // ---------------------------------------------------------------- home
  function viewHome() {
    const ps = profiles(), confirmed = ps.filter(p => p.confirmed).length;
    app.innerHTML = `
    <section class="hero">
      <div>
        <span class="badge blue">City of Espoo · Rethinking Recruitment · Junction 2026 prototype</span>
        <h1 style="margin-top:10px">Fewer, better conversations at Espoo's recruitment events.</h1><p class="sm mut" style="margin:-2px 0 8px"><b>Esittely</b> is Finnish for “introduction”.</p>
        <p class="mut">Esittely is a light layer on top of event registration. Before the event, at their own pace, companies confirm who they want to meet in about a minute and candidates answer a few concrete questions. City organisers then hand-pick introductions, with the technical needs translated into plain language and every overlap and gap linked to its source.</p>
        <p><b>How it differs from matchmaking platforms:</b> they let an algorithm score and rank people; Esittely gives the organiser the domain understanding to make the introduction themselves, with a reason.</p>
      </div>
      <div class="card">
        <h3>${esc(D.event.name)} <span class="mut sm">· ${esc(D.event.date)} · ${esc(D.event.format)}</span></h3>
        <div class="grid2" style="margin-top:8px">
          <div><div style="font-size:30px;font-weight:700">${D.companies.length}</div><div class="sm mut">company stands, ${confirmed} confirmed their needs</div></div>
          <div><div style="font-size:30px;font-weight:700">${D.candidates.length}</div><div class="sm mut">registered candidates (synthetic)</div></div>
        </div>
        <hr><p class="sm mut" style="margin:0">${esc(D.generated)}. Nobody here is real.</p>
      </div>
    </section>
    <div class="roles">
      <a href="#/org"><div class="card"><span class="badge blue">Main screen</span><h2 style="margin-top:8px">Organiser</h2><p class="mut">See each company's needs in plain language, and for each possible introduction the overlaps, gaps and their sources. Choose your own filters, decide, write one line why.</p></div></a>
      <a href="#/company/puro"><div class="card"><span class="badge ok">About one minute</span><h2 style="margin-top:8px">Company</h2><p class="mut">"Tell us who you want to meet and we'll promote your stand to them." Pre-filled from your public job ad; confirm or correct, and see a live anonymous count of attendees who fit.</p></div></a>
      <a href="#/cand"><div class="card"><span class="badge info">About three minutes</span><h2 style="margin-top:8px">Candidate</h2><p class="mut">A short questionnaire with concrete choices, the same dimensions companies answer. Get a short list of stands worth visiting, each with a reason, and see exactly how organisers see you.</p></div></a>
    </div>
    <h2 style="margin-top:26px">The journey</h2>
    <div class="flow">
      <div class="step"><b>1 · 3 weeks before</b><span class="sm mut">Draft made from each company's public job ad; company confirms in a minute.</span></div>
      <div class="step"><b>2 · 2 weeks before</b><span class="sm mut">Candidates answer on their phone, add an optional work sample, ask to meet stands.</span></div>
      <div class="step"><b>3 · 1 week before</b><span class="sm mut">Organisers hand-pick introductions with a reason; companies get a short list.</span></div>
      <div class="step"><b>4 · Event day</b><span class="sm mut">Planned conversations at the stands; nobody is blocked from any stand.</span></div>
      <div class="step"><b>5 · Next day</b><span class="sm mut">One question to both sides: was this conversation relevant?</span></div>
    </div>
    <p class="sm mut" style="margin-top:16px">Read: <a href="#/concept">one-page concept</a> · <a href="#/responsible">responsible-AI note</a> · <a href="#/demo">3-minute demo script</a> · <a href="#/mentors">questions for Espoo mentors</a></p>`;
  }

  // ---------------------------------------------------------------- organiser
  function viewOrg(coId) {
    const p = prof(coId), c = CO[coId], P = pool();
    const ui = S.ui;
    const list = D.companies.map(x => {
      const px = prof(x.id), asked = P.filter(k => k.wants.includes(x.id)).length, intro = Object.values(S.dec[x.id] || {}).filter(d => d.d === "introduce").length;
      return `<a href="#/org/${x.id}" class="${x.id === coId ? "on" : ""}"><div><b>${esc(x.name)}</b> <span class="mut xs">stand ${x.stand}</span></div>
        <div class="l2">${asked} asked to meet · ${intro} introduced</div><div style="margin-top:3px">${px.confirmed ? '<span class="badge ok">Confirmed</span>' : '<span class="badge warn">Unconfirmed draft</span>'}</div></a>`;
    }).join("");
    // candidates shown: organiser-chosen scope, filters and sort (all visible below as "your criteria")
    if (ui.lastCo !== coId) { ui.lastCo = coId; ui.f = {}; ui.more = false; save(); }
    let rows = P.filter(k => ui.show === "all" || k.wants.includes(coId)).map(k => ({ k, f: L.pairFacts(p, k), d: decOf(coId, k.id), all: L.meetsMust(p, k) }));
    const crit = [ui.show === "all" ? "everyone registered" : "candidates who asked to meet this company"];
    if (ui.f.must) { rows = rows.filter(r => r.all); crit.push("meets every stated must-have (skills, experience" + (p.finnish === "required" ? (p.confirmed ? ", Finnish" : "; the ad's Finnish line is not confirmed, so it is shown as a gap, not applied") : "") + ")"); }
    if (ui.f.mode) { rows = rows.filter(r => r.f.modeOk); crit.push("work mode fits"); }
    if (ui.f.undecided) { rows = rows.filter(r => !r.d); crit.push("not decided yet"); }
    if (ui.sort === "asked") { rows.sort((a, b) => (b.f.asked - a.f.asked) || a.k.registered.localeCompare(b.k.registered)); crit.push("sorted: asked to meet first, then registration time"); }
    else { rows.sort((a, b) => a.k.registered.localeCompare(b.k.registered)); crit.push("sorted by registration time"); }
    const shown = rows.slice(0, ui.more ? 400 : 25);

    app.innerHTML = `<div class="org">
      <aside class="card side"><div class="sm mut" style="padding:4px 10px 8px">${esc(D.event.name)} · ${esc(D.event.date)}</div>${list}
        <hr><a href="#/log">Decision log (${Object.values(S.dec).reduce((n, o) => n + Object.keys(o).length, 0)})</a></aside>
      <section>
        <div class="card">
          <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:wrap">
            <div><h1>${esc(c.name)} <span class="mut" style="font-weight:400;font-size:16px">· stand ${c.stand}</span></h1>
              <div class="mut">${esc(p.title)} · ${esc(c.sector)} · ${esc(c.size)}</div></div>
            <div style="text-align:right">${confirmBadge(p)}${p.confirmed ? "" : `<div style="margin-top:6px"><button class="ghost sm" data-act="remind" data-co="${coId}">Send the 1-minute check again</button></div>`}</div>
          </div>
          ${p.confirmed ? "" : `<div class="warnbox" style="margin-top:10px">This company has not confirmed. Everything below is a <b>draft read from its public job ad</b>; job ads often overstate requirements (e.g. Finnish). Treat it as a starting point.</div>`}
          <h3 style="margin-top:14px">What they need, in plain language</h3>
          <div class="needs">
            ${p.must.map(g => `<div class="need"><div class="k">Must-have</div><b>${terms(g)}</b><div class="sm mut">${g.map(id => esc(L.SKILL[id]?.plain || "")).join(" Or: ")}</div>${g.map(id => L.SKILL[id]?.esco ? `<div class="xs"><a href="${esc(L.SKILL[id].esco.uri)}" target="_blank" rel="noopener">ESCO: ${esc(L.SKILL[id].esco.title)}</a></div>` : "").join("")}</div>`).join("")}
            <div class="need"><div class="k">Nice to have</div>${p.nice.map(id => `<div>${term(id)} <span class="sm mut">— ${esc(L.SKILL[id]?.plain || "")}</span></div>`).join("") || '<span class="mut">None stated</span>'}</div>
            <div class="need"><div class="k">Experience</div><b>${esc(L.EXPMIN[p.exp])}</b><div class="sm mut">in ${esc(D.roles[p.role] || "this field")}</div></div>
            <div class="need"><div class="k">Language</div><b>Finnish: ${esc(FI[p.finnish])}</b>${p.note ? `<div class="sm">“${esc(p.note)}”</div>` : ""}<div class="sm mut">${p.finnish === "no" ? "Team works in English" : p.english ? "English is also a working language" : ""}</div></div>
            <div class="need"><div class="k">Practicalities</div><div class="sm">${p.modes.map(m => L.MODE[m]).join(" / ")} · ${p.types.map(t => L.TYPE[t]).join(", ")} · start ${esc(L.START[p.start] || "not stated")}</div><div class="sm">International hires: ${esc(INTL[p.intl].toLowerCase())}</div></div>
          </div>
        </div>
        ${fairness(coId, p, P)}
        <div class="controls">
          <label>Show ${seg("show", [["asked", "Asked to meet them"], ["all", "Everyone registered"]], ui.show)}</label>
          <label title="The same definition as the company's live count: every must-have skill used at work or in projects, the minimum experience${p.finnish === "required" ? ", and working Finnish" : ""}"><input type="checkbox" data-act="filt" data-v="must" ${ui.f.must ? "checked" : ""}> Meets every stated must-have</label>
          <label><input type="checkbox" data-act="filt" data-v="mode" ${ui.f.mode ? "checked" : ""}> Work mode fits</label>
          <label><input type="checkbox" data-act="filt" data-v="undecided" ${ui.f.undecided ? "checked" : ""}> Not decided yet</label>
          <label>Sort <select data-act="sort"><option value="reg" ${ui.sort === "reg" ? "selected" : ""}>Registration time</option><option value="asked" ${ui.sort === "asked" ? "selected" : ""}>Asked to meet first</option></select></label>
        </div>
        <p class="crit"><b>${rows.length}</b> shown · your criteria: ${crit.map(esc).join(" · ")}. The order is only the sort you chose; nothing is scored. Names are hidden until you decide, to keep attention on what people can do.</p>
        ${shown.map(r => candRow(coId, p, r)).join("")}
        ${rows.length > shown.length ? `<button class="ghost" data-act="more">Show all ${rows.length}</button>` : ""}
      </section></div>`;
  }

  function candRow(coId, p, { k, f, d }) {
    const open = S.ui.open[coId + k.id];
    const corr = (S.corr[k.id] || []).length;
    const name = S.ui.reveal[k.id] ? `${esc(k.name)}` : `<span class="mut">name hidden</span>`;
    const head = `<div class="head" data-act="toggle" data-id="${k.id}" data-co="${coId}">
      <div><div class="pid">${k.id}</div><div class="xs">${name}</div></div>
      <div class="sm">${esc(D.roles[k.roles[0]])} · ${esc(D.exp[k.exp])}<br>
        <span class="mut">${p.must.map(g => { const hit = g.find(id => { const s = k.skills.find(x => x.id === id); return s && s.depth !== "learning"; }); return `${hit ? "✓" : "○"} ${esc(L.skillLabel(hit || g[0]))}`; }).join(" · ")}${p.finnish === "required" ? ` · Finnish ${esc(L.LVTXT[k.langs.fi])}` : ""}</span>
        ${f.asked ? ' <span class="badge blue">asked to meet</span>' : ""} ${corr ? ' <span class="badge" style="background:var(--violet2);color:var(--violet)">corrected by candidate</span>' : ""}</div>
      <div style="text-align:right">${decBadge(d)} <span class="mut">${open ? "▲" : "▼"}</span></div></div>`;
    if (!open) return `<div class="cand">${head}</div>`;
    const col = (key, title, icon, empty) => `<div class="fcol"><h4>${icon} ${title} <span class="mut">(${f[key].length})</span></h4>${f[key].map((x, i) => {
      const sid = `${coId}|${k.id}|${key}|${i}`; const so = S.ui.open["src" + sid];
      return `<div class="fact ${key}">${esc(x.text)} <button class="srcbtn" data-act="src" data-id="${esc(sid)}">${so ? "hide source" : "source"}</button>${so ? srcHtml(x.src) : ""}</div>`;
    }).join("") || `<div class="sm mut">${empty}</div>`}</div>`;
    return `<div class="cand">${head}
      <div class="facts">${col("overlap", "Overlaps", "✓", "None found")}${col("gap", "Gaps", "○", "No gaps against the must-haves")}${col("check", "Practical checks", "?", "Nothing to check")}${col("style", "Conversation starters", "☺", "—")}</div>
      <div class="sm mut" style="padding:0 14px 10px">Written from the candidate's own answers${k.evidence ? " and a work-sample summary they approved" : ""}; they can see and correct this text. ${k.evidence ? "" : "Not sharing a work sample is normal and is never shown as a gap."} ${corr ? `<b>The candidate corrected their description ${corr} time(s).</b>` : ""}</div>
      <div class="decide">
        <b class="sm">Your decision</b>
        ${["introduce", "maybe", "no"].map(v => `<button class="${d && d.d === v ? "" : "quiet"} sm" data-act="pick" data-v="${v}" data-id="${k.id}" data-co="${coId}">${{ introduce: "Introduce", maybe: "Maybe later", no: "Not this time" }[v]}</button>`).join("")}
        <input id="why-${k.id}" placeholder="One line: why? (required, shared with the company if you introduce)" value="${esc(d ? d.reason : "")}" maxlength="160">
        <button class="sm" data-act="decide" data-id="${k.id}" data-co="${coId}">Save</button>
        ${S.ui.reveal[k.id] ? "" : `<button class="ghost sm" data-act="reveal" data-id="${k.id}" ${d ? "" : "disabled title='Decide first'"}>Show name</button>`}
        ${d ? `<span class="xs mut">Saved ${esc(fmtTime(d.at))} by ${esc(d.by)}: “${esc(d.reason)}”</span>` : ""}
      </div></div>`;
  }

  function fairness(coId, p, P) {
    const ds = Object.entries(S.dec[coId] || {}).filter(([, d]) => d.d === "introduce").map(([id]) => cand(id));
    const asked = P.filter(k => k.wants.includes(coId));
    if (ds.length < 3) return `<div class="note" style="margin-top:12px"><b>Fairness check</b> appears after 3 introductions: it compares who you introduce with who asked to meet this company, in aggregate only.</div>`;
    const share = (arr, fn) => arr.length ? Math.round(100 * arr.filter(fn).length / arr.length) : 0;
    const dims = [["Without working Finnish", k => L.LV[k.langs.fi] < 2], ["Career changers", k => !!k.careerChange], ["Need work-permit support", k => !!k.permit]];
    let alert = "";
    const cells = dims.map(([lab, fn]) => {
      const a = share(asked, fn), b = share(ds, fn);
      if (a - b >= 15) alert = alert || `${lab}: ${a}% of those who asked, ${b}% of your introductions so far.` + (lab.includes("Finnish") && p.finnish !== "required" ? (p.finnish === "unstated" ? " The company has not said Finnish is required." : ` The company says Finnish is ${FI[p.finnish].toLowerCase()}.`) : "");
      return `<div><div class="sm"><b>${lab}</b></div><div class="xs mut">asked to meet: ${a}%</div><div class="bar"><i style="width:${a}%"></i></div><div class="xs mut">introduced: ${b}%</div><div class="bar b2"><i style="width:${b}%"></i></div></div>`;
    }).join("");
    return `<div class="card" style="margin-top:12px"><h3>Fairness check <span class="mut sm" style="font-weight:400">· ${ds.length} introductions · aggregates only, to check our own choices</span></h3>
      ${alert ? `<div class="warnbox" style="margin-bottom:10px"><b>Worth a second look:</b> ${esc(alert)} Is the difference explained by the role's real needs?</div>` : ""}<div class="fair">${cells}</div></div>`;
  }

  function viewLog() {
    const rows = [];
    for (const [co, o] of Object.entries(S.dec)) for (const [id, d] of Object.entries(o)) rows.push({ co, id, ...d });
    rows.sort((a, b) => b.at.localeCompare(a.at));
    app.innerHTML = `<div class="card"><div class="row" style="justify-content:space-between;align-items:center"><div><h1>Decision log</h1><p class="mut">Every introduction is a human decision with a reason. This log is what an auditor, the company or the candidate can ask to see.</p></div>
      <div><button class="ghost" data-act="csv">Download CSV</button> <a href="#/org"><button class="quiet">Back</button></a></div></div>
      <div style="overflow-x:auto"><table><tr><th>When</th><th>Company</th><th>Candidate</th><th>Decision</th><th>Reason</th><th>Who</th></tr>
      ${rows.map(r => `<tr><td class="sm">${esc(fmtTime(r.at))}</td><td>${esc(CO[r.co].name)}</td><td>${r.id}</td><td>${decBadge(r)}</td><td>${esc(r.reason)}</td><td class="sm">${esc(r.by)}</td></tr>`).join("")}</table></div></div>`;
  }

  // ---------------------------------------------------------------- company: one-minute confirmation
  let timerStart = 0, timerInt = null;
  function viewCompany(coId) {
    const c = CO[coId]; if (!c) return viewHome();
    const e = S.comp[coId] || (S.comp[coId] = {});
    const p = prof(coId), P = pool(), cnt = L.poolCount(p, P);
    const asked = P.filter(k => k.wants.includes(coId)).length;
    const what = patch => L.poolCount(L.companyProfile(Object.assign({}, c), Object.assign({}, e, patch)), P).text;
    if (!timerStart || S.ui.timerCo !== coId) { timerStart = Date.now(); S.ui.timerCo = coId; }
    const used = new Set(Object.values(p.src).flat());
    const srcAttr = key => `data-src="${(p.src[key] || []).join(",")}"`;
    const fiNow = (L.extract(c.ad).finnish);
    const fiLine = (p.src.finnish || []).map(i => p.lines[i].replace(/^-\s*/, "")).join(" ");
    app.innerHTML = `
    <div class="row" style="justify-content:space-between;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px">
      <div><span class="badge ok">For ${esc(c.name)} · about one minute</span>
        <h1 style="margin-top:8px">Tell us who you want to meet, and we'll promote your stand to them.</h1>
        <p class="mut" style="margin:0">We drafted this from your public job ad “${esc(p.title)}”. Check and correct it. If you don't have time, we use the draft and show it as unconfirmed.</p></div>
      <div class="sm mut">Company: <select data-act="pickco">${D.companies.map(x => `<option value="${x.id}" ${x.id === coId ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
    </div>
    <div class="livecount"><div class="n" id="cnt">${esc(cnt.text)}</div><div class="t"><b>registered attendees meet your stated must-haves</b><br>Live count from this event's registrations. Aggregate only: you never see a list or a person here${cnt.suppressed ? ", and numbers under 5 are not shown exactly" : ""}. ${asked} attendees have already asked to visit your stand.</div>
      <div style="margin-left:auto;text-align:right"><div class="timer" id="timer">0:00</div><div class="xs" style="color:#aab6cf">${e.confirmedAt ? "confirmed" : "time spent"}</div></div></div>
    <div class="cmp" style="margin-top:14px">
      <div class="card"><h3>Your public job ad</h3><p class="xs mut">Highlighted lines were used for the draft. Hover a field on the right to see where it came from.</p>
        <div class="ad">${p.lines.map((l, i) => `<div class="ln ${used.has(i) ? "used" : ""}" data-ln="${i}">${esc(l)}</div>`).join("")}</div>
        <details style="margin-top:14px"><summary class="sm">Try it with another job ad</summary>
          <p class="xs mut">Paste any job ad text. The draft is made by transparent rules in your browser: nothing is sent anywhere.</p>
          <textarea id="adtext" placeholder="Paste a job ad…"></textarea><button class="sm" data-act="tryad" style="margin-top:6px">Make a draft</button><div id="tryout"></div></details>
      </div>
      <div>
        <div class="field" ${srcAttr("finnish")}><div class="lab"><b>Is Finnish truly required for this role?</b><span class="xs mut">${fiLine ? "Your ad says: “" + esc(fiLine) + "”" : "Your ad doesn't say"}</span></div>
          ${seg("fi", [["required", `Required <span class="xs">(${what({ finnish: "required" })})</span>`], ["helpful", `Helpful, not required <span class="xs">(${what({ finnish: "helpful" })})</span>`], ["no", `Not needed <span class="xs">(${what({ finnish: "no" })})</span>`]], p.finnish)}
          <div class="xs mut" style="margin-top:5px">The number in brackets is how many registered attendees would meet your must-haves with each answer. Many strong candidates work in English while learning Finnish.</div></div>
        <div class="field"><div class="lab"><b>Must-haves</b><span class="xs mut">only what you would really reject someone for</span></div>
          ${p.must.map((g, i) => `<span class="chip on" data-src="${(p.src["skill:" + g[0]] || []).join(",")}">${terms(g)} <button data-act="demote" data-i="${i}" title="Move to nice-to-have">→ nice-to-have</button><span class="whatif">${what({ must: p.must.filter((_, j) => j !== i), nice: p.nice.concat(g) })} if moved</span></span>`).join("")}
          <div style="margin-top:6px"><select data-act="addmust"><option value="">+ add a must-have…</option>${D.skills.map(s => `<option value="${s.id}">${esc(s.label)}</option>`).join("")}</select></div></div>
        <div class="field"><div class="lab"><b>Nice to have</b><span class="xs mut">used to promote your stand, never to exclude</span></div>
          ${p.nice.map((id, i) => `<span class="chip" data-src="${(p.src["skill:" + id] || []).join(",")}">${term(id)} <button data-act="promote" data-i="${i}" title="Make it a must-have">↑ must</button><button data-act="dropnice" data-i="${i}" title="Remove">✕</button></span>`).join("") || '<span class="mut sm">None</span>'}</div>
        <div class="field" ${srcAttr("exp")}><div class="lab"><b>Minimum experience in ${esc(D.roles[p.role] || "the field")}</b></div>
          ${seg("exp", L.EXPMIN.map((t, i) => [i, `${t} <span class="xs">(${what({ exp: i })})</span>`]), p.exp)}</div>
        <div class="field" ${srcAttr("intl")}><div class="lab"><b>International hires</b><span class="xs mut">Espoo's international recruitment services can help with permits</span></div>
          ${seg("intl", [["unstated", "Not decided"], ["open", "Welcome, no permit support"], ["supports", "Welcome, we support permits & relocation"]], p.intl)}</div>
        <div class="field" ${srcAttr("modes")}><div class="lab"><b>Work mode and start</b></div>
          <div class="opts">${Object.entries(L.MODE).map(([m, t]) => `<span class="opt ${p.modes.includes(m) ? "on" : ""}" data-act="mode" data-v="${m}">${t}</span>`).join("")}</div>
          <div style="margin-top:8px">${seg("start", [["now", "As soon as possible"], ["3m", "Within 3 months"], ["later", "Later"]], p.start)}</div></div>
        <div class="field"><div class="lab"><b>Your team, in three quick choices</b><span class="xs mut">helps start good conversations; never used to exclude</span></div>
          ${D.tradeoffs.map(t => `<div class="sm" style="margin:6px 0 3px">${esc(t.qe)}</div>${seg("trade", [["a", esc(t.a)], ["b", esc(t.b)]], p.company.tradeoffs[t.id], `data-t="${t.id}"`)}`).join("")}</div>
        ${e.confirmedAt ? `<div class="okbox"><b>Confirmed.</b> Your stand will be promoted to the ${esc(cnt.text)} attendees whose answers fit your must-haves, and to others whose nice-to-haves match. An Espoo organiser will send you a short list of hand-picked introductions a week before the event. <a href="#/company/${coId}/intros">See your introductions →</a></div>`
        : `<button style="width:100%;padding:12px;font-size:16px" data-act="confirm" data-co="${coId}">Confirm and promote my stand</button>
           <p class="xs mut" style="margin-top:6px">${p.confirmed ? "Already confirmed earlier; confirming again updates it." : "No reply = we use the draft above, marked “unconfirmed” for organisers."} You can change this until the event.</p>`}
      </div>
    </div>`;
    clearInterval(timerInt);
    const tick = () => { const t = document.getElementById("timer"); if (!t) return clearInterval(timerInt); const s = e.confirmedAt ? (e.took || 0) : Math.round((Date.now() - timerStart) / 1000); t.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
    tick(); if (!e.confirmedAt) timerInt = setInterval(tick, 1000);
  }

  function viewIntros(coId) {
    const c = CO[coId], p = prof(coId), P = pool();
    const intro = Object.entries(S.dec[coId] || {}).filter(([, d]) => d.d === "introduce");
        app.innerHTML = `<div class="wiz" style="max-width:900px"><a href="#/company/${coId}" class="sm">← back to your needs</a>
      <h1 style="margin-top:8px">${esc(c.name)}: your hand-picked introductions</h1>
      <p class="mut">An Espoo organiser read each attendee's answers against your confirmed needs and chose these conversations. Each comes with the organiser's reason and the candidate's own description, which they have checked. Names are shared at the event, when the candidate agrees.</p>
      <div class="note" style="margin-bottom:12px">Promoted to <b>${esc(L.poolCount(p, P).text)}</b> attendees whose answers fit your must-haves. ${P.filter(k => k.wants.includes(coId)).length} asked to visit your stand. Anyone can still visit; these are the planned conversations.</div>
      ${intro.length ? intro.map(([id, d], i) => { const k = cand(id), f = L.pairFacts(p, k); return `<div class="stand"><div class="top2"><b>${L.slotFor(coId, id)} · ${id}</b><span class="xs mut">introduced by ${esc(d.by)}</span></div>
        <div class="sm" style="margin:4px 0 8px"><b>Organiser's reason:</b> ${esc(d.reason)}</div>
        <div class="sm">${f.overlap.slice(0, 5).map(x => `<div>✓ ${esc(x.text)}</div>`).join("")}${f.gap.slice(0, 3).map(x => `<div class="mut">○ ${esc(x.text)}</div>`).join("")}</div></div>`; }).join("")
        : `<div class="card mut">No introductions yet. They appear here as the organiser decides (try the <a href="#/org/${coId}">organiser view</a>).</div>`}
    </div>`;
  }

  // ---------------------------------------------------------------- candidate questionnaire
  const STEPS = ["Start", "Your field", "Tools and skills", "Languages", "Practicalities", "Trade-offs", "Work sample", ];
  function setMe(patch, field) {
    S.cand[ME] = Object.assign({}, S.cand[ME] || {}, patch); save();
  }
  function motiv(html) { return `<div class="motiv"><span class="ic">💡</span><div>${html}<div class="xs mut" style="margin-top:3px">Computed live from the companies registered for this event.</div></div></div>`; }
  function viewWizard() {
    const me = cand(ME), ps = profiles(), st = S.ui.step || 0;
    const nav = `<div class="row" style="justify-content:space-between;margin-top:18px">${st > 0 ? `<button class="quiet" data-act="step" data-v="${st - 1}">Back</button>` : "<span></span>"}
      ${st < STEPS.length - 1 ? `<button data-act="step" data-v="${st + 1}">${st === 0 ? "Start" : "Next"}</button>` : `<a href="#/cand/stands"><button>See stands worth visiting</button></a>`}</div>`;
    let body = "";
    if (st === 0) body = `<h1>Meet the right companies at ${esc(D.event.name)}</h1>
      <p>Six short steps, about three minutes. We use them to tell you which stands are worth visiting and why, and to help Espoo's organisers introduce you to companies that need what you do.</p>
      <div class="note stack"><div><b>Only what you tell us.</b> We never search for you online and never use photos, age, gender, nationality or school names.</div>
      <div><b>You see what organisers see.</b> You can correct your description at any time.</div><div><b>No scores.</b> No computer decides about you; an organiser does, and writes down why.</div>
      <div><b>Deleted after the event</b> (30 days, unless you ask to stay for the next one).</div></div>
      <p class="xs mut" style="margin-top:10px">Demo: answers are pre-filled for the synthetic candidate Olena K. (${ME}). Change anything.</p>`;
    if (st === 1) {
      const n = ps.filter(p => me.roles.includes(p.role)).length;
      body = `<h2>Which field do you want to work in? <span class="mut sm">pick up to 2</span></h2>
      <div class="opts">${Object.entries(D.roles).map(([r, t]) => `<span class="opt ${me.roles.includes(r) ? "on" : ""}" data-act="role" data-v="${r}">${esc(t)}</span>`).join("")}</div>
      <h3 style="margin-top:16px">How much experience do you have in it? <span class="mut sm">work, traineeships and serious projects count</span></h3>${seg("cexp", D.exp.map((t, i) => [i, esc(t)]), me.exp)}
      <h3 style="margin-top:16px">Are you moving into tech from another field? <span class="mut sm">optional; earlier experience often transfers</span></h3>
      <select data-act="career"><option value="">No / prefer not to say</option>${["logistics", "retail", "teaching", "hospitality", "nursing", "accounting", "journalism", "manufacturing", "customer service", "the army", "other"].map(x => `<option ${me.careerChange === x ? "selected" : ""}>${x}</option>`).join("")}</select>
      ${motiv(`<b>${n} of ${ps.length} stands</b> at this event hire in ${me.roles.map(r => esc(D.roles[r])).join(" or ") || "your field"}.`)}`;
    }
    if (st === 2) {
      const mine = me.skills.map(s => s.id);
      const want = ps.map(p => ({ p, hits: p.must.flat().concat(p.nice).filter(id => mine.includes(id)) })).filter(x => x.hits.length);
      const fams = new Set(me.roles.flatMap(r => ({ data: ["data"], ml: ["data"], backend: ["programming", "cloud"], frontend: ["frontend", "programming", "design"], devops: ["cloud"], qa: ["quality"], embedded: ["embedded"], design: ["design"], product: ["process"], security: ["security"], support: ["support"], erp: ["business"], game: ["frontend"], mobile: ["frontend"] }[r] || [])));
      const sugg = D.skills.filter(s => fams.has(s.family) && !mine.includes(s.id));
      body = `<h2>Which tools and skills have you really used? <span class="mut sm">be concrete; depth matters more than a long list</span></h2>
      ${me.skills.map((s, i) => `<div class="skillrow"><div><b>${term(s.id)}</b> <button class="ghost sm" data-act="rmskill" data-i="${i}" title="Remove">✕</button><div class="xs mut">${esc(L.SKILL[s.id]?.plain || "")}</div></div>
        <div>${seg("depth", [["work", "Used at work"], ["project", "Own projects / studies"], ["learning", "Learning now"]], s.depth, `data-i="${i}"`)}
        ${s.depth === "work" ? ` <select data-act="years" data-i="${i}">${[1, 2, 3, 4, 5, 7, 10].map(y => `<option value="${y}" ${s.years === y ? "selected" : ""}>${y}${y === 10 ? "+" : ""} yr</option>`).join("")}</select>` : ""}
        ${s.depth !== "learning" ? `<input data-act="example" data-i="${i}" maxlength="120" style="width:100%;margin-top:5px" placeholder="Optional: one concrete thing you did with it" value="${esc(s.example || "")}">` : ""}</div></div>`).join("")}
      <div style="margin-top:10px" class="sm">Add: ${sugg.slice(0, 10).map(s => `<span class="chip" data-act="addskill" data-v="${s.id}" style="cursor:pointer">+ ${esc(s.label)}</span>`).join("")}
        <select data-act="addskillsel"><option value="">other…</option>${D.skills.filter(s => !mine.includes(s.id)).map(s => `<option value="${s.id}">${esc(s.label)}</option>`).join("")}</select></div>
      ${motiv(want.length ? `Your tools appear in the needs of <b>${want.length} stands</b>: ${want.slice(0, 4).map(x => `${esc(x.p.company.name)} (${x.hits.map(L.skillLabel).join(", ")})`).join("; ")}${want.length > 4 ? "…" : ""}.` : "Add the tools you have used to see which stands ask for them.")}`;
    }
    if (st === 3) {
      const fiFree = ps.filter(p => p.finnish !== "required").length;
      const fiOk = ps.filter(p => L.finnishOk(p, me)).length;
      const lv = (k, t) => `<div class="skillrow"><b>${t}</b>${seg("lang", [["none", "None"], ["basic", "Basic"], ["working", "Working level"], ["fluent", "Fluent / native"]], me.langs[k], `data-k="${k}"`)}</div>`;
      body = `<h2>Which languages can you work in?</h2>${lv("en", "English")}${lv("fi", "Finnish")}${lv("sv", "Swedish")}
      <p class="xs mut" style="margin-top:8px">We only ask about the languages companies here work in. Other languages you speak are not collected.</p>
      ${motiv(`<b>${fiFree} of ${ps.length} stands</b> say Finnish is helpful or not needed; with your answers you meet the language needs of <b>${fiOk}</b>.`)}`;
    }
    if (st === 4) {
      const fits = ps.filter(p => me.mode.some(m => p.modes.includes(m)) && me.types.some(t => p.types.includes(t))).length;
      body = `<h2>Practicalities</h2>
      <h3>Work mode</h3><div class="opts">${Object.entries(L.MODE).map(([m, t]) => `<span class="opt ${me.mode.includes(m) ? "on" : ""}" data-act="cmode" data-v="${m}">${t}</span>`).join("")}</div>
      <h3 style="margin-top:14px">Contract</h3><div class="opts">${Object.entries(L.TYPE).map(([m, t]) => `<span class="opt ${me.types.includes(m) ? "on" : ""}" data-act="ctype" data-v="${m}">${t}</span>`).join("")}</div>
      <h3 style="margin-top:14px">When could you start?</h3>${seg("cstart", Object.entries(L.START), me.start)}
      <h3 style="margin-top:14px">Would you need help with a work permit? <span class="mut sm">optional</span></h3>
      <label class="sm"><input type="checkbox" data-act="permit" ${me.permit ? "checked" : ""}> Yes. Used only to point you to companies that offer support, and to let Espoo's international recruitment advisers help the company.</label>
      ${motiv(`Work mode and contract fit <b>${fits} of ${ps.length} stands</b>.`)}`;
    }
    if (st === 5) body = `<h2>Three quick choices</h2><p class="mut sm">No right answers. They help you and the company start a good conversation, and are never used to exclude anyone.</p>
      ${D.tradeoffs.map(t => `<h3 style="margin-top:12px">${esc(t.q)}</h3><div class="trade"><span class="opt ${me.tradeoffs[t.id] === "a" ? "on" : ""}" data-act="ctrade" data-t="${t.id}" data-v="a">${esc(t.a)}</span><span class="mut">or</span><span class="opt ${me.tradeoffs[t.id] === "b" ? "on" : ""}" data-act="ctrade" data-t="${t.id}" data-v="b">${esc(t.b)}</span></div>`).join("")}`;
    if (st === 6) body = `<h2>A work sample <span class="mut sm">optional</span></h2>
      <p>If you have something public that shows your work (a project, a report, a design case), you can share a link. We summarise what it demonstrates; <b>you approve the summary before anyone sees it</b>.</p>
      <div class="note">Not having a public portfolio is normal (much good work is confidential) and is <b>never</b> shown as a gap. You can instead describe one thing you built in three short answers.</div>
      <div class="stand" style="margin-top:12px">${me.evidence ? `<b>Shared:</b> <span class="sm">${esc(me.evidence.summary)}</span> <span class="badge ${me.evidence.status === "approved" ? "ok" : "warn"}">${me.evidence.status === "approved" ? "approved by you" : "waiting for your approval"}</span>` : '<span class="mut">Nothing shared.</span>'}
      <div style="margin-top:8px"><a href="#/cand/evidence"><button class="ghost sm">${me.evidence ? "Review or change" : "Share a link or describe your work"}</button></a></div></div>`;
    app.innerHTML = `<div class="wiz"><div class="prog">${STEPS.map((_, i) => `<i class="${i <= st ? "on" : ""}"></i>`).join("")}</div>
      <div class="card">${body}${nav}</div>
      <p class="xs mut" style="text-align:center;margin-top:10px">Step ${st + 1} of ${STEPS.length} · <a href="#/cand/me">How organisers see you</a> · <a href="#/cand/stands">Stands for you</a></p></div>`;
  }

  function viewStands() {
    const me = cand(ME), r = L.recommend(me, profiles());
    const recIds = new Set(r.rec.map(o => o.p.company.id));
    const ask = id => `<button class="${me.wants.includes(id) ? "" : "ghost"} sm" data-act="want" data-v="${id}">${me.wants.includes(id) ? "✓ Introduction requested" : "Ask for an introduction"}</button>`;
    const mine = Object.entries(S.dec).filter(([, o]) => o[ME] && o[ME].d === "introduce").map(([co, o], i) => ({ co, d: o[ME], slot: L.slotFor(co, ME) }));
    app.innerHTML = `<div class="wiz">${mine.length ? `<div class="okbox" style="margin-bottom:14px"><b>Your planned conversations</b>${mine.map(m => `<div class="sm" style="margin-top:4px">${m.slot} · <b>${esc(CO[m.co].name)}</b>, stand ${CO[m.co].stand}. The organiser's note: “${esc(m.d.reason)}”</div>`).join("")}</div>` : `<div class="note" style="margin-bottom:14px">When an organiser plans a conversation for you, it appears here with a time and the reason.</div>`}<h1>Stands worth visiting</h1>
      <p class="mut">Based only on your answers and what each company told us. These are suggestions: <b>you can visit any stand</b>, and you can ask the organiser to introduce you to any company.</p>
      ${r.rec.length ? r.rec.map(o => `<div class="stand"><div class="top2"><div><b>${esc(o.p.company.name)}</b> <span class="mut sm">· stand ${o.p.company.stand} · ${esc(o.p.title)}</span></div>${confirmBadge(o.p)}</div>
        <p class="sm" style="margin:6px 0">Why: ${esc(o.why.join("; "))}.</p>
        ${o.f.gap.length ? `<p class="xs mut" style="margin:0 0 6px">Good to know: ${o.f.gap.slice(0, 2).map(g => esc(g.text)).join(" ")}</p>` : ""}${ask(o.p.company.id)}</div>`).join("")
        : `<div class="card mut">No stand matches your answers closely; browse them all below.</div>`}
      ${r.maybe.length ? `<h2 style="margin-top:22px">Also worth a look</h2><p class="sm mut">You cover some of what they need; the stand can tell you whether the rest can be learned on the job.</p>` + r.maybe.map(o => `<div class="stand"><div class="top2"><div><b>${esc(o.p.company.name)}</b> <span class="mut sm">· stand ${o.p.company.stand} · ${esc(o.p.title)}</span></div>${ask(o.p.company.id)}</div>
        <p class="sm" style="margin:6px 0 0">Why: ${esc(o.why.join("; "))}.</p><p class="xs mut" style="margin:4px 0 0">Good to know: ${o.f.gap.slice(0, 2).map(g => esc(g.text)).join(" ")}</p></div>`).join("") : ""}
      <h2 style="margin-top:22px">All other stands</h2>
      ${r.all.filter(o => !recIds.has(o.p.company.id) && !r.maybe.some(m => m.p.company.id === o.p.company.id)).map(o => `<div class="stand"><div class="top2"><div><b>${esc(o.p.company.name)}</b> <span class="mut sm">· ${esc(o.p.title)}</span></div>${ask(o.p.company.id)}</div>
        <p class="xs mut" style="margin:4px 0 0">They look for ${o.p.must.map(L.groupLabel).join(", ")}. ${!o.f.finnishOk ? `They say Finnish is required${o.p.confirmed ? "" : " (not yet confirmed by them)"}.` : ""}</p></div>`).join("")}
      <p class="sm" style="margin-top:16px"><a href="#/cand/me">See and correct how organisers see you →</a></p></div>`;
  }

  function viewMe() {
    const me = cand(ME), corr = S.corr[ME] || []; S.ui.correcting = null; save();
    const line = (q, a, act) => `<div class="line"><div><div class="q">${q}</div><div>${a}</div></div><div>${act || ""}</div></div>`;
    app.innerHTML = `<div class="wiz me"><h1>How organisers see you</h1>
      <p class="mut">This is exactly the information Espoo's organisers use to suggest introductions. It comes only from your answers. If anything is wrong or unfair, correct it: corrections are logged and organisers see that you checked.</p>
      <div class="card">
        ${line("Field", me.roles.map(r => esc(D.roles[r])).join("; "), `<button class="ghost sm" data-act="goto" data-v="1">Correct</button>`)}
        ${line("Experience in that field", esc(D.exp[me.exp]) + (me.careerChange ? ` · moving into tech from ${esc(me.careerChange)}` : ""), `<button class="ghost sm" data-act="goto" data-v="1">Correct</button>`)}
        ${me.skills.map((s, i) => line(`Skill: ${term(s.id)}`, esc(L.DEPTH[s.depth] + (s.years ? `, ${s.years} yr` : "")) + (s.example ? `<div class="sm mut">“${esc(s.example)}”</div>` : ""),
          `<select data-act="medepth" data-i="${i}">${Object.entries(L.DEPTH).map(([v, t]) => `<option value="${v}" ${s.depth === v ? "selected" : ""}>${t}</option>`).join("")}<option value="remove">remove this skill</option></select>`)).join("")}
        ${line("Working languages", `English ${esc(L.LVTXT[me.langs.en])} · Finnish ${esc(L.LVTXT[me.langs.fi])} · Swedish ${esc(L.LVTXT[me.langs.sv])}`, `<button class="ghost sm" data-act="goto" data-v="3">Correct</button>`)}
        ${line("Practicalities", `${me.mode.map(m => L.MODE[m]).join(" / ")} · ${me.types.map(t => L.TYPE[t]).join(", ")} · start ${esc(L.START[me.start])}${me.permit ? " · would need work-permit support" : ""}`, `<button class="ghost sm" data-act="goto" data-v="4">Correct</button>`)}
        ${line("Work style", D.tradeoffs.map(t => esc(me.tradeoffs[t.id] === "a" ? t.a : t.b)).join(" · "), `<button class="ghost sm" data-act="goto" data-v="5">Correct</button>`)}
        ${line("Work sample", me.evidence ? esc(me.evidence.summary) + ` <span class="badge ok">approved by you</span>` : '<span class="mut">None shared (never counts against you)</span>', `<a href="#/cand/evidence"><button class="ghost sm">Review</button></a>`)}
      </div>
      <div class="note" style="margin-top:12px"><b>Never collected:</b> photo, age, gender, nationality, school or university names, CV file. <b>Kept:</b> until 30 days after the event. <b>Decisions about you</b> are made by a named organiser with a written reason; you can ask to see them.</div>
      ${corr.length ? `<h3 style="margin-top:16px">Your corrections</h3>${corr.map(c => `<div class="corrected">${esc(fmtTime(c.at))}: ${esc(c.what)}</div>`).join("")}` : ""}
      <p class="sm" style="margin-top:14px"><a href="#/cand">← questionnaire</a> · <a href="#/cand/stands">stands for you →</a></p></div>`;
  }

  function viewEvidence() {
    const me = cand(ME), ev = S.ev[ME] || { stage: me.evidence ? "done" : "start" };
    let body = "";
    if (ev.stage === "start" || ev.stage === "done") body = `
      <div class="grid2">
        <div class="card"><h3>Share a link</h3><p class="sm mut">A public project, report, app, design case or repository.</p>
          <input id="evlink" style="width:100%" value="${esc(me.evidence ? me.evidence.link : "https://example.org/portfolio/" + ME.toLowerCase())}">
          <label class="xs" style="display:block;margin:8px 0"><input type="checkbox" id="evok" checked> Read only this page. Don't search for me anywhere else.</label>
          <button class="sm" data-act="evsum">Summarise what it shows</button></div>
        <div class="card"><h3>No public work? Describe one thing you built</h3><p class="sm mut">Three short answers. Treated exactly like a link.</p>
          <input style="width:100%;margin-bottom:6px" placeholder="What was the problem?"><input style="width:100%;margin-bottom:6px" placeholder="What did you do yourself?"><input style="width:100%;margin-bottom:6px" placeholder="What changed because of it?">
          <button class="ghost sm" data-act="evdesc">Use this instead</button></div>
      </div>${me.evidence ? `<div class="okbox" style="margin-top:12px"><b>Currently shared (approved by you):</b> ${esc(me.evidence.summary)} <button class="ghost sm" data-act="evremove">Stop sharing</button></div>` : ""}`;
    if (ev.stage === "reading") body = `<div class="card"><p>Reading only <b>${esc(ev.link)}</b>…</p><div class="bar"><i style="width:60%"></i></div></div>`;
    if (ev.stage === "draft") body = `<div class="card"><span class="badge warn">Only you can see this until you approve it</span>
      <h3 style="margin-top:8px">Draft summary of ${esc(ev.link)}</h3>
      <textarea id="evtext">${esc(ev.text)}</textarea>
      <p class="xs mut">What it does <b>not</b> say: anything about you as a person, your quality or your fit. It only describes what the work demonstrates. In this prototype the summary is pre-written (illustrative); in a real pilot an AI model drafts it from the page you shared.</p>
      <button data-act="evapprove">Approve and share with organisers</button> <button class="quiet" data-act="evdiscard">Discard</button></div>`;
    app.innerHTML = `<div class="wiz"><a href="#/cand" class="sm">← questionnaire</a><h1 style="margin-top:8px">Work sample <span class="badge info">mock-up</span></h1>
      <p class="mut">Optional. You decide what is shared, you approve the summary, and having no portfolio is never a negative signal.</p>${body}</div>`;
  }

  // ---------------------------------------------------------------- after the event
  function viewAfter() {
    const fb = S.fb;
    const q = (side, who) => `<div class="phone"><div class="xs mut">Day after · ${esc(D.event.name)}</div>
      <h3 style="margin-top:8px">Was your conversation with ${esc(who)} relevant?</h3><p class="xs mut">One tap. ${side === "cand" ? "The company never sees your individual answer." : "The candidate never sees your individual answer."}</p>
      ${["Yes", "Partly", "No"].map(v => `<span class="opt ${fb[side] === v ? "on" : ""}" data-act="fb" data-side="${side}" data-v="${v}" style="display:block;margin:6px 0;text-align:center">${v}</span>`).join("")}
      ${fb[side] ? `<div class="bubble sm">${fb[side] === "No" ? "Thanks. What was missing? " + ["Skills", "Language", "Level", "Timing"].map(x => `<span class="chip">${x}</span>`).join("") : "Thanks! This helps us plan the next event."}</div>` : ""}</div>`;
    app.innerHTML = `<h1>After the event <span class="badge info">mock-up</span></h1>
      <p class="mut">One screen, one question, to both sides of every planned conversation. The answers become proof of quality for companies and help organisers improve introductions. No ratings of people are stored.</p>
      <div class="grid2" style="margin-top:16px">${q("cand", "Puro Analytics")}${q("comp", "candidate C-027 (Olena K.)")}</div>
      <div class="card" style="margin-top:18px"><h2>What companies see next time <span class="illus">illustrative figures</span></h2>
        <div class="grid3"><div><div style="font-size:30px;font-weight:700">78%</div><div class="sm mut">of hand-picked introductions rated relevant by both sides</div></div>
        <div><div style="font-size:30px;font-weight:700">41%</div><div class="sm mut">of unplanned stand visits rated relevant</div></div>
        <div><div style="font-size:30px;font-weight:700">3.1</div><div class="sm mut">relevant conversations per company stand</div></div></div>
        <p class="xs mut" style="margin-top:10px">These numbers are invented to show the screen. In a pilot they would be computed from the one-tap answers, published only as aggregates of at least 5 answers.</p></div>`;
  }

  // ---------------------------------------------------------------- docs
  async function viewDoc(k) {
    const tabs = [["concept", "Concept (one page)"], ["responsible", "Responsible AI"], ["demo", "Demo script"], ["mentors", "Questions for mentors"]];
    app.innerHTML = `<div class="doctabs">${tabs.map(([v, t]) => `<a href="#/${v}"><button class="${v === k ? "" : "quiet"} sm">${t}</button></a>`).join("")}</div><div class="doc" id="doc">Loading…</div>`;
    try { const md = await (await fetch(`docs/${k}.md`)).text(); document.getElementById("doc").innerHTML = window.marked ? marked.parse(md) : `<pre>${esc(md)}</pre>`; }
    catch (e) { document.getElementById("doc").textContent = "Could not load the document."; }
  }

  // ---------------------------------------------------------------- events (delegated)
  function mutateMe(fn, what) { const me = cand(ME); const patch = fn(JSON.parse(JSON.stringify(me))); setMe(patch); if (!what && S.ui.correcting) what = `Corrected “${S.ui.correcting}”`; if (what) { (S.corr[ME] = S.corr[ME] || []).push({ at: new Date().toISOString(), what }); save(); } route(); }
  function compEdit(coId, patch) { S.comp[coId] = Object.assign({}, S.comp[coId] || {}, patch); save(); route(); }
  const curCo = () => (location.hash.split("/")[2] || "puro");
  const onMePage = () => location.hash.startsWith("#/cand/me");

  app.addEventListener("click", ev => {
    const t = ev.target.closest("[data-act]"); if (!t) return;
    const a = t.dataset.act, v = t.dataset.v, ui = S.ui;
    const co = t.dataset.co || curCo();
    if (a === "toggle") { ui.open[co + t.dataset.id] = !ui.open[co + t.dataset.id]; save(); return route(); }
    if (a === "src") { ui.open["src" + t.dataset.id] = !ui.open["src" + t.dataset.id]; save(); return route(); }
    if (a === "show") { ui.show = v; ui.more = false; save(); return route(); }
    if (a === "more") { ui.more = true; return route(); }
    if (a === "pick") { const inp = document.getElementById("why-" + t.dataset.id); inp.dataset.pick = v; t.parentElement.querySelectorAll('[data-act="pick"]').forEach(b => b.classList.toggle("quiet", b !== t)); inp.focus(); return; }
    if (a === "decide") {
      const inp = document.getElementById("why-" + t.dataset.id), d = decOf(co, t.dataset.id);
      const pick = inp.dataset.pick || (d && d.d); const reason = inp.value.trim();
      if (!pick) return toast("Choose Introduce, Maybe later or Not this time first.");
      if (reason.length < 8) { inp.focus(); return toast("Write one line explaining why (it is part of the record)."); }
      (S.dec[co] = S.dec[co] || {})[t.dataset.id] = { d: pick, reason, at: new Date().toISOString(), by: ORGANISER }; save(); route();
      return toast(pick === "introduce" ? "Introduction saved. The company gets it with your reason." : "Decision saved with your reason.");
    }
    if (a === "reveal") { ui.reveal[t.dataset.id] = true; save(); return route(); }
    if (a === "remind") return toast("Reminder sent: “One minute: confirm who you want to meet at your stand.”");
    if (a === "csv") {
      const rows = [["when", "company", "candidate", "decision", "reason", "by"]];
      for (const [c, o] of Object.entries(S.dec)) for (const [id, d] of Object.entries(o)) rows.push([d.at, CO[c].name, id, d.d, d.reason, d.by]);
      const blob = new Blob([rows.map(r => r.map(x => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n")], { type: "text/csv" });
      const u = URL.createObjectURL(blob), l = document.createElement("a"); l.href = u; l.download = "esittely-decisions.csv"; l.click(); return;
    }
    // company
    const p = location.hash.startsWith("#/company") ? prof(co) : null;
    if (a === "fi") return compEdit(co, { finnish: v });
    if (a === "exp" && p) return compEdit(co, { exp: +v });
    if (a === "intl") return compEdit(co, { intl: v, international: v });
    if (a === "start" && p) return compEdit(co, { start: v });
    if (a === "mode" && p) return compEdit(co, { modes: p.modes.includes(v) ? p.modes.filter(m => m !== v) : p.modes.concat(v) });
    if (a === "trade" && p) return compEdit(co, { tradeoffs: Object.assign({}, (S.comp[co] || {}).tradeoffs, { [t.dataset.t]: v }) });
    if (a === "demote" && p) { const i = +t.dataset.i; return compEdit(co, { must: p.must.filter((_, j) => j !== i), nice: p.nice.concat(p.must[i]) }); }
    if (a === "promote" && p) { const i = +t.dataset.i; return compEdit(co, { must: p.must.concat([[p.nice[i]]]), nice: p.nice.filter((_, j) => j !== i) }); }
    if (a === "dropnice" && p) { const i = +t.dataset.i; return compEdit(co, { nice: p.nice.filter((_, j) => j !== i) }); }
    if (a === "confirm") { const took = Math.round((Date.now() - timerStart) / 1000); compEdit(co, { confirmedAt: new Date().toISOString(), took }); return toast(`Confirmed in ${Math.floor(took / 60)}:${String(took % 60).padStart(2, "0")}. Your stand is now promoted.`); }
    if (a === "tryad") {
      const txt = document.getElementById("adtext").value; if (!txt.trim()) return;
      const x = L.extract(txt);
      document.getElementById("tryout").innerHTML = `<table style="margin-top:8px"><tr><th>Field</th><th>Draft</th><th>From the line</th></tr>
        ${[["Role", D.roles[x.role] || "—", "role"], ["Experience", L.EXPMIN[x.exp], "exp"], ["Must-haves", x.must.map(L.groupLabel).join(", ") || "—", null], ["Nice to have", x.nice.map(L.skillLabel).join(", ") || "—", null], ["Finnish", FI[x.finnish], "finnish"], ["Work mode", x.modes.map(m => L.MODE[m]).join(", ") || "—", "modes"], ["International", INTL[x.intl], "intl"], ["Start", L.START[x.start] || "—", "start"]]
          .map(([f, d, k]) => `<tr><td>${f}</td><td>${esc(d)}</td><td class="xs mut">${k && x.src[k] ? esc(x.src[k].map(i => x.lines[i]).join(" · ")) : ""}</td></tr>`).join("")}</table>`;
      return;
    }
    // candidate
    if (a === "step") { ui.step = +v; save(); return route(); }
    if (a === "goto") { ui.step = +v; ui.correcting = STEPS[+v]; save(); location.hash = "#/cand"; return; }
    if (a === "role") return mutateMe(m => ({ roles: m.roles.includes(v) ? m.roles.filter(r => r !== v) : m.roles.concat(v).slice(-2) }));
    if (a === "cexp") return mutateMe(() => ({ exp: +v }));
    if (a === "depth") return mutateMe(m => { m.skills[+t.dataset.i].depth = v; if (v !== "work") delete m.skills[+t.dataset.i].years; else m.skills[+t.dataset.i].years = m.skills[+t.dataset.i].years || 1; return { skills: m.skills }; });
    if (a === "rmskill") return mutateMe(m => ({ skills: m.skills.filter((_, j) => j !== +t.dataset.i) }));
    if (a === "addskill") return mutateMe(m => ({ skills: m.skills.concat({ id: v, depth: "project" }) }));
    if (a === "lang") return mutateMe(m => ({ langs: Object.assign({}, m.langs, { [t.dataset.k]: v }) }));
    if (a === "cmode") return mutateMe(m => ({ mode: m.mode.includes(v) ? m.mode.filter(x => x !== v) : m.mode.concat(v) }));
    if (a === "ctype") return mutateMe(m => ({ types: m.types.includes(v) ? m.types.filter(x => x !== v) : m.types.concat(v) }));
    if (a === "cstart") return mutateMe(() => ({ start: v }));
    if (a === "ctrade") return mutateMe(m => ({ tradeoffs: Object.assign({}, m.tradeoffs, { [t.dataset.t]: v }) }));
    if (a === "want") return mutateMe(m => ({ wants: m.wants.includes(v) ? m.wants.filter(x => x !== v) : m.wants.concat(v) }));
    if (a === "evsum") {
      const link = document.getElementById("evlink").value.trim(); if (!document.getElementById("evok").checked) return toast("Tick the box so we only read the page you shared.");
      S.ev[ME] = { stage: "reading", link }; save(); route();
      setTimeout(() => { S.ev[ME] = { stage: "draft", link, text: "A public Power BI report built on open Helsinki Region Transport data: five pages of charts, with filters by line and time of day, and a short written method note. It demonstrates: building BI dashboards, data modelling, explaining results in plain language." }; save(); route(); }, 1100);
      return;
    }
    if (a === "evdesc") { S.ev[ME] = { stage: "draft", link: "your own description", text: "Describes one piece of work in the candidate's own words (problem, what they did, what changed)." }; save(); return route(); }
    if (a === "evapprove") { const text = document.getElementById("evtext").value; const e = S.ev[ME]; setMe({ evidence: { skill: "analytics", link: e.link, summary: text, status: "approved" } }); (S.corr[ME] = S.corr[ME] || []).push({ at: new Date().toISOString(), what: "Approved and shared a work-sample summary" }); S.ev[ME] = { stage: "done" }; save(); toast("Approved. Organisers now see this summary."); location.hash = "#/cand/me"; return; }
    if (a === "evdiscard") { S.ev[ME] = { stage: "start" }; save(); return route(); }
    if (a === "evremove") { setMe({ evidence: null }); (S.corr[ME] = S.corr[ME] || []).push({ at: new Date().toISOString(), what: "Stopped sharing the work sample" }); S.ev[ME] = { stage: "start" }; save(); return route(); }
    if (a === "fb") { S.fb[t.dataset.side] = v; save(); return route(); }
  });
  app.addEventListener("change", ev => {
    const t = ev.target, a = t.dataset.act, v = t.value; if (!a) return;
    const co = curCo();
    if (a === "filt") { S.ui.f[t.dataset.v] = t.checked; save(); return route(); }
    if (a === "sort") { S.ui.sort = v; save(); return route(); }
    if (a === "pickco") { location.hash = "#/company/" + v; return; }
    if (a === "addmust" && v) { const p = prof(co); return compEdit(co, { must: p.must.concat([[v]]), nice: p.nice.filter(x => x !== v) }); }
    if (a === "career") return mutateMe(() => ({ careerChange: v || null }));
    if (a === "years") return mutateMe(m => { m.skills[+t.dataset.i].years = +v; return { skills: m.skills }; });
    if (a === "example") return mutateMe(m => { m.skills[+t.dataset.i].example = v.trim() || undefined; return { skills: m.skills }; });
    if (a === "addskillsel" && v) return mutateMe(m => ({ skills: m.skills.concat({ id: v, depth: "project" }) }));
    if (a === "permit") return mutateMe(() => ({ permit: t.checked }));
    if (a === "medepth") {
      const i = +t.dataset.i, me = cand(ME), s = me.skills[i];
      return mutateMe(m => v === "remove" ? { skills: m.skills.filter((_, j) => j !== i) } : (m.skills[i].depth = v, v !== "work" && delete m.skills[i].years, { skills: m.skills }),
        v === "remove" ? `Removed ${L.skillLabel(s.id)}` : `Changed ${L.skillLabel(s.id)}: ${L.DEPTH[s.depth]} → ${L.DEPTH[v]}`);
    }
  });
  // hover a company field -> highlight the ad lines it came from
  app.addEventListener("mouseover", ev => {
    const f = ev.target.closest("[data-src]"); document.querySelectorAll(".ad .ln.hl").forEach(x => x.classList.remove("hl"));
    if (f && f.dataset.src) f.dataset.src.split(",").filter(Boolean).forEach(i => { const ln = document.querySelector(`.ad .ln[data-ln="${i}"]`); if (ln) ln.classList.add("hl"); });
  });
  route();
})();
