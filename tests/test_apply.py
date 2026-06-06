"""Tests for AetherFusion apply module (safe_apply + reporters + CLI)."""

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.applier.safe_apply import apply_patch
from aetherfusion.reporter.apply_json_reporter import write_apply_json
from aetherfusion.reporter.apply_markdown_reporter import generate_apply_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_patch_manifest(
    tmp_path: Path,
    module_name: str = "components",
    ops: list[dict] | None = None,
) -> Path:
    """Create a minimal patch manifest JSON for testing."""
    if ops is None:
        ops = []
    data = {
        "patch_version": "0.3.0",
        "mode": "dry_run",
        "module_name": module_name,
        "module_type": module_name,
        "source_module_path": str(tmp_path / "src"),
        "target_match_path": str(tmp_path / "tgt"),
        "target_exists": True,
        "risk_level": "medium",
        "summary": {"files_to_add": 0, "files_conflicted": 0, "files_skipped": 0},
        "operations": ops,
        "blocked_actions": [],
        "required_human_decisions": [],
        "next_recommended_command": "",
    }
    path = tmp_path / "patch_manifest.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _make_files(base: Path, files: dict[str, str]) -> None:
    """Create files under base from {relpath: content} dict."""
    for relpath, content in files.items():
        fullpath = base / relpath
        fullpath.parent.mkdir(parents=True, exist_ok=True)
        fullpath.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test apply_patch core logic
# ---------------------------------------------------------------------------

