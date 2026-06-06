"""Fusion analysis — identifies fusible modules and conflict risks."""

import os
from pathlib import Path
from typing import Any

from aetherfusion.scanner.project_analyzer import ProjectInfo
from aetherfusion.utils import normalize_path_for_report


def analyze_fusion(source: ProjectInfo, target: ProjectInfo) -> dict[str, Any]:
    """Analyze fusion potential and conflict risks between two projects.

    Returns::

        {
            "fusible_modules": [...],
            "conflicts": [...],
            "recommendations": [...],
        }
    """
    fusible = _find_fusible_modules(source, target)
    conflicts = _find_conflicts(source, target)
    recommendations = _generate_recommendations(fusible, conflicts)

    return {
        "fusible_modules": fusible,
        "conflicts": conflicts,
        "recommendations": recommendations,
    }


def _find_fusible_modules(source: ProjectInfo, target: ProjectInfo) -> list[dict[str, Any]]:
    """Identify modules present in both projects that could be candidates for fusion."""
    s_modules = source.fusible_modules
    t_modules = target.fusible_modules
    common_names = set(s_modules) & set(t_modules)

    result: list[dict[str, Any]] = []
    for name in sorted(common_names):
        s_paths = s_modules[name]
        t_paths = t_modules[name]
        entry = {
            "module_name": name,
            "source_paths": [normalize_path_for_report(p) for p in s_paths],
            "target_paths": [normalize_path_for_report(p) for p in t_paths],
            "fusion_feasibility": _assess_fusion_feasibility(name, s_paths, t_paths),
        }
        result.append(entry)

    # Also report modules unique to one project that *could* be merged
    unique_s = set(s_modules) - set(t_modules)
    unique_t = set(t_modules) - set(s_modules)
    for name in sorted(unique_s):
        result.append({
            "module_name": name,
            "source_paths": [normalize_path_for_report(p) for p in s_modules[name]],
            "target_paths": [],
            "fusion_feasibility": "transfer",  # Can be moved from source to target
        })
    for name in sorted(unique_t):
        # Filter out if already added from unique_s
        if not any(m["module_name"] == name for m in result):
            result.append({
                "module_name": name,
                "source_paths": [],
                "target_paths": [normalize_path_for_report(p) for p in t_modules[name]],
                "fusion_feasibility": "transfer",
            })

    return result


def _assess_fusion_feasibility(name: str, s_paths: list[str], t_paths: list[str]) -> str:
    """Assess how feasible it is to fuse two modules with the same name."""
    # Check if both are under src/ — high feasibility
    s_under_src = any("src" in Path(p).parts for p in s_paths)
    t_under_src = any("src" in Path(p).parts for p in t_paths)
    if s_under_src and t_under_src:
        return "high"
    # If one is top-level and other is nested, medium
    s_top = any(Path(p).parent.name not in ("src",) for p in s_paths)
    t_top = any(Path(p).parent.name not in ("src",) for p in t_paths)
    if s_top != t_top:
        return "medium"
    return "low"


def _find_conflicts(source: ProjectInfo, target: ProjectInfo) -> list[dict[str, Any]]:
    """Identify potential conflicts between the two projects."""

    # 1. Version conflicts (from dependency comparison)
    from aetherfusion.comparer.dependencies import compare_dependencies
    dep_cmp = compare_dependencies(source, target)
    version_conflicts = dep_cmp.get("version_conflicts", [])

    # 2. Same-name file conflicts
    name_conflicts = _find_same_name_conflicts(source, target)

    # 3. Script name conflicts
    s_scripts = set(source.scripts)
    t_scripts = set(target.scripts)
    script_conflicts = [
        {"script": name, "source_cmd": source.scripts[name], "target_cmd": target.scripts[name]}
        for name in sorted(s_scripts & t_scripts)
        if source.scripts[name] != target.scripts[name]
    ]

    # 4. Entry file conflicts
    s_entries = set(source.entry_files)
    t_entries = set(target.entry_files)
    entry_conflicts = sorted(s_entries & t_entries)

    return {
        "version_conflicts": version_conflicts,
        "name_conflicts": name_conflicts,
        "script_conflicts": script_conflicts,
        "entry_conflicts": entry_conflicts,
    }


