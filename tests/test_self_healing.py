"""
tests/test_self_healing.py
Unit tests for engine.self_healing (CircuitBreaker, SelfHealingSystem).
"""

from __future__ import annotations

import pytest
from engine.self_healing import (
    CircuitBreaker,
    HealthStatus,
    SelfHealingSystem,
)


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == "CLOSED"
        assert cb.is_open is False

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "CLOSED"
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.is_open is True

    def test_success_resets_failures(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "OPEN"
        import time
        time.sleep(0.02)
        # Accessing state should trigger transition to HALF_OPEN
        assert cb.state == "HALF_OPEN"
        assert cb.is_open is False

    def test_repr(self):
        cb = CircuitBreaker("svc")
        assert "svc" in repr(cb)


# ---------------------------------------------------------------------------
# SelfHealingSystem — circuit breaker management
# ---------------------------------------------------------------------------

class TestSelfHealingSystemBreakers:
    def test_is_available_new_component(self):
        sh = SelfHealingSystem()
        assert sh.is_available("unknown_component") is True

    def test_record_success_marks_healthy(self):
        sh = SelfHealingSystem()
        sh.record_success("backend_a")
        hc = sh.health_check()
        assert hc["components"]["backend_a"]["status"] == "healthy"

    def test_record_failure_marks_degraded(self):
        sh = SelfHealingSystem(failure_threshold=5)
        sh.record_failure("backend_b", "connection refused")
        hc = sh.health_check()
        assert hc["components"]["backend_b"]["status"] in ("degraded", "critical")

    def test_record_failure_opens_breaker(self):
        sh = SelfHealingSystem(failure_threshold=2)
        sh.record_failure("svc", "err")
        sh.record_failure("svc", "err")
        assert sh.is_available("svc") is False
        hc = sh.health_check()
        assert hc["components"]["svc"]["status"] == "critical"

    def test_reset_breaker(self):
        sh = SelfHealingSystem(failure_threshold=1)
        sh.record_failure("svc", "err")
        assert sh.is_available("svc") is False
        sh.reset_breaker("svc")
        assert sh.is_available("svc") is True


# ---------------------------------------------------------------------------
# SelfHealingSystem — failover
# ---------------------------------------------------------------------------

def _make_always_raise(msg: str):
    def fn(messages, **kwargs):
        raise RuntimeError(msg)
    return fn


def _make_always_return(response: str):
    def fn(messages, **kwargs):
        return response
    return fn


class TestFailover:
    def test_primary_success(self):
        sh = SelfHealingSystem(fallback_backends=["fallback"])
        backends = {
            "primary": _make_always_return("primary response"),
            "fallback": _make_always_return("fallback response"),
        }
        response, used = sh.generate_with_failover("primary", backends, [])
        assert response == "primary response"
        assert used == "primary"

    def test_fallback_on_primary_failure(self):
        sh = SelfHealingSystem(fallback_backends=["fallback"])
        backends = {
            "primary": _make_always_raise("primary down"),
            "fallback": _make_always_return("fallback response"),
        }
        response, used = sh.generate_with_failover("primary", backends, [])
        assert response == "fallback response"
        assert used == "fallback"

    def test_all_fail_returns_error_message(self):
        sh = SelfHealingSystem(fallback_backends=["b"])
        backends = {
            "a": _make_always_raise("error a"),
            "b": _make_always_raise("error b"),
        }
        response, used = sh.generate_with_failover("a", backends, [])
        assert "difficulties" in response.lower() or used == "none"

    def test_skips_open_circuit(self):
        sh = SelfHealingSystem(fallback_backends=["good"], failure_threshold=1)
        # Open the circuit for "bad"
        sh.record_failure("bad", "broken")
        backends = {
            "bad": _make_always_raise("should not be called"),
            "good": _make_always_return("good response"),
        }
        response, used = sh.generate_with_failover("bad", backends, [])
        assert used == "good"
        assert response == "good response"

    def test_mock_always_appended_as_fallback(self):
        sh = SelfHealingSystem(fallback_backends=["anthropic"])
        assert "mock" in sh.fallback_backends

    def test_mock_not_duplicated(self):
        sh = SelfHealingSystem(fallback_backends=["mock"])
        assert sh.fallback_backends.count("mock") == 1


# ---------------------------------------------------------------------------
# Health check and report
# ---------------------------------------------------------------------------

class TestHealthReport:
    def test_health_check_structure(self):
        sh = SelfHealingSystem()
        sh.record_success("engine")
        hc = sh.health_check()
        assert "overall" in hc
        assert "components" in hc
        assert "recent_events" in hc

    def test_overall_healthy_when_all_ok(self):
        sh = SelfHealingSystem()
        sh.record_success("a")
        sh.record_success("b")
        assert sh.health_check()["overall"] == "healthy"

    def test_overall_critical_when_circuit_open(self):
        sh = SelfHealingSystem(failure_threshold=1)
        sh.record_failure("svc", "broken")
        assert sh.health_check()["overall"] == "critical"

    def test_report_contains_status(self):
        sh = SelfHealingSystem()
        sh.record_success("mock")
        report = sh.report()
        assert "Self-Healing" in report
        assert "healthy" in report.lower()

    def test_health_log_capped(self):
        sh = SelfHealingSystem(health_log_limit=10)
        for i in range(20):
            sh.record_success(f"comp_{i}")
        assert len(sh._health_log) <= 10
