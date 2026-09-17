"""
engine/self_improvement.py
Self-Improvement System — tracks engine interactions, scores response quality,
identifies patterns, and surfaces targeted improvement suggestions over time.

The system operates entirely in-process and persists its state to a JSON file
so that learning accumulates across sessions.

Usage
-----
    from engine.self_improvement import SelfImprovementSystem

    sis = SelfImprovementSystem()
    sis.record(session_id="s1", user_input="Explain Rust ownership",
               response="Ownership is Rust's memory management model…")
    print(sis.report())
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class InteractionRecord:
    """A single logged interaction with quality metadata."""

    session_id: str
    user_input: str          # truncated to 200 chars on save
    response_length: int
    quality_score: float     # 0.0–1.0
    timestamp: float
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_input": self.user_input[:200],
            "response_length": self.response_length,
            "quality_score": round(self.quality_score, 4),
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class SelfImprovementSystem:
    """
    Observes engine interactions, accumulates quality metrics, identifies
    recurring patterns, and generates improvement recommendations.

    Parameters
    ----------
    persist_path:   Path to the JSON file that stores learning data.
    history_limit:  Maximum number of interaction records to retain in memory.
    """

    _MIN_QUALITY_ALERT = 0.4   # alert threshold for average quality
    _HIGH_QUALITY_MIN  = 0.75  # threshold for "good" responses

    def __init__(
        self,
        persist_path: str = ".sessions/self_improvement.json",
        history_limit: int = 500,
    ) -> None:
        self.persist_path = persist_path
        self.history_limit = history_limit
        self._records: list[InteractionRecord] = []
        self._improvement_notes: list[str] = []
        self._session_stats: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        session_id: str,
        user_input: str,
        response: str,
        quality_score: float | None = None,
    ) -> None:
        """
        Record an interaction and update improvement state.

        Parameters
        ----------
        session_id:    The active session identifier.
        user_input:    Raw user message text.
        response:      The engine's response text.
        quality_score: Explicit quality score (0.0–1.0). If None, the system
                       auto-estimates the score from heuristics.
        """
        if quality_score is None:
            quality_score = self._auto_score(user_input, response)

        record = InteractionRecord(
            session_id=session_id,
            user_input=user_input,
            response_length=len(response),
            quality_score=quality_score,
            timestamp=time.time(),
            tags=self._auto_tag(user_input),
        )
        self._records.append(record)
        if len(self._records) > self.history_limit:
            self._records = self._records[-self.history_limit:]

        self._update_session_stats(session_id, record)
        self._analyze()
        self._save()

    def rate_last(self, score: float) -> None:
        """
        Apply a user-provided quality rating (0.0–1.0) to the most recent record.
        Call this right after the user explicitly rates a response.
        """
        if not self._records:
            return
        self._records[-1].quality_score = max(0.0, min(1.0, score))
        self._save()

    def average_quality(self, last_n: int = 0) -> float:
        """
        Return the average quality score.

        Parameters
        ----------
        last_n: If > 0, consider only the most recent *last_n* records.
        """
        records = self._records[-last_n:] if last_n > 0 else self._records
        if not records:
            return 1.0
        return sum(r.quality_score for r in records) / len(records)

    def topic_distribution(self) -> dict[str, int]:
        """Return interaction counts grouped by auto-detected topic tag."""
        dist: dict[str, int] = {}
        for r in self._records:
            for tag in r.tags:
                dist[tag] = dist.get(tag, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: x[1], reverse=True))

    def get_improvement_notes(self) -> list[str]:
        """Return the latest improvement suggestions."""
        return list(self._improvement_notes[-10:])

    def session_summary(self, session_id: str) -> dict[str, Any]:
        """Return per-session statistics."""
        return dict(self._session_stats.get(session_id, {}))

    def report(self) -> str:
        """Return a human-readable self-improvement report."""
        total = len(self._records)
        avg_all = self.average_quality()
        avg_recent = self.average_quality(last_n=20)
        dist = self.topic_distribution()

        lines = [
            "=== Self-Improvement Report ===",
            f"Total interactions  : {total}",
            f"Avg quality (all)   : {avg_all:.3f}",
            f"Avg quality (last 20): {avg_recent:.3f}",
        ]
        if dist:
            top_items = list(dist.items())[:5]
            dist_str = ", ".join(f"{k}={v}" for k, v in top_items)
            lines.append(f"Top topics          : {dist_str}")
        if self._improvement_notes:
            lines.append("\nImprovement notes:")
            for note in self._improvement_notes[-5:]:
                lines.append(f"  • {note}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all interaction history and notes."""
        self._records.clear()
        self._improvement_notes.clear()
        self._session_stats.clear()
        self._save()

    # ------------------------------------------------------------------
    # Heuristic scoring
    # ------------------------------------------------------------------

    def _auto_score(self, user_input: str, response: str) -> float:
        """Estimate response quality (0.0–1.0) from structural heuristics."""
        score = 0.5

        # Length signals
        resp_len = len(response)
        if resp_len < 20:
            score -= 0.25
        elif resp_len > 100:
            score += 0.10
        elif resp_len > 300:
            score += 0.05   # very long ≠ always better

        # Error / uncertainty signals
        low = response.lower()
        if low.startswith("error") or "i don't know" in low or "i cannot" in low:
            score -= 0.15

        # Positive signals
        for phrase in ("because", "therefore", "for example", "specifically",
                       "in other words", "the reason", "let me explain"):
            if phrase in low:
                score += 0.05
                break

        # Keyword overlap (relevance)
        query_words = set(user_input.lower().split())
        resp_words = set(low.split())
        overlap = len(query_words & resp_words) - len({"the", "a", "is", "and", "of", "to", "in"})
        score += min(max(overlap, 0) * 0.02, 0.10)

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Topic tagging
    # ------------------------------------------------------------------

    _TOPIC_KEYWORDS: dict[str, list[str]] = {
        "code": ["code", "function", "class", "algorithm", "implement",
                 "debug", "refactor", "module", "library", "import"],
        "ai_ml": ["ai", "ml", "model", "neural", "train", "dataset",
                  "llm", "inference", "embedding", "fine-tune"],
        "architecture": ["architecture", "design", "pattern", "system",
                         "scale", "microservice", "api", "service"],
        "security": ["security", "auth", "crypto", "encrypt", "vulnerability",
                     "exploit", "xss", "injection", "cert", "tls"],
        "blockchain": ["blockchain", "solidity", "smart contract", "defi",
                       "web3", "nft", "evm", "wallet", "token"],
        "linux": ["linux", "kernel", "shell", "bash", "systemd",
                  "process", "daemon", "socket", "fork"],
        "devops": ["docker", "kubernetes", "ci", "cd", "pipeline",
                   "deploy", "helm", "terraform", "ansible"],
        "philosophy": ["think", "philosophy", "opinion", "belief",
                       "principle", "ethics", "future", "society"],
    }

    def _auto_tag(self, text: str) -> list[str]:
        text_lower = text.lower()
        tags = [
            tag for tag, keywords in self._TOPIC_KEYWORDS.items()
            if any(kw in text_lower for kw in keywords)
        ]
        return tags or ["general"]

    # ------------------------------------------------------------------
    # Analysis and improvement notes
    # ------------------------------------------------------------------

    def _analyze(self) -> None:
        """Generate or update improvement notes based on recent records."""
        if len(self._records) < 5:
            return

        recent_scores = [r.quality_score for r in self._records[-20:]]
        avg = sum(recent_scores) / len(recent_scores)
        if avg < self._MIN_QUALITY_ALERT:
            self._add_note(
                f"Low recent quality ({avg:.2f} avg over last {len(recent_scores)} turns) — "
                "consider adjusting temperature, expanding context, or switching backend."
            )

        # Identify rapidly growing topics
        dist = self.topic_distribution()
        if dist:
            top_topic = next(iter(dist))
            count = dist[top_topic]
            if count > 10:
                self._add_note(
                    f"High engagement on topic '{top_topic}' ({count} interactions) — "
                    "enriching knowledge_domains for this area may improve response depth."
                )

        # Short response streak
        recent_lengths = [r.response_length for r in self._records[-10:]]
        if recent_lengths and sum(recent_lengths) / len(recent_lengths) < 50:
            self._add_note(
                "Recent responses are very short on average — the engine may be under-elaborating. "
                "Consider increasing max_tokens or adding elaboration cues to the system prompt."
            )

    def _add_note(self, note: str) -> None:
        if note not in self._improvement_notes:
            self._improvement_notes.append(note)
        # Keep at most 30 notes
        if len(self._improvement_notes) > 30:
            self._improvement_notes = self._improvement_notes[-30:]

    # ------------------------------------------------------------------
    # Per-session tracking
    # ------------------------------------------------------------------

    def _update_session_stats(self, session_id: str, record: InteractionRecord) -> None:
        stats = self._session_stats.setdefault(session_id, {
            "turn_count": 0,
            "total_quality": 0.0,
            "tag_counts": {},
        })
        stats["turn_count"] += 1
        stats["total_quality"] += record.quality_score
        stats["avg_quality"] = stats["total_quality"] / stats["turn_count"]
        for tag in record.tags:
            stats["tag_counts"][tag] = stats["tag_counts"].get(tag, 0) + 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data: dict[str, Any] = {
            "records": [r.to_dict() for r in self._records],
            "notes": self._improvement_notes,
            "session_stats": self._session_stats,
        }
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            self._improvement_notes = data.get("notes", [])
            self._session_stats = data.get("session_stats", {})
            for d in data.get("records", []):
                self._records.append(InteractionRecord(
                    session_id=d.get("session_id", ""),
                    user_input=d.get("user_input", ""),
                    response_length=d.get("response_length", 0),
                    quality_score=d.get("quality_score", 0.5),
                    timestamp=d.get("timestamp", 0.0),
                    tags=d.get("tags", []),
                ))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # corrupt file — start fresh
