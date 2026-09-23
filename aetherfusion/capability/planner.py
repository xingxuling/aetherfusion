"""Capability-level AetherFusion v2 alpha planner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .analyzer import analyze_project_capabilities
from .strategy import choose_strategy


CAPABILITY_FUSION_SCHEMA_VERSION = "2.0-alpha.1"


def generate_capability_fusion_plan(
    source: str | Path,
    target: str | Path,
    *,
    project_url: str | None = None,
) -> dict:
    source_profile = analyze_project_capabilities(source)
    target_profile = analyze_project_capabilities(target)
    target_ids = {c.capability_id for c in target_profile.capabilities}

    license_gate = source_profile.license.get("gate", "review_required")
    decisions = []
    for candidate in source_profile.capabilities:
        decision = choose_strategy(
            candidate,
            already_present=candidate.capability_id in target_ids,
            license_gate=license_gate,
        )
        decisions.append({
            "capability": candidate.to_dict(),
            "target_state": "overlap" if candidate.capability_id in target_ids else "gap",
            "decision": decision.to_dict(),
        })

    blocked = []
    if source_profile.license.get("legal_review_required"):
        blocked.append("license_review")
    if not decisions:
        blocked.append("no_recognized_capabilities")

    return {
        "schema_version": CAPABILITY_FUSION_SCHEMA_VERSION,
        "mode": "capability-fusion-plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source_profile.to_dict(),
        "source_project_url": project_url,
        "target": target_profile.to_dict(),
        "summary": {
            "recognized_source_capabilities": len(source_profile.capabilities),
            "recognized_target_capabilities": len(target_profile.capabilities),
            "gaps": sum(1 for d in decisions if d["target_state"] == "gap"),
            "overlaps": sum(1 for d in decisions if d["target_state"] == "overlap"),
            "blocked_gates": blocked,
        },
        "fusion_decisions": decisions,
        "execution_contract": {
            "read_only": True,
            "automatic_source_copy": False,
            "automatic_dependency_install": False,
            "automatic_config_write": False,
            "requires_explicit_apply_phase": True,
            "stages": [
                "license_gate",
                "capability_extract",
                "canonical_owner_map",
                "fusion_strategy_select",
                "adapter_port_or_native_organ_design",
                "isolated_branch_or_sandbox",
                "tests_and_benchmarks",
                "evidence_receipt",
                "commit_gate",
                "upstream_sync_plan",
            ],
        },
        "next_recommended_action": (
            "Review capability decisions, resolve license/canonical-owner gates, "
            "then generate implementation adapters or ports in an isolated branch."
        ),
    }
