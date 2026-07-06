"""
engine/database.py
AI Database System — multi-category persistent stores for Transparency,
Security, Documentation, Improvement, and Healing.

These five databases form the knowledge backbone of the engine:

  TransparencyDatabase  — full audit trail of every AI decision
  SecurityDatabase      — threat detection, blocked operations, security events
  DocumentationDatabase — knowledge base, auto-extracted facts, generated docs
  ImprovementDatabase   — successful patterns powering self-improvement
  HealingDatabase       — error→strategy mappings powering self-healing

Usage
-----
    from engine.database import AIDatabaseSystem

    db = AIDatabaseSystem(db_dir=".sessions/db")

    # Screen input before processing
    result = db.check_security(user_input, session_id="s1")

    # Record a completed interaction (populates transparency, docs, improvement)
    db.record_interaction(session_id, user_input, response,
                          system_prompt, backend, model, temperature,
                          quality_score, tags)

    # Query patterns for self-improvement
    patterns = db.query_improvement_patterns(topic="code")

    # Look up a healing strategy for a known error
    strategy = db.query_healing_strategy("connection_refused")

    # Full multi-database report
    print(db.report())
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


# ============================================================
# Shared helpers
# ============================================================

def _uid() -> str:
    """Return a 12-char random hex identifier."""
    return uuid.uuid4().hex[:12]


def _sha256_short(text: str) -> str:
    """Return a 16-char SHA-256 hash of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ============================================================
# Transparency Database
# ============================================================

@dataclass
class TransparencyRecord:
    """
    A single audited AI interaction.

    Fields
    ------
    record_id          : Unique record identifier.
    session_id         : Session this interaction belongs to.
    input_preview      : First 200 chars of the user's input.
    system_prompt_hash : Short SHA-256 of the system prompt (not the full text).
    backend            : LLM backend used.
    model              : Model identifier.
    temperature        : Sampling temperature.
    response_preview   : First 200 chars of the generated response.
    quality_score      : Estimated or provided quality (0.0–1.0).
    tags               : Auto-detected topic tags.
    timestamp          : UNIX epoch of the interaction.
    """

    record_id: str
    session_id: str
    input_preview: str
    system_prompt_hash: str
    backend: str
    model: str
    temperature: float
    response_preview: str
    quality_score: float
    tags: list[str]
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TransparencyRecord":
        return cls(**d)


