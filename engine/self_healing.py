"""
engine/self_healing.py
Self-Healing System — monitors engine health, implements circuit breakers,
orchestrates automatic backend failover, and provides a health dashboard.

Key capabilities
----------------
* CircuitBreaker  — per-component failure counting with CLOSED/OPEN/HALF_OPEN states.
* SelfHealingSystem — coordinates failover across multiple LLM backends, records
  health events, and exposes a health-check snapshot.

Usage
-----
    from engine.self_healing import SelfHealingSystem

    healer = SelfHealingSystem(fallback_backends=["anthropic", "ollama", "mock"])

    # Wrap normal generation:
    response, used_backend = healer.generate_with_failover(
        primary_backend="openai",
        backends={"openai": openai_fn, "mock": mock_fn},
        messages=messages,
        model="gpt-4o",
        temperature=0.85,
        max_tokens=512,
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Health status
# ---------------------------------------------------------------------------

class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    CRITICAL  = "critical"
    RECOVERING = "recovering"


# ---------------------------------------------------------------------------
# Health event
# ---------------------------------------------------------------------------

@dataclass
class HealthEvent:
    component: str
    status: HealthStatus
    message: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Three-state circuit breaker for a named component.

    States
    ------
    CLOSED    — Normal operation; failures are counted.
    OPEN      — Operations are blocked; fast-fail returns immediately.
                After *recovery_timeout* seconds the breaker moves to HALF_OPEN.
    HALF_OPEN — One probe request is allowed through to test recovery.
                Success → CLOSED; failure → OPEN again.

    Parameters
    ----------
    name:              Identifier for this breaker (used in logs).
    failure_threshold: Number of consecutive failures before opening.
    recovery_timeout:  Seconds to wait before probing in HALF_OPEN state.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = "CLOSED"
        self._opened_at: float = 0.0

    @property
    def state(self) -> str:
        """Return the current circuit breaker state string."""
        if self._state == "OPEN":
            if time.time() - self._opened_at >= self.recovery_timeout:
                self._state = "HALF_OPEN"
        return self._state

    @property
    def is_open(self) -> bool:
        """True if this component is currently unavailable."""
        return self.state == "OPEN"

    def record_success(self) -> None:
        """Signal a successful operation; resets failure count and closes the breaker."""
        self._failures = 0
        self._state = "CLOSED"

    def record_failure(self) -> None:
        """Signal a failed operation; may open the breaker."""
        self._failures += 1
        if self._failures >= self.failure_threshold:
            if self._state != "OPEN":
                self._opened_at = time.time()
            self._state = "OPEN"

    @property
    def failure_count(self) -> int:
        return self._failures

    def __repr__(self) -> str:
        return f"CircuitBreaker(name={self.name!r}, state={self.state!r}, failures={self._failures})"


# ---------------------------------------------------------------------------
# Self-healing system
# ---------------------------------------------------------------------------

class SelfHealingSystem:
    """
    Coordinates health monitoring and automatic recovery across engine components.

    Parameters
    ----------
    fallback_backends:      Ordered list of backend names to try when the primary
                            backend fails.  The engine always appends "mock" as the
                            last-resort fallback if it is not already present.
    failure_threshold:      Default failure threshold for new circuit breakers.
    recovery_timeout:       Default recovery timeout (seconds) for new circuit breakers.
    health_log_limit:       Maximum number of health events to retain in memory.
    """

    def __init__(
        self,
        fallback_backends: list[str] | None = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        health_log_limit: int = 200,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.health_log_limit = health_log_limit

        raw_fallbacks = list(fallback_backends or [])
        if "mock" not in raw_fallbacks:
            raw_fallbacks.append("mock")
        self.fallback_backends: list[str] = raw_fallbacks

        self._breakers: dict[str, CircuitBreaker] = {}
        self._health_log: list[HealthEvent] = []
        self._component_status: dict[str, HealthStatus] = {}

    # ------------------------------------------------------------------
    # Circuit breaker access
    # ------------------------------------------------------------------

    def get_breaker(self, name: str) -> CircuitBreaker:
        """Return (or create) the circuit breaker for *name*."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
            )
        return self._breakers[name]

    def is_available(self, component: str) -> bool:
        """Return True if the component's circuit breaker is not open."""
        return not self.get_breaker(component).is_open

    def record_success(self, component: str) -> None:
        """Signal a successful call to *component*."""
        self.get_breaker(component).record_success()
        self._emit(component, HealthStatus.HEALTHY, "Operation succeeded.")

    def record_failure(self, component: str, error: str = "") -> None:
        """Signal a failed call to *component*."""
        breaker = self.get_breaker(component)
        breaker.record_failure()
        if breaker.is_open:
            status = HealthStatus.CRITICAL
            msg = (
                f"Circuit breaker OPEN for '{component}' after "
                f"{breaker.failure_count} failures: {error}"
            )
        else:
            status = HealthStatus.DEGRADED
            msg = (
                f"Failure #{breaker.failure_count}/{breaker.failure_threshold} "
                f"for '{component}': {error}"
            )
        self._emit(component, status, msg)

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def generate_with_failover(
        self,
        primary_backend: str,
        backends: dict[str, Callable[..., str]],
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> tuple[str, str]:
        """
        Call the primary backend; on failure, iterate through fallbacks.

        Parameters
        ----------
        primary_backend: Name of the preferred backend.
        backends:        Mapping of backend name → callable that accepts
                         ``(messages, **kwargs)`` and returns a string.
        messages:        LLM message list to pass through.
        **kwargs:        Extra arguments forwarded to the backend callable
                         (e.g. model, temperature, max_tokens).

        Returns
        -------
        (response_text, backend_name_used)
        """
        attempt_order = [primary_backend] + [
            b for b in self.fallback_backends if b != primary_backend
        ]

        last_error = ""
        for backend_name in attempt_order:
            if backend_name not in backends:
                continue
            if not self.is_available(backend_name):
                self._emit(
                    backend_name, HealthStatus.DEGRADED,
                    f"Skipped — circuit breaker is OPEN.",
                )
                continue
            try:
                result = backends[backend_name](messages, **kwargs)
                self.record_success(backend_name)
                if backend_name != primary_backend:
                    self._emit(
                        "engine", HealthStatus.RECOVERING,
                        f"Failover succeeded: using '{backend_name}' instead of '{primary_backend}'.",
                    )
                return result, backend_name
            except Exception as exc:
                last_error = str(exc)
                self.record_failure(backend_name, last_error)

        # All backends exhausted
        self._emit(
            "engine", HealthStatus.CRITICAL,
            f"All backends exhausted. Last error: {last_error}",
        )
        return (
            "I'm experiencing technical difficulties right now. "
            "Please try again in a moment.",
            "none",
        )

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Return a complete health snapshot suitable for display or logging."""
        return {
            "overall": self._overall_status().value,
            "timestamp": time.time(),
            "components": {
                name: {
                    "status": status.value,
                    "circuit_breaker": self._breakers[name].state if name in self._breakers else "CLOSED",
                    "failure_count": (
                        self._breakers[name].failure_count if name in self._breakers else 0
                    ),
                }
                for name, status in self._component_status.items()
            },
            "recent_events": [e.to_dict() for e in self._health_log[-15:]],
        }

    def report(self) -> str:
        """Return a human-readable health report."""
        hc = self.health_check()
        lines = [
            "=== Self-Healing Health Report ===",
            f"Overall status : {hc['overall']}",
            f"Timestamp      : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(hc['timestamp']))}",
        ]
        if hc["components"]:
            lines.append("Components:")
            for name, info in hc["components"].items():
                lines.append(
                    f"  {name:<20} status={info['status']:<10} "
                    f"circuit={info['circuit_breaker']:<10} "
                    f"failures={info['failure_count']}"
                )
        if hc["recent_events"]:
            lines.append("\nRecent events (latest 5):")
            for evt in hc["recent_events"][-5:]:
                ts = time.strftime("%H:%M:%S", time.localtime(evt["timestamp"]))
                lines.append(f"  [{ts}] {evt['component']}: {evt['message'][:90]}")
        return "\n".join(lines)

    def reset_breaker(self, component: str) -> None:
        """Manually close (reset) the circuit breaker for *component*."""
        self.get_breaker(component).record_success()
        self._emit(component, HealthStatus.HEALTHY, "Circuit breaker manually reset.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, component: str, status: HealthStatus, message: str) -> None:
        self._component_status[component] = status
        event = HealthEvent(component=component, status=status, message=message)
        self._health_log.append(event)
        if len(self._health_log) > self.health_log_limit:
            self._health_log = self._health_log[-self.health_log_limit:]

    def _overall_status(self) -> HealthStatus:
        if not self._component_status:
            return HealthStatus.HEALTHY
        statuses = list(self._component_status.values())
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        if HealthStatus.RECOVERING in statuses:
            return HealthStatus.RECOVERING
        return HealthStatus.HEALTHY
