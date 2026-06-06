"""Session Markdown reporter — generates fusion-session.md."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aetherfusion.session.session_state import SessionState


def generate_session_report(state: "SessionState") -> str:
    """Generate the fusion-session.md Markdown report.

    Args:
        state: The completed session state.

    Returns:
        Markdown report string.
    """
    lines: list[str] = []

    # Title
    lines.append(f"# AetherFusion Session Report")
    lines.append("")
    lines.append(f"**Session ID:** `{state.session_id}`")
    lines.append(f"**Mode:** {state.mode}")
    lines.append("")

    # --- Session Summary ---
    lines.append("## Session Summary")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Session ID | `{state.session_id}` |")
    lines.append(f"| Mode | `{state.mode}` |")
    lines.append(f"| Apply | {'Yes' if state.options.get('apply_confirm') else 'No (dry-run only)'} |")
    lines.append(f"| Verify | {'Yes' if state.options.get('verify') else 'No'} |")
    lines.append(f"| Modules Requested | {len(state.modules)} |")
    lines.append(f"| Modules Succeeded | {len(state.succeeded_modules)} |")
    lines.append(f"| Modules Failed | {len(state.failed_modules)} |")
    if state.verify_result:
        vsum = state.verify_result.get("summary", {})
        lines.append(f"| Verify Passed | {state.verify_passed} |")
    lines.append("")

    # --- Source / Target ---
    lines.append("## Source / Target")
    lines.append("")
    lines.append(f"- **Source:** `{state.source_path}`")
    lines.append(f"- **Target:** `{state.target_path}`")
    lines.append("")

    # --- Modules Processed ---
    lines.append("## Modules Processed")
    lines.append("")
    lines.append("| Module | Status | Plan | Patch | Apply | Error |")
    lines.append("|--------|--------|------|-------|-------|-------|")
    for name in state.modules:
        mr = state.module_results.get(name)
        if mr:
            plan_str = "OK" if mr.plan_json_path else "-"
            patch_str = "OK" if mr.patch_json_path else "-"
            apply_str = "OK" if mr.apply_json_path else ("skipped" if state.options.get("apply_confirm") else "-")
            error_str = mr.error or ""
            lines.append(f"| {name} | {mr.status} | {plan_str} | {patch_str} | {apply_str} | {error_str} |")
        else:
            lines.append(f"| {name} | unknown | - | - | - | - |")
    lines.append("")

    # --- Scan Result ---
    lines.append("## Scan Result")
    lines.append("")
    if state.scan_report_path:
        lines.append(f"- **Report:** [{state.scan_report_path}](<{state.scan_report_path}>)")
    if state.scan_map_path:
        lines.append(f"- **Map:** [{state.scan_map_path}](<{state.scan_map_path}>)")
    lines.append("")

    # --- Per-Module Plan / Patch / Apply Summary ---
    lines.append("## Per-Module Plan / Patch / Apply Summary")
    lines.append("")
    for name in state.modules:
        mr = state.module_results.get(name)
        if not mr:
            continue
        lines.append(f"### {name} ({mr.status})")
        lines.append("")
        if mr.error:
            lines.append(f"> **Error:** {mr.error}")
            lines.append("")
        if mr.plan_json_path:
            lines.append(f"- Plan JSON: [{mr.plan_json_path}](<{mr.plan_json_path}>)")
        if mr.plan_md_path:
            lines.append(f"- Plan MD: [{mr.plan_md_path}](<{mr.plan_md_path}>)")
        if mr.patch_json_path:
            lines.append(f"- Patch JSON: [{mr.patch_json_path}](<{mr.patch_json_path}>)")
        if mr.patch_md_path:
            lines.append(f"- Patch MD: [{mr.patch_md_path}](<{mr.patch_md_path}>)")
        if mr.apply_json_path:
            lines.append(f"- Apply JSON: [{mr.apply_json_path}](<{mr.apply_json_path}>)")
        if mr.apply_md_path:
            lines.append(f"- Apply MD: [{mr.apply_md_path}](<{mr.apply_md_path}>)")
        if mr.rollback_manifest_path:
            lines.append(f"- Rollback: [{mr.rollback_manifest_path}](<{mr.rollback_manifest_path}>)")
        lines.append("")

    # --- Verify Result ---
    lines.append("## Verify Result")
    lines.append("")
    if state.verify_result:
        vsum = state.verify_result.get("summary", {})
        lines.append(f"- **Passed:** {state.verify_passed}")
        lines.append(f"- Total: {vsum.get('total', 0)} | Passed: {vsum.get('passed', 0)} | Failed: {vsum.get('failed', 0)} | Skipped: {vsum.get('skipped', 0)}")
        lines.append(f"- JSON: [{state.verify_json_path}](<{state.verify_json_path}>)")
        lines.append(f"- MD: [{state.verify_md_path}](<{state.verify_md_path}>)")
    else:
        lines.append("Verify was not run (`--verify` not set).")
    lines.append("")

    # --- Diagnostic Plans Generated ---
    lines.append("## Diagnostic Plans Generated")
    lines.append("")
    if state.diagnostic_plans_generated:
        for plan_name in state.diagnostic_plans_generated:
            lines.append(f"- **{plan_name}**")
            if plan_name == "repair-plan" and state.repair_plan_json_path:
                lines.append(f"  - JSON: [{state.repair_plan_json_path}](<{state.repair_plan_json_path}>)")
                lines.append(f"  - MD: [{state.repair_plan_md_path}](<{state.repair_plan_md_path}>)")
            elif plan_name == "import-fix-plan" and state.import_fix_plan_json_path:
                lines.append(f"  - JSON: [{state.import_fix_plan_json_path}](<{state.import_fix_plan_json_path}>)")
                lines.append(f"  - MD: [{state.import_fix_plan_md_path}](<{state.import_fix_plan_md_path}>)")
            elif plan_name == "dependency-plan" and state.dependency_plan_json_path:
                lines.append(f"  - JSON: [{state.dependency_plan_json_path}](<{state.dependency_plan_json_path}>)")
                lines.append(f"  - MD: [{state.dependency_plan_md_path}](<{state.dependency_plan_md_path}>)")
            elif plan_name == "config-plan" and state.config_plan_json_path:
                lines.append(f"  - JSON: [{state.config_plan_json_path}](<{state.config_plan_json_path}>)")
                lines.append(f"  - MD: [{state.config_plan_md_path}](<{state.config_plan_md_path}>)")
    else:
        lines.append("No diagnostic plans generated (verify passed or not run).")
    lines.append("")

    # --- Blocked Operations ---
    lines.append("## Blocked Operations")
    lines.append("")
    if state.blocked_operations:
        for op in state.blocked_operations:
            lines.append(f"- {op}")
    else:
        lines.append("None.")
    lines.append("")

    # --- Rollback Information ---
    lines.append("## Rollback Information")
    lines.append("")
    if state.rollback_manifests:
        for rb in state.rollback_manifests:
            lines.append(f"- [{rb}](<{rb}>)")
    else:
        lines.append("No rollback manifests (no apply performed).")
    lines.append("")

    # --- Artifact Index ---
    lines.append("## Artifact Index")
    lines.append("")
    if state.artifact_index_path:
        lines.append(f"- [{state.artifact_index_path}](<{state.artifact_index_path}>)")
    lines.append("")

    # --- Next Recommended Action ---
    lines.append("## Next Recommended Action")
    lines.append("")
    lines.append(state._build_next_action())
    lines.append("")

    # --- Errors ---
    if state.errors:
        lines.append("## Session Errors")
        lines.append("")
        for err in state.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)
