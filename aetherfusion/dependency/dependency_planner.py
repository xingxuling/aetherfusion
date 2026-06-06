"""Generate dependency update plans from extracted dependency errors."""

from pathlib import Path
from typing import Any

from aetherfusion.dependency.dependency_error_extractor import extract_dependency_errors
from aetherfusion.dependency.dependency_file_parser import parse_dependency_files

# --- Built-in / stdlib module lists ---

_NODE_BUILTINS: set[str] = {
    "fs", "path", "os", "http", "https", "url", "crypto", "stream",
    "events", "util", "assert", "buffer", "child_process", "cluster",
    "dgram", "dns", "net", "querystring", "readline", "repl",
    "string_decoder", "tls", "tty", "zlib", "process", "console",
    "timers", "module", "v8", "vm", "worker_threads", "perf_hooks",
    "punycode", "domain", "fs/promises", "inspector", "trace_events",
    "tty", "wasi",
}

_PYTHON_STDLIB: set[str] = {
    "os", "sys", "json", "pathlib", "subprocess", "re", "math",
    "datetime", "collections", "itertools", "functools", "typing",
    "io", "tempfile", "shutil", "logging", "argparse", "unittest",
    "csv", "hashlib", "uuid", "socket", "threading", "multiprocessing",
    "asyncio", "email", "http", "urllib", "xml", "html", "base64",
    "struct", "time", "random", "statistics", "textwrap", "copy",
    "enum", "abc", "decimal", "fractions", "configparser",
    "dataclasses", "platform", "sysconfig", "importlib", "pkgutil",
    "pdb", "traceback", "warnings", "weakref", "types", "operator",
    "queue", "concurrent", "inspect", "ast", "tokenize", "dis",
    "code", "codeop", "contextlib", "glob", "fnmatch", "tarfile",
    "zipfile", "gzip", "bz2", "lzma", "pickle", "shelve", "sqlite3",
    "getpass", "getopt", "pipes", "shlex", "fileinput", "linecache",
    "pprint", "string", "calendar", "bisect", "heapq", "array",
    "select", "ssl", "signal", "mmap", "errno", "ctypes", "curses",
    "readline", "rlcompleter", "gettext", "locale", "unicodedata",
    "stringprep",
}

_PATH_LIKE_PREFIXES = ("./", "../", "@/", "~")


def _is_path_like(name: str) -> bool:
    """Check if a module name looks like a relative/alias import path."""
    return any(name.startswith(p) for p in _PATH_LIKE_PREFIXES)


def _is_builtin_or_stdlib(name: str, ecosystem: str) -> bool:
    """Check if name is a built-in / stdlib module."""
    if ecosystem == "node":
        return name in _NODE_BUILTINS
    if ecosystem == "python":
        return name in _PYTHON_STDLIB
    return name in _NODE_BUILTINS or name in _PYTHON_STDLIB


def _collect_all_deps(
    dep_info: dict[str, Any],
) -> dict[str, str]:
    """Collect all dependencies from a parsed dependency info dict into a flat name→version map."""
    all_deps: dict[str, str] = {}
    for manifest_name, content in dep_info.items():
        if manifest_name == "package.json":
            for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                section_data = content.get(section, {})
                if isinstance(section_data, dict):
                    for name, ver in section_data.items():
                        all_deps[name] = ver
        elif manifest_name == "requirements.txt":
            for pkg in content.get("requirements", []):
                if isinstance(pkg, dict):
                    name = pkg.get("name", "")
                    if name:
                        raw = pkg.get("raw", "")
                        ver = ""
                        for sep in ("==", ">=", "<=", "~=", "!="):
                            if sep in raw:
                                ver = raw.split(sep)[-1].strip().split(";")[0].strip()
                                break
                        all_deps[name] = ver
        elif manifest_name == "pyproject.toml":
            for section in ("project_dependencies", "poetry_dependencies", "poetry_dev_dependencies"):
                section_data = content.get(section, {})
                if isinstance(section_data, dict):
                    for name, ver in section_data.items():
                        all_deps[name] = ver
    return all_deps


