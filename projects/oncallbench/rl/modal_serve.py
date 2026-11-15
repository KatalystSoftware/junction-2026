"""Gemma 4 26B-A4B behind an OpenAI-compatible endpoint on Modal: the untrained model as `gemma26-base`
and every adapter under the Volume's `ckpt/` whose name starts with `gemma26-` (ckpt/gemma26-sft is
served as `gemma26-sft`), from one vLLM with LoRA enabled, at Gemma 4's full 256k context.

    modal deploy modal_serve.py    # prints https://<workspace>--oncallbench-gemma-serve.modal.run
    curl $URL/v1/models

An adapter uploaded later (`modal volume put aq-rl <dir> /ckpt/gemma26-<name>`) is served by the next
container, or by this one at once:

    curl -X POST $URL/v1/load_lora_adapter -H 'Content-Type: application/json' \
      -d '{"lora_name": "gemma26-<name>", "lora_path": "/vol/ckpt/gemma26-<name>"}'

(reload the Volume first: the running container sees files committed before it started.)

OpenCode reaches it as a provider of its own, as the judged agents run (Harbor, the shipped task):

    harbor run -p ../tasks/shift-1 -a opencode -m vllm/gemma26-sft --base-url $URL/v1 \
      --api-format openai_chat_completions --api-key-name VLLM_API_KEY --ae VLLM_API_KEY=none

One H200 (or a B200 when one is free); the container stops after 15 idle minutes. Unauthenticated:
stop it with `modal app stop oncallbench-gemma` when no run needs it.
"""

import os
import subprocess
from pathlib import Path

import modal

VOL = "/vol"
MODEL = "google/gemma-4-26B-A4B-it"
PORT = 8000

vol = modal.Volume.from_name("aq-rl")
image = (
    modal.Image.from_registry("nvidia/cuda:13.0.1-devel-ubuntu24.04", add_python="3.12")
    .uv_pip_install("vllm==0.33.0", "transformers==5.20.2")  # as modal_app.py and the Verda box
    .env({"HF_HOME": f"{VOL}/hf", "HF_HUB_OFFLINE": "1", "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "True"})
)
app = modal.App("oncallbench-gemma", image=image)


@app.function(gpu=["H200", "B200"], volumes={VOL: vol}, timeout=24 * 3600, scaledown_window=15 * 60,
              max_containers=1)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=20 * 60)
def serve():
    adapters = sorted(p for p in Path(f"{VOL}/ckpt").glob("gemma26-*") if (p / "adapter_config.json").exists())
    cmd = ["vllm", "serve", MODEL, "--served-model-name", "gemma26-base", "--host", "0.0.0.0", "--port", str(PORT),
           "--max-model-len", "262144", "--gpu-memory-utilization", "0.9", "--enable-prefix-caching",
           "--enable-auto-tool-choice", "--tool-call-parser", "gemma4", "--reasoning-parser", "gemma4",
           "--limit-mm-per-prompt", '{"image":0,"audio":0,"video":0}',
           "--enable-lora", "--max-lora-rank", "64", "--max-loras", str(max(2, min(4, len(adapters)))),
           "--lora-modules", *[f"{p.name}={p}" for p in adapters]]
    print("adapters:", [p.name for p in adapters], flush=True)
    subprocess.Popen(cmd, env=os.environ)
