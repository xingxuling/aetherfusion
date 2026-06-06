"""Markdown report generator for AetherFusion."""

from datetime import datetime
from pathlib import Path
from typing import Any

from aetherfusion.scanner.project_analyzer import ProjectInfo
from aetherfusion.comparer.tech_stack import compare_tech_stack
from aetherfusion.comparer.dependencies import compare_dependencies
from aetherfusion.comparer.structure import compare_structure
from aetherfusion.comparer.fusion import analyze_fusion
from aetherfusion import __version__
from aetherfusion.utils import normalize_path_for_report


def generate_report(source_info: ProjectInfo, target_info: ProjectInfo) -> str:
    """Generate a complete Markdown fusion report.

    Args:
        source_info: Scanned data for the source project (project-b).
        target_info: Scanned data for the target project (project-a).

    Returns:
        Full Markdown report string.
    """
    ts_cmp = compare_tech_stack(source_info, target_info)
    dep_cmp = compare_dependencies(source_info, target_info)
    struct_cmp = compare_structure(source_info, target_info)
    fusion = analyze_fusion(source_info, target_info)

    lines: list[str] = []
    _append_header(lines, source_info, target_info)
    _append_scan_summary(lines, source_info, target_info)
    _append_tech_stack(lines, ts_cmp)
    _append_dependencies(lines, dep_cmp)
    _append_directory_trees(lines, source_info, target_info)
    _append_structure_comparison(lines, struct_cmp)
    _append_fusible_modules(lines, fusion)
    _append_conflicts(lines, fusion)
    _append_recommendations(lines, fusion)
    _append_footer(lines)

    return "\n".join(lines) + "\n"


def _append_header(
    lines: list[str],
    source: ProjectInfo,
    target: ProjectInfo,
) -> None:
    lines.append(f"# AetherFusion Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Project Overview")
    lines.append("")
    lines.append("| Role | Name | Path |")
    lines.append("|------|------|------|")
    lines.append(f"| Source | `{source.name}` | `{normalize_path_for_report(source.root)}` |")
    lines.append(f"| Target | `{target.name}` | `{normalize_path_for_report(target.root)}` |")
    lines.append("")
    lines.append("*Source = project-b (the project being merged from), Target = project-a (the base project being merged into).*")
    lines.append("")


def _append_scan_summary(
    lines: list[str],
    source: ProjectInfo,
    target: ProjectInfo,
) -> None:
    lines.append("## Scan Summary")
    lines.append("")
    lines.append("| Metric | Source | Target |")
    lines.append("|--------|--------|--------|")
    lines.append(f"| Files | {source.file_count} | {target.file_count} |")
    lines.append(f"| Directories | {source.dir_count} | {target.dir_count} |")
    lines.append(f"| Config files detected | {len(source.config_files_detected)} | {len(target.config_files_detected)} |")
    lines.append(f"| Entry files | {len(source.entry_files)} | {len(target.entry_files)} |")
    lines.append(f"| Dependencies | {len(source.dependencies)} | {len(target.dependencies)} |")
    lines.append(f"| Scripts | {len(source.scripts)} | {len(target.scripts)} |")
    lines.append("")

    # Config files detail
    lines.append("### Config Files Detected")
    lines.append("")
    lines.append("**Source:**")
    if source.config_files_detected:
        for fname, cat in sorted(source.config_files_detected.items()):
            lines.append(f"- `{fname}` ({cat})")
    else:
        lines.append("- *(none)*")
    lines.append("")
    lines.append("**Target:**")
    if target.config_files_detected:
        for fname, cat in sorted(target.config_files_detected.items()):
            lines.append(f"- `{fname}` ({cat})")
    else:
        lines.append("- *(none)*")
    lines.append("")

    # Entry files detail
    lines.append("### Entry Files")
    lines.append("")
    lines.append("**Source:**")
    if source.entry_files:
        for entry in sorted(source.entry_files):
            lines.append(f"- `{entry}`")
    else:
        lines.append("- *(none detected)*")
    lines.append("")
    lines.append("**Target:**")
    if target.entry_files:
        for entry in sorted(target.entry_files):
            lines.append(f"- `{entry}`")
    else:
        lines.append("- *(none detected)*")
    lines.append("")

    # Scripts detail
    if source.scripts or target.scripts:
        lines.append("### Scripts / Commands")
        lines.append("")
        if source.scripts:
            lines.append("**Source:**")
            for name, cmd in sorted(source.scripts.items()):
                lines.append(f"- `{name}` → `{cmd}`")
            lines.append("")
        if target.scripts:
            lines.append("**Target:**")
            for name, cmd in sorted(target.scripts.items()):
                lines.append(f"- `{name}` → `{cmd}`")
            lines.append("")


