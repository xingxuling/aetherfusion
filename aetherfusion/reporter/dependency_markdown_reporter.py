"""Markdown reporter for dependency plan."""

from typing import Any


def _code_block(text: str) -> str:
    return f"`{text}`"


def _build_summary_section(plan: dict[str, Any]) -> str:
    s = plan.get("summary", {})
    lines = [
        "# Dependency Plan Report",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|------:|",
        f"| Extracted Dependency Errors | {s.get('total_extracted_dependency_errors', 0)} |",
        f"| Total Dependency Candidates | {s.get('total_dependency_candidates', 0)} |",
        f"| Add to Target | {s.get('add_to_target', 0)} |",
        f"| Review Version Conflict | {s.get('review_version_conflict', 0)} |",
        f"| Likely Not Dependency Issue | {s.get('likely_not_dependency_issue', 0)} |",
        f"| Manual Research Required | {s.get('manual_research', 0)} |",
        f"| Builtin / Stdlib (Skipped) | {s.get('builtin_or_stdlib_skipped', 0)} |",
        f"| Redirect to Import Fix | {s.get('redirect_to_import_fix', 0)} |",
        "",
        f"**Source Repair File**: {plan.get('source_repair_file', 'N/A')}  ",
        f"**Source Import Fix File**: {plan.get('source_import_fix_file', 'N/A')}  ",
        f"**Target Path**: {plan.get('target_path', 'N/A')}  ",
        f"**Source Path**: {plan.get('source_path', 'N/A')}  ",
        "",
    ]
    return "\n".join(lines)


def _build_extracted_errors_section(plan: dict[str, Any]) -> str:
    errors = plan.get("extracted_dependency_errors", [])
    if not errors:
        return "## Extracted Dependency Errors\n\n*No dependency errors extracted.*\n"

    lines = [
        "## Extracted Dependency Errors",
        "",
        "| # | Package | Ecosystem | Source | Severity | Originating Command |",
        "|---|---------|-----------|--------|----------|---------------------|",
    ]
    for i, err in enumerate(errors, 1):
        pkg = _code_block(err.get("package_name", "?"))
        eco = err.get("ecosystem", "?")
        src = err.get("source", "?")
        sev = err.get("severity", "?")
        cmd = _code_block(err.get("originating_command", "?")[:50])
        lines.append(f"| {i} | {pkg} | {eco} | {src} | {sev} | {cmd} |")

    return "\n".join(lines) + "\n"


def _build_detected_files_section(plan: dict[str, Any]) -> str:
    files = plan.get("dependency_files_detected", [])
    if not files:
        return "## Dependency Files Detected\n\n*No dependency manifest files detected.*\n"

    lines = [
        "## Dependency Files Detected",
        "",
    ]
    for f in files:
        lines.append(f"- `{f}`")
    return "\n".join(lines) + "\n"


def _build_candidates_section(plan: dict[str, Any]) -> str:
    candidates = plan.get("dependency_candidates", [])
    if not candidates:
        return "## Dependency Candidates\n\n*No dependency candidates generated.*\n"

    lines = [
        "## Dependency Candidates",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        pkg = _code_block(c.get("package_name", "?"))
        lines.extend([
            f"### {i}. {pkg}",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Ecosystem | {c.get('ecosystem', '?')} |",
            f"| Found in Source | {c.get('found_in_source', '?')} |",
            f"| Found in Target | {c.get('found_in_target', '?')} |",
            f"| Source Version | {c.get('source_version', '-')} |",
            f"| Target Version | {c.get('target_version', '-')} |",
            f"| Version Conflict | {c.get('version_conflict', '?')} |",
            f"| Likely Cause | {c.get('likely_cause', '?')} |",
            f"| Automation Eligibility | {c.get('automation_eligibility', '?')} |",
            f"| Risk Level | {c.get('risk_level', '?')} |",
            f"| Recommended Action | {c.get('recommended_action', '?')} |",
            "",
            "<details>",
            "<summary>Evidence</summary>",
            "",
            "```",
            c.get("evidence", ""),
            "```",
            "",
            "</details>",
            "",
        ])
    return "\n".join(lines)


def _build_version_conflicts_section(plan: dict[str, Any]) -> str:
    conflicts = [
        c for c in plan.get("dependency_candidates", [])
        if c.get("version_conflict")
    ]
    if not conflicts:
        return "## Version Conflicts\n\n*No version conflicts detected.*\n"

    lines = [
        "## Version Conflicts",
        "",
        "| Package | Source Version | Target Version |",
        "|---------|---------------|----------------|",
    ]
    for c in conflicts:
        pkg = _code_block(c.get("package_name", "?"))
        sv = c.get("source_version", "-")
        tv = c.get("target_version", "-")
        lines.append(f"| {pkg} | {sv} | {tv} |")

    return "\n".join(lines) + "\n"


def _build_builtin_stdlib_section(plan: dict[str, Any]) -> str:
    skipped = [
        c for c in plan.get("dependency_candidates", [])
        if c.get("likely_cause") == "builtin_or_stdlib_module"
    ]
    if not skipped:
        return "## Builtin / Stdlib Skipped\n\n*No builtin or stdlib modules were skipped.*\n"

    lines = [
        "## Builtin / Stdlib Skipped",
        "",
        "| Package | Ecosystem |",
        "|---------|-----------|",
    ]
    for c in skipped:
        pkg = _code_block(c.get("package_name", "?"))
        eco = c.get("ecosystem", "?")
        lines.append(f"| {pkg} | {eco} |")

    return "\n".join(lines) + "\n"


def _build_automation_section(plan: dict[str, Any]) -> str:
    candidates = plan.get("dependency_candidates", [])
    by_auto: dict[str, int] = {}
    for c in candidates:
        key = c.get("automation_eligibility", "manual_only")
        by_auto[key] = by_auto.get(key, 0) + 1

    lines = [
        "## Automation Eligibility",
        "",
        "| Eligibility | Count |",
        "|-------------|------:|",
    ]
    for key in ("manual_only", "plan_only", "safe_auto_candidate"):
        lines.append(f"| {key} | {by_auto.get(key, 0)} |")

    return "\n".join(lines) + "\n"


def _build_blocked_section(plan: dict[str, Any]) -> str:
    blocked = plan.get("blocked_actions", [])
    lines = [
        "## Blocked Actions",
        "",
    ]
    for b in blocked:
        lines.append(f"- {b}")

    next_cmd = plan.get("next_recommended_command", "")
    if next_cmd:
        lines.append("")
        lines.append("## Next Recommended Command")
        lines.append("")
        lines.append(f"```bash\n{next_cmd}\n```")

    return "\n".join(lines)


def generate_dependency_report(plan: dict[str, Any]) -> str:
    """Generate a Markdown dependency plan report.

    Args:
        plan: Dependency plan dict from dependency_planner.

    Returns:
        Markdown string.
    """
    sections = [
        _build_summary_section(plan),
        _build_extracted_errors_section(plan),
        _build_detected_files_section(plan),
        _build_candidates_section(plan),
        _build_version_conflicts_section(plan),
        _build_builtin_stdlib_section(plan),
        _build_automation_section(plan),
        _build_blocked_section(plan),
    ]
    return "\n".join(sections)
