"""Fill report result blocks and a standalone distribution chart from committed audit evidence."""

import csv
import json
import re

from check import HERE

rows = [json.loads(line) for line in (HERE / "generality.jsonl").read_text().splitlines()]
assert len(rows) == 200 and [r["seed"] for r in rows] == list(range(1000, 1200))
summary = json.loads((HERE / "generality-summary.json").read_text())
details = json.loads((HERE / "counterexamples.json").read_text())
(HERE / "counterexamples.json").write_text("[\n" + ",\n".join(json.dumps(row, sort_keys=True) for row in details) + "\n]\n")
for path in HERE.glob("*-console.log"):
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()).rstrip() + "\n")
bad = [r for r in rows if r["reference_oracle"] < .75 or r["cost_ref"] > r["cost_null"]]
assert [r["seed"] for r in bad] == [r["seed"] for r in details]
by_seed = {r["seed"]: r for r in rows}
harbor = json.loads((HERE / "harbor-results.json").read_text())
assert harbor["trials"] == 27
assert not any(harbor[k] for k in ("cost_mismatches", "score_mismatches", "receipt_mismatches", "errors"))


def table(headers, lines):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in lines])


def percentage(x):
    return f"{100*x:.2f}%"


dist = summary["reference_oracle"]
finding = (f"**{len(summary['below_075'])}/200 seeds ({len(summary['below_075'])/2:.1f}%) fall below 0.75 "
           f"of the shipped oracle's avoided cost.** The mean is {dist['mean']:.4f}, median {dist['median']:.4f}, "
           f"and range {dist['min']:.4f}–{dist['max']:.4f}. "
           f"The reference costs more than doing nothing on **{len(summary['worse_than_nothing'])}/200** seeds. "
           "Thus the sampled build/held-out range is not a valid lower bound on new estates.")

distributions = table(["Statistic", "Reference / oracle avoided cost"],
                      [(key, f"{dist[key]:.4f}") for key in
                       ("min", "p05", "p25", "median", "mean", "p75", "p95", "max")])
policy_table = table(["Policy", "Min", "Median", "Mean", "Max"],
                     [(name, *[f"{stats[key]:.4f}" for key in ("min", "median", "mean", "max")])
                      for name, stats in summary["policies"].items()])
counter_lines = []
counter_policies = ["stop-early", "exploiter", "shotgun", "no-drain", "unprotected", "forgetful", "alerts-only", "no-late", "surge-responder"]
for detail in details:
    faults = detail["faults"]
    def fixed(f):
        if f["kind"] == "overload":
            scales = [e["result"]["completes_at_minute"] for e in detail["mitigations"]
                      if e["tool"] == "scale" and e["args"]["service"] == f["service"] and e["result"].get("ok")]
            return str(min(scales)) if scales else "not scaled"
        return str(f["end"]) if f["end"] is not None else "MISSED"
    remaining = [f for f in faults if f["end"] is None and f["kind"] != "overload"]
    edges_bad = [e for e in detail["edges_at_end"] if e["error_rate"] > .01]
    if remaining:
        reason = "Never finds " + ", ".join(f["service"] for f in remaining) + "; truncated alerts / single-path tracing"
    elif edges_bad:
        reason = "Causes treated, but customer errors remain; residual overload/retries: " + ", ".join(
            r["service"] for r in detail["residual_own"])
    else:
        reason = "All causes treated; time lost in diagnosis/protection (fix times shown)"
    quiet = next(f for f in faults if f.get("gray"))
    late = next(f for f in faults if f["start"] >= 0)
    initial = [f for f in faults if not f.get("gray") and f["start"] < 0]
    counter_lines.append([detail["seed"], f"{detail['ratio']:.4f}",
                          "; ".join(f"{f['service']} {fixed(f)}" for f in initial),
                          f"{quiet['service']} {fixed(quiet)}", f"{late['start']} → {fixed(late)}", reason])

with (HERE / "counterexample-scores.csv").open("w", newline="") as output:
    writer = csv.writer(output, lineterminator="\n")
    names = list(summary["policies"])
    writer.writerow(["seed", "reference_oracle", "cost_null", "cost_ref", "cost_oracle"] + names)
    for row in bad:
        writer.writerow([row[k] for k in ("seed", "reference_oracle", "cost_null", "cost_ref", "cost_oracle")] +
                        [row["score"][name] for name in names])

counter_table = table(["Seed", "Ratio", "Initial loud causes: fix/scale minute", "Quiet fix minute", "Late start → fix", "Why below bar"], counter_lines)
scores = table(["Seed"] + counter_policies, [[r["seed"]] + [f"{r['score'][p]:.4f}" for p in counter_policies] for r in bad])
generality = (distributions + "\n\n**Worse than do-nothing seeds:** " +
              (", ".join(map(str, summary["worse_than_nothing"])) or "none") + ".\n\n" +
              "All-policy score distribution across all 200 seeds (the benchmark score clipped to 0–1):\n\n" + policy_table +
              "\n\nEvery seed below 0.75, or worse than doing nothing, with its specific mitigation timing:\n\n" + counter_table +
              "\n\nCheap-policy scores on **each** of those seeds:\n\n" + scores +
              "\n\n[counterexample-scores.csv](counterexample-scores.csv) contains all 17 policies on every counterexample, "
              "including one-fix, thorough, trusting, loudest-first and the file-policy aliases. "
              "Fix/scale times are completion times, not the minute diagnosis begins; an overload's first successful "
              "scale is shown even if a later correction was needed. Cost components, including wasted fines, "
              "and raw tool-query evidence are retained in counterexamples.json.")

