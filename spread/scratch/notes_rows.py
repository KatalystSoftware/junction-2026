"""Scratch: one row for each won order with a note, from saved weeks: the note, what the request stated, and what was true."""
import json, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from spreadlab.server import data_dir, read_json_gz

def rows_of(path):
    run = read_json_gz(path)
    req = {r["request"]["id"]: r["request"] for r in run["reveal"]["requests"]}
    won = {e["order"]["id"]: e["order"] for e in run["events"] if e["kind"] == "order_won"}
    out = []
    for o in run["reveal"]["orders"]:
        r = req[o["orderId"]]
        if not r["note"] or o["orderId"] not in won:
            continue
        order = won[o["orderId"]]
        out.append({"seed": run["seed"], "id": r["id"], "note": r["note"]["text"], "arrivedAt": r["arrivedAt"], "option": order["option"],
                    "optionDeadline": next(x["deadline"] for x in r["options"] if x["kind"] == order["option"]), "deadline": order["deadline"],
                    "legs": [{"pickup": l["pickup"], "delivery": l["delivery"]} for l in r["legs"]], "truth": o["legs"]})
    return out

if __name__ == "__main__":
    variants = sys.argv[1].split(",")
    paths = [p for v in variants for p in sorted((data_dir() / "runs" / v).glob("*-L8.json.gz"))]
    seen, n = set(), 0
    with ProcessPoolExecutor(6) as pool, open(sys.argv[2], "w") as f:
        for rows in pool.map(rows_of, paths):
            for row in rows:
                if (row["seed"], row["id"]) not in seen:
                    seen.add((row["seed"], row["id"])); f.write(json.dumps(row) + "\n"); n += 1
    print(len(paths), "runs", n, "orders with a note")
