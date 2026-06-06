"""Safe rollback — deletes files created by apply using a rollback manifest.

v0.4.5: Only deletes files listed in the manifest's `created_files`.
Does NOT delete directories, source project files, or config files
that were not explicitly created by apply.
"""

import json
import os
from pathlib import Path
from typing import Any

from aetherfusion import __version__

# Config filenames that are protected from rollback deletion
PROTECTED_CONFIG_FILENAMES: set[str] = {
    "package.json", "package-lock.json", "yarn.lock",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "tsconfig.json", "jsconfig.json",
    "vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.mts",
    "next.config.js", "next.config.ts", "next.config.mjs",
    "webpack.config.js",
}


def rollback_apply(
    manifest_path: Path,
) -> dict[str, Any]:
    """Roll back files created by apply using a rollback manifest.

    Only deletes files listed in the manifest's ``created_files`` field.
    Every deletion is checked for path traversal and config protection.
    Files that no longer exist are recorded as ``already_missing``.
    A single failed deletion does not stop processing of other files.

    Args:
        manifest_path: Path to the v0.4 rollback manifest JSON.

    Returns:
        Rollback result dict with summary and per-file details.

    Raises:
        FileNotFoundError: Manifest file does not exist.
        ValueError: Manifest structure is invalid (e.g. created_files not a list).
        json.JSONDecodeError: Manifest contains invalid JSON.
    """
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Rollback manifest not found: {manifest_path}"
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest: dict[str, Any] = json.load(f)

    created_files: list[str] = manifest.get("created_files", [])
    if not isinstance(created_files, list):
        raise ValueError(
            "Manifest 'created_files' field is not a list. "
            "This does not appear to be a valid rollback manifest."
        )

    files_deleted: list[str] = []
    files_already_missing: list[dict[str, str]] = []
    files_blocked: list[dict[str, str]] = []
    files_failed: list[dict[str, str]] = []

    for file_path in created_files:
        # --- Path traversal check ---
        if ".." in str(file_path).replace("\\", "/").split("/"):
            files_blocked.append({
                "path": file_path,
                "reason": "Path traversal detected — blocked for safety.",
            })
            continue

        # --- Protected config filename check ---
        filename = os.path.basename(str(file_path))
        if filename in PROTECTED_CONFIG_FILENAMES:
            files_blocked.append({
                "path": file_path,
                "reason": (
                    f"Protected config file '{filename}' — rollback blocked. "
                ),
            })
            continue

        # --- Normalize to absolute path ---
        try:
            abs_path = str(Path(file_path).resolve())
        except (OSError, RuntimeError):
            files_blocked.append({
                "path": file_path,
                "reason": "Cannot resolve path — blocked for safety.",
            })
            continue

        # --- Check file exists ---
        if not os.path.isfile(abs_path):
            files_already_missing.append({
                "path": file_path,
                "reason": "File no longer exists on disk.",
            })
            continue

        # --- Delete file ---
        try:
            os.remove(abs_path)
            files_deleted.append(file_path)
        except OSError as e:
            files_failed.append({
                "path": file_path,
                "reason": str(e),
            })

    summary = {
        "files_deleted": len(files_deleted),
        "files_already_missing": len(files_already_missing),
        "files_blocked": len(files_blocked),
        "files_failed": len(files_failed),
    }

    next_cmd = (
        f"# Rollback complete. {summary['files_deleted']} file(s) deleted.\n"
        f"# {summary['files_already_missing']} file(s) were already missing.\n"
        f"# {summary['files_blocked']} file(s) were blocked.\n"
        f"# {summary['files_failed']} file(s) failed to delete.\n"
        f"# Manifest: {manifest_path}"
    )

    result: dict[str, Any] = {
        "rollback_version": __version__,
        "mode": "confirmed_rollback",
        "manifest_file": str(manifest_path.resolve()),
        "module_name": manifest.get("module_name", "unknown"),
        "target_match_path": manifest.get("target_match_path", ""),
        "summary": summary,
        "files_deleted": files_deleted,
        "files_already_missing": files_already_missing,
        "files_blocked": files_blocked,
        "files_failed": files_failed,
        "next_recommended_command": next_cmd,
    }

    return result