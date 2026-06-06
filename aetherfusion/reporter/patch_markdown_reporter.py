"""Patch Markdown reporter — generates human-readable dry-run patch preview."""

import os
from pathlib import Path
from typing import Any


def generate_patch_report(manifest: dict[str, Any]) -> str:
    """Generate a Markdown patch preview report.

    Args:
        manifest: Patch manifest dict from dry_run_patch_generator.

    Returns:
        Markdown string.
    """
    summary = manifest.get("summary", {})
    ops = manifest.get("operations", [])
    module_name = manifest.get("module_name", "?")
    source_mod = manifest.get("source_module_path", "?")
    target_mod = manifest.get("target_match_path", "?")
    risk_level = manifest.get("risk_level", "?")
    strategy = manifest.get("strategy", "?")
    import_notes = [
        op for op in ops
        if op.get("type") == "add_file" and _has_import_notes(manifest)
    ]
    # Extract actual import notes from the manifest's operations
    import_notes_from_ops = [
        op for op in ops
        if op.get("type") == "add_file"
        and manifest.get("_import_notes") is not None
    ]

    lines: list[str] = []

    lines.append(f"# AetherFusion Dry-Run Patch Preview — `{module_name}`")
    lines.append("")
    lines.append("> **No source or target files were modified.**  ")
    lines.append("> This is a dry-run preview only.  ")
    lines.append(f"> Patch version: `{manifest.get('patch_version', '?')}`  ")
    lines.append(f"> Mode: `{manifest.get('mode', 'dry_run')}`  ")
    lines.append("")

    # ---- Summary ----
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Files to add | {summary.get('files_to_add', 0)} |")
    lines.append(f"| Files conflicted (same-name) | {summary.get('files_conflicted', 0)} |")
    lines.append(f"| Files skipped (unsafe) | {summary.get('files_skipped', 0)} |")
    lines.append(f"| Dependency updates required | {summary.get('dependency_updates_required', 0)} |")
    lines.append(f"| Blocked operations | {summary.get('blocked_operations', 0)} |")
    lines.append("")
    lines.append(f"- **Module**: `{module_name}`")
    lines.append(f"- **Risk Level**: `{risk_level}`")
    lines.append(f"- **Strategy**: `{strategy}`")
    lines.append(f"- **Source**: `{source_mod}`")
    lines.append(f"- **Target**: `{target_mod}`")
    lines.append("")

    # ---- Safe Additions ----
    add_ops = [op for op in ops if op.get("type") == "add_file"]
    if add_ops:
        lines.append("## 2. Safe Additions")
        lines.append("")
        lines.append("These files exist only in the source module and can be safely added to the target:")
        lines.append("")
        lines.append("| # | File | Size |")
        lines.append("|---|------|------|")
        for i, op in enumerate(add_ops, 1):
            size_kb = (op.get("file_size_bytes", 0) or 0) / 1024.0
            lines.append(f"| {i} | `{op['relative_path']}` | {size_kb:.1f} KB |")
        lines.append("")

    # ---- Conflicts ----
    conflict_ops = [op for op in ops if op.get("type") == "conflict_same_name"]
    if conflict_ops:
        lines.append("## 3. Conflicts Requiring Human Decision")
        lines.append("")
        lines.append("These files exist in BOTH source and target with the same relative path.")
        lines.append("They are **blocked** in this dry-run and will not be copied without explicit resolution:")
        lines.append("")
        lines.append("| # | File | Source | Target | Size |")
        lines.append("|---|------|--------|--------|------|")
        for i, op in enumerate(conflict_ops, 1):
            size_kb = (op.get("file_size_bytes", 0) or 0) / 1024.0
            src = op.get("source_absolute", "?")
            tgt = op.get("target_absolute", "?")
            lines.append(f"| {i} | `{op['relative_path']}` | {_short_path(src)} | {_short_path(tgt)} | {size_kb:.1f} KB |")
        lines.append("")

    # ---- Import / Dependency Notes ----
    if import_notes:
        lines.append("## 4. Import / Dependency Notes")
        lines.append("")
        lines.append("Some source files reference third-party imports that may need attention:")
        lines.append("")
        for op in add_ops:
            # Check if this op has associated import notes in the manifest
            pass  # Import notes are tracked separately in the manifest
        lines.append("_Import review details are available in the JSON patch manifest._")
        lines.append("")

    # ---- Skipped ----
    skip_ops = [op for op in ops if op.get("type") == "skip_unsafe"]
    if skip_ops:
        lines.append("## 5. Skipped Files (Unsafe)")
        lines.append("")
        lines.append("| # | File | Reason |")
        lines.append("|---|------|--------|")
        for i, op in enumerate(skip_ops, 1):
            lines.append(f"| {i} | `{op['relative_path']}` | {op.get('reason', '?')} |")
        lines.append("")

    # ---- Blocked Actions ----
    lines.append("## 6. Blocked Actions")
    lines.append("")
    for action in manifest.get("blocked_actions", []):
        lines.append(f"- {action}")
    lines.append("")

    # ---- Required Human Decisions ----
    decisions = manifest.get("required_human_decisions", [])
    if decisions:
        lines.append("## 7. Required Human Decisions")
        lines.append("")
        for d in decisions:
            lines.append(f"### {d['decision_id']}")
            lines.append("")
            lines.append(f"**{d['question']}**")
            lines.append("")
            lines.append(d.get("context", ""))
            lines.append("")
            lines.append("| Option | Description |")
            lines.append("|--------|-------------|")
            for opt in d.get("options", []):
                lines.append(f"| `{opt['value']}` | {opt.get('description', '')} |")
            blocking = "blocking" if d.get("is_blocking") else "non-blocking"
            lines.append(f"\n_Status: {blocking}_")
            lines.append("")
        lines.append("")

    # ---- Next Command ----
    lines.append("## 8. Next Recommended Command")
    lines.append("")
    lines.append("```bash")
    lines.append(manifest.get("next_recommended_command", "# (no recommendation available)"))
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**No source or target files were modified.**  ")
    lines.append(f"_Generated by AetherFusion v{manifest.get('patch_version', '?')} (dry-run mode)_")
    lines.append("")

    return "\n".join(lines)


def _has_import_notes(manifest: dict[str, Any]) -> bool:
    """Check whether the manifest contains any import notes."""
    notes = manifest.get("_import_notes", [])
    return bool(notes)


def _short_path(p: str, max_len: int = 40) -> str:
    """Shorten a long path for display."""
    if len(p) <= max_len:
        return p
    return "..." + p[-(max_len - 3):]