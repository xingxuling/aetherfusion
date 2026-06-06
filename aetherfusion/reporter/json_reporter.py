"""JSON reporter — generates machine-readable AetherFusion project maps."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aetherfusion import __version__
from aetherfusion.scanner.project_analyzer import ProjectInfo
from aetherfusion.comparer.tech_stack import compare_tech_stack
from aetherfusion.comparer.dependencies import compare_dependencies
from aetherfusion.comparer.structure import compare_structure
from aetherfusion.comparer.fusion import analyze_fusion, generate_fusion_plan_candidates
from aetherfusion.git_checker import check_git_status
from aetherfusion.utils import normalize_path_for_report


def generate_json_map(
    source_info: ProjectInfo,
    target_info: ProjectInfo,
) -> dict[str, Any]:
    """Generate a complete JSON fusion map suitable for downstream agent consumption.

    Args:
        source_info: Scanned data for the source project.
        target_info: Scanned data for the target project.

    Returns:
        Full JSON-serializable dictionary.
    """
    ts_cmp = compare_tech_stack(source_info, target_info)
    dep_cmp = compare_dependencies(source_info, target_info)
    struct_cmp = compare_structure(source_info, target_info)
    fusion = analyze_fusion(source_info, target_info)
    candidates = generate_fusion_plan_candidates(source_info, target_info, fusion, dep_cmp)

    source_git = check_git_status(Path(source_info.root))
    target_git = check_git_status(Path(target_info.root))

    return {
        "report_metadata": {
            "tool": "AetherFusion",
            "version": __version__,
            "generated_at": datetime.now().isoformat(),
            "schema_version": "0.1.5",
        },
        "projects": {
            "source": _project_summary(source_info, source_git),
            "target": _project_summary(target_info, target_git),
        },
        "tech_stack": {
            "source_stack": ts_cmp["source_stack"],
            "target_stack": ts_cmp["target_stack"],
            "shared": ts_cmp["common"],
            "unique_to_source": ts_cmp["unique_to_source"],
            "unique_to_target": ts_cmp["unique_to_target"],
        },
        "dependencies": {
            "common": _serialize_common_deps(dep_cmp.get("common", {})),
            "unique_to_source": _serialize_unique_deps(dep_cmp.get("unique_to_source", {})),
            "unique_to_target": _serialize_unique_deps(dep_cmp.get("unique_to_target", {})),
            "version_conflicts": dep_cmp.get("version_conflicts", []),
        },
        "structure": {
            "common_directories": struct_cmp.get("common_dirs", []),
            "unique_to_source": struct_cmp.get("unique_to_source", []),
            "unique_to_target": struct_cmp.get("unique_to_target", []),
        },
        "fusible_modules": fusion.get("fusible_modules", []),
        "conflicts": fusion.get("conflicts", {}),
        "fusion_plan_candidates": candidates,
        "recommendations": fusion.get("recommendations", []),
        "git_status": {
            "source": source_git,
            "target": target_git,
        },
    }


def _project_summary(info: ProjectInfo, git_status: dict) -> dict[str, Any]:
    """Build a serializable project summary dict."""
    return {
        "name": info.name,
        "path": normalize_path_for_report(info.root),
        "file_count": info.file_count,
        "directory_count": info.dir_count,
        "config_files": {
            fname: cat
            for fname, cat in sorted(info.config_files_detected.items())
        },
        "entry_files": sorted(info.entry_files),
        "core_directories": sorted(info.core_directories),
        "dependencies": _serialize_unique_deps(info.dependencies),
        "scripts": dict(sorted(info.scripts.items())),
        "tech_stack": sorted(info.tech_stack),
        "git_status": git_status["status"],
        "git_branch": git_status["branch"],
        "git_changed_files": git_status["changed_files"],
    }


def _serialize_common_deps(common: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert common deps dict to a sorted list with conflict flag."""
    return sorted(
        [
            {
                "name": name,
                "source_version": info["source_version"],
                "target_version": info["target_version"],
                "type": info.get("type", "unknown"),
                "conflict": info["conflict"],
            }
            for name, info in common.items()
        ],
        key=lambda x: x["name"],
    )


def _serialize_unique_deps(unique: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert unique deps dict to a sorted list."""
    return sorted(
        [
            {
                "name": name,
                "version": info.get("version", ""),
                "type": info.get("type", "unknown"),
                "source": info.get("source", ""),
            }
            for name, info in unique.items()
        ],
        key=lambda x: x["name"],
    )


def write_json_map(output_path: Path, data: dict[str, Any]) -> None:
    """Write the JSON map to a file with indentation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )