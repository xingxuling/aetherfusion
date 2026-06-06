"""Directory tree builder with exclusions."""

import os
from pathlib import Path
from typing import Any

from aetherfusion.utils import IGNORE_DIRS, normalize_path_for_report


def build_tree(
    root: Path,
    max_depth: int = 4,
    max_files_per_dir: int = 30,
) -> dict[str, Any]:
    """Build a directory tree dict from a project root.

    Args:
        root: Project root path.
        max_depth: Maximum nesting depth to traverse.
        max_files_per_dir: Maximum files to record per directory before truncating.

    Returns:
        A nested dict representing the tree::
            {
                "name": "project-name",
                "type": "directory",
                "children": [...],
                "truncated": bool
            }
    """
    tree: dict[str, Any] = {
        "name": root.name or str(root),
        "type": "directory",
        "children": [],
        "truncated": False,
    }
    _walk(root, tree, current_depth=0, max_depth=max_depth, max_files=max_files_per_dir)
    return tree


def _walk(
    path: Path,
    node: dict[str, Any],
    current_depth: int,
    max_depth: int,
    max_files: int,
) -> None:
    """Recursively walk a directory, filling the tree node."""
    if current_depth >= max_depth:
        node["truncated"] = True
        return

    try:
        entries = sorted(os.listdir(path), key=lambda s: (not (path / s).is_dir(), s.lower()))
    except (PermissionError, OSError):
        return

    count = 0
    for entry in entries:
        full = path / entry

        # Skip symlinks that point outside the project
        try:
            if full.is_symlink():
                continue
        except OSError:
            continue

        if full.is_dir():
            if entry in IGNORE_DIRS or entry.startswith("."):
                continue
            child: dict[str, Any] = {
                "name": entry,
                "type": "directory",
                "children": [],
                "truncated": False,
            }
            _walk(full, child, current_depth + 1, max_depth, max_files)
            node["children"].append(child)
        else:
            if count >= max_files:
                node["truncated"] = True
                break
            node["children"].append({
                "name": entry,
                "type": "file",
            })
            count += 1


def tree_to_text(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> list[str]:
    """Render a tree dict as text lines (like the ``tree`` command)."""
    lines: list[str] = []
    connector = "└── " if is_last else "├── "
    lines.append(f"{prefix}{connector}{node['name']}{'/' if node['type'] == 'directory' else ''}")

    if node.get("truncated"):
        new_prefix = prefix + ("    " if is_last else "│   ")
        lines.append(f"{new_prefix}└── ...")

    if node["type"] == "directory" and "children" in node:
        children = node["children"]
        for i, child in enumerate(children):
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(tree_to_text(child, new_prefix, i == len(children) - 1))

    return lines