"""Evaluate, SFT and RL an open model on the aq-incident environment.

Qwen3.5-2B trains every weight with vLLM beside it on one GPU; Gemma 4 trains LoRA adapters on a
second GPU (--lora, --train-device cuda:1) and streams the merged weights into vLLM after each step.

    python3 run.py eval --model Qwen/Qwen3.5-2B --tag base
    python3 run.py sft  --model Qwen/Qwen3.5-2B --demos cache/demos.jsonl --tag sft
    python3 run.py rl   --model ckpt/sft --tag rl --steps 40

Held-out seeds 101-106 are only ever evaluated; training seeds are drawn from 1000 up.
"""

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")  # weights are synced into the engine in place
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import core  # noqa: E402
import env  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
HELD_OUT = list(range(101, 107))


def log(path, row):
    row = dict(row, time=round(time.time()))
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row), flush=True)


def engine(model, gpu_mem, max_ctx):
    from vllm import LLM

    kw = dict(model=model, gpu_memory_utilization=gpu_mem, max_model_len=max_ctx, enable_prefix_caching=True,
              dtype="bfloat16", seed=0)
    try:
        return LLM(**kw, limit_mm_per_prompt={"image": 0, "video": 0, "audio": 0})
    except (TypeError, ValueError):
        return LLM(**kw)


LORA_TARGETS = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"


def trainer(model_path, lr, lora=0, device="cuda", adapter=None):
    """Full-parameter (fp32 master weights) or, with `lora` > 0, LoRA on the text model's linear layers."""
    import torch
    import transformers

    cfg = transformers.AutoConfig.from_pretrained(model_path)
    cls = transformers.AutoModelForCausalLM
    if hasattr(cfg, "vision_config"):
        cls = transformers.AutoModelForImageTextToText
    model = cls.from_pretrained(model_path, torch_dtype=torch.bfloat16 if lora else torch.float32).to(device)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    if lora:
        import peft

        if adapter:
            model = peft.PeftModel.from_pretrained(model, adapter, is_trainable=True)
        else:
            model = peft.get_peft_model(model, peft.LoraConfig(r=lora, lora_alpha=2 * lora, lora_dropout=0.0,
                                                               target_modules=LORA_TARGETS))
        for p in model.parameters():
            if p.requires_grad:
                p.data = p.data.float()
    else:
        for n, p in model.named_parameters():  # the text model learns; a vision tower, if any, stays put
            p.requires_grad = not any(k in n for k in ("visual", "vision"))
    model.config.use_cache = False
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, betas=(0.9, 0.99),
                            weight_decay=0.0)
    return model, opt


def evaluate(llm, chat, tag, samples, temp, levels, max_ctx, seeds=HELD_OUT, step=None):
    jobs = [(s, lv) for lv in levels for s in seeds for _ in range(samples)]
    t0 = time.time()
    trajs = core.rollout(llm, chat, jobs, temp, max_ctx=max_ctx, **chat.eval_sampling(temp))
    summary = core.summarize(trajs)
    OUT.mkdir(exist_ok=True)
    name = f"{tag}" + (f"-step{step}" if step is not None else "")
    core.dump(trajs, OUT / f"eval-{name}.jsonl", chat)
    log(OUT / "evals.jsonl", dict(tag=tag, step=step, temp=temp, samples=samples, sim=env.SIM_SHA,
                                   secs=round(time.time() - t0), levels=summary))
    return summary


def cmd_eval(o):
    from transformers import AutoTokenizer

    chat = core.make_chat(AutoTokenizer.from_pretrained(o.model), think=o.think)
    llm = engine(o.model, o.gpu_mem, o.max_ctx)
    for temp in o.temps:
        evaluate(llm, chat, o.tag, o.samples if temp else 1, temp, o.levels, o.max_ctx)


def resolve(model):
    from huggingface_hub import snapshot_download

    return model if Path(model).exists() else snapshot_download(model)


