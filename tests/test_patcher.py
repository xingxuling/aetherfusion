"""Tests for AetherFusion patcher module and patch reporters."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.patcher.dry_run_patch_generator import generate_dry_run_patch
from aetherfusion.reporter.patch_markdown_reporter import generate_patch_report
from aetherfusion.reporter.patch_json_reporter import write_patch_json
from aetherfusion.reporter.diff_reporter import generate_diff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan_json(
    module_name: str = "components",
    source_module_path: str = "",
    target_match_path: str = "",
    risk_level: str = "medium",
    strategy: str = "manual_review",
) -> str:
    """Create a minimal but valid fusion plan JSON string for testing."""
    data = {
        "plan_version": "0.2.0",
        "module_name": module_name,
        "module_type": module_name,
        "source_module_path": source_module_path,
        "target_match_path": target_match_path,
        "source_project": {
            "name": "project-b",
            "path": source_module_path.rsplit(os.sep, 2)[0] if source_module_path else "",
        },
        "target_project": {
            "name": "project-a",
            "path": target_match_path.rsplit(os.sep, 2)[0] if target_match_path else "",
        },
        "risk_level": risk_level,
        "strategy": strategy,
        "score_summary": {
            "value_score": 90.0,
            "portability_score": 75.0,
            "conflict_score": 50.0,
            "priority_score": 135.0,
        },
        "ordered_steps": [],
        "required_human_decisions": [],
        "blocked_actions": [],
        "next_recommended_command": "",
    }
    return json.dumps(data)


def _make_dirs_and_files(base: str, files: dict[str, str]) -> None:
    """Create directories and files under base from {relpath: content} dict."""
    for relpath, content in files.items():
        fullpath = os.path.join(base, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        with open(fullpath, "w", encoding="utf-8") as f:
            f.write(content)


# ---------------------------------------------------------------------------
# DryRunPatchGenerator tests
# ---------------------------------------------------------------------------

class TestDryRunPatchGenerator:
    """Tests for generate_dry_run_patch."""

    def test_successful_patch_for_module_with_add_file(self, tmp_path):
        """source-only file is marked add_file."""
        source_dir = tmp_path / "source" / "components"
        target_dir = tmp_path / "target" / "components"
        _make_dirs_and_files(
            str(source_dir), {"Button.tsx": "export const Button = () => <button/>;\n"}
        )

        plan_path = tmp_path / "plan.json"
        plan_str = _make_plan_json(
            source_module_path=str(source_dir),
            target_match_path=str(target_dir),
        )
        plan_path.write_text(plan_str, encoding="utf-8")

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["mode"] == "dry_run"
        assert manifest["module_name"] == "components"
        assert manifest["summary"]["files_to_add"] == 1
        assert manifest["summary"]["files_conflicted"] == 0
        assert len(manifest["operations"]) == 1
        assert manifest["operations"][0]["type"] == "add_file"
        assert manifest["operations"][0]["relative_path"] == "Button.tsx"

    def test_conflict_same_name_detected(self, tmp_path):
        """Same-named file in both source and target → conflict_same_name."""
        source_dir = tmp_path / "source" / "components"
        target_dir = tmp_path / "target" / "components"
        _make_dirs_and_files(
            str(source_dir), {"Header.tsx": "// source header\n"}
        )
        _make_dirs_and_files(
            str(target_dir), {"Header.tsx": "// target header\n"}
        )

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(target_dir))
        )

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["summary"]["files_to_add"] == 0
        assert manifest["summary"]["files_conflicted"] == 1
        assert len(manifest["operations"]) == 1
        assert manifest["operations"][0]["type"] == "conflict_same_name"
        assert manifest["operations"][0]["relative_path"] == "Header.tsx"

    def test_mixed_add_and_conflict(self, tmp_path):
        """Source has one new file and one conflict."""
        source_dir = tmp_path / "source" / "components"
        target_dir = tmp_path / "target" / "components"
        _make_dirs_and_files(str(source_dir), {
            "Button.tsx": "// button\n",
            "Header.tsx": "// source header\n",
        })
        _make_dirs_and_files(str(target_dir), {
            "Header.tsx": "// target header\n",
        })

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(target_dir))
        )

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["summary"]["files_to_add"] == 1
        assert manifest["summary"]["files_conflicted"] == 1
        assert len(manifest["operations"]) == 2
        types = {op["type"] for op in manifest["operations"]}
        assert types == {"add_file", "conflict_same_name"}

    def test_skip_large_file(self, tmp_path):
        """Files > 1 MB are flagged skip_unsafe."""
        source_dir = tmp_path / "source" / "components"
        os.makedirs(str(source_dir), exist_ok=True)
        large_path = source_dir / "big.tsx"
        large_path.write_text("x" * 2_000_000, encoding="utf-8")  # ~2 MB

        target_dir = tmp_path / "target" / "components"
        os.makedirs(str(target_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(target_dir))
        )

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["summary"]["files_skipped"] == 1
        assert manifest["operations"][0]["type"] == "skip_unsafe"
        assert "exceeds" in manifest["operations"][0]["reason"].lower()

    def test_skip_binary_file(self, tmp_path):
        """Binary files are flagged skip_unsafe."""
        source_dir = tmp_path / "source" / "components"
        os.makedirs(str(source_dir), exist_ok=True)
        bin_path = source_dir / "image.png"
        bin_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100)

        target_dir = tmp_path / "target" / "components"
        os.makedirs(str(target_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(target_dir))
        )

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["summary"]["files_skipped"] >= 1
        skip_ops = [op for op in manifest["operations"] if op["type"] == "skip_unsafe"]
        assert any("binary" in op["reason"].lower() for op in skip_ops)

    def test_ignores_node_modules(self, tmp_path):
        """Files inside node_modules are excluded."""
        source_dir = tmp_path / "source" / "components"
        _make_dirs_and_files(str(source_dir), {
            "Button.tsx": "// button\n",
            "node_modules/dep/index.js": "// should be ignored\n",
        })

        target_dir = tmp_path / "target" / "components"
        os.makedirs(str(target_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(target_dir))
        )

        manifest = generate_dry_run_patch(plan_path)

        # Only Button.tsx should appear
        assert manifest["summary"]["files_to_add"] == 1
        rel_paths = [op["relative_path"] for op in manifest["operations"]]
        assert "node_modules/dep/index.js" not in rel_paths

    def test_target_not_exist_marks_all_as_add(self, tmp_path):
        """When target_match_path doesn't exist, all source files are add_file."""
        source_dir = tmp_path / "source" / "components"
        _make_dirs_and_files(str(source_dir), {
            "Foo.tsx": "// foo\n",
            "Bar.tsx": "// bar\n",
        })
        nonexistent = tmp_path / "nonexistent_target"

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(source_dir), target_match_path=str(nonexistent))
        )

        manifest = generate_dry_run_patch(plan_path)

        assert manifest["target_exists"] is False
        assert manifest["summary"]["files_to_add"] == 2
        assert manifest["summary"]["files_conflicted"] == 0

    def test_nonexistent_plan_file_raises(self, tmp_path):
        """FileNotFoundError for missing plan JSON."""
        plan_path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            generate_dry_run_patch(plan_path)

    def test_missing_source_module_path_raises(self, tmp_path):
        """ValueError when source_module_path is missing from plan."""
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(_make_plan_json(source_module_path=""))

        with pytest.raises(ValueError, match="source_module_path"):
            generate_dry_run_patch(plan_path)

    def test_source_module_does_not_exist_raises(self, tmp_path):
        """ValueError when source_module_path points to a nonexistent directory."""
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(tmp_path / "no_such_dir"))
        )

        with pytest.raises(ValueError, match="does not exist"):
            generate_dry_run_patch(plan_path)

    def test_invalid_json_in_plan_raises(self, tmp_path):
        """JSONDecodeError for malformed plan file."""
        plan_path = tmp_path / "plan.json"
        plan_path.write_text("not valid json {{{")

        with pytest.raises(json.JSONDecodeError):
            generate_dry_run_patch(plan_path)


