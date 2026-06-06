"""Verify runner — orchestrates command detection + safe execution for a
target project, and builds the unified verify result dict.
"""

from pathlib import Path
from typing import Any

from aetherfusion.verifier.command_detector import detect_commands
from aetherfusion.verifier.safe_runner import run_commands
from aetherfusion import __version__


def run_verify(
    target_path: Path,
    commands: list[str] | None = None,
) -> dict[str, Any]:
    """Detect and run safe verification commands on a target project.

    Args:
        target_path: Root directory of the target project.
        commands: Optional explicit command list to override detection.
                  If None or empty, commands are auto-detected.

    Returns:
        Verify result dict with keys:
        - verify_version
        - target_path
        - detected_stack
        - commands_detected
        - commands_run
        - summary
        - results
        - failed_commands
        - skipped_commands
        - next_recommended_command

    Raises:
        FileNotFoundError: target_path is not a directory.
        ValueError: target_path does not exist.
    """
    target = target_path.resolve()

    if not target.exists():
        raise ValueError(f"Target path does not exist: {target}")
    if not target.is_dir():
        raise FileNotFoundError(f"Target path is not a directory: {target}")

    # Detect or use provided commands
    if commands:
        cmds = [c.strip() for c in commands if c.strip()]
        detected_stack: list[str] = []
        no_cmds = len(cmds) == 0
    else:
        cmds, detected_stack, no_cmds = detect_commands(target)

    # Run all detected/provided commands
    results = run_commands(cmds, target)

    if no_cmds:
        detected_stack = []

    # Build summary
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "blocked": sum(1 for r in results if r["status"] == "blocked"),
    }

    # Collect failed / skipped commands
    failed_cmds = [r["command"] for r in results if r["status"] == "failed"]
    skipped_cmds = [r["command"] for r in results if r["status"] == "skipped"]

    # Next recommended command
    if no_cmds:
        next_cmd = "No commands detected. Provide --commands or add build/test scripts to the project."
    elif summary["failed"] > 0:
        next_cmd = "python -m aetherfusion verify --target <target> --commands \"<fix commands>\""
    elif summary["passed"] == summary["total"]:
        next_cmd = "All verify commands passed. The project is ready for fusion."
    else:
        next_cmd = "python -m aetherfusion verify --target <target>"

    return {
        "verify_version": __version__,
        "target_path": str(target),
        "detected_stack": detected_stack,
        "commands_detected": cmds if not commands else [],
        "commands_run": cmds,
        "summary": summary,
        "results": results,
        "failed_commands": failed_cmds,
        "skipped_commands": skipped_cmds,
        "next_recommended_command": next_cmd,
    }