"""Apply JSON reporter — serializes apply result to JSON."""

import json
from pathlib import Path
from typing import Any


def write_apply_json(json_path: Path, result: dict[str, Any]) -> None:
    """Serialize the apply result to a JSON file.

    Args:
        json_path: Output file path.
        result: The apply result dict from safe_apply.apply_patch.
    """
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)