def _find_same_name_conflicts(source: ProjectInfo, target: ProjectInfo) -> list[dict[str, str]]:
    """Find files/dirs with the same relative path in both projects."""
    conflicts: list[dict[str, str]] = []
    s_root = Path(source.root)
    t_root = Path(target.root)

    # Only check top two levels to avoid deep scanning
    for depth, s_root_ref in enumerate([s_root], start=0):
        _collect_conflicts(s_root, t_root, depth, conflicts)

    return conflicts[:50]  # Cap at 50 to avoid blowing up


def _collect_conflicts(
    s_dir: Path,
    t_dir: Path,
    depth: int,
    conflicts: list[dict[str, str]],
    max_depth: int = 2,
    ignore_dirs: set[str] | None = None,
) -> None:
    """Recursively collect same-name file/dir conflicts."""
    from aetherfusion.utils import IGNORE_DIRS
    if ignore_dirs is None:
        ignore_dirs = IGNORE_DIRS

    if depth > max_depth:
        return

    try:
        s_entries = {e for e in os.listdir(s_dir) if e not in ignore_dirs and not e.startswith(".")}
        t_entries = {e for e in os.listdir(t_dir) if e not in ignore_dirs and not e.startswith(".")}
    except (PermissionError, OSError):
        return

    common = s_entries & t_entries
    for name in sorted(common):
        s_path = s_dir / name
        t_path = t_dir / name
        s_is_dir = s_path.is_dir()
        t_is_dir = t_path.is_dir()

        if s_is_dir and t_is_dir:
            conflicts.append({
                "type": "directory",
                "relative_path": name,
                "source_path": normalize_path_for_report(s_path),
                "target_path": normalize_path_for_report(t_path),
            })
            _collect_conflicts(s_path, t_path, depth + 1, conflicts, max_depth, ignore_dirs)
        elif not s_is_dir and not t_is_dir:
            conflicts.append({
                "type": "file",
                "relative_path": name,
                "source_path": normalize_path_for_report(s_path),
                "target_path": normalize_path_for_report(t_path),
            })


def _generate_recommendations(
    fusible: list[dict[str, Any]],
    conflicts: dict[str, list[Any]],
) -> list[str]:
    """Generate human-readable recommendations."""
    recs: list[str] = []

    high_fusible = [m for m in fusible if m.get("fusion_feasibility") == "high"]
    medium_fusible = [m for m in fusible if m.get("fusion_feasibility") == "medium"]
    name_conflicts = conflicts.get("name_conflicts", [])
    ver_conflicts = conflicts.get("version_conflicts", [])
    entry_conflicts = conflicts.get("entry_conflicts", [])

    if high_fusible:
        names = ", ".join(f"`{m['module_name']}`" for m in high_fusible)
        recs.append(
            f"High feasibility modules found: {names}. "
            "Both projects have these under similar directory structures. "
            "Consider creating a shared package or merging into one codebase."
        )

    if medium_fusible:
        names = ", ".join(f"`{m['module_name']}`" for m in medium_fusible)
        recs.append(
            f"Medium feasibility modules: {names}. "
            "Directory structure differs — review naming conventions and API surfaces before merging."
        )

    if name_conflicts:
        count = len(name_conflicts)
        recs.append(
            f"{count} file/directory name conflict(s) detected. "
            "Resolve naming collisions before fusion: rename files, introduce namespaces, "
            "or merge content into a unified file."
        )

    if ver_conflicts:
        count = len(ver_conflicts)
        recs.append(
            f"{count} dependency version conflict(s) detected. "
            "Align to a single version before merging, typically the higher one "
            "after verifying compatibility."
        )

    if entry_conflicts:
        recs.append(
            f"Entry file conflicts: {', '.join(entry_conflicts)}. "
            "Multiple entry points exist — consider a monorepo tool (Turborepo, Nx) "
            "or a unified entry with routing."
        )

    if not recs:
        recs.append(
            "No major conflicts detected. The projects appear to be good candidates for fusion. "
            "Start by merging shared utility code, then progressively integrate feature modules."
        )

    return recs


# ---------------------------------------------------------------------------
# Fusion Plan Candidates — scoring engine for downstream agent consumption
# ---------------------------------------------------------------------------