selected = [r for r in harbor["rows"] if r["repeat"] == 1]
harbor_table = table(["Seed", "Policy", "In-process cost", "Harbor cost (all 3)", "Score (all 3)"],
                     [(r["seed"], r["policy"], f"${r['expected']['cost']:,.2f}",
                       f"${r['actual']['cost_total']:,.2f}", f"{r['actual']['reward']:.2f}") for r in selected])
harbor_text = ("**27/27 trials matched in-process cost, score and signed receipt byte content; zero mismatches, "
               "timeouts, MCP startup failures or verifier errors.** The JSON receipt comparison ignores serialization "
               "whitespace while preserving every action, argument and signature.\n\n" + harbor_table +
               "\n\n[harbor-results.json](harbor-results.json) records every repetition; [evidence/](evidence/) holds "
               "an individual comparison per trial. Host evaluation used Python 3.14.10; the sidecar/verifier used "
               "the declared Python 3.12 images. Docker server was 29.9.2. This is a small reliability sample and does "
               "not exercise OpenCode installation or model latency.")
bare_text = ("A model-free Harbor `nop` run against the unmodified captured `task/` reproduced "
             "`FileNotFoundError: /tests/calibration.json`, followed by **RewardFileEmptyError**. "
             "[evidence/bare-verifier.txt](evidence/bare-verifier.txt) contains the full verifier errors; "
             "[evidence/bare-result.json](evidence/bare-result.json) records Harbor's exception. "
             "The 27 generated-variant runs did not have this failure.")
path = HERE / "REPORT.md"
report = path.read_text()
for name, replacement in dict(GENERALITY_FINDING=finding, GENERALITY_TABLES=generality,
                              HARBOR_RESULTS=harbor_text, BARE_TASK_RESULT=bare_text).items():
    marker = f"<!-- {name} -->"
    report = re.sub(re.escape(marker) + r".*?" + re.escape(f"<!-- END_{name} -->"),
                    lambda _: marker, report, flags=re.S)
    report = report.replace(marker, marker + "\n" + replacement + f"\n<!-- END_{name} -->")
path.write_text(report)

# Dependency-free SVG histogram, embedded in a standalone HTML artifact.
edges = [i / 20 for i in range(6, 19)]
bins = [sum(lo <= r["reference_oracle"] < hi for r in rows) for lo, hi in zip(edges, edges[1:])]
maximum = max(bins)
svg = ['<svg viewBox="0 0 700 260" role="img" aria-label="Distribution of reference avoided cost relative to the shipped oracle">']
for i, count in enumerate(bins):
    lo, hi = edges[i:i+2]
    x, width, height = 44 + 52 * i, 40, count / maximum * 170
    color = "var(--destructive,#bc4a45)" if hi <= .75 else "var(--chart-1,#4784ce)"
    svg.append(f'<rect x="{x}" y="{208-height}" width="{width}" height="{height}" fill="{color}"><title>{lo:.2f}–{hi:.2f}: {count} seeds</title></rect>')
    svg.append(f'<text x="{x+20}" y="{200-height}" text-anchor="middle">{count}</text>')
    svg.append(f'<text x="{x+20}" y="230" text-anchor="middle" font-size="11">{lo:.2f}</text>')
cut_x = 44 + (0.75 - .3) / .05 * 52 - 6
svg.append(f'<path d="M{cut_x} 15 V213" stroke="var(--warning,#ba7b25)" stroke-width="2" stroke-dasharray="4 4"/>')
svg.append(f'<text x="{cut_x-6}" y="16" text-anchor="end">0.75 bar</text>')
svg.append('<text x="350" y="254" text-anchor="middle">Share of oracle avoided cost (bin lower bound)</text></svg>')
chart = ("<!doctype html><html><head><meta charset='utf-8'><style>"
         ":root{font-family:var(--font-sans,system-ui)}svg{display:block;width:100%;height:260px}"
         "text{fill:var(--foreground);font-family:var(--font-sans,system-ui);font-size:12px}"
         "p{margin:8px 0;color:var(--muted-foreground)}strong{color:var(--foreground)}"
         "</style></head><body>"
         f"<p><strong>{len(summary['below_075'])} of 200 fresh seeds below the 0.75 bar</strong> · level 4 · seeds 1000–1199</p>" +
         "".join(svg) + f"<p>Mean {dist['mean']:.3f} · median {dist['median']:.3f} · "
         f"range {dist['min']:.3f}–{dist['max']:.3f} · worse than do-nothing: {len(summary['worse_than_nothing'])}</p>"
         "</body></html>")
(HERE / "generality.html").write_text(chart)
print(json.dumps(dict(seeds=len(rows), below_075=len(bad), harbor_trials=harbor["trials"])))
