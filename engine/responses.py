"""
engine/responses.py
Response generation layer — wraps LLM backends with a unified interface.

Supported backends:
  - "openai"  : OpenAI Chat Completions API (requires OPENAI_API_KEY env var)
  - "ollama"  : Local Ollama server (http://localhost:11434)
  - "mock"    : Deterministic offline responses for testing / demo
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
# Backend: Ollama
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
# Public interface
# ---------------------------------------------------------------------------

_BACKENDS = {
    "openai": _openai_generate,
    "ollama": _ollama_generate,
    "mock": _mock_generate,
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
