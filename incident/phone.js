// OnCallBench on a phone: the replay's results as a page that reads at 390 px, drawn from the same
// bundles as app.js. index.html loads this instead of app.js on a phone; "Show the laptop replay"
// reloads with ?desk=1, which gives the laptop layout zoomed out instead.
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const files = window.REPLAY_FILES || [];
  const spread = window.REPLAY_SPREAD;
  const SVG = "http://www.w3.org/2000/svg";

  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "text") node.textContent = v;
      else if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    node.append(...kids.flat().filter((k) => k != null && k !== false));
    return node;
  }
  function s(tag, attrs, ...kids) {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) node.setAttribute(k, v);
    node.append(...kids.flat().filter(Boolean));
    return node;
  }
  const money = (v) => "$" + Math.round(v).toLocaleString("en-US");
  const score = (v) => v.toFixed(2);
  const withParams = (extra) => {
    const q = new URLSearchParams(location.search);
    for (const [k, v] of Object.entries(extra)) v == null ? q.delete(k) : q.set(k, v);
    return "?" + q.toString();
  };

  // the episode the address names, else the first listed: the same one the laptop replay opens on
  const wantedSession = params.get("session");
  const file = files.find((f) => f === `${wantedSession}.js`) || files[0];
  const loaded = new Promise((done) => {
    if (!file) return done();
    document.head.append(h("script", { src: `data/${file}` }));
    document.head.lastChild.onload = done;
    document.head.lastChild.onerror = done;
  });

  Promise.all([loaded, new Promise((r) => (document.readyState === "loading" ? addEventListener("DOMContentLoaded", r) : r()))]).then(render);

  function render() {
    document.body.classList.remove("loading");
    const bundle = (window.REPLAY_BUNDLES || [])[0];
    const ses = bundle && bundle.sessions[0];
    const page = h("div", { class: "pv" });
    page.append(head());
    if (spread && spread.models && spread.models.length) page.append(across(spread));
    if (ses) page.append(...shift(ses));
    page.append(h("p", { class: "pv-foot" }, "The laptop replay plays both runs side by side on the service map, minute by minute. ",
      h("a", { href: withParams({ desk: "1" }), text: "Open it here anyway" }), "."));
    document.body.append(page);
  }

  function head() {
    const mark = s("svg", { class: "pv-mark", viewBox: "4 4 24 24", "aria-hidden": "true" },
      s("path", { class: "mark-agent", d: "M14 19 25 7" }), s("path", { d: "M6 25 14 19H26" }));
    return h("header", { class: "pv-head" },
      h("h1", {}, mark, "OnCallBench"),
      h("p", { text: "An AI agent and an expert script work the same simulated outage, minute by minute. Every failed request at a customer-facing service costs revenue." }),
      h("div", { class: "pv-note" },
        h("p", { text: "The animated replay is made for a laptop screen, sorry. Here is what it shows." }),
        h("a", { class: "pv-btn", href: withParams({ desk: "1" }), text: "Show the laptop replay" })));
  }

  // every run on the common seeds: a dot each, the mean and its 95% interval, 0 and 1 marked
  function across(data) {
    const m = data.models[0];
    const W = 340, H = 64, x = (v) => 12 + v * (W - 24);
    const dots = m.runs.map((r, i) => s("circle", { cx: x(r.score), cy: 22 + ((i * 7) % 15) - 7, r: 4, class: "pv-dot" }));
    const strip = s("svg", { class: "pv-strip", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${m.n} runs; mean ${score(m.mean)}` },
      s("line", { x1: x(0), x2: x(1), y1: 22, y2: 22, class: "pv-axis" }),
      s("line", { x1: x(1), x2: x(1), y1: 8, y2: 36, class: "pv-ref" }),
      ...dots,
      s("line", { x1: x(m.low), x2: x(m.high), y1: 22, y2: 22, class: "pv-ci" }),
      s("line", { x1: x(m.mean), x2: x(m.mean), y1: 12, y2: 32, class: "pv-mean" }),
      s("text", { x: x(0), y: 56, class: "pv-tick", "text-anchor": "start" }, "0 doing nothing"),
      s("text", { x: x(1), y: 56, class: "pv-tick", "text-anchor": "end" }, "1 the expert"));
    return h("section", { class: "pv-card" },
      h("h2", { text: `Across ${m.n} runs` }),
      h("p", { class: "pv-big" }, h("b", { text: score(m.mean) }), ` ${m.label}'s mean score, as a share of what the expert script saves`),
      strip,
      h("p", { class: "pv-small", text: `${data.caption} 95% interval ${score(m.low)} to ${score(m.high)}.` }));
  }

  function shift(ses) {
    const ref = ses.runs.find((r) => r.id === "reference");
    const others = ses.runs.filter((r) => r !== ref);
    const wanted = params.get("run");
    const run = others.find((r) => r.id === wanted) || others.find((r) => r.kind === "trial" && /opus/i.test(r.id)) || others[0];
    const name = (a) => (a.args && a.args.service) || (ses.services[a.service] || {}).name || "";
    const trials = others.filter((r) => r.kind === "trial");
    const runName = (r) => r === ref ? "Expert script" : (trials.filter((t) => t.label === r.label).length > 1 ? `${r.label}, run ${trials.filter((t) => t.label === r.label).indexOf(r) + 1}` : r.label);

    // cumulative revenue lost, minute by minute: the featured run against the reference
    const cum = (r) => { const out = [0]; for (let t = 0; t < ses.horizon; t++) out.push(out[t] + r.loss[t + ses.pre]); return out; };
    const a = cum(run), b = cum(ref);
    const W = 340, H = 170, top = Math.max(a[a.length - 1], b[b.length - 1]) || 1;
    const px = (t) => 8 + (t / ses.horizon) * (W - 16), py = (v) => H - 22 - (v / top) * (H - 40);
    const line = (c) => c.map((v, t) => `${t ? "L" : "M"}${px(t).toFixed(1)},${py(v).toFixed(1)}`).join("");
    const chart = s("svg", { class: "pv-chart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Revenue lost over the shift: ${runName(run)} ${money(a[a.length - 1])}, the expert script ${money(b[b.length - 1])}` },
      s("line", { x1: px(0), x2: px(ses.horizon), y1: py(0), y2: py(0), class: "pv-axis" }),
      ...[0, 30, 60, 90, 120].map((t) => s("text", { x: px(t), y: H - 6, class: "pv-tick", "text-anchor": t === 0 ? "start" : t === 120 ? "end" : "middle" }, t === 0 ? "paged" : `${t} min`)),
      s("path", { d: line(b), class: "pv-line-ref" }),
      s("path", { d: line(a), class: "pv-line-run" }),
      s("text", { x: px(ses.horizon) - 2, y: py(a[a.length - 1]) - 6, class: "pv-end pv-end-run", "text-anchor": "end" }, money(a[a.length - 1])),
      s("text", { x: px(ses.horizon) - 2, y: py(b[b.length - 1]) - 6, class: "pv-end", "text-anchor": "end" }, money(b[b.length - 1])));

    const rows = [ref, ...others.filter((r) => r.kind === "trial")].map((r) =>
      h("tr", { class: r === run ? "pv-on" : r === ref ? "pv-reference" : null },
        h("th", {}, r === ref || r === run ? runName(r) : h("a", { href: withParams({ run: r.id }), text: runName(r) })),
        h("td", { text: score(r.score) }),
        h("td", { text: money(r.cost.total) })));
    rows.push(h("tr", {}, h("th", { text: "Doing nothing" }), h("td", { text: "0.00" }), h("td", { text: money(ses.cost_null) })));
    const table = h("table", { class: "pv-table" },
      h("thead", {}, h("tr", {}, h("th", { text: "Run" }), h("th", { text: "Score" }), h("th", { text: "Total cost" }))),
      h("tbody", {}, rows));

    // what each did, in order: fixes, give-backs and throttles, with the reference's reasons
    const steps = (r) => {
      const list = (r.actions || []).filter((x) => x.kind === "mitigation").map((x) => ({
        t: x.t1, what: `${x.tool.replace(/_/g, " ")} ${name(x)}${x.args && x.args.replicas ? ` to ${x.args.replicas} replicas` : ""}`, why: x.why, wasted: x.wasted,
      }));
      for (const th of r.throttles || []) list.push({ t: th.span[0], what: `throttle ${(ses.services[th.service] || {}).name || ""} at ${th.percent}% until minute ${th.span[1]}` });
      return list.sort((p, q) => p.t - q.t);
    };
    const stepList = (r) => h("ol", { class: "pv-steps" }, steps(r).map((x) =>
      h("li", {}, h("span", { class: "pv-min", text: `min ${x.t}` }), h("span", {}, h("b", { text: x.what }), x.why ? h("small", { text: x.why }) : null))));

    const sections = [
      h("section", { class: "pv-card" },
        h("h2", { text: `One shift: ${ses.title}` }),
        run.note && run.note.what ? h("p", { text: run.note.what }) : null,
        h("div", { class: "pv-legend" }, h("span", { class: "pv-key-run", text: runName(run) }), h("span", { class: "pv-key-ref", text: "Expert script" })),
        chart,
        h("p", { class: "pv-small", text: "Revenue lost so far, from the page at minute 0 to the end of the shift." }),
        table,
        h("p", { class: "pv-small", text: "Total cost is the revenue lost plus the replicas a run added. A score is the share of the avoidable cost it avoided: the expert script scores 1, doing nothing 0." })),
      h("section", { class: "pv-card" },
        h("h2", { text: "What each did" }),
        h("h3", { text: runName(run) }), stepList(run),
        h("h3", { text: "Expert script" }), ref.note && ref.note.what ? h("p", { class: "pv-small", text: ref.note.what }) : null, stepList(ref)),
    ];
    if (run.report) {
      sections.push(h("section", { class: "pv-card" },
        h("h2", { text: "In its own words" }),
        h("details", { class: "pv-report" }, h("summary", { text: `${runName(run)}'s closing report` }), ...run.report.split(/\n{2,}/).map((p) => h("p", { text: p })))));
    }
    if (ses.runbook) {
      sections.push(h("section", { class: "pv-card" },
        h("h2", { text: "How the expert script decides" }),
        h("ol", { class: "pv-runbook" }, ses.runbook.map(([verb, rest]) => h("li", {}, h("b", { text: verb }), " ", rest)))));
    }
    if (files.length > 1) {
      sections.push(h("nav", { class: "pv-other" }, h("span", { text: "Other shifts: " }),
        ...files.filter((f) => f !== file).map((f, i) => [i ? ", " : "", h("a", { href: withParams({ session: f.replace(/\.js$/, ""), run: null }), text: f.replace(/\.js$/, "").replace(/^l(\d+)-s/, "level $1, seed ") })])));
    }
    return sections;
  }
})();
