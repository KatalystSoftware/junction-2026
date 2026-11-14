"""Token-level plumbing shared by evaluation, SFT and RL.

A conversation is one token sequence: the chat template's prompt, then for each turn the tokens the
model generated (trained on) and the template's rendering of the tool results (not trained on).
Everything after the first prompt is built from the model's own chat template, so what vLLM sees
during rollouts, what SFT trains on and what RL scores are the same tokens.
"""

import json
import math
import random
from dataclasses import dataclass, field

import env

S, U = {"role": "system", "content": "S"}, {"role": "user", "content": "U"}
NUDGE = "Your reply had no tool call. Continue the incident with tool calls."


class Chat:
    """Qwen's ChatML: one assistant turn per reply, tool results come back as a user turn."""

    def __init__(self, tok, think=False):
        self.tok, self.think = tok, think
        self.im_end = tok.convert_tokens_to_ids("<|im_end|>")
        self.stop = sorted({self.im_end, tok.eos_token_id} - {None})
        self._prompt, self._tails = {}, {}

    def render(self, msgs, gen, tools=None):
        return self.tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=gen, tokenize=False,
                                            enable_thinking=self.think)

    def encode(self, text):
        return self.tok(text, add_special_tokens=False)["input_ids"]

    def eval_sampling(self, temp):
        """Qwen's recommended non-thinking sampling."""
        return dict(top_p=0.8, top_k=20) if temp else dict(top_p=1.0, top_k=-1)

    def decode(self, ids):
        """A reply's text without its closing stop token."""
        return self.tok.decode(ids[:-1] if ids and ids[-1] in self.stop else ids, skip_special_tokens=False)

    def prompt(self, level):
        if level not in self._prompt:
            msgs = [{"role": "system", "content": env.system_prompt(level)}, {"role": "user", "content": env.USER}]
            self._prompt[level] = self.encode(self.render(msgs, True, env.tools(level)))
        return list(self._prompt[level])

    def close(self, gen, has_calls):
        """The generated tokens as they stay in the sequence: ending with the turn's end token."""
        gen = list(gen)
        if gen and gen[-1] in self.stop:
            gen[-1] = self.im_end
        else:
            gen.append(self.im_end)
        return gen

    def _tail(self, kind, n):
        """Template text that follows a finished assistant reply: n tool results, or a user nudge,
        ending with the next generation prompt. Placeholders @@R0@@.. stand for the contents."""
        if (kind, n) not in self._tails:
            done = {"role": "assistant", "content": "", "tool_calls": [
                {"type": "function", "function": {"name": "zzdummy", "arguments": {}}}]}
            after = ([{"role": "tool", "name": "zzdummy", "content": f"@@R{i}@@"} for i in range(n)]
                     if kind == "tool" else [{"role": "user", "content": "@@R0@@"}])
            text = self.render([S, U, done] + after, True)
            self._tails[kind, n] = text[text.index("<|im_end|>", text.index("zzdummy")) + len("<|im_end|>"):]
        return self._tails[kind, n]

    def tool_results(self, names, contents):
        text = self._tail("tool", len(contents))
        for i, c in enumerate(contents):
            text = text.replace(f"@@R{i}@@", c, 1)
        return self.encode(text)

    def nudge(self):
        return self.encode(self._tail("user", 1).replace("@@R0@@", NUDGE))

    def assistant(self, calls):
        """The tokens a reply with these tool calls is, as the model would generate them."""
        msg = {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": n, "arguments": a}} for n, a in calls]}
        full, gen = self.render([S, U, msg], False), self.render([S, U], True)
        head = gen[gen.rindex("<|im_start|>assistant\n"):]
        start = full.rindex("<|im_start|>assistant\n")
        body = full[start:full.rindex("<|im_end|>")]
        assert body.startswith(head) or body.startswith("<|im_start|>assistant\n"), body[:80]
        body = body[len(head):] if body.startswith(head) else body[len("<|im_start|>assistant\n"):]
        return self.encode(body) + [self.im_end]


class GemmaChat(Chat):
    """Gemma 4: the whole shift is one model turn. A call ends with <|tool_response>, the harness
    writes the response inline and the model carries on; a reply without a call ends the turn."""

    def __init__(self, tok, think=False):
        self.tok, self.think = tok, think
        self.tr = tok.convert_tokens_to_ids("<|tool_response>")
        self.turn_end = tok.convert_tokens_to_ids("<turn|>")
        self.stop = sorted({self.tr, self.turn_end, tok.eos_token_id} - {None})
        self.im_end = self.turn_end  # what a demo's last reply ends with when it has no call
        self._prompt, self._tails = {}, {}
        text = self.render([S, U, {"role": "assistant", "content": "zzdummy"}, {"role": "user", "content": "@@R0@@"}], True)
        self._nudge = text[text.index("zzdummy") + len("zzdummy<turn|>"):]

    def eval_sampling(self, temp):
        """Gemma's recommended sampling (its generation_config)."""
        return dict(top_p=0.95, top_k=64) if temp else dict(top_p=1.0, top_k=-1)

    def close(self, gen, has_calls):
        gen = list(gen)
        end = self.tr if has_calls else self.turn_end
        if gen and gen[-1] in self.stop:
            gen[-1] = end
        else:
            gen.append(end)
        return gen

    def tool_results(self, names, contents):
        parts = [f'response:{n}{{value:<|"|>{c}<|"|>}}<tool_response|>' for n, c in zip(names, contents)]
        return self.encode("<|tool_response>".join(parts))

    def nudge(self):
        return self.encode(self._nudge.replace("@@R0@@", NUDGE))

    def assistant(self, calls):
        msg = {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": n, "arguments": a}} for n, a in calls]}
        full = self.render([S, U, msg], False)
        body = full[full.rindex("<|turn>model\n") + len("<|turn>model\n"):]
        assert body.startswith("<|tool_call>") and body.endswith("<|tool_response>"), body[:120]
        return self.encode(body[:-len("<|tool_response>")]) + [self.tr]


def make_chat(tok, think=False):
    return GemmaChat(tok, think) if "<|tool_call>" in tok.get_vocab() else Chat(tok, think)


@dataclass
class Traj:
    seed: int
    level: int
    ids: list
    mask: list
    turns: int = 0
    reward: float = 0.0
    raw: float = 0.0
    ended: str = ""
    actions: list = field(default_factory=list)
    invalid: int = 0
    nudges: int = 0


def act(chat, ep, calls):
    """Run the tool calls in a reply; returns the tokens that follow it."""
    if not calls:
        return chat.nudge(), True
    out = []
    for i, (name, args) in enumerate(calls):
        if ep.done:
            out.append(env.dumps({"ok": False, "error": "the shift is over"}))
        elif i >= env.CALLS_PER_TURN:
            out.append(env.dumps({"ok": False, "error": f"at most {env.CALLS_PER_TURN} tool calls per reply"}))
        elif name is None:
            ep.invalid += 1
            out.append(env.dumps({"ok": False, "error": args}))
        else:
            out.append(ep.step(name, args))
    return chat.tool_results([n or "error" for n, _ in calls], out), False


def rollout(llm, chat, jobs, temperature, top_p=1.0, top_k=-1, max_new=384, max_ctx=16384, max_turns=env.MAX_TURNS):
    """Play every (seed, level) job to its end, all episodes advanced together turn by turn."""
    from vllm import SamplingParams, TokensPrompt

    live = []
    for s, lv in jobs:
        ids = chat.prompt(lv)
        live.append((env.Episode(s, lv), Traj(s, lv, ids, [0] * len(ids))))
    turn = 0
    while True:
        active = [(ep, t) for ep, t in live if not ep.done]
        if not active:
            break
        sp = SamplingParams(temperature=temperature, top_p=top_p, top_k=top_k, max_tokens=max_new,
                            stop_token_ids=chat.stop)
        prompts = [TokensPrompt(prompt_token_ids=t.ids) for _, t in active]
        outs = llm.generate(prompts, sp, use_tqdm=False)
        turn += 1
        for (ep, t), o in zip(active, outs):
            calls = env.parse_calls(chat.decode(list(o.outputs[0].token_ids)))
            gen = chat.close(o.outputs[0].token_ids, bool(calls))
            t.ids += gen
            t.mask += [1] * len(gen)
            t.turns += 1
            follow, nudged = act(chat, ep, calls)
            t.nudges += nudged
            if ep.done:
                continue
            if t.turns >= max_turns:
                ep.end("cap")
            elif len(t.ids) + len(follow) + max_new > max_ctx:
                ep.end("context")
            else:
                t.ids += follow
                t.mask += [0] * len(follow)
    for ep, t in live:
        t.ended, t.invalid = ep.ended, ep.invalid
        t.actions = ep.actions()
        t.raw = ep.raw_score()
        t.reward = min(1.0, max(0.0, t.raw))
    return [t for _, t in live]


def demo_traj(chat, demo):
    """A rendered reference demo (demos.py) as a trajectory: only the replies are trained on."""
    msgs, level = demo["messages"], demo["level"]
    ids = chat.prompt(level)
    mask = [0] * len(ids)
    i = 2
    while i < len(msgs):
        m = msgs[i]
        calls = [(c["function"]["name"], c["function"]["arguments"]) for c in m["tool_calls"]]
        gen = chat.assistant(calls)
        ids += gen
        mask += [1] * len(gen)
        i += 1
        results = []
        while i < len(msgs) and msgs[i]["role"] == "tool":
            results.append(msgs[i]["content"])
            i += 1
        if i < len(msgs):  # the reply after the last results is not in the demo
            follow = chat.tool_results([c[0] for c in calls], results)
            ids += follow
            mask += [0] * len(follow)
    return Traj(demo["seed"], level, ids, mask, reward=demo["score"])


# --- training --------------------------------------------------------------------


def _chunk_logps(h, target, weight, cap):
    import torch

    logits = (h @ weight.T).float()
    if cap:  # Gemma soft-caps its logits
        logits = cap * torch.tanh(logits / cap)
    return logits.gather(-1, target[:, None])[:, 0] - logits.logsumexp(-1)


def token_logps(model, ids, mask, device, chunk=1024):
    """Log-probabilities of the masked tokens under the model. Logits over the 248k vocabulary are
    made a chunk of positions at a time and recomputed in backward, never held for all of them."""
    import torch
    from torch.utils.checkpoint import checkpoint

    hf = model.get_base_model() if hasattr(model, "get_base_model") else model
    cap = getattr(hf.config.get_text_config(), "final_logit_softcapping", None)
    x = torch.tensor(ids, device=device)[None]
    pos = torch.tensor([p for p in range(1, len(ids)) if mask[p]], device=device)
    h = hf.model(input_ids=x, use_cache=False).last_hidden_state[0, pos - 1]
    weight, target = hf.get_output_embeddings().weight, x[0, pos]
    return torch.cat([checkpoint(_chunk_logps, h[i:i + chunk], target[i:i + chunk], weight, cap, use_reentrant=False)
                      for i in range(0, len(pos), chunk)])


def step(model, opt, batch, weights, clip=1.0):
    """One optimizer step: maximise sum_i w_i * sum_t logp_it over all masked tokens of the batch,
    normalised by the batch's token count (DAPO-style token-level averaging)."""
    import torch

    model.train()
    device = next(p for p in model.parameters() if p.requires_grad).device
    n_tok = sum(sum(t.mask) for t in batch)
    total = 0.0
    for t, w in zip(batch, weights):
        if not w:
            continue
        with torch.autocast(device.type, dtype=torch.bfloat16):
            lp = token_logps(model, t.ids, t.mask, device)
        loss = -(w * lp.sum()) / n_tok
        loss.backward()
        total += float(loss)
    gn = float(torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], clip))
    opt.step()
    opt.zero_grad(set_to_none=True)
    return total, gn