# Heuristic multipliers per module type
_MODULE_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "components": {"value": 0.9, "portability": 0.7, "conflict": 0.3},
    "utils":       {"value": 0.7, "portability": 0.95, "conflict": 0.1},
    "lib":         {"value": 0.7, "portability": 0.95, "conflict": 0.1},
    "services":    {"value": 0.85, "portability": 0.5, "conflict": 0.5},
    "hooks":       {"value": 0.8, "portability": 0.7, "conflict": 0.2},
    "engines":     {"value": 0.9, "portability": 0.4, "conflict": 0.6},
    "skills":      {"value": 0.85, "portability": 0.6, "conflict": 0.4},
    "models":      {"value": 0.8, "portability": 0.6, "conflict": 0.4},
    "factories":   {"value": 0.75, "portability": 0.6, "conflict": 0.3},
    "training":    {"value": 0.9, "portability": 0.3, "conflict": 0.7},
}


def generate_fusion_plan_candidates(
    source: ProjectInfo,
    target: ProjectInfo,
    fusion: dict[str, Any],
    dep_cmp: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate scored fusion-plan candidates from the raw analysis.

    Each candidate includes a composite score derived from:
    - value_score: how valuable the module is to bring over
    - portability_score: how easy it is to move
    - conflict_score: how many issues it causes (lower is better)
    - priority_score: derived composite
    - risk_level: low / medium / high
    - reason: human-readable justification
    - recommended_action: suggested next step
    """
    fusible = fusion.get("fusible_modules", [])
    conflicts = fusion.get("conflicts", {})
    name_conflicts = {c["relative_path"] for c in conflicts.get("name_conflicts", [])}

    candidates: list[dict[str, Any]] = []

    for mod in fusible:
        module_name = mod["module_name"]
        feasibility = mod.get("fusion_feasibility", "low")
        s_paths = mod.get("source_paths", [])
        t_paths = mod.get("target_paths", [])

        weights = _MODULE_TYPE_WEIGHTS.get(module_name, {"value": 0.5, "portability": 0.5, "conflict": 0.3})

        # Base scores from module type heuristics
        value_base = weights["value"] * 100
        portability_base = weights["portability"] * 100
        conflict_base = weights["conflict"] * 100

        # Adjust for feasibility
        if feasibility == "high":
            portability_base += 15
            conflict_base -= 10
        elif feasibility == "medium":
            portability_base += 5
        elif feasibility == "transfer":
            portability_base += 20  # unique module — just copy it
            if not s_paths:
                # target-only unique: already there, nothing to transfer
                portability_base += 25
                value_base += 10
        # Low feasibility stays at base

        # Adjust for name conflicts
        if module_name in name_conflicts:
            conflict_base += 20
            portability_base -= 10

        # Adjust for dependency conflicts
        if dep_cmp:
            ver_conflicts = dep_cmp.get("version_conflicts", [])
            if ver_conflicts:
                conflict_base += min(len(ver_conflicts) * 5, 30)

        # Clamp scores
        value_score = max(0, min(100, value_base))
        portability_score = max(0, min(100, portability_base))
        conflict_score = max(0, min(100, conflict_base))

        # Priority = value * portability / (conflict + 1)
        priority_score = round((value_score * portability_score) / max(conflict_score, 1), 1)

        # Risk level
        if conflict_score > 60:
            risk_level = "high"
        elif conflict_score > 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Reason string
        reasons = []
        if feasibility == "high":
            reasons.append("both projects share this module under similar structure")
        elif feasibility == "transfer":
            if s_paths and not t_paths:
                reasons.append(f"module only in source; can be copied to target")
            elif t_paths and not s_paths:
                reasons.append(f"module only in target; no action needed")
            else:
                reasons.append("module transfer candidate")
        else:
            reasons.append(f"feasibility: {feasibility}")

        if module_name in name_conflicts:
            reasons.append("same-named files exist in both projects — manual resolution needed")
        if conflict_score > 50:
            reasons.append("high risk of integration conflicts")

        # Recommended action
        if risk_level == "high":
            action = "review_and_replan"
        elif feasibility == "high" and risk_level == "low":
            action = "proceed_to_fuse"
        elif feasibility == "transfer":
            action = "copy_to_target"
        else:
            action = "manual_review"

        candidate = {
            "module_name": module_name,
            "module_type": _infer_module_type(module_name, s_paths, t_paths),
            "source_paths": s_paths,
            "target_paths": t_paths,
            "value_score": round(value_score, 1),
            "portability_score": round(portability_score, 1),
            "conflict_score": round(conflict_score, 1),
            "priority_score": priority_score,
            "risk_level": risk_level,
            "reason": "; ".join(reasons),
            "recommended_action": action,
            "score_breakdown": {
                "value_reason": _build_value_reason(module_name, feasibility, s_paths, t_paths, weights),
                "portability_reason": _build_portability_reason(module_name, feasibility, s_paths, t_paths, portability_base),
                "conflict_reason": _build_conflict_reason(module_name, name_conflicts, dep_cmp, conflict_base),
                "priority_formula": (
                    f"value_score({round(value_score,1)}) "
                    f"* portability_score({round(portability_score,1)}) "
                    f"/ max(conflict_score({round(conflict_score,1)}), 1) "
                    f"= {priority_score}"
                ),
            },
        }
        candidates.append(candidate)

    # Sort candidates by priority_score descending
    candidates.sort(key=lambda c: c["priority_score"], reverse=True)
    return candidates


def _build_value_reason(
    module_name: str,
    feasibility: str,
    s_paths: list[str],
    t_paths: list[str],
    weights: dict[str, float],
) -> str:
    """Build a human-readable reason for the value_score."""
    parts = []
    parts.append(f"module '{module_name}' has base value weight {weights['value']}")
    if feasibility == "high":
        parts.append("shared under similar structure increases reuse value")
    elif feasibility == "transfer":
        if s_paths and not t_paths:
            parts.append("unique to source — must be transferred to unlock value")
        elif t_paths and not s_paths:
            parts.append("already in target — immediate value, no transfer needed")
        else:
            parts.append("transfer candidate with moderate value")
    else:
        parts.append(f"feasibility ({feasibility}) limits reuse value")
    return "; ".join(parts)


def _build_portability_reason(
    module_name: str,
    feasibility: str,
    s_paths: list[str],
    t_paths: list[str],
    portability_base: float,
) -> str:
    """Build a human-readable reason for the portability_score."""
    import math
    parts = []
    if feasibility == "high":
        parts.append("high feasibility — both projects share similar directory structure")
    elif feasibility == "transfer":
        if s_paths and not t_paths:
            parts.append("module only in source — direct copy candidate")
        elif t_paths and not s_paths:
            parts.append("module only in target — already portable, no action needed")
        else:
            parts.append("transfer candidate")
    else:
        parts.append(f"feasibility ({feasibility}) — portability may be limited")

    if portability_base >= 90:
        parts.append("minimal structural barriers to migration")
    elif portability_base >= 70:
        parts.append("moderate structural differences — review file paths")
    else:
        parts.append("significant structural differences — manual path adaptation likely needed")
    return "; ".join(parts)


def _build_conflict_reason(
    module_name: str,
    name_conflicts: set[str],
    dep_cmp: dict[str, Any] | None,
    conflict_base: float,
) -> str:
    """Build a human-readable reason for the conflict_score."""
    parts = []
    if module_name in name_conflicts:
        parts.append(f"module '{module_name}' has same-named files in both projects")
    if dep_cmp:
        ver_conflicts = dep_cmp.get("version_conflicts", [])
        if ver_conflicts:
            dep_names = [c["name"] for c in ver_conflicts]
            parts.append(f"dependency version conflicts detected: {', '.join(dep_names[:5])}")
    if conflict_base >= 60:
        parts.append("high conflict level — resolve before proceeding")
    elif conflict_base >= 30:
        parts.append("moderate conflict — may need manual resolution")
    else:
        parts.append("low conflict — minimal barriers to integration")
    if not parts:
        parts.append("no specific conflicts identified")
    return "; ".join(parts)


def _infer_module_type(name: str, s_paths: list[str], t_paths: list[str]) -> str:
    """Infer the module type from its name and location."""
    # Direct match on known types
    known = {
        "components", "utils", "lib", "services", "hooks",
        "engines", "skills", "models", "training", "factories",
    }
    if name in known:
        return name

    # Check paths for hints
    all_paths = s_paths + t_paths
    for p in all_paths:
        parts = Path(p).parts
        for part in parts:
            if part in known:
                return part

    return "unknown"