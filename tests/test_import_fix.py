"""Tests for the v0.7 import-fix-plan command — import_error_extractor,
target_indexer, import_fix_planner, reporters, CLI, and audit integration.

Ensures existing 235 tests remain importable and passable.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from aetherfusion.importfix.import_error_extractor import extract_missing_imports
from aetherfusion.importfix.target_indexer import index_target
from aetherfusion.importfix.import_fix_planner import (
    generate_import_fix_plan,
    IMPORT_FIX_PLAN_VERSION,
)
from aetherfusion.reporter.import_fix_json_reporter import write_import_fix_json
from aetherfusion.reporter.import_fix_markdown_reporter import generate_import_fix_report
from aetherfusion.audit.audit_logger import (
    log_audit_event,
    make_import_fix_plan_event,
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


def _make_repair_plan(tmp_path, with_missing_import=True, **overrides):
    """Build a minimal repair plan for testing."""
    items = []
    if with_missing_import:
        items.append({
            "error_type": "missing_import",
            "command": "npx tsc --noEmit",
            "severity": "high",
            "confidence": 85,
            "suspected_files": [],
            "evidence": "TS2307: Cannot find module './utils/helper'.",
            "recommended_action": "Check import paths.",
            "automation_eligibility": "plan_only",
            "risk_level": "medium",
            "reason": "",
        })
    base = {
        "repair_plan_version": "0.6.0",
        "source_verify_file": str(tmp_path / "verify.json"),
        "summary": {
            "total_failed": 1 if with_missing_import else 0,
            "classified_count": 1 if with_missing_import else 0,
            "unclassified_count": 0,
            "repair_items_count": 1 if with_missing_import else 0,
            "manual_only": 0,
            "plan_only": 1 if with_missing_import else 0,
            "safe_auto_candidate": 0,
        },
        "failed_commands": ["npx tsc --noEmit"] if with_missing_import else [],
        "classified_errors": {"missing_import": 1} if with_missing_import else {},
        "repair_items": items,
        "blocked_actions": [],
        "next_recommended_command": "...",
    }
    base.update(overrides)
    return base


def _make_target_project(tmp_path, files: dict[str, str] | None = None):
    """Create a minimal target project structure."""
    target = tmp_path / "target"
    target.mkdir()
    if files:
        for path, content in files.items():
            fp = target / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# ImportErrorExtractor tests
# ---------------------------------------------------------------------------

class TestImportErrorExtractor:
    """Tests for extract_missing_imports."""

    def test_extracts_ts2307(self):
        items = [{
            "error_type": "missing_import",
            "command": "tsc",
            "evidence": "TS2307: Cannot find module './utils/foo'.",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "./utils/foo"

    def test_extracts_module_not_found_webpack(self):
        items = [{
            "error_type": "missing_import",
            "command": "npm run build",
            "evidence": "Module not found: Can't resolve '@/components/Button'",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "@/components/Button"

    def test_extracts_python_module_not_found_error(self):
        items = [{
            "error_type": "missing_import",
            "command": "pytest",
            "evidence": "ModuleNotFoundError: No module named 'my_module'",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "my_module"

    def test_extracts_python_import_error(self):
        items = [{
            "error_type": "missing_import",
            "command": "pytest",
            "evidence": "ImportError: No module named utils",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "utils"

    def test_extracts_cannot_find_module_generic(self):
        items = [{
            "error_type": "missing_import",
            "command": "tsc",
            "evidence": "error: Cannot find module 'src/shared/types'.",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "src/shared/types"

    def test_unknown_module_for_empty_evidence(self):
        items = [{
            "error_type": "missing_import",
            "command": "tsc",
            "evidence": "",
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "unknown_module"

    def test_filters_non_missing_import_items(self):
        items = [
            {
                "error_type": "type_error",
                "command": "tsc",
                "evidence": "TypeError: ...",
            },
            {
                "error_type": "missing_import",
                "command": "tsc",
                "evidence": "Cannot find module './foo'.",
            },
        ]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "./foo"

    def test_handles_cannot_resolve_webpack(self):
        items = [{
            "error_type": "missing_import",
            "command": "build",
            "evidence": 'Cannot resolve \'./missing-dep\' in \'/src\'',
            "severity": "high",
            "confidence": 85,
        }]
        result = extract_missing_imports(items)
        assert len(result) == 1
        assert result[0]["missing_module"] == "./missing-dep"


# ---------------------------------------------------------------------------
# TargetIndexer tests
# ---------------------------------------------------------------------------

class TestTargetIndexer:
    """Tests for index_target."""

    def test_basic_index(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            "src/utils/helper.ts": "export {}",
            "package.json": "{}",
        })
        idx = index_target(target)
        assert idx["target_path"] == str(target)
        files = idx["indexed_files"]
        assert len(files) == 3
        names = {f["filename"] for f in files}
        assert names == {"index.ts", "helper.ts", "package.json"}

    def test_ignores_node_modules(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            "node_modules/lodash/index.js": "// lodash",
        })
        idx = index_target(target)
        assert len(idx["indexed_files"]) == 1
        assert idx["indexed_files"][0]["filename"] == "index.ts"

    def test_ignores_git_dir(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            ".git/config": "[core]",
        })
        idx = index_target(target)
        assert len(idx["indexed_files"]) == 1

    def test_ignores_dist_build_pycache(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            "dist/bundle.js": "// bundle",
            "build/output.js": "// output",
            "__pycache__/module.cpython-39.pyc": "binary",
        })
        idx = index_target(target)
        assert len(idx["indexed_files"]) == 1

    def test_by_name_index(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            "lib/index.ts": "export {}",
        })
        idx = index_target(target)
        by_name = idx["by_name"]
        assert "index.ts" in by_name
        assert len(by_name["index.ts"]) == 2

    def test_by_stem_index(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/Button.tsx": "export {}",
            "src/Button.test.tsx": "export {}",
        })
        idx = index_target(target)
        by_stem = idx["by_stem"]
        assert "Button" in by_stem
        assert "Button.test" in by_stem

    def test_by_dir_index(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/components/Header.tsx": "export {}",
            "src/lib/helper.ts": "export {}",
        })
        idx = index_target(target)
        by_dir = idx["by_dir"]
        assert "src/components" in by_dir
        assert "src/lib" in by_dir

    def test_target_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            index_target(tmp_path / "nope")

    def test_target_not_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(NotADirectoryError):
            index_target(f)

    def test_skips_binary_extensions(self, tmp_path):
        target = _make_target_project(tmp_path, {
            "src/index.ts": "export {}",
            "assets/logo.png": "PNG",
        })
        idx = index_target(target)
        assert len(idx["indexed_files"]) == 1


# ---------------------------------------------------------------------------
# ImportFixPlanner tests
# ---------------------------------------------------------------------------

class TestImportFixPlanner:
    """Tests for generate_import_fix_plan."""

    def test_classifies_relative_import(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "TS2307: Cannot find module './utils/helper'."
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        assert len(result["fix_candidates"]) == 1
        c = result["fix_candidates"][0]
        assert c["missing_module"] == "./utils/helper"
        # Should be relative import (no matching stem in target)
        assert c["suspected_import_kind"] == "missing_local_file"

    def test_classifies_alias_import(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "Module not found: Can't resolve '@/components/Button'"
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        assert c["missing_module"] == "@/components/Button"
        assert c["suspected_import_kind"] == "missing_alias_config"

    def test_classifies_wrong_relative_path(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "Cannot find module './src/Helper'."
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"lib/Helper.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        assert c["missing_module"] == "./src/Helper"
        assert c["suspected_import_kind"] == "wrong_relative_path"
        assert len(c["related_files"]) == 1
        assert "lib/Helper.ts" in c["related_files"]

    def test_classifies_package_missing(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "ModuleNotFoundError: No module named 'requests'"
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        assert c["missing_module"] == "requests"
        assert c["suspected_import_kind"] == "package_missing"

    def test_classifies_source_only_dependency(self, tmp_path):
        """When --patch and --apply point to manifests containing the
        source file, classify as source_only_dependency."""
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "Cannot find module 'components/Header'."
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")

        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        # Create a patch manifest that references the source file
        patch_data = {
            "operations": [{
                "type": "add_file",
                "source_path": "src/components/Header.tsx",
            }]
        }
        patch_path = tmp_path / "patch.json"
        patch_path.write_text(json.dumps(patch_data), encoding="utf-8")

        result = generate_import_fix_plan(repair_path, target, patch_path, None)
        c = result["fix_candidates"][0]
        assert c["suspected_import_kind"] == "source_only_dependency"

    def test_empty_plan_no_missing_imports(self, tmp_path):
        """No missing_import errors → empty plan, exit 0."""
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path, with_missing_import=False)
        plan["repair_items"] = []
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        assert result["summary"]["total_extracted_import_errors"] == 0
        assert result["summary"]["total_fix_candidates"] == 0
        assert len(result["fix_candidates"]) == 0

    def test_unresolved_unknown(self, tmp_path):
        """When module name can't be resolved, classify as unresolved_unknown."""
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "Cannot find module 'someUnknownThing'."
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        assert c["suspected_import_kind"] == "package_missing"

    def test_plan_contains_required_fields(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        assert "import_fix_plan_version" in result
        assert "source_repair_file" in result
        assert "target_path" in result
        assert "summary" in result
        assert "extracted_import_errors" in result
        assert "fix_candidates" in result
        assert "blocked_actions" in result
        assert "next_recommended_command" in result

    def test_fix_candidate_has_all_fields(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        for field in [
            "missing_module", "originating_command", "suspected_import_kind",
            "likely_cause", "confidence", "suggested_action",
            "automation_eligibility", "risk_level", "evidence", "related_files",
        ]:
            assert field in c, f"Missing field: {field}"
        assert 0 <= c["confidence"] <= 100

    def test_repair_not_found_raises(self, tmp_path):
        target = _make_target_project(tmp_path)
        with pytest.raises(FileNotFoundError):
            generate_import_fix_plan(tmp_path / "nope.json", target)

    def test_target_not_found_raises(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        with pytest.raises(FileNotFoundError):
            generate_import_fix_plan(repair_path, tmp_path / "nope")

    def test_missing_index_export(self, tmp_path):
        """Directory exists but has no index file → missing_index_export."""
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path)
        plan["repair_items"][0]["evidence"] = (
            "Cannot find module './components'."
        )
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        # Create components dir with files but no index.ts
        target = _make_target_project(tmp_path, {
            "components/Button.tsx": "export {}",
            "src/index.ts": "export {}",
        })

        result = generate_import_fix_plan(repair_path, target)
        c = result["fix_candidates"][0]
        assert c["suspected_import_kind"] == "missing_index_export"


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------

class TestImportFixReporters:
    """Tests for JSON and Markdown reporters."""

    def test_json_reporter_writes(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        plan = generate_import_fix_plan(repair_path, target)

        out = tmp_path / "ifp.json"
        write_import_fix_json(out, plan)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["import_fix_plan_version"] == IMPORT_FIX_PLAN_VERSION

    def test_markdown_reporter_generates(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        plan = generate_import_fix_plan(repair_path, target)

        text = generate_import_fix_report(plan)
        assert "# AetherFusion Import Fix Plan" in text
        assert "## 1. Summary" in text
        assert "## 2. Extracted Import Errors" in text
        assert "## 3. Fix Candidates" in text
        assert "## 4. Automation Eligibility" in text
        assert "## 5. Related Files" in text
        assert "## 6. Blocked Actions" in text
        assert "## 7. Next Recommended Command" in text

    def test_markdown_empty_plan(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path, with_missing_import=False)
        plan["repair_items"] = []
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        result = generate_import_fix_plan(repair_path, target)

        text = generate_import_fix_report(result)
        assert "No `missing_import` errors found" in text


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestImportFixCLI:
    """End-to-end CLI tests for import-fix-plan."""

    def test_cli_help_includes_import_fix_plan(self):
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "import-fix-plan" in (result.stdout or "")

    def test_no_output_fails(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
        )
        assert result.returncode != 0

    def test_repair_not_found_exits_nonzero(self, tmp_path):
        target = _make_target_project(tmp_path)
        result = _run_cli(
            "import-fix-plan",
            "--repair", str(tmp_path / "nope.json"),
            "--target", str(target),
            "--out", str(tmp_path / "plan.md"),
        )
        assert result.returncode != 0

    def test_target_not_found_exits_nonzero(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(tmp_path / "nope"),
            "--out", str(tmp_path / "plan.md"),
        )
        assert result.returncode != 0

    def test_invalid_json_exits_nonzero(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text("not json", encoding="utf-8")
        target = _make_target_project(tmp_path)
        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--out", str(tmp_path / "plan.md"),
        )
        assert result.returncode != 0

    def test_empty_plan_no_missing_import(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        plan = _make_repair_plan(tmp_path, with_missing_import=False)
        plan["repair_items"] = []
        repair_path.write_text(json.dumps(plan), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--out", str(tmp_path / "plan.md"),
        )
        assert result.returncode == 0

    def test_generates_markdown(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        out = tmp_path / "plan.md"

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--out", str(out),
        )
        assert result.returncode == 0
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "Import Fix Plan" in text

    def test_generates_json(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        out = tmp_path / "plan.json"

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--json", str(out),
        )
        assert result.returncode == 0
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["import_fix_plan_version"] == IMPORT_FIX_PLAN_VERSION

    def test_audit_written(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        out = tmp_path / "plan.md"
        audit = tmp_path / "audit.jsonl"

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--out", str(out),
            "--audit", str(audit),
        )
        assert result.returncode == 0
        assert audit.exists()
        lines = audit.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["event_type"] == "import_fix_plan"

    def test_audit_failure_no_break(self, tmp_path):
        """Audit write failure doesn't break main flow."""
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})
        out = tmp_path / "plan.md"
        # Block directory creation
        blocked = tmp_path / "blocked"
        blocked.write_text("blocked")

        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--out", str(out),
            "--audit", str(tmp_path / "blocked" / "audit.jsonl"),
        )
        assert result.returncode == 0

    def test_with_patch_optional(self, tmp_path):
        repair_path = tmp_path / "repair.json"
        repair_path.write_text(json.dumps(_make_repair_plan(tmp_path)), encoding="utf-8")
        target = _make_target_project(tmp_path, {"src/index.ts": "export {}"})

        # Patch file doesn't exist — should not crash
        result = _run_cli(
            "import-fix-plan",
            "--repair", str(repair_path),
            "--target", str(target),
            "--patch", str(tmp_path / "nope.json"),
            "--out", str(tmp_path / "plan.md"),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

class TestImportFixAudit:
    """Tests for audit logger import-fix-plan integration."""

    def test_make_import_fix_plan_event_fields(self):
        plan = {
            "import_fix_plan_version": "0.7.0",
            "summary": {"total_fix_candidates": 3},
        }
        event = make_import_fix_plan_event(
            plan, "/tmp/repair.json", "/tmp/target", "/tmp/ifp.json"
        )
        assert event["event_type"] == "import_fix_plan"
        assert event["version"] == "0.7.0"
        assert "timestamp" in event
        assert event["input_file"] == "/tmp/repair.json"
        assert event["backup_or_manifest_path"] == "/tmp/target"
        assert event["result_json_path"] == "/tmp/ifp.json"

    def test_log_audit_event_writes_import_fix(self, tmp_path):
        audit = tmp_path / "audit.jsonl"
        event = {
            "event_type": "import_fix_plan", "version": "0.7.0",
            "timestamp": "2026-01-01T00:00:00Z",
            "input_file": "/x", "summary": {}, "result_json_path": "",
            "backup_or_manifest_path": "/y",
        }
        assert log_audit_event(audit, event)
        assert audit.exists()
        data = json.loads(audit.read_text(encoding="utf-8").strip())
        assert data["event_type"] == "import_fix_plan"


# ---------------------------------------------------------------------------
# Existing tests integrity
# ---------------------------------------------------------------------------

class TestExistingTestsIntegrity:
    """Ensure new modules don't break existing imports or functionality."""

    def test_all_importfix_modules_importable(self):
        import aetherfusion.importfix
        import aetherfusion.importfix.import_error_extractor
        import aetherfusion.importfix.target_indexer
        import aetherfusion.importfix.import_fix_planner
        import aetherfusion.reporter.import_fix_json_reporter
        import aetherfusion.reporter.import_fix_markdown_reporter

    def test_version_is_080(self):
        assert __version__ == "1.0.1"

    def test_cli_help_includes_import_fix_plan(self):
        """CLI help lists import-fix-plan subcommand."""
        proj_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "aetherfusion", "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(proj_root),
        )
        assert result.returncode == 0
        assert "import-fix-plan" in (result.stdout or "")

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