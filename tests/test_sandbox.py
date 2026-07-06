"""
tests/test_sandbox.py
Unit tests for engine.sandbox (AISandbox and SandboxResult).
"""

from __future__ import annotations

import time

import pytest
from engine.sandbox import AISandbox, SandboxResult


@pytest.fixture
def sb():
    return AISandbox(timeout=3.0, safe_mode=True)


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

def test_execute_print(sb):
    result = sb.execute("print('hello')")
    assert result.success is True
    assert result.stdout.strip() == "hello"
    assert result.error == ""


def test_execute_return_value(sb):
    result = sb.execute("_result = 6 * 7")
    assert result.success is True
    assert result.return_value == 42


def test_execute_multiline(sb):
    code = "x = 2\ny = 3\n_result = x + y"
    result = sb.execute(code)
    assert result.success is True
    assert result.return_value == 5


def test_execute_dedented():
    sb = AISandbox()
    code = """
        x = 10
        print(x)
    """
    result = sb.execute(code)
    assert result.success is True
    assert result.stdout.strip() == "10"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_execute_syntax_error(sb):
    result = sb.execute("def foo(")
    assert result.success is False
    assert result.error != ""


def test_execute_runtime_error(sb):
    result = sb.execute("1 / 0")
    assert result.success is False
    assert "ZeroDivisionError" in result.error


def test_execute_name_error(sb):
    result = sb.execute("print(undefined_variable)")
    assert result.success is False


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def test_execute_timeout():
    # Use unsafe mode so time.sleep is available; set a very short timeout.
    sb = AISandbox(timeout=0.1, safe_mode=False)
    result = sb.execute("import time; time.sleep(5)")
    assert result.timed_out is True
    assert result.success is False
    assert "timed out" in result.error.lower()


# ---------------------------------------------------------------------------
# Safe mode
# ---------------------------------------------------------------------------

def test_safe_mode_blocks_import():
    sb = AISandbox(safe_mode=True)
    result = sb.execute("import os; _result = os.getcwd()")
    assert result.success is False


def test_safe_mode_allows_builtins(sb):
    result = sb.execute("_result = list(range(5))")
    assert result.success is True
    assert result.return_value == [0, 1, 2, 3, 4]


def test_unsafe_mode_allows_import():
    sb = AISandbox(safe_mode=False)
    result = sb.execute("import math; _result = math.pi")
    assert result.success is True
    assert abs(result.return_value - 3.14159) < 0.001


# ---------------------------------------------------------------------------
# test_snippet
# ---------------------------------------------------------------------------

def test_test_snippet_output_match(sb):
    result = sb.test_snippet("print('ok')", expected_output="ok")
    assert result.success is True


def test_test_snippet_output_mismatch(sb):
    result = sb.test_snippet("print('wrong')", expected_output="right")
    assert result.success is False
    assert "mismatch" in result.error.lower()


def test_test_snippet_return_match(sb):
    result = sb.test_snippet("_result = 42", expected_return=42, check_return=True)
    assert result.success is True


def test_test_snippet_return_mismatch(sb):
    result = sb.test_snippet("_result = 1", expected_return=99, check_return=True)
    assert result.success is False
    assert "mismatch" in result.error.lower()


def test_test_snippet_no_check(sb):
    # Without check_return=True, return value is not validated
    result = sb.test_snippet("_result = 999")
    assert result.success is True


# ---------------------------------------------------------------------------
# run_tests batch
# ---------------------------------------------------------------------------

def test_run_tests_batch(sb):
    cases = [
        {"code": "print('a')", "expected_output": "a"},
        {"code": "print('b')", "expected_output": "b"},
        {"code": "_result = 1 + 1", "expected_return": 2, "check_return": True},
    ]
    results = sb.run_tests(cases)
    assert len(results) == 3
    assert all(r.success for r in results)


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------

def test_stderr_captured(sb):
    result = sb.execute("import sys; sys.stderr.write('err!')")
    # In safe mode import sys will fail; in any mode stderr should be captured
    # We just ensure the sandbox doesn't crash
    assert isinstance(result, SandboxResult)


def test_max_output_truncation():
    sb = AISandbox(max_output=10, safe_mode=False)
    result = sb.execute("print('x' * 1000)")
    assert len(result.stdout) <= 10


# ---------------------------------------------------------------------------
# SandboxResult.__str__
# ---------------------------------------------------------------------------

def test_sandbox_result_str(sb):
    result = sb.execute("print('hi')")
    s = str(result)
    assert "✓" in s or "✗" in s
    assert "elapsed" in s


# ---------------------------------------------------------------------------
# Elapsed timing
# ---------------------------------------------------------------------------

def test_elapsed_ms_positive(sb):
    result = sb.execute("x = 1")
    assert result.elapsed_ms >= 0.0
