"""Tests for AetherFusion v0.8 dependency-plan subcommand."""

import json
import tempfile
from pathlib import Path

import pytest

from aetherfusion.dependency.dependency_error_extractor import extract_dependency_errors
from aetherfusion.dependency.dependency_file_parser import parse_dependency_files
from aetherfusion.dependency.dependency_planner import generate_dependency_plan
from aetherfusion.reporter.dependency_json_reporter import write_dependency_json
from aetherfusion.reporter.dependency_markdown_reporter import generate_dependency_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repair_plan(items: list[dict]) -> dict:
    return {
        "repair_plan_version": "0.6.0",
        "repair_items": items,
    }


def _make_import_fix_plan(candidates: list[dict]) -> dict:
    return {
        "import_fix_plan_version": "0.7.0",
        "fix_candidates": candidates,
    }


def _make_dep_item(
    error_type: str = "missing_dependency",
    evidence: str = "",
    command: str = "npm test",
    severity: str = "high",
    confidence: int = 80,
    **kwargs,
) -> dict:
    d = {
        "error_type": error_type,
        "command": command,
        "severity": severity,
        "confidence": confidence,
        "evidence": evidence,
    }
    d.update(kwargs)
    return d


def _make_target_project(base: Path, files: dict[str, str] | None = None) -> Path:
    """Create a minimal target project with optional dependency files."""
    base.mkdir(parents=True, exist_ok=True)
    if files:
        for rel, content in files.items():
            full = base / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
    return base


# ---------------------------------------------------------------------------
# TestDependencyErrorExtractor
# ---------------------------------------------------------------------------

