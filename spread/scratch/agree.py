"""Scratch: how far a variant's decisions are from a reference variant's, offline, as a fast proxy for how much of the
reference's gain the variant keeps. Feeds the same recorded event streams to each arm, with the recording's own wins, and
compares every quote and every won order's first post with the reference arm's.

An arm is `name=root:module:Class:variant`: the checkout to import spreadlab from (a `git worktree add <dir> <commit>`, so
arms can come from different branches), the desk class that plays the variant (play.py's choice: `spreadlab.policy:Policy`,
`spreadlab.pairs:PairPolicy`, `spreadlab.late_wide:WidePairPolicy`, ...) and the variant's name in that checkout's
variants.py. The first arm is the reference.

    SPREAD_DATA=... uv run python scratch/agree.py run --weeks slow-friday-late-150-kinds-limits --seeds fresh-1301:1330 \\
        --arm cand=/tmp/a:spreadlab.pairs:PairPolicy:f80-q24-wide-pairs-0.6-return-0.75 \\
        --arm d1=.:spreadlab.late_wide:WidePairPolicy:fee16-wide-pairs-0.6-return-0.75 --out /tmp/agree
    uv run python scratch/agree.py read --out /tmp/agree --chain cand,d2,d1,default --steps "outage split,0.9 opening,24-hour count,the rest"

Open loop: the recording's dealers and drivers answered another desk, so this measures how far decisions are apart, not
what the difference earns. Weight a decision type by what it is worth: on round 1 the quote prices tracked the played
capture, and 74% of first posts differed in fee for about 120 euros a week. `--chain` names arms that each add one part
on the way from the reference; each departure of an arm is put on the first arm along the chain that departs there.
"""
from __future__ import annotations

import argparse
import gzip
import importlib
import json
import math
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOL = 0.02  # a price or a fee within 2% of the reference's matches


def seeds_of(text: str) -> list[str]:
    out = []
    for part in text.split(","):
        if ":" in part:
            head, last = part.split(":")
            prefix, first = head.rsplit("-", 1)
            out += [f"{prefix}-{n:03d}" for n in range(int(first), int(last) + 1)]
        elif part:
            out.append(part)
    return out


def play(root: str, target: str, variant: str, week_path: str, map_path: str, out: str) -> None:
    """In a child process: one arm on one recorded week. Writes its quotes and each won order's first post."""
    sys.path.insert(0, str(Path(root).resolve() / "spread"))
    module, name = target.split(":")
    cls = getattr(importlib.import_module(module), name)
    params = importlib.import_module("spreadlab.variants").VARIANTS[variant]
    week = json.load(gzip.open(week_path))
    # A recorded order carries the delivery times filled in later; the world sent it without them (replay.as_sent).
    delivered = {(e["orderId"], e["leg"]): e["at"] for e in week["events"] if e["kind"] == "delivered"}
    for e in week["events"]:
        if e["kind"] in ("order_won", "order_changed"):
            o = e["order"]
            o["deliveredAt"] = [at if at is not None and at <= e["at"] and delivered.get((o["id"], leg)) == at else None
                                for leg, at in enumerate(o["deliveredAt"])]
    posts: dict[str, list] = {}  # order id -> [minute, opening fee in cents, cars, the other order of a pair gig]
    counts = {"reprices": 0}

    class World:
        gigs = 0

        def act(self, actions):
            results = []
            for action in actions:
                if action["type"] == "post":
                    self.gigs += 1
                    results.append({"ok": True, "id": f"g{self.gigs}"})
                    orders = sorted({s["orderId"] for s in action["stops"]})
                    for o in orders:
                        posts.setdefault(o, [desk.now, action["schedule"][0]["feeCents"], sum(s["kind"] == "pickup" for s in action["stops"]),
                                             next((x for x in orders if x != o), None)])
                else:
                    counts["reprices"] += action["type"] == "reprice"
                    results.append({"ok": True})
            return results

    desk = cls(World(), 8, 0, params, week["roster"], json.load(open(map_path)))

    def flush():
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, desk.world.act(actions))

    for event in week["events"]:
        while True:
            flush()
            wake = desk.wake_at()
            if not desk.now < wake < event["at"]:
                break
            desk.now = wake
            desk.look()
        flush()
        desk.now = event["at"]
        desk.handle(event)
        desk.look()
    flush()
    quotes = {rid: {"declined": d.get("declined"), "prices": d.get("prices") or {}} for rid, d in desk.decisions.items()}
    won = [e["order"]["id"] for e in week["events"] if e["kind"] == "order_won"]
    json.dump({"drivers": len(week["roster"]), "quotes": quotes, "posts": posts, "won": won, **counts}, open(out, "w"))


def run(args) -> None:
    data = Path(os.environ.get("SPREAD_DATA") or Path(__file__).parents[1] / "data")
    arms = dict(a.split("=", 1) for a in args.arm)
    jobs = []
    for seed in seeds_of(args.seeds):
        week = data / "runs" / args.weeks / f"{seed}-L8.json.gz"
        if not week.exists():
            print(f"no recording of {seed}", file=sys.stderr)
            continue
        for name, spec in arms.items():
            out = Path(args.out) / name / f"{seed}.json"
            if not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                root, module, cls, variant = spec.split(":")
                jobs.append([sys.executable, __file__, "_play", root, f"{module}:{cls}", variant, str(week), str(data / "map.json"), str(out)])
    (Path(args.out) / "arms.json").write_text(json.dumps(list(arms)))
    with ThreadPoolExecutor(args.jobs) as pool:
        for r in pool.map(lambda cmd: subprocess.run(cmd, capture_output=True, text=True), jobs):
            if r.returncode:
                print(" ".join(r.args[3:7]), r.stderr[-600:], file=sys.stderr)


