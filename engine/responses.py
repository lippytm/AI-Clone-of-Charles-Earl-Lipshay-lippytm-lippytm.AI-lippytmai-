"""
engine/responses.py
Response generation layer — wraps LLM backends with a unified interface.

Supported backends:
  - "mock"        : Deterministic offline responses for testing / demo (no deps)
  - "openai"      : OpenAI Chat Completions API      (requires OPENAI_API_KEY)
  - "anthropic"   : Anthropic API — Claude Fable 5   (requires ANTHROPIC_API_KEY)
  - "hermes"      : Nous-Hermes via local Ollama      (requires Ollama running)
  - "ollama"      : Any model via local Ollama        (requires Ollama running)
  - "openrouter"  : OpenRouter cloud — Hermes, Fable 5, and 200+ models
                    (requires OPENROUTER_API_KEY)

Backend selection guide
-----------------------
Set "backend" in config/engine_config.json (or pass backend= to ResponseGenerator).
Pair each backend with its preferred model:

  mock        → (any string, ignored)
  openai      → "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", …
  anthropic   → "claude-fable-5", "claude-opus-4", "claude-sonnet-4-5", …
  hermes      → "nous-hermes2", "hermes3", "hermes3:8b", …
  ollama      → "llama3", "mistral", "phi3", "deepseek-coder", …
  openrouter  → "nousresearch/hermes-3-llama-3.1-405b",
                "anthropic/claude-fable-5", "openai/gpt-4o", …
"""

from __future__ import annotations

import os
import random
from typing import Any


# ---------------------------------------------------------------------------
# Backend: Mock (no external dependencies)
# ---------------------------------------------------------------------------

_MOCK_REPLIES = [
    "That's a great question. Let me think about it from my perspective…",
    "Honestly, the way I see it — this comes down to fundamentals.",
    "I've spent a lot of time on this topic. Here's what I've concluded:",
    "Interesting. My take is always grounded in real-world experience.",
    "You know, this reminds me of something I was working on recently.",
    "The short answer: yes. The long answer: it depends on context.",
    "From a systems thinking standpoint, everything is connected.",
    "I'll be direct — there's no single right answer here.",
    "Whether it's Solidity, Rust, or Python — the fundamentals transfer.",
    "Cross-chain, cross-language — the patterns are universal.",
    "From kernel space to smart contracts, it's all about the abstractions.",
    "The Linux ecosystem taught me how to think at the systems level.",
    "Blockchain is just distributed systems with cryptographic trust — let's dig in.",
]


def _mock_generate(messages: list[dict[str, str]], **_kwargs: Any) -> str:
    user_content = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    base = random.choice(_MOCK_REPLIES)
    if user_content:
        snippet = user_content[:60].rstrip()
        return f'{base}\n\nRegarding "{snippet}" — I think the nuance matters most.'
    return base


# ---------------------------------------------------------------------------
# Backend: OpenAI
# ---------------------------------------------------------------------------

def _openai_generate(
    messages: list[dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.85,
    max_tokens: int = 512,
    **_kwargs: Any,
) -> str:
    try:
        import openai  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai package is required for the 'openai' backend. "
            "Install it with: pip install openai"
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Export it before running the engine."
        )

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Backend: Anthropic — Claude Fable 5 and other Anthropic models
# ---------------------------------------------------------------------------

def _anthropic_generate(
    messages: list[dict[str, str]],
    model: str = "claude-fable-5",
    temperature: float = 0.85,
    max_tokens: int = 512,
    **_kwargs: Any,
) -> str:
    """
    Use the Anthropic SDK to call Claude Fable 5 or any other Anthropic model.

    The system message is extracted from the messages list and passed via the
    dedicated ``system`` parameter, as required by the Anthropic Messages API.

    Environment variable required:
        ANTHROPIC_API_KEY
    """
    try:
        import anthropic  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "anthropic package is required for the 'anthropic' backend. "
            "Install it with: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it before running the engine."
        )

    # The Anthropic API separates system prompts from conversation turns.
    system_text = ""
    conversation: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            conversation.append({"role": msg["role"], "content": msg["content"]})

    client = anthropic.Anthropic(api_key=api_key)
    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=conversation,  # type: ignore[arg-type]
    )
    if system_text:
        kwargs["system"] = system_text

    response = client.messages.create(**kwargs)
    block = response.content[0] if response.content else None
    return block.text if block and hasattr(block, "text") else ""


