"""Fusion strategy selection for capability candidates."""

from __future__ import annotations

from dataclasses import dataclass, asdict

from .analyzer import CapabilityCandidate


@dataclass(frozen=True)
class StrategyDecision:
    capability_id: str
    strategy: str
    status: str
    reason: str
    blocked_by: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["blocked_by"] = list(self.blocked_by)
        data["next_actions"] = list(self.next_actions)
        return data


def choose_strategy(
    candidate: CapabilityCandidate,
    *,
    already_present: bool,
    license_gate: str,
) -> StrategyDecision:
    blocked: list[str] = []
    if license_gate in {"review_required", "boundary_required"}:
        blocked.append(f"license:{license_gate}")

    strategy = candidate.default_strategy
    status = "candidate"
    reason = candidate.rationale

    if already_present:
        strategy = "ADAPT" if strategy in {"WRAP", "FEDERATE", "ADAPT"} else "REVIEW"
        status = "overlap_review"
        reason = (
            "Target already exposes the same recognized capability; compare "
            "semantic ownership before introducing another implementation."
        )

    if license_gate == "boundary_required" and strategy in {"TRANSPLANT", "ABSORB", "ADAPT"}:
        strategy = "WRAP"
        status = "license_boundary"
        reason = (
            "Strong-copyleft/uncertain integration boundary detected; prefer "
            "an external adapter boundary until reviewed."
        )

    if license_gate == "review_required" and strategy == "TRANSPLANT":
        strategy = "REVIEW"
        status = "blocked_pending_review"
        reason = "Direct source transplantation is withheld until the license is confirmed."

    next_actions = (
        "confirm canonical owner and role",
        "capture source provenance and license notice",
        f"generate {strategy.lower()} integration design",
        "run target-side tests in an isolated branch/sandbox",
        "write evidence receipt and rollback path",
        "pass commit gate before authoritative integration",
    )
    return StrategyDecision(
        capability_id=candidate.capability_id,
        strategy=strategy,
        status=status,
        reason=reason,
        blocked_by=tuple(blocked),
        next_actions=next_actions,
    )
