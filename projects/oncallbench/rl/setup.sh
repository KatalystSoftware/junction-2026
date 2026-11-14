#!/bin/sh
# Run on the GPU box from projects/oncallbench/rl: a Python env with vLLM and the training stack.
set -e
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv -q --python 3.12 .venv
. .venv/bin/activate
uv pip install -q vllm
uv pip install -q flash-linear-attention accelerate
python -c "import vllm, torch, transformers; print('vllm', vllm.__version__, 'torch', torch.__version__, 'transformers', transformers.__version__, torch.cuda.get_device_name())"
