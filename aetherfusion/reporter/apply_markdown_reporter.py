"""Apply Markdown reporter — generates human-readable apply report."""

from typing import Any


def generate_apply_report(result: dict[str, Any]) -> str:
    """Generate a Markdown apply report from the apply result.

    Args:
        result: Apply result dict from safe_apply.apply_patch.

    Returns:
        Markdown string.
    """
    summary = result.get("summary", {})
    module_name = result.get("module_name", "?")
    target_path = result.get("target_match_path", "?")
    source_path = result.get("source_module_path", "?")
    rollback_path = result.get("rollback_manifest_path")

    applied = result.get("operations_applied", [])
    skipped = result.get("operations_skipped", [])
    blocked = result.get("operations_blocked", [])
    failed = result.get("operations_failed", [])

    lines: list[str] = []

    lines.append(f"# AetherFusion Apply Report — `{module_name}`")
    lines.append("")
    lines.append("> **v0.4 Only add_file operations were applied.**  ")
    lines.append("> No files were overwritten. No config files were modified.  ")
    lines.append(f"> Apply version: `{result.get('apply_version', '?')}`  ")
    lines.append(f"> Mode: `{result.get('mode', '?')}`  ")
    lines.append("")

    # Summary
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Files applied (copied) | {summary.get('files_applied', 0)} |")
    lines.append(f"| Files skipped | {summary.get('files_skipped', 0)} |")
    lines.append(f"| Files blocked | {summary.get('files_blocked', 0)} |")
    lines.append(f"| Files failed | {summary.get('files_failed', 0)} |")
    lines.append(f"| Directories created | {summary.get('directories_created', 0)} |")
    lines.append("")
    lines.append(f"- **Module**: `{module_name}`")
    lines.append(f"- **Source**: `{source_path}`")
    lines.append(f"- **Target**: `{target_path}`")
    if rollback_path:
        lines.append(f"- **Rollback manifest**: `{rollback_path}`")
    lines.append("")

    # Applied files
    if applied:
        lines.append("## 2. Files Applied (Copied)")
        lines.append("")
        lines.append("| # | Relative Path | Target Absolute |")
        lines.append("|---|---------------|-----------------|")
        for i, f in enumerate(applied, 1):
            lines.append(f"| {i} | `{f['relative_path']}` | `{f.get('target_absolute', '?')}` |")
        lines.append("")

    # Skipped files
    if skipped:
        lines.append("## 3. Files Skipped")
        lines.append("")
        lines.append("| # | Relative Path | Reason |")
        lines.append("|---|---------------|--------|")
        for i, f in enumerate(skipped, 1):
            lines.append(f"| {i} | `{f['relative_path']}` | {f.get('reason', '?')} |")
        lines.append("")

    # Blocked files
    if blocked:
        lines.append("## 4. Files Blocked")
        lines.append("")
        lines.append("These operations were blocked — v0.4 only supports `add_file`.")
        lines.append("")
        lines.append("| # | Relative Path | Reason |")
        lines.append("|---|---------------|--------|")
        for i, f in enumerate(blocked, 1):
            lines.append(f"| {i} | `{f['relative_path']}` | {f.get('reason', '?')} |")
        lines.append("")

    # Failed files
    if failed:
        lines.append("## 5. Files Failed")
        lines.append("")
        lines.append("| # | Relative Path | Reason |")
        lines.append("|---|---------------|--------|")
        for i, f in enumerate(failed, 1):
            lines.append(f"| {i} | `{f['relative_path']}` | {f.get('reason', '?')} |")
        lines.append("")
        lines.append("**Note:** Some files may have been applied successfully before failures occurred.  ")
        lines.append("Check the rollback manifest to undo applied files if needed.")
        lines.append("")

    # Rollback
    if rollback_path:
        lines.append("## 6. Rollback")
        lines.append("")
        lines.append(f"A rollback manifest has been saved to `{rollback_path}`.")
        lines.append("")
        lines.append("To undo this apply, delete each file listed under `created_files` in the manifest:")
        lines.append("")
        lines.append("```bash")
        lines.append(f"# Review the rollback manifest:")
        lines.append(f"cat {rollback_path}")
        lines.append("")
        lines.append("# Manual rollback — delete each created file:")
        for f in applied:
            lines.append(f"rm \"{f.get('target_absolute', '?')}\"")
        lines.append("```")
        lines.append("")

    # Next command
    lines.append("## 7. Next Recommended Command")
    lines.append("")
    lines.append("```bash")
    lines.append(result.get("next_recommended_command",
                            "# (no recommendation available)"))
    lines.append("```")
    lines.append("")

    # Safety recap
    lines.append("---")
    lines.append("")
    lines.append("**Safety recap (v0.4):**  ")
    lines.append("- Only `add_file` operations were applied.  ")
    lines.append("- No existing target files were overwritten.  ")
    lines.append("- No config files (package.json, requirements.txt, etc.) were modified.  ")
    lines.append("- No build/test/lint/typecheck was executed.  ")
    lines.append("- No network requests were made.  ")
    lines.append("")
    lines.append(f"_Generated by AetherFusion v{result.get('apply_version', '?')}_")
    lines.append("")

    return "\n".join(lines)