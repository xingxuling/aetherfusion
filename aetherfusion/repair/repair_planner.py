"""Repair planner for v0.6.

Reads a v0.5 verify result JSON and generates a repair plan.
v0.6 is read-only — no files are modified, no dependencies installed,
no imports fixed, no configs changed.
"""

import json
import re
from pathlib import Path
from typing import Any

from aetherfusion.repair.error_classifier import (
    classify_error,
    ERROR_TYPE_MISSING_IMPORT,
    ERROR_TYPE_MISSING_DEPENDENCY,
    ERROR_TYPE_TYPE_ERROR,
    ERROR_TYPE_SYNTAX_ERROR,
    ERROR_TYPE_TEST_FAILURE,
    ERROR_TYPE_CONFIG_ERROR,
    ERROR_TYPE_COMMAND_NOT_FOUND,
    ERROR_TYPE_TIMEOUT,
    ERROR_TYPE_UNKNOWN_ERROR,
)

REPAIR_PLAN_VERSION = "0.6.0"

# Severity mappings
_SEVERITY_MAP = {
    ERROR_TYPE_SYNTAX_ERROR: "high",
    ERROR_TYPE_MISSING_IMPORT: "high",
    ERROR_TYPE_MISSING_DEPENDENCY: "high",
    ERROR_TYPE_TYPE_ERROR: "medium",
    ERROR_TYPE_CONFIG_ERROR: "medium",
    ERROR_TYPE_TEST_FAILURE: "medium",
    ERROR_TYPE_COMMAND_NOT_FOUND: "low",
    ERROR_TYPE_TIMEOUT: "low",
    ERROR_TYPE_UNKNOWN_ERROR: "medium",
}

# Risk level mappings
_RISK_MAP = {
    ERROR_TYPE_SYNTAX_ERROR: "medium",
    ERROR_TYPE_MISSING_IMPORT: "medium",
    ERROR_TYPE_MISSING_DEPENDENCY: "medium",
    ERROR_TYPE_TYPE_ERROR: "low",
    ERROR_TYPE_CONFIG_ERROR: "medium",
    ERROR_TYPE_TEST_FAILURE: "low",
    ERROR_TYPE_COMMAND_NOT_FOUND: "low",
    ERROR_TYPE_TIMEOUT: "low",
    ERROR_TYPE_UNKNOWN_ERROR: "medium",
}

# Confidence mappings (how confident we are in this classification)
_CONFIDENCE_MAP = {
    ERROR_TYPE_MISSING_IMPORT: 85,
    ERROR_TYPE_MISSING_DEPENDENCY: 80,
    ERROR_TYPE_TYPE_ERROR: 90,
    ERROR_TYPE_SYNTAX_ERROR: 95,
    ERROR_TYPE_TEST_FAILURE: 60,
    ERROR_TYPE_CONFIG_ERROR: 70,
    ERROR_TYPE_COMMAND_NOT_FOUND: 95,
    ERROR_TYPE_TIMEOUT: 90,
    ERROR_TYPE_UNKNOWN_ERROR: 10,
}

# Automation eligibility mappings
_AUTOMATION_MAP = {
    ERROR_TYPE_MISSING_IMPORT: "plan_only",
    ERROR_TYPE_MISSING_DEPENDENCY: "plan_only",
    ERROR_TYPE_TYPE_ERROR: "manual_only",
    ERROR_TYPE_SYNTAX_ERROR: "safe_auto_candidate",
    ERROR_TYPE_TEST_FAILURE: "manual_only",
    ERROR_TYPE_CONFIG_ERROR: "plan_only",
    ERROR_TYPE_COMMAND_NOT_FOUND: "manual_only",
    ERROR_TYPE_TIMEOUT: "plan_only",
    ERROR_TYPE_UNKNOWN_ERROR: "manual_only",
}

# Recommendation text for each error type
_RECOMMENDATIONS = {
    ERROR_TYPE_MISSING_IMPORT:
        "Check import paths. Verify that the target file was successfully "
        "applied by 'aetherfusion apply'. Consider namespace refactoring "
        "or adding missing source files to the patch manifest.",
    ERROR_TYPE_MISSING_DEPENDENCY:
        "Generate a dependency-plan to identify missing packages. "
        "v0.6 does NOT install dependencies — manual review required. "
        "Check package.json / requirements.txt / pyproject.toml for "
        "missing entries.",
    ERROR_TYPE_TYPE_ERROR:
        "Manual type fix required. Inspect the type mismatch in the "
        "source code. Consider running 'npx tsc --noEmit' for detailed "
        "type error locations. v0.6 does not auto-fix types.",
    ERROR_TYPE_SYNTAX_ERROR:
        "Low-risk auto-fix candidate for future versions. Inspect the "
        "source file at the reported line. Common causes: missing "
        "bracket, unclosed string, unexpected token. v0.6 does not "
        "auto-fix syntax.",
    ERROR_TYPE_TEST_FAILURE:
        "Manual investigation required. Review test output for "
        "AssertionError details. This is likely a logic issue in the "
        "fused code, not a structural problem. Manual-only.",
    ERROR_TYPE_CONFIG_ERROR:
        "Generate a config-plan to identify missing or misconfigured "
        "config files. Check tsconfig.json, package.json, pytest.ini, "
        "pyproject.toml for correctness. v0.6 does not auto-modify "
        "config files.",
    ERROR_TYPE_COMMAND_NOT_FOUND:
        "The specified verification command is not available on this "
        "system. Check that the required tool (npm, npx, pytest) is "
        "installed and on PATH. Manual-only.",
    ERROR_TYPE_TIMEOUT:
        "Command exceeded the 120-second timeout. Consider narrowing "
        "the command scope (e.g., run a specific test file instead of "
        "the full suite) or increasing the timeout. v0.6 does not "
        "auto-rerun timed-out commands.",
    ERROR_TYPE_UNKNOWN_ERROR:
        "Unclassified error. Review the full stderr/stdout output "
        "manually. Consider running the command directly to reproduce "
        "the issue.",
}


