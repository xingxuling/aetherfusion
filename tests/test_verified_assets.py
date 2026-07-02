"""Regression tests for verified runtime assets and path containment."""

import hashlib
import json
from pathlib import Path

import pytest

from aetherfusion.applier.safe_apply import apply_patch
from aetherfusion.patcher.dry_run_patch_generator import generate_dry_run_patch
from aetherfusion.planner.fusion_planner import generate_fusion_plan


def _write_plan(path: Path, source: Path, target: Path, module: str = "engines") -> None:
    path.write_text(json.dumps({
        "plan_version": "1.0.1",
        "module_name": module,
        "module_type": module,
        "source_module_path": str(source),
        "target_match_path": str(target),
        "risk_level": "medium",
        "strategy": "copy_to_target",
    }), encoding="utf-8")


def _write_patch(path: Path, source: Path, target: Path, operations: list[dict]) -> None:
    path.write_text(json.dumps({
        "patch_version": "1.0.1",
        "mode": "dry_run",
        "module_name": "engines",
        "module_type": "engines",
        "source_module_path": str(source),
        "target_match_path": str(target),
        "operations": operations,
    }), encoding="utf-8")


def test_source_only_module_gets_deterministic_target_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    module = source / "engines"
    module.mkdir(parents=True)
    target.mkdir()
    mapping = {
        "projects": {
            "source": {"name": "source", "path": str(source)},
            "target": {"name": "target", "path": str(target)},
        },
        "conflicts": {},
        "dependencies": {},
        "fusion_plan_candidates": [{
            "module_name": "engines",
            "module_type": "engines",
            "source_paths": [str(module)],
            "target_paths": [],
            "recommended_action": "copy_to_target",
            "risk_level": "medium",
        }],
    }
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(mapping), encoding="utf-8")

    plan = generate_fusion_plan(map_path, "engines")

    assert plan["target_match_path"] == str((target / "engines").resolve())


def test_verified_asset_manifest_generates_add_asset(tmp_path: Path) -> None:
    source = tmp_path / "source" / "engines"
    target = tmp_path / "target" / "engines"
    model = source / "models" / "voice.tflite"
    model.parent.mkdir(parents=True)
    payload = b"\x00TFLITE\x00" * 32
    model.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (source / ".aetherfusion-assets.json").write_text(json.dumps({
        "assets": [{
            "path": "models/voice.tflite",
            "size_bytes": len(payload),
            "sha256": digest,
            "role": "acoustic_model",
        }]
    }), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, source, target)

    manifest = generate_dry_run_patch(plan_path)

    asset = next(op for op in manifest["operations"] if op["relative_path"] == "models/voice.tflite")
    assert asset["type"] == "add_asset"
    assert asset["sha256"] == digest
    assert asset["asset_verified"] is True
    assert manifest["summary"]["verified_assets_to_add"] == 1


def test_declared_asset_with_wrong_hash_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "source" / "engines"
    target = tmp_path / "target" / "engines"
    source.mkdir(parents=True)
    model = source / "voice.onnx"
    model.write_bytes(b"model-bytes")
    (source / ".aetherfusion-assets.json").write_text(json.dumps({
        "assets": [{
            "path": "voice.onnx",
            "size_bytes": len(b"model-bytes"),
            "sha256": "0" * 64,
            "role": "runtime_asset",
        }]
    }), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, source, target)

    manifest = generate_dry_run_patch(plan_path)

    op = next(op for op in manifest["operations"] if op["relative_path"] == "voice.onnx")
    assert op["type"] == "skip_unsafe"
    assert "sha-256" in op["reason"].lower()


def test_symlink_source_is_never_fused(tmp_path: Path) -> None:
    source = tmp_path / "source" / "engines"
    target = tmp_path / "target" / "engines"
    source.mkdir(parents=True)
    outside = tmp_path / "secret.bin"
    outside.write_bytes(b"secret")
    link = source / "linked.bin"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path, source, target)

    manifest = generate_dry_run_patch(plan_path)

    op = next(op for op in manifest["operations"] if op["relative_path"] == "linked.bin")
    assert op["type"] == "skip_unsafe"
    assert "symbolic link" in op["reason"].lower()


def test_verified_asset_is_applied_when_hash_matches(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    asset = source / "voice.tflite"
    payload = b"\x00voice-model\x00" * 16
    asset.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    patch = tmp_path / "patch.json"
    _write_patch(patch, source, target, [{
        "type": "add_asset",
        "relative_path": "models/voice.tflite",
        "source_absolute": str(asset),
        "file_size_bytes": len(payload),
        "sha256": digest,
        "asset_verified": True,
        "asset_role": "acoustic_model",
    }])

    result = apply_patch(patch)

    assert result["summary"]["files_applied"] == 1
    assert (target / "models" / "voice.tflite").read_bytes() == payload


def test_verified_asset_with_wrong_hash_is_blocked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    asset = source / "voice.tflite"
    asset.write_bytes(b"model")
    patch = tmp_path / "patch.json"
    _write_patch(patch, source, target, [{
        "type": "add_asset",
        "relative_path": "voice.tflite",
        "source_absolute": str(asset),
        "file_size_bytes": 5,
        "sha256": "0" * 64,
        "asset_verified": True,
    }])

    result = apply_patch(patch)

    assert result["summary"]["files_applied"] == 0
    assert result["summary"]["files_blocked"] == 1
    assert not (target / "voice.tflite").exists()


def test_absolute_relative_path_is_blocked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    file = source / "safe.txt"
    file.write_text("safe", encoding="utf-8")
    escape = tmp_path / "escaped.txt"
    patch = tmp_path / "patch.json"
    _write_patch(patch, source, target, [{
        "type": "add_file",
        "relative_path": str(escape),
        "source_absolute": str(file),
        "file_size_bytes": 4,
    }])

    result = apply_patch(patch)

    assert result["summary"]["files_blocked"] == 1
    assert not escape.exists()


def test_source_outside_declared_module_is_blocked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    patch = tmp_path / "patch.json"
    _write_patch(patch, source, target, [{
        "type": "add_file",
        "relative_path": "outside.txt",
        "source_absolute": str(outside),
        "file_size_bytes": 6,
    }])

    result = apply_patch(patch)

    assert result["summary"]["files_blocked"] == 1
    assert not (target / "outside.txt").exists()
