"""Git status checker — read-only, never modifies the repository."""

import os
import subprocess
from pathlib import Path

GIT_STATUS_VALUES = ("clean", "dirty", "not_git_repo", "error")


def check_git_status(project_path: Path) -> dict:
    """Check the Git status for a project directory.

    Reads the repository state without making any changes.
    Handles subprocess errors gracefully.

    Returns:
        dict with keys:
        - status: "clean" | "dirty" | "not_git_repo" | "error"
        - branch: current branch name or None
        - changed_files: list of changed files (dirty only) or empty
        - error_message: str or None
    """
    result: dict = {
        "status": "not_git_repo",
        "branch": None,
        "changed_files": [],
        "error_message": None,
    }

    git_dir = project_path / ".git"
    if not git_dir.exists():
        return result

    # Detect current branch
    branch = _run_git_command(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch is None:
        result["status"] = "error"
        result["error_message"] = "Failed to detect branch"
        return result
    result["branch"] = branch

    # Check for uncommitted changes (staged + unstaged)
    status_output = _run_git_command(project_path, ["status", "--porcelain"])
    if status_output is None:
        result["status"] = "error"
        result["error_message"] = "Failed to read git status"
        return result

    changed = [line.strip() for line in status_output.splitlines() if line.strip()]
    result["changed_files"] = changed
    result["status"] = "clean" if not changed else "dirty"

    return result


def _run_git_command(project_path: Path, args: list[str]) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None