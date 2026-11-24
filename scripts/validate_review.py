#!/usr/bin/env python3
"""Validate review.json against the submission contract.

Usage:
    python validate_review.py review.json

Exit code 0 = valid, 1 = invalid. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

TOP_LEVEL = ("candidate", "submitted_at", "environment", "test_review", "rubric_review")
ENV_REQUIRED = (
    "built_from_dockerfile",
    "dockerfile_modified",
    "build_command",
    "run_command",
    "python_version",
    "test_result",
    "reward",
    "completed",
    "stopped_at",
    "problems",
)
ENV_OPTIONAL = ("notes",)

TEST_TYPES = {
    "wrong_validation",
    "missing_validation",
    "false_rejection",
    "flaky",
    "tooling_defect",
    "undefined_requirement",
}
RUBRIC_TYPES = {
    "contradicts_code",
    "rewards_wrong_behavior",
    "penalizes_correct",
    "unobservable",
    "duplicate_scoring",
    "undefined_criterion",
    "missing_criterion",
    "process_defect",
}
SOURCES = {"instruction", "test_code", "reference_solution", "run_output", "task_metadata", "rubric"}
PLACEHOLDERS = {"", "n/a", "na", "无", "-", "--", "tbd", "todo", "null", "none", "待补充"}

# In strict mode, each issue_type may only use these primary sources.
STRICT_SOURCE = {
    "wrong_validation": {"test_code", "run_output"},
    "missing_validation": {"instruction", "run_output"},
    "false_rejection": {"test_code"},
    "flaky": {"test_code", "run_output"},
    "tooling_defect": {"test_code"},
    "undefined_requirement": {"instruction"},
    "contradicts_code": {"rubric"},
    "rewards_wrong_behavior": {"rubric"},
    "penalizes_correct": {"rubric"},
    "unobservable": {"rubric"},
    "duplicate_scoring": {"rubric"},
    "undefined_criterion": {"rubric"},
    "missing_criterion": {"instruction"},
    "process_defect": {"rubric"},
}


def is_text(value) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def check_date(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_issue(issue, section: str, index: int, errors: list[str], strict: bool = False) -> None:
    prefix = f"{section}[{index}]"
    if not isinstance(issue, dict):
        errors.append(f"{prefix}: must be an object")
        return

    expected_id = ("T" if section == "test_review" else "R") + f"{index + 1:02d}"
    if issue.get("id") != expected_id:
        errors.append(f"{prefix}.id: expected {expected_id!r}, got {issue.get('id')!r}")

    location = issue.get("location")
    if not isinstance(location, dict):
        errors.append(f"{prefix}.location: must be an object")
    else:
        for key in ("file", "ref"):
            if not is_text(location.get(key)):
                errors.append(f"{prefix}.location.{key}: required non-empty string")

    allowed = TEST_TYPES if section == "test_review" else RUBRIC_TYPES
    if issue.get("issue_type") not in allowed:
        errors.append(f"{prefix}.issue_type: {issue.get('issue_type')!r} not in {sorted(allowed)}")

    for key in ("description", "impact", "suggestion"):
        if not is_text(issue.get(key)):
            errors.append(f"{prefix}.{key}: required non-empty string")

    if strict:
        for key, minimum in (("description", 20), ("impact", 20), ("suggestion", 20)):
            value = issue.get(key)
            if isinstance(value, str) and len(value.strip()) < minimum:
                errors.append(f"{prefix}.{key}: too short for strict mode ({len(value.strip())} < {minimum} chars)")

    evidence = issue.get("evidence")
    if not isinstance(evidence, dict):
        errors.append(f"{prefix}.evidence: must be an object")
        return
    if evidence.get("source") not in SOURCES:
        errors.append(f"{prefix}.evidence.source: {evidence.get('source')!r} not in {sorted(SOURCES)}")
    for key in ("where", "content", "reasoning"):
        if not is_text(evidence.get(key)):
            errors.append(f"{prefix}.evidence.{key}: required non-empty string")

    if strict:
        issue_type = issue.get("issue_type")
        source = evidence.get("source")
        allowed_sources = STRICT_SOURCE.get(issue_type)
        if allowed_sources and source not in allowed_sources:
            errors.append(
                f"{prefix}.evidence.source: {source!r} cannot support {issue_type!r}; "
                f"use one of {sorted(allowed_sources)}"
            )
        where = evidence.get("where") or ""
        if source in {"instruction", "test_code", "reference_solution", "task_metadata", "rubric"}:
            if not re.search(r"(?:L\d+|:\d+)", where):
                errors.append(f"{prefix}.evidence.where: strict mode requires a line reference (Lx or :x)")
        location_file = (location or {}).get("file", "") if isinstance(location, dict) else ""
        if location_file and "/" not in location_file and "\\" not in location_file and "." not in location_file:
            errors.append(f"{prefix}.location.file: expected a package-relative path, got {location_file!r}")


def validate(data, errors: list[str], strict: bool = False) -> None:
    if not isinstance(data, dict):
        errors.append("$: top level must be an object")
        return

    for key in TOP_LEVEL:
        if key not in data:
            errors.append(f"$: missing required key {key!r}")

    if not is_text(data.get("candidate")):
        errors.append("$.candidate: required non-empty string")
    if not check_date(data.get("submitted_at")):
        errors.append("$.submitted_at: must be a valid YYYY-MM-DD date")

    env = data.get("environment")
    if not isinstance(env, dict):
        errors.append("$.environment: must be an object")
    else:
        for key in ENV_REQUIRED:
            if key not in env:
                errors.append(f"$.environment: missing required key {key!r}")
        for key in ("built_from_dockerfile", "dockerfile_modified", "completed"):
            if key in env and not isinstance(env[key], bool):
                errors.append(f"$.environment.{key}: must be boolean")
        for key in ("build_command", "run_command"):
            if not is_text(env.get(key)):
                errors.append(f"$.environment.{key}: required non-empty string")
        for key in ("python_version", "test_result", "reward", "stopped_at"):
            value = env.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(f"$.environment.{key}: must be string or null")
        if env.get("reward") not in (None, "0", "1"):
            errors.append("$.environment.reward: must be '0', '1', or null")
        if env.get("completed") is False and not is_text(env.get("stopped_at")):
            errors.append("$.environment.stopped_at: required when completed is false")
        if env.get("completed") is True and env.get("stopped_at") is not None:
            errors.append("$.environment.stopped_at: must be null when completed is true")
        if env.get("built_from_dockerfile") is True and env.get("stopped_at") == "docker build":
            errors.append("$.environment: built_from_dockerfile=true contradicts stopped_at='docker build'")
        if env.get("completed") is True:
            if env.get("reward") not in ("0", "1"):
                errors.append("$.environment.reward: must be '0' or '1' when completed is true")
            if not is_text(env.get("test_result")):
                errors.append("$.environment.test_result: required when completed is true")
        if env.get("completed") is False:
            if strict and env.get("reward") is not None:
                errors.append("$.environment.reward: must be null when completed is false (strict)")
            if strict and env.get("test_result") is not None:
                errors.append("$.environment.test_result: must be null when completed is false (strict)")
        problems = env.get("problems")
        if not isinstance(problems, list):
            errors.append("$.environment.problems: must be an array")
        else:
            for i, problem in enumerate(problems):
                if not isinstance(problem, dict):
                    errors.append(f"$.environment.problems[{i}]: must be an object")
                    continue
                for key in ("step", "symptom"):
                    if not is_text(problem.get(key)):
                        errors.append(f"$.environment.problems[{i}].{key}: required non-empty string")
                resolution = problem.get("resolution")
                if resolution is not None and not isinstance(resolution, str):
                    errors.append(f"$.environment.problems[{i}].resolution: must be string or null")
            if env.get("completed") is False and not problems and strict:
                errors.append("$.environment.problems: must be non-empty when completed is false (strict)")
        notes = env.get("notes")
        if notes is not None and not isinstance(notes, str):
            errors.append("$.environment.notes: must be string or null")

    for section in ("test_review", "rubric_review"):
        issues = data.get(section)
        if not isinstance(issues, list):
            errors.append(f"$.{section}: must be an array")
            continue
        for i, issue in enumerate(issues):
            validate_issue(issue, section, i, errors, strict=strict)
        if strict and section == "test_review" and not issues:
            errors.append("$.test_review: strict mode requires at least one issue")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate review.json shape and enums.")
    parser.add_argument("review", help="Path to review.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    parser.add_argument("--strict", action="store_true", help="Also check type/source pairs, line refs, and non-empty arrays.")
    args = parser.parse_args(argv)

    try:
        data = json.loads(open(args.review, encoding="utf-8-sig").read())
    except (OSError, json.JSONDecodeError) as exc:
        errors = [f"$: cannot parse JSON: {exc}"]
    else:
        errors = []
        validate(data, errors, strict=args.strict)

    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        if errors:
            print(f"INVALID: {len(errors)} error(s){' (strict)' if args.strict else ''}")
            for err in errors:
                print(f"  - {err}")
        else:
            print("VALID" + (" (strict)" if args.strict else ""))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
