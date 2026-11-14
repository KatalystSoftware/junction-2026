"""Gemma 4 26B-A4B behind an OpenAI-compatible endpoint on Modal: the untrained model as `gemma26-base`
and our SFT adapter on top of it as `gemma26-sft`, from one vLLM with LoRA enabled.

    modal deploy modal_serve.py    # prints https://<workspace>--oncallbench-gemma-serve.modal.run
    curl $URL/v1/models

OpenCode reaches it as a provider of its own, as the judged agents run (Harbor, the shipped task):

    harbor run -p ../tasks/shift-1 -a opencode -m vllm/gemma26-sft --base-url $URL/v1 \
      --api-format openai_chat_completions --api-key-name VLLM_API_KEY --ae VLLM_API_KEY=none

The weights and the adapter come from the `aq-rl` Volume (`modal_app.py::fetch`, `ckpt/gemma26-sft`).
One H200 (or a B200 when one is free); the container stops after 15 idle minutes.
"""

import subprocess

import modal

VOL = "/vol"
NAME = "gemma26"
MODEL = "google/gemma-4-26B-A4B-it"
ADAPTER = f"{VOL}/ckpt/gemma26-sft"
PORT = 8000

vol = modal.Volume.from_name("aq-rl")
image = (
    modal.Image.from_registry("nvidia/cuda:13.0.1-devel-ubuntu24.04", add_python="3.12")
    .uv_pip_install("vllm==0.33.0", "transformers==5.20.2")  # as modal_app.py and the Verda box
    .env({"HF_HOME": f"{VOL}/hf", "HF_HUB_OFFLINE": "1"})
)
app = modal.App("oncallbench-gemma", image=image)


@app.function(gpu=["H200", "B200"], volumes={VOL: vol}, timeout=24 * 3600, scaledown_window=15 * 60,
              max_containers=1)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=20 * 60)
def serve():
    cmd = ["vllm", "serve", MODEL, "--served-model-name", f"{NAME}-base", "--host", "0.0.0.0", "--port", str(PORT),
           "--max-model-len", "131072", "--gpu-memory-utilization", "0.9", "--enable-prefix-caching",
           "--enable-auto-tool-choice", "--tool-call-parser", "gemma4", "--reasoning-parser", "gemma4",
           "--limit-mm-per-prompt", '{"image":0,"audio":0,"video":0}',
           "--enable-lora", "--max-lora-rank", "64", "--max-loras", "1", "--lora-modules", f"{NAME}-sft={ADAPTER}"]
    subprocess.Popen(cmd)
