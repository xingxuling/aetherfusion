"""JSON and Markdown reports for capability fusion plans."""

from __future__ import annotations

import json
from pathlib import Path


def write_json(path: str | Path, plan: dict) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def generate_markdown(plan: dict) -> str:
    source = plan["source"]
    target = plan["target"]
    summary = plan["summary"]
    lines = [
        "# AetherFusion Capability Fusion Plan",
        "",
        f"- Schema: `{plan['schema_version']}`",
        f"- Source: `{source['root']}`",
        f"- Target: `{target['root']}`",
        f"- Source URL: `{plan.get('source_project_url') or 'not supplied'}`",
        f"- License gate: `{source['license']['gate']}` (`{source['license']['detected']}`)",
        "",
        "## Summary",
        "",
        f"- Recognized source capabilities: **{summary['recognized_source_capabilities']}**",
        f"- Target gaps: **{summary['gaps']}**",
        f"- Target overlaps: **{summary['overlaps']}**",
        f"- Blocked gates: `{', '.join(summary['blocked_gates']) or 'none'}`",
        "",
        "## Capability Decisions",
        "",
        "| Capability | Score | Layer | Target | Strategy | Status |",
        "|---|---:|---|---|---|---|",
    ]
    for item in plan["fusion_decisions"]:
        cap = item["capability"]
        decision = item["decision"]
        lines.append(
            f"| {cap['display_name']} | {cap['score']} | "
            f"{cap['canonical_layer']} / {cap['canonical_layer_zh']} | "
            f"{item['target_state']} | {decision['strategy']} | {decision['status']} |"
        )
    lines.extend(["", "## Evidence", ""])
    for item in plan["fusion_decisions"]:
        cap = item["capability"]
        lines.append(f"### {cap['display_name']}")
        lines.append("")
        lines.append(f"Strategy: **{item['decision']['strategy']}**")
        lines.append("")
        for evidence in cap.get("evidence", [])[:12]:
            lines.append(f"- `{evidence}`")
        lines.append("")
    lines.extend([
        "## Execution Contract",
        "",
        (
            "This alpha slice is planning-only and does not copy source code, "
            "install dependencies, or rewrite target configuration."
        ),
        "",
    ])
    for stage in plan["execution_contract"]["stages"]:
        lines.append(f"- `{stage}`")
    lines.extend([
        "",
        "## Next Recommended Action",
        "",
        plan["next_recommended_action"],
        "",
    ])
    return "\n".join(lines)


def write_markdown(path: str | Path, plan: dict) -> Path:
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generate_markdown(plan), encoding="utf-8")
    return out