class TransparencyDatabase:
    """
    Full audit trail for AI transparency and explainability.

    Every interaction is stored with enough metadata to answer:
    "Why did the engine produce this response?"
    """

    def __init__(self, persist_path: str, record_limit: int = 2000) -> None:
        self.persist_path = persist_path
        self.record_limit = record_limit
        self._records: list[TransparencyRecord] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
        backend: str,
        model: str,
        temperature: float,
        response: str,
        quality_score: float,
        tags: list[str],
    ) -> TransparencyRecord:
        """Record a single interaction in the audit trail."""
        rec = TransparencyRecord(
            record_id=_uid(),
            session_id=session_id,
            input_preview=user_input[:200],
            system_prompt_hash=_sha256_short(system_prompt),
            backend=backend,
            model=model,
            temperature=temperature,
            response_preview=response[:200],
            quality_score=quality_score,
            tags=list(tags),
            timestamp=time.time(),
        )
        self._records.append(rec)
        self._trim()
        self._save()
        return rec

    def get_recent(self, n: int = 20) -> list[TransparencyRecord]:
        """Return the *n* most recent records."""
        return list(self._records[-n:])

    def get_by_session(self, session_id: str) -> list[TransparencyRecord]:
        """Return all records for a given *session_id*."""
        return [r for r in self._records if r.session_id == session_id]

    def get_by_backend(self, backend: str) -> list[TransparencyRecord]:
        """Return all records generated by a specific *backend*."""
        return [r for r in self._records if r.backend == backend]

    def audit_summary(self) -> dict[str, Any]:
        """Return a statistical audit summary."""
        if not self._records:
            return {"total_records": 0, "avg_quality": 0.0, "sessions": 0,
                    "backends_used": {}, "models_used": {}}
        backends: dict[str, int] = {}
        models: dict[str, int] = {}
        total_quality = 0.0
        for r in self._records:
            backends[r.backend] = backends.get(r.backend, 0) + 1
            models[r.model] = models.get(r.model, 0) + 1
            total_quality += r.quality_score
        return {
            "total_records": len(self._records),
            "avg_quality": round(total_quality / len(self._records), 4),
            "backends_used": backends,
            "models_used": models,
            "sessions": len({r.session_id for r in self._records}),
        }

    def report(self) -> str:
        """Return a human-readable transparency report."""
        s = self.audit_summary()
        lines = [
            "--- Transparency Database ---",
            f"Total audit records : {s['total_records']}",
            f"Avg quality         : {s['avg_quality']:.3f}",
            f"Unique sessions     : {s['sessions']}",
            f"Backends used       : {s['backends_used']}",
            f"Models used         : {s['models_used']}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        if len(self._records) > self.record_limit:
            self._records = self._records[-self.record_limit:]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data = [r.to_dict() for r in self._records[-500:]]
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: list[dict[str, Any]] = json.load(fh)
            self._records = [TransparencyRecord.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass


# ============================================================
# Security Database
# ============================================================

@dataclass
class SecurityEvent:
    """
    A single detected or suspected security incident.

    category  : "injection_attempt" | "anomaly" | "sandbox_threat" | "blocked" | "rate_limit"
    severity  : "low" | "medium" | "high" | "critical"
    source    : "user_input" | "backend_response" | "sandbox"
    blocked   : True if the triggering operation was blocked.
    """

    event_id: str
    category: str
    severity: str
    source: str
    detail: str
    blocked: bool
    session_id: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SecurityEvent":
        return cls(**d)


@dataclass
class SecurityCheckResult:
    """Result of a security input screening."""

    safe: bool
    threat_level: str      # "none" | "low" | "medium" | "high" | "critical"
    threats: list[str]     # e.g. ["injection_attempt:high", "anomaly:low"]
    blocked: bool


# ---------------------------------------------------------------------------
# Compiled threat-detection patterns
# Each entry: (regex pattern, category, severity)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (r"ignore\s+(previous|prior|above)\s+instructions?", "injection_attempt", "high"),
    (r"system\s*:\s*you\s+are", "injection_attempt", "high"),
    (r"override\s+(your\s+)?(instructions?|directives?|rules?)", "injection_attempt", "high"),
    (r"do\s+not\s+follow\s+(your\s+)?(training|guidelines|rules)", "injection_attempt", "medium"),
    (r"pretend\s+(you\s+are|to\s+be)\s+(?:a\s+)?(?:different|evil|jailbreak)", "injection_attempt", "medium"),
    (r"(?:drop|delete|truncate)\s+(?:table|database|schema)", "injection_attempt", "high"),
    (r"<\s*script[^>]*>", "injection_attempt", "high"),
    (r"javascript\s*:\s*(?:void|alert|document)", "injection_attempt", "medium"),
    (r"data\s*:\s*text\/html", "injection_attempt", "medium"),
    (r"(?:__import__|compile)\s*\(\s*[\"']", "sandbox_threat", "critical"),
    (r"open\s*\(\s*[\"'][/\\](?:etc|proc|dev|root)", "sandbox_threat", "high"),
    (r"(?:rmdir|shutil\.rmtree|os\.remove|os\.unlink)\s*\(", "sandbox_threat", "high"),
]

_ANOMALY_PATTERNS: list[tuple[str, str, str]] = [
    (r".{5001,}", "anomaly", "medium"),                        # extremely long inputs
    (r"[\x00-\x08\x0b\x0e-\x1f\x7f]{3,}", "anomaly", "low"), # clusters of control chars
]

_SEVERITY_RANK: dict[str, int] = {
    "none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4
}


class SecurityDatabase:
    """
    Security event log and real-time threat detection.

    Screens text inputs against known injection, sandbox-escape, and
    anomaly patterns.  All detections are persisted for audit purposes.
    """

    def __init__(self, persist_path: str, event_limit: int = 1000) -> None:
        self.persist_path = persist_path
        self.event_limit = event_limit
        self._events: list[SecurityEvent] = []
        self._block_counts: dict[str, int] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_input(
        self,
        text: str,
        session_id: str = "unknown",
        block_on_high: bool = False,
    ) -> SecurityCheckResult:
        """
        Screen *text* for threats.

        Parameters
        ----------
        text         : Input string to screen.
        session_id   : Session identifier for event attribution.
        block_on_high: If True, set ``blocked=True`` for high/critical severity
                       detections (caller should act on the ``blocked`` flag).
                       Defaults to False (log-only mode).

        Returns
        -------
        SecurityCheckResult with threat level and list of detected threats.
        """
        threats: list[str] = []
        max_severity = "none"
        blocked = False
        text_lower = text.lower()

        for pattern, category, severity in _INJECTION_PATTERNS + _ANOMALY_PATTERNS:
            if re.search(pattern, text_lower, re.DOTALL):
                label = f"{category}:{severity}"
                if label not in threats:
                    threats.append(label)
                if _SEVERITY_RANK[severity] > _SEVERITY_RANK[max_severity]:
                    max_severity = severity
                should_block = block_on_high and severity in ("high", "critical")
                if should_block:
                    blocked = True
                self.record_event(
                    category=category,
                    severity=severity,
                    source="user_input",
                    detail=f"Pattern match in session={session_id}: {pattern[:60]}",
                    blocked=should_block,
                    session_id=session_id,
                )

        return SecurityCheckResult(
            safe=len(threats) == 0,
            threat_level=max_severity,
            threats=threats,
            blocked=blocked,
        )

    def record_event(
        self,
        category: str,
        severity: str,
        source: str,
        detail: str,
        blocked: bool,
        session_id: str = "unknown",
    ) -> SecurityEvent:
        """Manually record a security event."""
        evt = SecurityEvent(
            event_id=_uid(),
            category=category,
            severity=severity,
            source=source,
            detail=detail[:500],
            blocked=blocked,
            session_id=session_id,
            timestamp=time.time(),
        )
        self._events.append(evt)
        if blocked:
            self._block_counts[category] = self._block_counts.get(category, 0) + 1
        self._trim()
        self._save()
        return evt

    def get_recent_events(self, n: int = 20) -> list[SecurityEvent]:
        """Return the *n* most recent security events."""
        return list(self._events[-n:])

    def get_events_by_severity(self, severity: str) -> list[SecurityEvent]:
        """Return all events matching the given *severity*."""
        return [e for e in self._events if e.severity == severity]

    def threat_summary(self) -> dict[str, Any]:
        """Return an aggregate security summary."""
        if not self._events:
            return {"total_events": 0, "blocked": 0, "by_category": {}, "by_severity": {}}
        categories: dict[str, int] = {}
        severities: dict[str, int] = {}
        blocked_count = 0
        for e in self._events:
            categories[e.category] = categories.get(e.category, 0) + 1
            severities[e.severity] = severities.get(e.severity, 0) + 1
            if e.blocked:
                blocked_count += 1
        return {
            "total_events": len(self._events),
            "blocked": blocked_count,
            "by_category": categories,
            "by_severity": severities,
        }

    def report(self) -> str:
        """Return a human-readable security report."""
        s = self.threat_summary()
        lines = [
            "--- Security Database ---",
            f"Total events     : {s['total_events']}",
            f"Blocked events   : {s['blocked']}",
            f"By severity      : {s['by_severity']}",
            f"By category      : {s['by_category']}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        if len(self._events) > self.event_limit:
            self._events = self._events[-self.event_limit:]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data: dict[str, Any] = {
            "events": [e.to_dict() for e in self._events[-300:]],
            "block_counts": self._block_counts,
        }
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            self._block_counts = data.get("block_counts", {})
            self._events = [SecurityEvent.from_dict(e) for e in data.get("events", [])]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass


# ============================================================
# Documentation Database
# ============================================================

@dataclass
class DocumentationEntry:
    """
    A single knowledge or documentation item.

    category : "knowledge" | "fact" | "annotation" | "generated_doc" | "tip"
    source   : "auto_extracted" | "user_provided" | "generated"
    """

    entry_id: str
    category: str
    topic: str
    content: str
    source: str
    tags: list[str]
    quality_score: float
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DocumentationEntry":
        return cls(**d)


class DocumentationDatabase:
    """
    Knowledge base and documentation store.

    Automatically extracts and persists knowledge from high-quality
    AI responses, building a growing body of documented expertise.
    """

    _AUTO_EXTRACT_THRESHOLD = 0.70  # minimum quality to auto-extract

    def __init__(self, persist_path: str, entry_limit: int = 1000) -> None:
        self.persist_path = persist_path
        self.entry_limit = entry_limit
        self._entries: list[DocumentationEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        category: str,
        topic: str,
        content: str,
        source: str = "user_provided",
        tags: list[str] | None = None,
        quality_score: float = 1.0,
    ) -> DocumentationEntry:
        """Manually add a documentation entry."""
        entry = DocumentationEntry(
            entry_id=_uid(),
            category=category,
            topic=topic,
            content=content[:2000],
            source=source,
            tags=list(tags or []),
            quality_score=quality_score,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        self._trim()
        self._save()
        return entry

    def auto_extract(
        self,
        user_input: str,
        response: str,
        tags: list[str],
        quality_score: float,
    ) -> DocumentationEntry | None:
        """
        Auto-extract a knowledge entry from a high-quality interaction.
        Returns None if the quality threshold is not met or the content
        is too short to be meaningful.
        """
        if quality_score < self._AUTO_EXTRACT_THRESHOLD:
            return None
        topic = tags[0] if tags and tags[0] != "general" else "general"
        # Use first few sentences as the knowledge snippet
        sentences = response.split(". ")
        content = ". ".join(sentences[:3]).strip()[:500]
        if len(content) < 30:
            return None
        return self.record(
            category="knowledge",
            topic=topic,
            content=content,
            source="auto_extracted",
            tags=list(tags),
            quality_score=quality_score,
        )

    def query(self, topic: str, limit: int = 10) -> list[DocumentationEntry]:
        """Return entries relevant to *topic*, sorted by quality."""
        topic_lower = topic.lower()
        matches = [
            e for e in self._entries
            if topic_lower in e.topic.lower()
            or topic_lower in " ".join(e.tags).lower()
        ]
        return sorted(matches, key=lambda e: e.quality_score, reverse=True)[:limit]

    def query_by_category(self, category: str) -> list[DocumentationEntry]:
        """Return all entries in a specific category."""
        return [e for e in self._entries if e.category == category]

    def report(self) -> str:
        """Return a human-readable documentation report."""
        categories: dict[str, int] = {}
        for e in self._entries:
            categories[e.category] = categories.get(e.category, 0) + 1
        lines = [
            "--- Documentation Database ---",
            f"Total entries    : {len(self._entries)}",
            f"By category      : {categories}",
        ]
        if self._entries:
            top_topics: dict[str, int] = {}
            for e in self._entries:
                top_topics[e.topic] = top_topics.get(e.topic, 0) + 1
            top = sorted(top_topics.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"Top topics       : {dict(top)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        if len(self._entries) > self.entry_limit:
            self._entries = self._entries[-self.entry_limit:]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data = [e.to_dict() for e in self._entries[-500:]]
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: list[dict[str, Any]] = json.load(fh)
            self._entries = [DocumentationEntry.from_dict(e) for e in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass


# ============================================================
# Improvement Database
# ============================================================

@dataclass
class ImprovementPattern:
    """
    A recurring pattern associated with high-quality engine responses.

    pattern_type : "successful_response" | "quality_tip" | "topic_insight"
    avg_quality  : Running average quality score across all evidence.
    evidence_count: Number of interactions that contributed to this pattern.
    """

    pattern_id: str
    topic: str
    pattern_type: str
    description: str
    avg_quality: float
    evidence_count: int
    last_updated: float
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ImprovementPattern":
        return cls(**d)


class ImprovementDatabase:
    """
    Stores effective patterns discovered through self-improvement analysis.

    Ingests interactions, identifies successful patterns by topic, and
    surfaces them as improvement hints for the engine.
    """

    _HIGH_QUALITY_THRESHOLD = 0.75

    def __init__(self, persist_path: str, pattern_limit: int = 500) -> None:
        self.persist_path = persist_path
        self.pattern_limit = pattern_limit
        self._patterns: list[ImprovementPattern] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_interaction(
        self,
        user_input: str,
        response: str,
        quality_score: float,
        tags: list[str],
    ) -> ImprovementPattern | None:
        """
        Extract and store an improvement pattern from a high-quality interaction.
        Updates an existing pattern for the same topic when one is found.
        Returns the pattern, or None if quality is below threshold.
        """
        if quality_score < self._HIGH_QUALITY_THRESHOLD:
            return None

        topic = tags[0] if tags and tags[0] != "general" else "general"

        # Update an existing pattern for this topic
        existing = next(
            (p for p in self._patterns
             if p.topic == topic and p.pattern_type == "successful_response"),
            None,
        )
        if existing:
            n = existing.evidence_count
            existing.avg_quality = (existing.avg_quality * n + quality_score) / (n + 1)
            existing.evidence_count += 1
            existing.last_updated = time.time()
            self._save()
            return existing

        # Create a new pattern
        desc = (
            f"Responses to '{topic}' queries consistently score high "
            f"(initial q={quality_score:.2f}, response length ~{len(response)} chars)."
        )
        pattern = ImprovementPattern(
            pattern_id=_uid(),
            topic=topic,
            pattern_type="successful_response",
            description=desc,
            avg_quality=quality_score,
            evidence_count=1,
            last_updated=time.time(),
            tags=list(tags),
        )
        self._patterns.append(pattern)
        self._trim()
        self._save()
        return pattern

    def add_tip(
        self,
        topic: str,
        description: str,
        tags: list[str] | None = None,
    ) -> ImprovementPattern:
        """Manually register a quality improvement tip."""
        pattern = ImprovementPattern(
            pattern_id=_uid(),
            topic=topic,
            pattern_type="quality_tip",
            description=description,
            avg_quality=1.0,
            evidence_count=1,
            last_updated=time.time(),
            tags=list(tags or [topic]),
        )
        self._patterns.append(pattern)
        self._save()
        return pattern

    def query_patterns(self, topic: str, limit: int = 5) -> list[ImprovementPattern]:
        """Return patterns relevant to *topic*, sorted by quality."""
        topic_lower = topic.lower()
        matches = [
            p for p in self._patterns
            if topic_lower in p.topic.lower()
            or topic_lower in " ".join(p.tags).lower()
        ]
        return sorted(matches, key=lambda p: p.avg_quality, reverse=True)[:limit]

    def top_patterns(self, n: int = 10) -> list[ImprovementPattern]:
        """Return the highest-quality patterns regardless of topic."""
        return sorted(self._patterns, key=lambda p: p.avg_quality, reverse=True)[:n]

    def report(self) -> str:
        """Return a human-readable improvement patterns report."""
        lines = [
            "--- Improvement Database ---",
            f"Total patterns   : {len(self._patterns)}",
        ]
        top = self.top_patterns(5)
        if top:
            lines.append("Top patterns (by quality):")
            for p in top:
                lines.append(
                    f"  [{p.topic:<15}] {p.pattern_type:<22} "
                    f"q={p.avg_quality:.2f}  n={p.evidence_count}"
                )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        if len(self._patterns) > self.pattern_limit:
            self._patterns = self._patterns[-self.pattern_limit:]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data = [p.to_dict() for p in self._patterns]
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: list[dict[str, Any]] = json.load(fh)
            self._patterns = [ImprovementPattern.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass


# ============================================================
# Healing Database
# ============================================================

@dataclass
class HealingStrategy:
    """
    A recovery strategy mapped to a normalized error signature.

    backend_hint   : Suggested backend to switch to ("" if generic).
    success_count  : Number of times this strategy resolved the error.
    failure_count  : Number of times it was tried but failed.
    """

    strategy_id: str
    error_signature: str
    strategy: str
    backend_hint: str
    success_count: int
    failure_count: int
    last_used: float
    created_at: float

    @property
    def success_rate(self) -> float:
        """Fraction of uses that resulted in a successful recovery."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # success_rate is a computed property; do not persist it
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HealingStrategy":
        d.pop("success_rate", None)
        return cls(**d)


# Built-in default strategies seeded on first instantiation
_DEFAULT_HEALING_STRATEGIES: list[tuple[str, str, str]] = [
    ("connection_refused",
     "Switch to a local backend (ollama or hermes) or fall back to mock.",
     "ollama"),
    ("authentication_failed",
     "Check the API-key environment variable for the active backend. Fall back to mock.",
     "mock"),
    ("rate_limit_exceeded",
     "Back off and retry after a short delay. Switch to an alternate backend.",
     "openrouter"),
    ("timeout",
     "Reduce max_tokens or temperature. Switch to a faster backend.",
     "mock"),
    ("invalid_model",
     "Verify model name in engine_config.json. Revert to the default model.",
     ""),
    ("context_length_exceeded",
     "Reduce memory_window or shorten the system prompt.",
     ""),
    ("backend_unavailable",
     "Advance to the next backend in the self-healing fallback chain.",
     ""),
    ("json_decode_error",
     "Response format is unexpected. Retry with lower temperature.",
     ""),
    ("memory_exhausted",
     "Lower history_limit and sample_limit in the database config section.",
     ""),
    ("sandbox_timeout",
     "Reduce sandbox timeout or simplify the code being executed.",
     ""),
    ("ssl_error",
     "Verify TLS certificates. Retry after a short delay or switch backend.",
     ""),
    ("permission_denied",
     "Check file/directory permissions for the session_dir path.",
     ""),
]


class HealingDatabase:
    """
    Stores error→strategy mappings that power self-healing recovery.

    Strategies are seeded with built-in defaults and updated through
    ``record_outcome`` as the engine learns which strategies work best.
    """

    def __init__(self, persist_path: str) -> None:
        self.persist_path = persist_path
        self._strategies: dict[str, HealingStrategy] = {}
        self._load()
        self._seed_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, error_message: str) -> HealingStrategy | None:
        """
        Return the best-known strategy for *error_message*.

        Matches by checking whether any known error-signature keyword
        appears in the (lower-cased) error message.  When multiple
        strategies match, prefer those with the highest success count.
        """
        error_lower = error_message.lower()
        candidates: list[HealingStrategy] = []
        for sig, strategy in self._strategies.items():
            # Match whole signature or any of its underscore-separated words
            words = sig.replace("_", " ").split()
            if sig in error_lower or any(w in error_lower for w in words):
                candidates.append(strategy)
        if not candidates:
            return None
        return max(candidates, key=lambda s: (s.success_count, s.success_rate))

    def record_outcome(self, strategy_id: str, success: bool) -> None:
        """
        Update outcome statistics after applying a healing strategy.

        Parameters
        ----------
        strategy_id : The ``strategy_id`` of the strategy that was applied.
        success     : True if the strategy resolved the error; False otherwise.
        """
        for strategy in self._strategies.values():
            if strategy.strategy_id == strategy_id:
                if success:
                    strategy.success_count += 1
                else:
                    strategy.failure_count += 1
                strategy.last_used = time.time()
                self._save()
                return

    def add_strategy(
        self,
        error_signature: str,
        strategy: str,
        backend_hint: str = "",
    ) -> HealingStrategy:
        """Register a custom healing strategy for the given *error_signature*."""
        s = HealingStrategy(
            strategy_id=_uid(),
            error_signature=error_signature,
            strategy=strategy,
            backend_hint=backend_hint,
            success_count=0,
            failure_count=0,
            last_used=0.0,
            created_at=time.time(),
        )
        self._strategies[error_signature] = s
        self._save()
        return s

    def list_strategies(self) -> list[HealingStrategy]:
        """Return all registered healing strategies."""
        return list(self._strategies.values())

    def report(self) -> str:
        """Return a human-readable healing strategies report."""
        lines = [
            "--- Healing Database ---",
            f"Total strategies : {len(self._strategies)}",
        ]
        for sig, s in list(self._strategies.items())[:10]:
            lines.append(
                f"  [{sig:<28}] "
                f"ok={s.success_count} fail={s.failure_count} "
                f"hint={s.backend_hint or 'N/A'}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        """Add built-in strategies for any signature not yet in the database."""
        changed = False
        for error_sig, strategy_text, backend_hint in _DEFAULT_HEALING_STRATEGIES:
            if error_sig not in self._strategies:
                self._strategies[error_sig] = HealingStrategy(
                    strategy_id=_uid(),
                    error_signature=error_sig,
                    strategy=strategy_text,
                    backend_hint=backend_hint,
                    success_count=0,
                    failure_count=0,
                    last_used=0.0,
                    created_at=time.time(),
                )
                changed = True
        if changed:
            self._save()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data = {sig: s.to_dict() for sig, s in self._strategies.items()}
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            self._strategies = {
                sig: HealingStrategy.from_dict(d) for sig, d in data.items()
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            pass


# ============================================================
# Unified AI Database System
# ============================================================

class AIDatabaseSystem:
    """
    Unified AI Database System — orchestrates all five category-specific databases.

    Sub-databases
    -------------
    transparency  — Full audit trail of every AI decision and response.
    security      — Threat detection, security events, blocked operations.
    documentation — Knowledge base, auto-extracted facts, generated docs.
    improvement   — Effective patterns powering self-improvement learning.
    healing       — Error→strategy mappings powering self-healing recovery.

    Parameters
    ----------
    db_dir       : Directory where all database files are stored.
    record_limit : Max records per database (transparency, security, documentation).

    Integration with self-improvement
    ----------------------------------
    After each interaction, call ``record_interaction()``.  The improvement
    database will accumulate topic-specific quality patterns that can be
    surfaced via ``query_improvement_patterns(topic)`` to guide responses.

    Integration with self-healing
    ------------------------------
    When an error occurs, call ``query_healing_strategy(error_message)``
    to retrieve a known recovery action.  After applying it, call
    ``record_healing_outcome(strategy_id, success=True/False)`` so the
    database learns which strategies work.
    """

    def __init__(
        self,
        db_dir: str = ".sessions/db",
        record_limit: int = 2000,
    ) -> None:
        self.db_dir = db_dir
        os.makedirs(db_dir, exist_ok=True)

        self.transparency = TransparencyDatabase(
            persist_path=os.path.join(db_dir, "transparency.json"),
            record_limit=record_limit,
        )
        self.security = SecurityDatabase(
            persist_path=os.path.join(db_dir, "security.json"),
            event_limit=record_limit,
        )
        self.documentation = DocumentationDatabase(
            persist_path=os.path.join(db_dir, "documentation.json"),
            entry_limit=record_limit,
        )
        self.improvement = ImprovementDatabase(
            persist_path=os.path.join(db_dir, "improvement.json"),
            pattern_limit=max(record_limit // 4, 100),
        )
        self.healing = HealingDatabase(
            persist_path=os.path.join(db_dir, "healing.json"),
        )

    # ------------------------------------------------------------------
    # High-level orchestration API
    # ------------------------------------------------------------------

    def check_security(
        self,
        user_input: str,
        session_id: str = "unknown",
        block_on_high: bool = False,
    ) -> SecurityCheckResult:
        """
        Screen *user_input* for threats (passive by default — log only).

        Parameters
        ----------
        user_input   : The raw user message to screen.
        session_id   : Session identifier for event attribution.
        block_on_high: If True, the ``blocked`` flag is set for high/critical
                       threats so the caller can act on it.

        Returns
        -------
        SecurityCheckResult with threat_level, threats list, and blocked flag.
        """
        return self.security.check_input(
            user_input, session_id=session_id, block_on_high=block_on_high
        )

    def record_interaction(
        self,
        session_id: str,
        user_input: str,
        response: str,
        system_prompt: str,
        backend: str,
        model: str,
        temperature: float,
        quality_score: float,
        tags: list[str],
    ) -> None:
        """
        Record a completed chat interaction across all relevant databases.

        Populates:
        - Transparency database (full audit trail)
        - Documentation database (auto-extracts knowledge from quality responses)
        - Improvement database (stores successful response patterns)
        """
        self.transparency.record(
            session_id=session_id,
            user_input=user_input,
            system_prompt=system_prompt,
            backend=backend,
            model=model,
            temperature=temperature,
            response=response,
            quality_score=quality_score,
            tags=tags,
        )
        self.documentation.auto_extract(
            user_input=user_input,
            response=response,
            tags=tags,
            quality_score=quality_score,
        )
        self.improvement.ingest_interaction(
            user_input=user_input,
            response=response,
            quality_score=quality_score,
            tags=tags,
        )

    def query_healing_strategy(self, error_message: str) -> HealingStrategy | None:
        """
        Look up the best healing strategy for *error_message*.
        Returns None if no matching strategy is found.
        """
        return self.healing.query(error_message)

    def record_healing_outcome(self, strategy_id: str, success: bool) -> None:
        """
        Update outcome statistics for a healing strategy that was applied.

        Parameters
        ----------
        strategy_id : The id of the strategy that was applied.
        success     : True if the strategy resolved the error.
        """
        self.healing.record_outcome(strategy_id, success)

    def query_improvement_patterns(
        self,
        topic: str,
        limit: int = 5,
    ) -> list[ImprovementPattern]:
        """Return up to *limit* improvement patterns relevant to *topic*."""
        return self.improvement.query_patterns(topic, limit=limit)

    def record_knowledge(
        self,
        topic: str,
        content: str,
        category: str = "knowledge",
        tags: list[str] | None = None,
    ) -> DocumentationEntry:
        """
        Manually add a knowledge entry to the documentation database.

        Parameters
        ----------
        topic    : Topic or domain of the knowledge (e.g. "blockchain").
        content  : The knowledge text.
        category : One of "knowledge", "fact", "annotation", "generated_doc", "tip".
        tags     : Optional list of topic tags.
        """
        return self.documentation.record(
            category=category,
            topic=topic,
            content=content,
            source="user_provided",
            tags=list(tags or [topic]),
        )

    def report(self) -> str:
        """Return a comprehensive report spanning all five databases."""
        lines = [
            "=== AI Database System Report ===",
            self.transparency.report(),
            "",
            self.security.report(),
            "",
            self.documentation.report(),
            "",
            self.improvement.report(),
            "",
            self.healing.report(),
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"AIDatabaseSystem(db_dir={self.db_dir!r}, "
            f"transparency={len(self.transparency._records)}, "
            f"security={len(self.security._events)}, "
            f"documentation={len(self.documentation._entries)}, "
            f"improvement={len(self.improvement._patterns)}, "
            f"healing={len(self.healing._strategies)})"
        )