def lora_merged(model):
    """(checkpoint name, merged weight) for every LoRA-adapted layer, one at a time."""
    import torch

    for name, mod in model.named_modules():
        if hasattr(mod, "lora_A") and "default" in getattr(mod, "lora_A", {}):
            base = mod.base_layer.weight
            delta = (mod.lora_B["default"].weight.float() @ mod.lora_A["default"].weight.float()) * mod.scaling["default"]
            yield (name.removeprefix("base_model.model.") + ".weight",
                   (base.float() + delta).to(torch.bfloat16).to("cuda:0"))


def sync(model, llm):
    """Copy the trained weights into the vLLM engine in place (single-process engine, on cuda:0)."""
    import torch

    if hasattr(model, "peft_config"):
        weights = lora_merged(model)
    else:
        weights = [(n, p.detach().to(torch.bfloat16)) for n, p in model.state_dict().items()]
    engine = llm.llm_engine
    try:
        runner = engine.model_executor.driver_worker.worker.model_runner
    except AttributeError:
        runner = engine.engine_core.engine_core.model_executor.driver_worker.worker.model_runner
    runner.model.load_weights(weights)
    llm.reset_prefix_cache()


def summarize(trajs):
    by = {}
    for t in trajs:
        by.setdefault(t.level, []).append(t)
    out = {}
    for lv, ts in sorted(by.items()):
        r = [t.reward for t in ts]
        mean = sum(r) / len(r)
        sd = math.sqrt(sum((x - mean) ** 2 for x in r) / max(1, len(r) - 1))
        out[lv] = dict(n=len(r), mean=round(mean, 4), se=round(sd / math.sqrt(len(r)), 4),
                       raw=round(sum(t.raw for t in ts) / len(ts), 4),
                       turns=round(sum(t.turns for t in ts) / len(ts), 1),
                       ended={k: sum(1 for t in ts if t.ended == k) for k in {t.ended for t in ts}},
                       per_seed={s: round(sum(t.reward for t in ts if t.seed == s) /
                                          sum(1 for t in ts if t.seed == s), 3) for s in sorted({t.seed for t in ts})})
    return out


def shuffled(xs, rng=random):
    xs = list(xs)
    rng.shuffle(xs)
    return xs


def dump(trajs, path, chat=None):
    """One JSON row per episode; with `chat`, also the transcript after the prompt."""
    with open(path, "w") as f:
        for t in trajs:
            row = dict(seed=t.seed, level=t.level, reward=t.reward, raw=t.raw, turns=t.turns, ended=t.ended,
                       actions=t.actions, invalid=t.invalid, nudges=t.nudges)
            if chat is not None:
                row["text"] = chat.tok.decode(t.ids[len(chat.prompt(t.level)):], skip_special_tokens=False)
            f.write(json.dumps(row) + "\n")
