"""Tests for the v0.5 verify command — command_detector, safe_runner,
verify_runner, reporters, CLI, and audit integration.

Ensures existing tests remain importable and passable.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aetherfusion.verifier.command_detector import detect_commands
from aetherfusion.verifier.safe_runner import (
    run_single_command,
    run_commands,
    _is_command_allowed,
    ALLOWED_COMMANDS,
)
from aetherfusion.verifier.verify_runner import run_verify
from aetherfusion.reporter.verify_json_reporter import write_verify_json
from aetherfusion.reporter.verify_markdown_reporter import generate_verify_report
from aetherfusion.audit.audit_logger import (
    log_audit_event,
    make_verify_event,
)
from aetherfusion import __version__


# Module-level helper: shared CLI runner for both TestVerifyCLI and TestVerifyAudit
def _run_cli(*args, proj_root=None):
    if proj_root is None:
        proj_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "aetherfusion"] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=str(proj_root),
    )


# ---------------------------------------------------------------------------
# TestCommandDetector
# ---------------------------------------------------------------------------

class TestCommandDetector:
    """Tests for command_detector.detect_commands."""

    def test_detects_package_json_with_build_test_lint(self, tmp_path):
        """Detect build / test / lint / typecheck from package.json scripts."""
        pj = tmp_path / "package.json"
        pj.write_text(json.dumps({
            "scripts": {
                "build": "tsc",
                "test": "jest",
                "lint": "eslint .",
                "typecheck": "tsc --noEmit",
            }
        }), encoding="utf-8")
        commands, detected_stack, has_any = detect_commands(tmp_path)
        assert "npm run build" in commands
        assert "npm run test" in commands
        assert "npm run lint" in commands
        assert "npm run typecheck" in commands
        assert "node" in detected_stack

    def test_detects_tsconfig_suggests_tsc(self, tmp_path):
        """Detect tsconfig.json and suggest npx tsc --noEmit."""
        tc = tmp_path / "tsconfig.json"
        tc.write_text("{}", encoding="utf-8")
        commands, detected_stack, has_any = detect_commands(tmp_path)
        assert "npx tsc --noEmit" in commands
        assert "typescript" in detected_stack

    def test_detects_pytest_ini(self, tmp_path):
        """Detect pytest.ini and suggest pytest."""
        pi = tmp_path / "pytest.ini"
        pi.write_text("[pytest]", encoding="utf-8")
        commands, detected_stack, has_any = detect_commands(tmp_path)
        assert "pytest" in commands
        assert "python" in detected_stack

    def test_detects_pyproject_toml_pytest(self, tmp_path):
        """Detect pyproject.toml with [tool.pytest.ini_options]."""
        ppt = tmp_path / "pyproject.toml"
        ppt.write_text("[tool.pytest.ini_options]\naddopts = \"-v\"", encoding="utf-8")
        commands, detected_stack, has_any = detect_commands(tmp_path)
        assert "pytest" in commands
        assert "python" in detected_stack

    def test_detects_tests_dir(self, tmp_path):
        """Detect tests/ directory with test files and suggest pytest."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_example.py").write_text("def test_pass(): pass")
        commands, detected_stack, no_commands = detect_commands(tmp_path)
        assert "pytest" in commands
        assert "python" in detected_stack

    def test_no_commands_detected(self, tmp_path):
        """Returns empty commands and no_commands=True when nothing found."""
        commands, detected_stack, no_commands = detect_commands(tmp_path)
        assert commands == []
        assert detected_stack == []
        assert no_commands is True

    def test_combined_detection(self, tmp_path):
        """When both Node and Python configs detected, both stacks reported."""
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
        (tmp_path / "pytest.ini").write_text("[pytest]")
        commands, detected_stack, has_any = detect_commands(tmp_path)
        assert "npm run test" in commands
        assert "pytest" in commands
        assert "node" in detected_stack
        assert "python" in detected_stack


# ---------------------------------------------------------------------------
# TestSafeRunner
# ---------------------------------------------------------------------------

