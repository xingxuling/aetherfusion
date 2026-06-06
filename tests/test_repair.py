"""Tests for the v0.6 repair-plan command — error_classifier,
repair_planner, reporters, CLI, and audit integration.

Ensures existing 196 tests remain importable and passable.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from aetherfusion.repair.error_classifier import (
    classify_error,
    classify_all,
    ERROR_TYPE_MISSING_IMPORT,
    ERROR_TYPE_MISSING_DEPENDENCY,
    ERROR_TYPE_TYPE_ERROR,
    ERROR_TYPE_SYNTAX_ERROR,
    ERROR_TYPE_TEST_FAILURE,
    ERROR_TYPE_CONFIG_ERROR,
    ERROR_TYPE_COMMAND_NOT_FOUND,
    ERROR_TYPE_TIMEOUT,
    ERROR_TYPE_UNKNOWN_ERROR,
)
from aetherfusion.repair.repair_planner import generate_repair_plan
from aetherfusion.reporter.repair_json_reporter import write_repair_json
from aetherfusion.reporter.repair_markdown_reporter import generate_repair_report
from aetherfusion.audit.audit_logger import (
    log_audit_event,
    make_repair_plan_event,
)
from aetherfusion import __version__


# ---------------------------------------------------------------------------
# Module-level CLI helper
# ---------------------------------------------------------------------------

def _run_cli(*args, proj_root=None):
    if proj_root is None:
        proj_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "aetherfusion"] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=str(proj_root),
    )


def _make_verify_result(tmp_path, **overrides) -> dict:
    """Build a minimal verify result for testing."""
    base = {
        "verify_version": "0.5.0",
        "target_path": str(tmp_path),
        "detected_stack": ["python"],
        "commands_detected": ["pytest"],
        "commands_run": ["pytest"],
        "summary": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "timeout": 0, "blocked": 0},
        "results": [
            {
                "command": "pytest",
                "status": "failed",
                "exit_code": 1,
                "duration_ms": 500,
                "stdout_tail": "",
                "stderr_tail": "ModuleNotFoundError: No module named 'requests'",
                "reason": "",
            }
        ],
        "failed_commands": ["pytest"],
        "skipped_commands": [],
        "next_recommended_command": "python -m aetherfusion repair-plan --verify ...",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestErrorClassifier
# ---------------------------------------------------------------------------

class TestErrorClassifier:
    """Tests for error_classifier module."""

    def test_classify_missing_import(self):
        r = {"command": "pytest", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "ImportError: No module named foo", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_MISSING_IMPORT

    def test_classify_missing_dependency(self):
        r = {"command": "pytest", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "ModuleNotFoundError: No module named 'numpy'", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_MISSING_IMPORT

    def test_classify_type_error(self):
        r = {"command": "npm run build", "status": "failed", "exit_code": 2,
             "stdout_tail": "", "stderr_tail": "TypeError: undefined is not a function", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_TYPE_ERROR

    def test_classify_syntax_error(self):
        r = {"command": "npm run build", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "SyntaxError: Unexpected token", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_SYNTAX_ERROR

    def test_classify_test_failure(self):
        r = {"command": "pytest", "status": "failed", "exit_code": 1,
             "stdout_tail": "1 failed, 0 passed",
             "stderr_tail": "AssertionError", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_TEST_FAILURE

    def test_classify_config_error(self):
        r = {"command": "npm run build", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "ENOENT: no such file, open 'tsconfig.json'", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_CONFIG_ERROR

    def test_classify_command_not_found(self):
        r = {"command": "pytest", "status": "failed", "exit_code": None,
             "stdout_tail": "", "stderr_tail": "'pytest' is not recognized as an internal or external command", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_COMMAND_NOT_FOUND

    def test_classify_timeout(self):
        r = {"command": "npm run build", "status": "timeout", "exit_code": None,
             "stdout_tail": "", "stderr_tail": "", "reason": "timed out after 120s"}
        assert classify_error(r) == ERROR_TYPE_TIMEOUT

    def test_classify_unknown(self):
        r = {"command": "npm run build", "status": "failed", "exit_code": 99,
             "stdout_tail": "", "stderr_tail": "something went wrong", "reason": ""}
        assert classify_error(r) == ERROR_TYPE_UNKNOWN_ERROR

    def test_classify_all_buckets(self):
        results = [
            {"command": "a", "status": "passed", "exit_code": 0,
             "stdout_tail": "", "stderr_tail": "", "reason": ""},
            {"command": "b", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "ImportError", "reason": ""},
            {"command": "c", "status": "timeout", "exit_code": None,
             "stdout_tail": "", "stderr_tail": "", "reason": ""},
        ]
        buckets = classify_all(results)
        assert ERROR_TYPE_MISSING_IMPORT in buckets
        assert ERROR_TYPE_TIMEOUT in buckets
        assert len(buckets[ERROR_TYPE_MISSING_IMPORT]) == 1
        assert len(buckets[ERROR_TYPE_TIMEOUT]) == 1


# ---------------------------------------------------------------------------
# TestRepairPlanner
# ---------------------------------------------------------------------------

class TestRepairPlanner:
    """Tests for repair_planner.generate_repair_plan."""

    def test_generate_with_failures(self, tmp_path):
        """Generates repair plan when verify result has failures."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))

        assert plan["repair_plan_version"] == "0.6.0"
        assert plan["summary"]["total_failed"] == 1
        assert plan["summary"]["repair_items_count"] == 1
        assert len(plan["failed_commands"]) == 1
        assert len(plan["classified_errors"]) >= 1
        assert len(plan["repair_items"]) == 1

        item = plan["repair_items"][0]
        assert "error_type" in item
        assert "severity" in item
        assert "confidence" in item
        assert "suspected_files" in item
        assert "evidence" in item
        assert "recommended_action" in item
        assert "automation_eligibility" in item
        assert "risk_level" in item
        assert "reason" in item

    def test_generate_empty_when_no_failures(self, tmp_path):
        """Empty repair plan when verify result has no failures."""
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        result["results"][0]["status"] = "passed"
        result["summary"]["passed"] = 1
        result["summary"]["failed"] = 0
        result["failed_commands"] = []
        verify_path.write_text(json.dumps(result), encoding="utf-8")

        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))
        assert plan["summary"]["total_failed"] == 0
        assert plan["summary"]["repair_items_count"] == 0
        assert plan["repair_items"] == []
        assert plan["failed_commands"] == []

    def test_verify_file_not_found(self, tmp_path):
        """FileNotFoundError when verify file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            generate_repair_plan(tmp_path / "nope.json")

    def test_verify_file_invalid_json(self, tmp_path):
        """json.JSONDecodeError when file is not valid JSON."""
        vf = tmp_path / "bad.json"
        vf.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            generate_repair_plan(vf)

    def test_multiple_error_types(self, tmp_path):
        """Plan handles multiple error types correctly."""
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        result["results"] = [
            {"command": "npm run build", "status": "failed", "exit_code": 2,
             "stdout_tail": "", "stderr_tail": "TypeError: x is not a function",
             "reason": ""},
            {"command": "pytest", "status": "failed", "exit_code": 1,
             "stdout_tail": "", "stderr_tail": "ImportError",
             "reason": ""},
            {"command": "npx tsc", "status": "timeout", "exit_code": None,
             "stdout_tail": "", "stderr_tail": "", "reason": "timeout"},
        ]
        result["summary"]["total"] = 3
        result["summary"]["failed"] = 2
        result["summary"]["timeout"] = 1
        result["failed_commands"] = ["npm run build", "pytest", "npx tsc"]
        verify_path.write_text(json.dumps(result), encoding="utf-8")

        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))
        assert plan["summary"]["total_failed"] == 3
        assert plan["summary"]["repair_items_count"] == 3
        # Check classification counts
        assert plan["classified_errors"].get(ERROR_TYPE_TYPE_ERROR, 0) == 1
        assert plan["classified_errors"].get(ERROR_TYPE_MISSING_IMPORT, 0) == 1
        assert plan["classified_errors"].get(ERROR_TYPE_TIMEOUT, 0) == 1

    def test_blocked_actions_present(self, tmp_path):
        """Plan includes blocked_actions list."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))
        assert isinstance(plan["blocked_actions"], list)
        assert len(plan["blocked_actions"]) > 0
        assert "read-only" in plan["blocked_actions"][-1].lower()

    def test_suspected_files_extracted(self, tmp_path):
        """suspected_files extracted from stderr traceback."""
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        result["results"][0]["stderr_tail"] = (
            'File "C:\\project\\src\\main.py", line 42, in run\n'
            "ModuleNotFoundError: No module named 'requests'"
        )
        verify_path.write_text(json.dumps(result), encoding="utf-8")
        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))
        item = plan["repair_items"][0]
        assert len(item["suspected_files"]) >= 1
        assert "main.py" in str(item["suspected_files"])


