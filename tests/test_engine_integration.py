"""
tests/test_engine_integration.py
Integration tests verifying CloneEngine with all industrial-grade sub-systems.
"""

from __future__ import annotations

import os
import pytest
from engine.core import CloneEngine
from engine import (
    AIToolkit,
    AISandbox,
    SelfHealingSystem,
    SelfImprovementSystem,
    PerformanceMonitor,
    __version__,
)
from engine.sandbox import SandboxResult


@pytest.fixture
def engine(tmp_path):
    """Return a CloneEngine with session data isolated to tmp_path."""
    import json
    cfg = {
        "backend": "mock",
        "model": "gpt-4o",
        "temperature": 0.85,
        "max_tokens": 512,
        "memory_window": 20,
        "session_persist": True,
        "session_dir": str(tmp_path),
        "sandbox": {"timeout": 3.0, "max_output": 4096, "safe_mode": True},
        "self_improvement": {"persist_file": "improve.json", "history_limit": 100},
        "self_healing": {
            "fallback_backends": ["mock"],
            "failure_threshold": 3,
            "recovery_timeout": 60.0,
        },
        "performance": {"persist_file": "perf.json", "sample_limit": 100},
    }
    cfg_path = str(tmp_path / "config.json")
    with open(cfg_path, "w") as fh:
        json.dump(cfg, fh)
    return CloneEngine(config_path=cfg_path, session_id="test")


# ---------------------------------------------------------------------------
# Basic engine
# ---------------------------------------------------------------------------

def test_version():
    assert __version__ == "3.0.0"


def test_engine_repr(engine):
    r = repr(engine)
    assert "3.0.0" in r
    assert "mock" in r
    assert "test" in r


def test_chat_returns_string(engine):
    response = engine.chat("What is systems thinking?")
    assert isinstance(response, str)
    assert len(response) > 0


def test_chat_empty_input(engine):
    response = engine.chat("   ")
    assert response == ""


def test_chat_multiple_turns(engine):
    r1 = engine.chat("Hello!")
    r2 = engine.chat("Tell me about Rust.")
    assert r1
    assert r2


def test_reset_clears_memory(engine):
    engine.chat("Remember this.")
    engine.reset()
    assert len(engine.memory) == 0


def test_profile_summary(engine):
    summary = engine.profile_summary()
    assert "Charles Earl Lipshay" in summary
    assert "Backend" in summary
    assert "3.0.0" in summary


# ---------------------------------------------------------------------------
# Sub-systems present
# ---------------------------------------------------------------------------

def test_has_toolkit(engine):
    assert isinstance(engine.toolkit, AIToolkit)


def test_has_sandbox(engine):
    assert isinstance(engine.sandbox, AISandbox)


def test_has_self_improvement(engine):
    assert isinstance(engine.self_improvement, SelfImprovementSystem)


def test_has_self_healing(engine):
    assert isinstance(engine.self_healing, SelfHealingSystem)


def test_has_performance(engine):
    assert isinstance(engine.performance, PerformanceMonitor)


# ---------------------------------------------------------------------------
# Self-improvement integration
# ---------------------------------------------------------------------------

def test_chat_records_in_self_improvement(engine):
    engine.chat("What do you think about open-source?")
    assert len(engine.self_improvement._records) == 1


def test_improvement_report(engine):
    engine.chat("Explain blockchain.")
    report = engine.improvement_report()
    assert "Self-Improvement" in report


# ---------------------------------------------------------------------------
# Performance integration
# ---------------------------------------------------------------------------

def test_chat_records_performance_sample(engine):
    engine.chat("Hello!")
    names = [s.name for s in engine.performance._samples]
    assert any("chat" in n for n in names)


def test_performance_report(engine):
    engine.chat("Hello!")
    report = engine.performance_report()
    assert "Performance" in report


# ---------------------------------------------------------------------------
# Self-healing integration
# ---------------------------------------------------------------------------

def test_health_report(engine):
    engine.chat("Hello!")
    report = engine.health_report()
    assert "Self-Healing" in report


def test_health_report_shows_healthy_mock(engine):
    engine.chat("Hello!")
    report = engine.health_report()
    assert "healthy" in report.lower()


# ---------------------------------------------------------------------------
# Toolkit integration
# ---------------------------------------------------------------------------

def test_toolkit_call(engine):
    result = engine.toolkit.call(
        "analyze_python", code="def add(a, b): return a + b"
    )
    assert result.success is True
    assert "add" in result.output["functions"]


def test_toolkit_report(engine):
    engine.toolkit.call("analyze_python", code="x = 1")
    report = engine.toolkit_report()
    assert "analyze_python" in report


# ---------------------------------------------------------------------------
# Sandbox integration
# ---------------------------------------------------------------------------

def test_sandbox_execute(engine):
    result = engine.sandbox.execute("print('sandbox test')")
    assert result.success is True
    assert "sandbox test" in result.stdout


# ---------------------------------------------------------------------------
# Persistence across engine restarts
# ---------------------------------------------------------------------------

def test_performance_persists(tmp_path):
    import json
    cfg = {
        "backend": "mock", "model": "gpt-4o", "temperature": 0.85,
        "max_tokens": 512, "memory_window": 5, "session_persist": True,
        "session_dir": str(tmp_path),
        "sandbox": {}, "self_improvement": {}, "self_healing": {}, "performance": {},
    }
    cfg_path = str(tmp_path / "cfg.json")
    with open(cfg_path, "w") as fh:
        json.dump(cfg, fh)

    e1 = CloneEngine(config_path=cfg_path, session_id="persist_test")
    e1.chat("Hello")
    count_before = e1.performance.request_count
    del e1

    e2 = CloneEngine(config_path=cfg_path, session_id="persist_test")
    assert e2.performance.request_count >= count_before