def cmd_sft(o):
    from transformers import AutoTokenizer

    o.model = resolve(o.model)
    tok = AutoTokenizer.from_pretrained(o.model)
    chat = core.make_chat(tok, think=o.think)
    demos = [json.loads(line) for line in open(o.demos)]
    assert not {d["seed"] for d in demos} & set(HELD_OUT)
    trajs = [core.demo_traj(chat, d) for d in demos if d["level"] in o.levels]
    print(f"sft: {len(trajs)} demos, {sum(len(t.ids) for t in trajs)} tokens, "
          f"{sum(sum(t.mask) for t in trajs)} trained", flush=True)
    model, opt = trainer(o.model, o.lr, o.lora, o.train_device)
    model.name_or_path = o.model
    rng = random.Random(0)
    steps = o.epochs * len(trajs) // o.batch
    sched = __import__("torch").optim.lr_scheduler.LambdaLR(
        opt, lambda i: min(1.0, (i + 1) / 5) * max(0.1, 1 - i / max(1, steps)))
    i = 0
    for epoch in range(o.epochs):
        order = core.shuffled(trajs, rng)
        for b in range(0, len(order) - o.batch + 1, o.batch):
            batch = order[b:b + o.batch]
            loss, gn = core.step(model, opt, batch, [1.0] * len(batch))
            sched.step()
            i += 1
            if i % 5 == 0:
                log(OUT / f"sft-{o.tag}.jsonl", dict(step=i, epoch=epoch, loss=round(loss, 4), grad_norm=round(gn, 3)))
    save(model, tok, HERE / "ckpt" / o.tag)


def save(model, tok, path):
    import torch

    path.mkdir(parents=True, exist_ok=True)
    if hasattr(model, "peft_config"):  # only the adapter: a merged 26B copy does not fit the disk
        model.save_pretrained(path)
        return
    model.to(torch.bfloat16).save_pretrained(path, safe_serialization=True)
    model.to(torch.float32)
    tok.save_pretrained(path)
    src = Path(model.name_or_path)
    for extra in ("preprocessor_config.json", "video_preprocessor_config.json", "chat_template.jinja",
                  "generation_config.json"):
        if (src / extra).exists() and not (path / extra).exists():
            (path / extra).write_bytes((src / extra).read_bytes())


def reward_of(t, kind):
    if kind == "score":  # the environment's score as is
        return t.reward
    if kind == "raw":  # unclipped: below do-nothing still ranks, so a group of zeros still teaches
        return max(-2.0, min(1.5, t.raw))
    raise ValueError(kind)


