"""
tests/test_performance.py
Unit tests for engine.performance (PerformanceMonitor).
"""

from __future__ import annotations

import os
import json
import time
import tempfile

import pytest
from engine.performance import PerformanceMonitor, MetricSample


@pytest.fixture
def monitor(tmp_path):
    path = str(tmp_path / "perf.json")
    return PerformanceMonitor(persist_path=path, sample_limit=500)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def test_record_adds_sample(monitor):
    monitor.record("latency_ms", 42.5, unit="ms")
    assert len(monitor._samples) == 1
    assert monitor._samples[0].name == "latency_ms"
    assert monitor._samples[0].value == 42.5
    assert monitor._samples[0].unit == "ms"


def test_record_tags(monitor):
    monitor.record("latency_ms", 10.0, unit="ms", backend="mock", op="chat")
    sample = monitor._samples[0]
    assert sample.tags["backend"] == "mock"
    assert sample.tags["op"] == "chat"


def test_record_respects_sample_limit(tmp_path):
    path = str(tmp_path / "perf.json")
    monitor = PerformanceMonitor(persist_path=path, sample_limit=5)
    for i in range(10):
        monitor.record("m", float(i))
    assert len(monitor._samples) <= 5


# ---------------------------------------------------------------------------
# measure context manager
# ---------------------------------------------------------------------------

def test_measure_records_latency(monitor):
    with monitor.measure("test_op"):
        pass
    names = [s.name for s in monitor._samples]
    assert "test_op_latency_ms" in names


def test_measure_increments_request_count(monitor):
    with monitor.measure("op"):
        pass
    assert monitor.request_count == 1


def test_measure_records_error(monitor):
    with pytest.raises(ValueError):
        with monitor.measure("failing_op"):
            raise ValueError("test error")
    assert monitor.error_count == 1
    assert monitor.request_count == 1
    names = [s.name for s in monitor._samples]
    assert "failing_op_latency_ms" in names
    # Error tag should be set
    err_samples = [s for s in monitor._samples if s.name == "failing_op_latency_ms"]
    assert err_samples[0].tags.get("status") == "error"


def test_measure_elapsed_positive(monitor):
    with monitor.measure("op"):
        time.sleep(0.01)
    sample = monitor._samples[-1]
    assert sample.value >= 0.0


# ---------------------------------------------------------------------------
# error_rate
# ---------------------------------------------------------------------------

def test_error_rate_zero_requests(monitor):
    assert monitor.error_rate() == 0.0


def test_error_rate_calculation(monitor):
    with monitor.measure("op"):
        pass
    with pytest.raises(RuntimeError):
        with monitor.measure("op"):
            raise RuntimeError("oops")
    assert abs(monitor.error_rate() - 0.5) < 0.01


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_summary_single_metric(monitor):
    for v in [10.0, 20.0, 30.0]:
        monitor.record("latency", v, "ms")
    summ = monitor.summary("latency")
    assert "latency" in summ
    s = summ["latency"]
    assert s["count"] == 3
    assert abs(s["mean"] - 20.0) < 0.01
    assert s["min"] == 10.0
    assert s["max"] == 30.0


def test_summary_all_metrics(monitor):
    monitor.record("a", 1.0)
    monitor.record("b", 2.0)
    summ = monitor.summary()
    assert "a" in summ
    assert "b" in summ


def test_summary_empty(monitor):
    assert monitor.summary("nonexistent") == {}


def test_summary_percentiles(monitor):
    # 100 samples from 1..100
    for i in range(1, 101):
        monitor.record("m", float(i))
    summ = monitor.summary("m")["m"]
    assert summ["p50"] >= 50.0
    assert summ["p95"] >= 90.0
    assert summ["p99"] >= 98.0


# ---------------------------------------------------------------------------
# metric_names and samples_for
# ---------------------------------------------------------------------------

def test_metric_names(monitor):
    monitor.record("x", 1.0)
    monitor.record("y", 2.0)
    names = monitor.metric_names()
    assert "x" in names
    assert "y" in names


def test_samples_for(monitor):
    monitor.record("alpha", 1.0)
    monitor.record("alpha", 2.0)
    monitor.record("beta", 3.0)
    assert len(monitor.samples_for("alpha")) == 2
    assert len(monitor.samples_for("beta")) == 1
    assert monitor.samples_for("gamma") == []


# ---------------------------------------------------------------------------
# record_memory
# ---------------------------------------------------------------------------

def test_record_memory_returns_float(monitor):
    mb = monitor.record_memory()
    assert isinstance(mb, float)
    assert mb >= 0.0


def test_record_memory_adds_sample(monitor):
    monitor.record_memory()
    names = [s.name for s in monitor._samples]
    assert "memory_used_mb" in names


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def test_report_contains_key_info(monitor):
    with monitor.measure("chat"):
        pass
    report = monitor.report()
    assert "Performance Report" in report
    assert "Total requests" in report
    assert "Error rate" in report


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_roundtrip(tmp_path):
    path = str(tmp_path / "perf.json")
    m1 = PerformanceMonitor(persist_path=path, sample_limit=100)
    with m1.measure("chat"):
        pass
    m1.save()
    del m1

    m2 = PerformanceMonitor(persist_path=path, sample_limit=100)
    assert m2.request_count == 1
    names = [s.name for s in m2._samples]
    assert "chat_latency_ms" in names


def test_corrupt_file_handled(tmp_path):
    path = str(tmp_path / "perf.json")
    with open(path, "w") as fh:
        fh.write("not valid json{{{")
    m = PerformanceMonitor(persist_path=path)  # should not raise
    assert m.request_count == 0