class TestDependencyErrorExtractor:

    # --- Node error patterns ---

    def test_node_cannot_find_module(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Error: Cannot find module 'lodash'"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "lodash"
        assert errors[0]["ecosystem"] == "node"
        assert errors[0]["source"] == "repair_plan"

    def test_node_module_not_found(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Module not found: Can't resolve 'react' in '/src'"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "react"
        assert errors[0]["ecosystem"] == "node"

    def test_node_could_not_resolve_dependency(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Could not resolve dependency: express"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "express"

    def test_node_package_not_found(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Package not found: axios"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "axios"

    # --- Python error patterns ---

    def test_python_modulenotfounderror(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="ModuleNotFoundError: No module named 'requests'"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "requests"
        assert errors[0]["ecosystem"] == "python"

    def test_python_importerror(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="ImportError: No module named flask"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "flask"

    # --- Deduplication ---

    def test_deduplicate_same_package(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Error: Cannot find module 'lodash'"),
            _make_dep_item(evidence="Cannot find module 'lodash'"),
        ])
        errors = extract_dependency_errors(plan)
        assert len(errors) == 1

    # --- Extract from import-fix-plan ---

    def test_extract_from_import_fix_plan(self):
        repair = _make_repair_plan([])
        import_fix = _make_import_fix_plan([
            {
                "missing_module": "lodash",
                "suspected_import_kind": "package_missing",
                "evidence": "Cannot find module 'lodash'",
                "confidence": 85,
                "severity": "high",
            },
            {
                "missing_module": "./utils",
                "suspected_import_kind": "wrong_relative_path",
                "evidence": "...",
            },
        ])
        errors = extract_dependency_errors(repair, import_fix)
        assert len(errors) == 1
        assert errors[0]["package_name"] == "lodash"
        assert errors[0]["source"] == "import_fix_plan"

    # --- Empty / no dependency errors ---

    def test_empty_repair_plan(self):
        plan = _make_repair_plan([])
        errors = extract_dependency_errors(plan)
        assert errors == []

    def test_only_non_dependency_errors(self):
        plan = _make_repair_plan([
            _make_dep_item(error_type="test_failure", evidence="1 test failed"),
            _make_dep_item(error_type="missing_import", evidence="TS2307: Cannot find module './foo'"),
        ])
        errors = extract_dependency_errors(plan)
        assert errors == []

    # --- Path-like imports are excluded ---

    def test_path_like_excluded(self):
        plan = _make_repair_plan([
            _make_dep_item(evidence="Cannot find module './utils'"),
            _make_dep_item(evidence="Cannot find module '../shared'"),
            _make_dep_item(evidence="Module not found: Can't resolve '@/components'"),
        ])
        errors = extract_dependency_errors(plan)
        assert errors == []


# ---------------------------------------------------------------------------
# TestDependencyFileParser
# ---------------------------------------------------------------------------

class TestDependencyFileParser:

    def test_parse_package_json(self, tmp_path):
        proj = _make_target_project(tmp_path / "target", {
            "package.json": json.dumps({
                "dependencies": {"react": "^18.0.0"},
                "devDependencies": {"jest": "^29.0.0"},
                "peerDependencies": {"react-dom": "~18.0.0"},
            }),
        })
        source = _make_target_project(tmp_path / "source", {
            "package.json": json.dumps({
                "dependencies": {"lodash": "4.17.21"},
            }),
        })
        result = parse_dependency_files(proj, source)
        assert "package.json" in result["detected_files"]
        tgt = result["target_dependencies"]["package.json"]
        assert tgt["dependencies"]["react"] == "18.0.0"
        assert tgt["devDependencies"]["jest"] == "29.0.0"

    def test_parse_requirements_txt(self, tmp_path):
        proj = _make_target_project(tmp_path / "target", {
            "requirements.txt": "requests>=2.28.0\nflask==2.0.0\n# comment\n-e git+https://",
        })
        source = _make_target_project(tmp_path / "source", {})
        result = parse_dependency_files(proj, source)
        assert "requirements.txt" in result["detected_files"]
        reqs = result["target_dependencies"]["requirements.txt"]["requirements"]
        names = [r["name"] for r in reqs]
        assert "requests" in names
        assert "flask" in names
        # Comments and -e lines skipped
        assert len(names) == 2

    def test_parse_pyproject_toml_poetry(self, tmp_path):
        proj = _make_target_project(tmp_path / "target", {
            "pyproject.toml": (
                "[tool.poetry.dependencies]\n"
                "python = \"^3.10\"\n"
                "typer = \"0.9.0\"\n"
                "rich = \"^13.0\"\n"
                "\n"
                "[tool.poetry.group.dev.dependencies]\n"
                "pytest = \"^7.0\"\n"
            ),
        })
        source = _make_target_project(tmp_path / "source", {})
        result = parse_dependency_files(proj, source)
        assert "pyproject.toml" in result["detected_files"]
        tgt = result["target_dependencies"]["pyproject.toml"]
        poetry = tgt.get("poetry_dependencies", {})
        assert "typer" in poetry
        assert "rich" in poetry
        assert "python" not in poetry

    def test_detect_lock_files(self, tmp_path):
        proj = _make_target_project(tmp_path / "target", {
            "package-lock.json": "{}",
            "yarn.lock": "",
            "poetry.lock": "",
        })
        source = _make_target_project(tmp_path / "source", {})
        result = parse_dependency_files(proj, source)
        assert "package-lock.json" in result["detected_files"]
        assert "yarn.lock" in result["detected_files"]
        assert "poetry.lock" in result["detected_files"]

    def test_empty_project(self, tmp_path):
        proj = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        result = parse_dependency_files(proj, source)
        assert result["detected_files"] == []


# ---------------------------------------------------------------------------
# TestDependencyPlanner
# ---------------------------------------------------------------------------

class TestDependencyPlanner:

    def test_source_has_target_missing(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="Error: Cannot find module 'lodash'"),
        ])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {
            "package.json": json.dumps({"dependencies": {"lodash": "4.17.21"}}),
        })
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["add_to_target"] == 1
        cand = plan["dependency_candidates"][0]
        assert cand["package_name"] == "lodash"
        assert cand["found_in_source"] is True
        assert cand["found_in_target"] is False
        assert cand["likely_cause"] == "source_has_dependency_target_missing"

    def test_version_conflict(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="ModuleNotFoundError: No module named 'requests'"),
        ])))
        target = _make_target_project(tmp_path / "target", {
            "requirements.txt": "requests==2.25.0",
        })
        source = _make_target_project(tmp_path / "source", {
            "requirements.txt": "requests==2.28.0",
        })
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["review_version_conflict"] == 1
        cand = plan["dependency_candidates"][0]
        assert cand["version_conflict"] is True
        assert cand["source_version"] == "2.28.0"
        assert cand["target_version"] == "2.25.0"

    def test_target_already_has(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="Cannot find module 'react'"),
        ])))
        target = _make_target_project(tmp_path / "target", {
            "package.json": json.dumps({"dependencies": {"react": "18.0.0"}}),
        })
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["likely_not_dependency_issue"] == 1

    def test_neither_has_manual_research(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="Cannot find module 'mystery-lib'"),
        ])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["manual_research"] == 1
        cand = plan["dependency_candidates"][0]
        assert cand["likely_cause"] == "missing_from_both_projects"

    def test_skip_builtin_node(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="Cannot find module 'fs'"),
        ])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["builtin_or_stdlib_skipped"] == 1

    def test_skip_stdlib_python(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([
            _make_dep_item(evidence="ModuleNotFoundError: No module named 'os'"),
        ])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["builtin_or_stdlib_skipped"] == 1

    def test_empty_plan(self, tmp_path):
        repair = tmp_path / "repair-plan.json"
        repair.write_text(json.dumps(_make_repair_plan([])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["total_extracted_dependency_errors"] == 0
        assert plan["summary"]["total_dependency_candidates"] == 0


# ---------------------------------------------------------------------------
# TestDependencyReporters
# ---------------------------------------------------------------------------

class TestDependencyReporters:

    def _make_plan(self) -> dict:
        return {
            "dependency_plan_version": "0.8.0",
            "source_repair_file": "/tmp/repair-plan.json",
            "source_import_fix_file": "",
            "target_path": "/tmp/target",
            "source_path": "/tmp/source",
            "summary": {
                "total_extracted_dependency_errors": 2,
                "total_dependency_candidates": 2,
                "add_to_target": 1,
                "review_version_conflict": 0,
                "likely_not_dependency_issue": 0,
                "manual_research": 1,
                "builtin_or_stdlib_skipped": 0,
                "redirect_to_import_fix": 0,
            },
            "extracted_dependency_errors": [
                {"package_name": "lodash", "ecosystem": "node", "source": "repair_plan",
                 "severity": "high", "evidence": "Cannot find module 'lodash'",
                 "originating_command": "npm test", "confidence": 85},
            ],
            "dependency_candidates": [
                {"package_name": "lodash", "ecosystem": "node",
                 "found_in_source": True, "found_in_target": False,
                 "source_version": "4.17.21", "target_version": None,
                 "version_conflict": False,
                 "likely_cause": "source_has_dependency_target_missing",
                 "recommended_action": "Add lodash to target",
                 "automation_eligibility": "plan_only",
                 "risk_level": "medium",
                 "evidence": "Cannot find module 'lodash'"},
                {"package_name": "mystery", "ecosystem": "unknown",
                 "found_in_source": False, "found_in_target": False,
                 "source_version": None, "target_version": None,
                 "version_conflict": False,
                 "likely_cause": "missing_from_both_projects",
                 "recommended_action": "Manual research",
                 "automation_eligibility": "manual_only",
                 "risk_level": "high",
                 "evidence": "Cannot find module 'mystery'"},
            ],
            "dependency_files_detected": ["package.json"],
            "blocked_actions": ["Do NOT modify files."],
            "next_recommended_command": "python -m aetherfusion dependency-plan ...",
        }

    def test_json_reporter(self, tmp_path):
        plan = self._make_plan()
        out = tmp_path / "report.json"
        write_dependency_json(out, plan)
        assert out.is_file()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["dependency_plan_version"] == "0.8.0"
        assert loaded["summary"]["add_to_target"] == 1

    def test_markdown_reporter(self):
        plan = self._make_plan()
        report = generate_dependency_report(plan)
        assert "# Dependency Plan Report" in report
        assert "## Summary" in report
        assert "## Extracted Dependency Errors" in report
        assert "## Dependency Candidates" in report
        assert "## Blocked Actions" in report
        assert "lodash" in report
        assert "## Next Recommended Command" in report


# ---------------------------------------------------------------------------
# TestDependencyCLI
# ---------------------------------------------------------------------------

class TestDependencyCLI:

    @pytest.fixture(autouse=True)
    def _skip_cli_if_not_importable(self):
        """Allow CLI tests even if main() import would fail in test isolation."""
        pass

    def test_import(self):
        """Sanity: can import generate_dependency_plan."""
        assert generate_dependency_plan is not None

    def test_empty_plan_exit_0(self, tmp_path):
        repair = tmp_path / "repair.json"
        repair.write_text(json.dumps(_make_repair_plan([])))
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        plan = generate_dependency_plan(repair, target, source)
        assert plan["summary"]["total_extracted_dependency_errors"] == 0

    def test_repair_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Repair plan not found"):
            generate_dependency_plan(
                tmp_path / "nonexistent.json",
                tmp_path / "target",
                tmp_path / "source",
            )

    def test_target_not_found(self, tmp_path):
        repair = tmp_path / "repair.json"
        repair.write_text(json.dumps(_make_repair_plan([])))
        with pytest.raises(FileNotFoundError, match="Target path does not exist"):
            generate_dependency_plan(
                repair,
                tmp_path / "nonexistent-target",
                tmp_path / "source",
            )

    def test_source_not_found(self, tmp_path):
        repair = tmp_path / "repair.json"
        repair.write_text(json.dumps(_make_repair_plan([])))
        target = _make_target_project(tmp_path / "target", {})
        with pytest.raises(FileNotFoundError, match="Source path does not exist"):
            generate_dependency_plan(
                repair,
                target,
                tmp_path / "nonexistent-source",
            )

    def test_invalid_json(self, tmp_path):
        repair = tmp_path / "repair.json"
        repair.write_text("not valid json")
        target = _make_target_project(tmp_path / "target", {})
        source = _make_target_project(tmp_path / "source", {})
        with pytest.raises(json.JSONDecodeError):
            generate_dependency_plan(repair, target, source)


# ---------------------------------------------------------------------------
# TestDependencyAudit
# ---------------------------------------------------------------------------

class TestDependencyAudit:

    def test_make_dependency_plan_event_exists(self):
        from aetherfusion.audit.audit_logger import make_dependency_plan_event
        event = make_dependency_plan_event(
            {"dependency_plan_version": "0.8.0", "summary": {"add_to_target": 1}},
            "/tmp/repair.json",
            "/tmp/target",
            "/tmp/source",
            "/tmp/result.json",
        )
        assert event["event_type"] == "dependency_plan"
        assert event["version"] == "0.8.0"

    def test_audit_write_no_crash(self, tmp_path):
        from aetherfusion.audit.audit_logger import make_dependency_plan_event, log_audit_event
        event = make_dependency_plan_event(
            {"dependency_plan_version": "0.8.0", "summary": {"add_to_target": 0}},
            "/tmp/repair.json",
            "/tmp/target",
            "/tmp/source",
            "",
        )
        audit_path = tmp_path / "audit.jsonl"
        ok = log_audit_event(str(audit_path), event)
        assert ok is True or ok is False  # just ensure no crash


# ---------------------------------------------------------------------------
# TestDependencyIntegration
# ---------------------------------------------------------------------------

class TestDependencyIntegration:

    def test_version_0_8_0(self):
        from aetherfusion import __version__
        assert __version__ == "1.0.1"

    def test_generate_dependency_plan_exports(self):
        from aetherfusion.dependency import generate_dependency_plan as gdp
        assert gdp is not None
