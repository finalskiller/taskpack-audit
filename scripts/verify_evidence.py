#!/usr/bin/env python3
"""Verify that every evidence quote exists at the cited location.

Usage:
    python verify_evidence.py review.json --root 材料包/cancel-async-tasks --work ../work
    python verify_evidence.py review.json --root . --strict
    python verify_evidence.py review.json --root . --json

Checks:
  1. source/file mapping is legal
  2. evidence.content appears (whitespace-normalized) inside one of the cited line ranges
  3. a run_output quote has a matching record under the work directory
  4. --strict: warnings (missing line refs, oversized ranges, unrecorded run_output) fail

Exit code 1 if any FAIL (or any WARN under --strict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SOURCE_DEFAULTS = {
    "instruction": "instruction.md",
    "test_code": "tests/test_outputs.py",
    "reference_solution": "solution/solve.sh",
    "task_metadata": "task.toml",
    "rubric": "rubric.md",
    "run_output": "",
}

ALLOWED_PREFIX = {
    "instruction": ("instruction.md",),
    "test_code": ("tests/", "tests\\"),
    "reference_solution": ("solution/", "solution\\"),
    "task_metadata": ("task.toml", "readme.md"),
    "rubric": ("rubric.md",),
}

PATH_RE = re.compile(r"([A-Za-z0-9_./\\\-\u4e00-\u9fff]+\.(?:py|md|sh|toml|json|txt))")
RANGE_RE = re.compile(r"L(\d+)(?:\s*[-–~]\s*L?(\d+))?")
COLON_RE = re.compile(r":(\d+)(?:\s*[-–~]\s*(\d+))?")
MAX_RANGE_LINES = 40


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_allowed(root: Path, source: str, path: Path) -> tuple[bool, str]:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix().lower()
    except ValueError:
        return False, f"file outside package: {path}"
    prefixes = ALLOWED_PREFIX.get(source)
    if prefixes is None:
        return True, ""
    if any(rel == p.lower() or rel.startswith(p.lower()) for p in prefixes):
        return True, ""
    return False, f"{source} cannot cite {rel}"


def resolve_candidates(root: Path, where: str) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for match in PATH_RE.finditer(where):
        candidate = match.group(1).replace("\\", "/").lstrip("./")
        path = root / candidate
        if path.exists() and path not in seen:
            seen.add(path)
            candidates.append((path, candidate))
    return candidates


def parse_ranges(where: str) -> list[tuple[int, int]]:
    matches = list(RANGE_RE.finditer(where))
    if not matches:
        matches = list(COLON_RE.finditer(where))
    ranges: list[tuple[int, int]] = []
    for match in matches:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if (start, end) not in ranges:
            ranges.append((start, end))
    return ranges


def cited_ranges_by_file(root: Path, where: str) -> list[tuple[Path, str, list[tuple[int, int]]]]:
    """Split a multi-file where on semicolons; inherit the last file for bare ranges."""
    result: list[tuple[Path, str, list[tuple[int, int]]]] = []
    last: tuple[Path, str] | None = None
    for raw in re.split(r"[；;]", where):
        ranges = parse_ranges(raw)
        found: tuple[Path, str] | None = None
        for match in PATH_RE.finditer(raw):
            candidate = match.group(1).replace("\\", "/").lstrip("./")
            path = root / candidate
            if path.exists():
                found = (path, candidate)
                break
        if found:
            last = found
        if ranges and last:
            result.append((last[0], last[1], ranges))
    return result


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def find_work_dir(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    for candidate in (root / "work", root.parent / "work"):
        if candidate.exists():
            return candidate
    return None


def check_run_output(root: Path, content: str, work_dir: Path | None, strict: bool) -> dict:
    result = {"status": "WARN", "reason": "run_output has no matching record under work/"}
    if work_dir is None:
        return result
    for path in work_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".log", ".txt", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if norm(content) in norm(text):
            result["status"] = "PASS"
            result["reason"] = f"found in {path}"
            return result
    return result


def check_issue(root: Path, issue: dict, section: str, work_dir: Path | None, strict: bool) -> dict:
    issue_id = issue.get("id", "?")
    evidence = issue.get("evidence") or {}
    source = (evidence.get("source") or "").strip()
    where = (evidence.get("where") or "").strip()
    # Normalize full-width punctuation so Chinese-authored refs still parse.
    where = (
        where.replace("－", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("：", ":")
        .replace("，", ",")
        .replace("Ｌ", "L")
        .replace("（", "(")
        .replace("）", ")")
    )
    content = (evidence.get("content") or "").strip()

    result = {"id": issue_id, "section": section, "source": source, "status": "FAIL", "reason": ""}

    if source not in SOURCE_DEFAULTS:
        result["reason"] = f"unknown source: {source!r}"
        return result
    if not content:
        result["reason"] = "empty content"
        return result
    if len(norm(content)) < 8:
        result["reason"] = "content too short to be evidence"
        return result

    if source == "run_output":
        return {**result, **check_run_output(root, content, work_dir, strict)}

    candidates = resolve_candidates(root, where)
    if not candidates:
        default = SOURCE_DEFAULTS.get(source, "")
        path = root / default if default else None
        if path and path.exists():
            candidates = [(path, default)]
        else:
            result["reason"] = f"no cited file found; default {default!r} missing"
            return result

    # Validate every cited file/range, not just the one content matches.
    # Otherwise a bogus second reference (e.g. "instruction.md L999-L1000") passes silently.
    for path, rel, ranges in cited_ranges_by_file(root, where):
        lines = read_lines(path)
        for start, end in ranges:
            if start < 1 or end < 1 or start > len(lines) or end > len(lines):
                result["reason"] = f"cited range L{start}-L{end} is outside {rel} ({len(lines)} lines)"
                return result

    allowed = [(p, r) for p, r in candidates if is_allowed(root, source, p)[0]]
    if not allowed:
        why = is_allowed(root, source, candidates[0][0])[1]
        result["reason"] = f"cited file not allowed for {source}: {why}"
        return result

    ranges = parse_ranges(where)
    if not ranges:
        for path, rel in allowed:
            if norm(content) in norm("\n".join(read_lines(path))):
                return {
                    **result,
                    "status": "FAIL" if strict else "WARN",
                    "reason": f"quote found in {rel} but where has no line number",
                }
        result["reason"] = "no line range in where and quote not found"
        return result

    oversized = False
    out_of_bounds = False
    for path, rel in allowed:
        lines = read_lines(path)
        for start, end in ranges:
            if start < 1 or start > len(lines) or end > len(lines):
                out_of_bounds = True
                continue
            if end < start:
                start, end = end, start
            if end - start + 1 > MAX_RANGE_LINES:
                oversized = True
            if norm(content) in norm("\n".join(lines[start - 1 : end])):
                status = "WARN" if oversized else "PASS"
                reason = f"{rel} L{start}-L{end}"
                if oversized:
                    reason += f" (range > {MAX_RANGE_LINES} lines; cite tighter)"
                return {**result, "status": status, "reason": reason}

    if out_of_bounds:
        result["reason"] = "cited line range is outside the file (no clamping)"
        return result

    for path, rel in allowed:
        if norm(content) in norm("\n".join(read_lines(path))):
            result["reason"] = f"quote exists in {rel} but not in the cited range (line drift)"
            return result

    result["reason"] = f"quote not found in {', '.join(r for _, r in allowed)}"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify evidence quotes in review.json.")
    parser.add_argument("review", help="Path to review.json")
    parser.add_argument("--root", default=".", help="Task package root (default: .)")
    parser.add_argument("--work", default=None, help="Work directory containing run logs (default: <root>/work or <root>/../work)")
    parser.add_argument("--strict", action="store_true", help="Treat WARN as failure.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args(argv)

    review_path = Path(args.review)
    root = Path(args.root)
    data = json.loads(review_path.read_text(encoding="utf-8-sig"))
    work_dir = find_work_dir(root, args.work)

    results: list[dict] = []
    for section in ("test_review", "rubric_review"):
        for issue in data.get(section) or []:
            results.append(check_issue(root, issue, section, work_dir, args.strict))

    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    passes = [r for r in results if r["status"] == "PASS"]
    bad = fails + (warns if args.strict else [])

    if args.json:
        print(json.dumps(
            {"results": results, "pass": len(passes), "warn": len(warns), "fail": len(fails), "strict": args.strict},
            ensure_ascii=False,
            indent=2,
        ))
    else:
        for r in results:
            print(f"[{r['status']:4}] {r['id']:>4} {r['source']:<18} {r['reason']}")
        print(f"\n{len(passes)} pass, {len(warns)} warn, {len(fails)} fail"
              + (" (strict: warn counts as fail)" if args.strict else ""))

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
