"""File finished Harbor runs so they never have to be rerun. For every trial of the given job folders:

- the signed action log -> loop-evidence/receipts/<job>__<trial>.json
- the agent's closing message, verbatim -> loop-evidence/final-messages/<job>__<trial>.md
- the full OpenCode transcript and the verifier's ledger -> runs/<dest>/<job>/<trial>/
  (agent/opencode.txt, verifier/reward.json; never Harbor's config.json, which can hold API keys)

Rows in metrics.json come from collect.py. Already filed trials are left as they are.

python3 archive_runs.py <dest> jobs/<job>...
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent


def closing_message(transcript):
    texts = []
    for line in transcript.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            texts.append(event["part"]["text"])
    return texts[-1].strip() if texts else "(no closing message)"


def file_trial(dest, job, trial):
    name = f"{job.name}__{trial.name}"
    result = json.loads((trial / "result.json").read_text())
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    receipt = trial / "artifacts" / "ledger" / "receipt.json"
    if receipt.exists():
        out = HERE / "loop-evidence" / "receipts" / f"{name}.json"
        if not out.exists():
            shutil.copyfile(receipt, out)
    transcript = trial / "agent" / "opencode.txt"
    if transcript.exists():
        out = HERE / "loop-evidence" / "final-messages" / f"{name}.md"
        if not out.exists():
            # level, seed and run come from the job name: r<round>-l<level>-s<seed>-<run>-<time>
            parts = job.name.split("-")
            level, seed, run = parts[1][1:], parts[2][1:], "-".join(parts[3:-1])
            score = rewards.get("reward")
            out.write_text(f"# {job.name}/{trial.name}\n\nLevel {level}, seed {seed}, {run}, score as run "
                           f"{score if score is None else round(score, 4)}. The agent's closing message, "
                           f"verbatim:\n\n{closing_message(transcript)}\n")
        copy = HERE / "runs" / dest / job.name / trial.name
        (copy / "agent").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(transcript, copy / "agent" / "opencode.txt")
        reward = trial / "verifier" / "reward.json"
        if reward.exists():
            (copy / "verifier").mkdir(exist_ok=True)
            shutil.copyfile(reward, copy / "verifier" / "reward.json")
    return name


if __name__ == "__main__":
    dest, jobs = sys.argv[1], [Path(p) for p in sys.argv[2:]]
    n = 0
    for job in jobs:
        for trial in sorted(p for p in job.iterdir() if (p / "result.json").exists()):
            file_trial(dest, job, trial)
            n += 1
    print(f"filed {n} trials under runs/{dest}/ and loop-evidence/")
