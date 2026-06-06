"""Audit logger — appends JSONL events for apply/rollback operations.

Writes one JSON line per event to a configurable JSONL file.
Audit write failures must not destroy the main workflow.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def log_audit_event(
    audit_path: str | Path,
    event: dict[str, Any],
) -> bool:
    """Append a single JSONL audit event to the audit log file.

    Creates parent directories if they don't exist.
    Does NOT raise — returns False on failure so the main workflow
    is never interrupted by audit failures.

    Args:
        audit_path: Path to the JSONL audit log file.
        event: Event dict to serialize as a single JSON line.

    Returns:
        True on success, False on failure (OSError).
    """
    try:
        ap = Path(audit_path)
        ap.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with open(ap, "a", encoding="utf-8") as fh:
            fh.write(line)
        return True
    except OSError:
        return False


def make_apply_event(
    result: dict[str, Any],
    manifest_path: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed apply operation.

    Args:
        result: Apply result dict from safe_apply.apply_patch.
        manifest_path: Path to the patch manifest that was applied.
        result_json_path: Path where apply result JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    summary = result.get("summary", {})
    return {
        "event_type": "apply",
        "version": result.get("apply_version", "?"),
        "timestamp": _now_iso(),
        "input_file": manifest_path,
        "summary": summary,
        "result_json_path": result_json_path,
        "backup_or_manifest_path": result.get("rollback_manifest_path", ""),
    }


def make_rollback_event(
    result: dict[str, Any],
    manifest_path: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed rollback operation.

    Args:
        result: Rollback result dict from safe_rollback.rollback_apply.
        manifest_path: Path to the rollback manifest used.
        result_json_path: Path where rollback result JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    return {
        "event_type": "rollback",
        "version": result.get("rollback_version", "?"),
        "timestamp": _now_iso(),
        "input_file": manifest_path,
        "summary": result.get("summary", {}),
        "result_json_path": result_json_path,
        "backup_or_manifest_path": manifest_path,
    }


def make_verify_event(
    result: dict[str, Any],
    target_path: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed verify operation.

    Args:
        result: Verify result dict from verify_runner.run_verify.
        target_path: Path to the target project that was verified.
        result_json_path: Path where verify result JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    return {
        "event_type": "verify",
        "version": result.get("verify_version", "?"),
        "timestamp": _now_iso(),
        "input_file": target_path,
        "summary": result.get("summary", {}),
        "result_json_path": result_json_path,
        "backup_or_manifest_path": target_path,
    }


def make_repair_plan_event(
    plan: dict[str, Any],
    verify_file: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed repair-plan operation.

    Args:
        plan: Repair plan dict from repair_planner.generate_repair_plan.
        verify_file: Path to the verify result JSON that was analysed.
        result_json_path: Path where repair plan JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    return {
        "event_type": "repair_plan",
        "version": plan.get("repair_plan_version", "?"),
        "timestamp": _now_iso(),
        "input_file": verify_file,
        "summary": plan.get("summary", {}),
        "result_json_path": result_json_path,
        "backup_or_manifest_path": verify_file,
    }


def make_import_fix_plan_event(
    plan: dict[str, Any],
    repair_file: str,
    target_path: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed import-fix-plan operation.

    Args:
        plan: Import fix plan dict from import_fix_planner.
        repair_file: Path to the repair-plan JSON that was analysed.
        target_path: Path to the target project.
        result_json_path: Path where import fix plan JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    return {
        "event_type": "import_fix_plan",
        "version": plan.get("import_fix_plan_version", "?"),
        "timestamp": _now_iso(),
        "input_file": repair_file,
        "summary": plan.get("summary", {}),
        "result_json_path": result_json_path,
        "backup_or_manifest_path": target_path,
    }


def make_dependency_plan_event(
    plan: dict[str, Any],
    repair_file: str,
    target_path: str,
    source_path: str,
    result_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed dependency-plan operation.

    Args:
        plan: Dependency plan dict from dependency_planner.
        repair_file: Path to the repair-plan JSON that was analysed.
        target_path: Path to the target project.
        source_path: Path to the source project.
        result_json_path: Path where dependency plan JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    return {
        "event_type": "dependency_plan",
        "version": plan.get("dependency_plan_version", "?"),
        "timestamp": _now_iso(),
        "input_file": repair_file,
        "summary": plan.get("summary", {}),
        "result_json_path": result_json_path,
        "backup_or_manifest_path": target_path,
    }


def make_fusion_session_event(
    session_id: str,
    source_path: str,
    target_path: str,
    modules: list[str],
    summary: dict[str, Any],
    session_json_path: str = "",
) -> dict[str, Any]:
    """Build an audit event for a completed fusion-session operation.

    Args:
        session_id: Unique session identifier.
        source_path: Path to the source project.
        target_path: Path to the target project.
        modules: List of module names processed.
        summary: Session summary dict (total_modules, failed_modules etc.).
        session_json_path: Path where the session JSON was written (may be empty).

    Returns:
        Audit event dict.
    """
    from aetherfusion import __version__

    return {
        "event_type": "fusion_session",
        "version": __version__,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "source_path": source_path,
        "target_path": target_path,
        "modules": modules,
        "summary": summary,
        "session_json_path": session_json_path,
    }