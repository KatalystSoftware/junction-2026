"""Audit of an SFT result: does it read the incident or recite the reference's routine?

    python3 audit.py seeds                          # are nearby seeds different incidents?
    python3 audit.py replay                         # the reference's script from seed A, played on seed B
    python3 audit.py behaviour out/eval-X.jsonl     # what the model's own episodes did, against the planted faults
    python3 audit.py probes out/eval-X.jsonl        # counterfactual prefixes -> cache/probes.jsonl
    python3 run.py ... ; python3 audit.py complete --adapter ckpt/gemma26-sft --tag T   # GPU: next action, base and SFT
    python3 audit.py probe-report out/probes-T.jsonl
    python3 audit.py lora ckpt/gemma26-sft          # per-layer size of the adapter's update -> out/lora-*.png
    python3 audit.py lora-diff ckpt/gemma26-rl ckpt/gemma26-sft   # how far RL moved the SFT update

Set AQ_SIM/AQ_TASK to the pinned simulator, as for run.py.
"""

import difflib
import json
import random
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import env
from env import incident, policies

HERE = Path(__file__).resolve().parent
RIGHT = {"bad_deploy": "rollback", "leak": "rollback", "bad_config": "revert_config", "primary_down": "failover",
         "overload": "scale"}
UNDO = ("rollback", "revert_config", "restart", "failover")
CALL = re.compile(r"<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>", re.S)
RESP = re.compile(r'response:(\w+)\{value:<\|"\|>(.*?)<\|"\|>\}<tool_response\|>', re.S)


def faults(seed, level):
    return {f["service"]: f for f in incident.scenario(seed, level)["faults"]}


def mean_se(xs):
    return f"{st.mean(xs):.3f} ± {st.stdev(xs) / len(xs) ** 0.5:.3f} (n={len(xs)})" if len(xs) > 1 else str(xs)


def cmd_seeds():
    """Nearby seeds draw from independent RNG streams (the seed is hashed as a string): show it."""
    prev = None
    for seed in [*range(100, 111), 200000, 200001, 999999]:
        sc = incident.scenario(seed, 4)
        fs = [(f["kind"], f["service"]) for f in sc["faults"]]
        apps = {n for n, s in sc["svc"].items() if s["tier"] != "edge"}
        top = max(sc["edges"], key=lambda e: sc["svc"][e]["revenue"])
        same = f"shared services with seed-1: {len(apps & prev) / len(apps | prev):.2f}" if prev else ""
        print(seed, top, fs, same)
        prev = apps
    demo = [s for s in [*range(1, 13), *range(200, 400)]]
    seen = Counter((f["kind"], n) for s in demo for n, f in faults(s, 4).items())
    for name, seeds in (("held-out 101-106", range(101, 107)), ("fresh 200000-200023", range(200000, 200024))):
        fs = [(f["kind"], n) for s in seeds for n, f in faults(s, 4).items()]
        print(f"{name}: {sum(seen[x] > 0 for x in fs)}/{len(fs)} faults (kind, service) also planted in some demo seed; "
              f"identical full fault sets with a demo seed: "
              f"{sum(any(set(faults(s, 4)) == set(faults(d, 4)) for d in demo) for s in seeds)}")


def play(seed, level, calls):
    est = incident.Estate(seed, level)
    ok = 0
    for tool, args in calls:
        if est.done:
            break
        ok += bool(est.call(tool, dict(args)).get("ok"))
    est.finish()
    null, ref = env.anchors(seed, level)
    return (null - est.total_cost()) / (null - ref), ok


