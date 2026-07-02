"""Safe apply — executes only add_file operations from a v0.3 patch manifest.

v0.4: confirmed apply only. Only copies source-only files to target.
Does NOT overwrite, does NOT resolve conflicts, does NOT modify config files.
Generates a rollback manifest for manual undo.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from aetherfusion import __version__
from aetherfusion.utils import IGNORE_DIRS

# Maximum file size for safe apply (same as patch generator)
MAX_FILE_SIZE_BYTES: int = 1_048_576  # 1 MB
MAX_VERIFIED_ASSET_SIZE_BYTES: int = 67_108_864  # 64 MB


def apply_patch(
    patch_path: Path,
    backup_path: Path | None = None,
) -> dict[str, Any]:
    """Apply only add_file operations from a patch manifest.

    Reads a v0.3 patch manifest JSON and copies source-only files that
    have no counterpart in the target directory. All other operations
    (conflict_same_name, skip_unsafe, etc.) are blocked/skipped.
    """
    if not patch_path.is_file():
        raise FileNotFoundError(f"Patch manifest not found: {patch_path}")

    with open(patch_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    module_name = manifest.get("module_name", "unknown")
    source_module_path = _safe_resolve(manifest.get("source_module_path"))
    target_match_path = _safe_resolve(manifest.get("target_match_path"))
    operations = manifest.get("operations", [])

    if not target_match_path:
        raise ValueError(
            f"target_match_path is missing or invalid in the patch manifest for '{module_name}'."
        )

    created_target_dir = False
    if not os.path.isdir(target_match_path):
        os.makedirs(target_match_path, exist_ok=True)
        created_target_dir = True

    result_ops: list[dict[str, Any]] = []
    applied_files: list[str] = []
    skipped_files: list[dict[str, str]] = []
    blocked_files: list[dict[str, str]] = []
    failed_files: list[dict[str, str]] = []
    created_dirs: list[str] = []

    if created_target_dir:
        created_dirs.append(target_match_path)

    for op in operations:
        op_type = op.get("type")
        rel_path = op.get("relative_path", "?")
        source_absolute = op.get("source_absolute", "")

        if op_type not in {"add_file", "add_asset"}:
            blocked_files.append({
                "relative_path": rel_path,
                "reason": f"Operation type '{op_type}' is not supported — only add_file/add_asset are allowed.",
            })
            _record_result(result_ops, op, "blocked", f"Unsupported operation type: {op_type}")
            continue
        is_verified_asset = op_type == "add_asset"

        if not source_absolute or not os.path.isfile(source_absolute):
            skipped_files.append({
                "relative_path": rel_path,
                "reason": "Source file does not exist or is inaccessible.",
            })
            _record_result(result_ops, op, "skipped", "Source file does not exist")
            continue

        if os.path.islink(source_absolute):
            blocked_files.append({
                "relative_path": rel_path,
                "reason": "Symbolic-link sources are not allowed.",
            })
            _record_result(result_ops, op, "blocked", "Symbolic-link source")
            continue

        if source_module_path and not _is_path_within(source_absolute, source_module_path):
            blocked_files.append({
                "relative_path": rel_path,
                "reason": "Source file resolves outside source_module_path.",
            })
            _record_result(result_ops, op, "blocked", "Source-root escape detected")
            continue

        normalized_rel = rel_path.replace("\\", "/")
        if (
            not rel_path
            or os.path.isabs(rel_path)
            or normalized_rel.startswith("/")
            or ".." in normalized_rel.split("/")
        ):
            blocked_files.append({
                "relative_path": rel_path,
                "reason": "Path traversal detected — unsafe path.",
            })
            _record_result(result_ops, op, "blocked", "Path traversal detected")
            continue

        try:
            actual_size = os.path.getsize(source_absolute)
        except OSError:
            actual_size = -1

        if actual_size < 0:
            skipped_files.append({
                "relative_path": rel_path,
                "reason": "Cannot stat source file — read error.",
            })
            _record_result(result_ops, op, "skipped", "Cannot stat source file")
            continue

        max_size = MAX_VERIFIED_ASSET_SIZE_BYTES if is_verified_asset else MAX_FILE_SIZE_BYTES
        if actual_size > max_size:
            blocked_files.append({
                "relative_path": rel_path,
                "reason": f"File is too large for the allowed limit ({actual_size / 1_048_576:.1f} MB).",
            })
            _record_result(result_ops, op, "blocked", f"File too large: {actual_size} bytes")
            continue

        if is_verified_asset:
            expected_sha256 = str(op.get("sha256", "")).lower()
            actual_sha256 = _sha256_file(source_absolute)
            if not op.get("asset_verified") or expected_sha256 != actual_sha256:
                blocked_files.append({
                    "relative_path": rel_path,
                    "reason": "Verified asset SHA-256 is missing or does not match.",
                })
                _record_result(result_ops, op, "blocked", "Asset integrity check failed")
                continue
        elif _is_binary(source_absolute):
            skipped_files.append({
                "relative_path": rel_path,
                "reason": "Binary file — automatic apply skipped.",
            })
            _record_result(result_ops, op, "skipped", "Binary file")
            continue

        target_file = os.path.realpath(os.path.join(target_match_path, rel_path))
        if not _is_path_within(target_file, target_match_path):
            blocked_files.append({
                "relative_path": rel_path,
                "reason": "Target path resolves outside target_match_path.",
            })
            _record_result(result_ops, op, "blocked", "Target-root escape detected")
            continue
        if os.path.exists(target_file):
            blocked_files.append({
                "relative_path": rel_path,
                "reason": "Target file already exists — will not overwrite.",
            })
            _record_result(result_ops, op, "blocked", "Target file already exists")
            continue

        if _is_in_ignored_dir(rel_path):
            skipped_files.append({
                "relative_path": rel_path,
                "reason": "File is inside a directory excluded from fusion (node_modules, .git, etc.).",
            })
            _record_result(result_ops, op, "skipped", "Inside ignored directory")
            continue

        try:
            target_parent = os.path.dirname(target_file)
            if not os.path.isdir(target_parent):
                os.makedirs(target_parent, exist_ok=True)
                created_dirs.append(target_parent)

            shutil.copy2(source_absolute, target_file)
            applied_files.append(rel_path)
            _record_result(result_ops, op, "applied", f"Copied successfully ({actual_size} bytes)")
        except OSError as e:
            failed_files.append({"relative_path": rel_path, "reason": str(e)})
            _record_result(result_ops, op, "failed", str(e))

    summary = {
        "files_applied": len(applied_files),
        "files_skipped": len(skipped_files),
        "files_blocked": len(blocked_files),
        "files_failed": len(failed_files),
        "directories_created": len(created_dirs),
    }

    rollback: dict[str, Any] = {
        "rollback_version": __version__,
        "applied_at_timestamp": _now_iso(),
        "module_name": module_name,
        "target_match_path": target_match_path,
        "created_files": [os.path.join(target_match_path, rel) for rel in applied_files],
        "created_directories": created_dirs,
        "skipped_files": skipped_files,
        "blocked_files": blocked_files,
        "failed_files": failed_files,
        "rollback_actions": [
            {
                "action": "delete",
                "path": os.path.join(target_match_path, rel),
                "description": f"Remove file added during apply: {rel}",
            }
            for rel in applied_files
        ],
        "rollback_command_hint": (
            "To manually roll back: delete each file listed in 'rollback_actions'.\n"
            "The created directories (empty ones) can also be removed if no other "
            "files were placed there.\n"
            "If implemented: `python -m aetherfusion rollback "
            f"--manifest <backup_path> --confirm`"
        ),
    }

    rollback_path = None
    if backup_path is not None:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(rollback, f, indent=2, ensure_ascii=False)
        rollback_path = str(backup_path.resolve())

    return {
        "apply_version": __version__,
        "mode": "confirmed_apply",
        "patch_file": str(patch_path.resolve()),
        "module_name": module_name,
        "source_module_path": manifest.get("source_module_path", ""),
        "target_match_path": target_match_path,
        "summary": summary,
        "operations_applied": [
            {"relative_path": rel, "target_absolute": os.path.join(target_match_path, rel)}
            for rel in applied_files
        ],
        "operations_skipped": skipped_files,
        "operations_blocked": blocked_files,
        "operations_failed": failed_files,
        "rollback_manifest_path": rollback_path,
        "next_recommended_command": (
            f"# Review the applied files in: {target_match_path}\n"
            f"# Rollback manifest (if generated): {rollback_path}\n"
            "# To undo: delete the files listed in the rollback manifest."
        ),
    }


def _safe_resolve(path: str | None) -> str | None:
    """Resolve a path safely. Returns None for empty/invalid paths."""
    if not path:
        return None
    try:
        return str(Path(path).resolve())
    except (OSError, RuntimeError):
        return None


def _is_path_within(path: str, root: str) -> bool:
    """Return True only when resolved *path* is contained by resolved *root*."""
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except (OSError, ValueError):
        return False


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_binary(file_path: str) -> bool:
    """Check if a file is binary by scanning for null bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _is_in_ignored_dir(rel_path: str) -> bool:
    """Check if the relative path traverses into an ignored directory."""
    parts = rel_path.replace("\\", "/").split("/")
    return any(part in IGNORE_DIRS for part in parts)


def _record_result(
    ops: list[dict[str, Any]],
    op: dict[str, Any],
    status: str,
    detail: str,
) -> None:
    """Record an operation result."""
    ops.append({
        "type": op.get("type"),
        "relative_path": op.get("relative_path", "?"),
        "source_absolute": op.get("source_absolute", ""),
        "status": status,
        "detail": detail,
    })


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