class TestSafeRunner:
    """Tests for safe_runner."""

    def test_allowed_accepts_valid_commands(self):
        allowed_ids = ["npm run build", "npm test", "npm run test",
                        "npm run lint", "npm run typecheck",
                        "npx tsc --noEmit", "pytest", "python -m pytest"]
        for cmd in allowed_ids:
            ok, _ = _is_command_allowed(cmd)
            assert ok, f"Expected allowed: {cmd}"

    def test_blocked_rejects_rm_del(self):
        for cmd in ["rm -rf /", "del /f /s C:\\Windows", "rmdir /s /q ."]:
            ok, reason = _is_command_allowed(cmd)
            assert not ok, f"Expected blocked: {cmd}"

    def test_blocked_rejects_curl_wget(self):
        for cmd in ["curl http://evil.com", "wget http://evil.com"]:
            ok, _ = _is_command_allowed(cmd)
            assert not ok

    def test_blocked_rejects_git_push(self):
        for cmd in ["git push origin main", "git push --force"]:
            ok, _ = _is_command_allowed(cmd)
            assert not ok

    def test_blocked_rejects_install_commands(self):
        for cmd in ["npm install", "pip install requests", "python -m pip install pytest"]:
            ok, _ = _is_command_allowed(cmd)
            assert not ok

    def test_blocked_rejects_shell_splicing(self):
        for cmd in ["npm run build && rm -rf /", "pytest; curl evil.com"]:
            ok, _ = _is_command_allowed(cmd)
            assert not ok

    def test_run_single_command_timeout(self, tmp_path):
        """Commands exceeding timeout are recorded as timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("sleep 130", 120)
            result = run_single_command("npm run build", tmp_path, timeout=0.1)
        assert result["status"] == "timeout"
        assert "timed out" in result["reason"].lower()

    def test_run_single_command_blocked(self, tmp_path):
        """Non-whitelisted command is blocked."""
        result = run_single_command("rm -rf /", tmp_path)
        assert result["status"] == "blocked"
        assert "forbidden" in result["reason"].lower()

    def test_run_commands_single_failure_does_not_stop(self, tmp_path):
        """When one command fails, remaining commands still execute."""
        results = []
        def side_effect(cmd, cwd, timeout):
            r = {
                "command": cmd, "status": "blocked", "exit_code": None,
                "duration_ms": 0, "stdout_tail": "", "stderr_tail": "",
                "reason": "mock",
            }
            results.append(r)
            return r

        with patch("aetherfusion.verifier.safe_runner.run_single_command", side_effect=side_effect):
            run_commands(["cmd1", "cmd2", "cmd3"], tmp_path)
        assert len(results) == 3

    def test_run_commands_passes_cwd(self, tmp_path):
        with patch("aetherfusion.verifier.safe_runner.run_single_command") as mock:
            mock.return_value = {
                "command": "pytest", "status": "passed", "exit_code": 0,
                "duration_ms": 100, "stdout_tail": "", "stderr_tail": "",
                "reason": "",
            }
            run_commands(["pytest"], tmp_path)
            mock.assert_called_once_with("pytest", tmp_path, timeout=120)


# ---------------------------------------------------------------------------
# TestVerifyRunner
# ---------------------------------------------------------------------------

class TestVerifyRunner:
    """Tests for verify_runner.run_verify."""

    def test_run_verify_with_auto_detect(self, tmp_path):
        """Auto-detects commands from config files and returns full result."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        result = run_verify(tmp_path)
        assert result["verify_version"] == __version__
        assert str(tmp_path.resolve()) in str(result["target_path"])
        assert "detected_stack" in result
        assert "commands_detected" in result
        assert "commands_run" in result
        assert "summary" in result
        assert "results" in result
        assert "failed_commands" in result
        assert "skipped_commands" in result
        assert "next_recommended_command" in result

    def test_run_verify_with_explicit_commands(self, tmp_path):
        """When --commands provided, uses them instead of auto-detect."""
        (tmp_path / "package.json").write_text(json.dumps(
            {"scripts": {"test": "jest"}}))
        result = run_verify(tmp_path, commands=["pytest"])
        assert "pytest" in result["commands_run"]
        assert "npm run test" not in result["commands_run"]

    def test_run_verify_nonexistent_target_raises(self):
        """Non-existent path raises ValueError."""
        with pytest.raises(ValueError):
            run_verify(Path("C:/nonexistent_path_xyz_12345"))

    def test_run_verify_not_a_directory_raises(self, tmp_path):
        """File path instead of directory raises FileNotFoundError."""
        f = tmp_path / "not_a_dir.txt"
        f.write_text("hello")
        with pytest.raises(FileNotFoundError):
            run_verify(f)