def _append_tech_stack(lines: list[str], ts_cmp: dict[str, Any]) -> None:
    lines.append("## Tech Stack Comparison")
    lines.append("")

    if not ts_cmp["source_stack"] and not ts_cmp["target_stack"]:
        lines.append("*No technology stack could be inferred from either project.*")
        lines.append("")
        return

    lines.append("| Technology | Source | Target |")
    lines.append("|-------------|:------:|:------:|")

    all_techs = sorted(set(ts_cmp["source_stack"]) | set(ts_cmp["target_stack"]))
    for tech in all_techs:
        s = "Yes" if tech in ts_cmp["source_stack"] else "—"
        t = "Yes" if tech in ts_cmp["target_stack"] else "—"
        lines.append(f"| {tech} | {s} | {t} |")
    lines.append("")

    common = ts_cmp.get("common", [])
    unique_s = ts_cmp.get("unique_to_source", [])
    unique_t = ts_cmp.get("unique_to_target", [])

    if common:
        lines.append(f"**Shared:** {', '.join(common)}")
        lines.append("")
    if unique_s:
        lines.append(f"**Only in Source:** {', '.join(unique_s)}")
        lines.append("")
    if unique_t:
        lines.append(f"**Only in Target:** {', '.join(unique_t)}")
        lines.append("")


def _append_dependencies(lines: list[str], dep_cmp: dict[str, Any]) -> None:
    lines.append("## Dependency Analysis")
    lines.append("")

    # Common dependencies
    common = dep_cmp.get("common", {})
    unique_s = dep_cmp.get("unique_to_source", {})
    unique_t = dep_cmp.get("unique_to_target", {})
    conflicts = dep_cmp.get("version_conflicts", [])

    if not common and not unique_s and not unique_t:
        lines.append("*No dependencies detected in either project.*")
        lines.append("")
        return

    lines.append(f"| Category | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Common dependencies | {len(common)} |")
    lines.append(f"| Unique to Source | {len(unique_s)} |")
    lines.append(f"| Unique to Target | {len(unique_t)} |")
    lines.append(f"| Version conflicts | {len(conflicts)} |")
    lines.append("")

    if common:
        lines.append("### Common Dependencies")
        lines.append("")
        lines.append("| Package | Source Version | Target Version | Conflict? |")
        lines.append("|---------|---------------|---------------|-----------|")
        for name, info in sorted(common.items()):
            flag = "**YES**" if info["conflict"] else "No"
            lines.append(
                f"| `{name}` | `{info['source_version']}` | `{info['target_version']}` | {flag} |"
            )
        lines.append("")

    if unique_s:
        lines.append("### Dependencies Unique to Source")
        lines.append("")
        lines.append("| Package | Version | Type |")
        lines.append("|---------|---------|------|")
        for name, info in sorted(unique_s.items()):
            lines.append(f"| `{name}` | `{info['version']}` | {info['type']} |")
        lines.append("")

    if unique_t:
        lines.append("### Dependencies Unique to Target")
        lines.append("")
        lines.append("| Package | Version | Type |")
        lines.append("|---------|---------|------|")
        for name, info in sorted(unique_t.items()):
            lines.append(f"| `{name}` | `{info['version']}` | {info['type']} |")
        lines.append("")


def _append_directory_trees(
    lines: list[str],
    source: ProjectInfo,
    target: ProjectInfo,
) -> None:
    lines.append("## Directory Trees")
    lines.append("")

    lines.append("### Source (`project-b`)")
    lines.append("")
    lines.append("```")
    lines.extend(source.tree_text)
    lines.append("```")
    lines.append("")

    lines.append("### Target (`project-a`)")
    lines.append("")
    lines.append("```")
    lines.extend(target.tree_text)
    lines.append("```")
    lines.append("")


