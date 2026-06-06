"""Tests for AetherFusion scanner module."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.scanner.project_analyzer import ProjectAnalyzer
from aetherfusion.scanner.config_parser import (
    parse_package_json,
    parse_requirements_txt,
    parse_tsconfig_json,
    parse_pyproject_toml,
    detect_config_files,
)
from aetherfusion.scanner.tree_builder import build_tree
from aetherfusion.utils import IGNORE_DIRS, normalize_path_for_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal sample project tree for testing."""
    root = tmp_path / "sample-project"
    root.mkdir()

    # package.json
    (root / "package.json").write_text(json.dumps({
        "name": "sample-project",
        "version": "1.0.0",
        "scripts": {"dev": "vite", "build": "tsc && vite build"},
        "dependencies": {"react": "^18.2.0"},
        "devDependencies": {"typescript": "^5.0.0", "vite": "^5.0.0"},
    }), encoding="utf-8")

    # tsconfig.json
    (root / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {"target": "ES2020", "module": "ESNext", "jsx": "react-jsx", "strict": True},
        "include": ["src"],
    }), encoding="utf-8")

    # requirements.txt
    (root / "requirements.txt").write_text("requests==2.28.0\nflask>=2.3\n", encoding="utf-8")

    # Source directory
    src = root / "src"
    src.mkdir()
    (src / "index.tsx").write_text("// entry", encoding="utf-8")
    (src / "App.tsx").write_text("// app", encoding="utf-8")
    components = src / "components"
    components.mkdir()
    (components / "Button.tsx").write_text("// button", encoding="utf-8")
    utils = src / "utils"
    utils.mkdir()
    (utils / "helpers.ts").write_text("// helpers", encoding="utf-8")

    # Should be ignored
    (root / "node_modules").mkdir()
    (root / "node_modules" / "lodash").mkdir()
    (root / ".git").mkdir()
    (root / "dist").mkdir()
    (root / "__pycache__").mkdir()

    return root


# ---------------------------------------------------------------------------
# Config Parser Tests
# ---------------------------------------------------------------------------

class TestConfigParser:
    def test_parse_package_json(self, sample_project: Path) -> None:
        result = parse_package_json(sample_project / "package.json")
        assert result is not None
        assert result["name"] == "sample-project"
        assert result["version"] == "1.0.0"
        assert "dev" in result["scripts"]
        assert "react" in result["dependencies"]
        assert "typescript" in result["dev_dependencies"]

    def test_parse_requirements_txt(self, sample_project: Path) -> None:
        result = parse_requirements_txt(sample_project / "requirements.txt")
        assert result is not None
        assert len(result["packages"]) == 2
        assert any("requests" in p for p in result["packages"])
        assert any("flask" in p for p in result["packages"])

    def test_parse_tsconfig_json(self, sample_project: Path) -> None:
        result = parse_tsconfig_json(sample_project / "tsconfig.json")
        assert result is not None
        assert result["compiler_options"]["target"] == "ES2020"
        assert result["compiler_options"]["strict"] is True

    def test_parse_pyproject_toml(self, tmp_path: Path) -> None:
        toml_path = tmp_path / "pyproject.toml"
        toml_path.write_text(
            '[project]\nname = "testpkg"\nversion = "0.1.0"\n'
            'dependencies = ["requests>=2.28"]\n'
            '[project.scripts]\ncli = "testpkg.cli:main"\n',
            encoding="utf-8",
        )
        result = parse_pyproject_toml(toml_path)
        assert result is not None
        assert result["name"] == "testpkg"
        assert result["version"] == "0.1.0"

    def test_detect_config_files(self, sample_project: Path) -> None:
        detected = detect_config_files(sample_project)
        assert "package.json" in detected
        assert "tsconfig.json" in detected
        assert "requirements.txt" in detected
        assert detected["package.json"] == "node"
        assert detected["tsconfig.json"] == "typescript"


# ---------------------------------------------------------------------------
# Tree Builder Tests
# ---------------------------------------------------------------------------

class TestTreeBuilder:
    def test_build_tree_structure(self, sample_project: Path) -> None:
        tree = build_tree(sample_project)
        assert tree["type"] == "directory"
        child_names = {c["name"] for c in tree["children"]}
        assert "package.json" in child_names
        assert "src" in child_names
        # Ignored dirs should NOT appear
        assert "node_modules" not in child_names
        assert ".git" not in child_names
        assert "dist" not in child_names

    def test_tree_excludes_ignored_dirs(self, tmp_path: Path) -> None:
        root = tmp_path / "test-exclude"
        root.mkdir()
        for d in IGNORE_DIRS:
            (root / d).mkdir(exist_ok=True)
        for fname in ["README.md", "main.py"]:
            (root / fname).write_text("", encoding="utf-8")
        tree = build_tree(root)
        child_names = {c["name"] for c in tree["children"]}
        for d in IGNORE_DIRS:
            assert d not in child_names, f"{d} should be excluded"


# ---------------------------------------------------------------------------
# Project Analyzer Tests
# ---------------------------------------------------------------------------

class TestProjectAnalyzer:
    def test_analyze_sample_project(self, sample_project: Path) -> None:
        pa = ProjectAnalyzer(sample_project)
        info = pa.analyze()

        assert info.name == "sample-project"
        assert len(info.config_files_detected) >= 3
        assert "src/index.tsx" in info.entry_files
        assert "src" in info.core_directories
        assert "react" in info.dependencies
        assert "vite" in info.dependencies or any(
            "vite" in k for k in info.dependencies
        )
        assert "React" in info.tech_stack or "Node.js" in info.tech_stack
        assert "components" in info.fusible_modules
        assert info.file_count > 0
        assert info.dir_count > 0

    def test_analyze_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty-project"
        empty.mkdir()
        pa = ProjectAnalyzer(empty)
        info = pa.analyze()
        assert info.name == "empty-project"
        assert info.file_count == 0

    def test_analyze_invalid_path(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            ProjectAnalyzer(tmp_path / "does_not_exist")


# ---------------------------------------------------------------------------
# Utils Tests
# ---------------------------------------------------------------------------

class TestUtils:
    def test_normalize_path_for_report(self) -> None:
        p = str(Path("C:\\Users\\test\\project"))
        result = normalize_path_for_report(p)
        assert "\\" not in result
        assert "/" in result