def cmd_replay(level=4):
    """Seed A's reference calls, unchanged, on seed B; and the simulator's non-reading baselines on B."""
    from demos import reference_log

    targets = [*range(101, 107), *range(200000, 200014)]
    rng = random.Random(0)
    rows = []
    for b in targets:
        a = rng.choice([s for s in range(200, 400)])
        log = [(t, a_) for t, a_, _ in reference_log(a, level, 10)]
        mit = [(t, a_) for t, a_ in log if t in incident.MITIGATIONS or t in ("throttle", "wait", "finish")]
        own = [(t, a_) for t, a_, _ in reference_log(b, level, 10)]
        rows.append(dict(a=a, b=b, script=play(b, level, log)[0], acts=play(b, level, mit)[0], own=play(b, level, own)[0],
                         hit=sum(a_.get("service") in faults(b, level) for t, a_ in mit if t in UNDO),
                         undos=sum(t in UNDO for t, _ in mit)))
    for r in rows:
        print(f"A={r['a']:>3} -> B={r['b']:>6}: script {r['script']:+.3f}  mitigations-only {r['acts']:+.3f}  "
              f"B's own reference {r['own']:.3f}  undos on a B fault {r['hit']}/{r['undos']}")
    for k in ("script", "acts", "own"):
        xs = [r[k] for r in rows]
        print(f"{k}: raw {mean_se(xs)}  clipped score {st.mean(max(0, min(1, x)) for x in xs):.3f}")
    print("baselines on the same B seeds (clipped score):")
    for name in ("nothing", "stop_early", "one_fix", "alerts_only", "shotgun", "reference"):
        xs = []
        for b in targets:
            est = incident.Estate(b, level)
            getattr(policies, name)(lambda tool, **a: est.call(tool, a))
            est.finish()
            xs.append(incident.score(est.total_cost(), *env.anchors(b, level)))
        print(f"  {name}: {mean_se(xs)}")


ARG = re.compile(r'(\w+):(?:<\|"\|>(.*?)<\|"\|>|([^,]*))', re.S)


def args_of(text):
    return {k: q or b for k, q, b in ARG.findall(text)}


def calls_of(text):
    return [(m[1], args_of(m[2])) for m in CALL.finditer(text)]


def cmd_behaviour(path):
    rows = [json.loads(line) for line in open(path)]
    for level in sorted({r["level"] for r in rows}):
        rs = [r for r in rows if r["level"] == level]
        prec, rec, diff_first, seen_first, cross = [], [], [], [], []
        skel = defaultdict(list)
        for r in rs:
            fs = faults(r["seed"], level)
            calls = calls_of(r["text"])
            skel[r["seed"]].append([t for t, _ in calls])
            mits = [(t, a.get("service")) for t, a in calls if t in UNDO]
            if mits:
                prec.append(sum(s in fs for _, s in mits) / len(mits))
            rec.append(sum(any(t == RIGHT.get(f["kind"]) and s == n for t, s in mits) for n, f in fs.items()) / len(fs))
            others = {n for s in {x["seed"] for x in rs} if s != r["seed"] for n in faults(s, level)} - set(fs)
            cross += [s in others for _, s in mits]
            for i, (t, a) in enumerate(calls):
                if t in ("rollback", "revert_config"):
                    diff_first.append(any(t2 == "get_diff" and a2.get("service") == a.get("service") for t2, a2 in calls[:i]))
            first = next((i for i, (t, _) in enumerate(calls) if t in UNDO), None)
            if first is not None:  # the first mitigated service was named in an observation before (not topology)
                svc = calls[first][1].get("service")
                before = r["text"][:[m.start() for m in CALL.finditer(r["text"])][first]]
                obs = " ".join(v for k, v in RESP.findall(before) if k != "get_topology")
                seen_first.append(svc in obs)
        within = [difflib.SequenceMatcher(None, x, y).ratio() for ss in skel.values() for i, x in enumerate(ss)
                  for y in ss[i + 1:]]
        seeds = list(skel)
        across = [difflib.SequenceMatcher(None, x, y).ratio() for i, s in enumerate(seeds) for t in seeds[i + 1:]
                  for x in skel[s][:3] for y in skel[t][:3]]
        ended = Counter(r["ended"] for r in rs)
        print(f"level {level}: n={len(rs)} reward {mean_se([r['reward'] for r in rs])} ended {dict(ended)}")
        print(f"  undo/restart/failover precision (on a planted fault) {mean_se(prec)}; fault recall with the right "
              f"tool {mean_se(rec)}")
        print(f"  rollbacks/reverts preceded by get_diff of that service: {sum(diff_first)}/{len(diff_first)}; "
              f"first mitigation on a service an observation named: {sum(seen_first)}/{len(seen_first)}")
        print(f"  mitigations on a service that is a fault in another eval seed but not this one: {sum(cross)}/{len(cross)}")
        print(f"  call-sequence similarity (difflib ratio): same seed {st.mean(within):.2f}, different seeds "
              f"{st.mean(across):.2f}")
        for why in ended:
            sub = [r for r in rs if r["ended"] == why]
            mins = [max([int(m) for m in re.findall(r'"minute":(\d+)', r["text"])] or [0]) for r in sub]
            cpr = [len(calls_of(r["text"])) / max(1, r["turns"]) for r in sub]
            waits = [sum(t == "wait" for t, _ in calls_of(r["text"])) for r in sub]
            qs = [sum(t in incident.Estate.QUERIES for t, _ in calls_of(r["text"])) for r in sub]
            print(f"  ended {why}: reward {st.mean(r['reward'] for r in sub):.3f}, last minute seen "
                  f"{st.mean(mins):.0f}, replies {st.mean(r['turns'] for r in sub):.1f}, calls/reply {st.mean(cpr):.2f}, "
                  f"queries {st.mean(qs):.1f}, waits {st.mean(waits):.1f}")


