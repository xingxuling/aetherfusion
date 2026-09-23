from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from aetherfusion.capability.analyzer import analyze_project_capabilities
from aetherfusion.capability.planner import generate_capability_fusion_plan
from aetherfusion.capability.strategy import choose_strategy


APACHE = """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/
"""


def make_project(
    tmp_path: Path,
    name: str,
    files: dict[str, str],
    license_text: str | None = APACHE,
) -> Path:
    root = tmp_path / name
    root.mkdir()
    if license_text is not None:
        (root / "LICENSE").write_text(license_text, encoding="utf-8")
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def test_detect_android_device_control(tmp_path):
    source = make_project(tmp_path, "artemis", {
        "android/bridge.py": (
            "def run_adb(): pass\n"
            "# AccessibilityService + uiautomator device controller"
        ),
        "README.md": "Android device control through ADB and scrcpy",
    })
    profile = analyze_project_capabilities(source)
    ids = {c.capability_id for c in profile.capabilities}
    assert "android-device-control" in ids
    assert profile.license["detected"] == "Apache-2.0"


def test_detect_agent_and_tokenization(tmp_path):
    source = make_project(tmp_path, "agents", {
        "src/agent.py": "agent planner tool call mcp orchestrator",
        "src/tokenizer.py": "tokenizer byte pair encoding bpe tokenization",
    })
    profile = analyze_project_capabilities(source)
    ids = {c.capability_id for c in profile.capabilities}
    assert "agent-orchestration" in ids
    assert "tokenization-representation" in ids


def test_sparse_runtime_defaults_to_absorb(tmp_path):
    source = make_project(tmp_path, "edge", {
        "runtime/moe.py": (
            "mixture of experts expert routing paging offload "
            "prefetch quantization"
        ),
    })
    profile = analyze_project_capabilities(source)
    cap = next(
        c for c in profile.capabilities
        if c.capability_id == "sparse-model-runtime"
    )
    decision = choose_strategy(
        cap,
        already_present=False,
        license_gate="allowed_with_notice",
    )
    assert decision.strategy == "ABSORB"


def test_android_defaults_to_wrap(tmp_path):
    source = make_project(tmp_path, "android", {
        "adb/device.py": "adb uiautomator accessibilityservice scrcpy",
    })
    profile = analyze_project_capabilities(source)
    cap = next(
        c for c in profile.capabilities
        if c.capability_id == "android-device-control"
    )
    decision = choose_strategy(
        cap,
        already_present=False,
        license_gate="allowed_with_notice",
    )
    assert decision.strategy == "WRAP"


def test_planner_marks_gap_and_overlap(tmp_path):
    source = make_project(tmp_path, "source", {
        "adb/device.py": "adb uiautomator accessibilityservice scrcpy",
        "token/tokenizer.py": "tokenizer tokenization byte pair encoding bpe",
    })
    target = make_project(tmp_path, "target", {
        "device/android.py": (
            "android device adb accessibilityservice uiautomator"
        ),
    })
    plan = generate_capability_fusion_plan(
        source,
        target,
        project_url="https://example.invalid/source",
    )
    by_id = {
        item["capability"]["capability_id"]: item
        for item in plan["fusion_decisions"]
    }
    assert by_id["android-device-control"]["target_state"] == "overlap"
    assert by_id["tokenization-representation"]["target_state"] == "gap"
    assert plan["execution_contract"]["read_only"] is True
    assert plan["schema_version"] == "2.0-alpha.1"


def test_unknown_license_is_review_gate(tmp_path):
    source = make_project(
        tmp_path,
        "unknown",
        {"src/agent.py": "agent tool call planner"},
        license_text=None,
    )
    profile = analyze_project_capabilities(source)
    assert profile.license["gate"] == "review_required"
    assert profile.license["legal_review_required"] is True


def test_cli_writes_reports(tmp_path):
    source = make_project(
        tmp_path,
        "source",
        {
            "runtime/moe.py": (
                "expert routing paging offload prefetch quantization"
            )
        },
    )
    target = make_project(tmp_path, "target", {"README.md": "plain target"})
    out_md = tmp_path / "plan.md"
    out_json = tmp_path / "plan.json"
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aetherfusion.capability.cli",
            "--source",
            str(source),
            "--target",
            str(target),
            "--out",
            str(out_md),
            "--json",
            str(out_json),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_md.exists()
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0-alpha.1"
    assert "sparse-model-runtime" in {
        item["capability"]["capability_id"]
        for item in data["fusion_decisions"]
    }


def test_cli_strict_license_exit2(tmp_path):
    source = make_project(
        tmp_path,
        "source",
        {"src/agent.py": "agent planner tool call"},
        license_text=None,
    )
    target = make_project(tmp_path, "target", {"README.md": "target"})
    out_json = tmp_path / "plan.json"
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "aetherfusion.capability.cli",
            "--source",
            str(source),
            "--target",
            str(target),
            "--json",
            str(out_json),
            "--strict-license",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 2
    assert out_json.exists()
