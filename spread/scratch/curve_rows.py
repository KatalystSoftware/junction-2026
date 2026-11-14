"""Scratch: one row per serious quote of the random-price weeks (variant `explore`), with what the desk knew at the quote,
the dealer's answer and the account of the order. Writes curve_rows.json next to this file.

    PYTHONPATH=. uv run python scratch/curve_rows.py [variant ...]
"""
import glob, json, os, sys
from spreadlab import ledger
from spreadlab.play import load_run
from spreadlab.server import data_dir, drivers_near, near_places, world_map

SPEED = ["same_day", "next_day", "within_3_days"]
near = near_places(world_map())
out = []
for variant in sys.argv[1:] or ["explore"]:
    for path in sorted(glob.glob(str(data_dir() / "runs" / variant / "*-L8.json.gz"))):
        seed = path.split("/")[-1][:-len("-L8.json.gz")]
        run = load_run(variant, seed)
        played = ledger.week(run, near)
        notified = drivers_near(run["roster"], near)
        for r in run["reveal"]["requests"]:
            q, d, row = r["request"], run["decisions"][r["request"]["id"]], played["requests"][r["request"]["id"]]
            if d["declined"]:
                continue
            options = {o["kind"]: o for o in q["options"]}
            first = min(d["prices"], key=SPEED.index)  # the fastest option quoted
            leg, won = q["legs"][0], row["outcome"] in ("won", "cancelled")
            seen = d.get("seen", {})
            out.append(dict(
                variant=variant, seed=seed, id=q["id"], dealer=q["dealerId"], at=q["arrivedAt"], day=q["arrivedAt"] // 1440, hour=q["arrivedAt"] % 1440 / 60,
                pickup=leg["pickup"]["placeId"], delivery=leg["delivery"]["placeId"], kinds=sorted(d["prices"], key=SPEED.index), first=first,
                price=d["prices"][first], list=options[first]["listPriceCents"], fee=q["referenceFeeCents"],
                multiples={k: p / options[k]["listPriceCents"] for k, p in d["prices"].items()},
                trust=seen.get("trust"), unbooked=seen.get("unbooked"), answers=seen.get("answers"),
                notified=notified[leg["pickup"]["placeId"]], drivers=len(run["roster"]), batch=q["batchId"], note=q["note"] is not None,
                outcome=row["outcome"], won=won, option=r["option"], situation=row["situation"],
                paid=row["price"] if row["outcome"] == "won" else None, fees=row["fees"] if won else None, costs=row["costs"] if won else None,
                late=row["late"] if won else None, onTime=row["onTime"] if row["outcome"] == "won" else None))
        print(variant, seed, len(out), file=sys.stderr, flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "curve_rows.json"), "w"))
print(len(out), "rows")
