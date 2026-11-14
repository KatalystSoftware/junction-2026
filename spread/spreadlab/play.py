"""Plays one practice week with a variant and saves the run: every event, the reveal, the gigs, the
driver list and the policy's decisions.

    python -m spreadlab.play --variant baseline --seed cat-001
    python -m spreadlab.play --variant try --params '{"price": 1.7}' --seed cat-001

A run is two files under data/runs/<variant>/: <seed>-L<level>.json.gz holds everything, and
<seed>-L<level>.score.json the score alone, for reports.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from spread.starter import DAY

from .dealer import DealerPolicy
from .fallback import ActionDesk
from .exposure import ExposurePolicy
from .late_wide import WidePairPolicy, WidePolicy
from .pairs import PairPolicy
from .policy import Policy, fingerprint
from .riskfee import RiskFeePolicy
from .server import PracticeClient, data_dir, read_json_gz, world_map, write_json_gz
from .variants import VARIANTS


class CountingClient(PracticeClient):
    """Counts the week's requests and notes the lowest and highest share of the key's practice bucket that the server
    stated during the week (RateLimit-Limit, requests a second). The share is 10,000 a second split among the teams that
    practise, at most 1,000 (API.md, Limits); all worlds on the key share it, so it caps the weeks an hour."""
    calls = 0
    rates: tuple[float, float] | None = None

    def call(self, *args, **kwargs):
        self.calls += 1
        answer = super().call(*args, **kwargs)
        bucket = self._buckets.get("practice")
        if bucket is not None:
            low, high = self.rates or (bucket.per_second, bucket.per_second)
            self.rates = (min(low, bucket.per_second), max(high, bucket.per_second))
        return answer


def run_path(variant: str, seed: str, level: int = 8) -> Path:
    return data_dir() / "runs" / variant / f"{seed}-L{level}.json.gz"


def score_path(variant: str, seed: str, level: int = 8) -> Path:
    return run_path(variant, seed, level).with_suffix("").with_suffix(".score.json")


def failure_path(variant: str, seed: str, level: int = 8) -> Path:
    """Written by a sweep when the week failed, removed when it is played to its end."""
    return run_path(variant, seed, level).with_suffix("").with_suffix(".failed.json")


def load_run(variant: str, seed: str, level: int = 8) -> dict:
    return read_json_gz(run_path(variant, seed, level))


def load_score(variant: str, seed: str, level: int = 8) -> dict | None:
    path = score_path(variant, seed, level)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def policy_class(params: dict) -> type[Policy]:
    """The desk a variant plays a week with. Every script that plays a week asks here, so that a ranking run plays the
    policy its practice weeks played."""
    # The day's correction with an offset for each dealer (dealer.py), the note fallback (fallback.py), the fees by each car's
    # risk (riskfee.py), or out-and-back pairs (pairs.py).
    chosen = (PairPolicy if params.get("pair_hold") else DealerPolicy if params.get("dealer_sd") else ActionDesk if "note_actions" in params
              else RiskFeePolicy if params.get("risk_fees") else Policy)
    if params.get("late_wide"):  # the wide late chance (late_wide.py), with or without pairs
        chosen = {Policy: WidePolicy, PairPolicy: WidePairPolicy}[chosen]
    if params.get("exposure"):  # the quote's cost by the book's exposure to drops (exposure.py)
        chosen = {Policy: ExposurePolicy}[chosen]
    return chosen


def play(variant: str, params: dict, seed: str, level: int = 8) -> dict:
    """Plays the week and returns the summary that goes to the score file."""
    started, cpu = time.time(), time.thread_time()
    client = CountingClient()
    map_ = world_map(client)
    world = client.create(level=level, seed=seed)
    try:
        snapshot, roster = world.snapshot(), world.roster()
        desk, ends_at = policy_class(params)(world, level, snapshot["now"], params, roster, map_), snapshot["endsAt"]
        events: list[dict] = []
        while desk.now < ends_at:
            # One request a step, as the starter does: the advance applies the outbox, then moves the clock.
            actions, desk.outbox = desk.outbox, []
            step = world.advance(until=desk.wake_on, max=min(ends_at, (desk.now // DAY + 1) * DAY, desk.wake_at()), actions=actions)
            desk.read_results(actions, step["results"])
            desk.now = step["now"]
            for event in step["events"]:
                events.append(event)
                desk.handle(event)
            desk.look()
        summary = {"variant": variant, "seed": seed, "level": level, "params": desk.p, "fingerprint": fingerprint(params),
                   "score": world.score(), "calls": client.calls, "seconds": round(time.time() - started),
                   # The desk's own CPU seconds, and the bucket's share. While the key's worlds together send about `rate`
                   # requests a second, the share is what limits the weeks an hour, and more worlds add nothing.
                   "cpu": round(time.thread_time() - cpu, 1), "rate": client.rates}
        write_json_gz(run_path(variant, seed, level), {**summary, "events": events, "reveal": world.reveal(), "gigs": world.snapshot()["gigs"],
                                                       "roster": roster, "decisions": desk.decisions, "refused": desk.refused,
                                                       **({"noteActions": desk.review} if "note_actions" in params else {})})
        score_path(variant, seed, level).write_text(json.dumps(summary) + "\n", encoding="utf-8")
        failure_path(variant, seed, level).unlink(missing_ok=True)
        return summary
    finally:
        world.delete()  # frees the slot after an error; after a full week the run is on disk


def line(summary: dict) -> str:
    score = summary["score"]
    return (f"{summary['variant']:16s} {summary['seed']:10s} margin {score['marginCents'] / 100:>10,.0f}  orders {score['wonOrders']:>3}  "
            f"on time {score['onTimeShare']:6.1%}  {'ranked' if score['ranked'] else 'NOT RANKED'}  calls {summary['calls']}  secs {summary['seconds']}"
            + (f"  rate {summary['rate'][0]:.0f}" if summary.get("rate") else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", required=True, help="a name from variants.py, or any name with --params")
    parser.add_argument("--params", help="JSON: the parameters that differ from policy.DEFAULTS")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--level", type=int, default=8)
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else VARIANTS[args.variant]
    print(line(play(args.variant, params, args.seed, args.level)))


if __name__ == "__main__":
    main()
