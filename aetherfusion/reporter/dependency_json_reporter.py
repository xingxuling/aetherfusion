"""JSON reporter for dependency plan."""

import json
from pathlib import Path
from typing import Any


def write_dependency_json(output_path: Path, plan: dict[str, Any]) -> None:
    """Write the dependency plan as JSON to the given path.

    Args:
        output_path: Path to write the JSON file.
        plan: Dependency plan dict from dependency_planner.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
