"""
tests/test_toolkit.py
Unit tests for engine.toolkit (AIToolkit and built-in tools).
"""

from __future__ import annotations

import pytest
from engine.toolkit import (
    AIToolkit,
    ToolResult,
    _analyze_python,
    _count_complexity,
    _detect_code_smells,
    _diff_code,
    _extract_functions,
    _extract_todos,
    _generate_docstring_template,
    _generate_test_stubs,
    _estimate_token_count,
)


# ---------------------------------------------------------------------------
# _analyze_python
# ---------------------------------------------------------------------------

def test_analyze_python_valid():
    code = "def foo(x):\n    return x\n\nclass Bar:\n    pass\n"
    result = _analyze_python(code)
    assert result["valid_syntax"] is True
    assert "foo" in result["functions"]
    assert "Bar" in result["classes"]
    assert result["function_count"] == 1
    assert result["class_count"] == 1


def test_analyze_python_invalid():
    result = _analyze_python("def foo(")
    assert result["valid_syntax"] is False
    assert "error" in result


def test_analyze_python_async():
    code = "async def fetch(url):\n    pass\n"
    result = _analyze_python(code)
    assert result["valid_syntax"] is True
    assert "fetch" in result["async_functions"]


# ---------------------------------------------------------------------------
# _extract_functions
# ---------------------------------------------------------------------------

def test_extract_functions():
    code = (
        "def add(a, b):\n    '''Add two numbers.'''\n    return a + b\n\n"
        "def subtract(x, y=0):\n    return x - y\n"
    )
    fns = _extract_functions(code)
    names = [f["name"] for f in fns]
    assert "add" in names
    assert "subtract" in names
    add_fn = next(f for f in fns if f["name"] == "add")
    assert add_fn["docstring"] == "Add two numbers."
    assert add_fn["required_args"] == ["a", "b"]


def test_extract_functions_empty():
    assert _extract_functions("x = 1") == []


def test_extract_functions_invalid_syntax():
    assert _extract_functions("def foo(") == []


# ---------------------------------------------------------------------------
# _count_complexity
# ---------------------------------------------------------------------------

def test_count_complexity_simple():
    code = "def f():\n    return 1\n"
    result = _count_complexity(code)
    assert result["cyclomatic_complexity"] >= 1
    assert result["risk_level"] == "low"


def test_count_complexity_complex():
    code = (
        "def f(x):\n"
        "    if x > 0:\n"
        "        for i in range(x):\n"
        "            while i > 0:\n"
        "                if i % 2 == 0:\n"
        "                    pass\n"
        "                i -= 1\n"
    )
    result = _count_complexity(code)
    assert result["cyclomatic_complexity"] >= 5


def test_count_complexity_syntax_error():
    result = _count_complexity("def f(")
    assert "error" in result


# ---------------------------------------------------------------------------
# _detect_code_smells
# ---------------------------------------------------------------------------

def test_detect_code_smells_broad_exception():
    code = "try:\n    pass\nexcept:\n    pass\n"
    smells = _detect_code_smells(code)
    codes = [s["code"] for s in smells]
    assert "B001" in codes


def test_detect_code_smells_wildcard_import():
    code = "from os import *\n"
    smells = _detect_code_smells(code)
    codes = [s["code"] for s in smells]
    assert "F401" in codes


def test_detect_code_smells_eval():
    code = "result = eval('2+2')\n"
    smells = _detect_code_smells(code)
    codes = [s["code"] for s in smells]
    assert "S307" in codes


def test_detect_code_smells_clean():
    code = "def add(a, b):\n    return a + b\n"
    smells = _detect_code_smells(code)
    assert smells == []


# ---------------------------------------------------------------------------
# _generate_docstring_template
# ---------------------------------------------------------------------------

def test_generate_docstring_google():
    doc = _generate_docstring_template("my_func", ["a", "b"], style="google")
    assert "my_func" in doc
    assert "Args:" in doc
    assert "a:" in doc


def test_generate_docstring_numpy():
    doc = _generate_docstring_template("my_func", ["x"], style="numpy")
    assert "Parameters" in doc
    assert "x" in doc


def test_generate_docstring_skips_self():
    doc = _generate_docstring_template("method", ["self", "x"], style="google")
    assert "self:" not in doc
    assert "x:" in doc


# ---------------------------------------------------------------------------
# _generate_test_stubs
# ---------------------------------------------------------------------------

def test_generate_test_stubs_pytest():
    code = "def add(a, b):\n    return a + b\n"
    stubs = _generate_test_stubs(code, framework="pytest")
    assert "def test_add" in stubs
    assert "import pytest" in stubs


def test_generate_test_stubs_unittest():
    code = "def greet(name):\n    return f'Hello {name}'\n"
    stubs = _generate_test_stubs(code, framework="unittest")
    assert "import unittest" in stubs
    assert "test_greet" in stubs


def test_generate_test_stubs_no_functions():
    stubs = _generate_test_stubs("x = 1")
    assert "No functions found" in stubs


# ---------------------------------------------------------------------------
# _diff_code
# ---------------------------------------------------------------------------

def test_diff_code_added():
    original = "line1\n"
    modified = "line1\nline2\n"
    result = _diff_code(original, modified)
    assert result["added_lines"] == 1
    assert result["removed_lines"] == 0
    assert result["net_change"] == 1


def test_diff_code_removed():
    original = "line1\nline2\n"
    modified = "line1\n"
    result = _diff_code(original, modified)
    assert result["removed_lines"] == 1


# ---------------------------------------------------------------------------
# _extract_todos
# ---------------------------------------------------------------------------

def test_extract_todos():
    code = "# TODO: fix this\nx = 1  # FIXME: broken\n"
    todos = _extract_todos(code)
    markers = {t["marker"] for t in todos}
    assert "TODO" in markers
    assert "FIXME" in markers


def test_extract_todos_empty():
    assert _extract_todos("x = 1\n") == []


# ---------------------------------------------------------------------------
# _estimate_token_count
# ---------------------------------------------------------------------------

def test_estimate_token_count_heuristic():
    text = "Hello world, this is a test sentence."
    result = _estimate_token_count(text)
    assert result["token_count"] > 0
    assert "method" in result


# ---------------------------------------------------------------------------
# AIToolkit registry
# ---------------------------------------------------------------------------

def test_toolkit_list_tools():
    tk = AIToolkit()
    tools = tk.list_tools()
    assert "analyze_python" in tools
    assert "generate_test_stubs" in tools
    assert "detect_code_smells" in tools


def test_toolkit_call_success():
    tk = AIToolkit()
    result = tk.call("analyze_python", code="x = 1")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output["valid_syntax"] is True


def test_toolkit_call_unknown_tool():
    tk = AIToolkit()
    result = tk.call("nonexistent_tool")
    assert result.success is False
    assert "Unknown tool" in result.error


def test_toolkit_register_custom():
    tk = AIToolkit()
    tk.register("double", lambda n: n * 2)
    result = tk.call("double", n=21)
    assert result.success is True
    assert result.output == 42


def test_toolkit_elapsed_ms():
    tk = AIToolkit()
    result = tk.call("analyze_python", code="pass")
    assert result.elapsed_ms >= 0.0


def test_toolkit_report_after_calls():
    tk = AIToolkit()
    tk.call("analyze_python", code="pass")
    report = tk.report()
    assert "analyze_python" in report
    assert "1 calls" in report
