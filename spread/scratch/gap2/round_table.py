"""Per-week round table for katalyst against tenth, from Bahn's public practice board.

Usage: python3 -I round_table.py [--board FILE] [--drivers "Round name=d1,d2,d3,d4,d5"]...
Without --board it fetches the level-8 board and saves boards/board-<DD>-<HHMM>.json.
For each of the board's two rounds (current, previous) in which katalyst has played five weeks,
prints a Markdown table: per week (run) the drivers, tenth's margin and orders among that week's
valid runs (run ranked and not deleted), ours with orders, place and on-time share, and tenth's lead.
"""
import datetime
import json
import os
import sys
import urllib.request

URL = "https://spread.bahnexpress.com/v1/leaderboards/practice?level=8"
US = "katalyst"
HERE = os.path.dirname(os.path.abspath(__file__))


def eur(cents):
    return f"€{cents / 100:,.0f}"


def lead(cents):
    return ("+" if cents >= 0 else "−") + eur(abs(cents))


def load(argv):
    drivers, board = {}, None
    i = 0
    while i < len(argv):
        if argv[i] == "--drivers":
            name, counts = argv[i + 1].split("=")
            drivers[name.strip()] = [int(x) for x in counts.split(",")]
            i += 2
        elif argv[i] == "--board":
            board = argv[i + 1]
            i += 2
        else:
            sys.exit(f"unknown argument {argv[i]}")
    if board:
        return json.load(open(board)), board, drivers
    now = datetime.datetime.now(datetime.timezone.utc)
    with urllib.request.urlopen(URL, timeout=60) as r:
        raw = r.read()
    path = os.path.join(HERE, "boards", now.strftime("board-%d-%H%M.json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(raw)
    return json.loads(raw), path, drivers


def table(rnd, counts):
    teams = rnd["teams"]
    us = next((t for t in teams if t["team"] == US), None)
    finished = sum(t["played"] == 5 for t in teams)
    ranked = sum(bool(t["ranked"]) for t in teams)
    head = f"### {rnd['name']} (opened {rnd['startedAt'][11:16]} UTC): {finished} teams with five weeks, {ranked} ranked"
    if not us or us["played"] < 5:
        return head + f"\nkatalyst has {us['played'] if us else 0} weeks; no table.", None
    head += f"; katalyst {us['rank'] or 'unranked'}, {eur(us['marginCents'])} over five weeks, {us['onTimeShare']:.1%} on time"
    rows, leads = [], {"760+": [], "<760": []}
    lines = [head, "", "| Week | Drivers | 5th | 10th | Us, place | 10th ÷ us |",
             "| --- | --- | --- | --- | --- | --- |"]
    for w in range(1, 6):
        runs = []
        for t in teams:
            for r in t["runs"]:
                if r["run"] == w and r["ranked"] and not r["deletedAt"]:
                    runs.append((r["marginCents"], r["wonOrders"], t["team"], r["onTimeShare"]))
        runs.sort(reverse=True)
        mine = next(r for r in us["runs"] if r["run"] == w)
        tenth = runs[9] if len(runs) >= 10 else None
        place = next((i + 1 for i, r in enumerate(runs) if r[2] == US), None)
        d = counts[w - 1] if counts else None
        gap = tenth[0] - mine["marginCents"] if tenth else None
        if d is not None and gap is not None:
            leads["760+" if d >= 760 else "<760"].append(gap)
        us_cell = f"{eur(mine['marginCents'])} on {mine['wonOrders']}, {mine['onTimeShare']:.1%}, " + (
            f"{place}th of {len(runs)}" if place else f"not valid ({len(runs)} valid)")
        fifth = runs[4] if len(runs) >= 5 else None
        cell = lambda r: f"{eur(r[0])} on {r[1]}" if r else "-"
        lines.append(f"| {w} | {d if d else '?'} | {cell(fifth)} | {cell(tenth)} | {eur(mine['marginCents'])} on {mine['wonOrders']}, {place or '-'}th | {tenth[0]/mine['marginCents']:.3f} |" if tenth else "")
        rows.append({"week": w, "drivers": d, "tenth": tenth, "us": mine, "place": place, "valid": len(runs), "lead": gap})
    lines.append("")
    for k, v in leads.items():
        if v:
            lines.append(f"- Tenth's lead, mean at {k} drivers: {lead(sum(v) // len(v))} over {len(v)} weeks")
    if not counts:
        lines.append("- Driver counts not yet known for this round.")
    return "\n".join(lines).replace("1th", "1st").replace("2th", "2nd").replace("3th", "3rd").replace("11st", "11th").replace("12nd", "12th").replace("13rd", "13th"), rows


def main():
    board, path, drivers = load(sys.argv[1:])
    print(f"Board: {path}\n")
    for key in ("current", "previous"):
        rnd = board.get(key)
        if rnd:
            print(table(rnd, drivers.get(rnd["name"]))[0], "\n")


if __name__ == "__main__":
    main()