# --- counterfactual probes ---------------------------------------------------------------------

HUNKS = [h for _, d, c in incident.FLAVOURS for h in (d, c)]


def reply_start(text, pos):
    """Where the model's reply that contains position `pos` begins."""
    ends = [m.end() for m in re.finditer(r"<tool_response\|>", text[:pos])]
    starts = [e for e in ends if not text[e:].startswith("<|tool_response>")]
    return starts[-1] if starts else 0


def swap_names(text, x, y):
    return re.sub(rf"(?<![\w-])({re.escape(x)}|{re.escape(y)})(?![\w-])", lambda m: y if m[1] == x else x, text)


def edit_response(text, tool, service, fn):
    """Apply fn to the JSON of the last `tool` response about `service` in text; None if there is none."""
    hits = [m for m in RESP.finditer(text) if m[1] == tool and f'"service":"{service}"' in m[2]]
    if not hits:
        return None
    m = hits[-1]
    new = fn(json.loads(m[2]))
    if new is None:
        return None
    return text[:m.start(2)] + env.dumps(new) + text[m.end(2):]


def benign_diff(d):
    lines, out, skip = d["diff"].split("\n"), [], 0
    hunks = [h.split("\n") for h in HUNKS]
    i = 0
    while i < len(lines):
        h = next((h for h in hunks if lines[i:i + len(h)] == h), None)
        if h:
            i += len(h)
            skip += 1
        else:
            out.append(lines[i])
            i += 1
    return dict(d, diff="\n".join(out)) if skip and out else None


def calm_metrics(d):
    return dict(d, series=[dict(p, cpu=min(p["cpu"], 0.4), retry_share=0.0, error_rate=min(p["error_rate"], 0.001))
                           for p in d["series"]])


