"""run.py on Modal: every run in its own B200 container, weights and outputs on the `aq-rl` Volume.

    modal run modal_app.py::fetch --model google/gemma-4-26B-A4B-it       # weights into the Volume, on CPU
    modal run --detach modal_app.py --runs "rl --model ... --tag a; rl --model ... --tag b"

Each `;`-separated run is `run.py`'s own arguments. On the Volume: `hf/` (Hugging Face cache), `cache/`
(demos, shared), `ckpt/<tag>/` and `out/<tag>/` (curves, evals and the run's log, one folder per run so
parallel runs never write the same file). The simulator and task are pinned at SIM_REF (git), as on
the Verda box. Credentials: MODAL_TOKEN_ID/SECRET from `sops exec-env`.
"""

import os
import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import modal

SIM_REF = os.environ.get("AQ_SIM_REF", "3bac4f4")  # the simulator the Verda runs use
HERE = Path(__file__).resolve().parent
VOL = "/vol"
HOURS = 6
GPUS = ["B200:2", "H200:2"]  # B200s when Modal has them, else H200s; either holds vLLM or the trainer per GPU
GPUS_1 = ["B200", "H200"]  # one-GPU runs (Qwen: vLLM and trainer share it)

vol = modal.Volume.from_name("aq-rl", create_if_missing=True)
image = (
    # devel: FlashInfer compiles its kernels with nvcc on first use; torch is built for CUDA 13.0
    modal.Image.from_registry("nvidia/cuda:13.0.1-devel-ubuntu24.04", add_python="3.12")
    .uv_pip_install("vllm==0.33.0", "transformers==5.20.2", "peft==0.21.3", "flash-linear-attention==0.6.0",
                    "accelerate==1.15.0")  # the Verda box's versions
    .env({"HF_HOME": f"{VOL}/hf", "HF_XET_HIGH_PERFORMANCE": "1", "AQ_MAX_TURNS": "48",
          "AQ_SIM": "/root/pin/spikes/aq-incident/sim", "AQ_TASK": "/root/pin/spikes/aq-incident/task"})
)
if modal.is_local():
    pin = Path(tempfile.mkdtemp(prefix="aq-pin-"))
    subprocess.run(f"git archive {SIM_REF} spikes/aq-incident/sim spikes/aq-incident/task | tar -x -C {pin}",
                   shell=True, check=True, cwd=HERE.parents[2])
    image = image.add_local_dir(pin, "/root/pin")
image = image.add_local_dir(HERE, "/root/code", ignore=[".venv", "cache", "out", "ckpt", "__pycache__", "*.log"])
app = modal.App("aq-rl", image=image)


def _tag(argv):
    args = shlex.split(argv)
    return args[args.index("--tag") + 1]


@app.function(gpu=GPUS, volumes={VOL: vol}, timeout=HOURS * 3600)
def run(argv: str, submitted: float = 0.0):
    return _run(argv, submitted)


@app.function(gpu=GPUS_1, volumes={VOL: vol}, timeout=HOURS * 3600)
def run1(argv: str, submitted: float = 0.0):
    return _run(argv, submitted)


def _run(argv, submitted):
    """`python run.py <argv>` with cache/, ckpt/ and out/ on the Volume, committed every two minutes.
    The container's `nvidia-smi -L` is the first lines of out/<tag>/run.log."""
    t0 = time.time()
    tag = _tag(argv)
    work, out = Path("/root/rl"), Path(f"{VOL}/out/{tag}")
    subprocess.run(["cp", "-r", "/root/code", str(work)], check=True)
    for d in ("cache", "ckpt"):
        Path(f"{VOL}/{d}").mkdir(parents=True, exist_ok=True)
        (work / d).symlink_to(f"{VOL}/{d}")
    out.mkdir(parents=True, exist_ok=True)
    (work / "out").symlink_to(out)
    gpus = subprocess.getoutput("nvidia-smi -L")  # which of GPUS the container got
    with open(out / "run.log", "a") as log:
        log.write(f"{gpus}\n")
    print(f"[modal] {tag}: container up after {time.time() - (submitted or t0):.0f}s\n{gpus}",
          flush=True)

    done = threading.Event()

    def commit():
        while not done.wait(120):
            vol.commit()

    threading.Thread(target=commit, daemon=True).start()
    with open(out / "run.log", "a") as log:
        p = subprocess.Popen(["python", "run.py", *shlex.split(argv)], cwd=work, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        code = p.wait()
    done.set()
    vol.commit()
    print(f"[modal] {tag}: exit {code} after {time.time() - t0:.0f}s", flush=True)
    if code:
        raise RuntimeError(f"{tag}: run.py exited {code}")
    return tag


@app.function(volumes={VOL: vol}, timeout=3600, cpu=4)
def fetch(model: str):
    """Download a model's weights into the Volume's Hugging Face cache, without a GPU."""
    from huggingface_hub import snapshot_download

    t = time.time()
    path = snapshot_download(model)
    vol.commit()
    print(f"{model}: {path} in {time.time() - t:.0f}s")


@app.local_entrypoint()
def main(runs: str, gpus: int = 2):
    """Start every `;`-separated run in its own container and wait for all of them; `--gpus 1` takes
    one GPU per run (GPUS_1) instead of two (GPUS)."""
    argvs = [r.strip() for r in runs.split(";") if r.strip()]
    fn = run1 if gpus == 1 else run
    calls = [fn.spawn(a, time.time()) for a in argvs]
    for a, c in zip(argvs, calls):
        print(f"started {_tag(a)}: {c.object_id}")
    for a, c in zip(argvs, calls):
        try:
            print(f"finished {c.get()}")
        except Exception as e:  # one failed run does not stop the others
            print(f"failed {_tag(a)}: {e}")
