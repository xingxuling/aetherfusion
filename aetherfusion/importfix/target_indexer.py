"""Target indexer — builds a read-only file index of the target project.

Scans the target directory, ignoring build artifacts and dependency
directories, and creates an index of all source files for import
resolution analysis.

Read-only — never modifies the target project.
"""

import os
from pathlib import Path
from typing import Any

# Directories to skip entirely
_IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".next", ".nuxt", "out", "target",  # common build dirs
    ".venv", "venv", ".env", "env",     # virtualenvs
}

# Maximum file size for indexing (1 MB)
_MAX_FILE_SIZE = 1_048_576  # bytes

# Binary file extensions to skip
_BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".o", ".obj",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ttf", ".otf", ".woff", ".woff2",
    ".pyc", ".pyo", ".class",
    ".lock",  # skip lock files (often huge JSON)
}


def _is_binary_by_extension(file_path: Path) -> bool:
    """Check if a file is binary based on its extension."""
    ext = file_path.suffix.lower()
    if ext in _BINARY_EXTENSIONS:
        return True
    # Also treat files with no extension as potential binary
    return False


def _readable_text(file_path: Path) -> bool:
    """Quick check: try to read the first 1024 bytes as UTF-8 to
    detect binary content. Returns True if the file appears to be text."""
    try:
        with open(file_path, "rb") as fh:
            chunk = fh.read(1024)
        # Check for null bytes (strong binary signal)
        if b"\x00" in chunk:
            return False
        # Try to decode
        chunk.decode("utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        return False


def index_target(target_path: Path) -> dict[str, Any]:
    """Build a file index for the target project.

    Returns a dict with:
        target_path: str
        indexed_files: list of dicts with:
            filename, stem, relative_path, extension, directory, size
        by_name: dict mapping filename -> list of matches
        by_stem: dict mapping stem -> list of matches
        by_dir: dict mapping directory -> list of files

    Args:
        target_path: Absolute path to the target project root.

    Returns:
        Index dict.

    Raises:
        FileNotFoundError: If target_path does not exist.
        NotADirectoryError: If target_path is not a directory.
    """
    target_path = Path(target_path).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_path}")

    indexed: list[dict[str, Any]] = []
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_stem: dict[str, list[dict[str, Any]]] = {}
    by_dir: dict[str, list[dict[str, Any]]] = {}

    for root, dirs, files in os.walk(str(target_path)):
        # Filter ignored directories in-place
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]

        for fname in files:
            full_path = Path(root) / fname
            rel = full_path.relative_to(target_path)

            # Skip binary by extension
            if _is_binary_by_extension(full_path):
                continue

            # Skip size limit
            try:
                size = full_path.stat().st_size
            except OSError:
                continue
            if size > _MAX_FILE_SIZE:
                continue

            # Skip binary by content
            if not _readable_text(full_path):
                continue

            stem = full_path.stem
            parent_dir = (
                str(rel.parent).replace("\\", "/")
                if str(rel.parent) != "."
                else "."
            )

            entry = {
                "filename": fname,
                "stem": stem,
                "relative_path": str(rel).replace("\\", "/"),
                "extension": full_path.suffix.lower(),
                "directory": parent_dir,
                "size": size,
            }
            indexed.append(entry)

            # Index by filename
            by_name.setdefault(fname, []).append(entry)

            # Index by stem
            by_stem.setdefault(stem, []).append(entry)

            # Index by directory
            by_dir.setdefault(parent_dir, []).append(entry)

    return {
        "target_path": str(target_path),
        "indexed_files": indexed,
        "by_name": by_name,
        "by_stem": by_stem,
        "by_dir": by_dir,
    }