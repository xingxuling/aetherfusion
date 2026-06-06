#!/usr/bin/env python3
"""Smoke test for AetherFusion v1.0.1.

Runs scan → plan → patch --dry-run → fusion-session using the demo projects
in examples/demo-source and examples/demo-target.

Usage:
    python scripts/smoke_test.py

Exit codes:
    0 — smoke test passed
    1 — smoke test failed
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SOURCE_DIR = EXAMPLES_DIR / "demo-source"
TARGET_DIR = EXAMPLES_DIR / "demo-target"
PYTHON = sys.executable


def _run_aetherfusion(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run aetherfusion as a module from the project root."""
    cmd = [PYTHON, "-m", "aetherfusion"] + args
    return subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


def stage(msg: str) -> None:
    """Print a stage banner."""
    print(f"--- {msg} ---")


def check_prerequisites() -> None:
    """Ensure demo projects exist."""
    if not SOURCE_DIR.is_dir():
        sys.exit(f"FAIL: source demo project not found at {SOURCE_DIR}")
    if not TARGET_DIR.is_dir():
        sys.exit(f"FAIL: target demo project not found at {TARGET_DIR}")
    if not (SOURCE_DIR / "src" / "utils").is_dir():
        sys.exit(f"FAIL: demo-source missing src/utils/ directory")
    if (TARGET_DIR / "src" / "utils").exists():
        sys.exit(f"FAIL: demo-target should NOT have src/utils/ directory")


def run_smoke_test() -> int:
    """Execute the full smoke test pipeline. Returns 0 on success, 1 on failure."""
    check_prerequisites()

    # Create a temporary reports directory
    reports_dir = Path(tempfile.mkdtemp(prefix="aetherfusion_smoke_"))
    print(f"Reports directory: {reports_dir}")

    try:
        # ── Step 1: scan ──
        stage("Step 1: scan")
        scan_report = reports_dir / "fusion-report.md"
        scan_map = reports_dir / "fusion-map.json"
        result = _run_aetherfusion([
            "scan",
            "--source", str(SOURCE_DIR),
            "--target", str(TARGET_DIR),
            "--out", str(scan_report),
            "--json", str(scan_map),
        ])
        if result.returncode != 0:
            print(f"FAIL: scan exited with code {result.returncode}")
            print(result.stderr[-500:])
            return 1
        if not scan_map.exists():
            print("FAIL: scan map not generated")
            return 1
        scan_data = json.loads(scan_map.read_text(encoding="utf-8"))
        candidates = scan_data.get("fusion_plan_candidates", [])
        if not candidates:
            print("FAIL: no fusion plan candidates found — demo projects should produce at least one")
            return 1
        print(f"  OK — scan produced {len(candidates)} fusion plan candidate(s)")

        # ── Step 2: plan one module ──
        module_name = candidates[0]["module_name"]
        stage(f"Step 2: plan {module_name}")
        plan_report = reports_dir / f"plan-{module_name}.md"
        plan_json = reports_dir / f"plan-{module_name}.json"
        result = _run_aetherfusion([
            "plan",
            "--map", str(scan_map),
            "--module", module_name,
            "--out", str(plan_report),
            "--json", str(plan_json),
        ])
        if result.returncode != 0:
            print(f"FAIL: plan exited with code {result.returncode}")
            print(result.stderr[-500:])
            return 1
        if not plan_json.exists():
            print("FAIL: plan JSON not generated")
            return 1
        print(f"  OK — plan generated for {module_name}")

        # ── Step 3: patch --dry-run ──
        stage("Step 3: patch --dry-run")
        patch_report = reports_dir / f"patch-{module_name}.md"
        patch_json = reports_dir / f"patch-{module_name}.json"
        patch_diff = reports_dir / f"patch-{module_name}.diff"
        result = _run_aetherfusion([
            "patch",
            "--plan", str(plan_json),
            "--out", str(patch_report),
            "--json", str(patch_json),
            "--diff", str(patch_diff),
            "--dry-run",
        ])
        if result.returncode != 0:
            print(f"FAIL: patch --dry-run exited with code {result.returncode}")
            print(result.stderr[-500:])
            return 1
        if not patch_json.exists():
            print("FAIL: patch JSON not generated")
            return 1
        print(f"  OK — dry-run patch generated for {module_name}")

        # ── Step 4: fusion-session (safe mode) ──
        stage("Step 4: fusion-session (safe mode)")
        session_reports = reports_dir / "session"
        result = _run_aetherfusion([
            "fusion-session",
            "--source", str(SOURCE_DIR),
            "--target", str(TARGET_DIR),
            "--modules", module_name,
            "--reports", str(session_reports),
            "--mode", "safe",
        ])
        if result.returncode != 0:
            print(f"FAIL: fusion-session exited with code {result.returncode}")
            print(result.stderr[-500:])
            return 1

        # Verify session artifacts
        session_json = session_reports / "fusion-session.json"
        session_md = session_reports / "fusion-session.md"
        artifact_index = session_reports / "artifact-index.json"

        for expected_file in [session_json, session_md, artifact_index]:
            if not expected_file.exists():
                print(f"FAIL: missing session artifact: {expected_file}")
                return 1

        # Validate session JSON structure
        session_data = json.loads(session_json.read_text(encoding="utf-8"))
        required_fields = ["session_version", "session_id", "source_path", "target_path",
                           "modules", "mode", "module_results", "artifacts"]
        for field in required_fields:
            if field not in session_data:
                print(f"FAIL: fusion-session.json missing field: {field}")
                return 1

        if session_data["session_version"] != "1.0.1":
            print(f"FAIL: session_version is {session_data['session_version']}, expected 1.0.1")
            return 1

        # Verify artifact index
        index_data = json.loads(artifact_index.read_text(encoding="utf-8"))
        for field in ["session_id", "source", "target", "modules", "artifacts"]:
            if field not in index_data:
                print(f"FAIL: artifact-index.json missing field: {field}")
                return 1

        print(f"  OK — fusion-session artifacts generated and validated")

        # ── Final ──
        stage("All steps passed")
        print("smoke test passed")
        return 0

    finally:
        # Clean up reports directory
        shutil.rmtree(reports_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(run_smoke_test())