"""
engine/performance.py
Performance Monitor — collects engine metrics (latency, error rates, memory,
throughput) with statistical aggregation and persistent storage.

Usage
-----
    from engine.performance import PerformanceMonitor

    monitor = PerformanceMonitor()

    # Time a block:
    with monitor.measure("chat"):
        response = engine.chat("Hello")

    # Manually record:
    monitor.record("custom_metric", 42.0, unit="ms")

    # Report:
    print(monitor.report())
"""

from __future__ import annotations

import json
import os
import platform
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MetricSample:
    """A single captured metric value."""

    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "unit": self.unit,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class PerformanceMonitor:
    """
    Collects and reports runtime performance metrics for the AI Clone Engine.

    Built-in metrics
    ----------------
    ``<op>_latency_ms``  Wall-clock time for named operations (via ``measure``).
    ``memory_used_mb``   Process RSS memory (via ``record_memory``).
    Custom metrics can be added with ``record``.

    Parameters
    ----------
    persist_path:  JSON file to persist metrics across runs.
    sample_limit:  Maximum number of samples kept in memory.
    """

    def __init__(
        self,
        persist_path: str = ".sessions/performance.json",
        sample_limit: int = 1000,
    ) -> None:
        self.persist_path = persist_path
        self.sample_limit = sample_limit
        self._samples: list[MetricSample] = []
        self._request_count: int = 0
        self._error_count: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, name: str, value: float, unit: str = "ms", **tags: str) -> None:
        """
        Record a single metric sample.

        Parameters
        ----------
        name:   Metric name (e.g. "chat_latency_ms").
        value:  Numeric value.
        unit:   Unit label for display (e.g. "ms", "MB", "tokens/s").
        **tags: Arbitrary key=value tags stored alongside the sample.
        """
        sample = MetricSample(name=name, value=value, unit=unit, tags=dict(tags))
        self._samples.append(sample)
        if len(self._samples) > self.sample_limit:
            self._samples = self._samples[-self.sample_limit:]

    @contextmanager
    def measure(self, operation: str, **tags: str) -> Iterator[None]:
        """
        Context manager that times *operation* and records a latency sample.

        Example
        -------
            with monitor.measure("chat", backend="openai"):
                response = engine.chat(user_input)
        """
        start = time.perf_counter()
        try:
            yield
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.record(f"{operation}_latency_ms", elapsed_ms, unit="ms", **tags)
            self._request_count += 1
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.record(
                f"{operation}_latency_ms", elapsed_ms,
                unit="ms", status="error", **tags,
            )
            self._request_count += 1
            self._error_count += 1
            raise

    def record_memory(self) -> float:
        """
        Capture current process RSS memory in MB, record it, and return the value.
        Returns 0.0 if memory information is unavailable.
        """
        mb = 0.0
        try:
            import resource as rsrc  # Unix only
            raw = rsrc.getrusage(rsrc.RUSAGE_SELF).ru_maxrss
            # Linux: KB; macOS: bytes
            mb = raw / 1024.0 if platform.system() != "Darwin" else raw / (1024.0 * 1024.0)
        except ImportError:
            # Windows fallback via psutil if available
            try:
                import psutil  # type: ignore[import]
                mb = psutil.Process().memory_info().rss / (1024.0 * 1024.0)
            except Exception:
                pass
        except Exception:
            pass
        self.record("memory_used_mb", mb, unit="MB")
        return mb

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def samples_for(self, metric_name: str) -> list[MetricSample]:
        """Return all samples for a specific metric name."""
        return [s for s in self._samples if s.name == metric_name]

    def metric_names(self) -> list[str]:
        """Return the sorted list of distinct metric names recorded so far."""
        return sorted({s.name for s in self._samples})

    def summary(self, metric_name: str | None = None) -> dict[str, Any]:
        """
        Return statistical summaries.

        Parameters
        ----------
        metric_name: If given, summarize only that metric.
                     If None, summarize all recorded metrics.
        """
        samples = self._samples
        if metric_name:
            samples = [s for s in samples if s.name == metric_name]
        if not samples:
            return {}

        by_name: dict[str, list[float]] = {}
        for s in samples:
            by_name.setdefault(s.name, []).append(s.value)

        result: dict[str, Any] = {}
        for name, values in by_name.items():
            vs = sorted(values)
            n = len(vs)
            result[name] = {
                "count": n,
                "mean":  round(sum(vs) / n, 3),
                "min":   round(vs[0], 3),
                "max":   round(vs[-1], 3),
                "p50":   round(vs[n // 2], 3),
                "p95":   round(vs[min(int(n * 0.95), n - 1)], 3),
                "p99":   round(vs[min(int(n * 0.99), n - 1)], 3),
            }
        return result

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def error_count(self) -> int:
        return self._error_count

    def error_rate(self) -> float:
        """Return the cumulative error rate as a fraction (0.0–1.0)."""
        if self._request_count == 0:
            return 0.0
        return self._error_count / self._request_count

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> str:
        """Return a human-readable performance report."""
        lines = [
            "=== Performance Report ===",
            f"Total requests  : {self._request_count}",
            f"Total errors    : {self._error_count}",
            f"Error rate      : {self.error_rate():.1%}",
        ]
        summ = self.summary()
        if summ:
            lines.append("Metric summaries  (mean | p50 | p95 | p99 | n):")
            for name, s in summ.items():
                lines.append(
                    f"  {name:<35} "
                    f"{s['mean']:>8} | {s['p50']:>8} | {s['p95']:>8} | {s['p99']:>8} | n={s['count']}"
                )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist current metrics to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data: dict[str, Any] = {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "samples": [s.to_dict() for s in self._samples[-200:]],
        }
        with open(self.persist_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
            self._request_count = data.get("request_count", 0)
            self._error_count = data.get("error_count", 0)
            for s in data.get("samples", []):
                self._samples.append(MetricSample(
                    name=s["name"],
                    value=s["value"],
                    unit=s.get("unit", ""),
                    timestamp=s.get("timestamp", 0.0),
                    tags=s.get("tags", {}),
                ))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # corrupt file — start fresh