# ---------------------------------------------------------------------------
# PatchMarkdownReporter tests
# ---------------------------------------------------------------------------

class TestPatchMarkdownReporter:
    """Tests for generate_patch_report."""

    def _make_manifest(self, **overrides) -> dict:
        manifest = {
            "patch_version": "0.3.0",
            "mode": "dry_run",
            "module_name": "components",
            "module_type": "components",
            "source_module_path": "/tmp/src/components",
            "target_match_path": "/tmp/tgt/components",
            "target_exists": True,
            "risk_level": "medium",
            "strategy": "manual_review",
            "summary": {
                "files_to_add": 1,
                "files_conflicted": 1,
                "files_skipped": 0,
                "dependency_updates_required": 0,
                "blocked_operations": 1,
            },
            "operations": [
                {
                    "type": "add_file",
                    "relative_path": "Card.tsx",
                    "source_absolute": "/tmp/src/components/Card.tsx",
                    "file_size_bytes": 100,
                    "resolution_required": False,
                    "blocked_in_dry_run": True,
                },
                {
                    "type": "conflict_same_name",
                    "relative_path": "Header.tsx",
                    "source_absolute": "/tmp/src/components/Header.tsx",
                    "target_absolute": "/tmp/tgt/components/Header.tsx",
                    "file_size_bytes": 200,
                    "resolution_required": True,
                    "blocked_in_dry_run": True,
                },
                {
                    "type": "skip_unsafe",
                    "relative_path": "big.png",
                    "reason": "Binary file",
                    "resolution_required": False,
                    "blocked_in_dry_run": True,
                },
            ],
            "blocked_actions": [
                "v0.3 dry-run only",
            ],
            "required_human_decisions": [],
            "next_recommended_command": "python -m aetherfusion patch ...",
        }
        manifest.update(overrides)
        return manifest

    def test_markdown_generates(self):
        """Markdown generation succeeds."""
        manifest = self._make_manifest()
        report = generate_patch_report(manifest)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_markdown_contains_summary_table(self):
        """Summary section with key metrics."""
        report = generate_patch_report(self._make_manifest())
        assert "## 1. Summary" in report
        assert "Files to add" in report
        assert "Files conflicted" in report

    def test_markdown_contains_safe_additions(self):
        """Safe Additions table for add_file ops."""
        report = generate_patch_report(self._make_manifest())
        assert "## 2. Safe Additions" in report
        assert "Card.tsx" in report

    def test_markdown_contains_conflicts(self):
        """Conflicts section for conflict_same_name ops."""
        report = generate_patch_report(self._make_manifest())
        assert "Conflicts Requiring Human Decision" in report
        assert "Header.tsx" in report

    def test_markdown_has_skipped_section(self):
        """Skipped files section appears."""
        report = generate_patch_report(self._make_manifest())
        assert "Skipped Files" in report
        assert "big.png" in report

    def test_markdown_has_no_modify_disclaimer(self):
        """Must explicitly state no files were modified."""
        report = generate_patch_report(self._make_manifest())
        assert "No source or target files were modified" in report

    def test_markdown_has_blocked_actions(self):
        """Blocked actions are listed."""
        report = generate_patch_report(self._make_manifest())
        assert "## 6. Blocked Actions" in report

    def test_markdown_has_next_command(self):
        """Next recommended command appears in code block."""
        report = generate_patch_report(self._make_manifest())
        assert "## 8. Next Recommended Command" in report
        assert "```bash" in report


