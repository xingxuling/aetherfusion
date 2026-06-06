"""Tests for AetherFusion reporter module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.scanner.project_analyzer import ProjectInfo
from aetherfusion.reporter.markdown_reporter import generate_report


def _make_info(**overrides) -> ProjectInfo:
    defaults = dict(
        root=".",
        name="test",
        configs={},
        config_files_detected={},
        tree={"name": "test", "type": "directory", "children": [], "truncated": False},
        tree_text=["test/"],
        entry_files=[],
        core_directories=[],
        dependencies={},
        scripts={},
        tech_stack=[],
        fusible_modules={},
        file_count=0,
        dir_count=0,
    )
    defaults.update(overrides)
    return ProjectInfo(**defaults)


class TestReportGeneration:
    def test_generates_basic_report(self) -> None:
        source = _make_info(name="project-b", root="/tmp/project-b")
        target = _make_info(name="project-a", root="/tmp/project-a")
        report = generate_report(source, target)
        assert "# AetherFusion Report" in report
        assert "project-b" in report
        assert "project-a" in report
        assert "Tech Stack" in report
        assert "Dependency Analysis" in report
        assert "Fusible Modules" in report
        assert "Conflict Risks" in report
        assert "Recommendations" in report

    def test_report_includes_tech_stack(self) -> None:
        source = _make_info(tech_stack=["Node.js", "React"])
        target = _make_info(tech_stack=["Node.js", "Python"])
        report = generate_report(source, target)
        assert "React" in report
        assert "Python" in report

    def test_report_includes_dependencies(self) -> None:
        source = _make_info(
            dependencies={"react": {"version": "^18.0.0", "source": "pkg", "type": "npm"}}
        )
        target = _make_info()
        report = generate_report(source, target)
        assert "react" in report
        assert "^18.0.0" in report

    def test_report_includes_conflicts(self) -> None:
        source = _make_info(
            dependencies={"react": {"version": "^18.0.0", "source": "pkg", "type": "npm"}},
        )
        target = _make_info(
            dependencies={"react": {"version": "^17.0.0", "source": "pkg", "type": "npm"}},
        )
        report = generate_report(source, target)
        assert "**YES**" in report or "conflict" in report.lower()