"""
engine/toolkit.py
Industrial-Grade AI Toolkit — a registry of callable AI tools for code analysis,
generation, debugging, documentation, testing, and optimization.

Tools are pure Python and require no external dependencies.
"""

from __future__ import annotations

import ast
import json
import os
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result of a single tool invocation."""

    tool_name: str
    success: bool
    output: Any
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AIToolkit:
    """
    Registry and dispatcher for AI-powered development tools.

    Usage
    -----
    toolkit = AIToolkit()
    result = toolkit.call("analyze_python", code="def hello(): pass")
    print(result.output)

    Custom tools can be registered at runtime:
        toolkit.register("my_tool", my_function)
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._call_log: list[dict[str, Any]] = []
        self._register_builtins()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a custom tool under *name*."""
        self._tools[name] = fn

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        """Invoke a registered tool by name, capturing timing and errors."""
        if name not in self._tools:
            return ToolResult(
                tool_name=name, success=False, output=None,
                error=f"Unknown tool '{name}'. Available: {self.list_tools()}",
            )
        start = time.perf_counter()
        try:
            output = self._tools[name](**kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            result = ToolResult(tool_name=name, success=True, output=output, elapsed_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            result = ToolResult(
                tool_name=name, success=False, output=None,
                error=str(exc), elapsed_ms=elapsed,
            )
        self._call_log.append(result.to_dict())
        if len(self._call_log) > 500:
            self._call_log = self._call_log[-500:]
        return result

    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""
        return sorted(self._tools.keys())

    def call_log(self) -> list[dict[str, Any]]:
        """Return recent tool call records."""
        return list(self._call_log)

    def report(self) -> str:
        """Return a human-readable toolkit usage report."""
        if not self._call_log:
            return "AI Toolkit: no calls recorded yet."
        counts: dict[str, int] = {}
        errors: dict[str, int] = {}
        for entry in self._call_log:
            name = entry["tool"]
            counts[name] = counts.get(name, 0) + 1
            if not entry["success"]:
                errors[name] = errors.get(name, 0) + 1
        lines = [
            "=== AI Toolkit Report ===",
            f"Tools available : {len(self._tools)}",
            f"Total calls     : {len(self._call_log)}",
            "Call breakdown:",
        ]
        for name in sorted(counts):
            err_note = f" ({errors[name]} errors)" if name in errors else ""
            lines.append(f"  {name}: {counts[name]} calls{err_note}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Built-in tool registration
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        self.register("analyze_python", _analyze_python)
        self.register("extract_functions", _extract_functions)
        self.register("extract_classes", _extract_classes)
        self.register("count_complexity", _count_complexity)
        self.register("detect_code_smells", _detect_code_smells)
        self.register("format_code", _format_code)
        self.register("generate_docstring", _generate_docstring_template)
        self.register("generate_test_stubs", _generate_test_stubs)
        self.register("summarize_file", _summarize_file)
        self.register("diff_code", _diff_code)
        self.register("extract_todos", _extract_todos)
        self.register("estimate_token_count", _estimate_token_count)


# ---------------------------------------------------------------------------
# Built-in tool implementations
# ---------------------------------------------------------------------------

def _analyze_python(code: str) -> dict[str, Any]:
    """Parse and structurally analyze Python source code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"valid_syntax": False, "error": str(exc), "line": exc.lineno}

    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    async_functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(f"{module}.{alias.name}" for alias in node.names)
    lines = code.splitlines()
    return {
        "valid_syntax": True,
        "line_count": len(lines),
        "blank_lines": sum(1 for l in lines if not l.strip()),
        "functions": functions,
        "async_functions": async_functions,
        "classes": classes,
        "imports": imports,
        "function_count": len(functions) + len(async_functions),
        "class_count": len(classes),
    }


