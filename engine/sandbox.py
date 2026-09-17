"""
engine/sandbox.py
AI Sandbox — an isolated, resource-limited Python code execution environment.

Supports safe execution of AI-generated code with:
  - Configurable wall-clock timeout via a daemon thread
  - stdout/stderr capture
  - Restricted built-ins in safe mode
  - Return-value extraction via the ``_result`` convention
  - Output-size capping to prevent memory exhaustion

Usage
-----
    from engine.sandbox import AISandbox

    sb = AISandbox(timeout=5.0, safe_mode=True)
    result = sb.execute("print('hello world')")
    print(result.stdout)   # "hello world\\n"
    print(result.success)  # True

    # Validate output against expected value
    result = sb.test_snippet("print(2 + 2)", expected_output="4")
"""

from __future__ import annotations

import io
import sys
import textwrap
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Safe built-ins whitelist
# ---------------------------------------------------------------------------

_SAFE_BUILTINS_NAMES: frozenset[str] = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "complex", "dict", "dir", "divmod", "enumerate",
    "filter", "float", "format", "frozenset", "getattr", "hasattr", "hash",
    "hex", "id", "int", "isinstance", "issubclass", "iter", "len", "list",
    "map", "max", "min", "next", "object", "oct", "ord", "pow", "print",
    "property", "range", "repr", "reversed", "round", "set", "setattr",
    "slice", "sorted", "staticmethod", "str", "sum", "super", "tuple",
    "type", "vars", "zip", "classmethod",
    # Exceptions (read-only access is safe)
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
    "AssertionError", "ArithmeticError", "ZeroDivisionError",
    "OverflowError", "MemoryError", "RecursionError",
    "True", "False", "None",
})


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class SandboxResult:
    """Captures the outcome of a sandbox execution."""

    success: bool
    stdout: str
    stderr: str
    return_value: Any
    elapsed_ms: float
    error: str = ""
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_value": repr(self.return_value),
            "elapsed_ms": round(self.elapsed_ms, 2),
            "error": self.error,
            "timed_out": bool(self.timed_out),
        }

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        parts = [f"[{status}] elapsed={self.elapsed_ms:.1f}ms"]
        if self.stdout:
            parts.append(f"stdout={self.stdout!r}")
        if self.stderr:
            parts.append(f"stderr={self.stderr!r}")
        if self.error:
            parts.append(f"error={self.error!r}")
        return "  ".join(parts)


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

class AISandbox:
    """
    Isolated Python execution environment for AI-generated code.

    Parameters
    ----------
    timeout:    Maximum wall-clock execution time in seconds (default 5s).
    max_output: Maximum bytes to capture from stdout/stderr (default 8 KiB).
    safe_mode:  If True, restrict ``__builtins__`` to a safe subset.
                Set to False only for trusted code.
    """

    def __init__(
        self,
        timeout: float = 5.0,
        max_output: int = 8192,
        safe_mode: bool = True,
    ) -> None:
        self.timeout = timeout
        self.max_output = max_output
        self.safe_mode = safe_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        code: str,
        globals_ctx: dict[str, Any] | None = None,
    ) -> SandboxResult:
        """
        Execute *code* in the sandbox.

        The variable ``_result`` in the executed namespace is exposed as
        ``SandboxResult.return_value``, enabling snippets to return values:

            code = "_result = 2 + 2"
            sb.execute(code).return_value  # 4

        Parameters
        ----------
        code:        Python source to execute.
        globals_ctx: Optional extra names injected into the execution namespace.

        Returns
        -------
        SandboxResult
        """
        code = textwrap.dedent(code).strip()

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        exec_globals: dict[str, Any] = dict(globals_ctx or {})
        exec_globals["__builtins__"] = self._make_builtins()

        # Mutable containers for cross-thread communication
        state: dict[str, Any] = {
            "return_value": None,
            "success": False,
            "exc": None,
        }

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = stdout_buf
        sys.stderr = stderr_buf

        def _runner() -> None:
            try:
                compiled = compile(code, "<sandbox>", "exec")
                exec(compiled, exec_globals)  # noqa: S102
                state["return_value"] = exec_globals.get("_result")
                state["success"] = True
            except Exception as exc:
                state["exc"] = exc
                sys.stderr.write(traceback.format_exc())

        start = time.perf_counter()
        timed_out = False
        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000

        sys.stdout = old_stdout
        sys.stderr = old_stderr

        if thread.is_alive():
            timed_out = True

        stdout_val = stdout_buf.getvalue()[: self.max_output]
        stderr_val = stderr_buf.getvalue()[: self.max_output]

        if timed_out:
            return SandboxResult(
                success=False,
                stdout=stdout_val,
                stderr=stderr_val,
                return_value=None,
                elapsed_ms=elapsed_ms,
                error=f"Execution timed out after {self.timeout}s",
                timed_out=True,
            )

        exc = state.get("exc")
        if exc is not None:
            return SandboxResult(
                success=False,
                stdout=stdout_val,
                stderr=stderr_val,
                return_value=None,
                elapsed_ms=elapsed_ms,
                error=f"{type(exc).__name__}: {exc}",
            )

        return SandboxResult(
            success=state["success"],
            stdout=stdout_val,
            stderr=stderr_val,
            return_value=state["return_value"],
            elapsed_ms=elapsed_ms,
        )

    def test_snippet(
        self,
        code: str,
        expected_output: str | None = None,
        expected_return: Any = None,
        check_return: bool = False,
    ) -> SandboxResult:
        """
        Execute a snippet and optionally validate stdout or return value.

        Parameters
        ----------
        code:            Python source to execute.
        expected_output: Expected stdout text (stripped). If provided and
                         the actual output differs, ``success`` is set False.
        expected_return: Expected ``_result`` value. Only checked when
                         ``check_return=True``.
        check_return:    If True, compare ``_result`` against ``expected_return``.
        """
        result = self.execute(code)
        if not result.success:
            return result

        if expected_output is not None:
            actual = result.stdout.strip()
            expected = expected_output.strip()
            if actual != expected:
                result.success = False
                result.error = (
                    f"Output mismatch — expected: {expected!r}, got: {actual!r}"
                )

        if check_return:
            if result.return_value != expected_return:
                result.success = False
                result.error = (
                    f"Return value mismatch — expected: {expected_return!r}, "
                    f"got: {result.return_value!r}"
                )

        return result

    # Store sentinel as class attribute to avoid NameError in the method
    _sentinel = object()

    def run_tests(self, test_cases: list[dict[str, Any]]) -> list[SandboxResult]:
        """
        Run a batch of test cases.

        Each test case is a dict with keys:
          - ``code``            (required)  Python source
          - ``expected_output`` (optional)  Expected stdout
          - ``expected_return`` (optional)  Expected _result value
        """
        results = []
        for tc in test_cases:
            kwargs: dict[str, Any] = {"code": tc["code"]}
            if "expected_output" in tc:
                kwargs["expected_output"] = tc["expected_output"]
            if "expected_return" in tc:
                kwargs["expected_return"] = tc["expected_return"]
            results.append(self.test_snippet(**kwargs))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_builtins(self) -> Any:
        import builtins as _builtins_module
        if not self.safe_mode:
            return _builtins_module
        return {
            name: getattr(_builtins_module, name)
            for name in _SAFE_BUILTINS_NAMES
            if hasattr(_builtins_module, name)
        }
