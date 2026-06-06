"""Parsers for key project configuration files."""

import sys
from pathlib import Path
from typing import Any

from aetherfusion.utils import CONFIG_FILES, safe_read_json, safe_read_text

if sys.version_info >= (3, 11):
    import tomllib
    _HAS_TOML = True
else:
    _HAS_TOML = False


def parse_package_json(path: Path) -> dict[str, Any] | None:
    """Parse a package.json file.

    Returns a dict with keys: name, version, scripts, dependencies, devDependencies.
    """
    data = safe_read_json(path)
    if data is None:
        return None
    return {
        "name": data.get("name", ""),
        "version": data.get("version", ""),
        "scripts": data.get("scripts", {}),
        "dependencies": data.get("dependencies", {}),
        "dev_dependencies": data.get("devDependencies", {}),
    }


def parse_requirements_txt(path: Path) -> dict[str, Any] | None:
    """Parse a requirements.txt file.

    Returns a dict with key: packages — list of dependency strings.
    """
    text = safe_read_text(path)
    if text is None:
        return None
    packages: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Handle options like -r, --index-url, etc.
        if stripped.startswith("-"):
            continue
        packages.append(stripped)
    return {"packages": packages}


def parse_pyproject_toml(path: Path) -> dict[str, Any] | None:
    """Parse a pyproject.toml file.

    Returns a dict with keys: name, version, dependencies, dev_dependencies, scripts.
    """
    if not _HAS_TOML:
        return _parse_pyproject_toml_fallback(path)
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None

    project = data.get("project", {})
    dep_groups: dict[str, list[str]] = {}
    opt_deps = data.get("project", {}).get("optional-dependencies", {})
    dep_groups.update(opt_deps)

    return {
        "name": project.get("name", ""),
        "version": project.get("version", ""),
        "dependencies": project.get("dependencies", []),
        "dev_dependencies": dep_groups.get("dev", []),
        "scripts": project.get("scripts", {}),
    }


def _parse_pyproject_toml_fallback(path: Path) -> dict[str, Any] | None:
    """Fallback TOML parser using basic regex for Python < 3.11."""
    import re
    text = safe_read_text(path)
    if text is None:
        return None

    name_match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)

    deps: list[str] = []
    scripts: dict[str, str] = {}

    # Crude dependency extraction from [project] table
    in_project = False
    in_deps = False
    in_scripts = False
    for line in text.splitlines():
        if line.strip().startswith("[project]"):
            in_project = True
            in_deps = False
            in_scripts = False
        elif line.strip().startswith("[") and in_project:
            in_project = False
            in_deps = False
            in_scripts = False
        elif in_project:
            if line.strip().startswith("dependencies"):
                in_deps = True
                in_scripts = False
                continue
            elif line.strip().startswith("[project.scripts]"):
                in_scripts = True
                in_deps = False
                continue
            if in_deps:
                dep = line.strip().strip('"').strip("'").strip(",")
                if dep:
                    deps.append(dep)
            if in_scripts:
                m = re.match(r'(\w+)\s*=\s*"([^"]+)"', line.strip())
                if m:
                    scripts[m.group(1)] = m.group(2)

    return {
        "name": name_match.group(1) if name_match else "",
        "version": version_match.group(1) if version_match else "",
        "dependencies": deps,
        "dev_dependencies": [],
        "scripts": scripts,
    }


def parse_tsconfig_json(path: Path) -> dict[str, Any] | None:
    """Parse a tsconfig.json file."""
    data = safe_read_json(path)
    if data is None:
        return None
    compiler_options = data.get("compilerOptions", {})
    return {
        "compiler_options": {
            "target": compiler_options.get("target", ""),
            "module": compiler_options.get("module", ""),
            "jsx": compiler_options.get("jsx", ""),
            "strict": compiler_options.get("strict", False),
            "paths": compiler_options.get("paths", {}),
        },
        "include": data.get("include", []),
        "exclude": data.get("exclude", []),
        "extends": data.get("extends", ""),
    }


def detect_config_files(project_root: Path) -> dict[str, str]:
    """Detect which known config files exist in the project root.

    Returns dict of {filename: category}.
    """
    found: dict[str, str] = {}
    for fname, category in CONFIG_FILES.items():
        candidate = project_root / fname
        if candidate.is_file():
            found[fname] = category
    return found


def parse_all_configs(project_root: Path) -> dict[str, Any]:
    """Parse all relevant config files in a project.

    Returns a dict keyed by filename.
    """
    result: dict[str, Any] = {}
    for fname in CONFIG_FILES:
        path = project_root / fname
        if not path.is_file():
            continue
        if fname == "package.json":
            parsed = parse_package_json(path)
        elif fname == "requirements.txt":
            parsed = parse_requirements_txt(path)
        elif fname == "pyproject.toml":
            parsed = parse_pyproject_toml(path)
        elif fname == "tsconfig.json":
            parsed = parse_tsconfig_json(path)
        else:
            # For other configs, just record presence
            parsed = {"present": True}
        if parsed is not None:
            result[fname] = parsed
    return result