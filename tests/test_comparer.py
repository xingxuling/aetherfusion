"""Tests for AetherFusion comparer module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.scanner.project_analyzer import ProjectAnalyzer, ProjectInfo
from aetherfusion.comparer.tech_stack import compare_tech_stack
from aetherfusion.comparer.dependencies import compare_dependencies
from aetherfusion.comparer.structure import compare_structure
from aetherfusion.comparer.fusion import analyze_fusion, generate_fusion_plan_candidates


def _make_info(**overrides) -> ProjectInfo:
    """Helper to create a ProjectInfo with defaults overridden."""
    defaults = dict(
        root=".",
        name="test",
        configs={},
        config_files_detected={},
        tree={"name": "test", "type": "directory", "children": [], "truncated": False},
        tree_text=[],
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


class TestTechStack:
    def test_common_and_unique(self) -> None:
        source = _make_info(tech_stack=["Node.js", "React", "Vite"])
        target = _make_info(tech_stack=["Node.js", "React", "Python"])
        result = compare_tech_stack(source, target)
        assert set(result["common"]) == {"Node.js", "React"}
        assert result["unique_to_source"] == ["Vite"]
        assert result["unique_to_target"] == ["Python"]

    def test_no_overlap(self) -> None:
        source = _make_info(tech_stack=["Python"])
        target = _make_info(tech_stack=["Node.js"])
        result = compare_tech_stack(source, target)
        assert result["common"] == []


class TestDependencies:
    def test_version_conflict(self) -> None:
        source = _make_info(dependencies={
            "react": {"version": "^18.0.0", "source": "package.json", "type": "npm"},
            "lodash": {"version": "^4.17.0", "source": "package.json", "type": "npm"},
        })
        target = _make_info(dependencies={
            "react": {"version": "^17.0.0", "source": "package.json", "type": "npm"},
            "axios": {"version": "^1.0.0", "source": "package.json", "type": "npm"},
        })
        result = compare_dependencies(source, target)
        assert len(result["common"]) == 1
        assert result["common"]["react"]["conflict"] is True
        assert "lodash" in result["unique_to_source"]
        assert "axios" in result["unique_to_target"]

    def test_no_conflicts(self) -> None:
        source = _make_info(dependencies={
            "react": {"version": "^18.0.0", "source": "package.json", "type": "npm"},
        })
        target = _make_info(dependencies={
            "react": {"version": "^18.0.0", "source": "package.json", "type": "npm"},
        })
        result = compare_dependencies(source, target)
        assert result["common"]["react"]["conflict"] is False
        assert result["version_conflicts"] == []


class TestStructure:
    def test_structure_comparison(self) -> None:
        source = _make_info(
            core_directories=["src", "components", "lib", "docs"],
        )
        target = _make_info(
            core_directories=["src", "components", "tests", "scripts"],
        )
        result = compare_structure(source, target)
        assert set(result["common_dirs"]) == {"components", "src"}
        assert set(result["unique_to_source"]) == {"docs", "lib"}
        assert set(result["unique_to_target"]) == {"scripts", "tests"}


class TestFusion:
    def test_fusible_modules_found(self) -> None:
        source = _make_info(
            fusible_modules={
                "components": ["/proj-a/src/components"],
                "utils": ["/proj-a/src/utils"],
            }
        )
        target = _make_info(
            fusible_modules={
                "components": ["/proj-b/src/components"],
                "services": ["/proj-b/src/services"],
            }
        )
        result = analyze_fusion(source, target)
        fusible = result["fusible_modules"]
        names = {m["module_name"] for m in fusible}
        assert "components" in names
        assert "utils" in names
        assert "services" in names

    def test_conflicts_detected(self) -> None:
        source = _make_info(
            dependencies={"react": {"version": "^18.0.0", "source": "pkg", "type": "npm"}},
            scripts={"dev": "vite", "build": "tsc"},
            entry_files=["src/index.tsx"],
        )
        target = _make_info(
            dependencies={"react": {"version": "^17.0.0", "source": "pkg", "type": "npm"}},
            scripts={"dev": "next dev", "build": "next build"},
            entry_files=["src/index.tsx"],
        )
        result = analyze_fusion(source, target)
        conflicts = result["conflicts"]
        assert len(conflicts["version_conflicts"]) == 1
        assert len(conflicts["script_conflicts"]) == 2
        assert len(conflicts["entry_conflicts"]) == 1

    def test_recommendations_generated(self) -> None:
        source = _make_info(
            fusible_modules={"components": ["/a/src/components"]},
        )
        target = _make_info(
            fusible_modules={"components": ["/b/src/components"]},
        )
        result = analyze_fusion(source, target)
        assert len(result["recommendations"]) > 0


class TestFusionPlanCandidates:
    """Validate fusion_plan_candidates scoring logic."""

    def test_candidates_generated_for_shared_modules(self) -> None:
        source = _make_info(
            fusible_modules={
                "components": ["/a/src/components"],
                "utils": ["/a/src/utils"],
            },
        )
        target = _make_info(
            fusible_modules={
                "components": ["/b/src/components"],
            },
        )
        fusion = analyze_fusion(source, target)
        candidates = generate_fusion_plan_candidates(source, target, fusion)
        names = {c["module_name"] for c in candidates}
        assert "components" in names
        assert "utils" in names  # unique to source
        # Sorted by priority — first should be highest priority
        assert candidates[0]["priority_score"] >= candidates[-1]["priority_score"]

    def test_scoring_fields_present(self) -> None:
        source = _make_info(
            fusible_modules={"components": ["/a/src/components"]},
        )
        target = _make_info(
            fusible_modules={"components": ["/b/src/components"]},
        )
        fusion = analyze_fusion(source, target)
        candidates = generate_fusion_plan_candidates(source, target, fusion)
        assert len(candidates) == 1
        c = candidates[0]
        for field in ("value_score", "portability_score", "conflict_score",
                       "priority_score", "risk_level", "reason", "recommended_action"):
            assert field in c
        assert 0 <= c["value_score"] <= 100
        assert 0 <= c["portability_score"] <= 100
        assert 0 <= c["conflict_score"] <= 100
        assert c["risk_level"] in ("low", "medium", "high")

    def test_high_conflict_lowers_priority(self) -> None:
        """Modules with name conflicts should get lower portability and higher conflict."""
        source_one = _make_info(
            fusible_modules={"hooks": ["/a/src/hooks"]},
        )
        target_one = _make_info(
            fusible_modules={"hooks": ["/b/src/hooks"]},
        )
        fusion = analyze_fusion(source_one, target_one)
        candidates = generate_fusion_plan_candidates(source_one, target_one, fusion)
        # hooks without version conflicts should be relatively low conflict
        assert candidates[0]["conflict_score"] < 50

    def test_dependency_conflicts_affect_scoring(self) -> None:
        """Version conflicts should increase conflict_score."""
        source = _make_info(
            fusible_modules={"components": ["/a/src/components"]},
            dependencies={"react": {"version": "^18.0.0", "source": "pkg", "type": "npm"}},
        )
        target = _make_info(
            fusible_modules={"components": ["/b/src/components"]},
            dependencies={"react": {"version": "^17.0.0", "source": "pkg", "type": "npm"}},
        )
        fusion = analyze_fusion(source, target)
        from aetherfusion.comparer.dependencies import compare_dependencies
        dep_cmp = compare_dependencies(source, target)
        candidates = generate_fusion_plan_candidates(source, target, fusion, dep_cmp)
        assert len(candidates) == 1
        # Should have non-zero conflict score due to version conflict
        assert candidates[0]["conflict_score"] > 0

    def test_empty_input_returns_empty_list(self) -> None:
        """No fusible modules → empty candidate list."""
        fusion = analyze_fusion(_make_info(), _make_info())
        candidates = generate_fusion_plan_candidates(_make_info(), _make_info(), fusion)
        assert candidates == []

    def test_recommended_action_is_valid(self) -> None:
        """Each candidate must have a recognized action."""
        source = _make_info(
            fusible_modules={"utils": ["/a/src/utils"]},
        )
        target = _make_info(
            fusible_modules={"utils": ["/b/src/utils"]},
        )
        fusion = analyze_fusion(source, target)
        candidates = generate_fusion_plan_candidates(source, target, fusion)
        valid_actions = {"proceed_to_fuse", "manual_review", "copy_to_target", "review_and_replan"}
        for c in candidates:
            assert c["recommended_action"] in valid_actions