# ---------------------------------------------------------------------------
# TestVerifyReporters
# ---------------------------------------------------------------------------

class TestVerifyReporters:
    """Tests for verify JSON and Markdown reporters."""

    def _make_result(self, **overrides):
        base = {
            "verify_version": "0.5.0",
            "target_path": "/tmp/test-proj",
            "detected_stack": ["python"],
            "commands_detected": ["pytest"],
            "commands_run": ["pytest"],
            "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "timeout": 0, "blocked": 0},
            "results": [
                {
                    "command": "pytest", "status": "passed", "exit_code": 0,
                    "duration_ms": 234, "stdout_tail": "3 passed",
                    "stderr_tail": "", "reason": "",
                }
            ],
            "failed_commands": [],
            "skipped_commands": [],
            "next_recommended_command": "python -m aetherfusion apply --patch ... --confirm",
        }
        base.update(overrides)
        return base

    def test_json_reporter_writes_file(self, tmp_path):
        """write_verify_json writes valid JSON to disk."""
        out = tmp_path / "verify.json"
        result = self._make_result()
        write_verify_json(out, result)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["verify_version"] == "0.5.0"

    def test_markdown_report_contains_summary(self):
        """Markdown report includes Summary section with pass count."""
        result = self._make_result()
        report = generate_verify_report(result)
        assert "## 1. Summary" in report
        assert "| 1 |" in report
        assert "pytest" in report

    def test_markdown_report_includes_failed(self):
        """Markdown report shows Failed section when commands fail."""
        result = self._make_result()
        result["summary"]["failed"] = 1
        result["summary"]["passed"] = 0
        result["results"] = [
            {
                "command": "pytest", "status": "failed", "exit_code": 1,
                "duration_ms": 500, "stdout_tail": "",
                "stderr_tail": "AssertionError",
                "reason": "test failed",
            }
        ]
        report = generate_verify_report(result)
        assert "## 5. Failed" in report
        assert "AssertionError" in report

    def test_markdown_report_includes_blocked(self):
        """Markdown report shows blocked commands."""
        result = self._make_result(summary={"total": 1, "passed": 0, "failed": 0, "skipped": 0, "timeout": 0, "blocked": 1})
        result["results"] = [
            {
                "command": "rm -rf /", "status": "blocked", "exit_code": None,
                "duration_ms": 0, "stdout_tail": "", "stderr_tail": "",
                "reason": "not whitelisted",
            }
        ]
        report = generate_verify_report(result)
        assert "## 6. Skipped / Blocked" in report

    def test_markdown_report_no_results(self):
        """Markdown report handles no detected commands gracefully."""
        result = self._make_result(
            detected_stack=[],
            commands_detected=[],
            commands_run=[],
            results=[],
            summary={"total": 0, "passed": 0, "failed": 0, "skipped": 0, "timeout": 0, "blocked": 0},
        )
        report = generate_verify_report(result)
        assert "No commands were executed" in report


# ---------------------------------------------------------------------------
# TestVerifyCLI
# ---------------------------------------------------------------------------

