"""Read-only parser for dependency manifest files.

Parses package.json / requirements.txt / pyproject.toml / setup.py
to extract dependency lists. Lock files are only detected for presence;
deep parsing of lock files is not performed.
"""

import json
from pathlib import Path
from typing import Any


# Known dependency manifest filenames to detect.
_MANIFEST_FILES = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Pipfile",
    "Pipfile.lock",
]


def _parse_package_json(path: Path) -> dict[str, Any]:
    """Parse dependencies from a package.json file.

    Returns a dict with keys: dependencies, devDependencies,
    optionalDependencies, peerDependencies.
    """
    result: dict[str, Any] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return result

    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(key, {})
        if isinstance(deps, dict) and deps:
            result[key] = {
                name: str(ver).lstrip("^~>=<") for name, ver in deps.items()
            }

    return result


def _parse_requirements_txt(path: Path) -> dict[str, Any]:
    """Parse dependencies from a requirements.txt file.

    Returns a dict with key 'requirements' containing a list of package names.
    Version info is stripped to package name only for structural comparison.
    """
    pkgs: list[dict[str, str]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Strip version specifiers and extras
            pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0]
            pkg_name = pkg_name.split("~=")[0].split("!=")[0].split("[")[0].strip()
            if pkg_name:
                pkgs.append({"name": pkg_name, "raw": line})
    except OSError:
        return {}
    return {"requirements": pkgs} if pkgs else {}


def _parse_pyproject_toml(path: Path) -> dict[str, Any]:
    """Parse dependencies from a pyproject.toml file.

    Looks under [project].dependencies and [tool.poetry.dependencies].
    Uses a simple line-based parser; does not require the 'toml' library.
    """
    result: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result

    # Simple TOML section detection
    in_section = None
    in_poetry = False
    dependencies: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[project]"):
            in_section = "project"
            in_poetry = False
        elif stripped.startswith("[tool.poetry]"):
            in_section = "poetry"
            in_poetry = True
        elif stripped.startswith("[tool.poetry.dependencies]"):
            in_section = "poetry-deps"
            in_poetry = True
        elif stripped.startswith("[tool.poetry.group.dev.dependencies]"):
            in_section = "poetry-dev"
            in_poetry = True
        elif stripped.startswith("["):
            in_section = None
            in_poetry = False
        elif in_section in ("poetry-deps", "poetry-dev") and "=" in stripped:
            pkg = stripped.split("=")[0].strip().strip('"').strip("'")
            if pkg and pkg != "python":
                ver = stripped.split("=", 1)[1].strip().strip('"').strip("'").lstrip("^~>=<")
                section_name = "poetry_dependencies" if in_section == "poetry-deps" else "poetry_dev_dependencies"
                result.setdefault(section_name, {})[pkg] = ver
        elif in_section == "project" and stripped.startswith("dependencies"):
            # Handled below via a simpler approach
            pass

    # For project.dependencies array: look for quoted strings
    if "poetry_dependencies" not in result:
        in_deps = False
        project_deps: dict[str, str] = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("dependencies"):
                in_deps = True
                # Check inline array
                inline = stripped.split("=", 1)[-1].strip()
                if inline.startswith("[") and inline.endswith("]"):
                    for item in inline[1:-1].split(","):
                        item = item.strip().strip('"').strip("'")
                        if item and item != "python":
                            project_deps[item] = ""
                    in_deps = False
            elif in_deps:
                if stripped == "]":
                    in_deps = False
                else:
                    item = stripped.strip(",").strip().strip('"').strip("'")
                    if item and item != "python":
                        project_deps[item] = ""
        if project_deps:
            result["project_dependencies"] = project_deps

    return result


def parse_dependency_files(target_path: Path, source_path: Path) -> dict[str, Any]:
    """Parse dependency manifest files from target and source projects.

    Args:
        target_path: Absolute path to the target project root.
        source_path: Absolute path to the source project root.

    Returns:
        Dict with keys:
        - detected_files: list of manifest file names found across both projects
        - target_dependencies: parsed dependency info from target
        - source_dependencies: parsed dependency info from source
    """
    target_path = Path(target_path)
    source_path = Path(source_path)

    detected_files: list[str] = []
    target_deps: dict[str, Any] = {}
    source_deps: dict[str, Any] = {}

    for proj_root, store in ((target_path, target_deps), (source_path, source_deps)):
        # Check each manifest file
        for filename in _MANIFEST_FILES:
            fpath = proj_root / filename
            if not fpath.is_file():
                continue
            if filename not in detected_files:
                detected_files.append(filename)

            if filename == "package.json":
                parsed = _parse_package_json(fpath)
                if parsed:
                    store["package.json"] = parsed
            elif filename == "requirements.txt":
                parsed = _parse_requirements_txt(fpath)
                if parsed:
                    store["requirements.txt"] = parsed
            elif filename == "pyproject.toml":
                parsed = _parse_pyproject_toml(fpath)
                if parsed:
                    store["pyproject.toml"] = parsed
            elif filename == "setup.py":
                store["setup.py"] = {"detected": True, "parsed": False}
            elif filename.endswith(".lock") or filename == "pnpm-lock.yaml" or filename == "yarn.lock":
                store[filename] = {"detected": True, "parsed": False}

    return {
        "detected_files": detected_files,
        "target_dependencies": target_deps,
        "source_dependencies": source_deps,
    }