# ---------------------------------------------------------------------------
# TestRepairReporters
# ---------------------------------------------------------------------------

class TestRepairReporters:
    """Tests for repair JSON and Markdown reporters."""

    def _make_plan(self, tmp_path) -> dict:
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        verify_path.write_text(json.dumps(result), encoding="utf-8")
        return generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))

    def test_json_reporter_writes_file(self, tmp_path):
        """write_repair_json writes valid JSON to disk."""
        out = tmp_path / "repair.json"
        plan = self._make_plan(tmp_path)
        write_repair_json(out, plan)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["repair_plan_version"] == "0.6.0"
        assert "summary" in data
        assert "repair_items" in data

    def test_markdown_report_contains_summary(self, tmp_path):
        """Markdown report includes Summary section."""
        plan = self._make_plan(tmp_path)
        report = generate_repair_report(plan)
        assert "## 1. Summary" in report
        assert "Total failed commands" in report

    def test_markdown_report_contains_failed_commands(self, tmp_path):
        """Markdown report shows failed commands."""
        plan = self._make_plan(tmp_path)
        report = generate_repair_report(plan)
        assert "## 2. Failed Commands" in report
        assert "pytest" in report

    def test_markdown_report_contains_classification(self, tmp_path):
        """Markdown report shows error classification table."""
        plan = self._make_plan(tmp_path)
        report = generate_repair_report(plan)
        assert "## 3. Error Classification" in report

    def test_markdown_report_contains_repair_items(self, tmp_path):
        """Markdown report shows repair items."""
        plan = self._make_plan(tmp_path)
        report = generate_repair_report(plan)
        assert "## 4. Repair Items" in report

    def test_markdown_report_contains_blocked(self, tmp_path):
        """Markdown report shows blocked actions."""
        plan = self._make_plan(tmp_path)
        report = generate_repair_report(plan)
        assert "## 6. Blocked Actions" in report

    def test_markdown_report_empty_plan(self, tmp_path):
        """Markdown report handles empty plan gracefully."""
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        result["results"][0]["status"] = "passed"
        result["summary"]["passed"] = 1
        result["summary"]["failed"] = 0
        result["failed_commands"] = []
        verify_path.write_text(json.dumps(result), encoding="utf-8")
        plan = generate_repair_plan(verify_path, source_verify_file_override=str(verify_path))
        report = generate_repair_report(plan)
        assert "No failed commands" in report or "No repair items" in report