# ---------------------------------------------------------------------------
# PatchJsonReporter tests
# ---------------------------------------------------------------------------

class TestPatchJsonReporter:
    """Tests for write_patch_json."""

    def test_json_written_and_readable(self, tmp_path):
        """Patch JSON is written and contains required fields."""
        manifest = {
            "patch_version": "0.3.0",
            "mode": "dry_run",
            "module_name": "test",
            "source_module_path": "/tmp/a",
            "target_match_path": "/tmp/b",
            "summary": {"files_to_add": 3, "files_conflicted": 1, "files_skipped": 0},
            "operations": [],
            "blocked_actions": [],
            "required_human_decisions": [],
            "next_recommended_command": "",
        }
        json_path = tmp_path / "patch.json"
        write_patch_json(json_path, manifest)

        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["mode"] == "dry_run"
        assert data["patch_version"] == "0.3.0"
        assert data["summary"]["files_to_add"] == 3


# ---------------------------------------------------------------------------
# DiffReporter tests
# ---------------------------------------------------------------------------

class TestDiffReporter:
    """Tests for generate_diff."""

    def test_diff_generated_for_add_files(self, tmp_path):
        """Diff file contains only add_file operations."""
        # Create a real source file
        src_dir = tmp_path / "src"
        os.makedirs(str(src_dir), exist_ok=True)
        source_file = src_dir / "Button.tsx"
        source_file.write_text("export const Button = () => <button/>;\n", encoding="utf-8")

        manifest = {
            "patch_version": "0.3.0",
            "module_name": "components",
            "operations": [
                {
                    "type": "add_file",
                    "relative_path": "Button.tsx",
                    "source_absolute": str(source_file),
                    "file_size_bytes": 40,
                },
                {
                    "type": "conflict_same_name",
                    "relative_path": "Header.tsx",
                    "source_absolute": str(source_file),
                    "target_absolute": "/tmp/tgt/Header.tsx",
                },
            ],
        }
        diff_path = tmp_path / "patch.diff"
        generate_diff(manifest, diff_path)

        assert diff_path.is_file()
        content = diff_path.read_text(encoding="utf-8")
        # Should contain the add_file
        assert "Button.tsx" in content
        assert "export const Button" in content
        # Should NOT contain the conflict
        assert "Header.tsx" not in content

    def test_diff_empty_when_no_add_files(self, tmp_path):
        """Diff file has placeholder text when no add_file operations."""
        manifest = {
            "patch_version": "0.3.0",
            "module_name": "components",
            "operations": [
                {
                    "type": "conflict_same_name",
                    "relative_path": "Header.tsx",
                    "source_absolute": "/tmp/a/Header.tsx",
                    "target_absolute": "/tmp/b/Header.tsx",
                },
            ],
        }
        diff_path = tmp_path / "patch.diff"
        generate_diff(manifest, diff_path)

        content = diff_path.read_text(encoding="utf-8")
        assert "No add_file operations" in content

    def test_diff_has_header(self, tmp_path):
        """Diff output starts with a descriptive header."""
        src_dir = tmp_path / "src"
        os.makedirs(str(src_dir), exist_ok=True)
        source_file = src_dir / "Foo.ts"
        source_file.write_text("// foo\n", encoding="utf-8")

        manifest = {
            "patch_version": "0.3.0",
            "module_name": "components",
            "operations": [
                {
                    "type": "add_file",
                    "relative_path": "Foo.ts",
                    "source_absolute": str(source_file),
                    "file_size_bytes": 7,
                },
            ],
        }
        diff_path = tmp_path / "patch.diff"
        generate_diff(manifest, diff_path)

        content = diff_path.read_text(encoding="utf-8")
        assert "AetherFusion Dry-Run Diff" in content
        assert "dry_run" in content
        assert "--- /dev/null" in content
        assert "+++ b/" in content