def _extract_suspected_files(stderr: str, stdout: str) -> list[str]:
    """Extract file paths from error output using common patterns."""
    files: list[str] = []
    combined = f"{stderr}\n{stdout}"

    # Python-style traceback: File "path", line N
    for m in re.finditer(r'File\s+"([^"]+)"', combined):
        files.append(m.group(1))

    # TypeScript-style: src/file.ts(10,5)
    for m in re.finditer(r'([^\s()]+\.(ts|tsx|js|jsx))\s*\(\d+', combined):
        f = m.group(1)
        if f not in files:
            files.append(f)

    # Webpack-style: ./src/file.ts
    for m in re.finditer(r'\./[^\s:]+\.(ts|tsx|js|jsx|py)', combined):
        f = m.group(0)
        if f not in files:
            files.append(f)

    return files[:10]  # limit


def _build_blocked_actions() -> list[str]:
    """Return the standard v0.6 blocked actions list."""
    return [
        "Do NOT modify source or target project files.",
        "Do NOT auto-fix import statements.",
        "Do NOT auto-install dependencies (npm install / pip install).",
        "Do NOT auto-modify config files (package.json / tsconfig.json / pytest.ini / pyproject.toml).",
        "Do NOT execute build / test / lint / typecheck commands.",
        "Do NOT call the network or download packages.",
        "Do NOT auto-apply any file changes.",
        "This is a read-only repair plan. All actions require human review.",
    ]


def generate_repair_plan(
    verify_path: Path,
    source_verify_file_override: str = "",
) -> dict[str, Any]:
    """Generate a repair plan from a v0.5 verify result JSON.

    Args:
        verify_path: Path to the v0.5 verify result JSON.
        source_verify_file_override: Optional override for the
            source_verify_file field (used in tests).

    Returns:
        Repair plan dict.

    Raises:
        FileNotFoundError: If verify_path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If required fields are missing.
    """
    verify_path = Path(verify_path)
    if not verify_path.is_file():
        raise FileNotFoundError(f"Verify result file not found: {verify_path}")

    with open(verify_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("Verify result must be a JSON object")

    results = data.get("results", [])
    if not isinstance(results, list):
        results = []

    # Only classify non-passed results
    non_passed = [r for r in results if r.get("status") != "passed"]

    # Build repair items
    repair_items: list[dict[str, Any]] = []
    for r in non_passed:
        error_type = classify_error(r)
        repair_items.append({
            "error_type": error_type,
            "command": r.get("command", "?"),
            "severity": _SEVERITY_MAP.get(error_type, "medium"),
            "confidence": _CONFIDENCE_MAP.get(error_type, 10),
            "suspected_files": _extract_suspected_files(
                r.get("stderr_tail", ""),
                r.get("stdout_tail", ""),
            ),
            "evidence": (
                r.get("stderr_tail", "")[:500]
                or r.get("stdout_tail", "")[:500]
                or r.get("reason", "")
            ),
            "recommended_action": _RECOMMENDATIONS.get(
                error_type, _RECOMMENDATIONS[ERROR_TYPE_UNKNOWN_ERROR]
            ),
            "automation_eligibility": _AUTOMATION_MAP.get(
                error_type, "manual_only"
            ),
            "risk_level": _RISK_MAP.get(error_type, "medium"),
            "reason": r.get("reason", ""),
        })

    # Count by classification
    classified: dict[str, int] = {}
    for item in repair_items:
        et = item["error_type"]
        classified[et] = classified.get(et, 0) + 1

    # Count by automation eligibility
    manual_only = sum(1 for i in repair_items if i["automation_eligibility"] == "manual_only")
    plan_only = sum(1 for i in repair_items if i["automation_eligibility"] == "plan_only")
    safe_auto = sum(1 for i in repair_items if i["automation_eligibility"] == "safe_auto_candidate")

    return {
        "repair_plan_version": REPAIR_PLAN_VERSION,
        "source_verify_file": source_verify_file_override or str(verify_path.resolve()),
        "summary": {
            "total_failed": len(non_passed),
            "classified_count": len(repair_items),
            "unclassified_count": len(non_passed) - len(repair_items),
            "repair_items_count": len(repair_items),
            "manual_only": manual_only,
            "plan_only": plan_only,
            "safe_auto_candidate": safe_auto,
        },
        "failed_commands": [r.get("command", "?") for r in non_passed],
        "classified_errors": classified,
        "repair_items": repair_items,
        "blocked_actions": _build_blocked_actions(),
        "next_recommended_command": (
            "python -m aetherfusion verify --target <project> --json verify.json && "
            "python -m aetherfusion repair-plan --verify verify.json --json repair-plan.json"
        ),
    }