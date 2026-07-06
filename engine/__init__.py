"""
AI Clone Engine of Charles-Earl-Lipshay
lippytm · lippytmai · v3.0

Industrial-grade sub-systems:
  AIToolkit           — code analysis, generation, test stubs, smell detection
  AISandbox           — isolated Python code execution with timeout and safety
  SelfImprovementSystem — interaction tracking, quality scoring, topic analysis
  SelfHealingSystem   — circuit breakers, backend failover, health monitoring
  PerformanceMonitor  — latency, error rate, and memory metrics
"""

from .core import CloneEngine
from .performance import PerformanceMonitor
from .sandbox import AISandbox
from .self_healing import SelfHealingSystem
from .self_improvement import SelfImprovementSystem
from .toolkit import AIToolkit

__version__ = "3.0.0"
__author__ = "lippytm"
__all__ = [
    "CloneEngine",
    "AIToolkit",
    "AISandbox",
    "SelfImprovementSystem",
    "SelfHealingSystem",
    "PerformanceMonitor",
]