def cmd_rl(o):
    from transformers import AutoTokenizer

    path = resolve(o.model)
    tok = AutoTokenizer.from_pretrained(path)
    chat = core.make_chat(tok, think=o.think)
    llm = engine(path, o.gpu_mem, o.max_ctx)
    model, opt = trainer(path, o.lr, o.lora, o.train_device, o.adapter)
    model.name_or_path = path
    if o.adapter:
        core.sync(model, llm)
    rng = random.Random(o.rng)
    pool = [s for s in range(1000, 100000) if s not in HELD_OUT]
    curve = OUT / f"rl-{o.tag}.jsonl"
    if o.eval_every:
        evaluate(llm, chat, o.tag, o.eval_samples, o.eval_temp, o.levels, o.max_ctx, step=0)
    def draw():
        groups = [(rng.choice(pool), rng.choice(o.levels)) for _ in range(o.groups)]
        return [g for g in groups for _ in range(o.per)]

    def play(jobs):
        t = time.time()
        return core.rollout(llm, chat, jobs, o.temp, max_ctx=o.max_ctx), time.time() - t

    # --overlap: vLLM (cuda:0) plays step i+1 with the weights before step i's update while the
    # trainer (another GPU) learns from step i; weights are copied in once both are done
    ahead = ThreadPoolExecutor(1) if o.overlap else None
    nxt = ahead.submit(play, draw()) if ahead else None
    for i in range(1, o.steps + 1):
        trajs, roll_s = nxt.result() if nxt else play(draw())
        nxt = ahead.submit(play, draw()) if ahead and i < o.steps else None
        t1 = time.time()
        weights, used = [], []
        for g in range(o.groups):
            ts = trajs[g * o.per:(g + 1) * o.per]
            r = [reward_of(t, o.reward) for t in ts]
            mean = sum(r) / len(r)
            if max(r) - min(r) < 1e-6:
                continue  # no signal in this group
            sd = (sum((x - mean) ** 2 for x in r) / len(r)) ** 0.5
            for t, x in zip(ts, r):
                used.append(t)
                weights.append((x - mean) / (sd + 1e-4) if o.std else x - mean)
        loss, gn = core.step(model, opt, used, weights) if used else (0.0, 0.0)
        train_s = time.time() - t1
        if nxt:
            nxt.result()  # the engine must be idle before its weights change
        core.sync(model, llm)
        row = dict(step=i, reward=round(sum(t.reward for t in trajs) / len(trajs), 4),
                   raw=round(sum(t.raw for t in trajs) / len(trajs), 4),
                   by_level={lv: round(sum(t.reward for t in trajs if t.level == lv) /
                                       max(1, sum(1 for t in trajs if t.level == lv)), 4) for lv in o.levels},
                   groups_used=len(used) // o.per, turns=round(sum(t.turns for t in trajs) / len(trajs), 1),
                   finish=sum(t.ended == "finish" for t in trajs), cap=sum(t.ended == "cap" for t in trajs),
                   ctx=sum(t.ended == "context" for t in trajs), nudges=sum(t.nudges for t in trajs),
                   loss=round(loss, 5), grad_norm=round(gn, 3), roll_s=round(roll_s), train_s=round(train_s),
                   step_s=round(time.time() - t1 + (0 if o.overlap else roll_s)))
        log(curve, row)
        if o.eval_every and i % o.eval_every == 0:
            evaluate(llm, chat, o.tag, o.eval_samples, o.eval_temp, o.levels, o.max_ctx, step=i)
        if o.save_every and i % o.save_every == 0:
            save(model, tok, HERE / "ckpt" / o.tag)
    if o.steps:
        save(model, tok, HERE / "ckpt" / o.tag)
    if o.final_samples:
        evaluate(llm, chat, o.tag, o.final_samples, o.eval_temp, o.levels, o.max_ctx, step=f"{o.steps}-final")


def ints(text):
    out = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        out += range(int(lo), int(hi or lo) + 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["eval", "sft", "rl"])
    ap.add_argument("--model", default="Qwen/Qwen3.5-2B")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--levels", type=ints, default=[0, 1, 2])
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--gpu-mem", type=float, default=0.3)
    ap.add_argument("--max-ctx", type=int, default=16384, help="tokens per episode; the shift ends there")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--temps", type=lambda s: [float(x) for x in s.split(",")], default=[0.7])
    # sft
    ap.add_argument("--demos", default=str(HERE / "cache" / "demos.jsonl"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--lora", type=int, default=0, help="LoRA rank; 0 trains every weight")
    ap.add_argument("--train-device", default="cuda")
    ap.add_argument("--adapter", help="LoRA adapter to start from (rl)")
    # rl
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--groups", type=int, default=8)
    ap.add_argument("--per", type=int, default=8)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--reward", default="score", choices=["score", "raw"])
    ap.add_argument("--std", action="store_true", help="divide advantages by the group's std (GRPO)")
    ap.add_argument("--eval-every", type=int, default=10)
    ap.add_argument("--eval-samples", type=int, default=4)
    ap.add_argument("--eval-temp", type=float, default=0.7)
    ap.add_argument("--final-samples", type=int, default=0, help="held-out samples per seed after the last step")
    ap.add_argument("--save-every", type=int, default=0)
    ap.add_argument("--rng", type=int, default=0)
    ap.add_argument("--overlap", action="store_true", help="play the next step while training (one step off-policy)")
    opts = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    {"eval": cmd_eval, "sft": cmd_sft, "rl": cmd_rl}[opts.cmd](opts)
