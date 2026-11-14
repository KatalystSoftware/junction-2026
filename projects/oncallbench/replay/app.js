// On-call shift replay: two runs of one seeded episode, minute by minute. No dependencies.
// Data comes from export.py: data/index.js names the bundles, each one episode (see README.md).
"use strict";
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const RATE = 4; // simulated minutes per second at 1x: the whole shift in half a minute
  const $ = (q, root = document) => root.querySelector(q);

  function make(create, tag, props, kids) {
    const e = create(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    e.append(...kids.flat().filter((k) => k != null && k !== false));
    return e;
  }
  const h = (tag, props, ...kids) => make((t) => document.createElement(t), tag, props, kids);
  const s = (tag, props, ...kids) => make((t) => document.createElementNS(NS, t), tag, props, kids);

  const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const usd = (n) => (n < 0 ? "−$" : "$") + whole.format(Math.abs(n));
  const pct = (x) => (x < 0.0995 ? (x * 100).toFixed(1) : Math.round(x * 100)) + "%";
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  let remPx = 0;  // asked of the browser once per size of the window: asking forces a style pass
  const rem = () => remPx || (remPx = parseFloat(getComputedStyle(document.documentElement).fontSize));
  addEventListener("resize", () => (remPx = 0));

  // --- data ------------------------------------------------------------------------

  // data/index.js lists the bundles, newest level first; the first episode is the one that opens
  const sessions = [];
  function loadBundles() {
    const files = window.REPLAY_FILES || [], query = new URLSearchParams(location.search);
    const fetched = (file) => new Promise((done) => document.head.append(h("script", { src: `data/${file}`, onload: done, onerror: done })));
    const take = () => {
      for (const bundle of window.REPLAY_BUNDLES || []) {
        for (const ses of bundle.sessions) if (!sessions.includes(ses)) sessions.push(Object.assign(ses, { key: ses.id }));
      }
      sessions.sort((a, b) => files.indexOf(`${a.id}.js`) - files.indexOf(`${b.id}.js`));
    };
    // the episode that opens is enough to start with; the rest arrive behind it, unless the address asks for one
    const all = ["session", "seed", "level"].some((k) => query.has(k)) || files.length < 2;
    const later = all ? [] : files.slice(1);
    return Promise.all((all ? files : files.slice(0, 1)).map(fetched)).then(() => {
      take();
      Promise.all(later.map(fetched)).then(() => { if (later.length) { take(); if (state.ses) renderBar(); } });
    });
  }

  function prep(ses) {
    if (ses.ready) return;
    ses.ready = true;
    for (const run of ses.runs) {
      run.cum = [0];
      run.cumExtra = [0];
      for (let t = 0; t < ses.horizon; t++) {
        run.cum.push(run.cum[t] + run.loss[t + ses.pre]);
        run.cumExtra.push(run.cumExtra[t] + run.extra[t + ses.pre]);
      }
      run.errAt = run.err.map((rows) => new Map(rows.map(([i, e, own]) => [i, [e / 1e4, own / 1e4]])));
      run.hotAt = run.hot.map((list) => new Set(list));
      run.actions.forEach((a, i) => (a.i = i));
      run.mit = run.actions.filter((a) => a.kind === "mitigation");
      // level 4 and later: what the run throttled, and where retries alone kept a service over capacity
      run.throttles = run.throttles || [];
      run.stormAt = (run.storm || []).map((list) => new Set(list));
      run.stormSpans = new Map();
      run.stormAt.forEach((set, k) => {
        for (const i of set) {
          const spans = run.stormSpans.get(i) || run.stormSpans.set(i, []).get(i), m = k - ses.pre;
          if (spans.length && spans[spans.length - 1][1] === m) spans[spans.length - 1][1] = m + 1;
          else spans.push([m, m + 1]);
        }
      });
      // two moments per fault. `cleared`: the fault is removed. `clear`: the service is clear, that is
      // the retry storm the fault left behind has drained and every throttle on it is lifted
      run.faults.forEach((f, k) => {
        const svc = ses.faults[k].service;
        f.after = [];  // storm minutes on the service that the fault itself does not cover
        for (const [a, b] of run.stormSpans.get(svc) || []) {
          for (let m = a; m < b; m++) {
            if (liveAt(f.live, m)) continue;
            if (f.after.length && f.after[f.after.length - 1][1] === m) f.after[f.after.length - 1][1] = m + 1;
            else f.after.push([m, m + 1]);
          }
        }
        f.held = run.throttles.filter((t) => t.service === svc).map((t) => t.span);
        const ends = [f.cleared, ...f.after.map((sp) => sp[1]), ...f.held.map((sp) => sp[1])];
        f.clear = ends.some((e) => e == null || e >= ses.horizon) ? null : Math.max(...ends);
      });
      // the minutes on which something happens in this run: an action starts or lands, a throttle goes on
      // or off, a fault or a storm begins or ends. Values are never eased across one of these.
      run.events = new Set(ses.decoy ? [ses.decoy.start, ses.decoy.end] : []);
      for (const a of run.actions) {
        if (a.kind === "mitigation") run.events.add(a.t0).add(a.lands);
        if (a.kind === "throttle") run.events.add(a.span[0]).add(a.span[1]);
      }
      for (const f of run.faults) for (const [a, b] of [...f.live, ...f.after]) run.events.add(a).add(b);
      for (const list of run.stormSpans.values()) for (const [a, b] of list) run.events.add(a).add(b);
    }
  }

  // Between two simulated minutes the picture glides while it plays; the data stays per minute.
  // `at(m)` is a value in minute m. Paused, or with motion reduced, the value of the minute is shown as it is.
  // Playing, it moves evenly toward the next minute's value, unless something happens on that minute:
  // then it holds, and the new value eases in once the minute has come (about 0.3 seconds), never before.
  const calm = (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)
    || new URLSearchParams(location.search).has("still");
  const gliding = () => state.playing && !calm;
  function glide(ses, run, T, at) {
    const m = clamp(Math.floor(T), -ses.pre, ses.horizon - 1), v = at(m);
    if (!gliding()) return v;
    const part = clamp(T - m, 0, 1);
    let shown = m + 1 < ses.horizon && !run.events.has(m + 1) ? v + (at(m + 1) - v) * part : v;
    const ease = clamp(0.3 * RATE * state.speed, 0.12, 0.8);
    if (state.entered === m && run.events.has(m) && part < ease && m > -ses.pre) {
      const from = at(m - 1);
      shown = from + (shown - from) * (1 - (1 - part / ease) ** 3);
    }
    return shown;
  }

  // the timeline's wording for the two moments; the graph says "clear since" for the same minute
  function endOf(ses, f) {
    if (f.cleared == null) return "fault never removed";
    if (f.clear == null) return `fault removed ${f.cleared}, never clear`;
    if (f.clear !== f.cleared) return `fault removed ${f.cleared}, clear ${f.clear}`;
    return ses.rules.storms ? `fault removed and clear ${f.cleared}` : `fault removed ${f.cleared}`;
  }

  const throttleAt = (run, i, m) => run.throttles.find((x) => x.service === i && x.span[0] <= m && m < x.span[1]);
  const stormAt = (run, i, m) => (run.stormSpans.get(i) || []).find(([a, b]) => a <= m && m < b);

  function costAt(ses, run, T) {
    const t = clamp(T, 0, ses.horizon), k = Math.floor(t), part = t - k;
    let wasted = 0;
    if (T >= 0) for (const a of run.mit) if (a.t0 <= T) wasted += a.wasted;
    const outage = run.cum[k] + part * (run.loss[k + ses.pre] || 0);
    const replicas = run.cumExtra[k] + part * (run.extra[k + ses.pre] || 0);
    if (T >= ses.horizon) return run.cost;  // the settled cost, to the cent
    return { outage, replicas, wasted, total: outage + replicas + wasted };
  }

  const liveAt = (spans, m) => spans.some(([a, b]) => a <= m && m < b);
  const faultOn = (ses, run, i, m) => ses.faults.findIndex((f, k) => f.service === i && liveAt(run.faults[k].live, m));

  function latest(run, m, pick = () => true) {
    let found = null;
    for (const a of run.actions) {
      if (a.t0 > m) break;
      if (pick(a)) found = a;
    }
    return found;
  }

  const VERB = {
    get_topology: () => "reads the topology",
    list_alerts: (a) => (a.args.tier ? `reads the ${a.args.tier} alerts` : "reads the alerts"),
    get_metrics: (a) => `reads the metrics of ${a.args.service}`,
    get_logs: (a) => `reads the logs of ${a.args.service}`,
    get_changes: (a) => `lists the changes on ${a.args.service}`,
    get_diff: (a) => `reads the diff of ${a.args.change_id} on ${a.args.service}`,
    rollback: (a) => `rolls back ${a.args.service}`,
    revert_config: (a) => `reverts the config of ${a.args.service}`,
    restart: (a) => `restarts ${a.args.service}`,
    scale: (a) => `scales ${a.args.service} to ${a.args.replicas} replicas`,
    failover: (a) => `fails over ${a.args.service}`,
    throttle: (a) => (a.args.percent ? `throttles ${a.args.service} by ${a.args.percent}%` : `lifts the throttle on ${a.args.service}`),
    wait: (a) => `waits ${a.args.minutes} min`,
    finish: () => "ends the shift",
  };
  const verb = (a) => (VERB[a.tool] ? VERB[a.tool](a) : a.tool);
  const TOOL_NAME = { rollback: "rollback", revert_config: "config revert", restart: "restart", scale: "scale", failover: "failover" };

  // --- state -----------------------------------------------------------------------

  const params = new URLSearchParams(location.search);
  const state = { ses: null, run: null, ref: null, T: -12, playing: true, speed: 1, pin: null, lanes: false };
  const panels = {};
  let track = null;

  function chooseSession(id) {
    state.ses = sessions.find((x) => x.key === id) || sessions.find((x) => x.id === id) || sessions[0];
    prep(state.ses);
    state.ref = state.ses.runs.find((r) => r.id === "reference");
    const wanted = params.get("run");
    const others = state.ses.runs.filter((r) => r !== state.ref);
    state.run =
      others.find((r) => r.id === wanted) ||
      others.find((r) => r.kind === "trial" && /opus/i.test(r.id)) ||
      others.find((r) => r.kind === "trial") ||
      others[0] ||
      state.ref;
  }

  // --- the scores band: every run of each model on the pre-registered seeds -----------------
  // Scores only, so it is safe for any seed. A dot per run, the mean as a tick with its 95% interval as a bar,
  // the reference's 1.00 and doing nothing's 0.00 as the two walls. ?spread=0 leaves it out.

  function renderSpread() {
    const data = window.REPLAY_SPREAD, box = $("#spread");
    if (!data || !data.models.length || params.get("spread") === "0") return;
    const at = (v) => `${(Math.max(0, Math.min(1, v)) * 100).toFixed(2)}%`, two = (v) => v.toFixed(2);
    const rows = data.models.length;
    const how = `Level ${data.level}, seeds ${data.seeds.join(", ")}, ${data.source}. The mean counts each seed once; `
      + `its 95% interval is over the seed means (Student's t), because runs on one seed share its outage.`;
    box.replaceChildren(...[
      h("p", { class: "spread-caption", style: "grid-row: 1" }, data.caption,
        data.placeholder ? h("b", { class: "placeholder", text: "Placeholder data, not results" }) : null),
      h("p", { class: "spread-head", style: "grid-row: 1", title: how, text: "mean ± 95% CI" }),
      h("div", { class: "spread-walls", style: `grid-row: 2 / span ${rows}`, "aria-hidden": "true" },
        [0.25, 0.5, 0.75].map((v) => h("i", { class: "grid", style: `left: ${at(v)}` })),
        h("i", { class: "floor", style: "left: 0%" }), h("i", { class: "ceiling", style: "left: 100%" })),
      data.models.map((m, i) => [
        h("p", { class: "spread-name", style: `grid-row: ${i + 2}`, text: m.label }),
        h("div", { class: "spread-lane", style: `grid-row: ${i + 2}`, role: "img",
            "aria-label": `${m.label}, ${m.n} runs: ${m.runs.map((r) => two(r.score)).join(", ")}` },
          m.half != null ? h("i", { class: "ci", style: `left: ${at(m.mean - m.half)}; right: calc(100% - ${at(m.mean + m.half)})` }) : null,
          m.runs.map((r) => h("i", { class: "dot", style: `left: ${at(r.score)}; top: calc(50% + ${(r.k % 3) - 1} * 0.32rem)`,
            title: `Seed ${r.seed}: ${two(r.score)}` })),
          h("i", { class: "mean", style: `left: ${at(m.mean)}` })),
        h("p", { class: "spread-stat", style: `grid-row: ${i + 2}`, title: how },
          h("b", { text: m.half != null ? `${two(m.mean)} ± ${two(m.half)}` : two(m.mean) }),
          h("span", { text: `${m.n} run${m.n === 1 ? "" : "s"}, ${m.seeds} seed${m.seeds === 1 ? "" : "s"}` })),
      ]),
      h("div", { class: "spread-axis", style: `grid-row: ${rows + 2}`, "aria-hidden": "true" },
        h("span", { class: "start", style: "left: 0%" }, h("b", { text: "0.00" }), " doing nothing"),
        [0.25, 0.5, 0.75].map((v) => h("span", { style: `left: ${at(v)}`, text: two(v) })),
        h("span", { class: "end", style: "left: 100%" }, "the reference ", h("b", { text: "1.00" }))),
    ].flat(2).filter(Boolean));
    box.hidden = false;
  }

  // --- the bar ---------------------------------------------------------------------

  function renderBar() {
    const ses = state.ses;
    const go = (key) => { chooseSession(key); state.pin = null; state.T = -12; setPlaying(true); renderAll(); };
    const few = sessions.length <= 3;
    $("#episode").setAttribute("role", few ? "tablist" : "group");
    $("#episode").replaceChildren(...(few
      ? sessions.map((x) => h("button", { type: "button", role: "tab", "aria-selected": String(x === ses), title: `Seed ${x.seed}`, onclick: () => go(x.key), text: x.title }))
      : [h("select", { "aria-label": "Episode", onchange: (e) => go(e.target.value) },
          sessions.map((x) => h("option", { value: x.key, selected: x === ses, text: `${x.title}, seed ${x.seed}` })))]));
    document.body.classList.toggle("storms", !!ses.rules.storms);
    const runs = ses.runs.filter((r) => r !== state.ref);
    const pick = (id) => { state.run = runs.find((r) => r.id === id); state.pin = null; renderAll(); };
    const name = (r) => {  // a model with two runs: the second is "run 2"
      const same = runs.filter((x) => x.label === r.label);
      return same.indexOf(r) > 0 ? `${r.label} run ${same.indexOf(r) + 1}` : r.label;
    };
    for (const r of runs) r.name = name(r);
    // one picker for the run on the left: models first, then the scripted baselines that calibrate the score
    const groups = [["Models", runs.filter((r) => r.kind === "trial")], ["Scripted baselines", runs.filter((r) => r.kind !== "trial")]].filter((g) => g[1].length);
    $("#runs").replaceChildren(h("label", {}, "Run ",
      h("select", { "aria-label": "Run to compare with the reference", onchange: (e) => pick(e.target.value) },
        groups.map(([title, list]) => h("optgroup", { label: title },
          list.map((r) => h("option", { value: r.id, selected: r === state.run, text: `${name(r)}: ${r.score.toFixed(2)}` })))))));
    $("#runbook-lines").replaceChildren(...(ses.runbook || []).map(([verb, rest]) => h("li", {}, h("span", {}, h("b", { text: verb }), ` ${rest}`))));
    renderResults();
    $("#key-score").textContent = `Score: the share of the avoidable cost a run avoids. Doing nothing (${usd(ses.cost_null)} lost) is 0, the reference (${usd(ses.cost_ref)}) is 1.`;
  }

  // every measured run of the level in one strip: dots on a 0 to 1 score axis, the mean marked
  const HOW = {
    unprotected: "rolled back the quiet fault's service without adding capacity first",
    protected: "added capacity first, wasted nothing",
    wasted: "added capacity first, but rolled back an innocent caller",
    "never fixed": "never fixed the quiet fault",
  };
  function renderResults() {
    const ses = state.ses, head = ses.headline, button = $("#open-results");
    button.hidden = !head;
    if (!head) return void openSheet("results", false);
    const W = 150, x = (v) => 6 + v * (W - 12);
    button.replaceChildren(
      h("span", { text: `${head.label}, ${head.count} runs` }),
      s("svg", { viewBox: `0 0 ${W} 20`, "aria-hidden": "true" },
        s("line", { class: "axis", x1: x(0), x2: x(1), y1: 10, y2: 10 }),
        s("line", { class: "mean", x1: x(head.mean), x2: x(head.mean), y1: 2, y2: 18 }),
        head.runs.map((r) => s("circle", { class: `dot ${r.how || ""}${r.trial === state.run.id ? " on" : ""}`, cx: x(r.score), cy: 10, r: r.trial === state.run.id ? 4.6 : 3.4 }))),
      h("span", {}, "mean ", h("b", { text: head.mean.toFixed(2) })));
    button.title = `Every ${head.label} run on this level: ${head.runs.map((r) => r.score.toFixed(2)).join(", ")}. The reference is 1, doing nothing 0.`;
    $("#results-title").textContent = `All ${head.count} ${head.label} runs on this level`;
    const seeds = [...new Set(head.runs.map((r) => r.seed))];
    const groups = Object.keys(HOW).map((how) => [how, head.runs.filter((r) => r.how === how)]).filter(([, list]) => list.length);
    const range = (list) => { const v = list.map((r) => r.score); return v.length > 2 ? `${Math.min(...v).toFixed(2)} to ${Math.max(...v).toFixed(2)}` : v.map((n) => n.toFixed(2)).join(" and "); };
    const chip = (r) => {
      const here = ses.runs.find((run) => run.id === r.trial);
      const label = h("b", { text: r.score.toFixed(2) });
      return here ? h("button", { type: "button", class: `chip ${r.how || ""}`, "aria-pressed": String(here === state.run), title: "Show this run",
        onclick: () => { state.run = here; state.pin = null; renderAll(); } }, label) : h("span", { class: `chip ${r.how || ""}` }, label);
    };
    $("#results-body").replaceChildren(...[
      h("p", { class: "lead" }, "Mean ", h("b", { text: head.mean.toFixed(2) }), `, median ${head.median.toFixed(2)}, range ${head.low.toFixed(2)} to ${head.high.toFixed(2)}. The reference is 1, doing nothing is 0.`),
      h("table", {}, seeds.map((seed) => h("tr", {}, h("th", { text: `Seed ${seed}` }), h("td", {}, head.runs.filter((r) => r.seed === seed).map(chip))))),
      h("ul", { class: "split" }, groups.map(([how, list]) => h("li", { class: how },
        h("b", { text: `${list.length} run${list.length === 1 ? "" : "s"}` }), ` ${HOW[how]}: `, h("b", { text: range(list) })))),
      head.others.length ? h("p", { class: "quiet", text: `Other models, one run each on seed ${head.others[0].seed}: ${head.others.map((o) => `${o.label} ${o.score.toFixed(2)}`).join(", ")}.` }) : null,
      h("p", { class: "quiet", text: `${head.source}.` }),
      head.fresh ? [
        h("h4", {}, `${head.label} on ${head.fresh.runs.length} seeds no task ships, one run each: mean `, h("b", { text: head.fresh.mean.toFixed(2) })),
        h("table", { class: "fresh" },
          h("tr", {}, head.fresh.runs.map((r) => h("th", { text: `Seed ${r.seed}` }))),
          h("tr", {}, head.fresh.runs.map((r) => {
            const here = r.seed === ses.seed && ses.runs.find((run) => run.kind === "trial");
            return h("td", {}, chip({ ...r, trial: here ? here.id : null }));
          }))),
        h("p", { class: "quiet", text: `${head.fresh.source}. The replays here are of these seeds: the shipped tasks' episodes are never published. Click the score with a border to watch this seed's run.` }),
      ] : null,
    ].flat().filter(Boolean));
  }

  // --- one run: heading, till and graph ----------------------------------------------

  function makePanel(root, side) {
    const svg = $(".graph svg", root), box = $(".graph", root);
    const total = $(".total", root), gapEl = $(".gap", root), now = $(".now span", root), nowTag = $(".now .tag", root), sumLabel = $(".sum-label", root);
    const whyEl = $(".why", root);
    let wasOver = null;
    let ses, run, nodes, links, edges, labels, look, lookName, minute = null, lastWaste = 0;

    function head() {
      const worked = `(${usd(ses.cost_null)} − ${usd(run.cost.total)}) / (${usd(ses.cost_null)} − ${usd(ses.cost_ref)}), never below 0`;
      $("h2", root).replaceChildren(run.name || run.label, h("span", { title: `Final score: ${worked}` }, "final score ", h("b", { text: run.score.toFixed(2) }),
        side === "ref" ? `, seed ${ses.seed}` : run.kind === "trial" ? "" : " (scripted policy)"));
    }

    function build() {
      ses = state.ses;
      run = side === "ref" ? state.ref : state.run;
      head();
      const { width: W, height: H } = box.getBoundingClientRect();
      if (!W || !H) return;
      box.dataset.built = `${Math.round(W)}x${Math.round(H)}`;
      const u = rem(), svcs = ses.services;
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      svg.replaceChildren();
      // services off the customer path sit in a side block; the ones the story is about lead it,
      // the same in both panels
      const orphans = svcs.filter((v) => v.row == null);
      const inStory = (r, i) => ses.faults.some((f) => f.service === i) || (ses.decoy && ses.decoy.service === i) || r.mit.some((a) => a.service === i);
      const lead = orphans.filter((v) => inStory(state.run, svcs.indexOf(v)) || inStory(state.ref, svcs.indexOf(v)));
      const rest = orphans.filter((v) => !lead.includes(v));
      const cols = 4, pitch = 2.2 * u;
      const asideW = orphans.length ? cols * pitch + 1.7 * u : 0;
      const x0 = 3.4 * u, x1 = W - 0.9 * u - asideW;
      const top = 0.55 * u, gaugeY = top + 2.8 * u, gaugeH = 0.85 * u;
      const yA = gaugeY + gaugeH + 2.5 * u, yZ = H - 1.5 * u;
      // rows that hold one or two services get less height than the crowded ones
      const count = Array.from({ length: ses.rows }, (_, r) => svcs.filter((v) => v.row === r).length);
      const ys = [0, 0];
      for (let r = 2; r < ses.rows; r++) {
        ys.push(ys[r - 1] + (r === ses.rows - 1 ? 0.6 : 0.3 + 0.7 * Math.min(1, Math.max(count[r - 1], count[r]) / 6)));
      }
      const rowY = (r) => yA + (ys[r] * (yZ - yA)) / Math.max(1e-9, ys[ses.rows - 1]);
      const R = 0.5 * u;
      const ax = x1 + 1.6 * u, asideTop = yA - 0.9 * u, leadH = 4.5 * u;
      const gridTop = asideTop + 2.3 * u + lead.length * leadH, gridRows = Math.ceil(rest.length / cols);
      const pitchY = clamp(gridRows > 1 ? (yZ - gridTop) / (gridRows - 1) : pitch, 1.35 * u, pitch);

      const pos = svcs.map((v) => {
        if (v.row === 0) {
          const w = v.w * (x1 - x0) - 0.9 * u, x = x0 + v.x * (x1 - x0);
          return { x, y: gaugeY + gaugeH, r: 0, left: x - w / 2, right: x + w / 2 };
        }
        if (v.row == null) {
          const j = lead.indexOf(v), k = rest.indexOf(v);
          return j >= 0 ? { x: ax + 1.25 * R, y: asideTop + 2.6 * u + j * leadH, r: R, lead: j }
            : { x: ax + R + (k % cols) * pitch, y: gridTop + Math.floor(k / cols) * pitchY, r: R };
        }
        return { x: x0 + v.x * (x1 - x0), y: rowY(v.row), r: R };
      });

      // tier names and the services no edge reaches
      const gLinks = s("g"), gNodes = s("g"), gLabels = s("g"), gTop = s("g");
      svg.append(
        s("text", { class: "tier", x: 0.9 * u, y: gaugeY + gaugeH - 0.1 * u, text: "Edge" }),
        s("text", { class: "tier", x: 0.9 * u, y: rowY(1) + 0.3 * u, text: "App" }),
        s("text", { class: "tier", x: 0.9 * u, y: rowY(ses.rows - 1) + 0.3 * u, text: "Data" }),
        gLinks, gNodes, gLabels, gTop);
      const blocked = [];
      for (const r of [1, ses.rows - 1]) blocked.push({ x: 0, y: rowY(r) - u, w: 3 * u, h: 1.8 * u });
      if (orphans.length) {
        svg.prepend(
          s("line", { class: "aside-rule", x1: x1 + 0.7 * u, x2: x1 + 0.7 * u, y1: asideTop - 0.7 * u, y2: yZ + 0.6 * u }),
          s("text", { class: "tier", x: ax, y: asideTop + 0.4 * u, text: "Outside customer path" }));
        blocked.push({ x: x1 + 0.7 * u, y: 0, w: W, h: H });
      }

      links = [];
      svcs.forEach((v, c) => {
        if (v.row == null) return;
        for (const [d, w] of v.deps) {
          const a = pos[c], b = pos[d];
          const sx = v.row === 0 ? clamp(b.x, a.left + 0.5 * u, a.right - 0.5 * u) : a.x;
          const sy = a.y + a.r, ey = b.y - b.r - 1, my = (sy + ey) / 2;
          const el = s("path", { class: w < 1 ? "link soft" : "link", d: `M${sx},${sy}C${sx},${my} ${b.x},${my} ${b.x},${ey}` });
          gLinks.append(el);
          links.push({ c, d, w, el, soft: w < 1, at: [sx, sy, b.x, ey] });
        }
      });

      nodes = [];
      edges = [];
      svcs.forEach((v, i) => {
        const p = pos[i];
        if (v.row === 0) {
          const g = s("g", { class: "edge" },
            s("text", { class: "name", x: p.left, y: top + 1.0 * u, text: v.name }),
            s("text", { class: "rate", x: p.left, y: top + 2.25 * u }),
            s("rect", { class: "gauge", x: p.left, y: gaugeY, width: p.right - p.left, height: gaugeH, rx: 2 }),
            s("rect", { class: "fill", x: p.left, y: gaugeY, width: 0, height: gaugeH, rx: 2 }));
          gNodes.append(g);
          edges.push({ i, g, name: g.children[0], rate: g.children[1], fill: g.children[3], width: p.right - p.left });
          blocked.push({ x: p.left, y: top, w: p.right - p.left, h: gaugeY + gaugeH - top });
          return;
        }
        const big = v.tier === "data" ? R * 0.92 : R;
        const mark = v.tier === "data"
          ? s("rect", { class: "mark", x: -big, y: -big, width: 2 * big, height: 2 * big, rx: 1.5 })
          : s("circle", { class: "mark", r: R });
        const g = s("g", { class: "node", transform: `translate(${p.x},${p.y})` },
          s("circle", { class: "hit", r: 1.0 * u }), mark,
          s("circle", { class: "core", r: R * 0.5 }),
          s("circle", { class: "ring", r: R + 0.55 * u }),
          s("circle", { class: "gate", r: R + 0.95 * u, transform: "rotate(-90)" }),
          s("path", { class: "cross", d: `M${R + 0.25 * u},${-R - 1.05 * u}l${0.8 * u},${0.8 * u}m0,${-0.8 * u}l${-0.8 * u},${0.8 * u}` }));
        g.addEventListener("pointerenter", (e) => hover(i, e));
        g.addEventListener("pointermove", (e) => moveTip(e));
        g.addEventListener("pointerleave", () => hover(null));
        gNodes.append(g);
        nodes.push({ i, g, mark, gate: g.children[4], turn: 2 * Math.PI * (R + 0.95 * u), base: `node ${v.tier}${v.row == null ? " orphan" : ""}` });
      });

      // edge names share one width setting: if one does not fit its bar, all of them narrow together
      const tight = () => Math.min(...edges.map((ed) => (ed.width + 0.4 * u) / ed.name.getComputedTextLength()));
      if (tight() < 1) for (const ed of edges) ed.name.style.fontStretch = "68%";
      const still = tight();
      if (still < 1) for (const ed of edges) ed.name.style.fontSize = `${1.12 * u * still}px`;

      for (const ed of edges) {  // do an edge's longest figures fit its bar? Asked once, here
        ed.rate.textContent = `−${usd(svcs[ed.i].revenue)}/min, 100% fail`;
        ed.short = ed.rate.getComputedTextLength() > ed.width;
        ed.rate.textContent = "";
      }

      // labels for the services the story is about: faults, the decoy, anything mitigated
      const story = new Map();
      const note = (i, from, caps) => {
        if (svcs[i].row === 0) return;
        const it = story.get(i) || { i, from: Infinity, caps: [] };
        it.from = Math.min(it.from, from);
        it.caps.push(...caps);
        story.set(i, it);
      };
      ses.faults.forEach((f, k) => note(f.service, f.start, [faultCap(f), doneCap(run.faults[k], Infinity)]));
      if (ses.decoy) note(ses.decoy.service, ses.decoy.start, [DECOY]);
      for (const a of run.mit) note(a.service, a.t0, [opCap(a), wasteCap(a), `${TOOL_NAME[a.tool] || a.tool} set off a retry storm`]);
      for (const x of run.throttles) note(x.service, x.span[0], [throttleCap(x, x.span[0]), "retry storm outlives the fix"]);
      for (const [i, list] of run.stormSpans) note(i, list[0][0], ["retry storm outlives the fix"]);
      for (const n of nodes) if (story.has(n.i)) n.base += " story";

      // a label must not cover another service, the cross of a wasted mitigation, the edge bars or the side block
      const hard = svcs.map((v, i) => {
        if (v.row === 0) return null;
        const half = (story.has(i) ? 1.7 * R : R) + 3;
        return { x: pos[i].x - half, y: pos[i].y - half, w: 2 * half, h: 2 * half, i };
      }).filter(Boolean).concat(blocked);
      for (const a of run.mit) {
        if (a.wasted && svcs[a.service].row !== 0) hard.push({ x: pos[a.service].x + R, y: pos[a.service].y - R - 1.2 * u, w: 1.3 * u, h: 1.3 * u });
      }
      // and should keep off the links that can carry failures, and from straight above or below another service
      const upstream = new Set([...ses.faults.map((f) => f.service), ...run.mit.map((a) => a.service)]);
      for (let grew = true; grew;) {
        grew = false;
        for (const l of links) if (upstream.has(l.d) && !upstream.has(l.c)) grew = !!upstream.add(l.c);
      }
      const wires = [];
      for (const l of links) {
        if (!upstream.has(l.d)) continue;
        const [sx, sy, ex, ey] = l.at, my = (sy + ey) / 2;
        for (let t = 0.06; t < 1; t += 0.06) {
          const q = 1 - t;
          wires.push([(q * q * q + 3 * q * q * t) * sx + (3 * q * t * t + t * t * t) * ex, q * q * q * sy + 3 * q * t * my + t * t * t * ey]);
        }
      }
      const columns = hard.filter((b) => b.i != null).map((b) => ({ x: b.x, y: b.y - 2.3 * u, w: b.w, h: b.h + 4.6 * u, i: b.i, weight: story.has(b.i) ? 4 : 0.25 }));
      const cover = (sp, w, hgt, b) => Math.max(0, Math.min(sp.x + w, b.x + b.w) - Math.max(sp.x, b.x))
        * Math.max(0, Math.min(sp.y + hgt, b.y + b.h) - Math.max(sp.y, b.y));
      labels = [];
      const placed = [], lh = 1.3 * u, hgt = 2.1 * lh, off = R * 1.6 + 0.3 * u;
      for (const it of [...story.values()].sort((a, b) => a.from - b.from)) {
        const p = pos[it.i];
        const name = s("text", { class: "name", text: svcs[it.i].name });
        const cap = s("text", { class: "cap" });
        const g = s("g", { class: "label" }, name, cap);  // shown while it is measured; paint hides it until its time
        gLabels.append(g);
        if (p.lead != null) {  // in the side block: beside its mark, with the caption wrapped below
          name.setAttribute("x", p.x + 1.25 * R + 0.5 * u);
          name.setAttribute("y", p.y + 0.4 * u);
          cap.setAttribute("y", p.y + 1.95 * u);
          labels.push({ ...it, from: -Infinity, g, cap, wrap: W - 0.7 * u - ax, x: ax });
          continue;
        }
        let w = name.getComputedTextLength();
        for (const c of it.caps) { cap.textContent = c; w = Math.max(w, cap.getComputedTextLength()); }
        cap.textContent = "";
        const spots = [];
        for (const far of [0, 1.4 * u, 2.8 * u]) {  // beside the mark first, then further out on a leader
          const d = off + far * 0.7, dy = R * 0.3 + far * 0.7;
          spots.push(
            { x: p.x + d, y: p.y + dy, far }, { x: p.x + d, y: p.y - hgt - dy, far },
            { x: p.x - d - w, y: p.y + dy, far, end: true }, { x: p.x - d - w, y: p.y - hgt - dy, far, end: true },
            { x: p.x + off + 0.2 * u + far, y: p.y - hgt / 2, far }, { x: p.x - off - 0.2 * u - far - w, y: p.y - hgt / 2, far, end: true },
            { x: p.x - w / 2, y: p.y + off + far, far }, { x: p.x - w / 2, y: p.y - off - hgt - far, far },
            { x: p.x - w * 0.2, y: p.y + off + far, far }, { x: p.x - w * 0.8, y: p.y + off + far, far },
            { x: p.x - w * 0.2, y: p.y - off - hgt - far, far }, { x: p.x - w * 0.8, y: p.y - off - hgt - far, far });
        }
        let best = null;
        spots.forEach((sp, n) => {
          let bad = 1e6 * (Math.max(0, 0.3 * u - sp.x) + Math.max(0, sp.x + w - x1 - 0.3 * u) + Math.max(0, 0.2 * u - sp.y) + Math.max(0, sp.y + hgt - H));
          for (const b of hard) if (b.i !== it.i) bad += 60 * cover(sp, w, hgt, b);
          for (const b of placed) bad += 60 * cover(sp, w, hgt, b);
          for (const [qx, qy] of wires) if (qx > sp.x - 3 && qx < sp.x + w + 3 && qy > sp.y - 2 && qy < sp.y + hgt + 2) bad += 450;
          for (const b of columns) if (b.i !== it.i) bad += b.weight * cover(sp, w, hgt, b);
          bad += sp.far * 45 + n * 0.01;
          if (!best || bad < best.bad) best = { ...sp, bad };
        });
        const tx = best.end ? best.x + w : best.x;
        for (const [t, k] of [[name, 0], [cap, 1]]) {
          t.setAttribute("x", tx);
          t.setAttribute("y", best.y + lh * (k + 0.85));
          if (best.end) t.setAttribute("text-anchor", "end");
        }
        if (best.far) {
          const cx = clamp(p.x, best.x, best.x + w), cy = clamp(p.y, best.y + 0.3 * lh, best.y + hgt - 0.5 * lh);
          const len = Math.hypot(cx - p.x, cy - p.y) || 1, from = 1.7 * R + 2;
          g.prepend(s("line", { class: "leader", x1: p.x + ((cx - p.x) / len) * from, y1: p.y + ((cy - p.y) / len) * from, x2: cx, y2: cy }));
        }
        placed.push({ x: best.x - 1.2 * u, y: best.y - 2, w: w + 2.4 * u, h: hgt + 4 });
        labels.push({ ...it, g, cap });
      }

      const a = R + 0.62 * u, c = 0.42 * u;
      look = s("path", { class: "look", opacity: 0, d: `M${-a},${-a + c}V${-a}H${-a + c}M${a - c},${-a}H${a}V${-a + c}M${a},${a - c}V${a}H${a - c}M${-a + c},${a}H${-a}V${a - c}` });
      lookName = s("text", { class: "look-name", "text-anchor": "middle" });
      gTop.append(look, lookName);
      panel.pos = pos;
      panel.R = R;
      minute = null;
      paint(state.T, true);
    }

    const DECOY = "batch job: loud, not a cause";
    const faultCap = (f) => (f.late ? `${f.label} since minute ${f.start}` : `${f.quiet ? "quiet " : ""}${f.label}, ${pct(f.share)} fail`);
    // after its fault a service is clear only once the storm has drained and the throttles are lifted:
    // the same minute the timeline calls "clear"
    const doneCap = (f, m) => (ses.rules.storms && f.clear != null && m >= f.clear ? `clear since ${f.clear}` : `fault removed ${f.cleared}`);
    const wasteCap = (a) => `${TOOL_NAME[a.tool] || a.tool} wasted ${usd(a.wasted || ses.rules.wasted)}`;
    const opCap = (a) => (a.wasted ? wasteCap(a) : `${TOOL_NAME[a.tool] || a.tool} lands at minute ${a.lands}`);
    // a throttle on a fault that is still live names the fault: the throttle does not end it
    const throttleCap = (x, m) => {
      const live = faultOn(ses, run, x.service, m);
      return live >= 0 ? `${ses.faults[live].label}, throttled ${x.percent}%`
        : stormAt(run, x.service, m) ? `retry storm, throttled ${x.percent}%` : `throttled ${x.percent}%`;
    };
    // a storm set off while the run was changing the service is the run's own doing
    const stormBy = (i, m) => {
      const span = stormAt(run, i, m);
      return span && run.mit.find((a) => a.service === i && a.t0 <= span[0] && span[0] <= a.lands);
    };

    // a caption in the side block wraps to the block's width
    function setCap(lb, text) {
      if (!lb.wrap || !text) return void (lb.cap.textContent = text);
      const probe = s("tspan"), lines = [];
      lb.cap.replaceChildren(probe);
      let line = "";
      for (const word of text.split(" ")) {
        probe.textContent = line ? `${line} ${word}` : word;
        if (line && probe.getComputedTextLength() > lb.wrap) { lines.push(line); line = word; } else line = probe.textContent;
      }
      lb.cap.replaceChildren(...lines.concat(line).map((ln, k) => s("tspan", { x: lb.x, dy: k ? "1.2em" : 0, text: ln })));
    }

    function paint(T, force) {
      if (!nodes) return;
      const c = costAt(ses, run, T);
      const text = usd(c.total);
      if (total.textContent !== text) total.textContent = text;
      total.classList.toggle("idle", T < 0);
      if (c.wasted > lastWaste && !force) {
        total.classList.remove("hit");
        void total.offsetWidth;
        total.classList.add("hit");
      }
      lastWaste = c.wasted;
      // the breakdown, on hover: written when the playback rests, not on every frame
      if (!state.playing || force) total.title = T < 0 ? "The page comes at minute 0" : `Lost revenue ${usd(c.outage)}, replicas ${usd(c.replicas)}, wasted ${usd(c.wasted)}`;
      const label = T >= ses.horizon ? "Lost\nin total" : "Lost\nso far";
      if (sumLabel.textContent !== label) sumLabel.textContent = label;
      const over = side === "agent" && T >= 0 && run !== state.ref ? Math.round(c.total - costAt(ses, state.ref, T).total) : 0;
      if (gapEl.dataset.v !== String(over)) {  // two text nodes, rewritten in place
        gapEl.dataset.v = String(over);
        if (!gapEl.firstChild) gapEl.append(h("b"), "");
        gapEl.firstChild.textContent = side === "ref" || !over ? "" : (over > 0 ? "+" : "−") + usd(Math.abs(over));
        gapEl.lastChild.textContent = side === "ref" || !over ? "" : over > 0 ? " over the reference" : " under the reference";
        gapEl.classList.toggle("under", over < 0);
      }
      const ended = T >= ses.horizon;  // the last minute's picture stays, the lines under the name change
      if (ended !== wasOver) { wasOver = ended; force = true; }

      const m = clamp(Math.floor(T), -ses.pre, ses.horizon - 1);
      if (m === minute && !force) return void numbers(T);
      minute = m;
      const errs = run.errAt[m + ses.pre], hot = run.hotAt[m + ses.pre];
      const ops = run.mit.filter((a) => a.t0 <= m && m < a.lands);
      const wastes = run.mit.filter((a) => a.wasted && a.t0 <= m);

      for (const n of nodes) {
        const e = errs.get(n.i), k = faultOn(ses, run, n.i, m);
        let cls = n.base;
        const op = ops.find((a) => a.service === n.i);
        if (k >= 0) cls += ses.faults[k].quiet ? " cause quiet" : " cause";
        else {
          if (e && e[0] >= 0.005) cls += " hurt";
          if (hot.has(n.i)) cls += " busy";
        }
        if (op) cls += op.wasted ? " op unneeded" : " op";
        const thr = throttleAt(run, n.i, m), storm = stormAt(run, n.i, m);
        if (storm) cls += " storm";
        if (thr) cls += " throttled";
        const arc = thr ? `${((thr.percent / 100) * n.turn).toFixed(1)} ${n.turn.toFixed(1)}` : "";
        if (n.arc !== arc) n.gate.style.strokeDasharray = n.arc = arc;
        if (wastes.some((a) => a.service === n.i)) cls += " wasted";
        if (n.cls !== cls) n.g.setAttribute("class", (n.cls = cls));
        const scale = k >= 0 ? 1.6 : storm ? 1.45 : n.base.endsWith(" story") ? 1.25 : 1;
        if (n.scale !== scale) n.mark.style.transform = (n.scale = scale) === 1 ? "" : `scale(${scale})`;
        n.g.style.setProperty("--e", e ? Math.sqrt(e[0]).toFixed(3) : 0);
      }
      const u = rem();
      for (const l of links) {
        const e = errs.get(l.d), pass = e ? e[0] * l.w : 0;
        const cls = pass >= 0.005 ? "link fail" : l.soft ? "link soft" : "link";
        if (l.cls !== cls) l.el.setAttribute("class", (l.cls = cls));
        l.el.style.strokeWidth = pass >= 0.005 ? (0.09 * u + 0.4 * u * Math.sqrt(pass)).toFixed(2) : "";
      }
      for (const ed of edges) {
        const v = ses.services[ed.i], e = errs.get(ed.i), err = e ? e[0] : 0;
        const waste = wastes.filter((a) => a.service === ed.i).pop(), op = ops.find((a) => a.service === ed.i);
        ed.g.setAttribute("class", err >= 0.005 || waste ? "edge losing" : "edge");
        ed.fill.setAttribute("width", err >= 0.0005 ? Math.max(3, err * ed.width) : 0);
        ed.rate.textContent = op ? opCap(op) : waste ? wasteCap(waste)
          : err >= 0.005 ? `−${usd(v.revenue * err)}/min, ${pct(err)} fail` : `${usd(v.revenue)}/min`;
        if (ed.short) ed.rate.textContent = err >= 0.005 ? `−${usd(v.revenue * err)}/min` : `${usd(v.revenue)}/min`;
        ed.figures = !op && !waste && err >= 0.005;  // its line shows numbers, which glide while playing
      }
      for (const lb of labels) {
        const shown = lb.from <= m;
        let cap = "", kind = "";
        if (shown) {
          const op = ops.find((a) => a.service === lb.i), waste = wastes.filter((a) => a.service === lb.i).pop();
          const k = ses.faults.findIndex((f) => f.service === lb.i);
          const live = faultOn(ses, run, lb.i, m);
          const thr = throttleAt(run, lb.i, m), storm = stormAt(run, lb.i, m), by = stormBy(lb.i, m);
          if (by) [cap, kind] = [`${TOOL_NAME[by.tool] || by.tool} set off a retry storm`, "is-wasted"];
          else if (op) [cap, kind] = [opCap(op), op.wasted ? "is-wasted" : "is-op"];
          else if (thr) [cap, kind] = [throttleCap(thr, m), live >= 0 || storm ? "is-cause" : "is-op"];
          else if (live >= 0) [cap, kind] = [faultCap(ses.faults[live]), "is-cause"];
          else if (storm) [cap, kind] = [k >= 0 ? "retry storm outlives the fix" : "retry storm", "is-cause"];
          else if (waste) [cap, kind] = [wasteCap(waste), "is-wasted"];
          else if (k >= 0 && ses.faults[k].start <= m) cap = doneCap(run.faults[k], m);
          else if (ses.decoy && ses.decoy.service === lb.i && m < ses.decoy.end) [cap, kind] = [DECOY, "is-busy"];
          else if (ses.decoy && ses.decoy.service === lb.i) cap = "batch job finished";
        }
        lb.g.setAttribute("class", `label ${shown ? kind : "off"}`);
        if (lb.text !== cap) setCap(lb, (lb.text = cap));
      }

      // where the run is looking, and what it is doing
      const act = latest(run, m);
      const reading = act && act.kind === "query" && act.service != null && m < act.t1 + 2 ? act : null;
      if (reading && ses.services[reading.service].row !== 0) {
        const p = panel.pos[reading.service];
        look.setAttribute("transform", `translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`);
        look.setAttribute("opacity", 1);
        const named = labels.some((lb) => lb.i === reading.service && lb.from <= m);
        lookName.textContent = named ? "" : ses.services[reading.service].name;
        lookName.setAttribute("x", clamp(p.x, 4 * u, svg.viewBox.baseVal.width - 4 * u));
        const below = p.y + panel.R + 1.55 * u;
        lookName.setAttribute("y", below + 0.3 * u < svg.viewBox.baseVal.height - 0.3 * u ? below + 0.3 * u : p.y - panel.R - 1.2 * u);
      } else {
        look.setAttribute("opacity", 0);
        lookName.textContent = "";
      }
      // a mitigation stays on the line for a few minutes, so its reason can be read while queries go by
      // a moment the story turns on holds the line longest
      const moment = (r) => latest(r, m, (a) => a.label && m - a.t0 <= 9);
      // while the agent's line is on the moment its run turns on, the reference's line shows what it did
      // at its own moment on that service, however long ago: the two decisions side by side
      const theirs = side === "ref" && state.run !== run ? moment(state.run) : null;
      const answer = theirs && latest(run, m, (a) => a.label && a.service === theirs.service);
      const lead = answer || moment(run)
        || latest(run, m, (a) => (a.kind === "mitigation" || a.kind === "throttle") && m - a.t0 <= 7) || act;
      const outcome = ended && run.note;
      nowTag.textContent = outcome ? "Outcome" : "Now";
      now.textContent = outcome ? run.note.what
        : !run.actions.length ? "Never touches the estate"
        : m < 0 ? "Not paged yet"
        : !lead ? "Paged at minute 0"
        : lead.tool === "finish" ? `Left the shift at minute ${lead.t0}`
        : `Minute ${lead.t0}: ${verb(lead)}`;
      // the reference's reason from its runbook; the agent's own words about this call, from its report
      const reason = outcome || !lead || m < 0 ? "" : side === "ref" ? lead.why || "" : lead.quote || "";
      if (whyEl.dataset.v !== reason) {
        whyEl.dataset.v = reason;
        whyEl.replaceChildren(...(reason ? [h("b", { class: "tag", text: side === "ref" ? "Why" : "In its words" }), side === "ref" ? reason : `“${reason}”`] : []));
        whyEl.title = reason;
      }
      if (side === "ref") {  // the runbook panel follows along
        const at = latest(run, m, (a) => a.rule);
        document.querySelectorAll("#runbook-lines li").forEach((li, k) => li.classList.toggle("on", !!at && m >= 0 && !ended && at.rule === k + 1));
      }
      numbers(T);
    }

    // What changes by degree is redrawn every frame while playing, gliding between the minutes: how deep a
    // failing service is coloured, how thick a failing link is, an edge's bar and its figures. What a
    // service is (cause, storm, throttled, fixed) and every caption stay with their minute, above.
    function numbers(T) {
      if (!gliding()) return;  // paused or stepping: the minute's own values are already drawn
      const errOf = (i) => (m) => { const e = run.errAt[m + ses.pre].get(i); return e ? e[0] : 0; };
      const u = rem(), now = performance.now();
      for (const n of nodes) {
        if (n.cls.includes(" hurt")) n.g.style.setProperty("--e", Math.sqrt(Math.max(0, glide(ses, run, T, errOf(n.i)))).toFixed(3));
      }
      for (const l of links) {
        if (l.cls !== "link fail") continue;
        const pass = Math.max(0, glide(ses, run, T, errOf(l.d)) * l.w);
        l.el.style.strokeWidth = (0.09 * u + 0.4 * u * Math.sqrt(pass)).toFixed(2);
      }
      for (const ed of edges) {
        const v = ses.services[ed.i], err = Math.max(0, glide(ses, run, T, errOf(ed.i)));
        ed.fill.setAttribute("width", err >= 0.0005 ? Math.max(3, err * ed.width).toFixed(1) : 0);
        // the figures are rewritten eight times a second: readable, and text is the dearest thing to lay out
        if (ed.figures && now - (ed.wrote || 0) > 120) {
          ed.wrote = now;
          ed.rate.textContent = ed.short ? `−${usd(v.revenue * err)}/min` : `−${usd(v.revenue * err)}/min, ${pct(err)} fail`;
        }
      }
    }

    function hover(i, ev) {
      for (const n of nodes) n.g.classList.toggle("lit", n.i === i);
      for (const l of links) l.el.classList.toggle("near", i != null && (l.c === i || l.d === i));
      const tip = $("#tip");
      if (i == null) return (tip.hidden = true);
      const v = ses.services[i], m = clamp(Math.floor(state.T), -ses.pre, ses.horizon - 1);
      const e = run.errAt[m + ses.pre].get(i) || [0, 0];
      const callers = ses.services.filter((x) => x.deps.some(([d]) => d === i)).map((x) => x.name);
      tip.replaceChildren(...[
        h("b", { text: v.name }), h("span", { text: `  ${v.tier} service` }), h("br"),
        e[0] >= 0.0005 ? `Fails ${pct(e[0])} of requests, ${pct(e[1])} on its own` : "Serving normally",
        run.hotAt[m + ses.pre].has(i) ? ", CPU alert" : "", h("br"),
        v.retries ? `Callers retry ${v.retries} times${v.tight ? "; runs close to capacity" : ""}` : v.tight ? "Runs close to capacity" : null,
        v.retries || v.tight ? h("br") : null,
        h("span", { text: `Calls ${v.deps.map(([d, w]) => ses.services[d].name + (w < 1 ? " (soft)" : "")).join(", ") || "nothing"}` }), h("br"),
        h("span", { text: `Called by ${callers.join(", ") || "nothing"}` })].filter((x) => x != null));
      tip.hidden = false;
      moveTip(ev);
    }

    const panel = { build, paint, hover };
    return panel;
  }

  let lastPointer = null;
  function moveTip(e) {
    if (e && e.clientX != null) lastPointer = e;
    const tip = $("#tip");
    if (!lastPointer || tip.hidden) return;
    const w = tip.offsetWidth, hgt = tip.offsetHeight;
    tip.style.left = clamp(lastPointer.clientX + 14, 8, innerWidth - w - 8) + "px";
    tip.style.top = clamp(lastPointer.clientY + 16, 8, innerHeight - hgt - 8) + "px";
  }

  // --- timeline ----------------------------------------------------------------------

  function buildTrack() {
    const box = $("#track"), svg = $("svg", box), ses = state.ses, runs = [state.run, state.ref];
    const { width: W, height: H } = box.getBoundingClientRect();
    if (!W || !H) return;
    box.dataset.built = `${Math.round(W)}x${Math.round(H)}`;
    const u = rem(), gut = 16.5 * u, padR = 6.6 * u;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.replaceChildren(s("defs", {}, ...["agent", "ref"].map((who) =>
      s("pattern", { id: `hatch-${who}`, class: `hatch-${who}`, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
        s("rect", { class: "ground", width: 5, height: 5 }), s("rect", { class: "stripe", width: 2.2, height: 5 })))));
    const span = ses.pre + ses.horizon;
    const x = (t) => gut + ((t + ses.pre) / span) * (W - gut - padR);
    const lanes = state.lanes ? ses.faults.length + (ses.decoy ? 1 : 0) : 0;  // one row per fault, on demand
    // when the deck is short the rows give way before the chart does
    const axisH = 1.7 * u, labelH = 1.3 * u, room = H - axisH - 0.8 * u - 3.7 * u - 2 * labelH;
    const fit = clamp(room / (lanes * 2.05 * u + 2 * 1.95 * u), 0.78, 1);
    const laneH = 2.05 * u * fit, actH = 1.95 * u * fit;
    const lanesTop = H - axisH - 2 * actH - 2 * labelH - lanes * laneH - 0.2 * u;
    const chartTop = 0.5 * u, chartBot = lanesTop - 0.6 * u, chartH = Math.max(u, chartBot - chartTop);
    const mid = (y0, hgt) => y0 + hgt / 2 + 0.34 * u;  // baseline of one line of text centred in a row
    const [agent, ref] = runs;

    // lost revenue per minute: what both runs lose is pale, what only the agent loses is full red
    const peak = Math.max(1, ...runs.flatMap((r) => r.loss));
    const y = (v) => chartBot - (v / peak) * chartH;
    const px = (t) => x(t).toFixed(1), py = (v) => y(v).toFixed(1);
    const steps = (vals) => vals.map((v, k) => `L${px(k - ses.pre)},${py(v)}H${px(k - ses.pre + 1)}`).join("");
    const both = agent.loss.map((v, k) => Math.min(v, ref.loss[k]));
    const over = agent.loss.map((v, k) => (v > ref.loss[k] + 0.5
      ? `M${px(k - ses.pre)},${py(ref.loss[k])}V${py(v)}H${px(k - ses.pre + 1)}V${py(ref.loss[k])}Z` : "")).join("");
    const key = (row) => chartTop + (1.0 + 1.22 * row) * u;
    svg.append(
      s("rect", { class: "before", x: x(-ses.pre), y: 0, width: x(0) - x(-ses.pre), height: H - axisH }),
      s("line", { class: "grid", x1: gut, x2: W - padR, y1: y(peak), y2: y(peak) }),
      s("text", { x: W - padR + 0.9 * u, y: y(peak) + 0.35 * u, text: `${usd(peak)}/min` }),
      s("path", { class: "loss-both", d: `M${px(-ses.pre)},${chartBot}${steps(both)}V${chartBot}Z` }),
      s("path", { class: "loss-over", d: over || "M0,0" }),
      s("path", { class: "loss-ref", d: `M${px(-ses.pre)},${py(ref.loss[0])}${steps(ref.loss)}` }),
      s("line", { class: "lane-rule", x1: gut, x2: W - padR, y1: chartBot, y2: chartBot }),
      s("text", { class: "row-name", x: u, y: key(0), text: "Revenue lost per minute" }),
      s("rect", { class: "loss-over", x: u, y: key(1) - 0.72 * u, width: 1.2 * u, height: 0.78 * u }),
      s("text", { x: 2.7 * u, y: key(1), text: "more than the reference" }),
      key(2) < lanesTop - 0.2 * u && s("rect", { class: "loss-both", x: u, y: key(2) - 0.72 * u, width: 1.2 * u, height: 0.78 * u }),
      key(2) < lanesTop - 0.2 * u && s("text", { x: 2.7 * u, y: key(2), text: "lost in both runs" }),
      key(3) < lanesTop - 0.2 * u && s("line", { class: "loss-ref", x1: u, x2: 2.2 * u, y1: key(3) - 0.33 * u, y2: key(3) - 0.33 * u }),
      key(3) < lanesTop - 0.2 * u && s("text", { x: 2.7 * u, y: key(3), text: "reference" }));

    // one lane per fault: how long it stayed live in each run
    (state.lanes ? ses.faults : []).forEach((f, k) => {
      const y0 = lanesTop + k * laneH, name = ses.services[f.service].name;
      svg.append(
        s("line", { class: "lane-rule", x1: u, x2: W - padR, y1: y0, y2: y0 }),
        s("text", { x: u, y: mid(y0, laneH) }, s("tspan", { class: "row-name", text: name }),
          s("tspan", { class: "row-note", dx: 0.45 * u, text: (f.quiet ? "quiet " : "") + f.label })));
      if (f.late) {  // a fault that was not there when the shift began
        svg.append(
          s("line", { class: "onset", x1: x(f.start), x2: x(f.start), y1: y0 + 0.08 * laneH, y2: y0 + 0.92 * laneH }),
          s("text", { class: "onset-note", x: x(f.start) - 0.5 * u, y: mid(y0, laneH), "text-anchor": "end", text: `starts mid-shift, minute ${f.start}` }));
      }
      const bar = (cls, a, b, top, hgt) => s("rect", { class: cls, x: x(a), y: y0 + top * laneH, width: Math.max(1, x(b) - x(a)), height: hgt * laneH, rx: 1 });
      const lane = (run, who, top, hgt) => [
        ...run.faults[k].live.map(([a, b]) => bar(`bar-${who}`, a, b, top, hgt)),
        ...run.faults[k].after.map(([a, b]) => bar(`storm-${who}`, a, b, top, hgt)),
        ...run.faults[k].held.map(([a, b]) => bar("bar-throttle", a, b, top + hgt, 0.11))];
      svg.append(...lane(agent, "agent", 0.12, 0.28), ...(agent === ref ? [] : lane(ref, "ref", 0.62, 0.17)));
      // each run's label ends its bars: when the fault was removed and, where that is later, when the service was clear
      const a = agent.faults[k].clear, r = ref.faults[k].clear;
      const late = a != null && r != null && a - r > 0 ? `${a - r} min after the reference` : a != null && r != null && a < r ? `${r - a} min sooner` : "";
      // the reference's label keeps to the moment the gap is counted from
      const end = (run, cls, yy, more) => {
        const g = run.faults[k], at = g.clear == null ? ses.horizon : g.clear;
        const words = run !== ref || agent === ref || g.clear == null ? endOf(ses, g) : ses.rules.storms ? `clear ${g.clear}` : `fault removed ${g.cleared}`;
        const text = s("text", { class: cls, x: x(at) + 0.45 * u, y: yy }, s("tspan", { text: words }),
          more ? s("tspan", { class: "end-late", dx: 0.5 * u, text: more }) : null);
        svg.append(text);
        // near the end of the shift the label does not fit after its bars: it goes before the end, on the sheet's colour
        if (x(at) + 0.45 * u + text.getComputedTextLength() > W - 0.4 * u) {
          text.setAttribute("x", W - 0.4 * u);
          text.setAttribute("text-anchor", "end");
          text.classList.add("over");
        }
      };
      end(agent, "end-agent", y0 + 0.29 * laneH + 0.34 * u, agent !== ref && late);
      if (agent !== ref) end(ref, "end-ref", y0 + 0.745 * laneH + 0.34 * u);
    });
    if (ses.decoy && state.lanes) {
      const y0 = lanesTop + ses.faults.length * laneH, d = ses.decoy;
      const hits = agent.mit.filter((a) => a.service === d.service && a.wasted);
      svg.append(
        s("line", { class: "lane-rule", x1: u, x2: W - padR, y1: y0, y2: y0 }),
        s("text", { x: u, y: mid(y0, laneH) }, s("tspan", { class: "row-name", text: ses.services[d.service].name }),
          s("tspan", { class: "row-note", dx: 0.45 * u, text: "decoy: loud batch job" })),
        s("rect", { class: "bar-decoy", x: x(Math.max(d.start, -ses.pre)), y: y0 + 0.33 * laneH, width: x(d.end) - x(Math.max(d.start, -ses.pre)), height: 0.34 * laneH, rx: 1 }),
        s("text", { class: hits.length ? "end-agent" : "", x: x(d.end) + 0.45 * u, y: mid(y0, laneH),
          text: hits.length ? `${hits.length} wasted on it` : "left alone" }));
    }

    // actions
    const rowsTop = lanesTop + lanes * laneH;
    const acts = { agent: [], ref: [] };
    [["agent", agent], ["ref", ref]].forEach(([side, run], row) => {
      const cy = rowsTop + labelH + row * actH + actH / 2;
      const wasted = run.mit.filter((a) => a.wasted).length;
      svg.append(
        s("line", { class: "lane-rule", x1: u, x2: W - padR, y1: cy - actH / 2, y2: cy - actH / 2 }),
        s("text", { x: u, y: cy + 0.34 * u }, s("tspan", { class: "row-name", text: side === "ref" ? "Reference" : run.name || run.label }),
          s("tspan", { class: wasted ? "end-agent" : "row-note", dx: 0.45 * u,
            text: `${run.mit.length} mitigation${run.mit.length === 1 ? "" : "s"}${run.throttles.length ? `, ${run.throttles.length} throttle${run.throttles.length === 1 ? "" : "s"}` : ""}${wasted ? `, ${wasted} wasted` : ""}` })));
      if (side === "ref" && agent === ref) return;
      const d = 0.46 * u * fit;
      const diamond = (xx, yy) => `M${xx},${yy - 1.3 * d}L${xx + 1.3 * d},${yy}L${xx},${yy + 1.3 * d}L${xx - 1.3 * d},${yy}Z`;
      const draw = (a, shape, xx, title, yy = cy) => {
        const g = s("g", { class: "act", "data-side": side, "data-i": a === "report" ? "report" : a.i },
          s("rect", { class: "hit", x: xx - Math.max(4, 0.3 * u), y: cy - actH / 2, width: Math.max(8, 0.6 * u), height: actH }),
          s("circle", { class: "halo", cx: xx, cy: yy, r: 0.78 * u * fit }), shape);
        g.dataset.tip = title;
        svg.append(g);
        acts[side].push({ a, g });
      };
      for (const a of run.actions) {
        const xx = x(a.t0), title = `Minute ${a.t0}: ${verb(a)}`;
        if (a.kind === "query") draw(a, s("line", { class: "tick", x1: xx, x2: xx, y1: cy - d, y2: cy + d }), xx, title);
        else if (a.kind === "throttle") draw(a, s("rect", { class: a.percent ? "throttle-on" : "throttle-off", x: xx - 0.8 * d, y: cy - 0.8 * d, width: 1.6 * d, height: 1.6 * d, rx: 1 }), xx, title);
        else if (a.kind === "other") draw(a, s("path", { class: "soft", d: diamond(xx, cy) }), xx, title);
        else if (a.kind === "finish" && a.t0 < ses.horizon) draw(a, s("rect", { class: "stop", x: xx - 0.7 * d, y: cy - 0.7 * d, width: 1.4 * d, height: 1.4 * d }), xx, title);
      }
      let lastX = -Infinity, up = false;
      for (const a of run.mit) {  // drawn last so they sit above the query ticks; close neighbours step apart
        const xx = x(a.t0), title = `Minute ${a.t0}: ${verb(a)}${a.wasted ? `, ${usd(a.wasted)} wasted` : ""}`;
        up = xx - lastX < 2.7 * d ? !up : false;
        const yy = xx - lastX < 2.7 * d ? cy + (up ? -0.95 : 0.95) * d : cy;
        if (xx - lastX < 2.7 * d && up) acts[side][acts[side].length - 1].g.setAttribute("transform", `translate(0,${0.95 * d})`);
        lastX = xx;
        draw(a, a.effect === "wasted"
          ? s("path", { class: "waste", d: `M${xx - d},${yy - d}L${xx + d},${yy + d}M${xx + d},${yy - d}L${xx - d},${yy + d}` })
          : s("path", { class: a.effect === "fix" ? "fix" : "soft", d: diamond(xx, yy) }), xx, title, yy);
      }
      // the moments the story turns on are named: above the agent's row, below the reference's
      let edge = -Infinity;
      for (const a of run.actions) {
        if (!a.label || x(a.t0) < edge) continue;
        const up = side === "agent", yy = up ? cy - actH / 2 - 0.35 * u : cy + actH / 2 + 0.95 * u;
        const text = s("text", { class: `moment moment-${side}`, x: x(a.t0) - 0.3 * u, y: yy, text: a.label });
        svg.append(s("line", { class: `moment-tick moment-${side}`, x1: x(a.t0), x2: x(a.t0), y1: up ? yy + 0.2 * u : yy - 0.85 * u, y2: up ? cy - 0.6 * actH / 2 : cy + 0.6 * actH / 2 }), text);
        edge = x(a.t0) + text.getComputedTextLength() + u;
      }
      if (run.report) {
        const xx = x(ses.horizon) + 1.6 * u, e = 0.62 * u * fit;
        draw("report", s("path", { class: "soft", d: `M${xx - 0.65 * e},${cy - e}h${0.85 * e}l${0.45 * e},${0.45 * e}v${1.55 * e}h${-1.3 * e}z` }), xx, "The agent's own shift report, and our note on the run");
        svg.append(s("text", { x: xx + 1.35 * u, y: cy + 0.34 * u, text: "report", "pointer-events": "none" }));
      }
    });

    // axis and playhead
    const axis = s("g", { class: "axis" });
    for (let t = -ses.pre; t <= ses.horizon; t += 15) {
      axis.append(
        s("line", { x1: x(t), x2: x(t), y1: H - axisH, y2: H - axisH + 0.3 * u }),
        s("text", { x: x(t), y: H - 0.35 * u, "text-anchor": "middle", text: t === 0 ? "0, paged" : `${t}` }));
    }
    const headLine = s("line", { class: "head", y1: 0.1 * u, y2: H - axisH });
    const knob = s("path", { class: "head-knob", d: `M${-0.42 * u},0h${0.84 * u}l${-0.42 * u},${0.6 * u}z` });
    const head = s("g", {}, headLine, knob);
    svg.append(s("line", { class: "page", x1: x(0), x2: x(0), y1: 0, y2: H - axisH }), axis,
      s("text", { x: u, y: H - 0.35 * u, text: "Minutes, charged from 0" }), head);

    track = {
      acts, x,
      time: (px) => clamp(((px - gut) / (W - gut - padR)) * span - ses.pre, -ses.pre, ses.horizon),
      paint(T) { head.setAttribute("transform", `translate(${x(T).toFixed(1)},0)`); },
      mark() {
        for (const side of ["agent", "ref"]) {
          for (const { a, g } of acts[side]) {
            const shown = shownAction(), on = !!shown && shown.side === side && shown.action === a;
            g.classList.toggle("on", on);
          }
        }
      },
    };
    track.paint(state.T);
    track.mark();
  }

  // --- inspector ---------------------------------------------------------------------

  // the action whose details are open: the one that was clicked, or none
  function shownAction() {
    if (!state.pin) return null;
    const run = state.pin.side === "ref" ? state.ref : state.run;
    return { side: state.pin.side, run, action: state.pin.i === "report" ? "report" : run.actions[state.pin.i] };
  }

  function inline(text) {
    return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part) =>
      part.startsWith("**") ? h("b", { text: part.slice(2, -2) }) : part.startsWith("`") ? h("code", { text: part.slice(1, -1) }) : part);
  }

  function prose(text) {
    const out = h("div", { class: "said prose" });
    let list = null, table = null;
    for (const line of text.split("\n")) {
      const t = line.trim();
      if (/^\|/.test(t)) {
        if (/^\|[\s:|-]+\|$/.test(t)) continue;
        const cells = t.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!table) { table = h("table"); out.append(table); table.append(h("tr", {}, cells.map((c) => h("th", {}, inline(c))))); }
        else table.append(h("tr", {}, cells.map((c) => h("td", {}, inline(c)))));
        list = null;
        continue;
      }
      table = null;
      const item = t.match(/^(?:[-*]|\d+\.)\s+(.*)$/);
      if (item) {
        if (!list) { list = h("ul"); out.append(list); }
        list.append(h("li", {}, inline(item[1])));
      } else if (t) {
        list = null;
        out.append(h("p", {}, inline(t.replace(/^#+\s*/, ""))));
      }
    }
    return out;
  }

  const cell = (v, cls) => h("td", { class: cls, text: v });
  function tableOf(head, rows) {
    return h("table", {}, h("tr", {}, head.map(([name, num]) => h("th", { class: num && "num", text: name }))), rows);
  }

  function seen(a) {
    const r = a.result;
    switch (a.tool) {
      case "list_alerts":
        return [tableOf([["Service"], ["Signal"], ["Value", 1], ["Since", 1]], r.alerts.map((x) =>
          h("tr", {}, cell(x.service), cell(x.signal.replace("_", " ")), cell(x.signal === "error_rate" ? pct(x.value) : x.value.toFixed(2), "num"), cell(x.firing_since_minute, "num")))),
          r.total > r.alerts.length ? h("p", { class: "quiet", text: `${r.alerts.length} loudest of ${r.total} firing` }) : null];
      case "get_metrics":
        return tableOf([["Min", 1], ["Errors", 1], ["p99 ms", 1], ["Req/s", 1], ["CPU", 1], ["Mem", 1], ["Repl", 1]], r.series.map((p) =>
          h("tr", { class: p.error_rate >= 0.05 ? "hot" : null }, cell(p.minute, "num"), cell(pct(p.error_rate), "num"), cell(p.p99_ms, "num"),
            cell(whole.format(p.rps), "num"), cell(p.cpu.toFixed(2), "num"), cell(p.mem.toFixed(2), "num"), cell(p.replicas, "num"))));
      case "get_logs":
        return tableOf([["Level"], ["Per 10 min", 1], ["Message"]], r.lines.map((l) =>
          h("tr", { class: l.level === "ERROR" || l.level === "FATAL" ? "hot" : null }, cell(l.level), cell(whole.format(l.count), "num"), cell(l.message, "msg"))));
      case "get_changes":
        return tableOf([["Change"], ["Type"], ["Min", 1], ["Summary"], ["Status"]], r.changes.map((c) =>
          h("tr", {}, cell(c.id), cell(c.type), cell(c.minute, "num"), cell(c.summary), cell(c.status))));
      case "get_diff":
        return h("pre", {}, r.diff.split("\n").map((line) => h("span", { class: line[0] === "+" ? "add" : line[0] === "-" ? "del" : null, text: line + "\n" })));
      case "get_topology":
        return h("p", { text: `The whole estate: ${Object.entries(r.services).map(([tier, n]) => `${n} ${tier}`).join(", ")} services and who calls whom.` });
      case "wait":
        return h("p", { text: `The clock moved from minute ${a.t0} to ${a.t1}.` });
      case "finish":
        return h("p", { text: "The rest of the 120 minutes is still simulated and charged." });
      default:
        return h("pre", { text: Object.entries(r).filter(([k]) => k !== "ok").map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(", ") });
    }
  }

  function verdict(a, ses) {
    const name = a.args.service;
    if (a.effect === "wasted") return ["bad", `Wasted: ${name} did not need this. ${usd(a.wasted)} charged, and the service is disturbed until minute ${a.lands}.`];
    if (a.effect === "fix" && a.fixed.length) {
      const f = ses.faults[a.fixed[0]];
      return ["good", `Ends the ${f.quiet ? "quiet " : ""}${f.label} on ${name} when it lands at minute ${a.lands}.`];
    }
    if (a.effect === "fix") return ["good", `Adds capacity on ${name} from minute ${a.lands}.`];
    if (a.effect === "undo") return ["", `Back to the normal replica count from minute ${a.lands}. Not charged.`];
    return ["", `Relief only: the cause on ${name} stays. Lands at minute ${a.lands}.`];
  }

  function throttleVerdict(a, ses) {
    if (!a.percent) return ["", `Lifts the throttle on ${a.args.service} from minute ${a.span[0]}.`];
    const [from, to] = a.span;
    return ["", `Rejects ${a.percent}% of ${a.args.service}'s requests up front from minute ${from}`
      + (to >= ses.horizon ? " to the end of the shift: it is never lifted." : `, for ${to - from} minute${to - from === 1 ? "" : "s"}. It ends no fault; its cost is the traffic it turns away.`)];
  }

  let shownKey = null;
  function renderInspector(force) {
    const ses = state.ses, shown = shownAction(), root = $("#inspector");
    const key = shown ? [ses.key, shown.run.id, shown.side, shown.action === "report" ? "report" : shown.action.i].join("|") : "none";
    if (key === shownKey && !force) return;
    shownKey = key;
    root.hidden = !shown;
    root.classList.toggle("left", !!shown && shown.side === "ref");  // beside the run it is about, not over it
    if (track) track.mark();
    if (!shown) return;
    const { side, run, action: a } = shown;
    const who = side === "ref" ? "Scripted reference" : run.name || run.label;
    const close = h("button", { type: "button", class: "close", onclick: () => { state.pin = null; renderInspector(true); }, text: "Close" });
    if (a === "report") {
      root.replaceChildren(...[h("div", { class: "top" }, h("h3", { text: "After the shift" }), close),
        h("p", { class: "meta", text: `${who}, final score ${run.score.toFixed(2)}` }),
        run.note && h("section", { class: "ours" }, h("h4", { text: "Our note on this run" }), h("p", { text: run.note.what })),
        h("section", { class: "theirs" }, h("h4", { text: "The agent's own report" }), prose(run.report))].filter(Boolean));
    } else {
      const args = Object.entries(a.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
      const said = a.say || a.think;
      const v = a.kind === "mitigation" ? verdict(a, ses) : a.kind === "throttle" ? throttleVerdict(a, ses) : null;
      const rule = a.rule && ses.runbook && ses.runbook[a.rule - 1];
      root.replaceChildren(...[
        h("div", { class: "top" }, h("h3", { text: verb(a).replace(/^./, (c) => c.toUpperCase()) }), close),
        h("p", { class: "meta" }, `${who}, minute ${a.t0}${a.t1 > a.t0 ? ` to ${a.t1}` : ""} `, h("code", { text: `${a.tool}(${args})` })),
        v && h("p", { class: `verdict ${v[0]}`, text: v[1] }),
        // the reference: the runbook rule and the numbers behind this call
        rule && h("section", { class: "reason" }, h("h4", { text: "Why the reference does this" }),
          a.why && h("p", { text: a.why }),
          h("p", { class: "quiet" }, `Rule ${a.rule} of ${ses.runbook.length}: `, h("b", { text: rule[0] }), ` ${rule[1]}. `,
            h("button", { type: "button", class: "link", onclick: () => openSheet("runbook", true), text: "All the rules" }))),
        // the agent: what it wrote about this call in its report, and what it said at the time
        a.told && h("section", { class: "told" }, h("h4", { text: "What the task instruction said" }), h("p", {}, inline(a.told))),
        a.quote && h("section", { class: "reason" }, h("h4", { text: "In its own words, after the shift" }), h("p", { text: `“${a.quote}”` })),
        said && h("section", {}, h("h4", { text: a.say ? "What it said at the time" : "Its reasoning summary at the time" }), prose(said)),
        h("section", {}, h("h4", { text: "What it saw" }), seen(a)),
      ].filter(Boolean));
    }
    root.scrollTop = 0;
  }

  // --- sheets and onboarding ------------------------------------------------------------

  function openSheet(id, open) {
    const el = $(`#${id}`), button = $(`#open-${id}`);
    el.hidden = open == null ? !el.hidden : !open;
    if (button) button.setAttribute("aria-expanded", String(!el.hidden));
  }

  // the dismissal is remembered where the browser allows it; without storage the intro shows each visit
  const seenIntro = () => { try { return localStorage.getItem("replay-intro") === "seen"; } catch (e) { return false; } };
  const markIntro = () => { try { localStorage.setItem("replay-intro", "seen"); } catch (e) { /* private mode: nothing to remember */ } };

  function openIntro(thenPlay) {
    const dialog = $("#onboard"), ses = state.ses, head = ses.headline;
    $("#onboard-result").textContent = head
      ? `${head.label} averages ${head.mean.toFixed(2)} of the expert's savings on this level, over ${head.count} runs.`
      : `The score is the share of the expert's savings a run reaches.`;
    $("#onboard-watch").textContent = ses.rules.storms
      ? "The red services, the money counter, and the moment the agent rolls back without protecting first."
      : "The red services, the money counter, and where the two runs part.";
    const was = state.playing;
    setPlaying(false);
    dialog.onclose = () => { markIntro(); setPlaying(thenPlay || was); paint(); };
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
  }

  // --- playback ----------------------------------------------------------------------

  function setPlaying(on) {
    if (!on) {  // whatever stopped it: the page rests on a whole minute and shows that minute exactly
      state.T = Math.floor(state.T + 1e-9);
      state.entered = null;
      state.settle = false;
      state.exact = true;
    }
    state.playing = on;
    document.body.classList.toggle("paused", !on);
    $("#play").setAttribute("aria-label", on ? "Pause" : "Play");
    $("#play-icon").setAttribute("d", on ? "M5 4h4v12H5zM11 4h4v12h-4z" : "M6 4l10 6-10 6z");
  }

  function seek(T, keepPin) {
    state.T = clamp(Math.round(T), -state.ses.pre, state.ses.horizon);  // scrubbing moves by whole minutes
    state.entered = null;
    if (!keepPin) state.pin = null;
    paint();
  }

  function select(side, i) {
    const run = side === "ref" ? state.ref : state.run;
    state.pin = { side, i };
    setPlaying(false);
    state.T = i === "report" ? state.ses.horizon : run.actions[i].t0;
    paint();
    renderInspector(true);
  }

  let clockText = "";
  function paint() {
    const ses = state.ses, T = state.T, exact = state.exact;
    state.exact = false;
    panels.agent.paint(T, exact);
    panels.ref.paint(T, exact);
    if (track) track.paint(T);
    const m = Math.floor(T);
    const text = T < 0 ? `${-m} min before the page` : T >= ses.horizon ? "Shift over" : `Minute ${m}`;
    if (text !== clockText) {
      clockText = text;
      $("#clock").replaceChildren(text, h("span", { text: T < 0 || T >= ses.horizon ? "" : `of ${ses.horizon}` }));
    }
    renderInspector(false);
  }

  function renderAll() {
    renderBar();
    $("#to-moment").hidden = !state.run.actions.some((a) => a.label);
    panels.agent.build();
    panels.ref.build();
    buildTrack();
    shownKey = null;
    paint();
  }

  function start() {
    if (!sessions.length) {
      document.body.classList.remove("loading");
      document.body.replaceChildren(h("p", { style: "padding:2rem", text: "No runs found. Run `python3 export.py --level 4 --seeds 109` in this folder, then reload." }));
      return;
    }
    if (params.has("still")) document.documentElement.classList.add("still");  // no motion: for screenshots
    renderSpread();
    const bySeed = params.has("seed") && sessions.find((x) => String(x.seed) === params.get("seed")
      && (!params.has("level") || String(x.level) === params.get("level")));
    chooseSession(bySeed ? bySeed.key : params.get("session"));
    const zoom = parseFloat(params.get("zoom"));  // larger type for a screen recording
    if (zoom > 0) document.documentElement.style.fontSize = `calc(clamp(12.5px, 0.83vw, 18px) * ${zoom})`;
    remPx = 0;
    panels.agent = makePanel($("#panel-agent"), "agent");
    panels.ref = makePanel($("#panel-ref"), "ref");
    if (params.has("t")) state.T = clamp(Math.round(parseFloat(params.get("t"))), -state.ses.pre, state.ses.horizon);
    state.speed = parseFloat(params.get("speed")) || 1;
    const seconds = parseFloat(params.get("seconds"));  // play what is left of the shift in this many seconds
    if (seconds > 0) state.speed = (state.ses.horizon - state.T) / (RATE * seconds);
    if (![...$("#speed").options].some((o) => parseFloat(o.value) === state.speed)) {
      $("#speed").append(h("option", { value: String(state.speed), text: `${+state.speed.toFixed(2)}×` }));
    }
    $("#speed").value = String(state.speed);
    const wanted = params.get("autoplay") === "1";
    const auto = wanted || (params.has("play") ? params.get("play") !== "0" : !params.has("t") && !params.has("a"));
    // pause=key stops at the moment the agent's run turns on; pause=<minute> at that minute
    const turn = () => { const a = state.run.actions.find((x) => x.label); return a ? a.t0 + 3 : null; };
    state.pauseAt = params.get("pause") === "key" ? turn() : params.has("pause") ? parseFloat(params.get("pause")) : null;
    $("#to-moment").addEventListener("click", () => { if (turn() != null) { setPlaying(false); seek(turn()); } });
    setPlaying(false);
    state.lanes = params.get("lanes") === "1";
    document.body.classList.toggle("lanes", state.lanes);
    if (params.has("a")) {
      const side = params.get("side") === "ref" ? "ref" : "agent", i = params.get("a");
      state.pin = { side, i: i === "report" ? "report" : parseInt(i, 10) };
      if (!params.has("t")) state.T = i === "report" ? state.ses.horizon : (side === "ref" ? state.ref : state.run).actions[state.pin.i].t0;
    }
    renderAll();

    // details open on demand: the key, the reference's rules, each fault's lane, the intro
    for (const id of ["key", "runbook", "results"]) $(`#open-${id}`).addEventListener("click", () => openSheet(id));
    document.addEventListener("click", (e) => { const id = e.target.dataset && e.target.dataset.close; if (id) openSheet(id, false); });
    if (params.get("sheet")) openSheet(params.get("sheet"), true);
    $("#open-lanes").addEventListener("click", () => {
      state.lanes = !state.lanes;
      document.body.classList.toggle("lanes", state.lanes);
      $("#open-lanes").setAttribute("aria-expanded", String(state.lanes));
      $("#open-lanes").textContent = state.lanes ? "Hide the faults" : "Show each fault";
      buildTrack();
    });
    if (state.lanes) { $("#open-lanes").setAttribute("aria-expanded", "true"); $("#open-lanes").textContent = "Hide the faults"; }
    $("#open-help").addEventListener("click", () => openIntro(false));
    // first visit: say what this is before it plays. A link to a moment skips it.
    const intro = params.has("intro") ? params.get("intro") === "1" : !wanted && !seenIntro() && !params.has("t") && !params.has("a");
    // the page is drawn: take the loading notice away, and only then let it play
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.body.classList.remove("loading");
      if (intro) openIntro(auto);
      else if (auto) { setPlaying(true); paint(); }
    }));

    $("#play").addEventListener("click", () => {
      if (state.playing) {  // glide on to the next whole minute and stop there, so what stays on screen is exact
        if (Number.isInteger(state.T) || calm) setPlaying(false);
        else { state.pauseAt = Math.ceil(state.T); state.settle = true; }
        return paint();
      }
      if (state.T >= state.ses.horizon) state.T = -12;
      state.pin = null;
      setPlaying(true);
      paint();
    });
    $("#speed").addEventListener("change", (e) => (state.speed = parseFloat(e.target.value)));

    const svg = $("#track svg");
    let drag = false;
    svg.addEventListener("pointerdown", (e) => {
      const act = e.target.closest(".act");
      if (act) return select(act.dataset.side, act.dataset.i === "report" ? "report" : +act.dataset.i);
      drag = true;
      svg.setPointerCapture(e.pointerId);
      setPlaying(false);
      seek(track.time(e.clientX - svg.getBoundingClientRect().left));
    });
    svg.addEventListener("pointermove", (e) => {
      if (drag) return seek(track.time(e.clientX - svg.getBoundingClientRect().left));
      // hover a mark: what the run did there and, where known, why
      const act = e.target.closest(".act"), tip = $("#tip");
      if (!act) return void (tip.hidden = true);
      const run = act.dataset.side === "ref" ? state.ref : state.run, a = act.dataset.i === "report" ? null : run.actions[+act.dataset.i];
      const more = a && (act.dataset.side === "ref" ? a.why : a.quote && `“${a.quote}”`);
      tip.replaceChildren(...[h("b", { text: act.dataset.tip }), more && h("br"), more && h("span", { text: more })].filter(Boolean));
      tip.hidden = false;
      moveTip(e);
    });
    svg.addEventListener("pointerleave", () => ($("#tip").hidden = true));
    svg.addEventListener("pointerup", () => (drag = false));
    svg.addEventListener("pointercancel", () => (drag = false));

    addEventListener("keydown", (e) => {
      if (e.target.closest("select, input, textarea, dialog") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "Escape") { state.pin = null; renderInspector(true); for (const id of ["key", "runbook", "results"]) openSheet(id, false); }
      else if (e.key === " ") { e.preventDefault(); $("#play").click(); }
      else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const dir = e.key === "ArrowRight" ? 1 : -1;
        if (e.shiftKey) { setPlaying(false); return seek(Math.round(state.T) + 5 * dir); }
        const list = state.run.actions.filter((a) => a.kind !== "wait");
        const cur = state.pin && state.pin.side === "agent" ? list.findIndex((a) => a.i === state.pin.i) : -1;
        const next = cur >= 0 ? list[cur + dir]
          : dir > 0 ? list.find((a) => a.t0 > state.T) || list.find((a) => a.t0 >= state.T)
          : [...list].reverse().find((a) => a.t0 <= state.T);
        if (next) select("agent", next.i);
      } else if (e.key === "Home") { setPlaying(false); seek(-state.ses.pre); }
      else if (e.key === "End") { setPlaying(false); seek(state.ses.horizon); }
    });

    // redraw when a box changes size; the first report only repeats the size it was drawn at
    const sizes = new ResizeObserver((entries) => {
      const moved = entries.some((e) => e.target.dataset.built !== `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`);
      if (!moved) return;
      remPx = 0;
      panels.agent.build(); panels.ref.build(); buildTrack();
    });
    for (const box of document.querySelectorAll(".graph, #track")) sizes.observe(box);

    let last = performance.now();
    const frame = (t) => {
      const dt = Math.min(0.1, (t - last) / 1000);
      last = t;
      if (state.playing) {
        const was = state.T;
        // asked to stop: the rest of the minute goes by in a fifth of a second
        const rate = state.settle ? Math.max(RATE * state.speed, (state.pauseAt - was) / 0.2) : RATE * state.speed;
        state.T += dt * rate;
        if (Math.floor(state.T) !== Math.floor(was)) state.entered = Math.floor(state.T);  // a minute came while playing
        if (state.pauseAt != null && was < state.pauseAt && state.T >= state.pauseAt) { state.T = state.pauseAt; state.pauseAt = null; setPlaying(false); }
        if (state.T >= state.ses.horizon) { state.T = state.ses.horizon; setPlaying(false); }
        paint();
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  // labels are measured, so the face has to be there first
  (document.fonts ? document.fonts.load("1rem Archivo").catch(() => {}) : Promise.resolve()).then(loadBundles).then(start);
})();
