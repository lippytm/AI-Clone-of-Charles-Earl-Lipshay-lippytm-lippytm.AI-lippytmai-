"""
tests/test_self_improvement.py
Unit tests for engine.self_improvement (SelfImprovementSystem).
"""

from __future__ import annotations

import os
import json
import tempfile

import pytest
from engine.self_improvement import SelfImprovementSystem, InteractionRecord


@pytest.fixture
def sis(tmp_path):
    path = str(tmp_path / "improve.json")
    return SelfImprovementSystem(persist_path=path, history_limit=100)


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def test_record_creates_entry(sis):
    sis.record("s1", "What is Rust?", "Rust is a systems programming language.")
    assert len(sis._records) == 1


def test_record_auto_scores(sis):
    sis.record("s1", "Explain AI", "Artificial intelligence is the simulation of...")
    assert 0.0 <= sis._records[0].quality_score <= 1.0


def test_record_explicit_score(sis):
    sis.record("s1", "Hello", "Hi there.", quality_score=0.9)
    assert sis._records[0].quality_score == 0.9


def test_record_tags(sis):
    sis.record("s1", "How does Rust ownership work?", "Ownership is Rust's memory model.")
    # "rust" should trigger 'code' tag at minimum
    tags = sis._records[0].tags
    assert isinstance(tags, list)
    assert len(tags) > 0


def test_record_respects_history_limit():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "imp.json")
        sis = SelfImprovementSystem(persist_path=path, history_limit=5)
        for i in range(10):
            sis.record("s", f"question {i}", "answer " * 10)
        assert len(sis._records) <= 5


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def test_average_quality_empty(sis):
    assert sis.average_quality() == 1.0


def test_average_quality_after_records(sis):
    sis.record("s1", "Q?", "Short.", quality_score=0.6)
    sis.record("s1", "Q?", "Short.", quality_score=0.8)
    avg = sis.average_quality()
    assert abs(avg - 0.7) < 0.01


def test_average_quality_last_n(sis):
    for i in range(10):
        sis.record("s", "Q?", "A" * 50, quality_score=0.5)
    sis.record("s", "Q?", "A" * 50, quality_score=1.0)
    assert sis.average_quality(last_n=1) == 1.0
    assert sis.average_quality(last_n=0) < 1.0  # all records averaged


# ---------------------------------------------------------------------------
# rate_last
# ---------------------------------------------------------------------------

def test_rate_last(sis):
    sis.record("s1", "Q?", "Some answer.")
    sis.rate_last(0.95)
    assert abs(sis._records[-1].quality_score - 0.95) < 0.01


def test_rate_last_clamped(sis):
    sis.record("s1", "Q?", "Some answer.")
    sis.rate_last(1.5)
    assert sis._records[-1].quality_score <= 1.0
    sis.rate_last(-0.5)
    assert sis._records[-1].quality_score >= 0.0


def test_rate_last_no_op_on_empty(sis):
    sis.rate_last(0.8)  # should not raise


# ---------------------------------------------------------------------------
# Topic distribution
# ---------------------------------------------------------------------------

def test_topic_distribution(sis):
    sis.record("s1", "blockchain and smart contracts", "Answer.", quality_score=0.7)
    sis.record("s1", "blockchain defi", "Answer.", quality_score=0.7)
    dist = sis.topic_distribution()
    assert "blockchain" in dist
    assert dist["blockchain"] == 2


def test_topic_distribution_empty(sis):
    assert sis.topic_distribution() == {}


# ---------------------------------------------------------------------------
# Improvement notes
# ---------------------------------------------------------------------------

def test_improvement_notes_returned(sis):
    notes = sis.get_improvement_notes()
    assert isinstance(notes, list)


def test_improvement_notes_low_quality_triggers_note(tmp_path):
    path = str(tmp_path / "improve.json")
    sis = SelfImprovementSystem(persist_path=path, history_limit=100)
    # Feed many low-quality responses to trigger analysis
    for i in range(20):
        sis.record("s", "Q?", "", quality_score=0.1)
    notes = sis.get_improvement_notes()
    assert len(notes) > 0
    assert any("quality" in n.lower() for n in notes)


# ---------------------------------------------------------------------------
# Session stats
# ---------------------------------------------------------------------------

def test_session_summary(sis):
    sis.record("sess1", "Hello", "World.", quality_score=0.8)
    summary = sis.session_summary("sess1")
    assert summary["turn_count"] == 1
    assert abs(summary["avg_quality"] - 0.8) < 0.01


def test_session_summary_missing(sis):
    assert sis.session_summary("nonexistent") == {}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def test_report_format(sis):
    sis.record("s1", "A question", "An answer about AI and code.")
    report = sis.report()
    assert "Self-Improvement Report" in report
    assert "Total interactions" in report


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "improve.json")
    sis1 = SelfImprovementSystem(persist_path=path, history_limit=100)
    sis1.record("sess", "Hello", "World.", quality_score=0.75)
    del sis1

    sis2 = SelfImprovementSystem(persist_path=path, history_limit=100)
    assert len(sis2._records) == 1
    assert abs(sis2._records[0].quality_score - 0.75) < 0.01


def test_reset(sis):
    sis.record("s", "Q", "A.", quality_score=0.5)
    sis.reset()
    assert len(sis._records) == 0
    assert len(sis.get_improvement_notes()) == 0
