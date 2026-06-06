"""Diff reporter — generates unified diff for add_file operations.

Only generates NEW file diffs (add_file type). Never generates
overwrite diffs for conflict_same_name files.

Output is a standard unified diff format that can be read by
`patch`, `git apply`, or viewed as plain text.
"""

import datetime
import os
from pathlib import Path
from typing import Any


def generate_diff(manifest: dict[str, Any], diff_path: Path) -> None:
    """Generate a unified diff file for add_file operations.

    Args:
        manifest: Patch manifest dict from dry_run_patch_generator.
        diff_path: Output path for the .diff file.
    """
    diff_path.parent.mkdir(parents=True, exist_ok=True)

    ops = manifest.get("operations", [])
    add_ops = [op for op in ops if op.get("type") == "add_file"]

    if not add_ops:
        diff_path.write_text(
            "# AetherFusion Dry-Run Diff\n"
            "# No add_file operations to generate diffs for.\n",
            encoding="utf-8",
        )
        return

    module_name = manifest.get("module_name", "unknown")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    lines: list[str] = []
    lines.append(f"# AetherFusion Dry-Run Diff — {module_name}")
    lines.append(f"# Generated: {now}")
    lines.append(f"# Patch version: {manifest.get('patch_version', '?')}")
    lines.append(f"# Mode: dry_run — no files have been modified.")
    lines.append("")

    for op in add_ops:
        rel_path = op.get("relative_path", "?")
        source_abs = op.get("source_absolute", "")
        file_size = op.get("file_size_bytes", 0)

        # Read the source file content
        try:
            with open(source_abs, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            lines.append(f"# ERROR reading {rel_path}: {e}")
            lines.append("")
            continue

        target_path = _to_unix(rel_path)
        source_label = f"a/{target_path}"
        target_label = f"b/{target_path}"

        content_lines = content.splitlines(keepends=True)
        if content_lines and not content_lines[-1].endswith("\n"):
            content_lines[-1] += "\n"

        lines.append(f"--- /dev/null\t{now}")
        lines.append(f"+++ {target_label}\t{now}")
        lines.append(f"@@ -0,0 +1,{len(content_lines)} @@")
        for cl in content_lines:
            lines.append(f"+{cl.rstrip()}")

        lines.append("")

    diff_path.write_text("\n".join(lines), encoding="utf-8")


def _to_unix(path: str) -> str:
    """Convert a path to Unix-style separators."""
    return path.replace(os.sep, "/")