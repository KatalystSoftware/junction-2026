"""Plays the team's runs of the current ranking round at a level, one after the other, with one variant.

    SPREAD_KEY=... PYTHONPATH=. uv run python scratch/ranking.py --team <team> --round 2026-11-14T13:00
    SPREAD_KEY=... PYTHONPATH=. uv run python scratch/ranking.py --practice fresh-1301   # the same loop on a practice week

A ranking run is a decision for a person: spreadlab's own client refuses to start one, and this script
is the only place that does. A round is five secret weeks a level, played in order and one at a time, and
a team is ranked once all five are played with at least 90% on time each. So the script:

- starts nothing unless the board's current round started at the minute given with --round;
- never deletes a ranking world: a deleted run plays to its end without a desk and still counts;
- sends an advance again only when the server shows that the first one did not arrive, and otherwise
  stops and leaves the world standing, for a person to look at;
- stops after a run under 90% on time, because the round cannot be ranked any more.

Each run is saved under data/ranking/<round>/L<level>-run-<n>.json.gz: the events, the score, the gigs, the
driver list and the policy's decisions. There is no reveal of a ranking world.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from spread.client import ACTIONS_PER_CALL, Client, SpreadError, Unreachable
from spread.starter import DAY

from spreadlab.policy import Policy, fingerprint
from spreadlab.server import SERVER, PracticeClient, data_dir, world_map, write_json_gz
from spreadlab.variants import VARIANTS

RUNS = 5
MIN_ON_TIME = 0.9


class Stop(Exception):
    """The script cannot go on safely. The world is left as it is."""


def answered(call, what: str):
    """The answer to a read, however long the server takes to come back."""
    waited = 0
    while True:
        try:
            return call()
        except Unreachable as error:
            if waited >= 1800:
                raise Stop(f"The server has not answered {what} for 30 minutes: {error}") from error
            print(f"  waiting for the server ({what}): {error}", flush=True)
            time.sleep(3)
            waited += 3


def advance(world, desk, ends_at: int, last_seq: int) -> tuple[list, dict]:
    actions, desk.outbox = desk.outbox, []
    to = min(ends_at, (desk.now // DAY + 1) * DAY, desk.wake_at())
    while True:
        try:
            return actions, world.advance(until=desk.wake_on, max=to, actions=actions)
        except Unreachable as error:
            print(f"  the advance at minute {desk.now} got no answer: {error}", flush=True)
            now = answered(world.snapshot, "the snapshot")["now"]
            newer = answered(lambda: world.events(after=last_seq, limit=1), "the events")
            if now != desk.now or newer or len(actions) > ACTIONS_PER_CALL:
                raise Stop(f"The advance at minute {desk.now} may have arrived (the world is at minute {now}, "
                           f"{len(newer)} newer event, {len(actions)} actions). Not sent again") from error


def play(client: Client, world, variant: str, level: int, path, extra: dict) -> dict:
    """Plays the world to its end and saves the run. Deletes nothing."""
    started = time.time()
    params = VARIANTS[variant]
    map_ = answered(lambda: world_map(client), "the map")
    snapshot, roster = answered(world.snapshot, "the snapshot"), answered(world.roster, "the drivers")
    if snapshot["now"] != snapshot.get("startsAt", snapshot["now"]) or snapshot.get("events"):
        raise Stop(f"World {world.id} has already moved (minute {snapshot['now']}). This script only plays a week from its start")
    desk, ends_at = Policy(world, level, snapshot["now"], params, roster, map_), snapshot["endsAt"]
    events: list[dict] = []
    saved = {"variant": variant, "level": level, "worldId": world.id, "params": desk.p, "fingerprint": fingerprint(params), **extra}
    try:
        while desk.now < ends_at:
            actions, step = advance(world, desk, ends_at, events[-1]["seq"] if events else -1)
            desk.read_results(actions, step["results"])
            desk.now = step["now"]
            for event in step["events"]:
                events.append(event)
                desk.handle(event)
            desk.look()
        summary = {**saved, "score": answered(world.score, "the score"), "seconds": round(time.time() - started)}
        write_json_gz(path, {**summary, "events": events, "gigs": answered(world.snapshot, "the snapshot")["gigs"],
                             "roster": roster, "decisions": desk.decisions, "refused": desk.refused})
        path.with_suffix("").with_suffix(".score.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
        return summary
    except BaseException:
        write_json_gz(path.with_suffix("").with_suffix(".partial.json.gz"),
                      {**saved, "now": desk.now, "events": events, "roster": roster, "decisions": desk.decisions, "refused": desk.refused})
        raise


def line(summary: dict) -> str:
    score = summary["score"]
    return (f"margin {score['marginCents'] / 100:,.0f}  orders {score['wonOrders']}  on time {score['onTimeShare']:.1%}  "
            f"undelivered {score['undeliveredShare']:.1%}  ranked {score['ranked']}  {summary['seconds']} s")


def row(board: dict, team: str) -> dict | None:
    return next((t for t in board["current"]["teams"] if team.casefold() in (t["team"].casefold(), t["name"].casefold())), None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", default="slow-friday-late-150-kinds-limits")
    parser.add_argument("--level", type=int, default=8)
    parser.add_argument("--team", help="the team's id or name on the board")
    parser.add_argument("--round", help="the start of the round to play, as the board gives it, or its first characters: 2026-11-14T13:00")
    parser.add_argument("--runs", type=int, default=RUNS, help="play at most this many runs now")
    parser.add_argument("--practice", metavar="SEED", help="play this practice week instead, and delete the world afterwards")
    args = parser.parse_args()

    if args.practice:
        world = PracticeClient().create(level=args.level, seed=args.practice)
        try:
            path = data_dir() / "ranking" / "practice" / f"{args.variant}-{args.practice}-L{args.level}.json.gz"
            print(line(play(world.client, world, args.variant, args.level, path, {"seed": args.practice})))
        finally:
            world.delete()
        return
    if not args.team or not args.round:
        parser.error("--team and --round are required for a ranking run")

    client = Client(url=SERVER)
    board = client.board(args.level)
    current = board["current"]
    if not current or not current["startedAt"].startswith(args.round):
        sys.exit(f"The current round is {current and (current['name'], current['startedAt'])}, not one that started at {args.round}. Nothing played")
    open_runs = [w for w in client.worlds() if w.get("boardRun") is not None and not w["ended"]]
    if open_runs:
        sys.exit(f"A ranking run is open already: {open_runs}. Nothing played")
    team = row(board, args.team)
    played = team["played"] if team else 0
    print(f"round {current['name']} from {current['startedAt']}: {len(current['teams'])} teams, {played} of {RUNS} runs played by {args.team}", flush=True)
    folder = data_dir() / "ranking" / current["startedAt"].replace(":", "")
    try:
        for run in range(played + 1, min(RUNS, played + args.runs) + 1):
            world = client.create(level=args.level, board=True)
            print(f"run {run}: world {world.id}", flush=True)
            summary = play(client, world, args.variant, args.level, folder / f"L{args.level}-run-{run}.json.gz",
                           {"run": run, "round": current["startedAt"]})
            print(f"run {run}: {line(summary)}", flush=True)
            if summary["score"]["onTimeShare"] < MIN_ON_TIME:
                print(f"run {run} is under {MIN_ON_TIME:.0%} on time: the round cannot be ranked. Stopped", flush=True)
                break
    except (Stop, SpreadError) as error:
        print(f"STOPPED, the world is left as it is: {error}", flush=True)
    team = row(answered(lambda: client.board(args.level), "the board"), args.team)
    print("board:", json.dumps(team), flush=True)
    if team:
        ranked = [t for t in answered(lambda: client.board(args.level), "the board")["current"]["teams"] if t["ranked"]]
        print(f"rank {team['rank']} of {len(ranked)} ranked teams", flush=True)


if __name__ == "__main__":
    main()