def _append_structure_comparison(lines: list[str], struct_cmp: dict[str, Any]) -> None:
    lines.append("## Structure Comparison")
    lines.append("")

    lines.append("| Category | Directories |")
    lines.append("|----------|-------------|")

    common_dirs = struct_cmp.get("common_dirs", [])
    unique_s = struct_cmp.get("unique_to_source", [])
    unique_t = struct_cmp.get("unique_to_target", [])

    if common_dirs:
        lines.append(f"| Shared | {', '.join(f'`{d}`' for d in common_dirs)} |")
    else:
        lines.append("| Shared | *(none)* |")
    if unique_s:
        lines.append(f"| Only in Source | {', '.join(f'`{d}`' for d in unique_s)} |")
    if unique_t:
        lines.append(f"| Only in Target | {', '.join(f'`{d}`' for d in unique_t)} |")
    lines.append("")


def _append_fusible_modules(lines: list[str], fusion: dict[str, Any]) -> None:
    modules = fusion.get("fusible_modules", [])
    lines.append("## Fusible Modules")
    lines.append("")

    if not modules:
        lines.append("*No fusible modules identified.*")
        lines.append("")
        return

    lines.append("| Module | Feasibility | Source Paths | Target Paths |")
    lines.append("|--------|-------------|-------------|-------------|")
    for m in modules:
        lines.append(
            f"| `{m['module_name']}` | {m['fusion_feasibility']} | "
            f"{', '.join(f'`{p}`' for p in m['source_paths']) or '—'} | "
            f"{', '.join(f'`{p}`' for p in m['target_paths']) or '—'} |"
        )
    lines.append("")


def _append_conflicts(lines: list[str], fusion: dict[str, Any]) -> None:
    conflicts = fusion.get("conflicts", {})
    lines.append("## Conflict Risks")
    lines.append("")

    ver_conflicts = conflicts.get("version_conflicts", [])
    name_conflicts = conflicts.get("name_conflicts", [])
    script_conflicts = conflicts.get("script_conflicts", [])
    entry_conflicts = conflicts.get("entry_conflicts", [])

    if not any([ver_conflicts, name_conflicts, script_conflicts, entry_conflicts]):
        lines.append("*No conflicts detected.*")
        lines.append("")
        return

    if ver_conflicts:
        lines.append("### Dependency Version Conflicts")
        lines.append("")
        lines.append("| Package | Source | Target |")
        lines.append("|---------|--------|--------|")
        for c in ver_conflicts:
            lines.append(f"| `{c['name']}` | `{c['source_version']}` | `{c['target_version']}` |")
        lines.append("")

    if name_conflicts:
        lines.append("### File / Directory Name Conflicts")
        lines.append("")
        lines.append("| Type | Relative Path | Source Path | Target Path |")
        lines.append("|------|--------------|-------------|-------------|")
        for c in name_conflicts[:30]:
            lines.append(
                f"| {c['type']} | `{c['relative_path']}` | "
                f"`{c['source_path']}` | `{c['target_path']}` |"
            )
        if len(name_conflicts) > 30:
            lines.append(f"| ... | *and {len(name_conflicts) - 30} more* | | |")
        lines.append("")

    if script_conflicts:
        lines.append("### Script Name Conflicts")
        lines.append("")
        lines.append("| Script | Source Command | Target Command |")
        lines.append("|--------|---------------|---------------|")
        for c in script_conflicts:
            lines.append(f"| `{c['script']}` | `{c['source_cmd']}` | `{c['target_cmd']}` |")
        lines.append("")

    if entry_conflicts:
        lines.append("### Entry File Conflicts")
        lines.append("")
        lines.append(f"Both projects define: {', '.join(f'`{e}`' for e in entry_conflicts)}")
        lines.append("")


def _append_recommendations(lines: list[str], fusion: dict[str, Any]) -> None:
    recs = fusion.get("recommendations", [])
    lines.append("## Recommendations")
    lines.append("")
    for i, rec in enumerate(recs, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")


def _append_footer(lines: list[str]) -> None:
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generated by AetherFusion v{__version__} — Local Code Project Fusion Tool. "
        "No files were modified during this scan.*"
    )