def cmd_probes(path, n=10, out=HERE / "cache" / "probes.jsonl"):
    n, out = int(n), Path(out)
    rows = [json.loads(line) for line in open(path) if json.loads(line)["level"] == 4]
    rng = random.Random(0)
    by_seed = defaultdict(list)
    for r in rows:
        by_seed[r["seed"]].append(r)
    picked = []
    while len(picked) < n and any(by_seed.values()):  # round robin over seeds, best reward first
        for s in sorted(by_seed):
            if by_seed[s] and len(picked) < n:
                by_seed[s].sort(key=lambda r: -r["reward"])
                picked.append(by_seed[s].pop(0))
    probes = []
    for k, r in enumerate(picked):
        text, sc = r["text"], incident.scenario(r["seed"], 4)
        ms = [(m, m[1], args_of(m[2])) for m in CALL.finditer(text)]
        mits = [(m, t, a) for m, t, a in ms if t in incident.MITIGATIONS]
        if mits:  # first mitigation: a different service is the one everything points at
            m, t, a = mits[0]
            x = a["service"]
            pre = text[:reply_start(text, m.start())]
            tier = sc["svc"][x]["tier"]
            seen = " ".join(v for k_, v in RESP.findall(pre) if k_ != "get_topology") + " ".join(
                str(a_) for _, a_ in calls_of(pre))  # Y: a healthy service nothing so far looked at
            ys = [n for n, s in sc["svc"].items() if s["tier"] == tier and n != x and n not in faults(r["seed"], 4)
                  and not re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", seen)]
            y = rng.choice(ys)
            probes.append(dict(id=f"{k}-swap", kind="swap", seed=r["seed"], tool=t, x=x, y=y, orig=pre,
                               edit=swap_names(pre, x, y)))
        for m, t, a in mits:  # an undo after reading the diff: the diff no longer shows the harmful hunk
            if t in ("rollback", "revert_config"):
                pre = text[:reply_start(text, m.start())]
                ed = edit_response(pre, "get_diff", a["service"], benign_diff)
                if ed:
                    probes.append(dict(id=f"{k}-diff", kind="diff", seed=r["seed"], tool=t, x=a["service"], orig=pre, edit=ed))
                    break
        for m, t, a in mits:  # a scale-up after reading metrics: the metrics are calm
            if t == "scale":
                pre = text[:reply_start(text, m.start())]
                ed = edit_response(pre, "get_metrics", a["service"], calm_metrics)
                if ed:
                    probes.append(dict(id=f"{k}-scale", kind="scale", seed=r["seed"], tool=t, x=a["service"], orig=pre, edit=ed))
                    break
    with open(out, "w") as f:
        for p in probes:
            f.write(json.dumps(p) + "\n")
    print(f"{len(probes)} probes from {len(picked)} episodes: {Counter(p['kind'] for p in probes)} -> {out}")


def cmd_complete(argv):
    """GPU: greedy next reply for every probe prefix, edited and not, with the base model then with the adapter."""
    import argparse

    import core
    import run

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemma-4-26B-A4B-it")
    ap.add_argument("--adapter")
    ap.add_argument("--lora", type=int, default=32)
    ap.add_argument("--probes", default=str(HERE / "cache" / "probes.jsonl"))
    ap.add_argument("--tag", required=True)
    o = ap.parse_args(argv)
    from transformers import AutoTokenizer
    from vllm import SamplingParams, TokensPrompt

    path = run.resolve(o.model)
    chat = core.make_chat(AutoTokenizer.from_pretrained(path))
    llm = run.engine(path, 0.85, 32768)
    probes = [json.loads(line) for line in open(o.probes)]
    prompts = [TokensPrompt(prompt_token_ids=chat.prompt(4) + chat.encode(p[v])) for p in probes for v in ("orig", "edit")]
    sp = SamplingParams(temperature=0.0, max_tokens=384, stop_token_ids=chat.stop)
    out = []
    for model in ("base", "sft"):
        if model == "sft":
            m, _ = run.trainer(path, 0.0, o.lora, "cuda:1", o.adapter)
            core.sync(m, llm)
            del m
        res = llm.generate(prompts, sp, use_tqdm=False)
        for i, p in enumerate(probes):
            for j, v in enumerate(("orig", "edit")):
                out.append(dict(id=p["id"], kind=p["kind"], model=model, variant=v, tool=p["tool"], x=p["x"], y=p.get("y"),
                                reply=chat.decode(list(res[2 * i + j].outputs[0].token_ids))))
    (HERE / "out").mkdir(exist_ok=True)
    with open(HERE / "out" / f"probes-{o.tag}.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"{len(out)} completions -> out/probes-{o.tag}.jsonl")


def judge(r):
    calls = [(t, a.get("service")) for t, a in env.parse_calls(r["reply"]) if t]
    same = (r["tool"], r["x"]) in calls
    if r["kind"] == "swap":
        if (r["tool"], r["y"]) in calls:
            return "follows"
        return "repeats" if same else "other"
    return "repeats" if same else "follows"


def cmd_probe_report(path):
    rows = [json.loads(line) for line in open(path)]
    for model in ("base", "sft"):
        print(f"== {model}")
        for kind in ("swap", "diff", "scale"):
            rs = [r for r in rows if r["model"] == model and r["kind"] == kind]
            if not rs:
                continue
            orig = Counter(judge(r) for r in rs if r["variant"] == "orig")
            edit = Counter(judge(r) for r in rs if r["variant"] == "edit")
            # among probes where, unedited, the model takes the original action: what does the edit do?
            ids = {r["id"] for r in rs if r["variant"] == "orig" and judge(r) == "repeats"}
            cond = Counter(judge(r) for r in rs if r["variant"] == "edit" and r["id"] in ids)
            print(f"  {kind}: n={len(rs) // 2} unedited {dict(orig)} | edited {dict(edit)} | edited, where unedited "
                  f"repeats the transcript's action: {dict(cond)}")
            for r in rs:
                if r["variant"] == "edit":
                    calls = [(t, a.get("service")) for t, a in env.parse_calls(r["reply"]) if t]
                    print(f"     {r['id']}: {r['tool']} {r['x']}{' -> ' + r['y'] if r['y'] else ''}: {judge(r)} {calls[:3]}")


# --- the adapter ----------------------------------------------------------------------------------


def cmd_lora(adapter, name="sft"):
    """`name` names the outputs (out/lora-<name>.png) and the chart: sft, rl, ..."""
    import numpy as np
    from safetensors.numpy import load_file

    cfg = json.loads((Path(adapter) / "adapter_config.json").read_text())
    scale = cfg["lora_alpha"] / cfg["r"]
    w = load_file(str(Path(adapter) / "adapter_model.safetensors"))
    rows = []
    for k in sorted(w):
        if ".lora_A." not in k:
            continue
        a, b = w[k].astype(np.float64), w[k.replace(".lora_A.", ".lora_B.")].astype(np.float64)
        # ||B A||_F and the singular values of B A, from the r x r core: B A = Qb Rb Ra^T Qa^T
        _, rb = np.linalg.qr(b)
        _, ra = np.linalg.qr(a.T)
        s = np.linalg.svd(scale * rb @ ra.T, compute_uv=False)
        e = np.cumsum(s ** 2) / np.sum(s ** 2)
        layer = int(re.search(r"layers\.(\d+)\.", k)[1])
        module = re.search(r"\.(\w+_proj)\.lora_A", k)[1]
        rows.append(dict(layer=layer, module=module, norm=float(np.sqrt(np.sum(s ** 2))), rank90=int(np.searchsorted(e, 0.9) + 1),
                         shape=list(b.shape[:1]) + list(a.shape[1:])))
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    (out / f"lora-{name}.json").write_text(json.dumps(rows))
    mods = sorted({r["module"] for r in rows}, key=lambda m: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj",
                                                               "up_proj", "down_proj"].index(m))
    layers = sorted({r["layer"] for r in rows})
    by = {(r["layer"], r["module"]): r for r in rows}
    print(f"{len(rows)} adapted matrices, {len(layers)} layers, modules {mods}, alpha/r {scale}")
    print("module totals (sqrt of summed squared norms) and median 90%-energy rank:")
    for m in mods:
        rs = [r for r in rows if r["module"] == m]
        print(f"  {m}: {np.sqrt(sum(r['norm'] ** 2 for r in rs)):.2f}, rank90 median {st.median(r['rank90'] for r in rs)}, "
              f"top layers {[r['layer'] for r in sorted(rs, key=lambda r: -r['norm'])[:5]]}")
    per_layer = {l: np.sqrt(sum(by[l, m]["norm"] ** 2 for m in mods if (l, m) in by)) for l in layers}
    print("top layers overall:", sorted(per_layer, key=lambda l: -per_layer[l])[:8])
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#2a6fdb", "#5aa9e6", "#9bd0f5", "#1d3557", "#e76f51", "#f4a261", "#e9c46a"]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.3]))
    bottom = np.zeros(len(layers))
    for m, c in zip(mods, colors):
        v = np.array([by[l, m]["norm"] ** 2 if (l, m) in by else 0 for l in layers])
        ax.bar(layers, v, bottom=bottom, color=c, label=m, width=0.8)
        bottom += v
    ax.set_ylabel("‖ΔW‖²_F (stacked by module)")
    ax.set_title(f"Gemma 4 26B-A4B {name.upper()} adapter: how much each layer changed (ΔW = α/r · B·A)")
    ax.legend(ncol=len(mods), fontsize=8, frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    for m, c in zip(mods, colors):
        ax2.plot(layers, [by[l, m]["rank90"] if (l, m) in by else np.nan for l in layers], color=c, lw=1.2, marker=".")
    ax2.set_ylabel("rank for 90%\nof ‖ΔW‖²")
    ax2.set_xlabel("decoder layer")
    ax2.set_ylim(0, cfg["r"] + 1)
    ax2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / f"lora-{name}.png", dpi=150)
    print(f"-> {out / f'lora-{name}.png'}")


def cmd_lora_diff(adapter, start):
    """How far training moved an adapter from the one it started from: per module and overall,
    ||dW_adapter - dW_start||_F / ||dW_start||_F and the cosine between the two updates."""
    import numpy as np
    from safetensors.numpy import load_file

    def deltas(path):
        cfg = json.loads((Path(path) / "adapter_config.json").read_text())
        w = load_file(str(Path(path) / "adapter_model.safetensors"))
        s = cfg["lora_alpha"] / cfg["r"]
        return {k: s * w[k.replace(".lora_A.", ".lora_B.")].astype(np.float64) @ w[k].astype(np.float64)
                for k in w if ".lora_A." in k}

    a, b = deltas(adapter), deltas(start)
    by = defaultdict(lambda: [0.0, 0.0, 0.0])  # module -> [|a-b|^2, |b|^2, <a,b>]
    na = 0.0
    for k in b:
        mod = re.search(r"\.(\w+_proj)\.lora_A", k)[1]
        d = a[k] - b[k]
        for key in (mod, "all"):
            by[key][0] += float(np.sum(d * d))
            by[key][1] += float(np.sum(b[k] * b[k]))
            by[key][2] += float(np.sum(a[k] * b[k]))
        na += float(np.sum(a[k] * a[k]))
    print(f"{adapter} against {start}: relative change ||dW - dW0|| / ||dW0||, cosine(dW, dW0)")
    for mod, (dd, bb, ab) in sorted(by.items(), key=lambda x: x[0] != "all"):
        nb = bb ** 0.5
        cos = ab / (nb * (na if mod == "all" else sum(float(np.sum(a[k] ** 2)) for k in a if f".{mod}." in k)) ** 0.5)
        print(f"  {mod}: {dd ** 0.5 / nb:.3f}, cosine {cos:.4f}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "complete":
        cmd_complete(args)
    else:
        dict(seeds=cmd_seeds, replay=cmd_replay, behaviour=cmd_behaviour, probes=cmd_probes,
             lora=cmd_lora, **{"probe-report": cmd_probe_report, "lora-diff": cmd_lora_diff})[cmd](*args)
