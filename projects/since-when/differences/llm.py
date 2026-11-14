"""The model behind the classifier: any OpenAI-compatible chat completions endpoint.

Providers, in the order they are tried; the first whose key is set is used, or the one named by
DIFFERENCES_PROVIDER:

  custom     DIFFERENCES_API_KEY at DIFFERENCES_BASE_URL (default: Anthropic's)
  nvidia     NVIDIA_API_KEY, https://integrate.api.nvidia.com/v1 (NVIDIA Build, free tier)
  anthropic  ANTHROPIC_API_KEY, https://api.anthropic.com/v1 (OpenAI-compatible API)
  verda      VERDA_INFERENCE_API_KEY, https://inference.verda.com/v1 (an inference key, not the
             VERDA_CLIENT_ID/SECRET cloud credentials)
  vultr      VULTR_INFERENCE_API_KEY, https://api.vultrinference.com/v1

Request settings, all optional:

  DIFFERENCES_TEMPERATURE  default 0; NVIDIA recommends 1.0 for Nemotron text
  DIFFERENCES_TOP_P        not sent by default; NVIDIA recommends 0.95 for Nemotron text
  DIFFERENCES_THINKING     on or off: Nemotron's reasoning mode, sent as
                           chat_template_kwargs.enable_thinking. Not sent by default.
  DIFFERENCES_RPM          requests a minute this process sends, retries included, across all
                           workers; default 30, under NVIDIA's free-tier limit of about 40

DIFFERENCES_BASE_URL and DIFFERENCES_MODEL override the endpoint and model. Other endpoints
that work: https://api.openai.com/v1, a local vLLM or Ollama server. With no key at all, the
classifier runs the word list only.
"""

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request

ANTHROPIC = ("https://api.anthropic.com/v1", "claude-haiku-5-5")
PROVIDERS = {  # name -> (key variable, base URL, default model)
    "custom": ("DIFFERENCES_API_KEY", *ANTHROPIC),
    "nvidia": ("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
    "anthropic": ("ANTHROPIC_API_KEY", *ANTHROPIC),
    "verda": ("VERDA_INFERENCE_API_KEY", "https://inference.verda.com/v1", "deepseek-4-1-flash-1017"),
    "vultr": ("VULTR_INFERENCE_API_KEY", "https://api.vultrinference.com/v1", "deepseek-v4.1-flash-1017"),
}


def config():
    """(base_url, api_key, model), or None when no key is set."""
    chosen = os.environ.get("DIFFERENCES_PROVIDER")
    names = [chosen] if chosen else list(PROVIDERS)
    for name in names:
        var, base_url, model = PROVIDERS[name]
        if os.environ.get(var):
            return (
                os.environ.get("DIFFERENCES_BASE_URL", base_url).rstrip("/"),
                os.environ[var],
                os.environ.get("DIFFERENCES_MODEL", model),
            )
    return None


def options():
    """Request settings from the environment, merged into every request and part of the cache key."""
    # Nemotron's reasoning alone can use 15,000 tokens on a long pair; a lower limit cuts the
    # answer off before the JSON.
    opts = {"temperature": float(os.environ.get("DIFFERENCES_TEMPERATURE", "0")), "max_tokens": 32768}
    if os.environ.get("DIFFERENCES_TOP_P"):
        opts["top_p"] = float(os.environ["DIFFERENCES_TOP_P"])
    thinking = os.environ.get("DIFFERENCES_THINKING", "").lower()
    if thinking in ("on", "off"):
        opts["chat_template_kwargs"] = {"enable_thinking": thinking == "on"}
    return opts


def _post(url, key, body, timeout=300):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# Rate limits (NVIDIA's free tier allows about 40 requests a minute) can last a while in a run of
# thousands of pairs, so a request waits about five minutes in all before it fails.
RETRIES = 10


def _backoff(attempt):
    return min(60, 2 ** attempt * 2) * (0.5 + random.random())


# Many workers starting together, and their retries, exceed a per-minute limit at once and keep
# it exceeded; spacing every request evenly keeps the whole process under it.
_pace_lock = threading.Lock()
_next_send = [0.0]


def _pace():
    gap = 60 / float(os.environ.get("DIFFERENCES_RPM", "30"))
    with _pace_lock:
        now = time.monotonic()
        send = max(now, _next_send[0])
        _next_send[0] = send + gap
    time.sleep(send - now)


# Tokens billed by this process, for cost estimates. Answers read from the cache are not counted.
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
_usage_lock = threading.Lock()


def chat_json(messages, schema, cfg):
    """The model's answer as a string that should hold JSON matching schema.

    Asks for strict JSON schema output, and falls back to plain JSON mode, then to no format at
    all, for endpoints that refuse one. Retries rate limits and server errors.
    """
    base_url, key, model = cfg
    formats = [
        {"type": "json_schema", "json_schema": {"name": "differences", "strict": True, "schema": schema}},
        {"type": "json_object"},
        None,
    ]
    for fmt in formats:
        body = {"model": model, "messages": messages, **options()}
        if fmt:
            body["response_format"] = fmt
        for attempt in range(RETRIES):
            try:
                _pace()
                data = _post(f"{base_url}/chat/completions", key, body)
                usage = data.get("usage") or {}
                with _usage_lock:
                    USAGE["calls"] += 1
                    USAGE["input_tokens"] += usage.get("prompt_tokens", 0)
                    USAGE["output_tokens"] += usage.get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"] or ""
            except urllib.error.HTTPError as e:
                if e.code == 400 and fmt is not None:
                    break  # try the next format
                if e.code in (429, 500, 502, 503, 504) and attempt < RETRIES - 1:
                    time.sleep(_backoff(attempt))
                    continue
                raise RuntimeError(f"{e.code} from {base_url}: {e.read()[:500]!r}") from e
            except (urllib.error.URLError, TimeoutError):
                if attempt < RETRIES - 1:
                    time.sleep(_backoff(attempt))
                    continue
                raise
    raise RuntimeError(f"{base_url} refused every request format")
