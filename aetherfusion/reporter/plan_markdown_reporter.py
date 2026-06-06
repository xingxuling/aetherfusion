"""Plan Markdown reporter — generates Markdown fusion plans."""

from datetime import datetime
from typing import Any

from aetherfusion import __version__


def generate_plan_report(plan: dict[str, Any]) -> str:
    """Generate a Markdown fusion plan report from the plan dict.

    Args:
        plan: Fusion plan dict from ``generate_fusion_plan``.

    Returns:
        Full Markdown report string.
    """
    lines: list[str] = []
    _append_header(lines, plan)
    _append_score_summary(lines, plan)
    _append_ordered_steps(lines, plan)
    _append_human_decisions(lines, plan)
    _append_blocked_actions(lines, plan)
    _append_footer(lines, plan)
    return "\n".join(lines) + "\n"


def _append_header(lines: list[str], plan: dict[str, Any]) -> None:
    module = plan.get("module_name", "unknown")
    risk = plan.get("risk_level", "unknown")
    strategy = plan.get("strategy", "unknown")

    lines.append(f"# AetherFusion Plan — `{module}`")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Plan Version:** {plan.get('plan_version', __version__)}")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Module | `{module}` |")
    lines.append(f"| Module Type | `{plan.get('module_type', 'unknown')}` |")
    lines.append(f"| Risk Level | **{risk.upper()}** |")
    lines.append(f"| Strategy | `{strategy}` |")
    lines.append(f"| Source Path | `{plan.get('source_module_path', '(none)')}` |")
    lines.append(f"| Target Path | `{plan.get('target_match_path', '(none)')}` |")
    lines.append("")

    # Source/Target project context
    sp = plan.get("source_project", {})
    tp = plan.get("target_project", {})
    lines.append("### Project Context")
    lines.append("")
    lines.append(f"- **Source:** `{sp.get('name', '?')}` — `{sp.get('path', '?')}`")
    lines.append(f"- **Target:** `{tp.get('name', '?')}` — `{tp.get('path', '?')}`")
    lines.append("")


def _append_score_summary(lines: list[str], plan: dict[str, Any]) -> None:
    scores = plan.get("score_summary", {})
    if not scores:
        return

    lines.append("## Score Summary")
    lines.append("")
    lines.append("| Metric | Score |")
    lines.append("|--------|-------|")
    lines.append(f"| Value Score | {scores.get('value_score', '—')} / 100 |")
    lines.append(f"| Portability Score | {scores.get('portability_score', '—')} / 100 |")
    lines.append(f"| Conflict Score | {scores.get('conflict_score', '—')} / 100 |")
    lines.append(f"| **Priority Score** | **{scores.get('priority_score', '—')}** |")
    lines.append("")


def _append_ordered_steps(lines: list[str], plan: dict[str, Any]) -> None:
    steps = plan.get("ordered_steps", [])
    lines.append("## Ordered Steps")
    lines.append("")

    if not steps:
        lines.append("*No steps defined.*")
        lines.append("")
        return

    for st in steps:
        step_num = st.get("step", "?")
        action = st.get("action", "unknown")
        desc = st.get("description", "")
        complexity = st.get("estimated_complexity", "unknown")
        details = st.get("details", {})

        lines.append(f"### Step {step_num}: `{action}`")
        lines.append("")
        lines.append(f">{desc}")
        lines.append("")
        lines.append(f"**Complexity:** {complexity}")
        lines.append("")

        if details:
            lines.append("| Key | Detail |")
            lines.append("|-----|--------|")
            for key, val in details.items():
                # Escape pipe characters in values
                safe_val = str(val).replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {key.replace('_', ' ').title()} | {safe_val} |")
            lines.append("")


def _append_human_decisions(lines: list[str], plan: dict[str, Any]) -> None:
    decisions = plan.get("required_human_decisions", [])
    lines.append("## Required Human Decisions")
    lines.append("")

    if not decisions:
        lines.append("*No human decisions required.*")
        lines.append("")
        return

    for d in decisions:
        did = d.get("decision_id", "?")
        question = d.get("question", "")
        context = d.get("context", "")
        blocking = d.get("is_blocking", False)
        options = d.get("options", [])

        blocking_label = "**BLOCKING**" if blocking else "Non-blocking"
        lines.append(f"### {blocking_label}: {question}")
        lines.append("")
        lines.append(f"*{context}*")
        lines.append("")

        if options:
            lines.append("| Option | Label | Description |")
            lines.append("|--------|-------|-------------|")
            for opt in options:
                val = opt.get("value", "")
                label = opt.get("label", "")
                desc = opt.get("description", "")
                safe_desc = str(desc).replace("|", "\\|")
                lines.append(f"| `{val}` | {label} | {safe_desc} |")
            lines.append("")


def _append_blocked_actions(lines: list[str], plan: dict[str, Any]) -> None:
    blocked = plan.get("blocked_actions", [])
    lines.append("## Blocked Actions")
    lines.append("")

    if not blocked:
        lines.append("*No actions blocked.*")
        lines.append("")
        return

    lines.append("The following actions are **blocked** by the current v0.2 planning-only scope:")
    lines.append("")
    for i, action in enumerate(blocked, 1):
        lines.append(f"{i}. {action}")
    lines.append("")


def _append_footer(lines: list[str], plan: dict[str, Any]) -> None:
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generated by AetherFusion v{plan.get('plan_version', __version__)} "
        f"— Plan mode (read-only). No files were modified.*"
    )
    lines.append("")
    next_cmd = plan.get("next_recommended_command", "")
    if next_cmd:
        lines.append(f"**Next Recommended Command:**")
        lines.append("")
        lines.append(f"```bash")
        lines.append(f"{next_cmd}")
        lines.append(f"```")