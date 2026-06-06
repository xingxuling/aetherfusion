"""Tests for AetherFusion v0.4.5 rollback + audit modules."""

import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aetherfusion.rollback.safe_rollback import rollback_apply
from aetherfusion.reporter.rollback_json_reporter import write_rollback_json
from aetherfusion.reporter.rollback_markdown_reporter import generate_rollback_report
from aetherfusion.audit.audit_logger import (
    log_audit_event,
    make_apply_event,
    make_rollback_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rollback_manifest(
    tmp_path: Path,
    module_name: str = "components",
    created_files: list[str] | None = None,
    target_match_path: str | None = None,
) -> Path:
    """Create a minimal rollback manifest JSON for testing."""
    if created_files is None:
        created_files = []
    if target_match_path is None:
        target_match_path = str(tmp_path / "tgt")
    data = {
        "rollback_version": "0.4.0",
        "applied_at_timestamp": "2026-01-01T00:00:00+00:00",
        "module_name": module_name,
        "target_match_path": target_match_path,
        "created_files": created_files,
        "created_directories": [],
        "skipped_files": [],
        "blocked_files": [],
        "failed_files": [],
        "rollback_actions": [],
        "rollback_command_hint": "...",
    }
    path = tmp_path / "rollback_manifest.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _make_files(base: Path, files: dict[str, str]) -> None:
    """Create files under base from {relpath: content} dict."""
    for relpath, content in files.items():
        fullpath = base / relpath
        fullpath.parent.mkdir(parents=True, exist_ok=True)
        fullpath.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test rollback_apply core logic
# ---------------------------------------------------------------------------

class TestSafeRollback:
    """Tests for rollback_apply."""

    def test_deletes_created_file(self, tmp_path):
        """A file listed in created_files is deleted."""
        tgt = tmp_path / "tgt"
        file_path = tgt / "Button.tsx"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("export const Button = () => <button/>;\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(file_path.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 1
        assert result["summary"]["files_already_missing"] == 0
        assert result["summary"]["files_blocked"] == 0
        assert result["summary"]["files_failed"] == 0
        assert str(file_path.resolve()) in result["files_deleted"][0]
        assert not file_path.exists()

    def test_file_already_missing_recorded(self, tmp_path):
        """A file no longer on disk is recorded as already_missing."""
        tgt = tmp_path / "tgt"
        ghost_path = tgt / "Ghost.tsx"

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(ghost_path.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 0
        assert result["summary"]["files_already_missing"] == 1
        assert any("no longer exists" in f["reason"].lower() for f in result["files_already_missing"])

    def test_path_traversal_blocked(self, tmp_path):
        """Path with .. is blocked."""
        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=["/safe/../escape/evil.tsx"],
            target_match_path=str(tmp_path / "tgt"),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_blocked"] == 1
        assert "path traversal" in result["files_blocked"][0]["reason"].lower()

    def test_config_file_blocked(self, tmp_path):
        """package.json in created_files is blocked."""
        tgt = tmp_path / "tgt"
        pkg = tgt / "package.json"
        pkg.parent.mkdir(parents=True, exist_ok=True)
        pkg.write_text('{"name": "test"}\n', encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(pkg.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_blocked"] == 1
        assert "Protected config file" in result["files_blocked"][0]["reason"]
        assert pkg.exists()  # file must NOT be deleted

    def test_requirements_txt_blocked(self, tmp_path):
        """requirements.txt in created_files is blocked."""
        tgt = tmp_path / "tgt"
        req = tgt / "requirements.txt"
        req.parent.mkdir(parents=True, exist_ok=True)
        req.write_text("requests==2.28.0\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(req.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)
        assert result["summary"]["files_blocked"] == 1
        assert req.exists()

    def test_pyproject_toml_blocked(self, tmp_path):
        """pyproject.toml in created_files is blocked."""
        tgt = tmp_path / "tgt"
        ppt = tgt / "pyproject.toml"
        ppt.parent.mkdir(parents=True, exist_ok=True)
        ppt.write_text("[project]\nname = 'test'\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(ppt.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)
        assert result["summary"]["files_blocked"] == 1
        assert ppt.exists()

    def test_nonexistent_manifest_raises(self, tmp_path):
        """FileNotFoundError when manifest doesn't exist."""
        with pytest.raises(FileNotFoundError):
            rollback_apply(tmp_path / "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path):
        """JSONDecodeError for malformed JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("{{not json")
        with pytest.raises(json.JSONDecodeError):
            rollback_apply(bad)

    def test_non_list_created_files_raises(self, tmp_path):
        """ValueError when created_files is not a list."""
        tgt = tmp_path / "tgt"
        data = {
            "rollback_version": "0.4.0",
            "module_name": "test",
            "target_match_path": str(tgt),
            "created_files": "not_a_list",
        }
        path = tmp_path / "bad_manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(ValueError, match="not a list"):
            rollback_apply(path)

    def test_result_contains_required_fields(self, tmp_path):
        """Rollback result has all required top-level fields."""
        tgt = tmp_path / "tgt"
        f = tgt / "A.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// a\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        required = [
            "rollback_version", "mode", "manifest_file", "module_name",
            "target_match_path", "summary", "files_deleted",
            "files_already_missing", "files_blocked", "files_failed",
            "next_recommended_command",
        ]
        for key in required:
            assert key in result, f"Missing required field: {key}"

    def test_mixed_results_all_reported(self, tmp_path):
        """When some files deleted, some missing, some blocked — all reported."""
        tgt = tmp_path / "tgt"
        tgt.mkdir(parents=True, exist_ok=True)

        # File that exists — will be deleted
        good = tgt / "good.ts"
        good.write_text("// good\n", encoding="utf-8")

        # File that doesn't exist — already missing
        ghost = tgt / "ghost.ts"

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[
                str(good.resolve()),
                str(ghost.resolve()),
            ],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 1
        assert result["summary"]["files_already_missing"] == 1
        assert not good.exists()

    def test_delete_failure_does_not_stop_others(self, tmp_path, monkeypatch):
        """A failed delete does not prevent other files from being processed."""
        tgt = tmp_path / "tgt"
        tgt.mkdir(parents=True, exist_ok=True)

        a = tgt / "a.ts"
        b = tgt / "b.ts"
        a.write_text("// a\n", encoding="utf-8")
        b.write_text("// b\n", encoding="utf-8")

        # Make os.remove fail for 'a.ts' only
        original_remove = os.remove

        def mock_remove(path, *args, **kwargs):
            if "a.ts" in str(path):
                raise OSError("Simulated failure")
            return original_remove(path)

        monkeypatch.setattr(os, "remove", mock_remove)

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[
                str(a.resolve()),
                str(b.resolve()),
            ],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 1  # b.ts
        assert result["summary"]["files_failed"] == 1  # a.ts
        assert a.exists()  # a.ts not deleted
        assert not b.exists()  # b.ts deleted

    def test_normal_file_not_blocked(self, tmp_path):
        """A normal .tsx file is NOT blocked by config protection."""
        tgt = tmp_path / "tgt"
        f = tgt / "Component.tsx"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// comp\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 1
        assert result["summary"]["files_blocked"] == 0
        assert not f.exists()

    def test_empty_created_files_returns_zero_summary(self, tmp_path):
        """When created_files is empty, all counts are zero."""
        manifest = _make_rollback_manifest(tmp_path, created_files=[])

        result = rollback_apply(manifest)

        assert result["summary"]["files_deleted"] == 0
        assert result["summary"]["files_already_missing"] == 0
        assert result["summary"]["files_blocked"] == 0
        assert result["summary"]["files_failed"] == 0


# ---------------------------------------------------------------------------
# Test rollback reporters
# ---------------------------------------------------------------------------

class TestRollbackReporters:
    """Tests for rollback JSON and Markdown reporters."""

    def test_json_reporter_writes_file(self, tmp_path):
        """JSON rollback result is written to disk."""
        result = {
            "rollback_version": "0.4.5",
            "mode": "confirmed_rollback",
            "module_name": "test",
            "summary": {"files_deleted": 1},
            "files_deleted": ["/tmp/a.ts"],
            "files_already_missing": [],
            "files_blocked": [],
            "files_failed": [],
            "next_recommended_command": "",
        }
        json_path = tmp_path / "rollback_result.json"
        write_rollback_json(json_path, result)
        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["mode"] == "confirmed_rollback"

    def test_markdown_report_contains_summary(self):
        """Markdown rollback report includes summary table."""
        result = {
            "rollback_version": "0.4.5",
            "mode": "confirmed_rollback",
            "module_name": "components",
            "manifest_file": "/tmp/manifest.json",
            "target_match_path": "/tmp/tgt",
            "summary": {
                "files_deleted": 2,
                "files_already_missing": 1,
                "files_blocked": 0,
                "files_failed": 0,
            },
            "files_deleted": ["/tmp/tgt/A.tsx", "/tmp/tgt/B.tsx"],
            "files_already_missing": [
                {"path": "/tmp/tgt/C.tsx", "reason": "File no longer exists on disk."}
            ],
            "files_blocked": [],
            "files_failed": [],
            "next_recommended_command": "# done",
        }
        report = generate_rollback_report(result)
        assert "## 1. Summary" in report
        assert "Files deleted" in report
        assert "2" in report
        assert "## 2. Files Deleted" in report
        assert "A.tsx" in report
        assert "## 3. Files Already Missing" in report
        assert "## 6. Next Recommended Command" in report
        assert "Safety recap" in report

    def test_markdown_report_no_deleted(self):
        """Report renders with zero deletions."""
        result = {
            "rollback_version": "0.4.5",
            "mode": "confirmed_rollback",
            "module_name": "empty",
            "manifest_file": "/tmp/manifest.json",
            "target_match_path": "/tmp/tgt",
            "summary": {
                "files_deleted": 0,
                "files_already_missing": 0,
                "files_blocked": 3,
                "files_failed": 0,
            },
            "files_deleted": [],
            "files_already_missing": [],
            "files_blocked": [
                {"path": "/tmp/tgt/pkg.json", "reason": "Protected config file"}
            ],
            "files_failed": [],
            "next_recommended_command": "",
        }
        report = generate_rollback_report(result)
        assert "## 1. Summary" in report
        assert "Files deleted" in report
        assert "## 2. Files Deleted" not in report
        assert "## 4. Files Blocked" in report

    def test_markdown_report_includes_blocked_detail(self):
        """Blocked section includes reasons."""
        result = {
            "rollback_version": "0.4.5",
            "mode": "confirmed_rollback",
            "module_name": "test",
            "manifest_file": "/tmp/manifest.json",
            "target_match_path": "/tmp/tgt",
            "summary": {
                "files_deleted": 0,
                "files_already_missing": 0,
                "files_blocked": 1,
                "files_failed": 0,
            },
            "files_deleted": [],
            "files_already_missing": [],
            "files_blocked": [
                {"path": "/tmp/tgt/package.json", "reason": "Protected config file"}
            ],
            "files_failed": [],
            "next_recommended_command": "",
        }
        report = generate_rollback_report(result)
        assert "Protected config file" in report
        assert "package.json" in report


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestRollbackCLI:
    """End-to-end CLI tests for 'rollback' command."""

    def test_refuses_without_confirm(self, tmp_path):
        """Exit non-zero when --confirm is missing."""
        manifest = _make_rollback_manifest(tmp_path, created_files=[])

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode != 0
        assert "requires --confirm" in result.stderr

    def test_success_with_confirm(self, tmp_path):
        """rollback --confirm deletes file and exits 0."""
        tgt = tmp_path / "tgt"
        f = tgt / "Foo.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// foo\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        proj_root = Path(__file__).resolve().parent.parent
        out_path = tmp_path / "out.md"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm", "--out", str(out_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert out_path.is_file()
        assert not f.exists()

    def test_nonexistent_manifest_exits_nonzero(self, tmp_path):
        """Exits non-zero when manifest doesn't exist."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(tmp_path / "ghost.json"),
             "--confirm", "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_json_result_generated(self, tmp_path):
        """rollback --json writes result JSON."""
        tgt = tmp_path / "tgt"
        f = tgt / "Foo.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// foo\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        proj_root = Path(__file__).resolve().parent.parent
        json_path = tmp_path / "result.json"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm", "--json", str(json_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert json_path.is_file()
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["mode"] == "confirmed_rollback"
        assert "rollback_version" in data

    def test_markdown_report_generated(self, tmp_path):
        """rollback --out writes Markdown report."""
        tgt = tmp_path / "tgt"
        f = tgt / "Foo.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// foo\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        proj_root = Path(__file__).resolve().parent.parent
        out_path = tmp_path / "report.md"
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm", "--out", str(out_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        content = out_path.read_text(encoding="utf-8")
        assert "Rollback Report" in content
        assert "Files Deleted" in content

    def test_already_missing_reported(self, tmp_path):
        """Already-missing files are reported without error."""
        tgt = tmp_path / "tgt"
        ghost = tgt / "Ghost.ts"

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(ghost.resolve())],
            target_match_path=str(tgt),
        )

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm",
             "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "already missing" in result.stdout.lower() or "0 file(s) deleted" in result.stdout.lower()

    def test_path_traversal_reported_as_blocked(self, tmp_path):
        """Path traversal is reported as blocked."""
        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=["../escape/evil.tsx"],
            target_match_path=str(tmp_path / "tgt"),
        )

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm",
             "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "blocked" in result.stdout.lower()

    def test_invalid_json_manifest_exits_nonzero(self, tmp_path):
        """Exits non-zero when manifest contains invalid JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("{{not json")
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(bad), "--confirm",
             "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Test audit logger
# ---------------------------------------------------------------------------

class TestAuditLogger:
    """Tests for audit_logger."""

    def test_log_audit_event_writes_jsonl(self, tmp_path):
        """log_audit_event appends a JSONL line."""
        audit_path = tmp_path / "audit.jsonl"
        event = {"event_type": "apply", "version": "0.4.5"}
        ok = log_audit_event(audit_path, event)
        assert ok
        assert audit_path.is_file()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "apply"

    def test_log_audit_event_appends(self, tmp_path):
        """Multiple events append to the same JSONL file."""
        audit_path = tmp_path / "audit.jsonl"
        log_audit_event(audit_path, {"event_type": "apply"})
        log_audit_event(audit_path, {"event_type": "rollback"})
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_log_audit_event_creates_parent(self, tmp_path):
        """Parent directories are created automatically."""
        audit_path = tmp_path / "nested" / "deep" / "audit.jsonl"
        ok = log_audit_event(audit_path, {"event_type": "test"})
        assert ok
        assert audit_path.is_file()

    def test_make_apply_event_has_required_fields(self):
        """make_apply_event returns all required fields."""
        result = {
            "apply_version": "0.4.0",
            "rollback_manifest_path": "/tmp/backup.json",
            "summary": {"files_applied": 3},
        }
        event = make_apply_event(result, "/tmp/patch.json", "/tmp/result.json")
        assert event["event_type"] == "apply"
        assert event["version"] == "0.4.0"
        assert "timestamp" in event
        assert event["input_file"] == "/tmp/patch.json"
        assert "summary" in event
        assert event["result_json_path"] == "/tmp/result.json"
        assert event["backup_or_manifest_path"] == "/tmp/backup.json"

    def test_make_rollback_event_has_required_fields(self):
        """make_rollback_event returns all required fields."""
        result = {
            "rollback_version": "0.4.5",
            "summary": {"files_deleted": 2},
        }
        event = make_rollback_event(result, "/tmp/manifest.json", "/tmp/result.json")
        assert event["event_type"] == "rollback"
        assert event["version"] == "0.4.5"
        assert "timestamp" in event
        assert event["input_file"] == "/tmp/manifest.json"
        assert "summary" in event
        assert event["result_json_path"] == "/tmp/result.json"

    def test_audit_write_failure_does_not_raise(self, tmp_path, monkeypatch):
        """log_audit_event returns False on failure, does not raise."""
        def _fail_open(*args, **kwargs):
            raise OSError("Simulated disk full")

        monkeypatch.setattr("builtins.open", _fail_open)
        ok = log_audit_event(tmp_path / "audit.jsonl", {"event_type": "test"})
        assert ok is False

    def test_audit_after_apply_via_cli(self, tmp_path):
        """Apply writes an audit JSONL line."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        _make_files(src, {"Foo.ts": "// foo\n"})
        os.makedirs(str(tgt), exist_ok=True)

        patch_data = {
            "patch_version": "0.3.0",
            "mode": "dry_run",
            "module_name": "components",
            "module_type": "components",
            "source_module_path": str(src),
            "target_match_path": str(tgt),
            "target_exists": True,
            "risk_level": "medium",
            "summary": {"files_to_add": 1, "files_conflicted": 0, "files_skipped": 0},
            "operations": [{
                "type": "add_file", "relative_path": "Foo.ts",
                "source_absolute": str(src / "Foo.ts"), "file_size_bytes": 8,
            }],
            "blocked_actions": [],
            "required_human_decisions": [],
            "next_recommended_command": "",
        }
        patch_path = tmp_path / "patch.json"
        patch_path.write_text(json.dumps(patch_data, indent=2), encoding="utf-8")

        audit_path = tmp_path / "audit.jsonl"
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "apply",
             "--patch", str(patch_path), "--confirm",
             "--out", str(tmp_path / "out.md"),
             "--audit", str(audit_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert audit_path.is_file()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "apply"

    def test_audit_after_rollback_via_cli(self, tmp_path):
        """Rollback writes an audit JSONL line."""
        tgt = tmp_path / "tgt"
        f = tgt / "Foo.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// foo\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        audit_path = tmp_path / "audit.jsonl"
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm",
             "--out", str(tmp_path / "out.md"),
             "--audit", str(audit_path)],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert audit_path.is_file()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "rollback"

    def test_audit_default_path_used(self, tmp_path):
        """When --audit not specified, default reports/aetherfusion-audit.jsonl is used (relative to CWD)."""
        tgt = tmp_path / "tgt"
        f = tgt / "Bar.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// bar\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "rollback",
             "--manifest", str(manifest), "--confirm",
             "--out", str(tmp_path / "out.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0
        # Default path should be relative to CWD (project root)
        default_audit = proj_root / "reports" / "aetherfusion-audit.jsonl"
        assert default_audit.is_file()
        lines = default_audit.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1

    def test_audit_write_failure_does_not_break_main_flow(self, tmp_path, monkeypatch):
        """When audit write fails, main operation still succeeds and warns."""
        tgt = tmp_path / "tgt"
        f = tgt / "Safe.ts"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("// safe\n", encoding="utf-8")

        manifest = _make_rollback_manifest(
            tmp_path,
            created_files=[str(f.resolve())],
            target_match_path=str(tgt),
        )

        audit_path = tmp_path / "readonly_dir" / "audit.jsonl"
        # Create a file where a directory should be to cause OSError
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        (audit_path.parent / "audit.jsonl").write_text("block", encoding="utf-8")
        os.chmod(str(audit_path.parent), 0o444)  # read-only

        proj_root = Path(__file__).resolve().parent.parent
        try:
            result = subprocess.run(
                [sys.executable, "-m", "aetherfusion", "rollback",
                 "--manifest", str(manifest), "--confirm",
                 "--out", str(tmp_path / "out.md"),
                 "--audit", str(audit_path)],
                capture_output=True, text=True, cwd=str(proj_root),
            )
            assert result.returncode == 0
            assert "audit" in result.stdout.lower()  # warning
            assert not f.exists()  # main flow succeeded
        finally:
            os.chmod(str(audit_path.parent), 0o777)


# ---------------------------------------------------------------------------
# Integration test: verify existing tests still pass
# ---------------------------------------------------------------------------

class TestExistingTestsIntegrity:
    """Smoke test: verify all modules import correctly and key functions exist."""

    def test_all_modules_importable(self):
        """All v0.4.5 modules are importable."""
        import aetherfusion.rollback.safe_rollback  # noqa: F401
        import aetherfusion.rollback  # noqa: F401
        import aetherfusion.audit.audit_logger  # noqa: F401
        import aetherfusion.audit  # noqa: F401
        import aetherfusion.reporter.rollback_json_reporter  # noqa: F401
        import aetherfusion.reporter.rollback_markdown_reporter  # noqa: F401

    def test_version_updated(self):
        """Version is 0.7.0."""
        from aetherfusion import __version__
        assert __version__ == "1.0.1"

    def test_cli_help_includes_rollback(self):
        """CLI help lists rollback subcommand."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "rollback" in (result.stdout or "")

    def test_scan_still_works(self, tmp_path):
        """Existing scan command still works."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()

        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "scan",
             "--source", str(src), "--target", str(tgt),
             "--out", str(tmp_path / "report.md")],
            capture_output=True, text=True, cwd=str(proj_root),
        )
        assert result.returncode == 0