# ---------------------------------------------------------------------------
# CLI integration (via subprocess)
# ---------------------------------------------------------------------------

class TestPatchCLI:
    """End-to-end CLI tests for the 'patch' command."""

    def test_cli_refuses_without_dry_run(self, tmp_path):
        """Exit non-zero and error message when --dry-run is missing."""
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(
                source_module_path=str(tmp_path / "src"),
                target_match_path=str(tmp_path / "tgt"),
            )
        )
        out_path = tmp_path / "out.md"

        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(plan_path),
                "--out", str(out_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode != 0
        assert "requires --dry-run" in result.stderr

    def test_cli_success_with_dry_run(self, tmp_path):
        """Successful run when --dry-run is passed and source exists."""
        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        _make_dirs_and_files(str(src_dir), {"Button.tsx": "// button\n"})
        os.makedirs(str(tgt_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(src_dir), target_match_path=str(tgt_dir))
        )
        out_path = tmp_path / "out.md"

        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(plan_path),
                "--out", str(out_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        assert out_path.is_file()

    def test_cli_generates_json_manifest(self, tmp_path):
        """JSON manifest is written when --json is specified."""
        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        _make_dirs_and_files(str(src_dir), {"A.ts": "// a\n"})
        os.makedirs(str(tgt_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(src_dir), target_match_path=str(tgt_dir))
        )
        json_path = tmp_path / "manifest.json"

        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(plan_path),
                "--json", str(json_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["mode"] == "dry_run"

    def test_cli_generates_diff(self, tmp_path):
        """Diff output is written when --diff is specified."""
        src_dir = tmp_path / "src"
        tgt_dir = tmp_path / "tgt"
        _make_dirs_and_files(str(src_dir), {"Card.tsx": "// card\n"})
        os.makedirs(str(tgt_dir), exist_ok=True)

        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(src_dir), target_match_path=str(tgt_dir))
        )
        diff_path = tmp_path / "patch.diff"

        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(plan_path),
                "--diff", str(diff_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        assert diff_path.is_file()
        content = diff_path.read_text(encoding="utf-8")
        assert "Card.tsx" in content

    def test_cli_nonexistent_plan_exits_nonzero(self, tmp_path):
        """Exits non-zero when plan file does not exist."""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(tmp_path / "ghost.json"),
                "--out", str(tmp_path / "out.md"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_cli_no_output_specified_exits_nonzero(self, tmp_path):
        """Exits non-zero when no output is specified."""
        src_dir = tmp_path / "src"
        os.makedirs(str(src_dir), exist_ok=True)
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(
            _make_plan_json(source_module_path=str(src_dir), target_match_path=str(tmp_path / "tgt"))
        )

        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "patch",
                "--plan", str(plan_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode != 0
        assert "No output" in result.stderr