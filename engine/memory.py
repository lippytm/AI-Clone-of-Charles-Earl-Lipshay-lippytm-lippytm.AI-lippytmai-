"""
engine/memory.py
Conversation memory and session management for the AI Clone Engine.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str       # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """
    Sliding-window conversation memory with optional disk persistence.

    Parameters
    ----------
    window:  Maximum number of turns (user+assistant pairs) to keep in context.
    persist: If True, save/load the session from ``session_dir``.
    session_id: Unique identifier for this conversation.
    session_dir: Directory where session files are stored.
    """

    def __init__(
        self,
        window: int = 20,
        persist: bool = False,
        session_id: str = "default",
        session_dir: str = ".sessions",
    ) -> None:
        self.window = window
        self.persist = persist
        self.session_id = session_id
        self.session_dir = session_dir
        self._messages: list[Message] = []

        if persist:
            os.makedirs(session_dir, exist_ok=True)
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, role: str, content: str) -> None:
        self._messages.append(Message(role=role, content=content))
        self._trim()
        if self.persist:
            self._save()

    def get_context(self, system_prompt: str) -> list[dict[str, str]]:
        """Return the full message list suitable for the LLM API."""
        context: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        context.extend(m.to_dict() for m in self._messages)
        return context

    def reset(self) -> None:
        self._messages.clear()
        if self.persist:
            self._save()

    def __len__(self) -> int:
        return len(self._messages)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        max_messages = self.window * 2  # each turn = user + assistant
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def _session_path(self) -> str:
        return os.path.join(self.session_dir, f"{self.session_id}.json")

    def _save(self) -> None:
        data: list[dict[str, Any]] = [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in self._messages
        ]
        with open(self._session_path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        path = self._session_path()
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            data: list[dict[str, Any]] = json.load(fh)
        self._messages = [
            Message(role=d["role"], content=d["content"], timestamp=d.get("timestamp", 0.0))
            for d in data
        ]
        self._trim()
