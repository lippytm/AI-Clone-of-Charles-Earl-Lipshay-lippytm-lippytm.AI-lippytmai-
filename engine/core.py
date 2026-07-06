"""
engine/core.py
CloneEngine — the main orchestrator for the AI Clone Engine.

Usage:
    from engine.core import CloneEngine

    engine = CloneEngine()
    print(engine.chat("What's your take on AI?"))
"""

from __future__ import annotations

import json
import os
from typing import Any

from .memory import ConversationMemory
from .personality import PersonalityProfile
from .performance import PerformanceMonitor
from .responses import ResponseGenerator, _BACKENDS
from .sandbox import AISandbox
from .self_healing import SelfHealingSystem
from .self_improvement import SelfImprovementSystem
from .toolkit import AIToolkit

_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "engine_config.json")
_DEFAULT_PROFILE = os.path.join(os.path.dirname(__file__), "..", "config", "personality_profile.json")


def _load_config(path: str) -> dict[str, Any]:
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class CloneEngine:
    """
    The AI Clone Engine of Charles-Earl-Lipshay.

    Sub-systems
    -----------
    toolkit          — AI Toolkit: code analysis, generation, test stubs, smell detection.
    sandbox          — AI Sandbox: isolated Python code execution with timeout + safety.
    self_improvement — Self-Improvement System: interaction tracking & quality scoring.
    self_healing     — Self-Healing System: circuit breakers, backend failover, health monitoring.
    performance      — Performance Monitor: latency, error rate, and memory metrics.

    Parameters
    ----------
    config_path:   Path to engine_config.json (uses bundled default if omitted).
    profile_path:  Path to personality_profile.json (uses bundled default if omitted).
    session_id:    Unique session name for persistent memory.
    """

    VERSION = "3.0.0"

    def __init__(
        self,
        config_path: str | None = None,
        profile_path: str | None = None,
        session_id: str = "default",
    ) -> None:
        cfg = _load_config(config_path or _DEFAULT_CONFIG)
        profile_path = profile_path or _DEFAULT_PROFILE

        # Personality
        if os.path.exists(os.path.abspath(profile_path)):
            self.personality = PersonalityProfile.from_file(profile_path)
        else:
            self.personality = PersonalityProfile()

        # Response generator
        self.generator = ResponseGenerator(
            backend=cfg.get("backend", "mock"),
            model=cfg.get("model", "gpt-4o"),
            temperature=cfg.get("temperature", 0.85),
            max_tokens=cfg.get("max_tokens", 512),
        )

        # Memory
        session_dir = cfg.get("session_dir", ".sessions")
        self.memory = ConversationMemory(
            window=cfg.get("memory_window", 20),
            persist=cfg.get("session_persist", False),
            session_id=session_id,
            session_dir=session_dir,
        )

        self._system_prompt = self.personality.build_system_prompt()

        # ----------------------------------------------------------------
        # Industrial-grade AI sub-systems
        # ----------------------------------------------------------------

        # AI Toolkit
        self.toolkit = AIToolkit()

        # AI Sandbox
        sandbox_cfg = cfg.get("sandbox", {})
        self.sandbox = AISandbox(
            timeout=sandbox_cfg.get("timeout", 5.0),
            max_output=sandbox_cfg.get("max_output", 8192),
            safe_mode=sandbox_cfg.get("safe_mode", True),
        )

        # Self-Improvement System
        improve_cfg = cfg.get("self_improvement", {})
        self.self_improvement = SelfImprovementSystem(
            persist_path=os.path.join(
                session_dir, improve_cfg.get("persist_file", "self_improvement.json")
            ),
            history_limit=improve_cfg.get("history_limit", 500),
        )

        # Self-Healing System
        healing_cfg = cfg.get("self_healing", {})
        self.self_healing = SelfHealingSystem(
            fallback_backends=healing_cfg.get(
                "fallback_backends",
                ["anthropic", "openrouter", "ollama", "hermes", "mock"],
            ),
            failure_threshold=healing_cfg.get("failure_threshold", 3),
            recovery_timeout=healing_cfg.get("recovery_timeout", 60.0),
        )

        # Performance Monitor
        perf_cfg = cfg.get("performance", {})
        self.performance = PerformanceMonitor(
            persist_path=os.path.join(
                session_dir, perf_cfg.get("persist_file", "performance.json")
            ),
            sample_limit=perf_cfg.get("sample_limit", 1000),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_input: str) -> str:
        """
        Send a message and receive a response in character.

        The call is wrapped by the Performance Monitor (latency), routed
        through the Self-Healing System (backend failover), and recorded
        by the Self-Improvement System (quality tracking).

        Parameters
        ----------
        user_input: The user's message text.

        Returns
        -------
        The engine's in-character response string.
        """
        user_input = user_input.strip()
        if not user_input:
            return ""

        self.memory.add("user", user_input)
        messages = self.memory.get_context(self._system_prompt)

        try:
            with self.performance.measure("chat", backend=self.generator.backend):
                raw, _backend_used = self.self_healing.generate_with_failover(
                    primary_backend=self.generator.backend,
                    backends=_BACKENDS,
                    messages=messages,
                    model=self.generator.model,
                    temperature=self.generator.temperature,
                    max_tokens=self.generator.max_tokens,
                )
        except Exception:
            raw = self.generator.generate(messages)

        response = self.personality.apply_style(raw)
        self.memory.add("assistant", response)

        self.self_improvement.record(
            session_id=self.memory.session_id,
            user_input=user_input,
            response=response,
        )
        self.performance.record_memory()
        self.performance.save()

        return response

    def reset(self) -> None:
        """Clear all conversation memory for the current session."""
        self.memory.reset()

    def profile_summary(self) -> str:
        """Return a human-readable summary of the active personality profile."""
        p = self.personality
        lines = [
            f"Name      : {p.name}",
            f"Handle    : @{p.handle}",
            f"AI handle : {p.tagline}",
            f"Traits    : {', '.join(p.traits) or 'N/A'}",
            f"Interests : {', '.join(p.interests) or 'N/A'}",
            f"Domains   : {', '.join(p.knowledge_domains) or 'N/A'}",
            f"Backend   : {self.generator.backend} / {self.generator.model}",
            f"Engine v  : {self.VERSION}",
        ]
        return "\n".join(lines)

    def health_report(self) -> str:
        """Return the Self-Healing System health report."""
        return self.self_healing.report()

    def improvement_report(self) -> str:
        """Return the Self-Improvement System report."""
        return self.self_improvement.report()

    def performance_report(self) -> str:
        """Return the Performance Monitor report."""
        return self.performance.report()

    def toolkit_report(self) -> str:
        """Return the AI Toolkit usage report."""
        return self.toolkit.report()

    def __repr__(self) -> str:
        return (
            f"CloneEngine(version={self.VERSION!r}, "
            f"backend={self.generator.backend!r}, "
            f"session={self.memory.session_id!r})"
        )
