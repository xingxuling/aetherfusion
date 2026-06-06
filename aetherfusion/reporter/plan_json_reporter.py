"""Plan JSON reporter — serializes fusion plans to machine-readable JSON."""

import json
from pathlib import Path
from typing import Any


def generate_plan_json(plan: dict[str, Any]) -> dict[str, Any]:
    """Return the plan dict directly — it is already JSON-serializable.

    This function exists for API consistency and to allow future
    enrichment of the JSON output before serialization.

    Args:
        plan: Fusion plan dict from ``generate_fusion_plan``.

    Returns:
        The same dict, ready for JSON serialization.
    """
    return plan


def write_plan_json(output_path: Path, plan: dict[str, Any]) -> None:
    """Write a fusion plan dict to a JSON file.

    Args:
        output_path: Destination file path.
        plan: Fusion plan dict to serialize.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )