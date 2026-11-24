#!/usr/bin/env python3
"""Generate a test-function ledger skeleton from Python test files.

Usage:
    python inventory.py tests/*.py
    python inventory.py --root 材料包/cancel-async-tasks --ledger
    python inventory.py tests/test_outputs.py --json

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _node_lines(node: ast.AST) -> tuple[int, int]:
    return (getattr(node, "lineno", 0), getattr(node, "end_lineno", getattr(node, "lineno", 0)))


def _call_name(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _has_skip(decorators: list[ast.expr]) -> str:
    for dec in decorators:
        name = _call_name(dec.func if isinstance(dec, ast.Call) else dec)
        if name.endswith("mark.skip") or name.endswith("mark.skipif"):
            return "skip"
        if name.endswith("mark.xfail"):
            return "xfail"
    return ""


def _broad_except(func: ast.AST) -> list[int]:
    """Return line numbers of try blocks that swallow Exception/BaseException."""
    hits: list[int] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                hits.append(handler.lineno)
                continue
            names = []
            if isinstance(handler.type, ast.Tuple):
                names = [_call_name(e) for e in handler.type.elts]
            else:
                names = [_call_name(handler.type)]
            if any(n in {"Exception", "BaseException", "builtins.Exception"} for n in names):
                body_has_raise = any(isinstance(stmt, ast.Raise) for stmt in handler.body)
                if not body_has_raise:
                    hits.append(handler.lineno)
    return hits


TIME_FUNCS = {"sleep", "monotonic", "perf_counter", "time", "localtime"}


def analyze_function(path: Path, func: ast.AST, source: str) -> dict:
    asserts = [n.lineno for n in ast.walk(func) if isinstance(n, ast.Assert)]
    raises = [
        n.lineno
        for n in ast.walk(func)
        if isinstance(n, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and _call_name(item.context_expr.func).endswith("raises")
            for item in n.items
        )
    ]
    awaits = sum(1 for n in ast.walk(func) if isinstance(n, ast.Await))
    sleeps = [
        n.lineno
        for n in ast.walk(func)
        if isinstance(n, ast.Call) and _call_name(n.func).split(".")[-1] in TIME_FUNCS
    ]
    vacuous = [
        n.lineno
        for n in ast.walk(func)
        if isinstance(n, ast.Assert)
        and isinstance(n.test, ast.Constant)
        and bool(n.test.value) is True
    ]
    broad = _broad_except(func)
    skip = _has_skip(list(getattr(func, "decorator_list", [])))

    flags: list[str] = []
    if not asserts:
        flags.append("no-assert")
    if vacuous:
        flags.append("assert-true")
    if broad:
        flags.append("broad-except-swallow")
    if sleeps:
        flags.append("sleep")
    if skip:
        flags.append(skip)
    if awaits == 0 and isinstance(func, ast.AsyncFunctionDef):
        flags.append("async-no-await")

    return {
        "file": str(path),
        "name": func.name,
        "lines": list(_node_lines(func)),
        "assert_lines": asserts,
        "raises_lines": raises,
        "await_count": awaits,
        "sleep_lines": sleeps,
        "broad_except_lines": broad,
        "flags": flags,
        "docstring": (ast.get_docstring(func) or "").strip().splitlines()[0:1],
    }


def collect(paths: list[Path], include_all: bool = False) -> list[dict]:
    rows: list[dict] = []

    def walk(body: list[ast.stmt], owner: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if include_all or node.name.startswith("test_"):
                    row = analyze_function(Path(""), node, "")
                    row["name"] = f"{owner}.{node.name}" if owner else node.name
                    rows.append(row)
            elif isinstance(node, ast.ClassDef):
                walk(node.body, f"{owner}.{node.name}" if owner else node.name)

    for path in paths:
        try:
            tree = ast.parse(_read(path), filename=str(path))
        except SyntaxError as exc:
            rows.append({"file": str(path), "name": "<syntax-error>", "error": str(exc)})
            continue
        before = len(rows)
        walk(tree.body)
        for row in rows[before:]:
            row["file"] = str(path)
    return rows


def to_markdown(rows: list[dict], ledger: bool) -> str:
    if ledger:
        out = [
            "| # | 文件 | 函数 | 行号 | 声称验证 | 实际断言 | 结论 | 依据 | issue |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for i, row in enumerate(rows, 1):
            if row.get("error"):
                out.append(f"| {i} | {row['file']} | SYNTAX ERROR | - | - | - | 可疑 | {row['error']} |  |")
                continue
            lines = f"L{row['lines'][0]}-L{row['lines'][1]}"
            asserts = ", ".join(f"L{x}" for x in row["assert_lines"]) or "无"
            flags = ",".join(row["flags"])
            out.append(
                f"| {i} | {row['file']} | {row['name']} | {lines} |  | {asserts} |  | {flags} |  |"
            )
        return "\n".join(out)

    out = [
        "| # | 文件 | 函数 | 行号 | 断言数 | raises | await | 可疑标记 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, row in enumerate(rows, 1):
        if row.get("error"):
            out.append(f"| {i} | {row['file']} | SYNTAX ERROR | - | - | - | - | {row['error']} |")
            continue
        lines = f"L{row['lines'][0]}-L{row['lines'][1]}"
        flags = ", ".join(row["flags"]) or "—"
        out.append(
            f"| {i} | {row['file']} | {row['name']} | {lines} | "
            f"{len(row['assert_lines'])} | {len(row['raises_lines'])} | {row['await_count']} | {flags} |"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    parser = argparse.ArgumentParser(description="Inventory test functions for a coverage ledger.")
    parser.add_argument("paths", nargs="*", help="Python test files (globs are expanded by the shell).")
    parser.add_argument("--root", help="Package root; scans <root>/tests/**/*.py")
    parser.add_argument("--ledger", action="store_true", help="Emit a blank ledger table.")
    parser.add_argument("--all", action="store_true", help="Include harness/helper functions, not only test_*.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args(argv)

    paths: list[Path] = []
    if args.root:
        root = Path(args.root)
        paths.extend(sorted((root / "tests").rglob("*.py")))
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            paths.extend(sorted(p.rglob("*.py")))
        else:
            paths.append(p)

    paths = [p for p in paths if p.exists() and p.suffix == ".py"]
    if not paths:
        print("no python test files found", file=sys.stderr)
        return 2

    rows = collect(paths, include_all=args.all)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(rows, args.ledger))
        label = "function(s)" if args.all else "test function(s)"
        print(f"\n{len(rows)} {label} in {len(paths)} file(s)", file=sys.stderr)
    return 3 if any(row.get("error") for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