def generate_dependency_plan(
    repair_path: Path,
    target_path: Path,
    source_path: Path,
    import_fix_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a dependency update plan.

    Args:
        repair_path: Path to the v0.6 repair-plan JSON file.
        target_path: Path to the target project root.
        source_path: Path to the source project root.
        import_fix_path: Optional path to the v0.7 import-fix-plan JSON file.

    Returns:
        Dependency plan dict.

    Raises:
        FileNotFoundError: If repair_path, target_path, or source_path does not exist.
        NotADirectoryError: If target_path or source_path is not a directory.
        json.JSONDecodeError: If a JSON file has invalid format.
    """
    import json as _json

    repair_path = Path(repair_path).resolve()
    target_path = Path(target_path).resolve()
    source_path = Path(source_path).resolve()

    if not repair_path.is_file():
        raise FileNotFoundError(f"Repair plan not found: {repair_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")
    if not target_path.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_path}")
    if not source_path.exists():
        raise FileNotFoundError(f"Source path does not exist: {source_path}")
    if not source_path.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_path}")

    # Load repair plan
    try:
        repair_plan = _json.loads(repair_path.read_text(encoding="utf-8"))
    except _json.JSONDecodeError:
        raise

    # Load optional import-fix plan
    import_fix_plan: dict[str, Any] | None = None
    if import_fix_path:
        ifp = Path(import_fix_path).resolve()
        if ifp.is_file():
            try:
                import_fix_plan = _json.loads(ifp.read_text(encoding="utf-8"))
            except _json.JSONDecodeError:
                raise

    # Parse dependency files
    dep_files = parse_dependency_files(target_path, source_path)

    # Extract errors
    dependency_errors = extract_dependency_errors(repair_plan, import_fix_plan)

    # Collect all deps from target and source
    target_deps = _collect_all_deps(dep_files.get("target_dependencies", {}))
    source_deps = _collect_all_deps(dep_files.get("source_dependencies", {}))

    # Build dependency candidates
    candidates: list[dict[str, Any]] = []
    stats = {
        "add_to_target": 0,
        "review_version_conflict": 0,
        "likely_not_dependency_issue": 0,
        "manual_research": 0,
        "builtin_or_stdlib_skipped": 0,
        "redirect_to_import_fix": 0,
    }

    for err in dependency_errors:
        pkg_name = err["package_name"]
        ecosystem = err["ecosystem"]

        # Redirect path-like imports back to import-fix-plan
        if _is_path_like(pkg_name):
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": False,
                "found_in_target": False,
                "source_version": None,
                "target_version": None,
                "version_conflict": False,
                "likely_cause": "local_import_path",
                "recommended_action": "Redirect to import-fix-plan. Path-like import should be handled as a local file reference, not a dependency.",
                "automation_eligibility": "manual_only",
                "risk_level": "low",
                "evidence": err["evidence"],
            })
            stats["redirect_to_import_fix"] += 1
            continue

        # Skip builtin / stdlib
        if _is_builtin_or_stdlib(pkg_name, ecosystem):
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": False,
                "found_in_target": False,
                "source_version": None,
                "target_version": None,
                "version_conflict": False,
                "likely_cause": "builtin_or_stdlib_module",
                "recommended_action": f"Skipped: '{pkg_name}' is a {ecosystem} built-in / stdlib module. Import error is likely a configuration issue, not a missing dependency.",
                "automation_eligibility": "manual_only",
                "risk_level": "low",
                "evidence": err["evidence"],
            })
            stats["builtin_or_stdlib_skipped"] += 1
            continue

        in_source = pkg_name in source_deps
        in_target = pkg_name in target_deps
        src_ver = source_deps.get(pkg_name)
        tgt_ver = target_deps.get(pkg_name)

        if in_source and not in_target:
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": True,
                "found_in_target": False,
                "source_version": src_ver,
                "target_version": None,
                "version_conflict": False,
                "likely_cause": "source_has_dependency_target_missing",
                "recommended_action": f"Add '{pkg_name}' (version: {src_ver}) to target dependency manifest. Human review required before any modification.",
                "automation_eligibility": "plan_only",
                "risk_level": "medium",
                "evidence": err["evidence"],
            })
            stats["add_to_target"] += 1

        elif in_source and in_target:
            conflict = bool(src_ver != tgt_ver and src_ver and tgt_ver)
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": True,
                "found_in_target": True,
                "source_version": src_ver,
                "target_version": tgt_ver,
                "version_conflict": conflict,
                "likely_cause": "version_conflict" if conflict else "both_have_dependency",
                "recommended_action": (
                    f"Version conflict: source has {src_ver}, target has {tgt_ver}. "
                    "Human decision required to resolve version mismatch."
                ) if conflict else (
                    f"Both projects already have '{pkg_name}'. "
                    "Import error is likely not a dependency issue — check import paths or configuration."
                ),
                "automation_eligibility": "manual_only",
                "risk_level": "medium" if conflict else "low",
                "evidence": err["evidence"],
            })
            stats["review_version_conflict" if conflict else "likely_not_dependency_issue"] += 1

        elif not in_source and in_target:
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": False,
                "found_in_target": True,
                "source_version": None,
                "target_version": tgt_ver,
                "version_conflict": False,
                "likely_cause": "target_already_has_dependency",
                "recommended_action": f"Target already has '{pkg_name}'. Import error is likely not a dependency issue — check import paths, module resolution, or runtime environment.",
                "automation_eligibility": "manual_only",
                "risk_level": "low",
                "evidence": err["evidence"],
            })
            stats["likely_not_dependency_issue"] += 1

        else:
            # Not in source, not in target
            candidates.append({
                "package_name": pkg_name,
                "ecosystem": ecosystem,
                "found_in_source": False,
                "found_in_target": False,
                "source_version": None,
                "target_version": None,
                "version_conflict": False,
                "likely_cause": "missing_from_both_projects",
                "recommended_action": f"Package '{pkg_name}' not found in either project's dependency manifests. Manual research required: check if this is a transitive dependency, a library vendored within the source code, or a package that needs to be installed from a registry.",
                "automation_eligibility": "manual_only",
                "risk_level": "high",
                "evidence": err["evidence"],
            })
            stats["manual_research"] += 1

    # Build blocked actions
    blocked_actions = [
        "Do NOT modify source or target project files.",
        "Do NOT auto-modify package.json.",
        "Do NOT auto-modify requirements.txt.",
        "Do NOT auto-modify pyproject.toml.",
        "Do NOT auto-modify any lock files.",
        "Do NOT auto-install dependencies (npm install / pip install / poetry install).",
        "Do NOT execute build / test / lint / typecheck commands.",
        "Do NOT call the network or download packages.",
        "Do NOT execute any installer commands.",
        "This is a read-only dependency plan. All actions require human review.",
    ]

    summary = {
        "total_extracted_dependency_errors": len(dependency_errors),
        "total_dependency_candidates": len(candidates),
        **stats,
    }

    # Next recommended command
    next_cmd = (
        f"python -m aetherfusion dependency-plan "
        f"--repair {repair_path} "
        f"--target {target_path} "
        f"--source {source_path}"
    )
    if import_fix_path:
        next_cmd += f" --import-fix {import_fix_path}"

    return {
        "dependency_plan_version": "0.8.0",
        "source_repair_file": str(repair_path),
        "source_import_fix_file": str(import_fix_path) if import_fix_path else "",
        "target_path": str(target_path),
        "source_path": str(source_path),
        "summary": summary,
        "extracted_dependency_errors": dependency_errors,
        "dependency_candidates": candidates,
        "dependency_files_detected": dep_files.get("detected_files", []),
        "blocked_actions": blocked_actions,
        "next_recommended_command": next_cmd,
    }
