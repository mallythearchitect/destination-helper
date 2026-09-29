"""The AI services the switchboard can call. Each takes a system prompt and a
user message and returns text plus what it cost. Keys come from .env via
engine.secrets, never from the page."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from .. import secrets

# $ per million tokens (input, output). From the Anthropic price list, 2026-06.
PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5-1": (10.00, 50.00),
    "claude-opus-4-8": (5.00, 25.00),
}


@dataclass
class Reply:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    cost_cents: float
    ms: int


class ProviderError(RuntimeError):
    pass


class NotConfigured(ProviderError):
    pass


def cost_cents(model: str, inp: int | None, out: int | None, prices: dict | None = None) -> float:
    p = (prices or PRICES).get(model)
    if not p or inp is None or out is None:
        return 0.0
    return round((inp * p[0] + out * p[1]) / 1_000_000 * 100, 4)


def call_anthropic(model: str, system: str, user: str, max_tokens: int = 4000, effort: str = "low", prices: dict | None = None) -> Reply:
    key = secrets.get_for_engine("ANTHROPIC_API_KEY")
    if not key:
        raise NotConfigured("No Claude API key. Paste one in Settings → AI.")
    import anthropic
    client = anthropic.Anthropic(api_key=key, timeout=120.0)
    t0 = time.time()
    try:
        kwargs = {}
        if not model.startswith("claude-haiku"):
            kwargs["output_config"] = {"effort": effort if effort in ("low", "medium", "high") else "low"}
        resp = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                      messages=[{"role": "user", "content": user}], **kwargs)
    except anthropic.AuthenticationError:
        raise NotConfigured("The Claude API key was refused. Check it in Settings → AI.")
    except anthropic.RateLimitError as e:
        raise ProviderError(f"Claude is rate-limited right now ({e.message}). Try again in a minute.")
    except anthropic.APIStatusError as e:
        raise ProviderError(f"Claude returned an error: {e.message}")
    except anthropic.APIConnectionError:
        raise ProviderError("Could not reach Claude. Is the internet up?")
    if resp.stop_reason == "refusal":
        raise ProviderError("Claude declined this request.")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return Reply(text, resp.usage.input_tokens, resp.usage.output_tokens,
                 cost_cents(model, resp.usage.input_tokens, resp.usage.output_tokens, prices), int((time.time() - t0) * 1000))


def call_ollama(model: str, system: str, user: str, max_tokens: int = 4000) -> Reply:
    """A model on this machine, through Ollama's local HTTP API. Free, offline."""
    import urllib.error
    import urllib.request
    name = model.split("/", 1)[1] if "/" in model else model
    body = json.dumps({"model": name, "system": system, "prompt": user, "stream": False,
                       "options": {"num_predict": max_tokens, "temperature": 0}}).encode()
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                                           headers={"content-type": "application/json"}), timeout=300) as r:
            d = json.loads(r.read())
    except urllib.error.URLError:
        raise NotConfigured("Ollama isn't running on this machine (install it from ollama.com, then `ollama pull` a model).")
    return Reply(d.get("response", ""), d.get("prompt_eval_count"), d.get("eval_count"), 0.0, int((time.time() - t0) * 1000))


FAKE_REPLIES: list[str] = []   # tests push canned replies here


def call_fake(model: str, system: str, user: str, max_tokens: int = 4000) -> Reply:
    if not FAKE_REPLIES:
        raise ProviderError("fake provider: no reply queued")
    return Reply(FAKE_REPLIES.pop(0), 100, 50, 0.01, 1)


def call(model: str, system: str, user: str, max_tokens: int = 4000, effort: str = "low", prices: dict | None = None) -> Reply:
    if model.startswith("fake/"):
        return call_fake(model, system, user, max_tokens)
    if model.startswith("ollama/"):
        return call_ollama(model, system, user, max_tokens)
    if model.startswith("claude-"):
        return call_anthropic(model, system, user, max_tokens, effort, prices)
    raise ProviderError(f"unknown model {model!r}")


def is_local(model: str) -> bool:
    return model.startswith("ollama/") or model.startswith("fake/")
