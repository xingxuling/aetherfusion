"""Dry-run patch generator — walks source module and classifies files for fusion.

Reads a v0.2 fusion plan JSON, inspects the source module directory and
target match directory, then produces a patch manifest where every
operation is classified as add_file / conflict_same_name /
review_import_dependency / dependency_update_required / skip_unsafe.

v0.3: dry-run only. No files are modified on disk.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from aetherfusion import __version__
from aetherfusion.utils import IGNORE_DIRS

# Files larger than this are flagged skip_unsafe
MAX_FILE_SIZE_BYTES: int = 1_048_576  # 1 MB

# Extensions commonly considered text (NOT binary)
TEXT_EXTENSIONS: set[str] = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts", ".cjs", ".cts",
    ".py", ".pyi", ".pyx",
    ".css", ".scss", ".sass", ".less",
    ".json", ".jsonc", ".json5",
    ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".md", ".mdx", ".rst", ".txt", ".csv", ".tsv",
    ".html", ".htm", ".xml", ".svg",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1",
    ".env", ".env.local", ".env.example",
    ".gitignore", ".dockerignore", ".editorconfig",
    ".eslintrc", ".prettierrc",
    "Dockerfile", "Makefile",
}

# Regex patterns for import/require detection
IMPORT_PATTERN_PY = re.compile(
    r'^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))',
    re.MULTILINE,
)
IMPORT_PATTERN_JS = re.compile(
    r'(?:import\s+.*?\s+from\s+["\']([^"\']+)["\']'
    r'|require\s*\(\s*["\']([^"\']+)["\']\s*\))',
    re.MULTILINE,
)


def generate_dry_run_patch(plan_path: Path) -> dict[str, Any]:
    """Generate a dry-run patch manifest from a v0.2 fusion plan JSON.

    Args:
        plan_path: Path to the fusion plan JSON file.

    Returns:
        Structured patch manifest dict.

    Raises:
        FileNotFoundError: Plan file missing.
        ValueError: Source module path missing or doesn't exist.
        json.JSONDecodeError: Invalid plan JSON.
    """
    if not plan_path.is_file():
        raise FileNotFoundError(f"Fusion plan not found: {plan_path}")

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    module_name = plan.get("module_name", "unknown")
    source_module_path = _safe_resolve(plan.get("source_module_path"))
    target_match_path = _safe_resolve(plan.get("target_match_path"))

    if not source_module_path:
        raise ValueError(
            f"source_module_path is missing or invalid in the fusion plan for '{module_name}'."
        )
    if not os.path.isdir(source_module_path):
        raise ValueError(
            f"source_module_path does not exist or is not a directory: {source_module_path}"
        )

    target_exists = target_match_path is not None and os.path.isdir(target_match_path)

    operations: list[dict[str, Any]] = []
    files_to_add: list[str] = []
    files_conflicted: list[str] = []
    files_skipped: list[str] = []
    import_notes: list[dict[str, Any]] = []

    # Walk the source module
    _walk_and_classify(
        source_module_path=source_module_path,
        target_match_path=target_match_path if target_exists else None,
        source_root=source_module_path,
        operations=operations,
        files_to_add=files_to_add,
        files_conflicted=files_conflicted,
        files_skipped=files_skipped,
        import_notes=import_notes,
    )

    # Build summary
    summary = {
        "files_to_add": len(files_to_add),
        "files_conflicted": len(files_conflicted),
        "files_skipped": len(files_skipped),
        "dependency_updates_required": 0,
        "blocked_operations": len(files_conflicted),
    }

    # Build manifest
    manifest: dict[str, Any] = {
        "patch_version": __version__,
        "mode": "dry_run",
        "module_name": module_name,
        "module_type": plan.get("module_type", "unknown"),
        "source_module_path": source_module_path,
        "target_match_path": target_match_path,
        "target_exists": target_exists,
        "risk_level": plan.get("risk_level", "unknown"),
        "strategy": plan.get("strategy", "manual_review"),
        "summary": summary,
        "operations": operations,
        "blocked_actions": [
            "v0.3 dry-run only — no source or target files are modified",
            "do not automatically overwrite target project files",
            "do not automatically modify package.json / requirements.txt / pyproject.toml",
            "do not execute build / test / lint / typecheck",
            "do not make any network requests",
        ],
        "required_human_decisions": [
            {
                "decision_id": "resolve_conflicts",
                "question": "How should files with name conflicts be resolved?",
                "context": (
                    f"{len(files_conflicted)} file(s) have same-named counterparts in the target. "
                    f"Each is listed in operations with type 'conflict_same_name'."
                ),
                "options": [
                    {"value": "overwrite", "label": "Overwrite", "description": "Replace target files with source versions."},
                    {"value": "skip", "label": "Skip", "description": "Skip conflicting files; only add new files."},
                    {"value": "manual_merge", "label": "Manual Merge", "description": "Manually review each conflict."},
                ],
                "is_blocking": True,
            },
            {
                "decision_id": "review_imports",
                "question": "Should import dependencies be reviewed or left as-is?",
                "context": (
                    f"{len(import_notes)} import/dependency note(s) detected. "
                    f"Some source files reference modules that may not exist in the target project."
                ),
                "options": [
                    {"value": "review_all", "label": "Review All", "description": "Manually review each import note."},
                    {"value": "defer", "label": "Defer", "description": "Leave import review for v0.4+."},
                ],
                "is_blocking": False,
            },
        ],
        "next_recommended_command": (
            f"python -m aetherfusion patch "
            f"--plan {plan_path} "
            f"--dry-run"
        ),
    }

    return manifest


def _safe_resolve(path: str | None) -> str | None:
    """Resolve a path safely. Returns None for empty/invalid paths."""
    if not path:
        return None
    try:
        p = Path(path).resolve()
        return str(p)
    except (OSError, RuntimeError):
        return None


def _walk_and_classify(
    source_module_path: str,
    target_match_path: str | None,
    source_root: str,
    operations: list[dict[str, Any]],
    files_to_add: list[str],
    files_conflicted: list[str],
    files_skipped: list[str],
    import_notes: list[dict[str, Any]],
) -> None:
    """Walk the source module and classify each file into an operation.

    Recurses into subdirectories. Skips IGNORE_DIRS.
    """
    for dirpath, dirnames, filenames in os.walk(source_module_path):
        # Filter ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            source_file = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(source_file, source_root)

            # ---- Safety checks ----

            # Path traversal detection
            if ".." in rel_path.split(os.sep):
                _add_skip(operations, files_skipped, rel_path, "Path traversal detected — unsafe path")
                continue

            # File size check
            try:
                file_size = os.path.getsize(source_file)
            except OSError:
                _add_skip(operations, files_skipped, rel_path, "Cannot stat file — read error")
                continue

            if file_size > MAX_FILE_SIZE_BYTES:
                _add_skip(
                    operations, files_skipped, rel_path,
                    f"File exceeds 1 MB ({file_size / 1_048_576:.1f} MB) — "
                    f"too large for automatic fusion preview",
                )
                continue

            # Binary file check
            ext = os.path.splitext(filename)[1].lower()
            name_lower = filename.lower()
            # Special-case: no-extension config files
            is_likely_text = (
                ext in TEXT_EXTENSIONS
                or name_lower in {"dockerfile", "makefile", "license", ".gitignore", ".dockerignore"}
                or "." not in filename  # extension-less files are often text
            )
            if not is_likely_text and ext:
                # Additional check: try to read the first 8 KB as text
                try:
                    with open(source_file, "rb") as f:
                        chunk = f.read(8192)
                    if b"\x00" in chunk:
                        _add_skip(operations, files_skipped, rel_path, "Binary file — skipped")
                        continue
                except OSError:
                    _add_skip(operations, files_skipped, rel_path, "Cannot read file — skipped")
                    continue

            # ---- Classification ----

            # Check if a counterpart exists in target
            target_counterpart = None
            if target_match_path:
                candidate = os.path.join(target_match_path, rel_path)
                if os.path.isfile(candidate):
                    target_counterpart = candidate

            if target_counterpart:
                # conflict_same_name
                files_conflicted.append(rel_path)
                operations.append({
                    "type": "conflict_same_name",
                    "relative_path": rel_path,
                    "source_absolute": source_file,
                    "target_absolute": target_counterpart,
                    "file_size_bytes": file_size,
                    "resolution_required": True,
                    "blocked_in_dry_run": True,
                })
            else:
                # add_file
                files_to_add.append(rel_path)
                operations.append({
                    "type": "add_file",
                    "relative_path": rel_path,
                    "source_absolute": source_file,
                    "file_size_bytes": file_size,
                    "resolution_required": False,
                    "blocked_in_dry_run": True,
                })

            # ---- Import / dependency check (text files only) ----
            if is_likely_text and not target_counterpart:
                _check_imports(
                    source_file=source_file,
                    rel_path=rel_path,
                    file_size=file_size,
                    ext=ext,
                    import_notes=import_notes,
                )


def _check_imports(
    source_file: str,
    rel_path: str,
    file_size: int,
    ext: str,
    import_notes: list[dict[str, Any]],
) -> None:
    """Inspect a text file for third-party imports and record a note."""
    try:
        with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return

    third_party: list[str] = []

    if ext in {".py", ".pyi", ".pyx"}:
        for m in IMPORT_PATTERN_PY.finditer(content):
            mod = m.group(1) or m.group(2)
            if mod and "." not in mod and mod not in _STDLIB_PY_MODULES:
                third_party.append(mod)
    elif ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts", ".cjs", ".cts"}:
        for m in IMPORT_PATTERN_JS.finditer(content):
            mod = m.group(1) or m.group(2)
            if mod and not mod.startswith(".") and not mod.startswith("/"):
                third_party.append(mod)

    if third_party:
        import_notes.append({
            "relative_path": rel_path,
            "source_absolute": source_file,
            "file_size_bytes": file_size,
            "third_party_imports": list(set(third_party)),
        })


def _add_skip(
    operations: list[dict[str, Any]],
    files_skipped: list[str],
    rel_path: str,
    reason: str,
) -> None:
    """Record a skipped file."""
    files_skipped.append(rel_path)
    operations.append({
        "type": "skip_unsafe",
        "relative_path": rel_path,
        "reason": reason,
        "resolution_required": False,
        "blocked_in_dry_run": True,
    })


# Common Python stdlib modules for excluding from third-party detection
_STDLIB_PY_MODULES: set[str] = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect",
    "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "doctest",
    "email", "encodings", "enum", "errno", "faulthandler", "fcntl", "filecmp",
    "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc",
    "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip",
    "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib",
    "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib", "numbers",
    "operator", "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle",
    "pickletools", "pipes", "pkgutil", "platform", "plistlib", "poplib",
    "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re",
    "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
    "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "trace", "traceback", "tracemalloc", "tty", "turtle",
    "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
    "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib",
}