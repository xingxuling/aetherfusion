"""Rollback JSON reporter — serializes rollback result to JSON."""

import json
from pathlib import Path
from typing import Any


def write_rollback_json(json_path: Path, result: dict[str, Any]) -> None:
    """Serialize the rollback result to a JSON file.

    Args:
        json_path: Output file path.
        result: The rollback result dict from safe_rollback.rollback_apply.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)