class TestVerifyCLI:
    """End-to-end CLI tests for the verify subcommand."""

    @pytest.fixture(autouse=True)
    def proj_root(self):
        return Path(__file__).resolve().parent.parent

    # _run_cli is the module-level helper defined above for reuse across test classes.

    def test_verify_with_pytest_ini(self, tmp_path):
        """CLI verify works with a pytest.ini project."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        out = tmp_path / "verify-out.md"
        json_out = tmp_path / "verify-out.json"
        audit = tmp_path / "audit.jsonl"
        result = _run_cli(
            "verify", "--target", str(tmp_path),
            "--out", str(out), "--json", str(json_out),
            "--audit", str(audit),
        )
        assert result.returncode == 0
        assert out.exists()
        assert json_out.exists()

    def test_verify_json_result_generated(self, tmp_path):
        """JSON result contains required fields."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        json_out = tmp_path / "v.json"
        result = _run_cli("verify", "--target", str(tmp_path), "--json", str(json_out))
        assert result.returncode == 0
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert "verify_version" in data
        assert "summary" in data
        assert "results" in data

    def test_verify_markdown_generated(self, tmp_path):
        """Markdown report is generated."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        out = tmp_path / "v.md"
        result = _run_cli("verify", "--target", str(tmp_path), "--out", str(out))
        assert result.returncode == 0
        text = out.read_text(encoding="utf-8")
        assert "## 1. Summary" in text

    def test_verify_target_not_exists(self, tmp_path):
        """Non-existent target exits non-zero."""
        result = _run_cli(
            "verify", "--target", str(tmp_path / "does_not_exist"),
            "--out", str(tmp_path / "v.md"),
        )
        assert result.returncode != 0

    def test_verify_no_output_specified_fails(self, tmp_path):
        """Requires at least --out or --json."""
        result = _run_cli("verify", "--target", str(tmp_path))
        assert result.returncode != 0

    def test_verify_with_explicit_commands(self, tmp_path):
        """Explicit --commands are used and safe."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        out = tmp_path / "v.md"
        result = _run_cli(
            "verify", "--target", str(tmp_path),
            "--commands", "pytest",
            "--out", str(out),
        )
        assert result.returncode == 0
        assert "pytest" in result.stdout

    def test_verify_blocked_command_logged(self, tmp_path):
        """Non-whitelisted command is recorded as blocked."""
        out = tmp_path / "v.md"
        result = _run_cli(
            "verify", "--target", str(tmp_path),
            "--commands", "rm -rf /",
            "--out", str(out),
        )
        assert result.returncode == 0
        text = out.read_text(encoding="utf-8")
        assert "blocked" in text.lower()

    def test_verify_audit_written(self, tmp_path):
        """Audit JSONL is written after verify."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        out = tmp_path / "v.md"
        audit = tmp_path / "audit.jsonl"
        result = _run_cli(
            "verify", "--target", str(tmp_path),
            "--out", str(out), "--audit", str(audit),
        )
        assert result.returncode == 0
        assert audit.exists()
        lines = audit.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["event_type"] == "verify"


# ---------------------------------------------------------------------------
# TestVerifyAudit
# ---------------------------------------------------------------------------

class TestVerifyAudit:
    """Tests for audit logger verify integration."""

    def test_make_verify_event_fields(self):
        """make_verify_event includes all required fields."""
        result = {
            "verify_version": "0.5.0",
            "summary": {"total": 1, "passed": 1},
        }
        event = make_verify_event(result, "/tmp/target", "/tmp/result.json")
        assert event["event_type"] == "verify"
        assert event["version"] == "0.5.0"
        assert "timestamp" in event
        assert event["input_file"] == "/tmp/target"
        assert event["result_json_path"] == "/tmp/result.json"
        assert event["summary"] == {"total": 1, "passed": 1}

    def test_log_audit_event_writes_verify(self, tmp_path):
        """Appending a verify event writes JSONL line."""
        audit = tmp_path / "audit.jsonl"
        event = {
            "event_type": "verify", "version": "0.5.0",
            "timestamp": "2026-01-01T00:00:00Z",
            "input_file": "/x", "summary": {}, "result_json_path": "",
            "backup_or_manifest_path": "/x",
        }
        assert log_audit_event(audit, event)
        assert audit.exists()
        data = json.loads(audit.read_text(encoding="utf-8").strip())
        assert data["event_type"] == "verify"

    def test_verify_audit_write_failure_no_break(self, tmp_path):
        """Audit write failure doesn't break main flow (CLI just prints WARNING)."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        out = tmp_path / "v.md"
        # point audit at a path where the parent is not writable (a file)
        audit = tmp_path / "blocked" / "audit.jsonl"
        # create blocked as a regular file so mkdir fails
        (tmp_path / "blocked").write_text("blocked")
        result = _run_cli(
            "verify", "--target", str(tmp_path),
            "--out", str(out), "--audit", str(audit),
        )
        # Should still succeed (return code 0)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# TestExistingTestsIntegrity
# ---------------------------------------------------------------------------

class TestExistingTestsIntegrity:
    """Ensure new modules don't break existing imports or functionality."""

    def test_all_verify_modules_importable(self):
        import aetherfusion.verifier
        import aetherfusion.verifier.command_detector
        import aetherfusion.verifier.safe_runner
        import aetherfusion.verifier.verify_runner
        import aetherfusion.reporter.verify_json_reporter
        import aetherfusion.reporter.verify_markdown_reporter

    def test_version_is_050(self):
        assert __version__ == "1.0.1"

    def test_cli_help_includes_verify(self):
        """CLI help lists verify subcommand."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "verify" in (result.stdout or "")

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# _run_cli is used by both TestVerifyCLI and TestVerifyAudit via the module-level helper.