def _extract_functions(code: str) -> list[dict[str, Any]]:
    """Extract all function definitions with signatures and docstrings."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            defaults = len(node.args.defaults)
            required = len(args) - defaults
            results.append({
                "name": node.name,
                "line": node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "args": args,
                "required_args": args[:required],
                "optional_args": args[required:],
                "docstring": ast.get_docstring(node) or "",
                "decorator_count": len(node.decorator_list),
            })
    return sorted(results, key=lambda x: x["line"])


def _extract_classes(code: str) -> list[dict[str, Any]]:
    """Extract all class definitions with methods and base classes."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(f"{b.value.id}.{b.attr}" if isinstance(b.value, ast.Name) else b.attr)
            methods = [
                n.name for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            results.append({
                "name": node.name,
                "line": node.lineno,
                "bases": bases,
                "methods": methods,
                "docstring": ast.get_docstring(node) or "",
            })
    return sorted(results, key=lambda x: x["line"])


def _count_complexity(code: str) -> dict[str, Any]:
    """
    Estimate cyclomatic complexity by counting branching and looping constructs.
    Complexity = 1 + number of decision points.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"error": "SyntaxError — cannot parse code"}

    node_types = {
        "if_branches": (ast.If,),
        "for_loops": (ast.For, ast.AsyncFor),
        "while_loops": (ast.While,),
        "try_blocks": (ast.Try,),
        "with_blocks": (ast.With, ast.AsyncWith),
        "assert_stmts": (ast.Assert,),
        "boolean_ops": (ast.BoolOp,),
    }
    counts: dict[str, int] = {}
    for label, types in node_types.items():
        counts[label] = sum(1 for n in ast.walk(tree) if isinstance(n, types))

    complexity = 1 + sum(counts.values())
    risk = "low" if complexity <= 5 else "medium" if complexity <= 10 else "high"
    return {**counts, "cyclomatic_complexity": complexity, "risk_level": risk}


def _detect_code_smells(code: str) -> list[dict[str, Any]]:
    """Identify common code quality issues in Python source."""
    issues: list[dict[str, Any]] = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()
        # Long lines
        if len(stripped) > 120:
            issues.append({
                "line": i, "severity": "warning",
                "code": "E501",
                "message": f"Line too long ({len(stripped)} > 120 chars)",
            })
        # Marker comments
        for marker in ("TODO", "FIXME", "HACK", "XXX", "NOQA"):
            if marker in stripped:
                issues.append({
                    "line": i, "severity": "info",
                    "code": "C001",
                    "message": f"{marker} marker: {stripped.strip()[:60]}",
                })
        # Broad exception catches
        if "except:" in stripped or "except Exception:" in stripped or "except BaseException:" in stripped:
            issues.append({
                "line": i, "severity": "warning",
                "code": "B001",
                "message": "Broad exception catch — consider catching specific exceptions",
            })
        # Wildcard imports
        if stripped.strip().startswith("from ") and "import *" in stripped:
            issues.append({
                "line": i, "severity": "error",
                "code": "F401",
                "message": "Wildcard import — pollutes namespace and hides dependencies",
            })
        # Dynamic execution
        for danger in ("eval(", "exec(", "compile("):
            if danger in stripped:
                issues.append({
                    "line": i, "severity": "error",
                    "code": "S307",
                    "message": f"Dynamic code execution ({danger[:-1]}) — potential security risk",
                })
        # Mutable default arguments
        if "def " in stripped and ("=[]" in stripped or "={}" in stripped):
            issues.append({
                "line": i, "severity": "warning",
                "code": "B006",
                "message": "Mutable default argument — use None and initialize in body",
            })

    return issues


def _format_code(code: str) -> str:
    """Basic code normalization — dedent and strip trailing whitespace."""
    lines = textwrap.dedent(code).splitlines()
    return "\n".join(line.rstrip() for line in lines).strip()


def _generate_docstring_template(
    function_name: str,
    args: list[str] | None = None,
    returns: str = "",
    style: str = "google",
) -> str:
    """
    Generate a docstring template for a function.

    Supports 'google' and 'numpy' docstring styles.
    """
    args = args or []
    param_args = [a for a in args if a not in ("self", "cls")]

    if style == "numpy":
        lines = [f'"""', f"Summary of {function_name}.", ""]
        if param_args:
            lines += ["Parameters", "----------"]
            for arg in param_args:
                lines += [f"{arg} : type", f"    Description of {arg}."]
        if returns:
            lines += ["", "Returns", "-------", f"{returns}", "    Description of return value."]
        lines.append('"""')
    else:  # google style
        lines = [f'"""', f"Summary of {function_name}.", ""]
        if param_args:
            lines.append("Args:")
            for arg in param_args:
                lines.append(f"    {arg}: Description of {arg}.")
        if returns:
            lines += ["", "Returns:", f"    {returns}: Description of return value."]
        lines.append('"""')

    return "\n".join(lines)


def _generate_test_stubs(code: str, framework: str = "pytest") -> str:
    """
    Generate test stub functions for all discovered functions in *code*.
    Supports 'pytest' and 'unittest' frameworks.
    """
    functions = _extract_functions(code)
    if not functions:
        return "# No functions found — nothing to stub."

    if framework == "unittest":
        lines = [
            "# Auto-generated test stubs (unittest)",
            "import unittest",
            "",
            "",
            "class TestGenerated(unittest.TestCase):",
        ]
        for fn in functions:
            name = fn["name"]
            if name.startswith("_"):
                continue
            lines += [
                f"    def test_{name}(self):",
                f'        """Test {name}."""',
                "        # TODO: implement",
                "        self.fail('Not implemented')",
                "",
            ]
        lines += ["", "if __name__ == '__main__':", "    unittest.main()"]
    else:  # pytest (default)
        lines = [
            "# Auto-generated test stubs (pytest)",
            "import pytest",
            "",
        ]
        for fn in functions:
            name = fn["name"]
            if name.startswith("_"):
                continue
            args_repr = ", ".join(repr(None) for _ in fn.get("required_args", []))
            lines += [
                f"def test_{name}():",
                f'    """Test {name}."""',
                "    # TODO: implement",
                "    pass",
                "",
            ]

    return "\n".join(lines)


def _summarize_file(path: str) -> dict[str, Any]:
    """Summarize a source file's structure and statistics."""
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
    stat = os.stat(path)
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        code = fh.read()
    result: dict[str, Any] = {
        "path": path,
        "extension": ext,
        "size_bytes": stat.st_size,
        "line_count": len(code.splitlines()),
        "char_count": len(code),
    }
    if ext == ".py":
        result["analysis"] = _analyze_python(code)
        result["smells"] = _detect_code_smells(code)
    return result


def _diff_code(original: str, modified: str) -> dict[str, Any]:
    """Produce a simple unified diff and change statistics."""
    import difflib
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    diff = list(difflib.unified_diff(original_lines, modified_lines, lineterm=""))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return {
        "added_lines": added,
        "removed_lines": removed,
        "net_change": added - removed,
        "diff": "\n".join(diff[:200]),  # cap output
    }


def _extract_todos(code: str) -> list[dict[str, Any]]:
    """Extract all TODO/FIXME/HACK/NOTE/OPTIMIZE comments from source."""
    markers = ("TODO", "FIXME", "HACK", "NOTE", "OPTIMIZE", "XXX", "BUG")
    results: list[dict[str, Any]] = []
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        for marker in markers:
            if marker in stripped:
                # Find comment text
                comment_start = line.find("#")
                comment_text = line[comment_start:].strip() if comment_start != -1 else stripped
                results.append({
                    "line": i,
                    "marker": marker,
                    "text": comment_text[:120],
                })
                break
    return results


def _estimate_token_count(text: str, model: str = "gpt-4o") -> dict[str, Any]:
    """
    Estimate the token count for *text* using a simple word-based heuristic.
    For accurate counts install the ``tiktoken`` package.
    """
    try:
        import tiktoken  # type: ignore[import]
        enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
        exact = len(enc.encode(text))
        return {"method": "tiktoken", "model": model, "token_count": exact}
    except Exception:
        # Fallback: ~4 chars per token (GPT rule of thumb)
        approx = max(1, len(text) // 4)
        return {
            "method": "heuristic (4 chars/token)",
            "model": model,
            "token_count": approx,
            "note": "Install tiktoken for accurate counts: pip install tiktoken",
        }
