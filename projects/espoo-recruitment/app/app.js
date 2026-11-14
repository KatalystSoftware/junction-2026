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
    if (k === "event") return viewEvent();
    if (k === "join") return viewJoin(h[1] || "", h[2] || "");
    if (k === "org") { if (h[1] === "questions") return viewQuestions(); const id = CO[h[1]] ? h[1] : "puro"; return h[2] === "review" ? viewReview(id) : viewOrg(id); }
    if (k === "log") return viewLog();
    if (k === "company") { const id = CO[h[1]] ? h[1] : "puro"; return h[2] === "intros" ? viewIntros(id) : viewCompany(id); }
    if (k === "cand") return h[1] === "stands" ? viewStands() : h[1] === "me" ? viewMe() : h[1] === "evidence" ? viewEvidence() : viewWizard();
    if (k === "after") return viewAfter();
    if (["concept", "responsible", "demo", "mentors"].includes(k)) return viewDoc(k);
    return viewHome();
  }
  // a new screen starts at its top; going back (or forward) through the browser's history returns to where the reader was
  const scrolls = {}; let at = (history.state && typeof history.state.i === "number") ? history.state.i : 0;
  if (!history.state) history.replaceState({ i: at }, "");
  if ("scrollRestoration" in history) history.scrollRestoration = "manual"; // otherwise the browser restores its own position after ours
  const settle = (y, tries) => { window.scrollTo(0, y); if (Math.abs(window.scrollY - y) > 2 && tries > 0) setTimeout(() => settle(y, tries - 1), 50); };
  window.addEventListener("hashchange", () => {
    scrolls[at] = window.scrollY;
    const st = history.state, back = st && typeof st.i === "number";
    if (back) at = st.i; else { at += 1; history.replaceState({ i: at }, ""); }
    route(); settle(back ? (scrolls[at] || 0) : 0, back ? 10 : 0);
  });
  document.getElementById("hostev").textContent = `${D.event.name}, ${D.event.date}`;

  // ---------------------------------------------------------------- home
  function viewHome() {
    app.innerHTML = `
    <section class="hero">
      <div>
        <span class="badge blue">City of Espoo · Rethinking Recruitment · Junction 2026 prototype</span>
        <h1 style="margin-top:10px">Fewer, better conversations at Espoo's recruitment events.</h1>
        <p class="mut"><b>Esittely</b> (Finnish for “introduction”) is a light layer on top of event registration. Companies say in a minute who they want to meet, candidates answer a few concrete questions, and City organisers hand-pick the introductions, with a reason. Matchmaking platforms let an algorithm rank people; here the organiser decides.</p>
        <div class="principle"><span><b>The software gathers and translates</b> what people said.</span><span><b>People decide</b> who meets whom, with a reason.</span><span><b>No scores, no rankings of people.</b></span></div>
        <p>One event, in order: the company confirms its needs, the applicant joins, the organiser hand-picks the introductions, both sides meet on the day, and both say the day after whether it was relevant. What you do in one step shows up in the next.</p>
        <p><a href="#/company/puro"><button style="padding:12px 18px;font-size:16px">Start at 1 · Company confirms its needs →</button></a></p>
      </div>
      <div class="card">
        <h3>${esc(D.event.name)} <span class="mut sm">· ${esc(D.event.date)} · ${esc(D.event.format)}</span></h3>
        <div class="grid2" style="margin-top:8px">
          <div><div style="font-size:30px;font-weight:700">${D.companies.length}</div><div class="sm mut">company stands</div></div>
          <div><div style="font-size:30px;font-weight:700">${D.candidates.length}</div><div class="sm mut">registered candidates (synthetic)</div></div>
        </div>
        <hr><p class="sm mut" style="margin:0">${esc(D.generated)}. Nobody here is real. Read: <a href="#/concept">concept</a> · <a href="#/responsible">responsible AI</a> · <a href="#/demo">demo script</a> · <a href="#/mentors">questions for Espoo</a></p>
      </div>
    </section>`;
  }

  // ---------------------------------------------------------------- event day: both sides see the same planned conversations
  function viewEvent() {
    const coId = "puro", me = cand(ME);
    const mine = Object.entries(S.dec).filter(([, o]) => o[ME] && o[ME].d === "introduce").map(([co, o]) => ({ co, d: o[ME], slot: L.slotFor(co, ME) }));
    app.innerHTML = `<h1>Event day: planned conversations</h1>
      <p class="mut">What phases 1 to 3 produced. The company sees its hand-picked introductions with the organiser's reason; the candidate sees the same conversations with the same times. Nobody is blocked: any candidate can still visit any stand.</p>
      <div class="event2">
        <div class="card"><span class="badge ok">Company stand</span>${introsHtml(coId)}</div>
        <div class="card"><span class="badge info">Candidate's phone</span><h2 style="margin-top:8px">${esc(me.name || "Olena K.")} (${ME})</h2>
          ${mine.length ? `<div class="okbox"><b>Your planned conversations</b>${mine.map(m => `<div class="sm" style="margin-top:4px">${m.slot} · <b>${esc(CO[m.co].name)}</b>, stand ${CO[m.co].stand}. The organiser's note: “${esc(m.d.reason)}”</div>`).join("")}</div>`
            : `<div class="note">No planned conversation yet. In phase 3 the organiser can introduce ${ME} to a company; it then appears here with a time and the reason.</div>`}
          <p class="sm" style="margin-top:12px"><a href="#/cand/stands">Stands worth visiting →</a> · <a href="#/cand/me">How organisers see you →</a></p></div>
      </div>`;
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
          ${needsGrid(p)}
        </div>
        ${fairness(coId, p, P)}
        <div class="controls"><a href="#/org/questions" style="margin-left:auto;order:8"><button class="sm quiet">Event questions</button></a><a href="#/org/${coId}/review" style="order:9"><button class="sm">Review one at a time →</button></a>
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

  const needsGrid = p => `<div class="needs">
            ${p.must.map(g => `<div class="need"><div class="k">Must-have</div><b>${terms(g)}</b><div class="sm mut">${g.map(id => esc(L.SKILL[id]?.plain || "")).join(" Or: ")}</div>${g.map(id => L.SKILL[id]?.esco ? `<div class="xs"><a href="${esc(L.SKILL[id].esco.uri)}" target="_blank" rel="noopener">ESCO: ${esc(L.SKILL[id].esco.title)}</a></div>` : "").join("")}</div>`).join("")}
            <div class="need"><div class="k">Nice to have</div>${p.nice.map(id => `<div>${term(id)} <span class="sm mut">— ${esc(L.SKILL[id]?.plain || "")}</span></div>`).join("") || '<span class="mut">None stated</span>'}</div>
            <div class="need"><div class="k">Experience</div><b>${esc(L.EXPMIN[p.exp])}</b><div class="sm mut">in ${esc(D.roles[p.role] || "this field")}</div></div>
            <div class="need"><div class="k">Language</div><b>Finnish: ${esc(FI[p.finnish])}</b>${p.note ? `<div class="sm">“${esc(p.note)}”</div>` : ""}<div class="sm mut">${p.finnish === "no" ? "Team works in English" : p.english ? "English is also a working language" : ""}</div></div>
            <div class="need"><div class="k">Practicalities</div><div class="sm">${p.modes.map(m => L.MODE[m]).join(" / ")} · ${p.types.map(t => L.TYPE[t]).join(", ")} · start ${esc(L.START[p.start] || "not stated")}</div><div class="sm">International hires: ${esc(INTL[p.intl].toLowerCase())}</div></div>
          </div>`;

  function candRow(coId, p, { k, f, d }) {
    const open = S.ui.open[coId + k.id];
    const corr = (S.corr[k.id] || []).length;
    const name = S.ui.reveal[k.id] ? `${esc(k.name)}` : `<span class="mut">name hidden</span>`;
    const head = `<div class="head" data-act="toggle" data-id="${k.id}" data-co="${coId}">
      <div><div class="pid">${k.id}</div><div class="xs">${name}</div></div>
      <div class="sm">${esc(D.roles[k.roles[0]])} · ${esc(D.exp[k.exp])}<br>
        <span class="mut">${p.must.map(g => { const hit = g.find(id => { const s = k.skills.find(x => x.id === id); return s && s.depth !== "learning"; }); return `${hit ? "✓" : "○"} ${esc(L.skillLabel(hit || g[0]))}`; }).join(" · ")}${p.finnish === "required" ? ` · Finnish ${esc(L.LVTXT[k.langs.fi])}` : ""}</span>
        ${f.asked ? ' <span class="badge blue">asked to meet</span>' : ""} ${k.verified ? ` <span class="badge ok" title="The candidate confirmed every gathered line themselves">checked by candidate${k.verified.edited ? `, ${k.verified.edited} corrected` : ""}</span>` : ""}${corr && !k.verified ? ' <span class="badge" style="background:var(--violet2);color:var(--violet)">corrected by candidate</span>' : ""}</div>
      <div style="text-align:right">${decBadge(d)} <span class="mut">${open ? "▲" : "▼"}</span></div></div>`;
    if (!open) return `<div class="cand">${head}</div>`;
    const col = (key, title, icon, empty) => `<div class="fcol"><h4>${icon} ${title} <span class="mut">(${f[key].length})</span></h4>${f[key].map((x, i) => {
      const sid = `${coId}|${k.id}|${key}|${i}`; const so = S.ui.open["src" + sid];
      return `<div class="fact ${key}">${esc(x.text)} <button class="srcbtn" data-act="src" data-id="${esc(sid)}">${so ? "hide source" : "source"}</button>${so ? srcHtml(x.src) : ""}</div>`;
    }).join("") || `<div class="sm mut">${empty}</div>`}</div>`;
    return `<div class="cand">${head}
      ${k.own && (k.own.about || k.own.looking) ? `<div class="ownq"><b>In their own words:</b> ${k.own.about ? `“${esc(k.own.about)}”` : ""} ${k.own.looking ? `<span class="mut">Looking for:</span> “${esc(k.own.looking)}”` : ""}</div>` : ""}${k.eventAnswers && k.eventAnswers.length ? `<div class="ownq"><b>Event questions:</b> ${k.eventAnswers.map(x => `${esc(x.q)} <b>${esc(x.a)}</b>`).join(" · ")}</div>` : ""}
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

  function introsHtml(coId) {
    const c = CO[coId], p = prof(coId), P = pool();
    const intro = Object.entries(S.dec[coId] || {}).filter(([, d]) => d.d === "introduce");
    return `<h2 style="margin-top:8px">${esc(c.name)}: your hand-picked introductions</h2>
      <p class="mut sm">An Espoo organiser read each attendee's answers against your confirmed needs and chose these conversations, each with a reason. Names are shared at the event, when the candidate agrees.</p>
      <div class="note" style="margin-bottom:12px">Promoted to <b>${esc(L.poolCount(p, P).text)}</b> attendees whose answers fit your must-haves. ${P.filter(k => k.wants.includes(coId)).length} asked to visit your stand. Anyone can still visit; these are the planned conversations.</div>
      ${intro.length ? intro.map(([id, d]) => { const k = cand(id), f = L.pairFacts(p, k); return `<div class="stand"><div class="top2"><b>${L.slotFor(coId, id)} · ${id}</b><span class="xs mut">introduced by ${esc(d.by)}</span></div>
        <div class="sm" style="margin:4px 0 8px"><b>Organiser's reason:</b> ${esc(d.reason)}</div>
        <div class="sm">${f.overlap.slice(0, 5).map(x => `<div>✓ ${esc(x.text)}</div>`).join("")}${f.gap.slice(0, 3).map(x => `<div class="mut">○ ${esc(x.text)}</div>`).join("")}</div></div>`; }).join("")
        : `<div class="card mut">No introductions yet. They appear here as the organiser decides in phase 3 (<a href="#/org/${coId}">organiser view</a>).</div>`}`;
  }
  function viewIntros(coId) {
    app.innerHTML = `<div class="wiz" style="max-width:900px"><a href="#/company/${coId}" class="sm">← back to your needs</a>${introsHtml(coId)}</div>`;
  }



  // ---------------------------------------------------------------- organiser review: one candidate at a time, accept or reject with a reason
  function viewReview(coId) {
    const c = CO[coId], p = prof(coId), P = pool();
    const asked = P.filter(k => k.wants.includes(coId));
    const queue = asked.filter(k => L.meetsMust(p, k)).sort((a, b) => a.registered.localeCompare(b.registered));
    const dec = id => decOf(coId, id);
    const undecided = queue.filter(k => !dec(k.id));
    const rq = S.ui.rq = S.ui.rq || {};
    let cur = queue.find(k => k.id === rq[coId]); if (!cur) cur = undecided[0];
    const n = v => queue.filter(k => dec(k.id) && dec(k.id).d === v).length;
    const factsCols = (k, f) => {
      const col = (key, title, icon, empty) => `<div class="fcol"><h4>${icon} ${title} <span class="mut">(${f[key].length})</span></h4>${f[key].map((x, i) => {
        const sid = `${coId}|${k.id}|${key}|${i}`; const so = S.ui.open["src" + sid];
        return `<div class="fact ${key}">${esc(x.text)} <button class="srcbtn" data-act="src" data-id="${esc(sid)}">${so ? "hide source" : "source"}</button>${so ? srcHtml(x.src) : ""}</div>`;
      }).join("") || `<div class="sm mut">${empty}</div>`}</div>`;
      return `<div class="facts rev">${col("overlap", "Overlaps", "✓", "None found")}${col("gap", "Gaps", "○", "No gaps against the must-haves")}${col("check", "Practical checks", "?", "Nothing to check")}${col("style", "Conversation starters", "💬", "")}</div>`;
    };
    let right;
    if (cur) {
      const k = cur, f = L.pairFacts(p, k), d = dec(k.id), name = S.ui.reveal[k.id] ? esc(k.name) : '<span class="mut">name hidden until you decide</span>';
      right = `<div class="card revcard">
        <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
          <div><div class="pid" style="font-size:22px">${k.id} <span class="sm" style="font-weight:400">· ${name}</span></div>
            <div class="sm">${esc(D.roles[k.roles[0]])} · ${esc(D.exp[k.exp])}${k.careerChange ? ` · moving into tech from ${esc(k.careerChange)}` : ""}</div>
            <div style="margin-top:6px">${f.asked ? '<span class="badge blue">asked to meet this company</span>' : ""} ${k.verified ? `<span class="badge ok">checked by candidate${k.verified.edited ? `, ${k.verified.edited} corrected` : ""}</span>` : ""} ${k.evidence ? '<span class="badge">work sample shared</span>' : ""}</div></div>
          <div class="sm mut" style="text-align:right">${queue.indexOf(k) + 1} of ${queue.length}<br>registered ${esc(fmtTime(k.registered))}</div></div>
        ${k.own && (k.own.about || k.own.looking) ? `<div class="ownq" style="margin:10px 0 0"><b>In their own words:</b> ${k.own.about ? `“${esc(k.own.about)}”` : ""} ${k.own.looking ? `<span class="mut">Looking for:</span> “${esc(k.own.looking)}”` : ""}</div>` : ""}${k.eventAnswers && k.eventAnswers.length ? `<div class="ownq"><b>Event questions:</b> ${k.eventAnswers.map(x => `${esc(x.q)} <b>${esc(x.a)}</b>`).join(" · ")}</div>` : ""}
        <p class="xs mut" style="margin:10px 0 0 14px">Every line below is the candidate's own confirmed answer set against what ${esc(c.name)} stated. Nothing is scored.</p>
        ${factsCols(k, f)}
        <div class="decide">
          <b class="sm">Your decision</b>
          ${["introduce", "maybe", "no"].map(v => `<button class="${d && d.d === v ? "" : "quiet"} sm" data-act="pick" data-v="${v}" data-id="${k.id}" data-co="${coId}">${{ introduce: "Introduce", maybe: "Maybe later", no: "Not this time" }[v]}</button>`).join("")}
          <input id="why-${k.id}" placeholder="One line: why? (required, shared with the company if you introduce)" value="${esc(d ? d.reason : "")}" maxlength="160">
          <button class="sm" data-act="decide" data-id="${k.id}" data-co="${coId}">Save and next</button>
          ${S.ui.reveal[k.id] ? "" : `<button class="ghost sm" data-act="reveal" data-id="${k.id}" ${d ? "" : "disabled title='Decide first'"}>Show name</button>`}
          ${undecided.length > 1 || d ? `<button class="quiet sm" data-act="rq-skip" data-co="${coId}" data-id="${k.id}">Skip for now</button>` : ""}
        </div>
        ${d ? `<div class="okbox" style="margin:0 14px 14px">Decided: ${decBadge(d)} “${esc(d.reason)}” · ${esc(d.by)}, ${esc(fmtTime(d.at))}. ${d.d === "introduce" ? `The company gets this reason with the introduction; the candidate sees it as the organiser's note.` : ""}</div>` : ""}
      </div>`;
    } else {
      right = `<div class="card"><h2>All ${queue.length} decided</h2>
        <p class="mut">${n("introduce")} introduced, ${n("maybe")} maybe later, ${n("no")} not this time. Each with your reason, logged under your name.</p>
        ${queue.map(k => { const d = dec(k.id); return `<div class="sm" style="padding:6px 0;border-bottom:1px solid var(--line)"><b>${k.id}</b> ${decBadge(d)} “${esc(d.reason)}” <button class="link xs" data-act="rq" data-v="${k.id}" data-co="${coId}">revisit</button></div>`; }).join("")}
        <div class="row" style="gap:8px;margin-top:14px;flex-wrap:wrap"><a href="#/event"><button>Event day: planned conversations →</button></a><a href="#/log"><button class="ghost">Decision log</button></a><a href="#/org/${coId}"><button class="quiet">Back to the list</button></a></div></div>
        ${fairness(coId, p, P)}`;
    }
    app.innerHTML = `
    <div class="row" style="justify-content:space-between;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px">
      <div><span class="badge blue">For ${esc(ORGANISER)} · ${esc(c.name)}</span>
        <h1 style="margin-top:8px">Who should ${esc(c.name)} meet? One person at a time, with a reason.</h1>
        <p class="mut" style="margin:0">Everyone in this queue asked to meet ${esc(c.name)} and meets its stated must-haves (${queue.length} of the ${asked.length} who asked). The order is registration time; nothing is scored. Names stay hidden until you decide.</p></div>
      <div class="sm mut">Company: <select data-act="pickrev">${D.companies.map(x => `<option value="${x.id}" ${x.id === coId ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select> · <a href="#/org/${coId}">list view</a></div>
    </div>
    <div class="livecount"><div class="n">${undecided.length}</div><div class="t"><b>still to decide</b><br>${n("introduce")} introduced · ${n("maybe")} maybe later · ${n("no")} not this time. ${p.confirmed ? "The company confirmed its needs." : "The company has not confirmed; its needs are a draft from the job ad, so treat gaps as questions."}</div>
      <div style="margin-left:auto;text-align:right"><div class="timer">${queue.length - undecided.length} / ${queue.length}</div><div class="xs" style="color:#aab6cf">decided</div></div></div>
    <div class="cmp rev" style="margin-top:14px">
      <div class="card"><h3>What ${esc(c.name)} needs</h3>${p.confirmed ? "" : '<div class="warnbox" style="margin:0 0 10px;font-size:13px">Unconfirmed draft from the public job ad.</div>'}${needsGrid(p)}
        <h3 style="margin-top:16px">Queue</h3>
        ${queue.map(k => { const d = dec(k.id); return `<div class="qrow ${cur && k.id === cur.id ? "on" : ""} ${d ? "done" : ""}" data-act="rq" data-v="${k.id}" data-co="${coId}"><span>${k.id}</span><span class="xs mut">${esc(D.roles[k.roles[0]])} · ${esc(D.exp[k.exp])}</span><span>${d ? decBadge(d) : '<span class="xs mut">undecided</span>'}</span></div>`; }).join("") || '<div class="sm mut">Nobody who asked meets the stated must-haves. Widen the view in the list.</div>'}
      </div>
      <div>${right}</div>
    </div>`;
  }

  // ---------------------------------------------------------------- applicant joining: an invitation that is already filled in
  // Every step is a URL: #/join (what we may read) -> #/join/reading -> #/join/check/general -> #/join/check/event -> #/join/check/you -> #/join/check/confirm -> #/join/done
  const SRC = window.SOURCES || {};
  const LANGNAME = { en: "English", fi: "Finnish", sv: "Swedish" };
  const SRCNAME = { linkedin: "LinkedIn", github: "GitHub", portfolio: "Portfolio" };
  const DEMO = true; // in the demo every Next and Confirm stays clickable; what is still open is said, never enforced
  const JSTEPS = [["general", "General information"], ["event", "Questions for this event"], ["you", "In your own words"], ["confirm", "Confirm"]];
  const firstName = () => (cand(ME).name || "Olena K.").split(" ")[0];
  function joinState() {
    if (!S.join) { S.join = { consent: { linkedin: true, github: true, portfolio: false, project: false }, ids: { linkedin: "linkedin.com/in/olena-k", github: "github.com/olena-k", portfolio: "olena-k.example", project: "" }, project: null, facts: null, skipped: [], lines: [], own: { about: "", looking: "" }, trade: {}, types: ["full"], permit: false, ans: {}, wants: null, seen: {}, done: null, started: null }; save(); }
    if (!S.join.ans) S.join.ans = {}; if (!S.join.seen) S.join.seen = {}; if (!S.join.ids) S.join.ids = { linkedin: "linkedin.com/in/olena-k", github: "github.com/olena-k", portfolio: "olena-k.example", project: "" };
    return S.join;
  }
  function joinScan(J) {
    const c = J.consent;
    const r = L.scanSources({ linkedin: c.linkedin ? SRC.linkedin : null, github: c.github ? SRC.github : null, portfolio: c.portfolio ? SRC.portfolio : null });
    r.facts.forEach(f => { f.status = "ok"; }); // everything starts ticked: the applicant changes or removes what is wrong, instead of clicking every line
    J.facts = r.facts; J.skipped = r.skipped; J.lines = r.lines; J.started = Date.now(); J.seen = {}; J.ans = {}; save();
  }
  const jFact = (J, kind, value) => (J.facts || []).find(f => f.kind === kind && (value === undefined || f.value === value) && f.status !== "removed");
  function jSet(J, kind, value, patch) {
    // change a drafted value: the fact becomes "corrected by you"; a value the scan did not find is added by the applicant
    let f = jFact(J, kind, kind === "skill" || kind === "lang" ? value : undefined);
    if (!f) { f = { id: "f" + Date.now() + Math.random().toString(36).slice(2, 6), kind, value, from: "You", where: "", quote: "", li: null, lis: [], status: "edited" }; (J.facts = J.facts || []).push(f); }
    Object.assign(f, patch || {}); if (f.status !== "removed") f.status = "edited"; save();
  }
  const jGo = s => { location.hash = "#/join/" + s; };
  const isOpenJ = (J, id) => !!(J.open && J.open[id]);

  // The event's questions to applicants. Suggested from what the attending companies said they need; the organiser rewords, switches off or adds.
  const QKIND = { skills: "pick many", lang: "level", ynl: "yes / learning / no", trade: "either / or", wants: "pick companies", text: "free text" };
  function eventQuestions() { if (!S.evq) { S.evq = { qs: suggestQuestions() }; save(); } return S.evq; }
  function suggestQuestions() {
    const P = profiles(), who = {};
    P.forEach(p => new Set(p.must.flat().concat(p.nice)).forEach(id => (who[id] = who[id] || []).push(p.company.name)));
    const ranked = Object.entries(who).sort((a, b) => b[1].length - a[1].length);
    const qs = [{ id: "skills", kind: "skills", on: true, text: "Which of these do you use, at work or in your own projects?", why: `The ${P.length} companies at this event named these most often`, opts: ranked.slice(0, 10).map(([v, names]) => ({ v, who: names })) }];
    const fiReq = P.filter(p => p.finnish === "required"), fiHelp = P.filter(p => p.finnish === "helpful");
    if (fiReq.length || fiHelp.length) qs.push({ id: "finnish", kind: "lang", lang: "fi", on: true, text: "How is your Finnish at work?", why: `${fiReq.length} compan${fiReq.length === 1 ? "y needs" : "ies need"} Finnish, ${fiHelp.length} say it helps but is not required` });
    ranked.filter(([id, names]) => names.length === 1 && P.find(p => p.company.name === names[0]).must.flat().includes(id)).slice(0, 3)
      .forEach(([id, names]) => qs.push({ id: "must-" + id, kind: "ynl", skill: id, on: true, text: `Have you worked with ${L.skillLabel(id)}?`, why: `${names[0]} asks for it as a must-have` }));
    D.tradeoffs.forEach(t => qs.push({ id: "trade-" + t.id, kind: "trade", t: t.id, a: t.a, b: t.b, on: true, text: t.q, why: "Every company here answered the same question about itself" }));
    qs.push({ id: "wants", kind: "wants", on: true, text: "Which companies would you like to meet?", why: "Helps the organiser plan introductions; you can still visit any stand" });
    return qs;
  }
  function evAnswer(J, q) {
    // what the applicant sees ticked: their own click first, otherwise what their sources gave
    if (q.kind === "skills") return (J.facts || []).filter(f => f.kind === "skill" && f.status !== "removed").map(f => f.value);
    if (q.kind === "lang") { const f = jFact(J, "lang", q.lang); return f ? f.level : "none"; }
    if (q.kind === "trade") return J.trade[q.t] || "";
    if (q.kind === "wants") return J.wants || cand(ME).wants || [];
    if (J.ans[q.id] !== undefined) return J.ans[q.id];
    if (q.kind === "ynl") { const f = jFact(J, "skill", q.skill); return f ? (f.depth === "learning" ? "learning" : "yes") : ""; }
    return "";
  }
  function evPrefilled(J, q) {
    if (q.kind === "skills") return (J.facts || []).some(f => f.kind === "skill" && f.from !== "You" && f.status !== "removed");
    if (q.kind === "lang") { const f = jFact(J, "lang", q.lang); return !!(f && f.from !== "You"); }
    if (q.kind === "ynl") return J.ans[q.id] === undefined && !!jFact(J, "skill", q.skill);
    return false;
  }
  const YNL = { yes: "Yes, at work", learning: "Learning it now", no: "Not yet" };

  // Two invitations branch here: the golden ticket (a personal invitation with a reserved place, sent to people who came to
  // earlier events) and the regular one (an open link; the organiser decides whom to introduce). Same check pages, different words.
  const KIND = {
    golden: { title: () => `${esc(firstName())}, you have a golden ticket.`, lead: "You came to one of Espoo's events before, so your place is reserved. Your profile is drafted from what you already agreed we may read, the way companies get theirs drafted from their job ads. <b>You see every line before anyone else does</b>.", eyebrow: "golden ticket", go: "Draft my profile →", confirm: "Confirm: this is me", confirmed: "Confirmed. Only what you checked is used, and organisers see that you checked it.", doneH1: () => `You're in, ${esc(firstName())}.`, doneLead: (t) => `Your place is reserved. Confirmed on ${t}. Only what you checked is used, and the organiser sees that you checked it.`, first: ["Today", "Your profile goes to Espoo's event team", "lines, checked by you", "Marked “checked by the candidate”."] },
    regular: { title: () => `Apply to attend the ${esc(D.event.name)}.`, lead: "Tell us where to read about you, and your application is drafted from it, the way companies get theirs drafted from their job ads. <b>You see every line before anyone else does</b>, and a named organiser decides who is introduced, with a reason.", eyebrow: "application", go: "Draft my application →", confirm: "Send my application", confirmed: "Application sent. A named organiser reads it and tells you their decision with a reason.", doneH1: () => `Application sent, ${esc(firstName())}.`, doneLead: (t) => `Sent on ${t}. Only what you checked is in it, and the organiser sees that you checked it.`, first: ["Next days", "Espoo's event team reads your application", "lines, checked by you", "Accepted or declined by a named organiser, with the reason written down. You get it either way."] },
  };
  const kindOf = (J) => KIND[J.kind] || KIND.regular;
  function viewJoin(step, sec) {
    const J = joinState();
    if (step === "golden" || !step) { const k = step ? "golden" : "regular"; if (J.kind !== k) { J.kind = k; save(); } return joinInvite(J); }
    if (step === "reading") return joinReading(J);
    if (!J.facts) joinScan(J); // a deep link straight to a check page still gets a draft
    if (step === "done") return J.done ? joinDone(J) : joinCheck(J, "confirm");
    return joinCheck(J, JSTEPS.some(([k]) => k === sec) ? sec : "general");
  }
  function joinInvite(J) {
    const c = J.consent;
    const row = (k, title, sub, field) => `<div class="srcrow ${c[k] ? "on" : ""}"><label><input type="checkbox" data-act="jn-consent" data-v="${k}" ${c[k] ? "checked" : ""}><span><b>${title}</b><small>${sub}</small></span></label><span class="fld">${field}</span></div>`;
    const idField = (k, label) => `<input type="text" data-act="jn-srcid" data-v="${k}" value="${esc(J.ids[k] || "")}" aria-label="${label}" placeholder="${label}">`;
    const pr = J.project;
    app.innerHTML = `<div class="wiz join">
      <p class="eyebrow">${esc(D.event.name)} · ${esc(D.event.date)} · ${esc(D.event.format)}</p>
      <h1>${kindOf(J).title()}</h1>
      <p class="mut" style="font-size:1.0625rem;max-width:60ch">${kindOf(J).lead}</p>
      <div class="jcard srcs">
        <h2>What may we read?</h2>
        ${row("linkedin", "LinkedIn profile", "Headline, experience, skills and languages.", idField("linkedin", "LinkedIn address"))}
        ${row("github", "GitHub", "Public repositories only: what they do and in which language.", idField("github", "GitHub user or address"))}
        ${row("portfolio", "Portfolio or website", "One page you choose.", idField("portfolio", "Web address"))}
        ${row("project", "A project of mine", "A report, notebook, repository or slides. Shown to organisers as your work sample, summarised in your words.", `${pr ? `<span class="attached">✓ ${esc(pr.name)} <small>(${Math.max(1, Math.round(pr.size / 1024))} KB, stays in this browser)</small></span><button class="quiet sm" data-act="jn-project-rm">Remove</button>` : `<label class="upl"><input type="file" data-act="jn-project"> Upload a file</label><span class="xs mut">or</span> ${idField("project", "Link to the project")}`}`)}
      </div>
      <div class="promise">
        <div><b>Read once</b> to make the draft, then the raw files are deleted.</div>
        <div><b>You decide</b> what stays: confirm, correct or remove each line.</div>
        <div><b>Never used:</b> photo, age, gender, nationality, school names.</div>
        <div><b>No scores.</b> A named organiser introduces people, with a written reason.</div>
      </div>
      <div class="jnav"><a href="#/cand" class="back">Prefer to type everything yourself? →</a><button data-act="jn-scan" ${DEMO || Object.values(c).some(Boolean) ? "" : "disabled"}>${kindOf(J).go}</button></div>
      <p class="xs mut" style="margin-top:14px">Demo applicant ${esc(cand(ME).name)} (${ME}), synthetic sources. Nothing leaves this browser.</p></div>`;
  }
  function joinReading(J) {
    const rows = Object.keys(SRCNAME).filter(k => J.consent[k]).map(k => [k, SRCNAME[k]]).concat(J.consent.project && (J.project || J.ids.project) ? [["project", "Your project"]] : []);
    const n = k => k === "project" ? "attached as your work sample" : (x => `${x} line${x === 1 ? "" : "s"} used`)((J.facts || []).filter(f => f.from === SRCNAME[k] || (f.lis || []).some(i => (J.lines[i] || {}).from === SRCNAME[k])).length);
    app.innerHTML = `<div class="wiz join"><p class="eyebrow">${esc(D.event.name)}</p><h1>Reading what you chose…</h1><p class="mut">Only these sources, only once. Every line we keep will show where it came from.</p>
      ${rows.map(([k, t]) => `<div class="scanrow" id="scan-${k}"><span class="spin"></span> ${t}<span class="st">reading…</span></div>`).join("") || `<p class="note">No source chosen: the draft starts empty and you fill it in by hand.</p>`}
      <div id="scandone" style="display:none"><div class="cheer" style="margin-top:14px">Found <b>${(J.facts || []).length} things</b> about you. Now the important part: you decide what is true.</div><div class="jnav"><a class="back" href="#/join">← Change what we may read</a><button data-act="jn-go" data-v="check/general">Check the draft →</button></div></div></div>`;
    rows.forEach(([k], i) => setTimeout(() => { const el = document.getElementById("scan-" + k); if (!el) return; el.classList.add("done"); el.querySelector(".spin").outerHTML = "✓"; el.querySelector(".st").textContent = n(k); }, 700 + i * 650));
    setTimeout(() => { const d = document.getElementById("scandone"); if (d) d.style.display = "block"; }, 900 + rows.length * 650);
  }
  function joinCheck(J, sec) {
    const me = cand(ME);
    const F = (J.facts || []).filter(f => f.status !== "removed"), gathered = (J.facts || []).filter(f => f.from !== "You" && f.status !== "removed");
    const edited = gathered.filter(f => f.status === "edited").length, removed = (J.facts || []).filter(f => f.from !== "You" && f.status === "removed").length;
    const role = jFact(J, "role"), exp = jFact(J, "exp"), skills = F.filter(f => f.kind === "skill"), langs = Object.fromEntries(F.filter(f => f.kind === "lang").map(f => [f.value, f]));
    const modes = F.filter(f => f.kind === "mode").map(f => f.value), start = jFact(J, "start");
    const confirmedSkills = new Set(skills.map(f => f.value));
    const stands = profiles().filter(p => p.must.flat().concat(p.nice).some(id => confirmedSkills.has(id))).length;
    J.seen[sec] = true; save();
    const i = JSTEPS.findIndex(([k]) => k === sec), prev = JSTEPS[i - 1], next = JSTEPS[i + 1];
    const steps = `<ol class="jsteps">${JSTEPS.map(([k, t], n) => `<li><a href="#/join/check/${k}" class="${k === sec ? "on" : J.seen[k] ? "done" : ""}">${n + 1}. ${t}</a></li>`).join("")}</ol>`;
    const nav = hint => `<div class="jnav"><a class="back" href="${prev ? "#/join/check/" + prev[0] : "#/join/reading"}">← ${prev ? prev[1] : "Back"}</a>${next ? `<button data-act="jn-go" data-v="check/${next[0]}">Next: ${next[1]} →</button>` : ""}</div>${hint ? `<p class="jhint">${hint}</p>` : ""}`;
    const check = f => f && f.from !== "You" && f.status === "edited" ? `<span class="jbadge edited">corrected by you</span>` : "";
    const short = q => q.length > 90 ? q.slice(0, 88) + "…" : q;
    const fromTxt = f => !f ? `<div class="from">Not in your sources: pick one.</div>` : f.from === "You" ? `<div class="from you">Added by you</div>` : `<div class="from ok" title="${esc(f.quote || f.where)}">${esc(f.from)} · <q>${esc(short(f.quote || f.where))}</q></div>`;
    // one line per fact: value, where it came from, ✓ Correct; the controls appear only when the applicant presses Change (or the fact is missing)
    const isOpen = id => !!(J.open && J.open[id]);
    const row = (f, label, value, control, extra, o = {}) => { const key = f ? f.id : o.key, open = !f && !o.key ? true : isOpen(key);
      return `<div class="jf ${f ? f.status : "new"}"><div><div class="val">${label}<small>${value}</small></div>${o.from ? `<div class="from">${o.from}</div>` : fromTxt(f)}</div><div class="acts">${check(f)}${control && key ? `<button class="quiet sm" data-act="jn-edit" data-id="${key}">${open ? "Done" : "Change"}</button>` : ""}${extra || ""}</div>${control && open ? `<div class="edit">${control}</div>` : ""}</div>`; };
    const where = kinds => {
      const idx = new Set(F.filter(f => kinds.includes(f.kind)).flatMap(f => (f.lis && f.lis.length ? f.lis : [f.li]).filter(x => x !== null && x !== undefined)));
      const ls = [...idx].sort((a, b) => a - b).map(x => J.lines[x]).filter(Boolean); if (!ls.length) return "";
      return `<details class="where"><summary>Where this came from: ${ls.length} line${ls.length === 1 ? "" : "s"} of your sources</summary><ul>${ls.map(l => `<li><b>${esc(l.from)}:</b> ${esc(l.text)}</li>`).join("")}</ul>${J.skipped.length ? `<p style="margin:8px 0 0"><b>Left out on purpose:</b> ${J.skipped.map(x => esc(x.what)).join(", ")}. You are introduced for what you can do.</p>` : ""}</details>`;
    };
    let h1, lead, body, hint = "", wh = "";
    if (sec === "general") {
      h1 = "Is this you?"; lead = `Read from ${esc(Object.keys(SRCNAME).filter(k => J.consent[k]).map(k => "your " + SRCNAME[k]).join(" and ") || "nothing yet")}, each line with its source. Everything is ticked for you: change or remove what is wrong.`;
      const group = t => `<div class="jgroup">${t}</div>`;
      const ms = F.filter(f => f.kind === "mode" || f.kind === "start"), mf = ms.length ? Object.assign({}, ms.find(f => f.from !== "You") || ms[0], { id: "modes", status: ms.some(f => f.status === "new") ? "new" : ms.some(f => f.status === "edited") ? "edited" : "ok" }) : null;
      body = group("Your work") + row(role, "Field", role ? esc(D.roles[role.value]) : "—", `<div class="opts">${Object.entries(D.roles).map(([r, t]) => `<span class="opt ${role && role.value === r ? "on" : ""}" data-act="jn-role" data-v="${r}">${esc(t)}</span>`).join("")}</div>`)
        + row(exp, "Experience", exp ? esc(D.exp[exp.value]) : "—", seg("jn-exp", D.exp.map((t, n) => [n, esc(t)]), exp ? exp.value : -1))
        + group("Tools and skills") + (skills.map(f => row(f, term(f.value), `${L.DEPTH[f.depth]}${f.years ? `, ${f.years} yr` : ""}`, `${seg("jn-depth", Object.entries(L.DEPTH).map(([v, t]) => [v, t]), f.depth, `data-id="${f.id}"`)} <label class="xs">years <input type="number" min="0" max="40" data-act="jn-years" data-id="${f.id}" value="${f.years || ""}" style="width:58px"></label>`, `<button class="quiet sm" data-act="jn-rm" data-id="${f.id}" title="Remove this skill">✕</button>`)).join("")
          || `<div class="jf"><div class="val">Tools and skills<small>none found yet</small></div></div>`)
        + `<div style="margin:10px 0 4px"><select data-act="jn-addskill"><option value="">+ add a tool or skill…</option>${D.skills.filter(sk => !skills.some(f => f.value === sk.id)).map(sk => `<option value="${sk.id}">${esc(sk.label)}</option>`).join("")}</select> ${(J.facts || []).some(f => f.status === "removed") ? `<button class="quiet sm" data-act="jn-undo">Undo last removal</button>` : ""}</div>`
        + group("Languages") + ["en", "fi", "sv"].map(k => row(langs[k], LANGNAME[k], langs[k] ? L.LVTXT[langs[k].level] : "not mentioned", seg("jn-lang", Object.entries(L.LVTXT).map(([v, t]) => [v, t]), langs[k] ? langs[k].level : "none", `data-id="${k}"`))).join("")
        + group("Practicalities") + row(mf, "Work", `${modes.map(m => L.MODE[m]).join(" or ") || "—"}${start ? `, ${L.START[start.value]}` : ""}`, `<div class="opts">${Object.entries(L.MODE).map(([m, t]) => `<span class="opt ${modes.includes(m) ? "on" : ""}" data-act="jn-mode" data-v="${m}">${t}</span>`).join("")}</div> ${seg("jn-start", Object.entries(L.START).map(([v, t]) => [v, t]), start ? start.value : "")}`)
        + row(null, "Type of work", `${J.types.map(v => L.TYPE[v]).join(", ") || "—"}${J.permit ? ", work-permit support needed" : ""}`, `<div class="opts">${Object.entries(L.TYPE).map(([v, t]) => `<span class="opt ${J.types.includes(v) ? "on" : ""}" data-act="jn-type" data-v="${v}">${esc(t)}</span>`).join("")}</div><label class="sm" style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-act="jn-permit" ${J.permit ? "checked" : ""}> I would need work-permit support <span class="mut xs">(optional; it never counts against you)</span></label>`, "", { key: "types", from: "Not read from any source: your choice." });
      hint = `${gathered.length} lines from your sources${edited ? `, ${edited} corrected by you` : ""}${removed ? `, ${removed} removed` : ""}. Nothing is used until you confirm.`;
      wh = where(["role", "exp", "skill", "lang", "mode", "start"]);
    } else if (sec === "event") {
      const Q = eventQuestions().qs.filter(q => q.on);
      h1 = "Questions for this event"; lead = `The ${D.companies.length} companies coming to ${esc(D.event.name)} said what they look for. These questions come from their answers, chosen by Espoo's organiser. Where your sources already answer one, it is filled in.`;
      const ctl = q => {
        const a = evAnswer(J, q);
        if (q.kind === "skills") return `<div class="opts">${q.opts.map(o => `<span class="opt ${a.includes(o.v) ? "on" : ""}" data-act="jn-evskill" data-v="${o.v}" title="Asked for by ${esc(o.who.join(", "))}">${esc(L.skillLabel(o.v))}</span>`).join("")}</div><div class="xs mut" style="margin-top:6px">Hover one to see which companies ask for it.</div>`;
        if (q.kind === "lang") return seg("jn-lang", Object.entries(L.LVTXT).map(([v, t]) => [v, t]), a, `data-id="${q.lang}"`);
        if (q.kind === "ynl") return seg("jn-ans", Object.entries(YNL), a, `data-id="${q.id}"`);
        if (q.kind === "trade") return seg("jn-trade", [["a", esc(q.a)], ["b", esc(q.b)]], a, `data-t="${q.t}"`);
        if (q.kind === "wants") return `<div class="opts">${D.companies.map(c => `<span class="opt ${a.includes(c.id) ? "on" : ""}" data-act="jn-want" data-v="${c.id}">${esc(c.name)}</span>`).join("")}</div>`;
        return `<input type="text" data-act="jn-anstext" data-id="${q.id}" value="${esc(a)}" placeholder="Your answer" style="width:100%">`;
      };
      body = Q.map(q => `<div class="evq"><div class="q">${esc(q.text)}</div><div class="asked">${esc(q.why)}</div>${ctl(q)}${evPrefilled(J, q) ? `<div class="pre">✓ Filled in from your sources. Change it if it is wrong.</div>` : ""}</div>`).join("")
        || `<p class="note">The organiser has switched every question off for this event.</p>`;
      const open = Q.filter(q => { const a = evAnswer(J, q); return Array.isArray(a) ? !a.length : !a; }).length;
      hint = open ? `${open} question${open === 1 ? "" : "s"} still open. You can skip them for now.` : "All answered.";
      hint += ` <span class="mut">Organiser: <a href="#/org/questions">edit these questions</a>.</span>`;
      wh = where(["skill", "lang"]);
    } else if (sec === "you") {
      h1 = "In your own words"; lead = "No document can tell this. What you write here is shown to the organiser exactly as you write it, marked as yours.";
      body = `<div class="own"><label class="sm" style="font-weight:600">What should companies know about you that no document shows?</label><textarea data-act="jn-own" data-v="about" placeholder="e.g. I like being the person who explains the numbers to people who hate numbers.">${esc(J.own.about)}</textarea>
        <label class="sm" style="display:block;margin-top:12px;font-weight:600">What are you looking for next?</label><textarea data-act="jn-own" data-v="looking" placeholder="e.g. A team where I can grow from reporting into forecasting." style="min-height:64px">${esc(J.own.looking)}</textarea></div>`;
      hint = "Optional, and often the most useful part for the organiser.";
    } else {
      const Q = eventQuestions().qs.filter(q => q.on && (q.kind === "ynl" || q.kind === "text")), wants = J.wants || me.wants || [];
      const sum = (k, v) => `<div class="sumrow"><span>${k}</span><span>${v}</span></div>`;
      h1 = J.done ? "Confirmed, and all yours." : "Confirm: this is me"; lead = J.done ? `Checked by you on ${esc(fmtTime(J.done))}. You can change it until the event.` : "This is what Espoo's organiser will see, marked “checked by the candidate”. Nothing is used before you confirm.";
      body = sum("Field", role ? esc(D.roles[role.value]) : "—") + sum("Experience", exp ? esc(D.exp[exp.value]) : "—")
        + sum("Tools and skills", skills.map(f => `${esc(L.skillLabel(f.value))} <span class="mut">(${L.DEPTH[f.depth]}${f.years ? `, ${f.years} yr` : ""})</span>`).join(", ") || "—")
        + sum("Languages", ["en", "fi", "sv"].filter(k => langs[k]).map(k => `${LANGNAME[k]} ${L.LVTXT[langs[k].level]}`).join(", ") || "—")
        + sum("Work", `${modes.map(m => L.MODE[m]).join(" or ") || "—"}${start ? `, ${L.START[start.value]}` : ""}; ${J.types.map(v => L.TYPE[v]).join(", ")}${J.permit ? "; work-permit support needed" : ""}`)
        + sum("Would like to meet", wants.map(id => esc(CO[id] ? CO[id].name : id)).join(", ") || "no preference")
        + (J.consent.project && (J.project || J.ids.project) ? sum("Work sample", `${esc(J.project ? J.project.name : J.ids.project)} <span class="mut">shared with organisers, in your words</span>`) : "")
        + Q.map(q => { const a = evAnswer(J, q); return a ? sum(esc(q.text), esc(q.kind === "ynl" ? YNL[a] : a)) : ""; }).join("")
        + (J.own.about || J.own.looking ? sum("In your words", `<span class="own-q">${esc(J.own.about)}${J.own.looking ? ` <span class="mut">Looking for:</span> ${esc(J.own.looking)}` : ""}</span>`) : "")
        + (J.done ? `<div class="okbox" style="margin-top:16px"><b>Confirmed.</b> ${F.length} lines, checked by you. <a href="#/join/done">What happens next →</a></div>`
          : `<div style="margin-top:18px"><button style="width:100%;min-height:3rem;font-size:1.0625rem" data-act="jn-confirm">${kindOf(J).confirm}</button>
             <p class="jhint" style="text-align:center">${gathered.length} lines from your sources${edited ? `, ${edited} corrected by you` : ""}${removed ? `, ${removed} removed` : ""}.</p></div>`);
    }
    app.innerHTML = `<div class="wiz join">
      <p class="eyebrow">${esc(D.event.name)} · ${esc(firstName())}'s ${kindOf(J).eyebrow}</p>
      ${steps}
      <div class="jcard"><h1>${h1}</h1><p class="lead">${lead}</p>${body}${sec === "confirm" ? `<div class="jnav"><a class="back" href="#/join/check/${prev[0]}">← ${prev[1]}</a>${J.done ? `<a href="#/join/done"><button>Done →</button></a>` : ""}</div>` : nav(hint)}</div>
      ${wh}
      <div class="livemini"><b>${stands}</b> of ${D.companies.length} stands look for something you have confirmed. <span class="mut">Grows as you tick lines; nobody is ranked, and you can visit any stand.</span></div>
    </div>`;
  }
  function joinDone(J) {
    const F = (J.facts || []).filter(f => f.status !== "removed"), edited = F.filter(f => f.status === "edited").length;
    const K = kindOf(J);
    app.innerHTML = `<div class="wiz join"><p class="eyebrow">${esc(D.event.name)} · ${esc(D.event.date)}</p><h1>${K.doneH1()}</h1>
      <p class="mut" style="font-size:1.0625rem;max-width:60ch">${K.doneLead(esc(fmtTime(J.done)))}</p>
      <div class="jcard">
        <div class="sumrow"><span>${K.first[0]}</span><span><b>${K.first[1]}</b><br><span class="mut">${F.length} ${K.first[2]}${edited ? `, ${edited} corrected` : ""}. ${K.first[3]}</span></span></div>
        <div class="sumrow"><span>Before the event</span><span><b>A named organiser picks introductions, with a reason</b><br><span class="mut">No scores, no ranking. You see every planned conversation with the organiser's note.</span></span></div>
        <div class="sumrow"><span>${esc(D.event.date)}</span><span><b>Short 1:1 conversations at the stands</b><br><span class="mut">And you can still visit any stand you like.</span></span></div>
        <div class="jnav"><a class="back" href="#/join/check/general">← Change my answers</a><a href="#/cand/me"><button>How organisers see you →</button></a></div>
      </div></div>`;
  }
  function joinApply(J) {
    const F = (J.facts || []).filter(f => f.status !== "removed"), me = cand(ME), patch = {};
    const roles = F.filter(f => f.kind === "role").map(f => f.value); if (roles.length) patch.roles = roles.slice(0, 2);
    const ex = F.find(f => f.kind === "exp"); if (ex) patch.exp = +ex.value;
    const skills = F.filter(f => f.kind === "skill").map(f => ({ id: f.value, depth: f.depth, years: f.years || undefined, example: f.example || undefined })); if (skills.length) patch.skills = skills;
    const langs = { en: "none", fi: "none", sv: "none" }; F.filter(f => f.kind === "lang").forEach(f => langs[f.value] = f.level); patch.langs = langs;
    const modes = F.filter(f => f.kind === "mode").map(f => f.value); if (modes.length) patch.mode = modes;
    const stf = F.find(f => f.kind === "start"); if (stf) patch.start = stf.value;
    patch.types = J.types.length ? J.types : ["full"]; patch.permit = !!J.permit; patch.tradeoffs = Object.assign({}, me.tradeoffs, J.trade); patch.own = { about: J.own.about.trim(), looking: J.own.looking.trim() };
    if (J.wants) patch.wants = J.wants;
    if (J.consent.project && (J.project || J.ids.project)) { const sk = F.find(f => f.kind === "skill"); patch.evidence = { skill: sk ? sk.value : "analytics", link: J.project ? J.project.name : J.ids.project, summary: `Project shared by the candidate: ${J.project ? J.project.name : J.ids.project}. ${J.own.about ? "" : "Summarised by the candidate before the event."}`.trim(), status: "approved" }; }
    patch.eventAnswers = eventQuestions().qs.filter(q => q.on && (q.kind === "ynl" || q.kind === "text")).map(q => ({ q: q.text, a: evAnswer(J, q) })).filter(x => x.a).map(x => ({ q: x.q, a: YNL[x.a] || x.a }));
    const edited = F.filter(f => f.status === "edited").length, removed = (J.facts || []).length - F.length;
    patch.verified = { at: new Date().toISOString(), n: F.length, edited };
    setMe(patch);
    (S.corr[ME] = S.corr[ME] || []).push({ at: patch.verified.at, what: `Checked all ${F.length} gathered lines${edited ? `, corrected ${edited}` : ""}${removed ? `, removed ${removed}` : ""}` });
    J.done = patch.verified.at; save();
  }
  function joinAction(a, t, v) {
    const J = joinState(), id = t.dataset.id, f = (J.facts || []).find(x => x.id === id);
    if (a === "jn-consent") { J.consent[v] = t.checked; save(); return route(); }
    if (a === "jn-scan") { joinScan(J); J.done = null; save(); return jGo("reading"); }
    if (a === "jn-go") return jGo(v);
    if (a === "jn-project-rm") { J.project = null; save(); return route(); }
    if (a === "jn-edit") { (J.open = J.open || {})[id] = !isOpenJ(J, id); save(); return route(); }
    if (a === "jn-rm") { f.status = "removed"; J.lastRemoved = f.id; save(); return route(); }
    if (a === "jn-undo") { const r = (J.facts || []).find(x => x.id === J.lastRemoved); if (r) r.status = "ok"; J.lastRemoved = null; save(); return route(); }
    if (a === "jn-role") { jSet(J, "role", v, { value: v }); return route(); }
    if (a === "jn-exp") { jSet(J, "exp", +v, { value: +v }); return route(); }
    if (a === "jn-depth") { jSet(J, "skill", f.value, { depth: v }); return route(); }
    if (a === "jn-lang") { jSet(J, "lang", id, { level: v }); return route(); }
    if (a === "jn-mode") { const m = jFact(J, "mode", v); if (m) { m.status = "removed"; save(); } else jSet(J, "mode", v, {}); return route(); }
    if (a === "jn-start") { jSet(J, "start", v, { value: v }); return route(); }
    if (a === "jn-trade") { J.trade[t.dataset.t] = v; save(); return route(); }
    if (a === "jn-type") { J.types = J.types.includes(v) ? J.types.filter(x => x !== v) : J.types.concat(v); save(); return route(); }
    if (a === "jn-evskill") { const m = jFact(J, "skill", v); if (m) { m.status = "removed"; J.lastRemoved = m.id; save(); } else jSet(J, "skill", v, { depth: "work", years: null }); return route(); }
    if (a === "jn-ans") { J.ans[id] = v; save(); return route(); }
    if (a === "jn-want") { const w = J.wants || (cand(ME).wants || []).slice(); J.wants = w.includes(v) ? w.filter(x => x !== v) : w.concat(v); save(); return route(); }
    if (a === "jn-confirm") { joinApply(J); jGo("done"); return toast(kindOf(J).confirmed); }
  }
  function joinChange(t) {
    const J = joinState(), a = t.dataset.act, id = t.dataset.id, f = (J.facts || []).find(x => x.id === id);
    if (a === "jn-consent") return joinAction(a, t, t.dataset.v);
    if (a === "jn-permit") { J.permit = t.checked; save(); return; }
    if (a === "jn-srcid") { J.ids[t.dataset.v] = t.value.trim(); save(); return; }
    if (a === "jn-project") { const f = t.files && t.files[0]; if (!f) return; J.project = { name: f.name, size: f.size }; J.consent.project = true; save(); return route(); } // the file itself never leaves the browser
    if (a === "jn-own") { J.own[t.dataset.v] = t.value; save(); return; }
    if (a === "jn-anstext") { J.ans[id] = t.value.trim(); save(); return; }
    if (a === "jn-years") { jSet(J, "skill", f.value, { years: +t.value || null }); return route(); }
    if (a === "jn-addskill" && t.value) { jSet(J, "skill", t.value, { depth: "work", years: null, example: null }); return route(); }
  }

  // ---------------------------------------------------------------- organiser: the event's questions to applicants
  function viewQuestions() {
    const E = eventQuestions(), P = profiles();
    app.innerHTML = `<div class="wiz"><p class="eyebrow mut" style="font-weight:700;font-size:.875rem">Organiser · ${esc(D.event.name)}</p><h1>Questions for this event</h1>
      <p class="mut" style="font-size:1.0625rem;max-width:62ch">Applicants see these on the second page of their invitation, after their general information. They are suggested from what the ${P.length} attending companies said they need (${P.filter(p => p.confirmed).length} confirmed, the rest drafted from their job ads). Change the wording, switch any off, or add your own.</p>
      <div class="jcard">
        ${E.qs.map((q, i) => `<div class="qedit ${q.on ? "" : "off"}"><input type="checkbox" data-act="qe-on" data-i="${i}" ${q.on ? "checked" : ""} title="Ask this question" style="margin-top:10px"><div><input type="text" data-act="qe-text" data-i="${i}" value="${esc(q.text)}" aria-label="Question text"><div class="why"><span class="kind">${QKIND[q.kind]}</span> · ${esc(q.why)}${q.kind === "skills" ? ": " + q.opts.map(o => esc(L.skillLabel(o.v))).join(", ") : ""}</div></div>${q.kind === "text" ? `<button class="quiet sm" data-act="qe-rm" data-i="${i}">Remove</button>` : "<span></span>"}</div>`).join("")}
        <div class="row" style="margin-top:14px;flex-wrap:wrap;align-items:center;gap:8px"><input type="text" id="qe-new" placeholder="Add your own question (free-text answer)" style="flex:1;min-width:240px"><button class="quiet" data-act="qe-add">Add</button><button class="quiet" data-act="qe-reset" title="Back to the questions suggested from the companies' needs">Reset to suggested</button></div>
        <div class="jnav"><a class="back" href="#/org/puro">← Organiser list</a><a href="#/join/check/event"><button>Preview as an applicant →</button></a></div>
      </div></div>`;
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
      <p class="mut">This is exactly the information Espoo's organisers use to suggest introductions. It comes only from what you confirmed${me.verified ? ` (checked by you on ${esc(fmtTime(me.verified.at))})` : ""}. If anything is wrong or unfair, correct it: corrections are logged and organisers see that you checked.</p>
      <div class="card">
        ${line("Field", me.roles.map(r => esc(D.roles[r])).join("; "), `<button class="ghost sm" data-act="goto" data-v="1">Correct</button>`)}
        ${line("Experience in that field", esc(D.exp[me.exp]) + (me.careerChange ? ` · moving into tech from ${esc(me.careerChange)}` : ""), `<button class="ghost sm" data-act="goto" data-v="1">Correct</button>`)}
        ${me.skills.map((s, i) => line(`Skill: ${term(s.id)}`, esc(L.DEPTH[s.depth] + (s.years ? `, ${s.years} yr` : "")) + (s.example ? `<div class="sm mut">“${esc(s.example)}”</div>` : ""),
          `<select data-act="medepth" data-i="${i}">${Object.entries(L.DEPTH).map(([v, t]) => `<option value="${v}" ${s.depth === v ? "selected" : ""}>${t}</option>`).join("")}<option value="remove">remove this skill</option></select>`)).join("")}
        ${line("Working languages", `English ${esc(L.LVTXT[me.langs.en])} · Finnish ${esc(L.LVTXT[me.langs.fi])} · Swedish ${esc(L.LVTXT[me.langs.sv])}`, `<button class="ghost sm" data-act="goto" data-v="3">Correct</button>`)}
        ${line("Practicalities", `${me.mode.map(m => L.MODE[m]).join(" / ")} · ${me.types.map(t => L.TYPE[t]).join(", ")} · start ${esc(L.START[me.start])}${me.permit ? " · would need work-permit support" : ""}`, `<button class="ghost sm" data-act="goto" data-v="4">Correct</button>`)}
        ${line("Work style", D.tradeoffs.map(t => esc(me.tradeoffs[t.id] === "a" ? t.a : t.b)).join(" · "), `<button class="ghost sm" data-act="goto" data-v="5">Correct</button>`)}
        ${me.own && (me.own.about || me.own.looking) ? line("In your own words", `${esc(me.own.about || "")}${me.own.looking ? `<div class="sm mut">Looking for: ${esc(me.own.looking)}</div>` : ""}`, `<a href="#/join"><button class="ghost sm">Edit</button></a>`) : ""}
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
    if (a.startsWith("jn-") && !["jn-consent", "jn-permit", "jn-own", "jn-addskill", "jn-years", "jn-anstext", "jn-srcid", "jn-project"].includes(a)) return joinAction(a, t, v);
    if (a === "qe-add") { const inp = document.getElementById("qe-new"), txt = inp.value.trim(); if (!txt) { inp.focus(); return toast("Write the question first."); } eventQuestions().qs.push({ id: "q" + Date.now(), kind: "text", on: true, text: txt, why: "Added by the organiser" }); save(); return route(); }
    if (a === "qe-rm") { eventQuestions().qs.splice(+t.dataset.i, 1); save(); return route(); }
    if (a === "qe-reset") { S.evq = null; eventQuestions(); toast("Back to the suggested questions."); return route(); }
    if (a === "rq") { (ui.rq = ui.rq || {})[co] = v; save(); return route(); }
    if (a === "rq-skip") { const ids = [...document.querySelectorAll(".qrow:not(.done)")].map(e => e.dataset.v); const i = ids.indexOf(t.dataset.id); (ui.rq = ui.rq || {})[co] = ids[(i + 1) % ids.length] || null; save(); return route(); }
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
      (S.dec[co] = S.dec[co] || {})[t.dataset.id] = { d: pick, reason, at: new Date().toISOString(), by: ORGANISER }; if (ui.rq && ui.rq[co] === t.dataset.id) ui.rq[co] = null; save(); route();
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
    const jt = ev.target.closest("[data-act]"); if (jt && jt.dataset.act.startsWith("jn-")) return joinChange(jt);
    if (jt && jt.dataset.act === "pickrev") { location.hash = "#/org/" + jt.value + "/review"; return; }
    if (jt && jt.dataset.act === "qe-on") { eventQuestions().qs[+jt.dataset.i].on = jt.checked; save(); return route(); }
    if (jt && jt.dataset.act === "qe-text") { eventQuestions().qs[+jt.dataset.i].text = jt.value.trim() || eventQuestions().qs[+jt.dataset.i].text; save(); return; }
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

  // ---------------------------------------------------------------- demo control panel
  const goTo = h => { if (location.hash === h) route(); else location.hash = h; };
  document.addEventListener("click", ev => { const d = document.getElementById("demo"); if (d && d.open && !d.contains(ev.target)) d.open = false; });
  document.getElementById("demo").addEventListener("click", ev => {
    if (ev.target.closest("a[href]")) { document.getElementById("demo").open = false; const h = ev.target.closest("a[href]").getAttribute("href"); if (location.hash === h) route(); return; } // a plain link in the menu: close it, and re-render when already there
    const b = ev.target.closest("[data-dbg]"); if (!b) return; const k = b.dataset.dbg, now = new Date().toISOString();
    document.getElementById("demo").open = false;
    if (k === "reset") { S = seed(); save(); toast("Demo reset"); return goTo("#/"); }
    if (k === "co-draft") { delete S.comp.puro; save(); return goTo("#/company/puro"); }
    if (k === "co-ok") { S.comp.puro = { finnish: "helpful", confirmedAt: now }; save(); return goTo("#/company/puro"); }
    if (k === "jn-0") { S.join = null; joinState(); save(); return goTo("#/join/golden"); }
    if (k === "jn-reg") { S.join = null; joinState(); save(); return goTo("#/join"); }
    if (k === "jn-2") { S.join = null; const J = joinState(); joinScan(J); save(); return goTo("#/join/check/general"); }
    if (k === "jn-done") { S.join = null; const J = joinState(); J.kind = "golden"; joinScan(J); J.trade = { build: "b", depth: "a", pace: "b" }; J.own = { about: "I like being the person who explains the numbers to people who hate numbers.", looking: "A team where I can grow from reporting into forecasting." }; joinApply(J); return goTo("#/join/done"); }
    if (k === "org-questions") return goTo("#/org/questions");
    if (k === "org-puro") { S.ui.open = {}; S.ui.f = {}; if (S.dec.puro) delete S.dec.puro[ME]; save(); return goTo("#/org/puro"); }
    if (k === "org-intro") { (S.dec.puro = S.dec.puro || {})[ME] = { d: "introduce", reason: "Power BI and SQL at work for 4–5 years; their exact stack. Finnish only helpful.", at: now, by: ORGANISER }; S.ui.open["puro" + ME] = true; save(); return goTo("#/org/puro"); }
    if (k === "org-lahde") return goTo("#/org/lahde");
    if (k === "org-review") { S.ui.rq = {}; if (S.dec.puro) delete S.dec.puro[ME]; save(); return goTo("#/org/puro/review"); }
    if (k === "event") return goTo("#/event");
    if (k === "after") return goTo("#/after");
  });
})();
