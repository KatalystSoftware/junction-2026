"""Classify the hero topics' pairs with one model, with every raw answer cached on disk.

    python demo/hero_classify.py nemotron PAIRS.jsonl [--workers 4]
    DIFFERENCES_TIMEOUT=1800 python demo/hero_classify.py nemotron-verda PAIRS.jsonl --workers 24
    python demo/hero_classify.py haiku PAIRS.jsonl --max-requests 300
    python demo/hero_classify.py nemotron PAIRS.jsonl --offline

Run from projects/since-when/. PAIRS.jsonl comes from `python -m gapfinder pairs --only Q…`.
Everything is written under $HERO_CLASSIFY (default ~/junction2026-data/mariadb/classify)/<model>/:

    cache/<key>.json     the raw answer, written by differences.classify; the key covers the prompt
                         version, the endpoint, the model, its settings and both passage texts
    index.jsonl          one line per pair of the last run: pair_id, prompt version, revisions, the
                         SHA-1 of each passage text, the cache key and whether the answer is there
    differences.jsonl    the rows of the last run, the input of `python -m gapfinder findings load`
    requests.json        requests sent to the model by all runs so far (the cap for --max-requests)

--offline never calls the model: a pair whose answer is not cached gets no rows and is listed.
nemotron is Nemotron 3.5 Super VL on NVIDIA Build's free tier; nemotron-verda is the same model on the
dedicated Verda container (provider verda-super), with no per-minute limit; it queues when busy,
hence the longer DIFFERENCES_TIMEOUT. The key is read by differences.llm from NVIDIA_API_KEY,
VERDA_INFERENCE_KEY or ANTHROPIC_API_KEY (sops exec-env).
"""

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

MODELS = {"nemotron": "nvidia", "nemotron-verda": "verda-super", "haiku": "anthropic"}
KEYS = {"nvidia": "NVIDIA_API_KEY", "verda-super": "VERDA_INFERENCE_KEY", "anthropic": "ANTHROPIC_API_KEY"}

ap = argparse.ArgumentParser()
ap.add_argument("model", choices=MODELS)
ap.add_argument("pairs")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--offline", action="store_true", help="answers from the cache only, no model call")
ap.add_argument("--max-requests", type=int, help="stop sending once all runs together sent this many")
args = ap.parse_args()

OUT = Path(os.environ.get("HERO_CLASSIFY", Path.home() / "junction2026-data/mariadb/classify")) / args.model
os.environ["DIFFERENCES_PROVIDER"] = MODELS[args.model]
os.environ["DIFFERENCES_CACHE"] = str(OUT / "cache")
if args.offline:  # the cache key needs the endpoint and model, not the key
    os.environ.setdefault(KEYS[MODELS[args.model]], "offline")
    os.environ["DIFFERENCES_RPM"] = "6000"  # nothing is sent, so nothing to pace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from differences import classify, lexicon, llm

cfg = llm.config()
if not cfg:
    sys.exit("no model key in the environment: run through sops exec-env, or with --offline")

OUT.mkdir(parents=True, exist_ok=True)
counter = OUT / "requests.json"
sent = json.loads(counter.read_text())["requests"] if counter.exists() else 0
lock = threading.Lock()
post = llm._post


def counted_post(url, key, body, **kw):
    """llm._post, counting every request sent (failed ones too) across runs."""
    global sent
    if args.model == "haiku":
        # claude-haiku-5-5 answers 400 to a request that sets temperature, and to a schema with
        # maxItems; without a schema it answers in prose that does not parse.
        body = json.loads(json.dumps({k: v for k, v in body.items() if k != "temperature"}))
        schema = (body.get("response_format") or {}).get("json_schema", {}).get("schema", {})
        schema.get("properties", {}).get("differences", {}).pop("maxItems", None)
    with lock:
        if args.offline:
            raise RuntimeError("not in the cache (offline)")
        if args.max_requests is not None and sent >= args.max_requests:
            raise RuntimeError(f"request cap {args.max_requests} reached")
        sent += 1
        counter.write_text(json.dumps({"requests": sent}))
    return post(url, key, body, **kw)


llm._post = counted_post
if args.offline:
    llm.RETRIES = 1


def cache_key(pair):
    """The key differences.classify._cached_chat files this pair's answer under."""
    messages = classify._messages(pair, lexicon.compare(pair["a"], pair["b"]))
    opts = {k: v for k, v in llm.options().items() if k != "max_tokens"}
    return hashlib.sha256(
        json.dumps([classify.PROMPT_VERSION, cfg[0], cfg[2], opts, messages], ensure_ascii=False).encode()
    ).hexdigest()


sha = lambda text: hashlib.sha1(text.encode()).hexdigest()
pairs = [json.loads(line) for line in open(args.pairs, encoding="utf-8") if line.strip()]
started, before, n_rows, missing = time.monotonic(), sent, 0, []
with (
    open(OUT / "differences.jsonl", "w", encoding="utf-8") as rows_out,
    open(OUT / "index.jsonl", "w", encoding="utf-8") as index_out,
):
    for i, (pair, rows) in enumerate(zip(pairs, classify.classify_pairs(pairs, workers=args.workers, cfg=cfg)), 1):
        key = cache_key(pair)
        cached = (OUT / "cache" / f"{key}.json").exists()
        if not cached:
            missing.append(pair["pair_id"])
        rows_out.writelines(
            json.dumps(dict(row, distance=pair.get("distance")), ensure_ascii=False) + "\n" for row in rows
        )
        index_out.write(
            json.dumps(
                {
                    "pair_id": pair["pair_id"],
                    "prompt_version": classify.PROMPT_VERSION,
                    "model": cfg[2],
                    "a_rev": pair["a"]["rev_id"],
                    "b_rev": pair["b"]["rev_id"],
                    "a_sha1": sha(pair["a"]["text"]),
                    "b_sha1": sha(pair["b"]["text"]),
                    "cache": f"cache/{key}.json",
                    "cached": cached,
                    "rows": len(rows),
                }
            )
            + "\n"
        )
        rows_out.flush()
        index_out.flush()
        n_rows += len(rows)
        print(
            f"{i}/{len(pairs)} {pair['pair_id']} {len(rows)} rows, {time.monotonic() - started:.0f} s",
            file=sys.stderr,
            flush=True,
        )

u = llm.USAGE
print(
    f"{args.model} ({cfg[2]}, prompt version {classify.PROMPT_VERSION}): {len(pairs)} pairs, {n_rows} rows, "
    f"{len(missing)} pairs without an answer; this run sent {sent - before} requests ({u['calls']} answered, "
    f"{u['input_tokens']:,} input and {u['output_tokens']:,} output tokens), {sent} in all runs; "
    f"{time.monotonic() - started:.0f} s"
)
for pid in missing:
    print("no answer:", pid)
