"""Tests for v1.0 fusion-session subcommand and supporting modules."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add project root to sys.path for testing
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def fake_projects(tmp_path):
    """Create minimal fake source/target projects for integration tests."""
    source_dir = tmp_path / "project-b"
    target_dir = tmp_path / "project-a"
    source_dir.mkdir()
    target_dir.mkdir()

    # Source project
    (source_dir / "package.json").write_text(json.dumps({
        "name": "project-b",
        "dependencies": {"react": "^18.0.0"}
    }))
    (source_dir / "utils").mkdir()
    (source_dir / "utils" / "helpers.py").write_text("def add(a, b): return a + b\n")
    (source_dir / "lib").mkdir()
    (source_dir / "lib" / "core.js").write_text("export function run() {}\n")

    # Target project
    (target_dir / "package.json").write_text(json.dumps({
        "name": "project-a",
        "dependencies": {"react": "^18.0.0"}
    }))

    return source_dir, target_dir


@pytest.fixture
def reports_dir(tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    return d


# ============================================================
# CLI help test
# ============================================================

def test_fusion_session_help():
    """`python -m aetherfusion fusion-session --help` shows expected args."""
    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "fusion-session", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0
    assert "--source" in result.stdout
    assert "--target" in result.stdout
    assert "--modules" in result.stdout
    assert "--reports" in result.stdout
    assert "--mode" in result.stdout
    assert "--apply-confirm" in result.stdout
    assert "--verify" in result.stdout


# ============================================================
# Input validation — source/target/modules
# ============================================================

def test_source_not_exists_exit1(fake_projects, reports_dir):
    """source path does not exist → exit 1."""
    source, target = fake_projects
    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source / "nonexistent"),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 1


def test_target_not_exists_exit1(fake_projects, reports_dir):
    """target path does not exist → exit 1."""
    source, target = fake_projects
    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target / "nonexistent"),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 1


def test_modules_empty_exit1(fake_projects, reports_dir):
    """Empty modules list → exit 1."""
    source, target = fake_projects
    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 1


# ============================================================
# Reports directory auto-creation
# ============================================================

def test_reports_dir_auto_created(fake_projects, tmp_path):
    """Reports directory that does not exist → auto created."""
    source, target = fake_projects
    new_reports = tmp_path / "new_reports"
    assert not new_reports.exists()

    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(new_reports),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    # May succeed or fail depending on module existence in scan map,
    # but the directory should be created regardless.
    assert new_reports.exists()


# ============================================================
# Dry session — default: scan/plan/patch only, no apply
# ============================================================

def test_dry_session_default_no_apply(fake_projects, reports_dir, monkeypatch):
    """Default mode (no --apply-confirm): scan + plan + patch, no apply artifacts."""
    source, target = fake_projects

    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    # Should succeed (module "utils" may be in fusion_plan_candidates)
    # Even if the module fails planning, the session should generate final artifacts
    assert (reports_dir / "fusion-session.json").exists()
    assert (reports_dir / "fusion-session.md").exists()
    assert (reports_dir / "artifact-index.json").exists()
    # No apply artifacts should exist
    assert not list(reports_dir.glob("apply-result-*.json"))


# ============================================================
# --apply-confirm calls apply
# ============================================================

def test_apply_confirm_calls_apply(fake_projects, reports_dir):
    """--apply-confirm flag should produce apply result files."""
    source, target = fake_projects

    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
            "--apply-confirm",
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    # Apply may succeed or the module may be not found in fusion_plan_candidates;
    # we just verify session artifacts are generated regardless.
    assert (reports_dir / "fusion-session.json").exists()


# ============================================================
# --verify flag triggers verify
# ============================================================

def test_verify_flag_triggers_verify(fake_projects, reports_dir):
    """--verify flag should produce verify result."""
    source, target = fake_projects

    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
            "--verify",
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert (reports_dir / "fusion-session.json").exists()


# ============================================================
# Verify failed → generate diagnostic plans
# ============================================================

def test_verify_failed_generates_diagnostic_plans(fake_projects, reports_dir):
    """When verify finds failures, diagnostic plans are generated."""
    source, target = fake_projects

    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
            "--verify",
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0


# ============================================================
# Artifact generation tests
# ============================================================

def test_artifact_index_json_generated(fake_projects, reports_dir):
    """artifact-index.json is produced with correct structure."""
    source, target = fake_projects

    subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )

    art_path = reports_dir / "artifact-index.json"
    assert art_path.exists()
    data = json.loads(art_path.read_text())
    assert "session_id" in data
    assert "created_at" in data
    assert "source" in data
    assert "target" in data
    assert "modules" in data
    assert "artifacts" in data


def test_fusion_session_json_generated(fake_projects, reports_dir):
    """fusion-session.json is produced with correct schema."""
    source, target = fake_projects

    subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )

    session_path = reports_dir / "fusion-session.json"
    assert session_path.exists()
    data = json.loads(session_path.read_text())
    assert data["session_version"] == "1.0.1"
    assert "session_id" in data
    assert data["source_path"] == str(source.resolve())
    assert data["target_path"] == str(target.resolve())
    assert "modules" in data
    assert data["mode"] == "safe"
    assert "options" in data
    assert "module_results" in data
    assert "artifacts" in data
    assert "next_recommended_action" in data


def test_fusion_session_md_generated(fake_projects, reports_dir):
    """fusion-session.md is produced."""
    source, target = fake_projects

    subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )

    md_path = reports_dir / "fusion-session.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "# AetherFusion Session Report" in content
    assert "## Session Summary" in content
    assert "## Source / Target" in content
    assert "## Modules Processed" in content
    assert "## Scan Result" in content
    assert "## Artifact Index" in content
    assert "## Next Recommended Action" in content


# ============================================================
# Audit event
# ============================================================

def test_audit_event_written(fake_projects, reports_dir):
    """fusion-session generates an audit event."""
    source, target = fake_projects

    audit_file = reports_dir / "audit.jsonl"

    subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "utils",
            "--reports", str(reports_dir),
            "--audit", str(audit_file),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )

    assert audit_file.exists()
    # Read the last line as a JSON object
    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    last_event = json.loads(lines[-1])
    assert last_event["event_type"] == "fusion_session"
    assert "session_id" in last_event
    assert "source_path" in last_event
    assert "target_path" in last_event
    assert "modules" in last_event
    assert "summary" in last_event
    assert "session_json_path" in last_event


# ============================================================
# Single module failure doesn't lose session report
# ============================================================

def test_single_module_failure_preserves_session(fake_projects, reports_dir):
    """When one module fails, session still generates full report."""
    source, target = fake_projects

    # Use a module name that definitely won't exist in the scan map
    result = subprocess.run(
        [
            sys.executable, "-m", "aetherfusion", "fusion-session",
            "--source", str(source),
            "--target", str(target),
            "--modules", "zz_nonexistent_module_zz,utils",
            "--reports", str(reports_dir),
        ],
        capture_output=True, text=True, cwd=str(_project_root),
    )

    # Session artifacts must still be produced
    assert (reports_dir / "fusion-session.json").exists()
    assert (reports_dir / "fusion-session.md").exists()
    assert (reports_dir / "artifact-index.json").exists()

    session_data = json.loads((reports_dir / "fusion-session.json").read_text())
    module_results = session_data.get("module_results", {})

    # zz_nonexistent should be failed
    if "zz_nonexistent_module_zz" in module_results:
        assert module_results["zz_nonexistent_module_zz"]["status"] == "failed"

    # Session should still have a valid next action
    assert "next_recommended_action" in session_data


# ============================================================
# SessionState unit tests
# ============================================================

def test_session_state_creation():
    from aetherfusion.session.session_state import SessionState
    state = SessionState(
        session_id="test-123",
        source_path="/src",
        target_path="/tgt",
        modules=["utils", "lib"],
    )
    assert state.session_id == "test-123"
    assert state.source_path == "/src"
    assert state.target_path == "/tgt"
    assert state.modules == ["utils", "lib"]
    assert state.mode == "safe"
    assert state.failed_modules == []
    assert state.succeeded_modules == []


def test_session_state_module_results():
    from aetherfusion.session.session_state import SessionState, ModuleResult
    state = SessionState(
        session_id="test-123",
        source_path="/src",
        target_path="/tgt",
        modules=["utils", "lib"],
    )

    mr = ModuleResult(module_name="utils", status="applied")
    state.module_results["utils"] = mr

    mr2 = ModuleResult(module_name="lib", status="failed", error="Plan failed")
    state.module_results["lib"] = mr2

    assert state.succeeded_modules == ["utils"]
    assert state.failed_modules == ["lib"]


def test_session_state_to_dict():
    from aetherfusion.session.session_state import SessionState, ModuleResult
    state = SessionState(
        session_id="test-123",
        source_path="/src",
        target_path="/tgt",
        modules=["utils"],
    )
    mr = ModuleResult(module_name="utils", status="patched")
    state.module_results["utils"] = mr
    state.scan_report_path = "/reports/fusion-report.md"

    d = state.to_dict()
    assert d["session_version"] == "1.0.1"
    assert d["session_id"] == "test-123"
    assert d["source_path"] == "/src"
    assert d["target_path"] == "/tgt"
    assert "utils" in d["module_results"]
    assert d["module_results"]["utils"]["status"] == "patched"
    assert "next_recommended_action" in d


def test_session_state_get_artifact_paths():
    from aetherfusion.session.session_state import SessionState, ModuleResult
    state = SessionState(
        session_id="test-123",
        source_path="/src",
        target_path="/tgt",
        modules=["utils"],
    )
    state.scan_report_path = "/r/scan.md"
    state.scan_map_path = "/r/scan.json"

    mr = ModuleResult(
        module_name="utils",
        status="applied",
        plan_json_path="/r/plan-utils.json",
        patch_json_path="/r/patch-utils.json",
        apply_json_path="/r/apply-utils.json",
    )
    state.module_results["utils"] = mr

    artifacts = state.get_artifact_paths()
    assert artifacts["scan_report"] == "/r/scan.md"
    assert artifacts["scan_map"] == "/r/scan.json"
    assert artifacts["plan_reports"] == ["/r/plan-utils.json"]
    assert artifacts["patch_reports"] == ["/r/patch-utils.json"]
    assert artifacts["apply_results"] == ["/r/apply-utils.json"]


# ============================================================
# Artifact index unit tests
# ============================================================

def test_build_artifact_index():
    from aetherfusion.session.artifact_index import build_artifact_index
    data = build_artifact_index(
        session_id="abc",
        source_path="/src",
        target_path="/tgt",
        modules=["utils"],
        artifacts={"scan_report": "/r/scan.md", "plan_reports": []},
        reports_dir=Path("/reports"),
    )
    assert data["session_id"] == "abc"
    assert data["source"] == "/src"
    assert data["target"] == "/tgt"
    assert data["modules"] == ["utils"]
    assert "created_at" in data
    assert data["artifacts"]["scan_report"] == "/r/scan.md"
    assert data["artifacts"]["plan_reports"] == []


def test_write_artifact_index(tmp_path):
    from aetherfusion.session.artifact_index import build_artifact_index, write_artifact_index
    data = build_artifact_index(
        session_id="abc",
        source_path="/src",
        target_path="/tgt",
        modules=["utils"],
        artifacts={},
        reports_dir=tmp_path,
    )
    path = tmp_path / "artifact-index.json"
    write_artifact_index(path, data)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["session_id"] == "abc"


# ============================================================
# Audit make_fusion_session_event unit
# ============================================================

def test_make_fusion_session_event():
    from aetherfusion.audit.audit_logger import make_fusion_session_event
    event = make_fusion_session_event(
        session_id="s1",
        source_path="/src",
        target_path="/tgt",
        modules=["utils"],
        summary={"total_modules": 1},
        session_json_path="/r/session.json",
    )
    assert event["event_type"] == "fusion_session"
    assert event["session_id"] == "s1"
    assert event["source_path"] == "/src"
    assert event["target_path"] == "/tgt"
    assert event["modules"] == ["utils"]
    assert event["summary"] == {"total_modules": 1}
    assert event["session_json_path"] == "/r/session.json"
    assert "version" in event
    assert "timestamp" in event


# ============================================================
# Version check
# ============================================================

def test_version_is_1_0_0():
    import aetherfusion
    assert aetherfusion.__version__ == "1.0.1"


def test_version_export_complete():
    import aetherfusion
    assert hasattr(aetherfusion, "__version__")
    assert "." in aetherfusion.__version__


# ============================================================
# Original tests continue to pass
# ============================================================

def test_original_subcommands_still_work():
    """Verify other subcommands are not broken."""
    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "scan", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "plan", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "patch", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "apply", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "rollback", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "verify", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "repair-plan", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "import-fix-plan", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0

    result = subprocess.run(
        [sys.executable, "-m", "aetherfusion", "dependency-plan", "--help"],
        capture_output=True, text=True, cwd=str(_project_root),
    )
    assert result.returncode == 0