def same_quote(a, b) -> bool:
    qa, qb = not a["declined"] and bool(a["prices"]), not b["declined"] and bool(b["prices"])
    if qa != qb or set(a["prices"]) != set(b["prices"]):
        return False
    return all(abs(a["prices"][k] / b["prices"][k] - 1) <= TOL for k in a["prices"])


def same_post(a, b) -> bool:
    return a is None or b is None or (a[0] == b[0] and abs(a[1] / b[1] - 1) <= TOL and a[3] == b[3])


def read(args) -> None:
    out = Path(args.out)
    arms = json.loads((out / "arms.json").read_text())
    ref = arms[0]
    seeds = sorted(set.intersection(*({p.stem for p in (out / a).glob("*.json")} for a in arms)))
    chain = args.chain.split(",") if args.chain else []
    steps = dict(zip(chain[1:], args.steps.split(","))) if args.steps else {a: a for a in chain[1:]}
    for title, keep in (("Natural (720 drivers or more)", lambda d: d >= 720), ("Thin (under 720 drivers)", lambda d: d < 720)):
        rows = {a: {k: [] for k in ("status", "options", "price", "logp", "minute", "fee", "pair")} | {"pairs": 0, "reprices": 0} for a in arms}
        firsts = {a: {} for a in chain[1:]}
        weeks = 0
        for seed in seeds:
            data = {a: json.loads((out / a / f"{seed}.json").read_text()) for a in arms}
            if not keep(data[ref]["drivers"]):
                continue
            weeks += 1
            r0 = data[ref]
            for a in arms:
                d, row = data[a], rows[a]
                row["pairs"] += sum(1 for p in d["posts"].values() if p[3]) / 2
                row["reprices"] += d["reprices"]
                for rid, q in r0["quotes"].items():
                    mine = d["quotes"][rid]
                    qa, qb = not mine["declined"] and bool(mine["prices"]), not q["declined"] and bool(q["prices"])
                    row["status"].append(qa == qb)
                    if qa and qb:
                        row["options"].append(set(mine["prices"]) == set(q["prices"]))
                        if set(mine["prices"]) == set(q["prices"]):
                            row["price"].append(all(abs(mine["prices"][k] / q["prices"][k] - 1) <= TOL for k in q["prices"]))
                            row["logp"] += [math.log(mine["prices"][k] / q["prices"][k]) for k in q["prices"]]
                for oid in r0["won"]:
                    p, p0 = d["posts"].get(oid), r0["posts"].get(oid)
                    if p and p0:
                        row["minute"].append(p[0] == p0[0])
                        row["fee"].append(abs(p[1] / p0[1] - 1) <= TOL)
                        row["pair"].append(p[3] == p0[3])
            for i, a in enumerate(chain[1:], 1):
                for kind, ids, same in (("quote", r0["quotes"], lambda x, k: same_quote(data[x]["quotes"][k], r0["quotes"][k])),
                                        ("post", r0["won"], lambda x, k: same_post(data[x]["posts"].get(k), r0["posts"].get(k)))):
                    for k in ids:
                        if not same(a, k):
                            first = next(x for x in chain[1:i + 1] if not same(x, k))
                            firsts[a][(kind, first)] = firsts[a].get((kind, first), 0) + 1
        if not weeks:
            continue
        share = lambda xs: f"{100 * sum(xs) / len(xs):.1f}%" if xs else "-"  # noqa: E731
        print(f"\n{title}: {weeks} weeks; agreement with {ref} (prices and fees within {TOL:.0%})")
        print("| arm | quote or decline | same options | price, all options | median price vs ref | post minute | opening fee | pairing | pair gigs/wk | reprices/wk |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for a in arms:
            r = rows[a]
            med = f"{100 * (math.exp(statistics.median(r['logp'])) - 1):+.1f}%" if r["logp"] else "-"
            print(f"| {a} | {share(r['status'])} | {share(r['options'])} | {share(r['price'])} | {med} | {share(r['minute'])} | "
                  f"{share(r['fee'])} | {share(r['pair'])} | {r['pairs'] / weeks:.1f} | {r['reprices'] / weeks:.0f} |")
        for a, counts in firsts.items():
            parts = []
            for kind in ("quote", "post"):
                total = sum(v for (k, _), v in counts.items() if k == kind)
                parts += [f"{kind} {steps[x]} {100 * v / total:.0f}%" for (k, x), v in counts.items() if k == kind]
            if parts:
                print(f"{a}: departures by the first step that makes them: " + "; ".join(parts))


def main() -> None:
    if sys.argv[1:2] == ["_play"]:
        return play(*sys.argv[2:8])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    r = sub.add_parser("run")
    r.add_argument("--weeks", required=True, help="the variant whose recorded weeks are fed to every arm")
    r.add_argument("--seeds", required=True, help="a,b or fresh-1301:1330")
    r.add_argument("--arm", action="append", required=True, help="name=root:module:Class:variant; the first is the reference")
    r.add_argument("--out", required=True)
    r.add_argument("--jobs", type=int, default=2)
    s = sub.add_parser("read")
    s.add_argument("--out", required=True)
    s.add_argument("--chain", default="", help="arms from the reference, each adding one part, for the attribution of departures")
    s.add_argument("--steps", default="", help="a name for each step of the chain after the reference, comma-separated")
    args = parser.parse_args()
    run(args) if args.action == "run" else read(args)


if __name__ == "__main__":
    main()
