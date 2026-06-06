"""Tests for AetherFusion planner module and plan reporters."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.planner.fusion_planner import generate_fusion_plan
from aetherfusion.reporter.plan_markdown_reporter import generate_plan_report
from aetherfusion.reporter.plan_json_reporter import generate_plan_json, write_plan_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_map_json(candidates: list[dict] | None = None, conflicts: dict | None = None) -> str:
    """Create a minimal but valid JSON map string for testing."""
    data = {
        "report_metadata": {
            "tool": "AetherFusion",
            "version": "0.1.5",
            "generated_at": "2026-06-06T00:00:00",
            "schema_version": "0.1.5",
        },
        "projects": {
            "source": {
                "name": "project-b",
                "path": "/tmp/project-b",
                "file_count": 10,
                "directory_count": 3,
                "config_files": {"package.json": "node"},
                "entry_files": ["src/index.tsx"],
                "core_directories": ["src"],
                "dependencies": [],
                "scripts": {},
                "tech_stack": ["React", "TypeScript"],
                "git_status": "clean",
                "git_branch": "main",
                "git_changed_files": [],
            },
            "target": {
                "name": "project-a",
                "path": "/tmp/project-a",
                "file_count": 15,
                "directory_count": 5,
                "config_files": {"package.json": "node"},
                "entry_files": ["src/index.tsx"],
                "core_directories": ["src"],
                "dependencies": [],
                "scripts": {},
                "tech_stack": ["React", "TypeScript"],
                "git_status": "clean",
                "git_branch": "main",
                "git_changed_files": [],
            },
        },
        "tech_stack": {
            "source_stack": ["React"],
            "target_stack": ["React"],
            "shared": ["React"],
            "unique_to_source": [],
            "unique_to_target": [],
        },
        "dependencies": {
            "common": [],
            "unique_to_source": [],
            "unique_to_target": [],
            "version_conflicts": [],
        },
        "structure": {
            "common_directories": ["src"],
            "unique_to_source": [],
            "unique_to_target": [],
        },
        "fusible_modules": [],
        "conflicts": conflicts or {
            "version_conflicts": [],
            "name_conflicts": [],
            "script_conflicts": [],
            "entry_conflicts": [],
        },
        "fusion_plan_candidates": candidates or [
            {
                "module_name": "components",
                "module_type": "components",
                "source_paths": ["/tmp/project-b/src/components"],
                "target_paths": ["/tmp/project-a/src/components"],
                "value_score": 90.0,
                "portability_score": 75.0,
                "conflict_score": 50.0,
                "priority_score": 135.0,
                "risk_level": "medium",
                "reason": "shared module with conflicts",
                "recommended_action": "manual_review",
            },
        ],
        "recommendations": [],
        "git_status": {
            "source": {"status": "clean", "branch": "main", "changed_files": [], "error_message": None},
            "target": {"status": "clean", "branch": "main", "changed_files": [], "error_message": None},
        },
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Fusion Planner Tests
# ---------------------------------------------------------------------------

class TestFusionPlanner:
    """Test the generate_fusion_plan function."""

    def test_plan_successful_for_existing_module(self) -> None:
        """Generating a plan for a module that exists in candidates should succeed."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "components")
            assert plan["module_name"] == "components"
            assert plan["plan_version"] is not None
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_plan_missing_module_raises_valueerror(self) -> None:
        """Requesting a plan for a non-existent module must raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            with pytest.raises(ValueError, match="not found"):
                generate_fusion_plan(Path(map_path), "nonexistent_module")
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_plan_missing_map_file_raises_filenotfound(self) -> None:
        """Requesting a plan with a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            generate_fusion_plan(Path("/nonexistent/path/map.json"), "components")

    def test_plan_contains_required_top_fields(self) -> None:
        """Plan dict must contain all required top-level fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "components")
            required = (
                "plan_version", "module_name", "module_type",
                "source_module_path", "target_match_path",
                "risk_level", "strategy", "score_summary",
                "ordered_steps", "required_human_decisions",
                "blocked_actions", "next_recommended_command",
            )
            for key in required:
                assert key in plan, f"Missing top-level field: {key}"
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_ordered_steps_have_required_actions(self) -> None:
        """ordered_steps must cover the five specified actions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "components")
            steps = plan["ordered_steps"]
            actions = {s["action"] for s in steps}
            required_actions = {
                "inspect_same_named_files",
                "copy_non_conflicting_files",
                "review_import_dependencies",
                "check_config_requirements",
                "prepare_dry_run_patch",
            }
            assert required_actions <= actions, f"Missing actions: {required_actions - actions}"
            # Steps must be ordered 1-5
            step_numbers = [s["step"] for s in steps]
            assert step_numbers == [1, 2, 3, 4, 5]
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_required_human_decisions_present(self) -> None:
        """required_human_decisions must cover the four decision categories."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "components")
            decisions = plan["required_human_decisions"]
            decision_ids = {d["decision_id"] for d in decisions}
            required_ids = {
                "same_named_files",
                "dependency_updates",
                "route_integration",
                "preserve_structure",
            }
            assert required_ids <= decision_ids, f"Missing decisions: {required_ids - decision_ids}"
            # Each decision must have question, context, options
            for d in decisions:
                assert "question" in d
                assert "context" in d
                assert "options" in d
                assert isinstance(d["options"], list) and len(d["options"]) > 0
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_blocked_actions_present(self) -> None:
        """blocked_actions must contain the five blocking statements."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "components")
            blocked = plan["blocked_actions"]
            assert len(blocked) == 5
            # Each must mention a key blocking constraint
            blocked_text = " ".join(blocked).lower()
            assert "not modify" in blocked_text
            assert "overwrite" in blocked_text
            assert "dependency" in blocked_text
            assert "build" in blocked_text or "test" in blocked_text
            assert "network" in blocked_text
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_plan_with_different_risk_level(self) -> None:
        """Plan should reflect the risk level from the candidate."""
        candidates = [
            {
                "module_name": "engines",
                "module_type": "engines",
                "source_paths": ["/tmp/project-b/src/engines"],
                "target_paths": [],
                "value_score": 90.0,
                "portability_score": 60.0,
                "conflict_score": 70.0,
                "priority_score": 77.1,
                "risk_level": "high",
                "reason": "high risk",
                "recommended_action": "review_and_replan",
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json(candidates=candidates))
            map_path = f.name

        try:
            plan = generate_fusion_plan(Path(map_path), "engines")
            assert plan["risk_level"] == "high"
            assert plan["strategy"] == "review_and_replan"
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_error_message_includes_available_modules(self) -> None:
        """When module is not found, the error must list available modules."""
        candidates = [
            {
                "module_name": "utils",
                "module_type": "utils",
                "source_paths": [],
                "target_paths": ["/tmp/project-a/src/utils"],
                "value_score": 80.0,
                "portability_score": 100.0,
                "conflict_score": 20.0,
                "priority_score": 400.0,
                "risk_level": "low",
                "reason": "",
                "recommended_action": "copy_to_target",
            },
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json(candidates=candidates))
            map_path = f.name

        try:
            with pytest.raises(ValueError, match="Available modules: utils"):
                generate_fusion_plan(Path(map_path), "components")
        finally:
            Path(map_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Plan Markdown Reporter Tests
# ---------------------------------------------------------------------------

class TestPlanMarkdownReporter:
    """Test the generate_plan_report function."""

    def _get_plan(self) -> dict:
        """Get a real plan dict via generate_fusion_plan."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(_make_map_json())
            map_path = f.name
        try:
            return generate_fusion_plan(Path(map_path), "components")
        finally:
            Path(map_path).unlink(missing_ok=True)

    def test_markdown_plan_generates_successfully(self) -> None:
        """Markdown plan should be generated without errors."""
        plan = self._get_plan()
        report = generate_plan_report(plan)
        assert isinstance(report, str)
        assert len(report) > 100
        assert "AetherFusion Plan" in report
        assert "components" in report

    def test_markdown_contains_score_summary(self) -> None:
        """Markdown should include the score summary section."""
        plan = self._get_plan()
        report = generate_plan_report(plan)
        assert "Score Summary" in report
        assert "Value Score" in report
        assert "Priority Score" in report

    def test_markdown_contains_ordered_steps(self) -> None:
        """Markdown should contain all five ordered steps."""
        plan = self._get_plan()
        report = generate_plan_report(plan)
        assert "Ordered Steps" in report
        assert "inspect_same_named_files" in report
        assert "copy_non_conflicting_files" in report
        assert "review_import_dependencies" in report
        assert "check_config_requirements" in report
        assert "prepare_dry_run_patch" in report

    def test_markdown_contains_human_decisions(self) -> None:
        """Markdown should contain the human decisions section."""
        plan = self._get_plan()
        report = generate_plan_report(plan)
        assert "Required Human Decisions" in report
        assert "same_named_files" in report or "Same-named" in report

    def test_markdown_contains_blocked_actions(self) -> None:
        """Markdown should list all blocked actions."""
        plan = self._get_plan()
        report = generate_plan_report(plan)
        assert "Blocked Actions" in report
        assert "not modify" in report.lower()
        assert "overwrite" in report.lower()

    def test_error_plan_markdown(self) -> None:
        """Even an error plan should produce valid Markdown explaining the error."""
        # Simulate an empty plan (module not found scenario handled at higher level)
        error_plan = {
            "plan_version": "0.2.0",
            "module_name": "nonexistent",
            "module_type": "unknown",
            "source_module_path": None,
            "target_match_path": None,
            "risk_level": "unknown",
            "strategy": "n/a — module not found",
            "score_summary": {},
            "ordered_steps": [],
            "required_human_decisions": [
                {
                    "decision_id": "module_not_found",
                    "question": "The requested module was not found in this project map.",
                    "context": "Please verify the module name and regenerate the map if needed.",
                    "options": [],
                    "is_blocking": True,
                }
            ],
            "blocked_actions": ["Cannot generate plan for non-existent module."],
            "next_recommended_command": "python -m aetherfusion scan --json ...",
        }
        report = generate_plan_report(error_plan)
        assert "nonexistent" in report
        assert "not found" in report.lower()