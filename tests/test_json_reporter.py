"""Tests for AetherFusion JSON reporter module."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.scanner.project_analyzer import ProjectAnalyzer, ProjectInfo
from aetherfusion.reporter.json_reporter import generate_json_map, write_json_map


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


class TestJsonReporter:
    """Verify the JSON map structure and content."""

    def test_json_generates_successfully(self) -> None:
        """JSON map should be produced without errors."""
        source = _make_info(
            name="proj-b",
            tech_stack=["Node.js", "React"],
            file_count=10,
            dir_count=3,
        )
        target = _make_info(
            name="proj-a",
            tech_stack=["Node.js", "React", "Python"],
            file_count=15,
            dir_count=5,
        )
        data = generate_json_map(source, target)
        assert isinstance(data, dict)
        assert json.dumps(data)  # must be JSON serializable

    def test_report_metadata_present(self) -> None:
        """Top-level report_metadata must contain required fields."""
        data = generate_json_map(_make_info(), _make_info())
        meta = data["report_metadata"]
        for key in ("tool", "version", "generated_at", "schema_version"):
            assert key in meta
        assert meta["tool"] == "AetherFusion"
        assert meta["schema_version"] == "0.1.5"

    def test_projects_section_has_required_keys(self) -> None:
        """Each project summary must include the canonical keys."""
        data = generate_json_map(
            _make_info(
                name="proj-b",
                config_files_detected={"package.json": "node"},
                entry_files=["src/index.tsx"],
                scripts={"dev": "vite"},
                dependencies={"react": {"version": "^18.0.0", "source": "pkg", "type": "npm"}},
                file_count=5,
                dir_count=2,
            ),
            _make_info(),
        )
        source = data["projects"]["source"]
        required = (
            "name", "path", "file_count", "directory_count",
            "config_files", "entry_files", "core_directories",
            "dependencies", "scripts", "tech_stack",
            "git_status", "git_branch", "git_changed_files",
        )
        for key in required:
            assert key in source

    def test_tech_stack_section_complete(self) -> None:
        data = generate_json_map(
            _make_info(tech_stack=["React", "Vite"]),
            _make_info(tech_stack=["React", "Python"]),
        )
        ts = data["tech_stack"]
        assert "shared" in ts
        assert "unique_to_source" in ts
        assert "unique_to_target" in ts
        assert ts["shared"] == ["React"]
        assert "Vite" in ts["unique_to_source"]

    def test_dependencies_section_has_all_subkeys(self) -> None:
        data = generate_json_map(
            _make_info(dependencies={
                "react": {"version": "^18.0.0", "source": "pkg", "type": "npm"},
            }),
            _make_info(dependencies={
                "react": {"version": "^17.0.0", "source": "pkg", "type": "npm"},
            }),
        )
        deps = data["dependencies"]
        for key in ("common", "unique_to_source", "unique_to_target", "version_conflicts"):
            assert key in deps, f"Missing key: {key}"
        assert len(deps["common"]) == 1
        assert deps["common"][0]["conflict"] is True
        assert len(deps["version_conflicts"]) == 1

    def test_fusion_plan_candidates_exist(self) -> None:
        """JSON must include fusion_plan_candidates with scoring."""
        data = generate_json_map(
            _make_info(
                name="proj-b",
                fusible_modules={
                    "components": ["/proj-b/src/components"],
                    "utils": ["/proj-b/src/utils"],
                },
            ),
            _make_info(
                name="proj-a",
                fusible_modules={
                    "components": ["/proj-a/src/components"],
                    "hooks": ["/proj-a/src/hooks"],
                },
            ),
        )
        candidates = data["fusion_plan_candidates"]
        assert isinstance(candidates, list)
        assert len(candidates) > 0

        # Check required fields on first candidate
        first = candidates[0]
        for key in (
            "module_name", "module_type", "source_paths", "target_paths",
            "value_score", "portability_score", "conflict_score",
            "priority_score", "risk_level", "reason", "recommended_action",
        ):
            assert key in first, f"fusion_plan_candidate missing key: {key}"

    def test_fusion_candidate_scores_in_range(self) -> None:
        """All score fields must be in 0-100 range (except priority)."""
        data = generate_json_map(
            _make_info(fusible_modules={"components": ["/p/src/components"]}),
            _make_info(fusible_modules={"components": ["/q/src/components"]}),
        )
        for c in data["fusion_plan_candidates"]:
            assert 0 <= c["value_score"] <= 100
            assert 0 <= c["portability_score"] <= 100
            assert 0 <= c["conflict_score"] <= 100
            assert c["risk_level"] in ("low", "medium", "high")
            assert isinstance(c["reason"], str) and len(c["reason"]) > 0

    def test_write_json_map_writes_valid_file(self) -> None:
        """write_json_map must write valid JSON that can be re-read."""
        data = generate_json_map(
            _make_info(name="proj-b", tech_stack=["React"]),
            _make_info(name="proj-a", tech_stack=["Python"]),
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "test-map.json"
            write_json_map(out, data)
            assert out.is_file()
            reread = json.loads(out.read_text(encoding="utf-8"))
            assert reread["projects"]["source"]["name"] == "proj-b"
            assert "Vite" in reread["tech_stack"]["unique_to_source"] or "React" in reread["tech_stack"]["source_stack"]

    def test_git_status_included(self) -> None:
        """JSON map must include git_status section."""
        data = generate_json_map(_make_info(), _make_info())
        gs = data["git_status"]
        assert "source" in gs
        assert "target" in gs
        for side in ("source", "target"):
            for key in ("status", "branch", "changed_files"):
                assert key in gs[side]

    def test_structure_section_present(self) -> None:
        data = generate_json_map(
            _make_info(core_directories=["src", "lib"]),
            _make_info(core_directories=["src", "tests"]),
        )
        st = data["structure"]
        assert "common_directories" in st
        assert st["common_directories"] == ["src"]