# ---------------------------------------------------------------------------
# TestRepairCLI
# ---------------------------------------------------------------------------

class TestRepairCLI:
    """End-to-end CLI tests for the repair-plan subcommand."""

    @pytest.fixture(autouse=True)
    def proj_root(self):
        return Path(__file__).resolve().parent.parent

    def test_repair_plan_with_failures(self, tmp_path):
        """CLI repair-plan works with a verify result that has failures."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        out = tmp_path / "repair.md"
        json_out = tmp_path / "repair.json"

        result = _run_cli(
            "repair-plan",
            "--verify", str(verify_path),
            "--out", str(out),
            "--json", str(json_out),
        )
        assert result.returncode == 0
        assert out.exists()
        assert json_out.exists()

    def test_repair_plan_json_generated(self, tmp_path):
        """JSON result contains required fields."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        json_out = tmp_path / "rp.json"

        result = _run_cli("repair-plan", "--verify", str(verify_path), "--json", str(json_out))
        assert result.returncode == 0
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert "repair_plan_version" in data
        assert "repair_items" in data
        assert "blocked_actions" in data

    def test_repair_plan_markdown_generated(self, tmp_path):
        """Markdown report is generated."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        out = tmp_path / "rp.md"

        result = _run_cli("repair-plan", "--verify", str(verify_path), "--out", str(out))
        assert result.returncode == 0
        text = out.read_text(encoding="utf-8")
        assert "## 1. Summary" in text

    def test_verify_not_found(self, tmp_path):
        """Non-existent verify file exits non-zero."""
        result = _run_cli(
            "repair-plan",
            "--verify", str(tmp_path / "nope.json"),
            "--out", str(tmp_path / "rp.md"),
        )
        assert result.returncode != 0

    def test_verify_invalid_json(self, tmp_path):
        """Invalid JSON exits non-zero."""
        vf = tmp_path / "bad.json"
        vf.write_text("not json")
        result = _run_cli(
            "repair-plan",
            "--verify", str(vf),
            "--out", str(tmp_path / "rp.md"),
        )
        assert result.returncode != 0

    def test_empty_plan_for_passing_verify(self, tmp_path):
        """Empty repair plan when verify passed everything."""
        verify_path = tmp_path / "verify.json"
        result = _make_verify_result(tmp_path)
        result["results"][0]["status"] = "passed"
        result["summary"]["passed"] = 1
        result["summary"]["failed"] = 0
        result["failed_commands"] = []
        verify_path.write_text(json.dumps(result), encoding="utf-8")
        out = tmp_path / "rp.md"

        r = _run_cli("repair-plan", "--verify", str(verify_path), "--out", str(out))
        assert r.returncode == 0
        text = out.read_text(encoding="utf-8")
        assert "No failed commands" in text or "No repair items" in text

    def test_repair_audit_written(self, tmp_path):
        """Audit JSONL is written after repair-plan."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        out = tmp_path / "rp.md"
        audit = tmp_path / "audit.jsonl"

        result = _run_cli(
            "repair-plan",
            "--verify", str(verify_path),
            "--out", str(out),
            "--audit", str(audit),
        )
        assert result.returncode == 0
        assert audit.exists()
        lines = audit.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["event_type"] == "repair_plan"

    def test_no_output_specified_fails(self, tmp_path):
        """Requires at least --out or --json."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        result = _run_cli("repair-plan", "--verify", str(verify_path))
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# TestRepairAudit
# ---------------------------------------------------------------------------

class TestRepairAudit:
    """Tests for audit logger repair-plan integration."""

    def test_make_repair_plan_event_fields(self):
        """make_repair_plan_event includes all required fields."""
        plan = {
            "repair_plan_version": "0.6.0",
            "summary": {"total_failed": 2},
        }
        event = make_repair_plan_event(plan, "/tmp/verify.json", "/tmp/repair.json")
        assert event["event_type"] == "repair_plan"
        assert event["version"] == "0.6.0"
        assert "timestamp" in event
        assert event["input_file"] == "/tmp/verify.json"
        assert event["result_json_path"] == "/tmp/repair.json"

    def test_log_audit_event_writes_repair(self, tmp_path):
        """Appending a repair_plan event writes JSONL line."""
        audit = tmp_path / "audit.jsonl"
        event = {
            "event_type": "repair_plan", "version": "0.6.0",
            "timestamp": "2026-01-01T00:00:00Z",
            "input_file": "/x", "summary": {}, "result_json_path": "",
            "backup_or_manifest_path": "/x",
        }
        assert log_audit_event(audit, event)
        assert audit.exists()
        data = json.loads(audit.read_text(encoding="utf-8").strip())
        assert data["event_type"] == "repair_plan"

    def test_repair_audit_write_failure_no_break(self, tmp_path):
        """Audit write failure doesn't break main flow."""
        verify_path = tmp_path / "verify.json"
        verify_path.write_text(json.dumps(_make_verify_result(tmp_path)), encoding="utf-8")
        out = tmp_path / "rp.md"
        audit = tmp_path / "blocked" / "audit.jsonl"
        (tmp_path / "blocked").write_text("blocked")  # block mkdir
        result = _run_cli(
            "repair-plan",
            "--verify", str(verify_path),
            "--out", str(out),
            "--audit", str(audit),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# TestExistingTestsIntegrity
# ---------------------------------------------------------------------------

class TestExistingTestsIntegrity:
    """Ensure new modules don't break existing imports or functionality."""

    def test_all_repair_modules_importable(self):
        import aetherfusion.repair
        import aetherfusion.repair.error_classifier
        import aetherfusion.repair.repair_planner
        import aetherfusion.reporter.repair_json_reporter
        import aetherfusion.reporter.repair_markdown_reporter

    def test_version_is_060(self):
        assert __version__ == "1.0.1"

    def test_cli_help_includes_repair_plan(self):
        """CLI help lists repair-plan subcommand."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "repair-plan" in (result.stdout or "")

    def test_scan_still_works(self, tmp_path):
        """Existing scan command still works."""
        s = tmp_path / "src"
        t = tmp_path / "tgt"
        s.mkdir()
        t.mkdir()
        (s / "readme.md").write_text("# src")
        (t / "readme.md").write_text("# tgt")
        out = tmp_path / "report.md"
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable, "-m", "aetherfusion", "scan",
                "--source", str(s), "--target", str(t),
                "--out", str(out),
            ],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert out.exists()