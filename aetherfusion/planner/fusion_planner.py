"""Fusion planner — generates module-level fusion plans from JSON project maps."""

import json
from pathlib import Path
from typing import Any

from aetherfusion import __version__


def generate_fusion_plan(
    map_path: Path,
    module_name: str,
) -> dict[str, Any]:
    """Generate a detailed module-level fusion plan from a JSON project map."""
    if not map_path.is_file():
        raise FileNotFoundError(f"JSON map not found: {map_path}")

    with open(map_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates: list[dict[str, Any]] = data.get("fusion_plan_candidates", [])
    candidate = next((c for c in candidates if c.get("module_name") == module_name), None)
    if candidate is None:
        available = sorted([c.get("module_name", "?") for c in candidates])
        raise ValueError(
            f"Module '{module_name}' not found in fusion_plan_candidates. "
            f"Available modules: {', '.join(available) if available else '(none)'}"
        )

    source_info = data.get("projects", {}).get("source", {})
    target_info = data.get("projects", {}).get("target", {})
    conflicts = data.get("conflicts", {})
    deps = data.get("dependencies", {})

    source_module_path = _pick_first(candidate.get("source_paths", []))
    target_match_path = _pick_first(candidate.get("target_paths", []))

    # Source-only transfer modules need a deterministic destination so patch/apply
    # can form a complete transaction rather than emitting an empty target path.
    source_only_transfer = (
        not target_match_path
        and bool(source_module_path)
        and (
            candidate.get("fusion_feasibility") == "transfer"
            or candidate.get("recommended_action") == "copy_to_target"
            or not candidate.get("target_paths", [])
        )
    )
    if source_only_transfer:
        target_root = target_info.get("path", "")
        if target_root:
            target_match_path = str((Path(target_root) / module_name).resolve())

    return {
        "plan_version": __version__,
        "module_name": module_name,
        "module_type": candidate.get("module_type", "unknown"),
        "source_module_path": source_module_path,
        "target_match_path": target_match_path,
        "source_project": {
            "name": source_info.get("name", "unknown"),
            "path": source_info.get("path", ""),
        },
        "target_project": {
            "name": target_info.get("name", "unknown"),
            "path": target_info.get("path", ""),
        },
        "risk_level": candidate.get("risk_level", "unknown"),
        "strategy": candidate.get("recommended_action", "manual_review"),
        "score_summary": {
            "value_score": candidate.get("value_score"),
            "portability_score": candidate.get("portability_score"),
            "conflict_score": candidate.get("conflict_score"),
            "priority_score": candidate.get("priority_score"),
        },
        "ordered_steps": _build_ordered_steps(module_name, candidate, conflicts),
        "required_human_decisions": _build_human_decisions(module_name, candidate, conflicts, deps),
        "blocked_actions": [
            "v0.2 does not modify any source or target project files",
            "do not automatically overwrite target project files",
            "do not automatically modify dependency configuration (package.json / requirements.txt)",
            "do not execute build or test commands (npm build / pytest / etc.)",
            "do not make any network requests",
        ],
        "next_recommended_command": (
            f"python -m aetherfusion plan --map {map_path} --module {module_name}"
        ),
    }


def _pick_first(paths: list[str]) -> str | None:
    return paths[0] if paths else None


def _build_ordered_steps(
    module_name: str,
    candidate: dict[str, Any],
    conflicts: dict[str, Any],
) -> list[dict[str, Any]]:
    source_paths: list[str] = candidate.get("source_paths", [])
    target_paths: list[str] = candidate.get("target_paths", [])
    name_conflicts = {c.get("relative_path", "") for c in conflicts.get("name_conflicts", [])}
    has_same_named = module_name in name_conflicts or bool(source_paths and target_paths)

    return [
        {
            "step": 1,
            "action": "inspect_same_named_files",
            "description": f"Inspect files in module '{module_name}' for naming collisions between source and target projects.",
            "details": {
                "source_paths": source_paths,
                "target_paths": target_paths,
                "has_same_named_conflicts": has_same_named,
                "recommended_tool": "Use aetherfusion scan to identify file-level conflicts, then manually diff conflicting files.",
            },
            "estimated_complexity": "medium" if has_same_named else "low",
        },
        {
            "step": 2,
            "action": "copy_non_conflicting_files",
            "description": f"Identify files in '{module_name}' that do not conflict with target files and prepare a copy plan.",
            "details": {
                "condition": "Only files not present in target should be copied in this step.",
                "status": "BLOCKED — v0.2 is read-only; actual file copy is deferred to v0.3+.",
                "note": "Human review is required before copying.",
            },
            "estimated_complexity": "low",
        },
        {
            "step": 3,
            "action": "review_import_dependencies",
            "description": f"Review import/require statements within '{module_name}' so they resolve in the target project.",
            "details": {
                "target_dependencies": "Check whether imported modules are available in the target project.",
                "relative_imports": "Verify relative paths remain valid after fusion.",
                "status": "Requires manual review — automatic import rewriting is out of scope for v0.2.",
            },
            "estimated_complexity": "medium",
        },
        {
            "step": 4,
            "action": "check_config_requirements",
            "description": f"Check whether '{module_name}' requires target config changes.",
            "details": {
                "tsconfig_paths": "Check path aliases.",
                "env_vars": "Document required environment variables.",
                "build_config": "Review module-specific build settings.",
            },
            "estimated_complexity": "medium",
        },
        {
            "step": 5,
            "action": "prepare_dry_run_patch",
            "description": f"Generate a dry-run preview for fusing '{module_name}' into the target project.",
            "details": {
                "status": "BLOCKED — v0.2 is planning-only; patch generation is deferred to v0.3+.",
                "planned_actions": "Produce create/copy/modify operations with before/after paths for review.",
            },
            "estimated_complexity": "low (planning only)",
        },
    ]


def _build_human_decisions(
    module_name: str,
    candidate: dict[str, Any],
    conflicts: dict[str, Any],
    deps: dict[str, Any],
) -> list[dict[str, Any]]:
    source_paths: list[str] = candidate.get("source_paths", [])
    target_paths: list[str] = candidate.get("target_paths", [])
    has_same_path = bool(source_paths and target_paths)
    ver_conflicts = deps.get("version_conflicts", [])

    return [
        {
            "decision_id": "same_named_files",
            "question": f"How should same-named files in module '{module_name}' be handled?",
            "context": (
                f"Source and target both contain a module named '{module_name}'. Files with identical names must be resolved."
                if has_same_path
                else f"No same-named file conflicts are currently detected for '{module_name}', but this should be confirmed."
            ),
            "options": [
                {"value": "overwrite", "label": "Overwrite", "description": "Replace target files with source versions."},
                {"value": "namespace", "label": "Namespace", "description": "Rename source files to avoid collisions."},
                {"value": "skip", "label": "Skip", "description": "Skip conflicting files."},
                {"value": "manual_merge", "label": "Manual Merge", "description": "Manually merge each conflicting file."},
            ],
            "is_blocking": True,
        },
        {
            "decision_id": "dependency_updates",
            "question": "Should dependency conflicts allow updating package.json / requirements.txt?",
            "context": (
                f"{len(ver_conflicts)} dependency version conflict(s) detected."
                if ver_conflicts
                else "No dependency version conflicts detected; confirm whether new dependencies are needed."
            ),
            "options": [
                {"value": "allow", "label": "Allow Updates", "description": "Permit dependency file changes."},
                {"value": "deny", "label": "Deny Updates", "description": "Resolve conflicts manually."},
                {"value": "review", "label": "Review Each", "description": "Review each conflict individually."},
            ],
            "is_blocking": True,
        },
        {
            "decision_id": "route_integration",
            "question": "Should routing conflicts be resolved by integrating into target routes?",
            "context": f"If '{module_name}' defines routes or entry points, decide whether to merge or isolate them.",
            "options": [
                {"value": "integrate", "label": "Integrate Routes", "description": "Merge into target routing."},
                {"value": "isolate", "label": "Isolate Routes", "description": "Keep routes separate."},
                {"value": "defer", "label": "Defer Decision", "description": "Revisit after initial fusion."},
            ],
            "is_blocking": False,
        },
        {
            "decision_id": "preserve_structure",
            "question": "Should the original source directory structure be preserved?",
            "context": (
                f"Source: {', '.join(source_paths) if source_paths else '(none)'}. "
                f"Target: {', '.join(target_paths) if target_paths else '(none)'}."
            ),
            "options": [
                {"value": "preserve", "label": "Preserve Structure", "description": "Keep the source layout."},
                {"value": "flatten", "label": "Flatten Structure", "description": "Flatten into target structure."},
                {"value": "adapt", "label": "Adapt to Target", "description": "Reorganize to target conventions."},
            ],
            "is_blocking": False,
        },
    ]