class TestSafeApply:
    """Tests for apply_patch."""

    def test_add_file_copied_to_target(self, tmp_path):
        """add_file operation copies the file to target."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Button.tsx": "export const Button = () => <button/>;\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "Button.tsx",
            "source_absolute": str(src / "Button.tsx"),
            "file_size_bytes": 40,
        }])
        # Override target_match_path in the manifest
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 1
        assert result["summary"]["files_blocked"] == 0
        assert result["summary"]["files_failed"] == 0
        assert os.path.isfile(tgt / "Button.tsx")
        assert (tgt / "Button.tsx").read_text() == "export const Button = () => <button/>;\n"

    def test_target_already_exists_blocked(self, tmp_path):
        """File that already exists in target is blocked."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Button.tsx": "// source\n"})
        _make_files(tgt, {"Button.tsx": "// target\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "Button.tsx",
            "source_absolute": str(src / "Button.tsx"),
            "file_size_bytes": 12,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_blocked"] == 1
        assert result["operations_blocked"][0]["relative_path"] == "Button.tsx"
        assert "already exists" in result["operations_blocked"][0]["reason"].lower()
        # Target file must be unchanged
        assert (tgt / "Button.tsx").read_text() == "// target\n"

    def test_conflict_same_name_is_blocked(self, tmp_path):
        """conflict_same_name operation is blocked."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Header.tsx": "// source\n"})
        _make_files(tgt, {"Header.tsx": "// target\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "conflict_same_name",
            "relative_path": "Header.tsx",
            "source_absolute": str(src / "Header.tsx"),
            "target_absolute": str(tgt / "Header.tsx"),
            "file_size_bytes": 12,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_blocked"] == 1
        assert "not supported" in result["operations_blocked"][0]["reason"].lower()

    def test_skip_unsafe_is_blocked(self, tmp_path):
        """skip_unsafe operation is blocked."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"big.tsx": "x" * 2000})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "skip_unsafe",
            "relative_path": "big.tsx",
            "source_absolute": str(src / "big.tsx"),
            "reason": "Binary file",
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_blocked"] >= 1

    def test_path_traversal_blocked(self, tmp_path):
        """File with .. in path is blocked for path traversal."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"safe.tsx": "// safe\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "../escape/evil.tsx",
            "source_absolute": str(src / "safe.tsx"),
            "file_size_bytes": 10,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_blocked"] >= 1
        assert any("path traversal" in b["reason"].lower() for b in result["operations_blocked"])

    def test_backup_manifest_generated(self, tmp_path):
        """Rollback manifest is created when --backup is specified."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Button.tsx": "// button\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "Button.tsx",
            "source_absolute": str(src / "Button.tsx"),
            "file_size_bytes": 12,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        backup_path = tmp_path / "backup.json"
        result = apply_patch(manifest, backup_path)

        assert backup_path.is_file()
        assert result["rollback_manifest_path"] is not None
        with open(backup_path, "r", encoding="utf-8") as f:
            rollback = json.load(f)
        assert rollback["module_name"] == "components"
        assert len(rollback["created_files"]) == 1
        assert len(rollback["rollback_actions"]) == 1

    def test_large_file_blocked(self, tmp_path):
        """File > 1 MB is blocked."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        os.makedirs(str(src), exist_ok=True)
        os.makedirs(str(tgt), exist_ok=True)
        large_file = src / "big.tsx"
        large_file.write_text("x" * 2_000_000, encoding="utf-8")

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "big.tsx",
            "source_absolute": str(large_file),
            "file_size_bytes": 2_000_000,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)
        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_blocked"] >= 1
        assert any("too large" in b["reason"].lower() for b in result["operations_blocked"])

    def test_binary_file_skipped(self, tmp_path):
        """Binary file is skipped."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        os.makedirs(str(src), exist_ok=True)
        os.makedirs(str(tgt), exist_ok=True)
        bin_file = src / "image.png"
        bin_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "image.png",
            "source_absolute": str(bin_file),
            "file_size_bytes": 210,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)
        assert result["summary"]["files_applied"] == 0
        assert result["summary"]["files_skipped"] >= 1

    def test_target_directory_created_if_missing(self, tmp_path):
        """Target directory is auto-created if it doesn't exist."""
        src = tmp_path / "src"
        tgt = tmp_path / "nonexistent_tgt"
        _make_files(src, {"Foo.tsx": "// foo\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "Foo.tsx",
            "source_absolute": str(src / "Foo.tsx"),
            "file_size_bytes": 8,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert os.path.isdir(tgt)
        assert result["summary"]["files_applied"] == 1
        assert os.path.isfile(tgt / "Foo.tsx")

    def test_nonexistent_patch_raises(self, tmp_path):
        """FileNotFoundError when patch manifest doesn't exist."""
        with pytest.raises(FileNotFoundError):
            apply_patch(tmp_path / "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path):
        """JSONDecodeError for malformed patch JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("{{not json")
        with pytest.raises(json.JSONDecodeError):
            apply_patch(bad)

    def test_missing_target_match_path_raises(self, tmp_path):
        """ValueError when target_match_path is missing."""
        manifest = _make_patch_manifest(tmp_path, ops=[])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = ""
        manifest.write_text(json.dumps(data, indent=2))

        with pytest.raises(ValueError, match="target_match_path"):
            apply_patch(manifest)

    def test_nested_target_dirs_created(self, tmp_path):
        """Parent directories in target path are created as needed."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"nested/deep/Comp.tsx": "// deep\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "nested/deep/Comp.tsx",
            "source_absolute": str(src / "nested/deep/Comp.tsx"),
            "file_size_bytes": 10,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 1
        assert (tgt / "nested/deep/Comp.tsx").is_file()

    def test_no_applicable_operations_returns_gracefully(self, tmp_path):
        """When no add_file ops exist, apply returns zero applied, exit code 0."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Header.tsx": "// source\n"})
        _make_files(tgt, {"Header.tsx": "// target\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "conflict_same_name",
            "relative_path": "Header.tsx",
            "source_absolute": str(src / "Header.tsx"),
            "target_absolute": str(tgt / "Header.tsx"),
            "file_size_bytes": 12,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 0

    def test_apply_result_json_contains_required_fields(self, tmp_path):
        """Apply result has all required top-level fields."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"A.ts": "// a\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file",
            "relative_path": "A.ts",
            "source_absolute": str(src / "A.ts"),
            "file_size_bytes": 6,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        required = [
            "apply_version", "mode", "patch_file", "module_name",
            "source_module_path", "target_match_path", "summary",
            "operations_applied", "operations_skipped", "operations_blocked",
            "operations_failed", "rollback_manifest_path", "next_recommended_command",
        ]
        for key in required:
            assert key in result, f"Missing required field: {key}"

    def test_partial_success_reports_failures(self, tmp_path):
        """When some add_files succeed and some fail, both are reported."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {
            "Good.tsx": "// good\n",
        })
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[
            {
                "type": "add_file",
                "relative_path": "Good.tsx",
                "source_absolute": str(src / "Good.tsx"),
                "file_size_bytes": 9,
            },
            {
                "type": "add_file",
                "relative_path": "Ghost.tsx",
                "source_absolute": str(src / "Ghost.tsx"),  # does not exist
                "file_size_bytes": 10,
            },
        ])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        result = apply_patch(manifest)

        assert result["summary"]["files_applied"] == 1
        assert result["summary"]["files_skipped"] == 1


# ---------------------------------------------------------------------------
# Test apply reporters
# ---------------------------------------------------------------------------

class TestApplyReporters:
    """Tests for apply JSON and Markdown reporters."""

    def test_json_reporter_writes_file(self, tmp_path):
        """JSON apply result is written to disk."""
        result = {
            "apply_version": "0.4.0",
            "mode": "confirmed_apply",
            "module_name": "test",
            "summary": {"files_applied": 1},
            "operations_applied": [],
            "operations_skipped": [],
            "operations_blocked": [],
            "operations_failed": [],
            "next_recommended_command": "",
        }
        json_path = tmp_path / "apply_result.json"
        write_apply_json(json_path, result)
        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["mode"] == "confirmed_apply"

    def test_markdown_report_contains_summary(self):
        """Markdown apply report includes summary table."""
        result = {
            "apply_version": "0.4.0",
            "mode": "confirmed_apply",
            "module_name": "components",
            "source_module_path": "/tmp/src",
            "target_match_path": "/tmp/tgt",
            "summary": {"files_applied": 2, "files_skipped": 1, "files_blocked": 0, "files_failed": 0, "directories_created": 3},
            "operations_applied": [
                {"relative_path": "A.tsx", "target_absolute": "/tmp/tgt/A.tsx"},
                {"relative_path": "B.tsx", "target_absolute": "/tmp/tgt/B.tsx"},
            ],
            "operations_skipped": [{"relative_path": "C.png", "reason": "Binary file"}],
            "operations_blocked": [],
            "operations_failed": [],
            "rollback_manifest_path": "/tmp/backup.json",
            "next_recommended_command": "# review",
        }
        report = generate_apply_report(result)
        assert "## 1. Summary" in report
        assert "Files applied (copied)" in report
        assert "2" in report
        assert "## 2. Files Applied" in report
        assert "A.tsx" in report
        assert "## 3. Files Skipped" in report
        assert "Binary file" in report
        assert "## 6. Rollback" in report
        assert "/tmp/backup.json" in report
        assert "## 7. Next Recommended Command" in report
        assert "Only `add_file` operations were applied" in report

    def test_markdown_report_no_applied_still_renders(self):
        """Report renders correctly even with zero applied."""
        result = {
            "apply_version": "0.4.0",
            "mode": "confirmed_apply",
            "module_name": "empty",
            "source_module_path": "/tmp/src",
            "target_match_path": "/tmp/tgt",
            "summary": {"files_applied": 0, "files_skipped": 0, "files_blocked": 5, "files_failed": 0, "directories_created": 0},
            "operations_applied": [],
            "operations_skipped": [],
            "operations_blocked": [{"relative_path": "X.ts", "reason": "Not add_file"}],
            "operations_failed": [],
            "rollback_manifest_path": None,
            "next_recommended_command": "",
        }
        report = generate_apply_report(result)
        assert "## 1. Summary" in report
        assert "0" in report
        assert "## 2. Files Applied" not in report  # No applied files section
        assert "## 4. Files Blocked" in report

    def test_markdown_report_no_rollback_when_no_backup(self):
        """No Rollback section when rollback_manifest_path is None."""
        result = {
            "apply_version": "0.4.0",
            "mode": "confirmed_apply",
            "module_name": "components",
            "source_module_path": "/tmp/src",
            "target_match_path": "/tmp/tgt",
            "summary": {"files_applied": 1, "files_skipped": 0, "files_blocked": 0, "files_failed": 0, "directories_created": 1},
            "operations_applied": [{"relative_path": "A.ts", "target_absolute": "/tmp/tgt/A.ts"}],
            "operations_skipped": [],
            "operations_blocked": [],
            "operations_failed": [],
            "rollback_manifest_path": None,
            "next_recommended_command": "",
        }
        report = generate_apply_report(result)
        assert "## 6. Rollback" not in report


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestApplyCLI:
    """End-to-end CLI tests for 'apply' command."""

    def test_refuses_without_confirm(self, tmp_path):
        """Exit non-zero when --confirm is missing."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Foo.ts": "// foo\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file", "relative_path": "Foo.ts",
            "source_absolute": str(src / "Foo.ts"), "file_size_bytes": 8,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(manifest), "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode != 0
        assert "requires --confirm" in result.stderr

    def test_success_with_confirm(self, tmp_path):
        """apply --confirm copies add_file and exits 0."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Foo.ts": "// foo\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file", "relative_path": "Foo.ts",
            "source_absolute": str(src / "Foo.ts"), "file_size_bytes": 8,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        proj_root = Path(__file__).resolve().parent.parent
        out_path = tmp_path / "out.md"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(manifest), "--confirm", "--out", str(out_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert out_path.is_file()
        assert (tgt / "Foo.ts").is_file()

    def test_json_result_generated(self, tmp_path):
        """apply --json writes result JSON."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Foo.ts": "// foo\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file", "relative_path": "Foo.ts",
            "source_absolute": str(src / "Foo.ts"), "file_size_bytes": 8,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        proj_root = Path(__file__).resolve().parent.parent
        json_path = tmp_path / "result.json"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(manifest), "--confirm", "--json", str(json_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as f:
            res = json.load(f)
        assert res["mode"] == "confirmed_apply"

    def test_backup_manifest_generated_via_cli(self, tmp_path):
        """apply --backup writes rollback manifest."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Foo.ts": "// foo\n"})
        os.makedirs(str(tgt), exist_ok=True)

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "add_file", "relative_path": "Foo.ts",
            "source_absolute": str(src / "Foo.ts"), "file_size_bytes": 8,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        proj_root = Path(__file__).resolve().parent.parent
        json_path = tmp_path / "result.json"
        backup_path = tmp_path / "backup.json"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(manifest), "--confirm",
             "--json", str(json_path), "--backup", str(backup_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert backup_path.is_file()
        with open(backup_path, "r", encoding="utf-8") as f:
            rollback = json.load(f)
        assert "created_files" in rollback
        assert "rollback_actions" in rollback
        assert len(rollback["created_files"]) == 1

    def test_no_applicable_ops_exits_zero(self, tmp_path):
        """When no add_file is present, exits 0 with summary."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Header.tsx": "// source\n"})
        _make_files(tgt, {"Header.tsx": "// target\n"})

        manifest = _make_patch_manifest(tmp_path, ops=[{
            "type": "conflict_same_name", "relative_path": "Header.tsx",
            "source_absolute": str(src / "Header.tsx"),
            "target_absolute": str(tgt / "Header.tsx"),
            "file_size_bytes": 12,
        }])
        data = json.loads(manifest.read_text())
        data["target_match_path"] = str(tgt)
        manifest.write_text(json.dumps(data, indent=2))

        proj_root = Path(__file__).resolve().parent.parent
        out_path = tmp_path / "out.md"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(manifest), "--confirm", "--out", str(out_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        content = out_path.read_text(encoding="utf-8")
        assert "0" in content

    def test_nonexistent_patch_exits_nonzero(self, tmp_path):
        """Exits non-zero when patch manifest doesn't exist."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(tmp_path / "ghost.json"),
             "--confirm", "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()