# ---------------------------------------------------------------------------
# Backend: Hermes — Nous-Hermes models via local Ollama
# ---------------------------------------------------------------------------

def _hermes_generate(
    messages: list[dict[str, str]],
    model: str = "nous-hermes2",
    temperature: float = 0.85,
    **_kwargs: Any,
) -> str:
    """
    Run Nous-Hermes models locally through an Ollama server.

    Supported Hermes models (pull with ``ollama pull <model>``):
        nous-hermes2        — Hermes 2 Pro (recommended general-purpose)
        hermes3             — Hermes 3 (latest, instruction-tuned)
        hermes3:8b          — Hermes 3 8B (fast, lightweight)
        nous-hermes2-mistral — Mistral-based Hermes 2

    Override the Ollama server URL with the OLLAMA_BASE_URL environment variable
    (default: http://localhost:11434).
    """
    try:
        import requests  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "requests package is required for the 'hermes' backend. "
            "Install it with: pip install requests"
        ) from exc

    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    resp = requests.post(f"{url}/api/chat", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ---------------------------------------------------------------------------
# Backend: Ollama (generic — any model served locally)
# ---------------------------------------------------------------------------

def _ollama_generate(
    messages: list[dict[str, str]],
    model: str = "llama3",
    temperature: float = 0.85,
    **_kwargs: Any,
) -> str:
    try:
        import requests  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "requests package is required for the 'ollama' backend. "
            "Install it with: pip install requests"
        ) from exc

    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    resp = requests.post(f"{url}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ---------------------------------------------------------------------------
# Backend: OpenRouter — cloud routing to Hermes, Fable 5, and 200+ models
# ---------------------------------------------------------------------------

def _openrouter_generate(
    messages: list[dict[str, str]],
    model: str = "nousresearch/hermes-3-llama-3.1-405b",
    temperature: float = 0.85,
    max_tokens: int = 512,
    **_kwargs: Any,
) -> str:
    """
    Call any model available on OpenRouter using its OpenAI-compatible API.

    Popular models for this engine:
        nousresearch/hermes-3-llama-3.1-405b  — Hermes 3 405B (flagship)
        nousresearch/hermes-3-llama-3.1-70b   — Hermes 3 70B (fast)
        anthropic/claude-fable-5              — Claude Fable 5
        openai/gpt-4o                         — GPT-4o
        mistralai/mistral-large               — Mistral Large

    Environment variable required:
        OPENROUTER_API_KEY
    Optional site identification headers (recommended by OpenRouter):
        OPENROUTER_SITE_URL   (e.g. https://github.com/lippytm)
        OPENROUTER_SITE_NAME  (e.g. lippytmai)
    """
    try:
        import openai  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai package is required for the 'openrouter' backend. "
            "Install it with: pip install openai"
        ) from exc

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Export it before running the engine."
        )

    extra_headers: dict[str, str] = {}
    site_url = os.environ.get("OPENROUTER_SITE_URL", "https://github.com/lippytm")
    site_name = os.environ.get("OPENROUTER_SITE_NAME", "lippytmai")
    if site_url:
        extra_headers["HTTP-Referer"] = site_url
    if site_name:
        extra_headers["X-Title"] = site_name

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers=extra_headers,
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_BACKENDS = {
    "mock": _mock_generate,
    "openai": _openai_generate,
    "anthropic": _anthropic_generate,
    "hermes": _hermes_generate,
    "ollama": _ollama_generate,
    "openrouter": _openrouter_generate,
}


class ResponseGenerator:
    def __init__(
        self,
        backend: str = "mock",
        model: str = "gpt-4o",
        temperature: float = 0.85,
        max_tokens: int = 512,
    ) -> None:
        if backend not in _BACKENDS:
            raise ValueError(
                f"Unknown backend '{backend}'. Choose from: {list(_BACKENDS)}"
            )
        self.backend = backend
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, messages: list[dict[str, str]]) -> str:
        fn = _BACKENDS[self.backend]
        return fn(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
