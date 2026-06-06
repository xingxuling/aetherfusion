"""Project scanner — orchestrates config parsing, tree building, and analysis."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aetherfusion.scanner.config_parser import parse_all_configs, detect_config_files
from aetherfusion.scanner.tree_builder import build_tree
from aetherfusion.utils import (
    CONFIG_FILES,
    ENTRY_PATTERNS,
    FUSIBLE_DIR_NAMES,
    IGNORE_DIRS,
    normalize_path_for_report,
)


@dataclass
class ProjectInfo:
    """Structured result of scanning a single project."""

    root: str
    name: str
    configs: dict[str, Any] = field(default_factory=dict)
    config_files_detected: dict[str, str] = field(default_factory=dict)
    tree: dict[str, Any] = field(default_factory=dict)
    tree_text: list[str] = field(default_factory=list)
    entry_files: list[str] = field(default_factory=list)
    core_directories: list[str] = field(default_factory=list)
    dependencies: dict[str, dict[str, str]] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    tech_stack: list[str] = field(default_factory=list)
    fusible_modules: dict[str, list[str]] = field(default_factory=dict)
    file_count: int = 0
    dir_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": normalize_path_for_report(self.root),
            "name": self.name,
            "config_files_detected": self.config_files_detected,
            "entry_files": self.entry_files,
            "core_directories": self.core_directories,
            "dependencies": self.dependencies,
            "scripts": self.scripts,
            "tech_stack": self.tech_stack,
            "fusible_modules": {
                k: [normalize_path_for_report(p) for p in v]
                for k, v in self.fusible_modules.items()
            },
            "file_count": self.file_count,
            "dir_count": self.dir_count,
        }


class ProjectAnalyzer:
    """Scans a single local project directory and extracts structured info."""

    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Not a directory: {self.root}")

    def analyze(self) -> ProjectInfo:
        """Run all scanning steps and return a ProjectInfo."""
        info = ProjectInfo(
            root=str(self.root),
            name=self.root.name,
        )

        info.config_files_detected = detect_config_files(self.root)
        info.configs = parse_all_configs(self.root)
        info.tree = build_tree(self.root)
        info.tree_text = self._render_tree_text(info.tree)

        info.entry_files = self._find_entry_files()
        info.core_directories = self._find_core_directories()
        info.dependencies = self._extract_dependencies(info.configs)
        info.scripts = self._extract_scripts(info.configs)
        info.tech_stack = self._infer_tech_stack(info.config_files_detected, info.configs)
        info.fusible_modules = self._find_fusible_modules()
        info.file_count, info.dir_count = self._count_files_and_dirs()

        return info

    def _render_tree_text(self, tree: dict[str, Any]) -> list[str]:
        from aetherfusion.scanner.tree_builder import tree_to_text
        lines = [self.root.name + "/"]
        for i, child in enumerate(tree.get("children", [])):
            lines.extend(tree_to_text(child, "", i == len(tree["children"]) - 1))
        return lines

    def _find_entry_files(self) -> list[str]:
        """Find entry point files."""
        found: list[str] = []
        for pattern in ENTRY_PATTERNS:
            candidate = self.root / pattern
            if candidate.is_file():
                found.append(pattern)
        return found

    def _find_core_directories(self) -> list[str]:
        """Find top-level & second-level directories that look like core project dirs."""
        core: set[str] = set()
        try:
            for entry in sorted(os.listdir(self.root)):
                full = self.root / entry
                if not full.is_dir():
                    continue
                if entry in IGNORE_DIRS or entry.startswith("."):
                    continue
                core.add(entry)
        except PermissionError:
            pass
        return sorted(core)

    def _extract_dependencies(self, configs: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Extract all dependencies from config files into {name: version}."""
        deps: dict[str, dict[str, str]] = {}

        pkg = configs.get("package.json")
        if pkg:
            all_deps = {}
            all_deps.update(pkg.get("dependencies", {}))
            all_deps.update(pkg.get("dev_dependencies", {}))
            for name, ver in all_deps.items():
                deps[name] = {"version": ver, "source": "package.json", "type": "npm"}

        req = configs.get("requirements.txt")
        if req:
            for pkg_str in req.get("packages", []):
                name, ver = _parse_pip_dep(pkg_str)
                deps[name] = {"version": ver, "source": "requirements.txt", "type": "pip"}

        pyproject = configs.get("pyproject.toml")
        if pyproject:
            for pkg_str in pyproject.get("dependencies", []):
                name, ver = _parse_pip_dep(pkg_str)
                if name not in deps:
                    deps[name] = {"version": ver, "source": "pyproject.toml", "type": "pip"}

        return deps

    def _extract_scripts(self, configs: dict[str, Any]) -> dict[str, str]:
        """Extract runnable scripts / commands."""
        scripts: dict[str, str] = {}
        pkg = configs.get("package.json")
        if pkg and pkg.get("scripts"):
            scripts.update(pkg["scripts"])
        pyproject = configs.get("pyproject.toml")
        if pyproject and pyproject.get("scripts"):
            scripts.update(pyproject["scripts"])
        return scripts

    def _infer_tech_stack(self, config_files_detected: dict[str, str], configs: dict[str, Any]) -> list[str]:
        """Infer the technology stack from detected config files."""
        stack: list[str] = []
        cfgs = config_files_detected

        if any(c in cfgs for c in ["package.json", "tsconfig.json", "vite.config.ts", "vite.config.js"]):
            stack.append("Node.js")
        if "tsconfig.json" in cfgs:
            stack.append("TypeScript")
        elif "jsconfig.json" in cfgs:
            stack.append("JavaScript")
        elif "package.json" in cfgs:
            # Check package.json for type hints
            pkg = configs.get("package.json", {})
            deps = {**pkg.get("dependencies", {}), **pkg.get("dev_dependencies", {})}
            if "typescript" in deps or "ts-node" in deps:
                stack.append("TypeScript")
            else:
                stack.append("JavaScript")
        if any(c in cfgs for c in ["requirements.txt", "pyproject.toml", "setup.py"]):
            stack.append("Python")
        if any(c.startswith("vite.config") for c in cfgs):
            stack.append("Vite")
        if any(c.startswith("next.config") for c in cfgs):
            stack.append("Next.js")
        if "tailwind.config.js" in cfgs or "tailwind.config.ts" in cfgs:
            stack.append("Tailwind CSS")
        if "webpack.config.js" in cfgs:
            stack.append("Webpack")
        if "Dockerfile" in cfgs:
            stack.append("Docker")
        if configs.get("package.json"):
            pkg = configs["package.json"]
            all_deps = {**pkg.get("dependencies", {}), **pkg.get("dev_dependencies", {})}
            lower = {k.lower(): v for k, v in all_deps.items()}
            if "react" in lower:
                stack.append("React")
            if "vue" in lower:
                stack.append("Vue")
            if "svelte" in lower:
                stack.append("Svelte")
            if "express" in lower:
                stack.append("Express")
            if "fastify" in lower:
                stack.append("Fastify")
            if "electron" in lower:
                stack.append("Electron")

        return stack

    def _find_fusible_modules(self) -> dict[str, list[str]]:
        """Find directories that match common fusible module names."""
        modules: dict[str, list[str]] = {}
        for dir_name in FUSIBLE_DIR_NAMES:
            # Check top-level
            top = self.root / dir_name
            if top.is_dir():
                modules.setdefault(dir_name, []).append(str(top))
            # Check src/ level
            src = self.root / "src" / dir_name
            if src.is_dir():
                modules.setdefault(dir_name, []).append(str(src))
        return modules

    def _count_files_and_dirs(self) -> tuple[int, int]:
        """Count total files and directories (excluding ignored)."""
        fcount, dcount = 0, 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
            fcount += len(filenames)
            # Count the current dir if it's not the root itself (root counted separately)
            rel = os.path.relpath(dirpath, self.root)
            if rel != ".":
                dcount += 1
        dcount += 1  # Root itself
        return fcount, dcount


def _parse_pip_dep(pkg_str: str) -> tuple[str, str]:
    """Parse a pip dependency string into (name, version_spec).

    e.g. ``"requests>=2.28,<3"`` → ``("requests", ">=2.28,<3")``
    """
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", ";"):
        idx = pkg_str.find(sep)
        if idx != -1:
            return pkg_str[:idx].strip(), pkg_str[idx:].strip()
    # Check for extras like "package[extra1,extra2]"
    if "[" in pkg_str:
        idx = pkg_str.find("[")
        return pkg_str[:idx].strip(), pkg_str[idx:]
    return pkg_str.strip(), ""